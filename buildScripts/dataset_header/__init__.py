"""Dataset-header validation and fixing for ReliCapGrid instance files.

Single source of truth for the DCAT dataset-header rules (Svein's review of
PR #322), consumed by two modes:

- ``validate_dataset_header.py`` — semantic validation via rdflib (report).
- ``fix_dataset_header.py``      — formatting-preserving auto-fix of the
  deterministic (Tier-A) subset.

Rules are split into two tiers:

- **Tier A** — structural / fixed-value: deterministic, auto-fixable now.
- **Tier B** — reference-data membership: checkable now, but fixing is blocked
  until the reference schemes are extended (see the parked PR #322 items).
"""
