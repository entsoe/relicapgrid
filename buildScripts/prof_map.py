"""Map profile URIs to SHACL shape files via the DX-PROF descriptors of the
ENTSO-E application-profiles-library (APL).

An instance file declares its profile as `md:Model.profile` (CGMES) or
`dcterms:conformsTo` (NC). Each APL PROF descriptor carries the matching keys
(`rdf:about`, `owl:versionIRI`, `owl:priorVersion`) and, per resource, the
role and artifact. Two SHACL resource kinds are returned:

- `role/constraints` → `shacl_paths`: the individual shape files (CGMES + NCP).
- `role/validation` whose artifact is an `owl:imports` aggregate →
  `validation_paths`: the aggregate plus its import closure. NCP 2.5 ships one
  per profile ("shall be executed when validating a dataset that conforms to
  X"): it imports the Simple + common per-dataset shapes and `sh:deactivated`s
  the cross-dataset value-type checks. CGMES `role/validation` artifacts are
  plain shape variants (NotSolvedMAS) without imports — not returned.

Artifacts and imports are resolved by basename against `<family>/SHACL/**`
then `<family>/RDFS/` (CGMES artifacts are bare filenames, NCP ones absolute
URLs — raw.githubusercontent.com/.../main/... for the imports — none resolves
as a relative URI, and the checkout is the pinned source of truth).

Debug CLI:  python buildScripts/prof_map.py <apl_dir>
"""
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import pandas
import triplets  # noqa: F401  (registers pandas.read_RDF)

ROLE_CONSTRAINTS = "role/constraints"
ROLE_VALIDATION = "role/validation"
SHACL_MARK = "http://www.w3.org/ns/shacl"
OWL_IMPORTS = "http://www.w3.org/2002/07/owl#imports"
SH_DEACTIVATED = "http://www.w3.org/ns/shacl#deactivated"


@dataclass
class ProfileShapes:
    prof_file: str
    family: str                                # "CGMES" | "NCP"
    keys: set = field(default_factory=set)     # about + versionIRI + priorVersion URIs
    shacl_paths: list = field(default_factory=list)        # role/constraints shape files
    validation_paths: list = field(default_factory=list)   # role/validation aggregate + import closure
    missing_artifacts: list = field(default_factory=list)


def _artifact_basename(value):
    return PurePosixPath(urlparse(str(value)).path).name


def _resolve_artifact(apl_dir, family, basename):
    for subdir in ("SHACL", "RDFS"):
        candidates = sorted((apl_dir / family / subdir).rglob(basename))
        if candidates:
            return candidates[0]
    return None


def import_closure(path, apl_dir, family):
    """[aggregate, *transitively imported shape files] resolved in the checkout.

    Returns (paths, missing basenames). A file without owl:imports yields
    ([path], []) — the caller uses that to tell aggregates from plain shapes."""
    import rdflib

    seen, missing, queue = {}, [], [Path(path)]
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        graph = rdflib.Graph()
        try:
            graph.parse(str(current), format="turtle")
        except Exception as error:  # authoring defect upstream — keep the rest of the closure usable
            missing.append(f"{current.name} (unparsable: {str(error).splitlines()[-1][:80]})")
            continue
        imports = [str(o) for o in graph.objects(None, rdflib.URIRef(OWL_IMPORTS))]
        seen[current] = imports
        for uri in imports:
            resolved = _resolve_artifact(apl_dir, family, _artifact_basename(uri))
            if resolved is None:
                missing.append(_artifact_basename(uri))
            else:
                queue.append(resolved)
    return sorted(seen), sorted(set(missing))


def deactivated_shapes(paths):
    """Shape IRIs any of *paths* marks `sh:deactivated true` (the NCP 2.5
    validation aggregates switch cross-dataset value-type checks off this way).
    triplets 0.2.0 does not honour sh:deactivated at compile — until 0.3 the
    caller drops findings of these shapes; delete this once it does."""
    import rdflib

    graph = rdflib.Graph()
    for path in paths:
        try:
            graph.parse(str(path), format="turtle")
        except Exception:
            continue
    return {str(shape) for shape, flag in graph.subject_objects(rdflib.URIRef(SH_DEACTIVATED))
            if bool(flag.toPython())}


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
            if not (conforms == SHACL_MARK).any():
                continue
            is_constraints = role.str.endswith(ROLE_CONSTRAINTS).any()
            is_validation = role.str.endswith(ROLE_VALIDATION).any()
            if not (is_constraints or is_validation):
                continue
            for artifact in desc_rows.loc[desc_rows["KEY"] == "hasArtifact", "VALUE"]:
                resolved = _resolve_artifact(apl_dir, family, _artifact_basename(artifact))
                if resolved is None:
                    profile.missing_artifacts.append(_artifact_basename(artifact))
                elif is_constraints:
                    profile.shacl_paths.append(resolved)
                else:
                    closure, missing = import_closure(resolved, apl_dir, family)
                    if len(closure) > 1:          # an aggregate, not a plain shape variant
                        profile.validation_paths.extend(closure)
                        profile.missing_artifacts.extend(missing)

        profile.shacl_paths = sorted(set(profile.shacl_paths))
        profile.validation_paths = sorted(set(profile.validation_paths))
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
        for path in profile.validation_paths:
            print(f"  validation: {path.name}")
    if gaps:
        print("\nGaps:")
        print("\n".join(f"  {g}" for g in gaps))
