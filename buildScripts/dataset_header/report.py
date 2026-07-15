"""Reporting helpers shared by the validator CLI and the pytest integration."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from .rules import Violation


def to_dicts(violations: list[Violation]) -> list[dict]:
    return [
        {
            "file": v.file,
            "rule_id": v.rule_id,
            "tier": v.tier,
            "review_ref": v.review_ref,
            "message": v.message,
            "fixable": v.fixable,
            "detail": v.detail,
        }
        for v in violations
    ]


def summarize(violations: list[Violation], files_scanned: int, headers: int) -> str:
    tier_a = [v for v in violations if v.tier == "A"]
    tier_b = [v for v in violations if v.tier == "B"]
    fixable = [v for v in tier_a if v.fixable]
    lines = [
        f"Scanned {files_scanned} files ({headers} with a dcat:Dataset header).",
        f"Tier-A violations: {len(tier_a)} ({len(fixable)} auto-fixable)",
        f"Tier-B violations: {len(tier_b)} (blocked on reference-scheme extensions)",
    ]
    return "\n".join(lines)


def by_rule_table(violations: list[Violation]) -> str:
    """Markdown table of violation counts per rule (for CI/PR comments)."""
    counts = Counter((v.tier, v.rule_id, v.review_ref) for v in violations)
    if not counts:
        return "_No violations._"
    rows = ["| Tier | Rule | Review | Count |", "|---|---|---|---|"]
    for (tier, rule, ref), n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
        rows.append(f"| {tier} | {rule} | {ref} | {n} |")
    return "\n".join(rows)


def details_text(violations: list[Violation], root: Path | None = None) -> str:
    lines = []
    for v in sorted(violations, key=lambda x: (x.tier, x.file, x.rule_id)):
        f = v.file
        if root is not None:
            try:
                f = str(Path(v.file).relative_to(root))
            except ValueError:
                pass
        lines.append(f"{f}: {v}")
    return "\n".join(lines)
