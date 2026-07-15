"""
Discover which CIM model folders need their manifest.ttl regenerated.

Emits a JSON array of {"model_dir": ..., "manifest_path": ...} objects on
stdout, consumed as a GitHub Actions matrix by generate_manifests.yml.

A model folder is normally a `cimxml/` directory, with manifest.ttl written
to its parent. Folders listed in SPECIAL_CASES hold model XML directly
(no cimxml/ subfolder), so manifest.ttl is written in place instead.

Usage:
    python buildScripts/find_manifest_targets.py --full
    python buildScripts/find_manifest_targets.py --before <sha> --after <sha>
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

INSTANCE_DIR = "Instance"

# Folders that hold model XML directly instead of under a cimxml/ subfolder.
# Instance/Jotunheim/NetworkCode predates the cimxml/ convention used
# everywhere else and hasn't been migrated yet.
SPECIAL_CASES = {
    "Instance/Jotunheim/NetworkCode",
}


def manifest_path_for(model_dir: str) -> str:
    if model_dir in SPECIAL_CASES:
        return f"{model_dir}/manifest.ttl"
    return f"{Path(model_dir).parent.as_posix()}/manifest.ttl"


def discover_all() -> set[str]:
    dirs = {p.as_posix() for p in Path(INSTANCE_DIR).rglob("cimxml") if p.is_dir()}
    return dirs | SPECIAL_CASES


def model_dir_for_changed_file(changed_path: str) -> str | None:
    path = Path(changed_path)
    if path.suffix.lower() not in (".xml", ".rdf"):
        return None
    for special in SPECIAL_CASES:
        if changed_path.startswith(f"{special}/"):
            return special
    for parent in path.parents:
        if parent.name == "cimxml":
            return parent.as_posix()
    return None


def discover_changed(before: str, after: str) -> set[str]:
    diff = subprocess.run(
        ["git", "diff", "--name-only", before, after],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()

    dirs: set[str] = set()
    for changed in diff:
        model_dir = model_dir_for_changed_file(changed)
        if model_dir:
            dirs.add(model_dir)
    return dirs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Discover every model folder, ignoring git diff")
    parser.add_argument("--before", help="Git revision before the push")
    parser.add_argument("--after", help="Git revision after the push")
    args = parser.parse_args()

    is_new_branch = bool(args.before) and set(args.before) == {"0"}
    if args.full or not args.before or is_new_branch:
        model_dirs = discover_all()
    else:
        model_dirs = discover_changed(args.before, args.after)

    matrix = [
        {"model_dir": d, "manifest_path": manifest_path_for(d)}
        for d in sorted(model_dirs)
    ]
    json.dump(matrix, sys.stdout)


if __name__ == "__main__":
    main()