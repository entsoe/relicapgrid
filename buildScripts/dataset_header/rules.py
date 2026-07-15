"""Declarative dataset-header rule catalog + rdflib-based validation.

This module is the single source of truth for the header rules. The validator
evaluates them against an rdflib graph; the fixer (``fix_dataset_header.py``)
consumes the same constants to apply the Tier-A subset via text edits.

Review-point references (e.g. ``#3``) point to Svein's numbered review of
PR #322.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF
from rdflib.term import Literal, URIRef as URIRefT

# ------------------------------------------------------------------ namespaces
DCAT = Namespace("http://www.w3.org/ns/dcat#")
DCTERMS = Namespace("http://purl.org/dc/terms/")
ADMS = Namespace("http://www.w3.org/ns/adms#")
PROV = Namespace("http://www.w3.org/ns/prov#")
DCATCIM = Namespace("https://cim4.eu/ns/dcatcim#")

BASE = "https://energy.referencedata.eu/"

# ------------------------------------------------------------------ rule data
# Required properties that must appear at least once (Tier A = presence).
REQUIRED_PROPERTIES: dict[str, URIRef] = {
    "dcterms:accessRights": DCTERMS.accessRights,
    "dcterms:conformsTo": DCTERMS.conformsTo,
    "dcterms:description": DCTERMS.description,
    "dcterms:identifier": DCTERMS.identifier,
    "dcterms:issued": DCTERMS.issued,
    "dcat:isVersionOf": DCAT.isVersionOf,
    "dcat:keyword": DCAT.keyword,
    "dcterms:license": DCTERMS.license,
    "dcterms:publisher": DCTERMS.publisher,
    "dcterms:rights": DCTERMS.rights,
    "dcterms:rightsHolder": DCTERMS.rightsHolder,
    "dcterms:spatial": DCTERMS.spatial,
    "dcat:startDate": DCAT.startDate,
    "dcterms:title": DCTERMS.title,
    "dcterms:type": DCTERMS.type,
    "dcat:version": DCAT.version,
    "prov:generatedAtTime": PROV.generatedAtTime,
    "prov:wasGeneratedBy": PROV.wasGeneratedBy,
    "adms:versionNotes": ADMS.versionNotes,
}

# Properties whose value is a fixed constant (Tier A).
FIXED_VALUES: dict[str, tuple[URIRef, object]] = {
    "dcterms:accessRights": (DCTERMS.accessRights, URIRef(f"{BASE}Confidentiality/Public")),
    "dcterms:type": (DCTERMS.type, URIRef(f"{BASE}type/CIM-PowerSystemModel")),
    "dcterms:license": (DCTERMS.license, URIRef("https://creativecommons.org/licenses/by/4.0/")),
    "dcterms:rights": (DCTERMS.rights, Literal("Copyright")),
    "dcterms:rightsHolder": (DCTERMS.rightsHolder, Literal("ENTSO-E")),
}

# Properties whose object must be an English-tagged literal (Tier A).
LANG_REQUIRED: dict[str, URIRef] = {
    "dcterms:description": DCTERMS.description,
    "adms:versionNotes": ADMS.versionNotes,
}

# Properties that shall not appear in any header (Tier A).
FORBIDDEN_PROPERTIES: dict[str, URIRef] = {
    "dcatcim:alternativeVersionOf": DCATCIM.alternativeVersionOf,
    "dcterms:accrualPeriodicity": DCTERMS.accrualPeriodicity,
    "dcterms:hasPart": DCTERMS.hasPart,
    "dcat:temporalResolution": DCAT.temporalResolution,
    "dcatcim:preferredVersionOf": DCATCIM.preferredVersionOf,
    "dcat:inSeries": DCAT.inSeries,
}

# Namespace URIs that must not be declared (Tier A). Maps URI -> prefix label.
DISALLOWED_NAMESPACES: dict[str, str] = {
    "https://cim4.eu/ns/Metadata-European#": "eumd",
    "http://entsoe.eu/ns/Metadata-European#": "eumd",
    "http://publications.europa.eu/ontology/euvoc#": "euvoc",
}

# The correct dcterms namespace; a trailing '#' is a bug (Tier A).
DCTERMS_URI = "http://purl.org/dc/terms/"

# Datetime-valued properties that must be UTC with a trailing 'Z' (Tier A).
DATETIME_PROPERTIES: dict[str, URIRef] = {
    "dcterms:issued": DCTERMS.issued,
    "dcat:startDate": DCAT.startDate,
    "dcat:endDate": DCAT.endDate,
    "prov:generatedAtTime": PROV.generatedAtTime,
}

PUBLISHER_PATTERN = re.compile(rf"^{re.escape(BASE)}test/party/(TSO|RCC)-.+$")
DATETIME_Z_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

# Tier-B reference-data rules: property -> (scheme key used by schemes.py).
REFERENCE_RULES: dict[str, tuple[URIRef, str, str]] = {
    "dcterms:conformsTo": (DCTERMS.conformsTo, "conformance", "#6"),
    "dcat:isVersionOf": (DCAT.isVersionOf, "model", "#10"),
    "dcterms:spatial": (DCTERMS.spatial, "frame", "#16"),
    "prov:wasGeneratedBy": (PROV.wasGeneratedBy, "activity", "#21"),
    "dcterms:publisher": (DCTERMS.publisher, "party", "#13"),
}


# ------------------------------------------------------------------ violations
@dataclass
class Violation:
    file: str
    rule_id: str
    tier: str  # "A" or "B"
    review_ref: str
    message: str
    fixable: bool = False
    detail: dict = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.tier}] {self.rule_id} ({self.review_ref}): {self.message}"


# ------------------------------------------------------------------ validation
def find_dataset(graph: Graph) -> URIRef | None:
    """Return the dcat:Dataset subject of a header graph, if any."""
    for s in graph.subjects(RDF.type, DCAT.Dataset):
        if isinstance(s, URIRefT):
            return s
    return None


def _lang_ok(obj) -> bool:
    return isinstance(obj, Literal) and (obj.language or "").lower().startswith("en")


def validate_graph(
    graph: Graph, file: str, schemes: "object | None" = None
) -> list[Violation]:
    """Run all header rules against ``graph`` and return the violations found."""
    out: list[Violation] = []
    ds = find_dataset(graph)
    if ds is None:
        # Not a dataset-header file; nothing to validate here.
        return out

    # --- namespace / prefix checks (Tier A) -------------------------------
    for prefix, ns in graph.namespaces():
        uri = str(ns)
        if uri in DISALLOWED_NAMESPACES:
            out.append(Violation(
                file, "disallowed-namespace", "A", "#1/#2",
                f"disallowed namespace declared: {prefix or DISALLOWED_NAMESPACES[uri]}={uri}",
                fixable=True, detail={"uri": uri}))
        if prefix == "dcterms" and uri != DCTERMS_URI:
            out.append(Violation(
                file, "bad-dcterms-namespace", "A", "#1",
                f"dcterms namespace should be {DCTERMS_URI!r}, found {uri!r}",
                fixable=True, detail={"uri": uri}))

    # --- forbidden properties (Tier A) ------------------------------------
    for label, pred in FORBIDDEN_PROPERTIES.items():
        if (ds, pred, None) in graph:
            out.append(Violation(
                file, "forbidden-property", "A", "#3",
                f"forbidden property present: {label}", fixable=True,
                detail={"property": label}))

    # --- required properties present (Tier A) -----------------------------
    for label, pred in REQUIRED_PROPERTIES.items():
        if not any(graph.objects(ds, pred)):
            fixable = label in FIXED_VALUES or label in (
                "dcterms:rights", "dcterms:rightsHolder")
            out.append(Violation(
                file, "missing-required", "A", "#4-#20",
                f"missing required property: {label}", fixable=fixable,
                detail={"property": label}))

    # --- fixed values (Tier A) --------------------------------------------
    for label, (pred, expected) in FIXED_VALUES.items():
        values = list(graph.objects(ds, pred))
        if values and expected not in values:
            out.append(Violation(
                file, "wrong-fixed-value", "A", "#5/#12/#15/#18",
                f"{label} should be {expected}, found {values[0]}", fixable=True,
                detail={"property": label, "expected": str(expected)}))

    # --- language tags (Tier A) -------------------------------------------
    for label, pred in LANG_REQUIRED.items():
        objs = list(graph.objects(ds, pred))
        if objs and not any(_lang_ok(o) for o in objs):
            out.append(Violation(
                file, "missing-lang-tag", "A", "#4/#7",
                f'{label} must be tagged xml:lang="en"', fixable=True,
                detail={"property": label}))

    # --- identifier is a UUID (Tier A) ------------------------------------
    for ident in graph.objects(ds, DCTERMS.identifier):
        try:
            uuid.UUID(str(ident))
        except (ValueError, AttributeError, TypeError):
            out.append(Violation(
                file, "identifier-not-uuid", "A", "#8",
                f"dcterms:identifier is not a UUID: {ident!r}"))

    # --- datetimes are UTC with 'Z' (Tier A) ------------------------------
    for label, pred in DATETIME_PROPERTIES.items():
        for obj in graph.objects(ds, pred):
            if not DATETIME_Z_PATTERN.match(str(obj)):
                out.append(Violation(
                    file, "datetime-not-utc-z", "A", "#9",
                    f"{label} should be UTC ending in 'Z': {obj!r}",
                    detail={"property": label}))

    # --- publisher naming pattern (Tier A) --------------------------------
    for pub in graph.objects(ds, DCTERMS.publisher):
        if not PUBLISHER_PATTERN.match(str(pub)):
            out.append(Violation(
                file, "publisher-naming", "A", "#13",
                f"publisher should match .../test/party/(TSO|RCC)-<Name>: {pub}",
                detail={"value": str(pub)}))

    # --- Tier-B reference-data membership ---------------------------------
    if schemes is not None:
        for label, (pred, scheme_key, ref) in REFERENCE_RULES.items():
            valid = schemes.values_for(scheme_key)
            if not valid:
                continue  # scheme not loaded; skip silently
            for obj in graph.objects(ds, pred):
                if str(obj) not in valid:
                    out.append(Violation(
                        file, f"unknown-{scheme_key}", "B", ref,
                        f"{label} value not found in {scheme_key} scheme: {obj}",
                        fixable=False, detail={"value": str(obj)}))

    return out


def parse_header(path: str) -> Graph:
    """Parse an RDF/XML instance file into a graph (namespaces preserved)."""
    g = Graph()
    g.parse(path, format="xml")
    return g
