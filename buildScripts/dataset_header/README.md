# Dataset-header validation & fixing

A reusable, branch/version-agnostic tool that checks (and fixes) the DCAT
dataset headers of ReliCapGrid instance files against the rules from Svein's
PR #322 review. The **validator** and the **fixer** share one rule set
(`rules.py`) so they can't drift apart.

## Two tiers

- **Tier A — structural / fixed-value.** Deterministic and auto-fixable:
  required properties, fixed values (`accessRights`, `type`, `license`,
  `rights`, `rightsHolder`), `xml:lang` tags, forbidden properties,
  disallowed namespaces (`eumd`/`euvoc`), UUID and UTC-`Z` datetime formats,
  and `TSO-`/`RCC-` publisher naming.
- **Tier B — reference-data membership.** `conformsTo` / `isVersionOf` /
  `spatial` / `wasGeneratedBy` / publisher-party validated against the
  schemes in `Instance/referenceData`. **Report-only** — fixing is blocked
  until those schemes are extended (the parked PR #322 items). New scheme
  entries become valid automatically, no code change.

## Usage

```bash
# Validate (report-only; exit 0). Add --strict to fail on Tier-A.
uv run python buildScripts/validate_dataset_header.py --scope networkcode \
    --details --json validation_report/dataset_header.json

# Auto-fix the deterministic Tier-A subset (dry-run without --apply).
uv run python buildScripts/fix_dataset_header.py --scope networkcode
uv run python buildScripts/fix_dataset_header.py --scope networkcode --apply
```

`--scope` is `networkcode` (default) or `all`. The fixer is idempotent and
formatting-preserving (text edits, not graph re-serialization), so diffs stay
minimal. It never invents Tier-B values, real dates, titles, or spatial refs.

## CI / pytest

`tests/test_dataset_header.py` runs the validator over the in-scope files.
It is **report-only** (`xfail`) until a branch's headers are clean; once you
have run the fixer and resolved the manual gaps, flip the fixable-Tier-A check
to a hard failure so regressions (e.g. re-introducing `eumd` or a forbidden
property) fail the build. Fast unit tests cover the rule and fixer logic.

## Layout

| File | Role |
|---|---|
| `rules.py` | single source of truth: rule catalog + rdflib checks |
| `schemes.py` | loads referenceData schemes into valid-value sets (Tier B) |
| `discovery.py` | enumerates in-scope header files |
| `fixer.py` | formatting-preserving Tier-A auto-fixes |
| `report.py` | text / markdown / JSON reporting |
| `../validate_dataset_header.py` | validator CLI |
| `../fix_dataset_header.py` | fixer CLI |

## Roadmap

- Extend scope beyond NetworkCode cimxml (Grid, GridSituation, boundary).
- Emit DCAT-AP-CIM SHACL shapes and run `pyshacl` as an independent
  cross-check of the Python rules (`pyshacl` is already a dependency).
