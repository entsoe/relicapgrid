"""Auto-fix the deterministic (Tier-A) dataset-header violations.

Dry-run by default; pass ``--apply`` to write changes. Formatting-preserving
(text edits, not graph re-serialization). Tier-B (reference-data) values are
never invented here — run ``validate_dataset_header.py`` to see what remains.

Usage:
    python buildScripts/fix_dataset_header.py [--scope networkcode|all] [--apply]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset_header.discovery import discover_headers
from dataset_header.fixer import fix_text

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = REPO_ROOT / "Instance"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", default="networkcode",
                        choices=["networkcode", "all"])
    parser.add_argument("--apply", action="store_true",
                        help="write changes (default: dry-run)")
    args = parser.parse_args(argv)

    files = discover_headers(INSTANCE_DIR, scope=args.scope)
    changed = 0
    fix_counts: Counter = Counter()
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        new_text, applied = fix_text(text)
        if not applied or new_text == text:
            continue
        changed += 1
        fix_counts.update(a.split(":")[0] for a in applied)
        rel = path.relative_to(REPO_ROOT)
        print(f"{'FIX ' if args.apply else 'WOULD FIX '}{rel}: {', '.join(applied)}")
        if args.apply:
            path.write_text(new_text, encoding="utf-8", newline="")

    print()
    print(f"{'Fixed' if args.apply else 'Would fix'} {changed} files.")
    for kind, n in fix_counts.most_common():
        print(f"  {kind}: {n}")
    if not args.apply and changed:
        print("\nDry-run only. Re-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
