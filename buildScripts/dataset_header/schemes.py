"""Load the reference-data schemes into valid-value sets for Tier-B checks.

The schemes live under ``Instance/referenceData/NetworkCode/cimxml`` and are the
``*-Collection-*_RD.xml`` files. Membership is derived from the URI conventions
used in those files, so entries added to the reference data become valid with no
code change here.

Because the collections still list only a subset of the parties/frames/models/
activities/profiles the instance files actually reference, Tier-B stays
report-only -- that gap is the parked PR #322 reference-data work.

An empty scheme is *not* normal: it means the glob matched no file, and
``rules.validate_graph`` then skips that check silently. ``missing_schemes``
reports those keys so the drift is visible instead of reading as a clean run.
The older ``*Scheme-NCP_RD`` names these globs used to carry survive only under
``referenceData/NetworkCode/ttl/``, which is how they went stale unnoticed.
"""
from __future__ import annotations

from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF
from rdflib.term import URIRef

from .rules import PROV

# Scheme key -> (glob under referenceData, URI substring that marks a member).
# The conformance entry stays a glob so the branch's profile release (NCP-2-4 /
# NCP-2-5 / ...) is picked up without editing this map.
_SCHEME_FILES: dict[str, tuple[str, str | None]] = {
    "model": ("NetworkCode/cimxml/Test-Model-Collection-*_RD.xml", "/model/"),
    "frame": ("NetworkCode/cimxml/Test-Frame-Collection-*_RD.xml", "/frame/"),
    "activity": ("NetworkCode/cimxml/Activity-Collection_RD.xml", "/activity/"),
    "party": ("NetworkCode/cimxml/Test-Party-Collection-*_RD.xml", "/party/"),
    "conformance": ("NetworkCode/cimxml/ConformTo-Collection-*_RD.xml", None),
}


class Schemes:
    """Holds the valid-value set for each reference scheme."""

    def __init__(self, reference_dir: Path):
        self.reference_dir = reference_dir
        self._values: dict[str, set[str]] = {}
        self._missing: dict[str, str] = {}
        self._load()

    def values_for(self, key: str) -> set[str]:
        return self._values.get(key, set())

    def missing_schemes(self) -> dict[str, str]:
        """Scheme key -> glob, for every scheme whose glob matched no file.

        A non-empty result means those Tier-B checks are being skipped, so the
        report understates the findings rather than showing a clean run.
        """
        return dict(self._missing)

    def _load(self) -> None:
        for key, (rel, marker) in _SCHEME_FILES.items():
            matches = sorted(self.reference_dir.glob(rel))
            if not matches:
                self._values[key] = set()
                self._missing[key] = rel
                continue
            g = Graph()
            for path in matches:
                try:
                    g.parse(str(path), format="xml")
                except Exception:
                    continue
            self._values[key] = self._extract(g, marker)

    @staticmethod
    def _extract(g: Graph, marker: str | None) -> set[str]:
        values: set[str] = set()
        if marker is not None:
            # Individuals whose URI matches the scheme's naming convention.
            for s in set(g.subjects()):
                if isinstance(s, URIRef) and marker in str(s):
                    values.add(str(s))
        else:
            # Conformance: gather members of any prov:Collection plus the
            # semantic-asset subjects (profile / vocabulary identifiers).
            for o in g.objects(None, PROV.hadMember):
                if isinstance(o, URIRef):
                    values.add(str(o))
            for s in set(g.subjects()):
                if isinstance(s, URIRef) and (
                    "ap.cim4.eu" in str(s) or "cim4.eu/ns/nc" in str(s)
                ):
                    values.add(str(s))
        return values

    def summary(self) -> str:
        return ", ".join(
            f"{k}={len(v)}" for k, v in sorted(self._values.items())
        )
