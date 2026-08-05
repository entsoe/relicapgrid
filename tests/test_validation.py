""" Author: kristjan.vilgo """

print("Loading test script...")
import sys
from pathlib import Path
import pandas
import pytest
from triplets.cgmes_tools import get_dangling_references
import uuid

# Add buildScripts to path to reuse create_cgm_zip
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "buildScripts"))
from create_cgm_zip import discover_tsos, collect_cgm_files

INSTANCE_DIR = REPO_ROOT / "Instance"


def readable_path(path):
    """Make absolute path relative to repo root."""
    return str(path).replace(str(REPO_ROOT) + '/', '', 1)

@pytest.fixture(scope="module")
def grid_data():
    tsos = discover_tsos(INSTANCE_DIR)
    print(f"Discovered TSOs: {tsos}")
    files, missing = collect_cgm_files(INSTANCE_DIR, tsos, include_ncp=True)
    if missing:
        print(f"Missing files: {missing}")
    xml_files = [str(f) for f, _ in files]
    print(f"Loading {len(xml_files)} files...")
    data = pandas.read_RDF(xml_files)
    print("Data loaded successfully.")
    return data

def test_dangling_references(grid_data):
    print("Checking for dangling references...")

    # Get detailed dangling references
    dangling = get_dangling_references(grid_data, detailed=True)

    if not dangling.empty:

        # Filename mapping
        filename_mapping = grid_data[grid_data['KEY'] == 'label'][['INSTANCE_ID', 'VALUE']].rename(columns={'VALUE': 'Filename'})

        dangling = dangling.merge(filename_mapping, left_on='INSTANCE_ID_FROM', right_on='INSTANCE_ID', how='left').drop(columns=['INSTANCE_ID'])

        # Filter out valid missing references or references to profiles not loaded
        to_ignore = [
            'Model.Supersedes',
            # PropertyReference associations target external CIM/nc ontology
            # properties (issue #358), which resolve outside the instance data.
            'GridStateAlteration.PropertyReference',
            'StaticPropertyRange.PropertyReference',
            'FunctionOutputVariable.PropertyReference',
        ]
        dangling = dangling[~dangling['KEY_FROM'].isin(to_ignore)]

    if not dangling.empty:
        dangling = dangling.copy()
        dangling['Filename'] = dangling['Filename'].apply(readable_path)

        summary = (
            dangling.groupby("Filename")["KEY_FROM"]
            .value_counts()
            .reset_index(name='Count')
            .sort_values(['Count', 'Filename'], ascending=[False, True])
        )

        max_rows = 15
        summary_table = summary.head(max_rows).to_markdown(index=False)
        if len(summary) > max_rows:
            summary_table += f"\n\n... and **{len(summary) - max_rows}** more"

        # Detailed table with missing target IDs
        details = (
            dangling[['Filename', 'KEY_FROM', 'ID_FROM', 'VALUE_FROM']]
            .rename(columns={'VALUE_FROM': 'ID_TO'})
            .sort_values(['Filename', 'KEY_FROM'])
            .reset_index(drop=True)
        )

        details_table = details.head(max_rows).to_markdown(index=False)
        if len(details) > max_rows:
            details_table += f"\n\n... and **{len(details) - max_rows}** more"

        message = (
            f"**Found {len(dangling)} dangling references:**\n\n"
            f"**Summary:**\n\n{summary_table}\n\n"
            f"**Details:**\n\n{details_table}"
        )
        pytest.fail(message)


def test_no_duplicate_type_ids_per_instance(grid_data):
    """Ensure no ID is used more than once as 'Type' within the same file."""
    # Filter Type entries
    type_entries = grid_data[grid_data['KEY'] == 'Type'].copy()

    # === Get Filename Mapping ===
    filename_mapping = grid_data[grid_data['KEY'] == 'label'][['INSTANCE_ID', 'VALUE']].rename(columns={'VALUE': 'Filename'})
    type_entries = type_entries.merge(filename_mapping, on='INSTANCE_ID', how='left')

    # Step 1: Count occurrences of each (INSTANCE_ID, ID) pair
    counts = type_entries.groupby(['INSTANCE_ID', 'ID']).size().reset_index(name='count')
    dup_keys = counts[counts['count'] > 1][['INSTANCE_ID', 'ID']]

    # Step 2: Keep only the duplicated rows
    if not dup_keys.empty:
        duplicates = type_entries.merge(dup_keys, on=['INSTANCE_ID', 'ID'], how='inner')
    else:
        duplicates = type_entries.iloc[0:0].copy()  # empty DataFrame with same columns

    if not duplicates.empty:
        duplicates = duplicates.copy()
        duplicates['Filename'] = duplicates['Filename'].apply(readable_path)

        summary = (
            duplicates.groupby(['Filename', 'VALUE', 'ID'])
            .size()
            .reset_index(name='Count')
            .sort_values(['Count', 'Filename'], ascending=[False, True])
        )

        max_rows = 15
        table = summary.head(max_rows).to_markdown(index=False)
        if len(summary) > max_rows:
            table += f"\n\n... and **{len(summary) - max_rows}** more"

        message = (
            f"**Found {len(duplicates)} duplicated 'Type' ID entries:**\n\n"
            f"{table}\n\n"
            "Each ID should appear only once as 'Type' per file."
        )
        pytest.fail(message)


def test_duplicate_detection_logic():
    """Negative test: Verify our duplicate detection logic works correctly (fast version)."""
    # Create a minimal reproducible example
    test_data = pandas.DataFrame({
        'INSTANCE_ID': [101, 101, 102, 102, 103],
        'KEY': ['Type', 'Type', 'Type', 'Other', 'Type'],
        'ID': ['A01', 'A01', 'B01', 'X01', 'C01']  # A01 is duplicated in instance 101
    })

    # === Same fast logic as the main test ===
    type_entries = test_data[test_data['KEY'] == 'Type'].copy()
    counts = type_entries.groupby(['INSTANCE_ID', 'ID']).size().reset_index(name='count')
    dup_keys = counts[counts['count'] > 1][['INSTANCE_ID', 'ID']]
    duplicates = type_entries.merge(dup_keys, on=['INSTANCE_ID', 'ID'], how='inner')

    assert not duplicates.empty, "Duplicate detection logic failed"
    assert len(duplicates) == 2, f"Expected 2 duplicate rows, got {len(duplicates)}"
    assert duplicates['INSTANCE_ID'].nunique() == 1, "Duplicates should be within the same instance"


def is_valid_uuid(val):
    """Helper function to check if a value is a valid UUID."""
    if pandas.isna(val):
        return False
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def test_uuid_validation_logic():
    """Negative test: Verify UUID validation logic works correctly with invalid data."""
    # Create test data with mix of valid and invalid UUIDs
    test_data = pandas.DataFrame({
        'ID': [
            '123e4567-e89b-12d3-a456-426614174000',  # valid
            'invalid-uuid-string',  # invalid
            'not-a-uuid-at-all',  # invalid
            None,  # invalid (missing)
            '550e8400-e29b-41d4-a716-446655440000',  # valid
            '123e4567-e89b-12d3-a456-42661417400',  # invalid (too short)
            'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',  # invalid characters
        ]
    })

    test_data['is_valid_uuid'] = test_data['ID'].apply(is_valid_uuid)
    invalid_count = (~test_data['is_valid_uuid']).sum()

    assert invalid_count == 5, f"Expected 5 invalid UUIDs, got {invalid_count}"
    assert not test_data.loc[1, 'is_valid_uuid'], "Second row should be invalid"
    assert not test_data.loc[2, 'is_valid_uuid'], "Third row should be invalid"
    assert not test_data.loc[3, 'is_valid_uuid'], "Fourth row (None) should be invalid"


def test_valid_uuids_in_data(grid_data):
    """Ensure all values in the 'ID' column are valid UUIDs."""
    print("Validating UUIDs in ID column...")

    # Apply UUID validation
    grid_data = grid_data.copy()
    grid_data['is_valid_uuid'] = grid_data['ID'].apply(is_valid_uuid)

    invalid_ids = grid_data[~grid_data['is_valid_uuid']].copy()

    if not invalid_ids.empty:
        # Get Filename mapping for better error reporting
        filename_mapping = grid_data[grid_data['KEY'] == 'label'][['INSTANCE_ID', 'VALUE']].rename(
            columns={'VALUE': 'Filename'})
        invalid_ids = invalid_ids.merge(filename_mapping, on='INSTANCE_ID', how='left')

        invalid_ids['Filename'] = invalid_ids['Filename'].apply(readable_path)

        summary = (
            invalid_ids.groupby(['Filename', 'KEY', 'ID'])
            .size()
            .reset_index(name='Count')
            .sort_values(['Filename', 'KEY'])
        )

        max_rows = 15
        table = summary.head(max_rows).to_markdown(index=False)
        if len(summary) > max_rows:
            table += f"\n\n... and **{len(summary) - max_rows}** more"

        message = (
            f"**Found {len(invalid_ids)} rows with INVALID UUIDs in 'ID' column:**\n\n"
            f"{table}\n\n"
            "All IDs must be valid UUID format (e.g. `123e4567-e89b-12d3-a456-426614174000`)."
        )
        pytest.fail(message)



