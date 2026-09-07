"""PROF-driven SHACL + schema validation of all CGMES 3.0 and NCP 2.5 instance files.

Instance files map to shape sets via the DX-PROF descriptors of the
application-profiles-library (prof_map.py), grouped so cross-file references
resolve, and validated in two passes: per-dataset constraints per instance
file (scope=), everything else on the group frame. Schema conformance is a
third, shapes-independent pass straight from the export schema. Outputs: one
grouped SARIF per release + layer, full sh:ValidationReports per group,
summary.md.

NC files additionally run the *dependency-closure* variant side by side (each
file validated with its own PROF validation set over itself plus the transitive
`dcterms:requires` closure) — its SARIF is written for comparison only and the
per-rule diff lands in summary.md; the type-split result is what code scanning
gets until the closure variant is adopted.

Run:
    uv run buildScripts/validate_instances.py --apl cgmes-3.0=.apl-main --apl ncp-2.5=.apl-main
"""
import argparse
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

import pandas
import triplets
from triplets import cgmes_tools
from triplets.export_schema import schemas
from triplets.validation import compile as compile_shapes

from prof_map import build_prof_map, deactivated_shapes, import_closure

logging.getLogger("triplets.validation").setLevel(logging.ERROR)

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS = REPO_ROOT / "reports"
LEVEL_ICONS = {"error": "🔴", "warning": "🟠", "note": "🔵"}

# One APL checkout (main) carries both CGMES 3.0 and NCP 2.5 PROF + SHACL.
# The NCP 2.5-dev export schema is vendored (buildScripts/schemas/, provenance
# in SOURCE.json) until a triplets release ships it.
RELEASES = {
    "cgmes-3.0": {"apl": ".apl-main", "kind": "cgmes", "rdf_map": schemas.ENTSOE_CGMES_3_0_0_552_ED1},
    "ncp-2.5": {"apl": ".apl-main", "kind": "nc",
                "rdf_map": str(REPO_ROOT / "buildScripts/schemas/ENTSOE_NC_2.5-dev_552_ED1.json")},
}

# Cross-cutting shapes referenced by no PROF descriptor (APL gaps, CGMES one
# filed as application-profiles-library#130). The NC one is the APL's own
# "IGM and additional data" aggregate: every Complex shape file + Common, meant
# for the assembled union — exactly our union pass.
CGMES_COMMON_SHACL = ["CGMES/SHACL/61970-600-1_AllProfiles-AP-Con-Complex-SHACL.ttl"]
NC_COMMON_SHACL = ["NCP/SHACL/Validation/NCP-AP-Con-Complex-Validation-SHACL.ttl"]

# Header variants of the same datasets (identical rdf:about): the NetworkCode
# copy is the one the header checker maintains, so GridSituation/cimxml is the
# duplicate on this branch (the inverse of cgmes-3.0_ncp-2.4_tc-1.1)
DUPLICATE_GLOB = "Instance/Jotunheim/GridSituation/cimxml/*.xml"

# Superseded versions of a live dataset: validated on their own, never in a
# union frame (they duplicate the live dataset's objects)
VERSION_CHAIN_GLOB = "Instance/*/NetworkCode/cimxml/Dataset_version_dependency/*.xml"

# HARDCODED FIX — boundary datasets on this branch carry a dcat:Dataset header
# that declares only the vocabularies (CIM100#, nc/2.4#), no application
# profile. In CGMES 3.0 the boundary is a small EQ dataset (EQBD was folded
# into EQ), so the header should declare conformsTo CoreEquipment-EU/3.0 (it is
# in the repo's own ConformTo-Collection). Until the data is fixed upstream the
# EQ profile is assumed here; remove once the headers declare it (#395).
BOUNDARY_PROFILE_FIX = ("Instance/boundaryData/", "http://iec.ch/TC57/ns/CIM/CoreEquipment-EU/3.0")

# per-dataset semantics — evaluated per instance file, never on the union:
# counting must not see other files' rdf:about continuation, and each profile's
# sh:closed AllowedProperties list only applies to datasets of THAT profile
# (e.g. ssi:OrdinaryContingency-AllowedProperties allows 2 properties; run over
# a frame with CO data it would reject every legitimate Contingency property).
# Shapes that count "in the data graph" (ClassCount, PrefixDeclaration) are
# per-dataset by construction — identified by shape id, see dataset_shape_ids.
PER_DATASET = ("sh:minCount", "sh:maxCount", "sh:closed")
PER_DATASET_SHAPE_FILES = {"NC-AP-Con-ClassCount-Complex-SHACL.ttl", "NC-AP-Con-PrefixDeclaration-Complex-SHACL.ttl"}


@dataclass
class FileInfo:
    path: str                 # repo-relative posix
    instance_id: str
    kind: str                 # "cgmes" | "nc"
    profile_uris: list
    area: str                 # Instance/<area>/...
    superseded: bool = False  # version-chain member: per-dataset passes only


@dataclass
class Group:
    name: str
    files: list               # FileInfo loaded into the frame (incl. context)
    report_paths: set         # paths whose violations are reported
    union_shapes: list        # cross-file shapes, run on the group frame
    dataset_shapes: dict      # instance_id -> [per-dataset shapes], run with scope=
    rdf_map: object
    closure_common: list = field(default_factory=list)  # NC only: AllComplex closure for the closure variant


def scan_instances():
    """Parse every instance file once; classify by header profile declaration."""
    everything = sorted(str(p.relative_to(REPO_ROOT)) for p in REPO_ROOT.glob("Instance/**/*.xml"))
    duplicates = {p for p in everything if Path(p).match(DUPLICATE_GLOB)}
    files = [p for p in everything if p not in duplicates]
    skipped = [(p, "duplicate of Jotunheim/NetworkCode") for p in sorted(duplicates)]

    frame = pandas.read_RDF(files, max_workers=os.cpu_count())

    # release routing policy over the header inventory: Model.profile => the
    # CGMES release, an ap.cim4.eu conformsTo => the NC release
    headers = cgmes_tools.get_loaded_profiles(frame)
    headers = headers.assign(path=[str(Path(v).resolve().relative_to(REPO_ROOT)) for v in headers["label"]])
    cgmes = headers[headers["KEY"] == "Model.profile"]
    nc = headers[(headers["KEY"] == "conformsTo") & headers["VALUE"].str.startswith("https://ap.cim4.eu/")]
    boundary_prefix, boundary_profile = BOUNDARY_PROFILE_FIX
    boundary = headers[headers["path"].str.startswith(boundary_prefix)
                       & ~headers["path"].isin(set(cgmes["path"]) | set(nc["path"]))].assign(VALUE=boundary_profile)

    declared = {}
    for source, kind in ((cgmes, "cgmes"), (nc, "nc"), (boundary, "cgmes")):
        for row in source.itertuples():
            entry = declared.setdefault(str(row.INSTANCE_ID), (row.path, kind, set()))
            if entry[1] == kind:
                entry[2].add(row.VALUE)
    infos = [FileInfo(path, instance_id, kind, sorted(uris), Path(path).parts[1],
                      superseded=Path(path).match(VERSION_CHAIN_GLOB))
             for instance_id, (path, kind, uris) in sorted(declared.items(), key=lambda kv: kv[1][0])]
    skipped += [(p, "no application profile declared") for p in files if p not in {fi.path for fi in infos}]
    fixed = sorted(set(boundary["path"]))
    return frame, infos, skipped, fixed


def resolve_shapes(profile_uris, prof_map, attribute="shacl_paths"):
    """(shape paths, unmapped uris) for a set of declared profile URIs."""
    shapes, unmapped = set(), []
    for uri in profile_uris:
        profile = prof_map.get(uri)
        if profile is None:
            unmapped.append(uri)
        else:
            shapes.update(getattr(profile, attribute))
    return sorted(shapes), unmapped


def is_dataset_shape(path):
    """CGMES cost filter for the per-file pass: only these files carry counting
    constraints, so the Complex sh:sparql shapes are not re-run once per
    instance file. The semantic split is the PER_DATASET type filter."""
    return "-Con-Simple-" in path.name


def drop_boundary(paths):
    """EquipmentBoundary shapes (bundled into the EQ PROF) constrain Terminal/
    ConnectivityNode to boundary-legal classes — boundary datasets only."""
    return [p for p in paths if "EquipmentBoundary" not in p.name]


def shape_split(files, prof_map, keep_boundary=False):
    """(union_shapes, dataset_shapes, unmapped) for a set of reported files.

    CGMES: union = every constraints shape (reference checks need the group
    frame); dataset = the file's Simple shapes, re-run per file with scope=.
    NC 2.5: dataset = the PROF `role/validation` closure (the APL's own
    per-dataset set, cross-dataset value types deactivated); union = the same
    closure (deactivations kept) — the Complex shapes join via NC_COMMON_SHACL."""
    union, dataset, unmapped = set(), {}, {}
    for fi in files:
        attribute = "validation_paths" if fi.kind == "nc" else "shacl_paths"
        shapes, missing = resolve_shapes(fi.profile_uris, prof_map, attribute)
        if missing or not shapes:
            unmapped[fi.path] = missing or fi.profile_uris
            continue
        if fi.kind == "cgmes" and not keep_boundary:
            shapes = drop_boundary(shapes)
        dataset[fi.instance_id] = [p for p in shapes if is_dataset_shape(p)] if fi.kind == "cgmes" else shapes
        union.update(shapes)
    return sorted(union), dataset, unmapped


def common_shapes(apl_dir, relative_paths, family):
    """Cross-cutting shape files resolved in the checkout, import closures expanded."""
    paths = []
    for rel in relative_paths:
        path = apl_dir / rel
        if path.exists():
            closure, _ = import_closure(path, apl_dir, family)
            paths.extend(closure)
    return sorted(set(paths))


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
    common = common_shapes(apl_dir, CGMES_COMMON_SHACL, "CGMES")

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
                and fi.area not in ("Jotunheim", "boundaryData", "commonData")]
    groups.append(cgmes_group("cgmes-CGM-Jotunheim", jotunheim, eq_files + boundary))
    return groups, []


def build_nc_groups(infos, prof_map, apl_dir, rdf_map):
    nc = [fi for fi in infos if fi.kind == "nc"]
    grid = [fi for fi in infos if fi.kind == "cgmes"]
    common = common_shapes(apl_dir, NC_COMMON_SHACL, "NCP")
    groups, skipped = [], []

    for area in sorted({fi.area for fi in nc}):
        area_files = [fi for fi in nc if fi.area == area]
        union, dataset, unmapped = shape_split(area_files, prof_map)
        skipped += [(path, f"unmapped profile URI: {', '.join(uris)}") for path, uris in unmapped.items()]
        mapped = [fi for fi in area_files if fi.path not in unmapped]
        if not mapped:
            continue
        context = [fi for fi in grid if fi.area in (area, "boundaryData", "commonData")]
        groups.append(Group(f"nc-{area}", mapped + context, {fi.path for fi in mapped},
                            sorted(set(union) | set(common)), dataset, rdf_map, closure_common=common))
    return groups, skipped


def shape_ids(shapes):
    """Shape ids declared by *shapes* (compile is cached — the same files are
    compiled for validation anyway)."""
    shapes = sorted({str(p) for p in shapes})
    return set(compile_shapes(shapes).ir["shape_id"]) if shapes else set()


def per_dataset_mask(violations, per_file_ids, count_ids):
    """Findings the per-file pass owns: a per-dataset constraint type, a
    data-graph counting shape, or a class-membership check (AllowedClasses:
    sh:in on rdf:type — "this class is not part of the profile" is about the
    dataset, not the union) — but only from shapes the per-file pass actually
    re-runs; a counting constraint of a union-only shape (e.g. Common-Complex
    dangling-reference checks) stays with the union pass."""
    rerun = violations["SOURCE_SHAPE"].isin(per_file_ids)
    class_membership = (violations["VIOLATION_TYPE"] == "sh:in") & (violations["KEY"].str.lower() == "type")
    return rerun & (violations["VIOLATION_TYPE"].isin(PER_DATASET) | violations["SOURCE_SHAPE"].isin(count_ids)
                    | class_membership)


def finish(violations, data, group, shapes):
    """Drop deactivated shapes → dedupe → enrich → locate → filter to the group's reported files."""
    if violations.empty:
        return violations, violations
    # triplets 0.2.0 evaluates sh:deactivated shapes; honour the APL switch-off here
    violations = violations[~violations["SOURCE_SHAPE"].astype(str).isin(deactivated_shapes(shapes))]
    # rdf:about continuation duplicates a fact across files — one finding per fact
    violations = violations.drop_duplicates(subset=["ID", "KEY", "VALUE", "VIOLATION_TYPE", "SOURCE_SHAPE"])
    enriched = violations.shacl.enrich(data=data, shapes=sorted({str(p) for p in shapes}), rdf_map=group.rdf_map)
    located = enriched.shacl.locate(sources=[fi.path for fi in group.files])

    reported = located[located["SOURCE_URI"].isin(group.report_paths) | located["SOURCE_URI"].isna()].copy()
    # shape-level meta findings (e.g. triplets:invalidSparql) carry no instance
    # line — anchor them to an in-repo path so GitHub can display the alert
    anchor = sorted(group.report_paths)[0]
    reported.loc[reported["SOURCE_URI"].isna(), "SOURCE_LINE"] = 1
    reported.loc[reported["SOURCE_URI"].isna(), "SOURCE_URI"] = anchor
    return located, reported


def all_shapes(group):
    return sorted({str(p) for p in group.union_shapes}
                  | {str(p) for shapes in group.dataset_shapes.values() for p in shapes})


def validate_group(frame, group):
    """Type-split passes: union for reference checks, per-file scope= for
    per-dataset constraints (cardinality, closed, data-graph counts)."""
    by_id = {fi.instance_id: fi for fi in group.files}
    data = frame[frame["INSTANCE_ID"].isin(set(by_id))]
    live = data[~data["INSTANCE_ID"].isin({i for i, fi in by_id.items() if fi.superseded})]
    per_file_shapes = {p for shapes in group.dataset_shapes.values() for p in shapes}
    per_file_ids = shape_ids(per_file_shapes)
    count_ids = shape_ids(p for p in per_file_shapes if p.name in PER_DATASET_SHAPE_FILES)

    union = live.shacl.validate(group.union_shapes, rdf_map=group.rdf_map)
    passes = []
    if len(union):
        passes.append(union[~per_dataset_mask(union, per_file_ids, count_ids)])
    context_ids = [i for i, fi in by_id.items() if fi.kind == "cgmes"]
    for instance_id, shapes in group.dataset_shapes.items():
        if not shapes:
            continue
        per_file = data.shacl.validate(shapes, rdf_map=group.rdf_map, scope=[instance_id])
        if len(per_file):
            passes.append(per_file[per_dataset_mask(per_file, per_file_ids, count_ids)])
        if by_id[instance_id].superseded:
            # never in the union: its reference checks run here, against the grid context
            own_ids = set(data.loc[data["INSTANCE_ID"].astype(str) == instance_id, "ID"].astype(str))
            references = data.shacl.validate(shapes, rdf_map=group.rdf_map, scope=[instance_id] + context_ids)
            if len(references):
                passes.append(references[~per_dataset_mask(references, per_file_ids, count_ids)
                                         & references["ID"].astype(str).isin(own_ids)])
    violations = pandas.concat(passes, ignore_index=True) if passes else union
    return finish(violations, data, group, all_shapes(group))


def dependency_closure(relations, instance_id):
    """Transitive Model.DependentOn / requires closure over loaded instances."""
    edges = relations.dropna(subset=["INSTANCE_ID_TO"])
    edges = dict(edges.groupby("INSTANCE_ID_FROM")["INSTANCE_ID_TO"].apply(lambda s: set(map(str, s))))
    closure, queue = set(), [instance_id]
    while queue:
        current = queue.pop()
        for dependency in edges.get(current, ()):
            if dependency not in closure:
                closure.add(dependency)
                queue.append(dependency)
    return closure


def validate_group_closure(frame, group, relations):
    """Dependency-closure variant (NC) — differs from validate_group only in
    the scope of the reference checks: each file's PROF validation set runs
    over the file + its transitive dependency closure instead of the area
    union, keeping the findings whose focus node lives in the file (emulates
    focus-node scoping; the APL deactivations decide what is cross-dataset).
    Per-dataset constraints stay on the file's own graph — sh:closed and the
    counts are about the dataset, and rdf:about continuation would otherwise
    hand the file its dependencies' properties — and the AllComplex aggregate
    runs once on the live group frame. Files without any loaded dependency
    fall back to the group frame (listed in the summary)."""
    by_id = {fi.instance_id: fi for fi in group.files}
    data = frame[frame["INSTANCE_ID"].isin(set(by_id))]
    live = data[~data["INSTANCE_ID"].isin({i for i, fi in by_id.items() if fi.superseded})]
    per_file_shapes = {p for shapes in group.dataset_shapes.values() for p in shapes}
    per_file_ids = shape_ids(per_file_shapes)
    count_ids = shape_ids(p for p in per_file_shapes if p.name in PER_DATASET_SHAPE_FILES)
    passes, fallbacks = [], []
    for instance_id, shapes in group.dataset_shapes.items():
        closure = dependency_closure(relations, instance_id)
        if not closure:
            fallbacks.append(by_id[instance_id].path)
        scope = ({instance_id} | closure) if closure else set(by_id)
        own_ids = set(frame.loc[frame["INSTANCE_ID"].astype(str) == instance_id, "ID"].astype(str))
        referencing = frame.shacl.validate(shapes, rdf_map=group.rdf_map, scope=sorted(scope))
        if len(referencing):
            passes.append(referencing[~per_dataset_mask(referencing, per_file_ids, count_ids)
                                      & referencing["ID"].astype(str).isin(own_ids)])
        per_file = data.shacl.validate(shapes, rdf_map=group.rdf_map, scope=[instance_id])
        if len(per_file):
            passes.append(per_file[per_dataset_mask(per_file, per_file_ids, count_ids)])
    if group.closure_common:
        union = live.shacl.validate(group.closure_common, rdf_map=group.rdf_map)
        if len(union):
            passes.append(union)
    violations = pandas.concat(passes, ignore_index=True) if passes else pandas.DataFrame()
    located, reported = finish(violations, data, group, all_shapes(group))
    return reported, fallbacks


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


def export_release(name, frames):
    combined = pandas.concat([f for f in frames if not f.empty], ignore_index=True) if frames else pandas.DataFrame()
    if combined.empty:
        return None
    meta = combined["VIOLATION_TYPE"].astype(str).str.contains("invalidSparql")
    combined = pandas.concat([combined[~meta],
                              combined[meta].drop_duplicates(subset=["VIOLATION_TYPE", "MESSAGE", "SOURCE_SHAPE"])],
                             ignore_index=True)
    sarif_path = combined.shacl.to_sarif(path=REPORTS / f"{name}.sarif")
    return json.loads(Path(sarif_path).read_text())


def rule_counts(sarif):
    return {r["ruleId"]: r.get("occurrenceCount", len(r.get("locations", [])))
            for r in (sarif["runs"][0]["results"] if sarif else [])}


def rule_url(repo, branch, rule_id):
    """Code-scanning list filtered to one rule — links a summary row to its alerts."""
    query = quote_plus(f'is:open branch:{branch} rule:"{rule_id}"')
    return f"https://github.com/{repo}/security/code-scanning?query={query}"


def write_summary(release_sarifs, group_stats, skipped, gaps, fixed, closure):
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

    for release, (split_sarif, closure_sarif, fallbacks, seconds) in closure.items():
        split, clos = rule_counts(split_sarif), rule_counts(closure_sarif)
        lines += ["", f"## {release}: dependency-closure variant vs type split ({seconds:.0f}s, comparison only)", "",
                  "Reference checks of each NC file run over itself + its transitive `dcterms:requires` "
                  "closure (focus nodes of the file only) instead of the area union; per-dataset "
                  "constraints and AllComplex as in the main run. Not uploaded to code scanning.", "",
                  "| rule | type split | closure | delta |", "|---|---|---|---|"]
        for rule in sorted(set(split) | set(clos), key=lambda r: (-(clos.get(r, 0) - split.get(r, 0)), r)):
            a, b = split.get(rule, 0), clos.get(rule, 0)
            if a != b:
                lines.append(f"| `{rule}` | {a} | {b} | {b - a:+d} |")
        lines.append(f"| **total** | {sum(split.values())} | {sum(clos.values())} | {sum(clos.values()) - sum(split.values()):+d} |")
        if fallbacks:
            lines += ["", "Files without a loaded dependency (validated on the group frame instead):", ""]
            lines += [f"- `{p}`" for p in sorted(fallbacks)]

    if fixed:
        lines += ["", "## Hardcoded header fix", "",
                  f"Boundary datasets declare no application profile; validated as `{BOUNDARY_PROFILE_FIX[1]}` "
                  "(CGMES 3.0: the boundary is a small EQ dataset). Fix the headers upstream, then drop the fix:", ""]
        lines += [f"- `{p}`" for p in fixed]
    if skipped:
        lines += ["", "## Skipped files", "", "| file | reason |", "|---|---|"]
        lines += [f"| `{path}` | {reason} |" for path, reason in skipped]
    if gaps:
        lines += ["", "## Profile library gaps", ""]
        lines += [f"- {gap}" for gap in sorted(set(gaps))]
    lines += ["", "Notes: per-dataset constraints (cardinality, sh:closed, data-graph counts) run per instance "
              "file (scope=) so rdf:about continuation across a model set is not double-counted; everything "
              "else runs on the group frame; superseded dataset versions never join a union frame; NC shape "
              "sets are the PROF role/validation aggregates (APL deactivations honoured) plus the AllComplex "
              "aggregate; EquipmentBoundary shapes run only on the boundary group; the cross-cutting CGMES "
              "AllProfiles and NC AllComplex shapes are added manually (no PROF references them); variant "
              "CGMES shape sets (SolvedMAS/NotSolvedMAS, CrossProfile, InverseAssociation) are not run."]
    (REPORTS / "summary.md").write_text("\n".join(lines) + "\n")


def main():
    os.chdir(REPO_ROOT)  # relative source paths => repo-relative SARIF artifact URIs
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apl", action="append", default=[], metavar="RELEASE=PATH",
                        help="APL checkout per release, e.g. cgmes-3.0=.apl-main (repeatable)")
    parser.add_argument("--only", choices=sorted(RELEASES), help="run a single release")
    parser.add_argument("--no-closure", action="store_true", help="skip the dependency-closure comparison run")
    args = parser.parse_args()
    for override in args.apl:
        release, _, path = override.partition("=")
        RELEASES[release]["apl"] = path

    print("triplets", triplets.__version__)
    REPORTS.mkdir(exist_ok=True)
    frame, infos, skipped, fixed = scan_instances()
    print(f"parsed {len(frame):,} triples from {len(infos)} mapped files ({len(skipped)} skipped, "
          f"{len(fixed)} boundary headers fixed)")

    group_stats, release_sarifs, closure, all_gaps = [], {}, {}, []
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
            groups, more_skipped = build_nc_groups(infos, prof_map, apl_dir, config["rdf_map"])
        skipped += more_skipped

        frames, closure_frames, fallbacks, closure_seconds = [], [], [], 0.0
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
                        report_references=sorted({Path(p).name for p in all_shapes(group)}))
            frames.append(reported)
            if config["kind"] == "nc" and not args.no_closure:
                start = time.monotonic()
                reported_closure, group_fallbacks = validate_group_closure(frame, group, relations)
                closure_seconds += time.monotonic() - start
                closure_frames.append(reported_closure)
                fallbacks += group_fallbacks
        release_sarifs[release] = export_release(f"shacl-{release}", frames)
        if closure_frames:
            closure[release] = (release_sarifs[release], export_release(f"closure-{release}", closure_frames),
                                fallbacks, closure_seconds)
            print(f"closure-{release}: {closure_seconds:.1f}s, {sum(rule_counts(closure[release][1]).values())} findings")

        start = time.monotonic()
        schema_sarif, schema_files, schema_located = run_schema_pass(frame, infos, config, release)
        if schema_sarif:
            release_sarifs[f"schema-{release}"] = schema_sarif
            severities = schema_located["SEVERITY"].value_counts().to_dict()
            group_stats.append((f"schema-{release}", len(schema_files), severities, time.monotonic() - start))
            print(f"schema-{release}: {len(schema_files)} files, {time.monotonic() - start:.1f}s, {severities}")

    write_summary(release_sarifs, group_stats, skipped, all_gaps, fixed, closure)
    for key, sarif in release_sarifs.items():
        if sarif:
            name = key if key.startswith("schema-") else f"shacl-{key}"
            print(f"wrote reports/{name}.sarif: {len(sarif['runs'][0]['results'])} grouped results")
    print(f"wrote {REPORTS / 'summary.md'}")


if __name__ == "__main__":
    main()
