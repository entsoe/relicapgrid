"""Load the reference-data schemes into valid-value sets for Tier-B checks.

The schemes live under ``Instance/referenceData``. Because they only list a
subset of parties/frames/models/activities/profiles today, Tier-B checks are
report-only and best-effort: membership is derived from the URI conventions
used in the scheme files, so newly added entries become valid with no code
change. This is exactly the parked PR #322 reference-data work.
"""
from __future__ import annotations

from pathlib import Path

from rdflib import Graph
from rdflib.namespace import RDF
from rdflib.term import URIRef

from .rules import PROV

# Scheme key -> (glob under referenceData, URI substring that marks a member).
_SCHEME_FILES: dict[str, tuple[str, str | None]] = {
    "model": ("NetworkCode/cimxml/Test-ModelScheme-NCP_RD.xml", "/model/"),
    "frame": ("NetworkCode/cimxml/Test-FrameScheme-NCP_RD.xml", "/frame/"),
    "activity": ("NetworkCode/cimxml/ActivityScheme-NCP_RD.xml", "/activity/"),
    "party": ("NetworkCode/cimxml/Test-PartyScheme-NCP_RD.xml", "/party/"),
    "conformance": ("NetworkCode/cimxml/ConformanceReleaseScheme-*_RD.xml", None),
}


class Schemes:
    """Holds the valid-value set for each reference scheme."""

    def __init__(self, reference_dir: Path):
        self.reference_dir = reference_dir
        self._values: dict[str, set[str]] = {}
        self._load()

    def values_for(self, key: str) -> set[str]:
        return self._values.get(key, set())

    def _load(self) -> None:
        for key, (rel, marker) in _SCHEME_FILES.items():
            matches = sorted(self.reference_dir.glob(rel))
            if not matches:
                self._values[key] = set()
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
