"""
Generate missing AssessedElement (AE) and OrdinaryContingency (CO) entries for
branches (ACLineSegment, 2W/3W PowerTransformer) at or above a voltage threshold
that are not yet covered in a grid's NetworkCode AE/CO profiles.

See GitHub issue #318.

Usage:
    python buildScripts/generate_ae_co_branch_coverage.py --grid Belgovia
    python buildScripts/generate_ae_co_branch_coverage.py --grid Belgovia --write

Notes:
    - Pure-stdlib regex-based block parsing is used (not a full RDF/XML parser) so that
      existing file content can be preserved byte-for-byte; new blocks are appended just
      before </rdf:RDF>.
    - GSU (generator step-up) transformers are excluded from scope: a 2-winding
      transformer is classified as GSU if its lowest-voltage end's ConnectivityNode has
      no other attached equipment except a single SynchronousMachine.
    - .trig regeneration is NOT performed by this script -- it requires the Jena
      riot/owl.bat toolchain used by semantic-tools/cim-trig.pl, which is not available
      in this environment. Trig files must be regenerated separately.
"""
from __future__ import annotations

import argparse
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_PATH = REPO_ROOT / "Instance"
COMMON_DATA_EQ = INSTANCE_PATH / "commonData" / "Grid" / "cimxml" / "Grid_CommonData_CGM-CD.xml"

MIN_VOLTAGE_KV = 110.0
BRANCH_TYPES = ("ACLineSegment", "PowerTransformer")

BLOCK_RE = re.compile(
    r'<(cim|nc):(\w+) rdf:ID="_([0-9a-fA-F-]+)">(.*?)</\1:\2>', re.DOTALL
)


@dataclass
class Element:
    tag: str
    id: str
    inner: str


def parse_blocks(text: str) -> list[Element]:
    return [Element(tag=m.group(2), id=m.group(3), inner=m.group(4)) for m in BLOCK_RE.finditer(text)]


def get_literal(inner: str, prop: str) -> str | None:
    m = re.search(rf'<(?:cim|nc):{re.escape(prop)}>([^<]*)</(?:cim|nc):{re.escape(prop)}>', inner)
    return m.group(1) if m else None


def get_resource(inner: str, prop: str) -> str | None:
    m = re.search(rf'<(?:cim|nc):{re.escape(prop)}\s+rdf:resource="#_([0-9a-fA-F-]+)"', inner)
    return m.group(1) if m else None


def sanitize_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def build_name(prefix: str, n: int, branch_name: str, max_len: int = 32) -> str:
    base = f"{prefix}{n}_"
    budget = max(0, max_len - len(base))
    return base + sanitize_name(branch_name)[:budget]


def find_eq_file(grid: str) -> Path:
    candidates = list((INSTANCE_PATH / grid / "Grid" / "cimxml").glob("*_EQ_*.xml"))
    if len(candidates) != 1:
        raise SystemExit(f"Expected exactly one EQ file for {grid}, found {len(candidates)}: {candidates}")
    return candidates[0]


def load_base_voltages() -> dict[str, float]:
    text = COMMON_DATA_EQ.read_text(encoding="utf-8")
    result = {}
    for e in parse_blocks(text):
        if e.tag == "BaseVoltage":
            v = get_literal(e.inner, "BaseVoltage.nominalVoltage")
            if v is not None:
                result[e.id] = float(v)
    return result


def analyze_grid(grid: str) -> dict:
    eq_path = find_eq_file(grid)
    eq_text = eq_path.read_text(encoding="utf-8")
    eq_elements = parse_blocks(eq_text)
    type_map = {e.id: e.tag for e in eq_elements}

    bv_nominal = load_base_voltages()

    acls = [e for e in eq_elements if e.tag == "ACLineSegment"]
    transformers = {e.id: e for e in eq_elements if e.tag == "PowerTransformer"}
    pt_ends = [e for e in eq_elements if e.tag == "PowerTransformerEnd"]
    terminals = [e for e in eq_elements if e.tag == "Terminal"]

    terminal_info = {}
    for e in terminals:
        ce = get_resource(e.inner, "Terminal.ConductingEquipment")
        node = get_resource(e.inner, "Terminal.ConnectivityNode")
        terminal_info[e.id] = (ce, node)

    node_to_equipment: dict[str, set[str]] = defaultdict(set)
    for ce, node in terminal_info.values():
        if node and ce:
            node_to_equipment[node].add(ce)

    # --- qualifying ACLineSegments ---
    qualifying_acl = []
    for e in acls:
        bv_id = get_resource(e.inner, "ConductingEquipment.BaseVoltage")
        kv = bv_nominal.get(bv_id)
        if kv is not None and kv >= MIN_VOLTAGE_KV:
            name = get_literal(e.inner, "IdentifiedObject.name") or e.id
            qualifying_acl.append({"id": e.id, "name": name, "type": "ACLineSegment", "kv": kv})

    # --- group PowerTransformerEnds by transformer ---
    ends_by_transformer: dict[str, list[dict]] = defaultdict(list)
    for e in pt_ends:
        t_id = get_resource(e.inner, "PowerTransformerEnd.PowerTransformer")
        rated_u = get_literal(e.inner, "PowerTransformerEnd.ratedU")
        terminal_id = get_resource(e.inner, "TransformerEnd.Terminal")
        if t_id is None or rated_u is None:
            continue
        ends_by_transformer[t_id].append({"ratedU": float(rated_u), "terminal_id": terminal_id})

    qualifying_pt = []
    gsu_excluded = []
    for t_id, ends in ends_by_transformer.items():
        max_kv = max(e["ratedU"] for e in ends)
        if max_kv < MIN_VOLTAGE_KV:
            continue
        name = get_literal(transformers[t_id].inner, "IdentifiedObject.name") if t_id in transformers else t_id

        is_gsu = False
        if len(ends) == 2:
            lv_end = min(ends, key=lambda e: e["ratedU"])
            _, node = terminal_info.get(lv_end["terminal_id"], (None, None))
            if node:
                others = node_to_equipment.get(node, set()) - {t_id}
                other_types = {type_map.get(o) for o in others}
                if others and other_types == {"SynchronousMachine"}:
                    is_gsu = True

        entry = {"id": t_id, "name": name, "type": "PowerTransformer", "kv": max_kv, "windings": len(ends)}
        if is_gsu:
            gsu_excluded.append(entry)
        else:
            qualifying_pt.append(entry)

    qualifying_branches = sorted(qualifying_acl + qualifying_pt, key=lambda b: b["name"])

    # --- existing AE coverage ---
    ae_path = INSTANCE_PATH / grid / "NetworkCode" / "cimxml" / f"{grid}_AE.xml"
    ae_text = ae_path.read_text(encoding="utf-8") if ae_path.exists() else None
    ae_elements = parse_blocks(ae_text) if ae_text else []

    ae_refs = set()
    ae_numbers = []
    ae_operators, ae_regions = [], []
    for e in ae_elements:
        if e.tag != "AssessedElement":
            continue
        ref = get_resource(e.inner, "AssessedElement.ConductingEquipment")
        if ref:
            ae_refs.add(ref)
        name = get_literal(e.inner, "IdentifiedObject.name") or ""
        m = re.match(r"AE(\d+)(?:_|$)", name)
        if m:
            ae_numbers.append(int(m.group(1)))
        op = get_resource(e.inner, "AssessedElement.AssessedSystemOperator")
        if op:
            ae_operators.append(op)
        reg = get_resource(e.inner, "AssessedElement.ScannedForRegion")
        if reg:
            ae_regions.append(reg)

    covered_ae_ids = {r for r in ae_refs if type_map.get(r) in BRANCH_TYPES}
    missing_ae = [b for b in qualifying_branches if b["id"] not in covered_ae_ids]
    next_ae_num = max(ae_numbers, default=0) + 1

    # --- existing CO coverage ---
    co_path = INSTANCE_PATH / grid / "NetworkCode" / "cimxml" / f"{grid}_CO.xml"
    co_text = co_path.read_text(encoding="utf-8") if co_path.exists() else None
    co_elements = parse_blocks(co_text) if co_text else []

    co_equipment_refs = set()
    co_numbers = []
    ce_numbers = []
    co_operators = []
    for e in co_elements:
        if e.tag == "ContingencyEquipment":
            ref = get_resource(e.inner, "ContingencyEquipment.Equipment")
            if ref:
                co_equipment_refs.add(ref)
            ce_name = get_literal(e.inner, "IdentifiedObject.name") or ""
            m = re.match(r"CE(\d+)(?:_|$)", ce_name)
            if m:
                ce_numbers.append(int(m.group(1)))
        elif e.tag in ("OrdinaryContingency", "OutOfRangeContingency"):
            name = get_literal(e.inner, "IdentifiedObject.name") or ""
            m = re.match(r"CO(\d+)(?:_|$)", name)
            if m:
                co_numbers.append(int(m.group(1)))
            op = get_resource(e.inner, "Contingency.EquipmentOperator")
            if op:
                co_operators.append(op)

    covered_co_ids = {r for r in co_equipment_refs if type_map.get(r) in BRANCH_TYPES}
    missing_co = [b for b in qualifying_branches if b["id"] not in covered_co_ids]
    next_co_num = max(co_numbers, default=0) + 1
    next_ce_num = max(ce_numbers, default=0) + 1

    def resolve(values: list[str]) -> tuple[str | None, list[str]]:
        if not values:
            return None, []
        counts = Counter(values)
        return counts.most_common(1)[0][0], list(counts.keys())

    ae_operator, ae_operator_distinct = resolve(ae_operators)
    ae_region, ae_region_distinct = resolve(ae_regions)
    co_operator, co_operator_distinct = resolve(co_operators)

    return {
        "grid": grid,
        "eq_path": eq_path,
        "ae_path": ae_path,
        "co_path": co_path,
        "qualifying_branches": qualifying_branches,
        "gsu_excluded": gsu_excluded,
        "missing_ae": missing_ae,
        "missing_co": missing_co,
        "next_ae_num": next_ae_num,
        "next_co_num": next_co_num,
        "next_ce_num": next_ce_num,
        "ae_operator": ae_operator,
        "ae_operator_distinct": ae_operator_distinct,
        "ae_region": ae_region,
        "ae_region_distinct": ae_region_distinct,
        "co_operator": co_operator,
        "co_operator_distinct": co_operator_distinct,
    }


def render_ae_block(branch: dict, n: int, operator: str, region: str) -> str:
    mrid = str(uuid.uuid4())
    desc = f"Assessed element for branch {branch['name']} ({branch['type']}, {branch['kv']:.0f} kV)."
    return f'''  <nc:AssessedElement rdf:ID="_{mrid}">
    <nc:AssessedElement.AssessedSystemOperator rdf:resource="#_{operator}"/>
    <nc:AssessedElement.ConductingEquipment rdf:resource="#_{branch['id']}"/>
    <nc:AssessedElement.ScannedForRegion rdf:resource="#_{region}"/>
    <nc:AssessedElement.inBaseCase>true</nc:AssessedElement.inBaseCase>
    <cim:IdentifiedObject.description>{desc}</cim:IdentifiedObject.description>
    <cim:IdentifiedObject.mRID>{mrid}</cim:IdentifiedObject.mRID>
    <cim:IdentifiedObject.name>{build_name("AE", n, branch['name'])}</cim:IdentifiedObject.name>
    <nc:AssessedElement.normalEnabled>true</nc:AssessedElement.normalEnabled>
  </nc:AssessedElement>
'''


def render_co_block(branch: dict, n: int, ce_n: int, operator: str) -> str:
    ce_mrid = str(uuid.uuid4())
    co_mrid = str(uuid.uuid4())
    return f'''  <cim:ContingencyEquipment rdf:ID="_{ce_mrid}">
    <cim:ContingencyElement.Contingency rdf:resource="#_{co_mrid}"/>
    <cim:ContingencyEquipment.Equipment rdf:resource="#_{branch['id']}"/>
    <cim:ContingencyEquipment.contingentStatus rdf:resource="https://cim.ucaiug.io/ns#ContingencyEquipmentStatusKind.outOfService"/>
    <cim:IdentifiedObject.description>The equipment for this contingency; loss of branch {branch['name']}</cim:IdentifiedObject.description>
    <cim:IdentifiedObject.mRID>{ce_mrid}</cim:IdentifiedObject.mRID>
    <cim:IdentifiedObject.name>{build_name("CE", ce_n, branch['name'])}</cim:IdentifiedObject.name>
  </cim:ContingencyEquipment>
  <nc:OrdinaryContingency rdf:ID="_{co_mrid}">
    <nc:Contingency.EquipmentOperator rdf:resource="#_{operator}"/>
    <nc:Contingency.normalMustStudy>true</nc:Contingency.normalMustStudy>
    <cim:IdentifiedObject.description>This is an ordinary contingency; loss of branch {branch['name']} ({branch['type']}, {branch['kv']:.0f} kV).</cim:IdentifiedObject.description>
    <cim:IdentifiedObject.mRID>{co_mrid}</cim:IdentifiedObject.mRID>
    <cim:IdentifiedObject.name>{build_name("CO", n, branch['name'])}</cim:IdentifiedObject.name>
  </nc:OrdinaryContingency>
'''


def insert_before_close(text: str, new_blocks: str) -> str:
    idx = text.rindex("</rdf:RDF>")
    return text[:idx] + new_blocks + text[idx:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grid", required=True, help="Grid name, e.g. Belgovia")
    parser.add_argument("--write", action="store_true", help="Write changes to AE/CO xml files (default: dry-run report only)")
    args = parser.parse_args()

    result = analyze_grid(args.grid)

    print(f"=== {result['grid']} ===")
    print(f"EQ file: {result['eq_path'].relative_to(REPO_ROOT)}")
    print(f"Qualifying branches (>= {MIN_VOLTAGE_KV:.0f} kV, GSU excluded): {len(result['qualifying_branches'])}")
    if result["gsu_excluded"]:
        print(f"GSU transformers excluded: {len(result['gsu_excluded'])}")
        for g in result["gsu_excluded"]:
            print(f"  - {g['name']} ({g['kv']:.0f} kV)")
    print()
    print(f"Missing AE entries: {len(result['missing_ae'])} (next name: AE{result['next_ae_num']})")
    for b in result["missing_ae"]:
        print(f"  - {b['name']:30s} {b['type']:16s} {b['kv']:.0f} kV  id={b['id']}")
    print()
    print(f"Missing CO entries: {len(result['missing_co'])} (next name: CO{result['next_co_num']}, next CE name: CE{result['next_ce_num']})")
    for b in result["missing_co"]:
        print(f"  - {b['name']:30s} {b['type']:16s} {b['kv']:.0f} kV  id={b['id']}")
    print()
    print(f"AE operator to reuse: {result['ae_operator']} (distinct options seen: {result['ae_operator_distinct']})")
    print(f"AE region to reuse:   {result['ae_region']} (distinct options seen: {result['ae_region_distinct']})")
    print(f"CO operator to reuse: {result['co_operator']} (distinct options seen: {result['co_operator_distinct']})")

    if result["ae_operator"] is None or result["co_operator"] is None:
        raise SystemExit("No existing AssessedSystemOperator/EquipmentOperator found to reuse -- cannot proceed without a decision on which operator id to use.")

    ae_blocks = "".join(
        render_ae_block(b, result["next_ae_num"] + i, result["ae_operator"], result["ae_region"])
        for i, b in enumerate(result["missing_ae"])
    )
    co_blocks = "".join(
        render_co_block(b, result["next_co_num"] + i, result["next_ce_num"] + i, result["co_operator"])
        for i, b in enumerate(result["missing_co"])
    )

    print("\n--- sample AE block ---")
    print(ae_blocks[: ae_blocks.find(">\n", 400) + 2] if ae_blocks else "(none)")
    print("\n--- sample CO block pair ---")
    print(co_blocks[: co_blocks.find("</nc:OrdinaryContingency>") + len("</nc:OrdinaryContingency>\n")] if co_blocks else "(none)")

    if args.write:
        if ae_blocks:
            ae_text = result["ae_path"].read_text(encoding="utf-8")
            result["ae_path"].write_text(insert_before_close(ae_text, ae_blocks), encoding="utf-8")
            print(f"\nWrote {len(result['missing_ae'])} AE entries to {result['ae_path'].relative_to(REPO_ROOT)}")
        if co_blocks:
            co_text = result["co_path"].read_text(encoding="utf-8")
            result["co_path"].write_text(insert_before_close(co_text, co_blocks), encoding="utf-8")
            print(f"Wrote {len(result['missing_co'])} CO entries to {result['co_path'].relative_to(REPO_ROOT)}")
        print("\nNOTE: .trig files were NOT regenerated (requires Jena riot/owl.bat toolchain, not available here).")
    else:
        print("\n(dry-run: no files written; pass --write to apply)")


if __name__ == "__main__":
    main()
