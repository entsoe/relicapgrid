""" Author: kristjan.vilgo """
from pathlib import Path
import pandas
from triplets.cgmes_tools import get_dangling_references
import uuid

# ====================== CONFIGURATION ======================
REPO_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_PATH = REPO_ROOT / "Instance"

from create_cgm_zip import discover_tsos, collect_cgm_files
# ===========================================================

tsos = discover_tsos(INSTANCE_PATH)
entries, missing = collect_cgm_files(INSTANCE_PATH, tsos, include_ncp=True)
xml_files = [f for f, _ in entries]

if missing:
    print("WARNING: Some expected files were not found:")
    for m in missing:
        print(f"  {m}")


print(f"Loading RDF from {len(xml_files)} files...")
data = pandas.read_RDF([str(f) for f in xml_files])

# Extract filename mapping
filename_mapping = data[data['KEY'] == 'label'][['INSTANCE_ID', 'VALUE']].rename(columns={'VALUE': 'Filename'})

# Extract profile mapping
profile_mapping = data[data['KEY'] == 'Model.profile'][['INSTANCE_ID', 'VALUE']].rename(columns={'VALUE': 'Profile'})

profile_mapping = data[data['KEY'] == 'conformsTo'][['INSTANCE_ID', 'VALUE']].rename(columns={'VALUE': 'Profile'})

# Start writing reports
REPORT_DIR = REPO_ROOT / "validation_report"
REPORT_DIR.mkdir(exist_ok=True)

# Record files used as input
pandas.DataFrame({"Loaded File Path": [str(f) for f in xml_files]}).to_csv(REPORT_DIR / "loaded_files.csv", index=False)

# Check dangling references
print("Checking for dangling references...")
dangling = get_dangling_references(data, detailed=True)

if not dangling.empty:

    # Add file data
    dangling = dangling.merge(filename_mapping, left_on='INSTANCE_ID_FROM', right_on='INSTANCE_ID', how='left').drop(columns=['INSTANCE_ID'])

    # Filter out valid missing references. PropertyReference associations target
    # external CIM/nc ontology properties (issue #358), which resolve outside the
    # instance data and are not dangling references.
    to_ignore = [
        'Model.Supersedes',
        'GridStateAlteration.PropertyReference',
        'StaticPropertyRange.PropertyReference',
        'FunctionOutputVariable.PropertyReference',
    ]
    dangling = dangling[~dangling['KEY_FROM'].isin(to_ignore)]

    # Details
    dangling[['ID_FROM', 'KEY_FROM', 'VALUE_FROM', 'Filename']].to_csv(REPORT_DIR / "dangling_references_detailed.csv", index=False)

    # Summary
    summary = dangling.groupby("Filename")["KEY_FROM"].value_counts().reset_index(name='Count')
    summary.to_csv(REPORT_DIR / "dangling_references_summary.csv", index=False)

    print(f"\nFound {len(dangling)} dangling references. Reports saved to {REPORT_DIR}")

else:
    print("No dangling references found.")




