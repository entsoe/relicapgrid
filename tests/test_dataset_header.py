"""Dataset-header validation tests.

Report-only until the fixer (phase 2) cleans this branch: while ``ENFORCE`` is
False, Tier-A findings ``xfail`` (visible in CI, non-blocking). Flip ``ENFORCE``
to True once headers are clean so regressions fail the build. Tier-B findings
(reference-scheme membership) are always report-only — blocked on extending the
schemes.
"""
import sys
from pathlib import Path

import pytest
from rdflib import Graph

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "buildScripts"))

from dataset_header.report import by_rule_table, details_text  # noqa: E402
from dataset_header.rules import validate_graph  # noqa: E402
from validate_dataset_header import run  # noqa: E402

# Flip to True in phase 2, after the fixer brings Tier-A to zero.
ENFORCE = False


@pytest.fixture(scope="module")
def findings():
    violations, n_files, headers = run(scope="networkcode")
    return violations


def test_tier_a_headers(findings):
    tier_a = [v for v in findings if v.tier == "A"]
    if not tier_a:
        return
    message = (
        f"**{len(tier_a)} Tier-A dataset-header violations** "
        f"({sum(v.fixable for v in tier_a)} auto-fixable):\n\n"
        f"{by_rule_table(tier_a)}\n\n"
        f"{details_text(tier_a, root=REPO_ROOT)[:4000]}"
    )
    if ENFORCE:
        pytest.fail(message)
    pytest.xfail(message)


def test_tier_b_reference_data(findings):
    tier_b = [v for v in findings if v.tier == "B"]
    if not tier_b:
        return
    pytest.xfail(
        f"{len(tier_b)} Tier-B reference-data violations "
        f"(blocked on scheme extensions):\n\n{by_rule_table(tier_b)}"
    )


# --------------------------------------------------------------- unit tests

_CLEAN_HEADER = """<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    xmlns:dcterms="http://purl.org/dc/terms/"
    xmlns:dcat="http://www.w3.org/ns/dcat#"
    xmlns:adms="http://www.w3.org/ns/adms#"
    xmlns:prov="http://www.w3.org/ns/prov#">
  <dcat:Dataset rdf:about="urn:uuid:b2d1215a-a124-4b6e-9df5-85ecdce9793b">
    <dcterms:accessRights rdf:resource="https://energy.referencedata.eu/Confidentiality/Public"/>
    <dcterms:conformsTo rdf:resource="https://ap.cim4.eu/Contingency/2.3"/>
    <dcterms:description xml:lang="en">desc</dcterms:description>
    <dcterms:identifier>b2d1215a-a124-4b6e-9df5-85ecdce9793b</dcterms:identifier>
    <dcterms:issued>2025-05-18T18:00:00Z</dcterms:issued>
    <dcat:isVersionOf rdf:resource="https://energy.referencedata.eu/test/model/Belgovia-CO"/>
    <dcat:keyword>CO</dcat:keyword>
    <dcterms:license rdf:resource="https://creativecommons.org/licenses/by/4.0/"/>
    <dcterms:publisher rdf:resource="https://energy.referencedata.eu/test/party/TSO-Belgovia"/>
    <dcterms:rights>Copyright</dcterms:rights>
    <dcterms:rightsHolder>ENTSO-E</dcterms:rightsHolder>
    <dcterms:spatial rdf:resource="https://energy.referencedata.eu/test/frame/Belgovia-Transmission"/>
    <dcat:startDate>2025-05-18T18:00:00Z</dcat:startDate>
    <dcterms:title>20250520_Belgovia_CO</dcterms:title>
    <dcterms:type rdf:resource="https://energy.referencedata.eu/type/CIM-PowerSystemModel"/>
    <dcat:version>1.0.0</dcat:version>
    <prov:generatedAtTime>2025-05-15T07:06:25Z</prov:generatedAtTime>
    <prov:wasGeneratedBy rdf:resource="https://energy.referencedata.eu/activity/IGM-CO"/>
    <adms:versionNotes xml:lang="en">Initial version.</adms:versionNotes>
  </dcat:Dataset>
</rdf:RDF>"""


def _validate(xml):
    g = Graph()
    g.parse(data=xml, format="xml")
    return validate_graph(g, "<test>", schemes=None)


def test_clean_header_has_no_tier_a():
    tier_a = [v for v in _validate(_CLEAN_HEADER) if v.tier == "A"]
    assert tier_a == [], "\n".join(str(v) for v in tier_a)


def test_forbidden_property_detected():
    xml = _CLEAN_HEADER.replace(
        "</dcat:Dataset>",
        '<dcterms:hasPart rdf:resource="urn:uuid:x"/></dcat:Dataset>',
    ).replace("<rdf:RDF ", '<rdf:RDF xmlns:dcatcim="https://cim4.eu/ns/dcatcim#" ')
    rules = [v.rule_id for v in _validate(xml)]
    assert "forbidden-property" in rules


def test_disallowed_namespace_detected():
    xml = _CLEAN_HEADER.replace(
        "<rdf:RDF ",
        '<rdf:RDF xmlns:eumd="https://cim4.eu/ns/Metadata-European#" ',
    )
    rules = [v.rule_id for v in _validate(xml)]
    assert "disallowed-namespace" in rules


def test_publisher_naming_detected():
    xml = _CLEAN_HEADER.replace("test/party/TSO-Belgovia", "test/party/Belgovia")
    rules = [v.rule_id for v in _validate(xml)]
    assert "publisher-naming" in rules


# --------------------------------------------------------------- fixer tests
from dataset_header.fixer import fix_text  # noqa: E402


def test_fixer_is_idempotent_on_clean_header():
    new, applied = fix_text(_CLEAN_HEADER)
    assert applied == []
    assert new == _CLEAN_HEADER


def test_fixer_removes_eumd_declaration_and_usage():
    dirty = _CLEAN_HEADER.replace(
        "<rdf:RDF ",
        '<rdf:RDF xmlns:eumd="https://cim4.eu/ns/Metadata-European#" ',
    ).replace(
        "  </dcat:Dataset>",
        "    <eumd:applicationSoftware>X</eumd:applicationSoftware>\n  </dcat:Dataset>",
    )
    new, applied = fix_text(dirty)
    assert "eumd" not in new
    Graph().parse(data=new, format="xml")  # still well-formed


def test_fixer_forces_value_and_normalizes_publisher():
    dirty = (_CLEAN_HEADER
             .replace("type/CIM-PowerSystemModel", "type/Activity")
             .replace("test/party/TSO-Belgovia", "test/party/Belgovia"))
    new, _ = fix_text(dirty)
    assert "type/CIM-PowerSystemModel" in new
    assert "test/party/TSO-Belgovia" in new
    tier_a_fixable = [v for v in _validate(new) if v.tier == "A" and v.fixable]
    assert tier_a_fixable == [], "\n".join(str(v) for v in tier_a_fixable)
