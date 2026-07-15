"""Formatting-preserving auto-fixer for the Tier-A header rules.

Operates on the raw file text (not a re-serialized graph) so diffs stay
minimal and reviewable. Only the deterministic Tier-A subset is fixed;
Tier-B (reference-data) values are never invented here.

Each ``fix_text`` call is idempotent: running it again yields no change.
"""
from __future__ import annotations

import re

# Namespace prefixes that must be dropped entirely.
_DISALLOWED_PREFIXES = ("eumd", "euvoc")

# Canonical publisher party names (bare -> prefixed). Extend as needed.
KNOWN_PARTY = {
    "Belgovia": "TSO-Belgovia",
    "Espheim": "TSO-Espheim",
    "Galia": "TSO-Galia",
    "Svedala": "TSO-Svedala",
    "Jotunheim": "RCC-Jotunheim",
    "JOTUNHEIM": "RCC-Jotunheim",
}

# Fixed-value properties: label -> full element line body (value-forcing).
_FIXED_URI = {
    "dcterms:accessRights": "https://energy.referencedata.eu/Confidentiality/Public",
    "dcterms:type": "https://energy.referencedata.eu/type/CIM-PowerSystemModel",
    "dcterms:license": "https://creativecommons.org/licenses/by/4.0/",
}
_FIXED_LITERAL = {
    "dcterms:rights": "Copyright",
    "dcterms:rightsHolder": "ENTSO-E",
}

_FORBIDDEN = (
    "dcatcim:alternativeVersionOf", "dcterms:accrualPeriodicity",
    "dcterms:hasPart", "dcat:temporalResolution",
    "dcatcim:preferredVersionOf", "dcat:inSeries",
)

_DATASET_OPEN = re.compile(r"<dcat:Dataset\b")


def _indent_of(block: str) -> str:
    m = re.search(r"\n([ \t]+)<", block)
    return m.group(1) if m else "    "


def fix_text(text: str) -> tuple[str, list[str]]:
    """Return (new_text, list_of_applied_fix_ids)."""
    applied: list[str] = []

    # repair a doubled closing quote in an attribute value (well-formedness),
    # e.g. rdf:resource=".../2.4""/> -> .../2.4"/>
    dq = re.sub(r'(="[^"]*)""', r'\1"', text)
    if dq != text:
        text = dq
        applied.append("fix-doubled-quote")

    open_m = _DATASET_OPEN.search(text)
    close_m = re.search(r"\n[ \t]*</dcat:Dataset>", text)
    if not open_m or not close_m:
        return text, applied  # not a header file

    prolog, ds_start = text[:open_m.start()], open_m.start()
    block = text[ds_start:close_m.start()]  # up to the newline before </dcat:Dataset>
    tail = text[close_m.start():]           # newline + indent + close tag + rest

    # --- drop disallowed prefixes (declaration AND any usage) --------------
    for pfx in _DISALLOWED_PREFIXES:
        p = pfx_esc(pfx)
        new = re.sub(rf'\n[ \t]*xmlns:{p}="[^"]*"', "", prolog)
        new = re.sub(rf'[ \t]*xmlns:{p}="[^"]*"', "", new)  # inline
        if new != prolog:
            prolog = new
            applied.append(f"drop-ns:{pfx}")
        # remove usage elements of the dropped prefix so it stays well-formed
        for scope_name in ("block", "tail"):
            src = block if scope_name == "block" else tail
            cleaned = re.sub(rf'\n[ \t]*<{p}:[^>]*>.*?</{p}:[^>]*>', "", src)
            cleaned = re.sub(rf'\n[ \t]*<{p}:[^>]*/>', "", cleaned)
            if cleaned != src:
                if scope_name == "block":
                    block = cleaned
                else:
                    tail = cleaned
                applied.append(f"remove-usage:{pfx}")

    # --- prolog: fix dcterms '#' -------------------------------------------
    if 'xmlns:dcterms="http://purl.org/dc/terms/#"' in prolog:
        prolog = prolog.replace(
            'xmlns:dcterms="http://purl.org/dc/terms/#"',
            'xmlns:dcterms="http://purl.org/dc/terms/"')
        applied.append("fix-dcterms-ns")

    # --- block: remove forbidden properties --------------------------------
    for label in _FORBIDDEN:
        new = re.sub(rf'\n[ \t]*<{re.escape(label)}\b[^>]*/>', "", block)
        new = re.sub(rf'\n[ \t]*<{re.escape(label)}\b[^>]*>.*?</{re.escape(label)}>',
                     "", new)
        if new != block:
            block = new
            applied.append(f"remove:{label}")

    # --- block: force fixed values -----------------------------------------
    for label, uri in _FIXED_URI.items():
        pat = re.compile(rf'(<{re.escape(label)} rdf:resource=")[^"]*(")')
        if pat.search(block) and f'"{uri}"' not in block:
            block = pat.sub(rf'\g<1>{uri}\g<2>', block)
            applied.append(f"force-value:{label}")
    for label, lit in _FIXED_LITERAL.items():
        pat = re.compile(rf'(<{re.escape(label)}>)[^<]*(</{re.escape(label)}>)')
        m = pat.search(block)
        if m and m.group(0) != f'<{label}>{lit}</{label}>':
            block = pat.sub(rf'\g<1>{lit}\g<2>', block)
            applied.append(f"force-value:{label}")

    # --- block: add xml:lang to description / versionNotes -----------------
    for label in ("dcterms:description", "adms:versionNotes"):
        pat = re.compile(rf'<{re.escape(label)}>')
        if pat.search(block):
            block = pat.sub(f'<{label} xml:lang="en">', block)
            applied.append(f"add-lang:{label}")

    # --- block: normalize publisher party naming ---------------------------
    def _pub(m):
        name = m.group(2)
        canon = KNOWN_PARTY.get(name)
        return f'{m.group(1)}test/party/{canon}"' if canon else m.group(0)

    new = re.sub(
        r'(rdf:resource="https://energy\.referencedata\.eu/)[Tt]est/[Pp]arty/([^"/]+)"',
        _pub, block)
    if new != block:
        block = new
        applied.append("normalize-publisher")

    # --- block: insert missing fixed-value props + versionNotes ------------
    indent = _indent_of(block)
    inserts: list[str] = []
    for label, uri in _FIXED_URI.items():
        if f"<{label}" not in block:
            inserts.append(f'{indent}<{label} rdf:resource="{uri}"/>')
    for label, lit in _FIXED_LITERAL.items():
        if f"<{label}" not in block:
            inserts.append(f'{indent}<{label}>{lit}</{label}>')
    if "<adms:versionNotes" not in block:
        inserts.append(f'{indent}<adms:versionNotes xml:lang="en">Initial version.</adms:versionNotes>')
        applied.append("insert:adms:versionNotes(placeholder)")
        if "xmlns:adms" not in prolog:
            prolog = _add_adms_ns(prolog)
            applied.append("add-ns:adms")
    if inserts:
        block = block.rstrip("\n") + "\n" + "\n".join(inserts)
        for ins in inserts:
            label = re.search(r"<([\w:]+)", ins).group(1)
            if not label == "adms:versionNotes":
                applied.append(f"insert:{label}")

    text = prolog + block + tail

    # --- whole file: drop dcatcim ns if now unused -------------------------
    if "dcatcim:" not in re.sub(r'xmlns:dcatcim="[^"]*"', "", text):
        new = re.sub(r'\n[ \t]*xmlns:dcatcim="[^"]*"', "", text)
        new = re.sub(r'[ \t]*xmlns:dcatcim="[^"]*"', "", new)
        if new != text:
            text = new
            applied.append("drop-ns:dcatcim")

    return text, applied


def _add_adms_ns(prolog: str) -> str:
    """Insert an xmlns:adms declaration into the rdf:RDF open tag."""
    decl = 'xmlns:adms="http://www.w3.org/ns/adms#"'
    m = re.search(r"(<rdf:RDF\b)([ \t]*\n)", prolog)
    if m:  # multi-line form: add as first prefix line
        indent_m = re.search(r"\n([ \t]+)xmlns:", prolog)
        indent = indent_m.group(1) if indent_m else "    "
        return prolog.replace(m.group(0), f"{m.group(1)}\n{indent}{decl}\n", 1)
    return prolog.replace("<rdf:RDF", f"<rdf:RDF {decl}", 1)


def pfx_esc(pfx: str) -> str:
    return re.escape(pfx)
