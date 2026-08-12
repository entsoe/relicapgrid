"""
Create a zip package for CGM (Common Grid Model) import from the ReliCapGrid repo.

CGM package contents (per README):
  Grid:
    - EQ profile from each TSO's Instance/<TSO>/Grid/cimxml/ folder
    - All files from Instance/Jotunheim/Grid/cimxml/ (TP, SV)
    - RCC-updated per-IGM SSH files from Instance/Jotunheim/ChangeSet/cimxml/
    - All boundary files from Instance/boundaryData/Grid/cimxml/
    - Instance/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml
  Network Code Profiles (optional, --ncp flag):
    - All files from Instance/<TSO>/NetworkCode/cimxml/ for each TSO that has them
    - Instance/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml

Usage:
    python buildScripts/create_cgm_zip.py
    python buildScripts/create_cgm_zip.py --ncp
    python buildScripts/create_cgm_zip.py --tsos Espheim Svedala --ncp
    python buildScripts/create_cgm_zip.py --output my_cgm_package.zip
"""

import argparse
import sys
import zipfile
from pathlib import Path

NON_TSO_FOLDERS = {"boundaryData", "commonData", "referenceData", "NetworkCode", "Jotunheim"}


def discover_tsos(instance_dir: Path) -> list[str]:
    return sorted(
        d.name for d in instance_dir.iterdir()
        if d.is_dir() and d.name not in NON_TSO_FOLDERS
    )


def collect_cgm_files(instance_dir: Path, tsos: list[str], include_ncp: bool) -> list[tuple[Path, str]]:
    """Return list of (absolute_path, archive_name) tuples."""
    entries: list[tuple[Path, str]] = []
    missing: list[str] = []

    # EQ profile from each TSO
    for tso in tsos:
        cimxml_dir = instance_dir / tso / "Grid" / "cimxml"
        eq_files = list(cimxml_dir.glob("*_EQ_*.xml")) if cimxml_dir.exists() else []
        if not eq_files:
            missing.append(f"EQ file not found: {cimxml_dir}")
        for f in eq_files:
            entries.append((f, f.name))

    # All files from Jotunheim/Grid/cimxml (SSH, TP, SV)
    jotunheim_dir = instance_dir / "Jotunheim" / "Grid" / "cimxml"
    if not jotunheim_dir.exists():
        missing.append(f"Jotunheim Grid cimxml dir not found: {jotunheim_dir}")
    else:
        for f in sorted(jotunheim_dir.glob("*.xml")):
            entries.append((f, f.name))

    # SSH files from Jotunheim/ChangeSet/cimxml (RCC-updated per-IGM SSH for the CGM)
    changeset_dir = instance_dir / "Jotunheim" / "ChangeSet" / "cimxml"
    if not changeset_dir.exists():
        missing.append(f"Jotunheim ChangeSet cimxml dir not found: {changeset_dir}")
    else:
        ssh_files = sorted(changeset_dir.glob("*_SSH_*.xml"))
        if not ssh_files:
            missing.append(f"No SSH files found in: {changeset_dir}")
        for f in ssh_files:
            entries.append((f, f.name))

    # All boundary files
    boundary_dir = instance_dir / "boundaryData" / "Grid" / "cimxml"
    if not boundary_dir.exists():
        missing.append(f"Boundary data dir not found: {boundary_dir}")
    else:
        for f in sorted(boundary_dir.glob("*.xml")):
            entries.append((f, f.name))

    # Grid CommonData
    grid_cd = instance_dir / "commonData" / "Grid" / "cimxml" / "Grid_CommonData_CGM-CD.xml"
    if not grid_cd.exists():
        missing.append(f"Grid CommonData not found: {grid_cd}")
    else:
        entries.append((grid_cd, grid_cd.name))

    if include_ncp:
        # NetworkCode profiles for each TSO that has them
        for tso in tsos:
            ncp_dir = instance_dir / tso / "NetworkCode" / "cimxml"
            if ncp_dir.exists():
                for f in sorted(ncp_dir.glob("*.xml")):
                    entries.append((f, f.name))

        # NetworkCode CommonData
        ncp_cd = instance_dir / "commonData" / "NetworkCode" / "cimxml" / "Org-NineRealms_CD.xml"
        if not ncp_cd.exists():
            missing.append(f"NetworkCode CommonData not found: {ncp_cd}")
        else:
            entries.append((ncp_cd, ncp_cd.name))

    return entries, missing


def main():
    repo_root = Path(__file__).resolve().parent.parent
    instance_dir = repo_root / "Instance"

    parser = argparse.ArgumentParser(description="Create a CGM import zip package from ReliCapGrid.")
    parser.add_argument(
        "--tsos", nargs="+", metavar="TSO",
        help="TSO names to include (default: all discovered TSOs)",
    )
    parser.add_argument(
        "--ncp", action="store_true",
        help="Also include Network Code Profile files",
    )
    parser.add_argument(
        "--output", "-o", default="CGM_package.zip",
        help="Output zip file path (default: CGM_package.zip)",
    )
    parser.add_argument(
        "--list-tsos", action="store_true",
        help="Print discovered TSO folders and exit",
    )
    args = parser.parse_args()

    all_tsos = discover_tsos(instance_dir)

    if args.list_tsos:
        print("Discovered TSOs:")
        for tso in all_tsos:
            print(f"  {tso}")
        return

    tsos = args.tsos if args.tsos else all_tsos

    # Validate requested TSOs
    unknown = [t for t in tsos if t not in all_tsos]
    if unknown:
        print(f"ERROR: Unknown TSO(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Available: {', '.join(all_tsos)}", file=sys.stderr)
        sys.exit(1)

    entries, missing = collect_cgm_files(instance_dir, tsos, args.ncp)

    if missing:
        print("WARNING: Some expected files were not found:")
        for m in missing:
            print(f"  {m}")

    base = Path(args.output)
    suffixes = "_NCP" if args.ncp else ""
    output_path = (base.parent / (base.stem + suffixes + base.suffix)).resolve()
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for abs_path, arc_name in entries:
            zf.write(abs_path, arc_name)
            print(f"  + {arc_name}")

    total = len(entries)
    print(f"\nCreated {output_path} with {total} file(s).")
    print(f"TSOs included: {', '.join(tsos)}")
    if args.ncp:
        print("Network Code Profiles: included")


if __name__ == "__main__":
    main()
