# Loading Relicapgrid to a Semantic Database

Vladimir Alexiev (Grpahwise).
- Last updated: 20-Apr-2026

<!-- markdown-toc start - Don't edit this section. Run M-x markdown-toc-refresh-toc -->
**Table of Contents**

- [Loading Relicapgrid to a Semantic Database](#loading-relicapgrid-to-a-semantic-database)
    - [Trig Conversion and Fixes](#trig-conversion-and-fixes)
        - [Prerequisites](#prerequisites)
        - [Make Targets](#make-targets)
    - [Loading to GraphDB](#loading-to-graphdb)
    - [Data Validation with SPARQL](#data-validation-with-sparql)
        - [Undefined Objects](#undefined-objects)
        - [Undefined Props](#undefined-props)
        - [Mismatched Domain](#mismatched-domain)
        - [Mismatched Range](#mismatched-range)
    - [Exploration](#exploration)
        - [Class Hierarchy](#class-hierarchy)
        - [Domain/Range Diagram](#domainrange-diagram)
        - [Class Relations](#class-relations)
        - [Visual Graph](#visual-graph)

<!-- markdown-toc end -->

## Trig Conversion and Fixes

CIMXML has some shortcomings that need to be fixed for better loading to a semantic database.
This is explained in [Sveino/Inst4CIM-KG/rdf-improved](https://github.com/Sveino/Inst4CIM-KG/tree/develop/rdf-improved), a consulting for ENTSO-E
that Vladimir Alexiev (Graphwise) did in 2024

- Namespaces use a mix of version-free and version-dependent variants, making NCP incompatible with CGMES
  - https://github.com/entsoe/relicapgrid/issues/46
  - https://github.com/entsoe/application-profiles-library/issues/8
- URIs are under-defined since there is no `xml:base`.
  Since no consistent base can be picked for boundary resources, it's best to use `urn:uuid`
- Individual models (instance files) should go to separate named graphs,
  but RDF XML (and CIMXML) doesn't support named graphs
- Literals in instance data lack datatypes.
  This means numbers cannot be properly compared,
  and range searches are slow (can't use literal range indexes)
- CIMXML uses the old `md:FullModel, dm:DifferenceModel` metadata schema,
  but `manifest.ttl` use the new `dcat:Dataset` schema.

These tools fix up CIMXML.
They were developed by Vladimir Alexiev at [Sveino/Inst4CIM-KG/rdf-improved](https://github.com/Sveino/Inst4CIM-KG/tree/develop/rdf-improved),
then copied here and slightly extended.
They are listed in the same order as the problems above:

- `fix-namespaces.pl`: Convert old `cim:` and `eu:` namespaces to the newest namespaces
  - Also fix the `dcterms:` namespace
  - Also remove the leading space from ` http://belgovia.bo/CGMES` that makes it invalid URL
- `cim-urn-uuid.pl`: Convert CIMXML under-defined URIs
  from `rdf:ID="_<uuid>", rdf:about="#_<uuid>, rdf:resource="#_<uuid>`
  to `urn:uuid:<uuid>`
- `cim-trig.pl`: Convert CIM XML file to Trig (Turtle with graphs).
  Invoke with option `-r` to call Jena riot
- `fix-datatypes-and-model.ru`:
  - Add datatypes to literals
  - Convert `md:FullModel, dm:DifferenceModel` to the newest `dcat:Dataset` metadata schema

### Prerequisites

The tools use some standard programs.
We have tested with the following versions, but many other versions should also work:

- make (GNU Make 4.4.1)
- zip (Info-Zip 3.0, July 5th 2008)
- jena `riot` (version 5.2.0: used by `cim-trig.pl`)
- jena `update` (version 5.2.0, used by `fix-datatypes-and-model.ru`)
- perl (v5.38.2) and the following modules:
  - warnings
  - autodie
  - UUID
  - Getopt::Std

### Make Targets
[Instances/Makefile](../Instances/Makefile) uses the tools together.
- As per https://github.com/entsoe/relicapgrid/issues/131 , it looks in 16 fixed folders.
  There are more
- It looks for `xml` files and converts them to `trig`
- It also picks up all `manifest.ttl`
  (it may be better practice to put dataset metadata in the same named graph as the data,
  but such practice is not yet adopted here)
- As per https://github.com/entsoe/relicapgrid/issues/147 ,
  it also picks up all `referenceData/*/ttl/*`
  because the respective `cimxml` files lack any `Dataset` metadata,
  so cannot be slotted into named graphs

First make sure you are in the right folder:
```
cd Instance
```

The `Makefile` defines the following targets:
- `make` shows the targets
- `make dirs` makes the required `trig` folders
- `make echo` lists the `trig` and `ttl` files to be zipped
- `make trig` creates `.trig` from `.xml`
- `make validate` checks each `trig` and `ttl` file with jena riot
- `make zip`: makes `relicapgrid-CGM-trig.zip` with all  `trig` and `ttl` files (3.9Mb at 20 Apr 2026).
  It can be loaded directly to the GraphDB semantic database

## Loading to GraphDB

https://cim.ontotext.com/graphdb is a GraphDB instance maintained by Graphwise

Repo `cim` is used by the Statnett and Graphwise project [talk2powersystem](https://github.com/statnett/talk2powersystem).
- https://cim.ontotext.com/chat is the `CIMon` chatbot that you can try
- It includes the following synthetic datasets:
  [Nordic44](https://github.com/statnett/Nordic44) (TSO) and [Telemark120](https://github.com/statnett/CIM4NoUtility) (DSO, also called CIM4NoUtility or DIGIN10).
  See [Related-Repositories](https://github.com/statnett/Talk2PowerSystem/wiki/Related-Repositories) for more details.
- Shameless plug:
  register for our [Talk2PowerSystem: Democratizing Power System Analytics via Generative AI](https://graphwise.ai/event/talk2powersystem-democratizing-power-system-analytics-via-generative-ai/)
  webinar on 21 May 2026 that includes
  CIMon project results, live demo, and an expert panel with PNNL & Siemens Energy

Repo `relicapgrid` is used to load this data and experiment with it
- SPARQL querying: https://cim.ontotext.com/graphdb/sparql?repositoryId=relicapgrid
- I have loaded the `relicapgrid-CGM-trig.zip` data:
> relicapgrid-CGM-trig.zip, 3.93 mb: Imported successfully in 3s. Added 307243 statements

- I also loaded the ontologies from [Sveino/Inst4CIM-KG/rdfs-improved/CGMES-NC-ttl.zip](https://github.com/Sveino/Inst4CIM-KG/raw/refs/heads/develop/rdfs-improved/CGMES-NC-ttl.zip) (472k)
> Imported successfully in 1s. Added 65849 statements

## Conversion and Loading to GraphDB using Docker

To create image with dependencies and scripts:

Edit refresh-data.sh and add values for GDBUSER and GDBPASS variables at the very top of the file and run:

> docker build -t semantic-tools-image .

To use Docker semantic-tools-image guest shell:
> docker run -it semantic-tools-image bash

To run data coversion and uploading to cim.ontotext.com/graphdb/ repository:
>./refresh-data.sh

Now let's try some queries.

## Data Validation with SPARQL

### Undefined Objects

The query `undef-objects` looks for undefined objects, i.e. broken links.
As you see below, I developed it incrementally by adding exceptions.

```sparql
PREFIX adms: <http://www.w3.org/ns/adms#>
PREFIX cims: <http://iec.ch/TC57/1999/rdf-schema-extensions-19990926#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX nc: <https://cim4.eu/ns/nc#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX prefix: <http://qudt.org/vocab/prefix/>
PREFIX prof: <http://www.w3.org/ns/dx/prof/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX quantitykind: <http://qudt.org/vocab/quantitykind/>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfg: <http://www.w3.org/2004/03/trix/rdfg-1/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX uml: <http://iec.ch/TC57/NonStandard/UML#>
PREFIX unit: <http://qudt.org/vocab/unit/>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>

SELECT * {
    ?x ?p ?y
    # look for objects that are resources
    filter(isIRI(?y) &&
    # that don't have a type (so presumably, no statements at all)
    !exists {?y a ?type} &&
    # and are not in the standard ontologies
    !strstarts(str(?y),str(owl:)) &&
    !strstarts(str(?y),str(rdfg:)) &&
    !strstarts(str(?y),str(dcat:)) &&
    !strstarts(str(?y),str(adms:)) &&
    !strstarts(str(?y),str(dct:)) &&
    !strstarts(str(?y),str(prov:)) &&
    !strstarts(str(?y),str(prof:)) &&
    !strstarts(str(?y),str(qudt:)) &&
    !strstarts(str(?y),str(quantitykind:)) &&
    !strstarts(str(?y),str(prefix:)) &&
    !strstarts(str(?y),str(unit:)) &&
    !strstarts(str(?y),str(skos:)) &&
    !strstarts(str(?y),str(xsd:)) &&
    # and are not standard objects
    ?y not in (<https://creativecommons.org/licenses/by/4.0/>, <https://www.apache.org/licenses/LICENSE-2.0>, <https://opendatacommons.org/licenses/odbl/>, <https://creativecommons.org/licenses/by-nc/4.0/>, <https://creativecommons.org/licenses/by-sa/4.0/>, <https://opendatacommons.org/licenses/pddl/1-0/>, <http://www.iana.org/assignments/media-types/application/rdf+xml>, geo:Geometry) &&
    !strstarts(str(?y),"http://publications.europa.eu/resource/authority/") &&
    # and are not placeholders
    ?y not in (<urn:placeholder:spatial>, <urn:placeholder:license>, <urn:placeholder:publisher>, <https://energy.referencedata.eu/Test/Action/PlaceholderGeneration>) &&
    # and are not yet defined in CIMS or UML
    ?y not in (cims:ClassCategory) &&
    ?p not in (cims:stereotype, cims:multiplicity) &&
    # and are not yet defined (but should be at some point)
    ?y not in (<https://www.statnett.no/en/about-statnett/contact-us/>, <https://www.entsoe.eu/>) &&
    !regex(str(?y),"^https://energy.referencedata.eu/(CGM/SoftwareAgent|Frame|NameType|activity|type|test/(action|frame|party|model))/","i") &&
    # and is not a file dcat:accessURL (but see https://github.com/entsoe/relicapgrid/issues/124)
    !strstarts(str(?y),"file://cimxml/") &&
    # and are not conformance or super-dataset or legislation URLs (which should be defined at some point)
    ?p not in (dct:conformsTo, dcat:isVersionOf, dcat:applicableLegislation, dcat:landingPage) &&
    # and are not OWL versioned URLs
    ?p not in (owl:versionIRI, owl:incompatibleWith, owl:priorVersion, owl:backwardCompatibleWith) &&
    # nor PropertyReference to ref data
    ?p not in (nc:StaticPropertyRange.PropertyReference, nc:GridStateAlteration.PropertyReference)
  )
} order by ?y
```

Of immediate concern:
- 16 UUIDs that are not defined: https://github.com/entsoe/relicapgrid/issues/151
- The `provcim` ontology is not defined. 10 resources use it: https://github.com/entsoe/relicapgrid/issues/152
- 2 `nc` terms are not defined: https://github.com/entsoe/relicapgrid/issues/153
- 3 various undefined objects: https://github.com/entsoe/relicapgrid/issues/154


To be fixed later on:
- The `cims:` ontology (and `uml:` stereotypes it uses) are not defined: https://github.com/sveino/Inst4CIM-KG/issues/161
- Many resources from https://energy.referencedata.eu are used but not defined (don't resolve). See https://github.com/entsoe/relicapgrid/issues/102 for more


### Undefined Props

The query `undef-props` looks for undefined props

```sparql
PREFIX adms: <http://www.w3.org/ns/adms#>
PREFIX cim: <https://cim.ucaiug.io/ns#>
PREFIX cims: <http://iec.ch/TC57/1999/rdf-schema-extensions-19990926#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX json-ld: <https://www.w3.org/ns/json-ld#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX prof: <http://www.w3.org/ns/dx/prof/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfg: <http://www.w3.org/2004/03/trix/rdfg-1/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX uml: <http://iec.ch/TC57/NonStandard/UML#>
SELECT * {
  ?x ?p ?y
  filter (not exists {?p a ?kind} &&
    # and are not in the standard ontologies
    !strstarts(str(?p),str(rdf:)) &&
    !strstarts(str(?p),str(rdfs:)) &&
    !strstarts(str(?p),str(owl:)) &&
    !strstarts(str(?p),str(dcat:)) &&
    !strstarts(str(?p),str(dct:)) &&
    !strstarts(str(?p),str(skos:)) &&
    !strstarts(str(?p),str(geo:)) &&
    !strstarts(str(?p),str(prov:)) &&
    !strstarts(str(?p),str(prof:)) &&
    !strstarts(str(?p),str(qudt:)) &&
    ?p not in (json-ld:base, dc:source) &&
    # and are not yet defined (but should)
    !strstarts(str(?p),str(cims:)) &&
    ?p not in (cim:unitMultiplier, cim:unitSymbol)
  )
} order by ?p
```

- About 10 undefined `cim, nc` props: https://github.com/entsoe/relicapgrid/issues/155
- 4 undefined `provcim` props: https://github.com/entsoe/relicapgrid/issues/152

### Mismatched Domain

The query `mismatch-domain` looks for props with mismatched domain, i.e. used on a class they are not attached to:
```sparql
PREFIX adms: <http://www.w3.org/ns/adms#>
PREFIX cim: <https://cim.ucaiug.io/ns#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX md: <http://iec.ch/TC57/61970-552/ModelDescription/1#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX prof: <http://www.w3.org/ns/dx/prof/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT * {
  ?x ?p ?y.
  ?p rdfs:domain ?domain
  filter (
    isIRI(?x) &&
    ?domain not in (md:Model) &&
    ?p not in (dct:conformsTo, dct:title, dct:description, dct:identifier, dct:issued, dcat:version, dcat:isVersionOf, dct:license, dct:rights, dct:rightsHolder, dct:accessRights, dct:spatial, dcat:keyword, prov:generatedAtTime, prov:wasGeneratedBy, adms:versionNotes, dct:source) &&
    not exists {?x rdf:type/rdfs:subClassOf* ?domain})
    optional {?x sesame:directType ?type}
} order by ?type
```

Issues describing the exceptions:
- hijacked `rdfs:domain` in Header (MAJOR breakage): https://github.com/sveino/Inst4CIM-KG/issues/178
  - full list of hijacked terms: `dct:conformsTo, dct:title, dct:description, dct:identifier, dct:issued, dcat:version, dcat:isVersionOf, dct:license, dct:rights, dct:rightsHolder, dct:accessRights, dct:spatial, dcat:keyword, prov:generatedAtTime, prov:wasGeneratedBy, adms:versionNotes, dct:source`
- 4 `nc` classes without appropriate superclass: https://github.com/entsoe/relicapgrid/issues/160

### Mismatched Range

This query looks for props with mismatched range, i.e. used with a wrong value (literal or resource):
```
PREFIX adms: <http://www.w3.org/ns/adms#>
PREFIX cim: <https://cim.ucaiug.io/ns#>
PREFIX cims: <http://iec.ch/TC57/1999/rdf-schema-extensions-19990926#>
PREFIX dc: <http://purl.org/dc/elements/1.1/>
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX dct: <http://purl.org/dc/terms/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX json-ld: <https://www.w3.org/ns/json-ld#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX prof: <http://www.w3.org/ns/dx/prof/>
PREFIX prov: <http://www.w3.org/ns/prov#>
PREFIX qudt: <http://qudt.org/schema/qudt/>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT * {
  ?x ?p ?y.
  ?p rdfs:range ?range
  filter(
    ?p not in (dct:conformsTo, dct:accessRights, dct:publisher, dct:license, dct:spatial, prov:wasGeneratedBy,
            dct:rights, dct:title, dct:description, adms:versionNotes,
            dct:issued, dcat:startDate, dcat:endDate, prov:generatedAtTime) &&
    datatype(?y) != ?range &&
    not exists {?y rdf:type/rdfs:subClassOf* ?range})
}
```

I have posted these issues describing the exceptions:
- `conformsTo, publisher, accessRights` should be URLs not strings: https://github.com/entsoe/relicapgrid/issues/156
- `dct:title, dct:description, dct:rights, adms:versionNotes`: string on langString? https://github.com/entsoe/relicapgrid/issues/157
- `dct:issued, dcat:startDate, dcat:endDate`: date or dateTime? https://github.com/entsoe/relicapgrid/issues/158
- `dct:spatial, prov:wasGeneratedBy` cannot be dcat:Dataset! https://github.com/entsoe/relicapgrid/issues/159

## Exploration

But it's not all bug finding.
Let's try some data exploration.

- I've enabled Autocomplete, so you can explore both ontology terms and instance data (resources)
  - "power tra" completes to the class `cim:PowerTransformer`
  - "trafo" finds a number of resources named "... TRAFO"
  - "STUPET G4" completes to several resources called by that name, amongst them `HydroGeneratingUnit, ControlAreaGeneratingUnit, SynchronousMachine` ...
  - It also finds resources with a longer name, eg `STUPET_G4_TRAFO`

### Class Hierarchy

[Class Hierarchy](https://cim.ontotext.com/graphdb/hierarchy?repositoryId=relicapgrid) shows the 884 classes used in this data.
You can zoom to any level to see its subclasses.

Eg below you see that the largest subclass of IdentifiedObject (that is not PowerSystemResource) 
is `ACDCTerminal` (over 7k instances):

![](img/classHierarchy.png)

### Domain/Range Diagram

From the previous diagram, you can explore the domain (outgoing) and range (incoming) links of a class, eg
- [Domain/Range of cim:Terminal](https://cim.ontotext.com/graphdb/domain-range-graph?repositoryId=relicapgrid&uri=https:%2F%2Fcim.ucaiug.io%2Fns%23Terminal&name=cim:Terminal&collapsed=false)

![](img/domainRangeGraph-Terminal.png)

### Class Relations

[Class Relations](https://cim.ontotext.com/graphdb/relationships?repositoryId=relicapgrid) show the count of relations between classes.

You can explore incoming, outgoing, or all relations both as a count and as choroplets, eg
- Relations of Terminal

![](img/classRelations-Terminal.png)

You can also filter by class name (include) or remove (exclude) classes.

You can also see a second-level breakdown by clicking on "Related Classes" on a row in the table on the left.

### Visual Graph

[VisualGraph](https://cim.ontotext.com/graphdb/graphs-visualizations?uri=urn:uuid:a6ce9705-e654-b6ae-7cce-483726a1ffa9&repositoryId=relicapgrid) is used to make diagrams of particular instance resources.

It first shows some Graph Configurations. 
The most useful amongst them are:
- CIM: for instance data
- Classes and Relations: for exploring the ontology

Then it shows some Saved Graphs:
- [SynchronousMachine STUPET_G4](https://cim.ontotext.com/graphdb/graphs-visualizations?repositoryId=relicapgrid&saved=2cc1935b71f5464c8b286dd38b0e4fa9) is from Relicapgrid

![](img/vizGraph-STUPET_G4.png)

- But there are also a lot more graphs saved from the Nordic44+Telemark120 datasets
