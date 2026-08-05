# GeographicalRegion & SubGeographicalRegion — Design Considerations

This note captures the modelling rules the dataset follows for `cim:GeographicalRegion`
and `cim:SubGeographicalRegion`, and why. It exists because both classes can legally
appear in more than one file, and getting the duplication rule wrong reintroduces the
exact inconsistency this project once had to fix (issue #134 / PR #182).

## The core rule

> Cross-file duplication of the same `rdf:ID` is allowed, but only as a **byte-identical
> copy** — same mRID, name, and every other property. Never two definitions of the same
> real-world object with different property values under one shared ID, and never two
> *different* IDs standing in for what should be the same object.

Issue #134 was exactly the anti-pattern this forbids: Britheim carried two
`GeographicalRegion` instances, same name, **different** `mRID`s — an inconsistency, not
a duplication. PR #182 fixed it and established where each class canonically lives.

## Canonical location by class

| Class | Canonical home | Cross-file duplicate allowed? |
|---|---|---|
| `GeographicalRegion` | `commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml` | Yes, identical copy in the owning TSO's EQ file |
| `SubGeographicalRegion` | The owning TSO's own EQ file | Yes, identical copy wherever a `Substation` referencing it is itself duplicated |

`GeographicalRegion` is deliberately centralised in CommonData — one file is the source
of truth for the top-level region catalogue shared by every TSO. `SubGeographicalRegion`
stays local to each TSO's EQ file instead, since it's finer-grained and normally has no
reason to be shared.

**Living example — Nordheim** (`_9356077b-...`): defined identically, description and
all, in both `Grid_CommonData_CGM-CD.xml` and `Nordheim_EQ_1.xml`. PR #182 kept this one
TSO duplicated on purpose, specifically to demonstrate that a compliant identical copy
is possible and validator-safe — every other TSO's `GeographicalRegion` exists only in
CommonData.

## Why duplication is sometimes unavoidable: shared boundary substations

Most borders in this dataset are plain AC tie-lines (`BoundaryPoint` on a `Line`) and
never define a `Substation`, so the question doesn't arise. Two borders are different —
`Espheim-Portheim` and `Galia-Nordheim` model an **AC Substation Boundary**: a single
`Substation` straddling the border, described in
[`BoundaryConfigurations.adoc`](BoundaryConfigurations.adoc).

`cim:Substation.Region` is mandatory (1..1) — every `Substation` in this dataset has
exactly one. Because the boundary file and each owning TSO's EQ file all carry their own
copy of that shared `Substation` (and its `VoltageLevel`), each copy's
`Substation.Region` needs a `SubGeographicalRegion` that resolves *within that file*,
not just across the combined model graph. So the `SubGeographicalRegion` has to be
duplicated identically everywhere its `Substation` is duplicated:

| Border | Shared `Substation` lives in | `SubGeographicalRegion` must therefore live in |
|---|---|---|
| Espheim–Portheim | Boundary file + Espheim EQ + Portheim EQ (3 copies) | Same 3 files, identical copy |
| Galia–Nordheim | Boundary file + Nordheim EQ (2 copies — Galia has no side of it) | Same 2 files, identical copy |

Each duplicated copy carries a description noting where its siblings live, e.g.
*"...this instance appears in two EQ files and in the Boundary"* — the same convention
already used on the `Substation` and `VoltageLevel` objects it belongs to.

## Checklist for contributors

- Adding a new TSO's top-level region? Define it once in CommonData; don't add EQ-only
  copies unless you're intentionally demonstrating duplication.
- Adding/editing a `SubGeographicalRegion`? It belongs in the owning TSO's EQ file.
- Only duplicate either class across files when a `Substation` (or other referencing
  object) is *itself* duplicated across those same files — and make every copy
  byte-identical, with a description noting the duplication.
- Never let two files disagree about the same `rdf:ID`, and never mint a second ID for
  what should be one region.
