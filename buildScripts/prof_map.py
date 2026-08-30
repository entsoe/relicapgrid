"""Map profile URIs to SHACL shape files via the DX-PROF descriptors of the
ENTSO-E application-profiles-library (APL).

An instance file declares its profile as `md:Model.profile` (CGMES) or
`dcterms:conformsTo` (NC). Each APL PROF descriptor carries the matching keys
(`rdf:about`, `owl:versionIRI`, `owl:priorVersion`) and, per resource, the
role and artifact. Only `role/constraints` resources that conform to SHACL are
returned; artifacts are resolved by basename against `<family>/SHACL/` then
`<family>/RDFS/` (CGMES artifacts are bare filenames, NCP ones absolute URLs —
neither resolves as a relative URI).

Debug CLI:  python buildScripts/prof_map.py <apl_dir>
"""
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import pandas
import triplets  # noqa: F401  (registers pandas.read_RDF)

ROLE_CONSTRAINTS = "role/constraints"
SHACL_MARK = "http://www.w3.org/ns/shacl"


@dataclass
class ProfileShapes:
    prof_file: str
    family: str                                # "CGMES" | "NCP"
    keys: set = field(default_factory=set)     # about + versionIRI + priorVersion URIs
    shacl_paths: list = field(default_factory=list)
    missing_artifacts: list = field(default_factory=list)


def _artifact_basename(value):
    return PurePosixPath(urlparse(str(value)).path).name


def _resolve_artifact(apl_dir, family, basename):
    for subdir in ("SHACL", "RDFS"):
        candidate = apl_dir / family / subdir / basename
        if candidate.exists():
            return candidate
    return None


def build_prof_map(apl_dir):
    """Return ({key_uri: ProfileShapes}, gap_messages) for one APL checkout."""
    apl_dir = Path(apl_dir)
    prof_files = sorted(path for family in ("CGMES", "NCP") for path in apl_dir.glob(f"{family}/PROF/*.rdf"))
    if not prof_files:
        return {}, [f"no PROF files under {apl_dir}/(CGMES|NCP)/PROF"]

    data = pandas.read_RDF([str(p) for p in prof_files])
    by_basename = {p.name: p for p in prof_files}

    prof_map, gaps = {}, []
    for instance_id, rows in data.groupby("INSTANCE_ID"):
        labels = rows.loc[rows["KEY"] == "label", "VALUE"]
        source = next((by_basename[Path(v).name] for v in labels if Path(v).name in by_basename), None)
        if source is None:
            continue
        family = source.parent.parent.name

        profile_nodes = rows.loc[(rows["KEY"] == "type") & rows["VALUE"].str.endswith("Profile"), "ID"]
        if profile_nodes.empty:
            gaps.append(f"{source.name}: no prof:Profile node")
            continue
        profile_id = profile_nodes.iloc[0]

        keys = set(rows.loc[rows["KEY"].isin(["versionIRI", "priorVersion"]), "VALUE"])
        if str(profile_id).startswith("http"):
            keys.add(str(profile_id))

        profile = ProfileShapes(prof_file=str(source), family=family, keys=keys)

        descriptor_ids = set(rows.loc[(rows["ID"] == profile_id) & (rows["KEY"] == "hasResource"), "VALUE"])
        for descriptor in descriptor_ids:
            desc_rows = rows[rows["ID"] == descriptor]
            role = desc_rows.loc[desc_rows["KEY"] == "hasRole", "VALUE"]
            conforms = desc_rows.loc[desc_rows["KEY"] == "conformsTo", "VALUE"]
            if not role.str.endswith(ROLE_CONSTRAINTS).any() or not (conforms == SHACL_MARK).any():
                continue
            for artifact in desc_rows.loc[desc_rows["KEY"] == "hasArtifact", "VALUE"]:
                resolved = _resolve_artifact(apl_dir, family, _artifact_basename(artifact))
                if resolved is None:
                    profile.missing_artifacts.append(_artifact_basename(artifact))
                else:
                    profile.shacl_paths.append(resolved)

        profile.shacl_paths = sorted(set(profile.shacl_paths))
        if not profile.shacl_paths:
            gaps.append(f"{source.name}: no resolvable constraints-role SHACL artifacts")
        gaps.extend(f"{source.name}: artifact not found: {name}" for name in profile.missing_artifacts)

        for key in profile.keys:
            prof_map[key] = profile

    return prof_map, gaps


if __name__ == "__main__":
    import sys

    prof_map, gaps = build_prof_map(sys.argv[1])
    profiles = {id(p): p for p in prof_map.values()}
    print(f"{len(profiles)} profiles, {len(prof_map)} match keys")
    for profile in sorted(profiles.values(), key=lambda p: p.prof_file):
        print(f"\n{Path(profile.prof_file).name} [{profile.family}]")
        for key in sorted(profile.keys):
            print(f"  key: {key}")
        for path in profile.shacl_paths:
            print(f"  shacl: {path.name}")
    if gaps:
        print("\nGaps:")
        print("\n".join(f"  {g}" for g in gaps))
