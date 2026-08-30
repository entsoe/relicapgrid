"""PROF-driven SHACL + schema validation of all CGMES and NC instance files.

Instance files map to shape sets via the DX-PROF descriptors of the
application-profiles-library (prof_map.py), grouped so cross-file references
resolve, and validated in two passes: counting constraints per instance file
(scope=), everything else on the group frame. Schema conformance is a third,
shapes-independent pass straight from the export schema. Outputs: one grouped
SARIF per release + layer, full sh:ValidationReports per group, summary.md.

Run:
    uv run buildScripts/validate_instances.py --apl cgmes-3.0=.apl-main --apl ncp-2.4=.apl-ncp24
"""
import argparse
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

import pandas
import triplets
from triplets import cgmes_tools
from triplets.export_schema import schemas

from prof_map import build_prof_map

logging.getLogger("triplets.validation").setLevel(logging.ERROR)

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"
LEVEL_ICONS = {"error": "🔴", "warning": "🟠", "note": "🔵"}

RELEASES = {
    "cgmes-3.0": {"apl": ".apl-main", "kind": "cgmes", "rdf_map": schemas.ENTSOE_CGMES_3_0_0_552_ED1},
    "ncp-2.4": {"apl": ".apl-ncp24", "kind": "nc", "rdf_map": schemas.ENTSOE_NC_2_4_1_552_ED1},
    # "ncp-2.5": add once triplets ships an NC 2.5 export schema (rdf_map)
    # "cgmes-2.4": add once the APL publishes its PROF + SHACL
}

# Cross-cutting CGMES shapes referenced by no PROF descriptor (APL gap, filed
# as application-profiles-library#130)
CGMES_COMMON_SHACL = [
    "CGMES/SHACL/61970-600-1_AllProfiles-AP-Con-Complex-SHACL.ttl",
]

# Near-duplicates of Instance/Jotunheim/GridSituation/cimxml/ (kept dir wins)
DUPLICATE_GLOB = "Instance/Jotunheim/NetworkCode/*.xml"

# per-dataset semantics — evaluated per instance file, never on the union:
# counting must not see other files' rdf:about continuation, and each profile's
# sh:closed AllowedProperties list only applies to datasets of THAT profile
# (e.g. ssi:OrdinaryContingency-AllowedProperties allows 2 properties; run over
# a frame with CO data it would reject every legitimate Contingency property)
PER_DATASET = ("sh:minCount", "sh:maxCount", "sh:closed")


@dataclass
class FileInfo:
    path: str                 # repo-relative posix
    instance_id: str
    kind: str                 # "cgmes" | "nc"
    profile_uris: list
    area: str                 # Instance/<area>/...


@dataclass
class Group:
    name: str
    files: list               # FileInfo loaded into the frame (incl. context)
    report_paths: set         # paths whose violations are reported
    union_shapes: list        # Complex/AllProfiles shapes, run on the group frame
    dataset_shapes: dict      # instance_id -> [Simple shapes], run with scope=
    rdf_map: object


def scan_instances():
    """Parse every instance file once; classify by header profile declaration."""
    everything = sorted(str(p.relative_to(REPO_ROOT)) for p in REPO_ROOT.glob("Instance/**/*.xml"))
    duplicates = {p for p in everything if Path(p).match(DUPLICATE_GLOB)}
    files = [p for p in everything if p not in duplicates]
    skipped = [(p, "duplicate of GridSituation/cimxml") for p in sorted(duplicates)]

    frame = pandas.read_RDF(files, max_workers=os.cpu_count())

    # release routing policy over the header inventory: Model.profile => the
    # CGMES release, an ap.cim4.eu conformsTo => the NC release
    headers = cgmes_tools.get_loaded_profiles(frame)
    headers = headers.assign(path=[str(Path(v).resolve().relative_to(REPO_ROOT)) for v in headers["label"]])
    cgmes = headers[headers["KEY"] == "Model.profile"]
    nc = headers[(headers["KEY"] == "conformsTo") & headers["VALUE"].str.startswith("https://ap.cim4.eu/")]

    declared = {}
    for source, kind in ((cgmes, "cgmes"), (nc, "nc")):
        for row in source.itertuples():
            entry = declared.setdefault(str(row.INSTANCE_ID), (row.path, kind, set()))
            if entry[1] == kind:
                entry[2].add(row.VALUE)
    infos = [FileInfo(path, instance_id, kind, sorted(uris), Path(path).parts[1])
             for instance_id, (path, kind, uris) in sorted(declared.items(), key=lambda kv: kv[1][0])]
    skipped += [(p, "no application profile declared") for p in files if p not in {fi.path for fi in infos}]
    return frame, infos, skipped


def resolve_shapes(profile_uris, prof_map):
    """(shape paths, unmapped uris) for a set of declared profile URIs."""
    shapes, unmapped = set(), []
    for uri in profile_uris:
        profile = prof_map.get(uri)
        if profile is None:
            unmapped.append(uri)
        else:
            shapes.update(profile.shacl_paths)
    return sorted(shapes), unmapped


def is_dataset_shape(path):
    """Cost filter for the per-file pass: only these files carry counting
    constraints, so the Complex sh:sparql shapes are not re-run once per
    instance file. The semantic split is the PER_DATASET type filter."""
    return "-Con-Simple-" in path.name or path.name == "DatasetMetadata-AP-Con-SHACL.ttl"


def drop_boundary(paths):
    """EquipmentBoundary shapes (bundled into the EQ PROF) constrain Terminal/
    ConnectivityNode to boundary-legal classes — boundary datasets only."""
    return [p for p in paths if "EquipmentBoundary" not in p.name]


def shape_split(files, prof_map, keep_boundary=False):
    """(union_shapes, dataset_shapes, unmapped) for a set of reported files.

    union_shapes = everything (reference checks need the full group frame);
    dataset_shapes = the file's own Simple shapes, re-run per file with scope=
    for the cardinality constraints (see validate_group)."""
    union, dataset, unmapped = set(), {}, {}
    for fi in files:
        shapes, missing = resolve_shapes(fi.profile_uris, prof_map)
        if missing:
            unmapped[fi.path] = missing
            continue
        if not keep_boundary:
            shapes = drop_boundary(shapes)
        dataset[fi.instance_id] = [p for p in shapes if is_dataset_shape(p)]
        union.update(shapes)
    return sorted(union), dataset, unmapped


# Group policy — context files are loaded for reference resolution but their
# violations are reported only in their own group:
#   cgmes-<Area>         reported: the area's EQ/SSH/TP/SV  context: boundary + commonData
#   cgmes-boundary       reported: boundary + commonData    context: none (EQBD shapes kept)
#   cgmes-CGM-Jotunheim  reported: Jotunheim TP/SV + SSH_2  context: every TSO's EQ + boundary
#   nc-<Area>            reported: the area's NC files      context: the area's Grid + boundary
# Unmapped CGMES profiles hard-fail (the 4 URIs must always resolve);
# unmapped NC profiles skip the file with a summary note.
def build_cgmes_groups(infos, prof_map, apl_dir, rdf_map):
    grid = [fi for fi in infos if fi.kind == "cgmes"]
    boundary = [fi for fi in grid if fi.area in ("boundaryData", "commonData")]
    jotunheim = [fi for fi in grid if fi.area == "Jotunheim"]
    areas = sorted({fi.area for fi in grid} - {"boundaryData", "commonData", "Jotunheim"})

    common = [apl_dir / rel for rel in CGMES_COMMON_SHACL if (apl_dir / rel).exists()]

    def cgmes_group(name, reported, context):
        union, dataset, unmapped = shape_split(reported, prof_map, keep_boundary=(name == "cgmes-boundary"))
        if unmapped:
            raise SystemExit(f"unmapped CGMES Model.profile URIs (APL PROF broken?): {unmapped}")
        return Group(name, reported + context, {fi.path for fi in reported},
                     sorted(set(union) | set(common)), dataset, rdf_map)

    groups = [cgmes_group(f"cgmes-{area}", [fi for fi in grid if fi.area == area], boundary)
              for area in areas]
    groups.append(cgmes_group("cgmes-boundary", boundary, []))

    eq_files = [fi for fi in grid if fi.profile_uris[0].startswith("http://iec.ch/TC57/ns/CIM/CoreEquipment")
                and fi.area != "Jotunheim"]
    groups.append(cgmes_group("cgmes-CGM-Jotunheim", jotunheim, eq_files))
    return groups, []


def build_nc_groups(infos, prof_map, rdf_map):
    nc = [fi for fi in infos if fi.kind == "nc"]
    grid = [fi for fi in infos if fi.kind == "cgmes"]
    groups, skipped = [], []

    def area_name(fi):
        return "Jotunheim-GridSituation" if (fi.area, Path(fi.path).parts[2]) == ("Jotunheim", "GridSituation") else fi.area

    for area in sorted({area_name(fi) for fi in nc}):
        area_files = [fi for fi in nc if area_name(fi) == area]
        union, dataset, unmapped = shape_split(area_files, prof_map)
        skipped += [(path, f"unmapped profile URI: {', '.join(uris)}") for path, uris in unmapped.items()]
        mapped = [fi for fi in area_files if fi.path not in unmapped]
        if not mapped:
            continue
        base_area = area.split("-GridSituation")[0]
        context = [fi for fi in grid if fi.area in (base_area, "boundaryData", "commonData")]
        groups.append(Group(f"nc-{area}", mapped + context, {fi.path for fi in mapped},
                            union, dataset, rdf_map))
    return groups, skipped


def validate_group(frame, group):
    data = frame[frame["INSTANCE_ID"].isin({fi.instance_id for fi in group.files})]

    # reference checks need the group frame; cardinality must not see the
    # rdf:about continuation of other files, so it comes from per-file scope=
    union = data.shacl.validate(group.union_shapes, rdf_map=group.rdf_map)
    passes = []
    if len(union):
        passes.append(union[~union["VIOLATION_TYPE"].isin(PER_DATASET)])
    for instance_id, shapes in group.dataset_shapes.items():
        if shapes:
            per_file = data.shacl.validate(shapes, rdf_map=group.rdf_map, scope=[instance_id])
            if len(per_file):
                passes.append(per_file[per_file["VIOLATION_TYPE"].isin(PER_DATASET)])
    violations = pandas.concat(passes, ignore_index=True) if passes else union
    if violations.empty:
        return violations, violations
    # rdf:about continuation duplicates a fact across files — one finding per fact
    violations = violations.drop_duplicates(subset=["ID", "KEY", "VALUE", "VIOLATION_TYPE", "SOURCE_SHAPE"])

    all_shapes = sorted({str(p) for p in group.union_shapes}
                        | {str(p) for shapes in group.dataset_shapes.values() for p in shapes})
    enriched = violations.shacl.enrich(data=data, shapes=all_shapes, rdf_map=group.rdf_map)
    located = enriched.shacl.locate(sources=[fi.path for fi in group.files])

    reported = located[located["SOURCE_URI"].isin(group.report_paths) | located["SOURCE_URI"].isna()].copy()
    # shape-level meta findings (e.g. triplets:invalidSparql) carry no instance
    # line — anchor them to an in-repo path so GitHub can display the alert
    anchor = sorted(group.report_paths)[0]
    reported.loc[reported["SOURCE_URI"].isna(), "SOURCE_LINE"] = 1
    reported.loc[reported["SOURCE_URI"].isna(), "SOURCE_URI"] = anchor
    return located, reported


def run_schema_pass(frame, infos, config, release):
    """Schema conformance straight from the export schema, shapes-independent:
    each instance's declared profiles run separately against its own rows."""
    files = [fi for fi in infos if fi.kind == config["kind"]]
    data = frame[frame["INSTANCE_ID"].isin({fi.instance_id for fi in files})]
    violations = data.shacl.validate_schema(config["rdf_map"])
    if violations.empty:
        return None, files, violations
    located = violations.shacl.locate(sources=[fi.path for fi in files])
    sarif_path = located.shacl.to_sarif(path=REPORTS / f"schema-{release}.sarif")
    return json.loads(Path(sarif_path).read_text()), files, located


def export_release(release, frames):
    combined = pandas.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pandas.DataFrame()
    if combined.empty:
        return None
    meta = combined["VIOLATION_TYPE"].astype(str).str.contains("invalidSparql")
    combined = pandas.concat([combined[~meta],
                              combined[meta].drop_duplicates(subset=["VIOLATION_TYPE", "MESSAGE", "SOURCE_SHAPE"])],
                             ignore_index=True)
    sarif_path = combined.shacl.to_sarif(path=REPORTS / f"shacl-{release}.sarif")
    return json.loads(Path(sarif_path).read_text())


def rule_url(repo, branch, rule_id):
    """Code-scanning list filtered to one rule — links a summary row to its alerts."""
    query = quote_plus(f'is:open branch:{branch} rule:"{rule_id}"')
    return f"https://github.com/{repo}/security/code-scanning?query={query}"


def write_summary(release_sarifs, group_stats, skipped, gaps):
    lines = ["# SHACL validation — PROF-driven full sweep", ""]
    repo, branch = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_REF_NAME")
    if repo and branch:
        alerts = f"https://github.com/{repo}/security/code-scanning?query=is%3Aopen+branch%3A{branch}+tool%3A%22triplets-shacl%22"
        lines += [f"**[Open the code scanning alerts of this branch →]({alerts})**", "",
                  "Full sh:ValidationReports (turtle + RDF/XML) per group are attached as the `shacl-reports` artifact.", ""]

    lines += ["| group | files | errors | warnings | notes | seconds |", "|---|---|---|---|---|---|"]
    for name, file_count, severities, seconds in group_stats:
        lines.append(f"| `{name}` | {file_count} | {severities.get('Violation', 0)} | "
                     f"{severities.get('Warning', 0)} | {severities.get('Info', 0)} | {seconds:.1f} |")

    for release, sarif in release_sarifs.items():
        if sarif is None:
            continue
        lines += ["", f"## {release} rules (grouped)", "", "| rule | level | occurrences |", "|---|---|---|"]
        for result in sarif["runs"][0]["results"]:
            icon = LEVEL_ICONS.get(result["level"], "")
            count = result.get("occurrenceCount", len(result.get("locations", [])))
            rule = f"`{result['ruleId']}`"
            if repo and branch:
                rule = f"[{rule}]({rule_url(repo, branch, result['ruleId'])})"
            lines.append(f"| {rule} | {icon} {result['level']} | {count} |")

    if skipped:
        lines += ["", "## Skipped files", "", "| file | reason |", "|---|---|"]
        lines += [f"| `{path}` | {reason} |" for path, reason in skipped]
    if gaps:
        lines += ["", "## Profile library gaps", ""]
        lines += [f"- {gap}" for gap in sorted(set(gaps))]
    lines += ["", "Notes: Simple shapes run per instance file (scope=) so rdf:about continuation across a "
              "model set is not double-counted; Complex/AllProfiles shapes run on the group frame; "
              "EquipmentBoundary shapes run only on the boundary group; the cross-cutting AllProfiles "
              "shapes are added manually (no PROF references them); variant shape sets "
              "(SolvedMAS/NotSolvedMAS, CrossProfile, InverseAssociation; role/validation) are not run."]
    (REPORTS / "summary.md").write_text("\n".join(lines) + "\n")


def main():
    os.chdir(REPO_ROOT)  # relative source paths => repo-relative SARIF artifact URIs
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apl", action="append", default=[], metavar="RELEASE=PATH",
                        help="APL checkout per release, e.g. cgmes-3.0=.apl-main (repeatable)")
    parser.add_argument("--only", choices=sorted(RELEASES), help="run a single release")
    args = parser.parse_args()
    for override in args.apl:
        release, _, path = override.partition("=")
        RELEASES[release]["apl"] = path

    print("triplets", triplets.__version__)
    REPORTS.mkdir(exist_ok=True)
    frame, infos, skipped = scan_instances()
    print(f"parsed {len(frame):,} triples from {len(infos)} mapped files ({len(skipped)} skipped)")

    group_stats, release_sarifs, all_gaps = [], {}, []
    relations = cgmes_tools.get_model_relations(frame)
    missing = relations[relations["INSTANCE_ID_TO"].isna()]
    if len(missing):
        all_gaps += [f"declared model dependency not loaded: {row.ID_FROM} -[{row.KEY}]-> {row.ID_TO}"
                     for row in missing.itertuples()]
    print(f"model dependencies: {len(relations)} declared, {len(missing)} not loaded")
    for release, config in RELEASES.items():
        if args.only and release != args.only:
            continue
        apl_dir = Path(config["apl"]).resolve()
        prof_map, gaps = build_prof_map(apl_dir)
        all_gaps += [f"{release}: {g}" for g in gaps]
        if not prof_map:
            raise SystemExit(f"{release}: empty PROF map at {apl_dir}")

        if config["kind"] == "cgmes":
            groups, more_skipped = build_cgmes_groups(infos, prof_map, apl_dir, config["rdf_map"])
        else:
            groups, more_skipped = build_nc_groups(infos, prof_map, config["rdf_map"])
        skipped += more_skipped

        frames = []
        for group in groups:
            start = time.monotonic()
            located, reported = validate_group(frame, group)
            seconds = time.monotonic() - start
            severities = reported["SEVERITY"].value_counts().to_dict() if len(reported) else {}
            group_stats.append((group.name, len(group.report_paths), severities, seconds))
            print(f"{group.name}: {len(group.report_paths)} files, {seconds:.1f}s, {severities or 'conforms'}")
            if len(located):  # full unfiltered report incl. context-file findings
                for suffix in ("ttl", "xml"):
                    located.shacl.to_shacl_report(
                        path=REPORTS / f"{group.name}-shacl-report.{suffix}", report_source=group.name,
                        report_references=sorted({p.name for p in group.union_shapes}
                                                 | {p.name for s in group.dataset_shapes.values() for p in s}))
            frames.append(reported)
        release_sarifs[release] = export_release(release, frames)

        start = time.monotonic()
        schema_sarif, schema_files, schema_located = run_schema_pass(frame, infos, config, release)
        if schema_sarif:
            release_sarifs[f"schema-{release}"] = schema_sarif
            severities = schema_located["SEVERITY"].value_counts().to_dict()
            group_stats.append((f"schema-{release}", len(schema_files), severities, time.monotonic() - start))
            print(f"schema-{release}: {len(schema_files)} files, {time.monotonic() - start:.1f}s, {severities}")

    write_summary(release_sarifs, group_stats, skipped, all_gaps)
    for key, sarif in release_sarifs.items():
        if sarif:
            name = key if key.startswith("schema-") else f"shacl-{key}"
            print(f"wrote reports/{name}.sarif: {len(sarif['runs'][0]['results'])} grouped results")
    print(f"wrote {REPORTS / 'summary.md'}")


if __name__ == "__main__":
    main()
