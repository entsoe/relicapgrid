"""Discover instance files that carry a dcat:Dataset header.

Phase-1 scope is the NetworkCode cimxml surface (the PR #322 files). The
existing ``create_cgm_zip.collect_cgm_files`` helper is too narrow (it skips
the ``Dataset_version_dependency/`` subfolder and the Jotunheim NetworkCode
IAM/SAR files), so we glob directly here. Scope can be widened later.
"""
from __future__ import annotations

from pathlib import Path

# Directories that are not instance datasets.
_EXCLUDE_PARTS = {"referenceData"}


def discover_headers(instance_dir: Path, scope: str = "networkcode") -> list[Path]:
    """Return sorted instance XML files in scope that may contain a header."""
    if scope == "networkcode":
        pattern = "*/NetworkCode/**/*.xml"
    elif scope == "all":
        pattern = "**/*.xml"
    else:
        raise ValueError(f"unknown scope: {scope!r}")

    files = [
        p for p in instance_dir.glob(pattern)
        if not (_EXCLUDE_PARTS & set(p.parts))
    ]
    return sorted(set(files))
