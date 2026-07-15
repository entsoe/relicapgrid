"""Validate ReliCapGrid dataset headers against the DCAT header rules.

Report-only by default (exit 0); pass ``--strict`` to exit non-zero when any
Tier-A violation is found. Tier-B (reference-scheme membership) violations are
always report-only, since fixing them is blocked on extending the schemes.

Usage:
    python buildScripts/validate_dataset_header.py [--scope networkcode|all]
        [--strict] [--json validation_report/dataset_header.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a plain script: make the sibling package importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset_header.discovery import discover_headers
from dataset_header.report import by_rule_table, details_text, summarize, to_dicts
from dataset_header.rules import Violation, find_dataset, parse_header, validate_graph
from dataset_header.schemes import Schemes

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = REPO_ROOT / "Instance"
REFERENCE_DIR = INSTANCE_DIR / "referenceData"


def run(scope: str = "networkcode") -> tuple[list[Violation], int, int]:
    """Validate all in-scope headers. Returns (violations, files, headers)."""
    schemes = Schemes(REFERENCE_DIR)
    files = discover_headers(INSTANCE_DIR, scope=scope)
    violations: list[Violation] = []
    headers = 0
    for path in files:
        try:
            graph = parse_header(str(path))
        except Exception as exc:  # malformed XML is itself a finding
            violations.append(Violation(
                str(path), "xml-parse-error", "A", "#1",
                f"file is not well-formed / parseable: {exc}"))
            continue
        if find_dataset(graph) is None:
            continue
        headers += 1
        violations.extend(validate_graph(graph, str(path), schemes))
    return violations, len(files), headers


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", default="networkcode",
                        choices=["networkcode", "all"])
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero if Tier-A violations are found")
    parser.add_argument("--json", type=Path, default=None,
                        help="write a JSON report to this path")
    parser.add_argument("--details", action="store_true",
                        help="print one line per violation")
    args = parser.parse_args(argv)

    violations, n_files, headers = run(args.scope)
    schemes = Schemes(REFERENCE_DIR)

    print(summarize(violations, n_files, headers))
    print(f"Reference schemes loaded: {schemes.summary()}")
    print()
    print(by_rule_table(violations))
    if args.details:
        print()
        print(details_text(violations, root=REPO_ROOT))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({
            "scope": args.scope,
            "files_scanned": n_files,
            "headers": headers,
            "violations": to_dicts(violations),
        }, indent=2), encoding="utf-8")
        print(f"\nJSON report written to {args.json}")

    tier_a = [v for v in violations if v.tier == "A"]
    if args.strict and tier_a:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
