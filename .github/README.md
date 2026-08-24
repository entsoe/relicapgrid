# ReliCapGrid Test Model

ICTC approved on 11 September 2025 — actively improved and enhanced throughout 2026.

## Introduction
This repository contains a synthetic grid model (fake, with no reference to real IGM/CGM elements)​ that instances of the ENTSO-E CIM extension called "Network Code Profiles" refer to.

> **Note:** This document uses several technical abbreviations (e.g., TSO, IGM, CGM, CSA). For full definitions, please refer to the [Glossary of Abbreviations](#glossary-of-abbreviations) at the end of this README.

The aim is to demonstrate practical TSO and RCC data exchange use cases for the Regional Coordination Processes, namely the Coordinated Security Analysis (CSA), Coordinated Capacity Calculation (CCC), Outage Planning Coordination (OPC) and the Short-Term Adequacy (STA).

The Regional Coordination Processes Data Exchange Specification (RCP DES) complements the test model as this is the document describing use cases and general guidance on the use of Network Code Profiles. Find this data exchange specification and more on the [ENTSO-E's CGMES Library](https://www.entsoe.eu/data/cim/cim-for-grid-models-exchange).

ENTSO-E continuously collaborates with an ecosystem of TSOs, RCCs, regional projects and relevant industry software vendors. One of the outputs of this collaboration is the ReliCapGrid test model. Readers can consult the Accreditations section down below to see the list of people and organisations collaborating under the [CC-BY-SA-4.0 open-source License](../LICENSE.md).

The following chapters describe the model content, which will be continuously improved in subsequent releases.

### How to provide feedback
When importing any data contained in the repository, you might find some bugs or issues to report. Please, open a GitHub issue and include your export log when applicable.

Do not forget to read the [CONTRIBUTING](../.github/CONTRIBUTING.adoc) file.

### License
Please, refer to the [LICENSE](../LICENSE.md) for more information on the open-source license collaboration framework of the repository.

### Accreditations
List of the people and organisations contributing to this repository.

- [@HarisVranaj](https://github.com/HarisVranaj) - ENTSO-E
- [@Haigutus](https://github.com/Haigutus) - Gridraven
- [@sam-phillipson1](https://github.com/sam-phillipson1) - Siemens A.G.
- [@Hakr-DNV](https://github.com/Hakr-DNV) - DNV
- [StephanLupp](https://github.com/StephanLupp) - DNV
- [@fengtu2024](https://github.com/fengtu2024) - PowerInfo
- [@SanPen](https://github.com/SanPen) - eRoots
- [@tviegut](https://github.com/viegut) - AspenTech
- [@fmalicevicdigsilent](https://github.com/fmalicevicdigsilent) - DIgSILENT
- [@LarsTruelsenEnerginet](https://github.com/LarsTruelsenEnerginet) and [@Holdersen](https://github.com/Holdersen) - Energinet
- [@VladimirAlexiev](https://github.com/VladimirAlexiev) - Graphwise (Ontotext)
- [@griddigit-ci](https://github.com/griddigit-ci), [@benceszirbik](https://github.com/benceszirbik), [@benedekfodor](https://github.com/benedekfodor), [@MateZsebehazi](https://github.com/MateZsebehazi) - gridDigIt
- [@jakubscg](https://github.com/jakubscg) - PSE
- [@pweaver-rte](https://github.com/pweaver-rte) - RTE
- [@sindrevh](https://github.com/sindrevh) - Siemens A.G.
- [@Sveino](https://github.com/Sveino) - Statnett
- [@emhg23](https://github.com/emhg23) - Svenska kraftnät
- [@dariaT-swissgrid](https://github.com/dariaT-swissgrid) - Swissgrid
- [@PavelKocica](https://github.com/PavelKocica) - Unicorn
- [@makkes](https://github.com/makkes) - Valimate

It must be mentioned that the synthetic grid model *Svedala* is based on [Svenska Kraftnät's](https://www.svk.se/) test model of the same name, which is licensed under [CC BY-SA 4-0 open-source license](https://creativecommons.org/licenses/by-sa/4.0/).


---

### How to Assemble File Packages for Import

Each TSO's grid model files are organized under [Instance/*TSO*/Grid](../Instance) folders, serialized in multiple forms, with **CIMXML** being the primary serialization under active development. Similarly, the test Network Code Profiles instance datasets can be found under [Instance/*TSO*/NetworkCode](../Instance).
The following guidance describes which files to combine when creating import packages for your tooling.

**Individual Grid Model import with individual boundary files - IGM**

- All profiles from the respective `Instance/<TSO>/Grid/cimxml` folder (EQ, SSH, SV, TP)
- The relevant per-border boundary file(s) from `Instance/boundaryData/Grid/cimxml`
- CommonData for Grids: `Instance/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml`

  additionally the Network Code Profiles:

- Desired profiles from the respective `Instance/<TSO>/NetworkCode/cimxml` folder
- CommonData for Network Code: `Instance/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml`

#### Common Grid Model creation - CGM

- The EQ profile from **each** `Instance/<TSO>/Grid/cimxml` folder
- All files from `Instance/Jotunheim/Grid/cimxml` (SSH, TP, SV)
- All relevant per-border boundary file(s) from `Instance/boundaryData/Grid/cimxml`
- CommonData for Grids: `Instance/commonData/Grid/cimxml/Grid_CommonData_CGM-CD.xml`

  additionally the Network Code Profiles:

- Desired profiles from the respective `Instance/<TSO>/NetworkCode/cimxml` folder
- CommonData for Network Code: `Instance/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml`


The load flow calculation parameters are documented in the [power flow settings document](../docs/PowerFlowCalculationSettings.adoc).


The [sematic-tools](../semantic-tools) folder includes some scripts to convert CIMXML to Trig (Turtle with named graphs) and fix some instance data problems, and it describes the location of Trig files and how to zip them up together with all manifest.ttl files, for direct loading to a semantic graph database.


---

### The Grid Test Model
ReliCapGrid consists of the following fictitious TSOs, as shown in Figure 1 below:
- Espheim - developed based on legacy SmallGrid Test Configuration
- Svedala - developed based on Svenska Kraftnät's Svedala Test Configuration
- Belgovia - developed based on legacy MicroGrid Test Configuration
- Galia - developed based on legacy MicroGrid Test Configuration
- Nordheim - only one node
- Britheim - includes HVDC internal interconnection VSC and also some small grid 1-2 nodes
- Portheim - few nodes modelled in a boundary substation 
- HVDC Espheim-Svedala - an HVDC IGM LCC
- HVDC Nordheim-Galia - an HVDC IGM VSC Bipole

All of them are in a geographical region called *Nine Realms*. This information and more - like the voltage level of the transmission network - is available in the synthetic *Common Data* dataset that has been created for ReliCapGrid. As the name suggests, it is designed to replicate the real (public), more extensive ENTSO-E Common Data dataset available on the [CGMES Library](https://www.entsoe.eu/data/cim/cim-for-grid-models-exchange/).

![Figure 1: Visualisation of ReliCapGrid's synthetic grid model](Media/ReliCapGrid_map1.png)

A [detailed boundary description](../docs/BoundaryConfigurations.adoc) is available in the docs folder.

### The Network Code Instances
The *Nine Realms* region that ReliCapGrid represents also happens to be a capacity calculation region called *CCR-NineRealms* that has a few synchronous areas, with *SyncArea-Continental* being the main one. 

The *SecurityCoordinator* and *CoordinatedCapacityCalculator* roles are represented by *Jotunheim*, which is analogous to a Regional Coordination Centre (RCC) in the real world.

This information and more (e.g., BiddingZoneBorder) is again represented in the *Common Data* dataset that the Network Code Profiles instances use. A [synthetic common data dataset for the Network Code Profiles](../Instance/commonData/NetworkCode/cimxml/Org-NineRealms_CD.xml) has been created and follows the roles defined in the PowerSystemOrganizationRole diagram of the EquipmentReliability profile (refer to Figure 2).

![Figure 2: roles defined in the PowerSystemOrganizationRole diagram of the EquipmentReliability profile](../.github/Media/PowerSystemOrganizationRole.png)


### Currently demonstrated Network Code Profiles instances
Currently, four of the TSOs in NineRealms (Belgovia, Galia, Svedala and Espheim) have provided their Network Code Profile instances for Jotunheim to use in coordination.

Namely, the AssessedElement (AE), Contingency (CO), EquipmentReliability (ER), RemedialAction (RA), RemedialActionSchedule (RAS), StateInstructionSchedule (SIS), SteadyStateInstruction (SSI) and ImpactAssessmentMatrix (IAM) are demonstrated in the ReliCapGrid repository.

As already mentioned, ENTSO-E explains the use of the Network Code Profiles in the Regional Coordination Processes Data Exchange Specification.

The ReliCapGrid Network Code Profile instance data will be further developed and demonstrated in subsequent releases.

### Glossary of Abbreviations

This section provides definitions for the technical abbreviations used throughout this repository, categorized by their role in the power system and data exchange processes.

#### Organizations & Standards
* **ENTSO-E**: European Network of Transmission System Operators for Electricity
* **ICTC**: Information and Communication Technologies Committee (ICTC) is a specialized committee within ENTSO-E
* **CIM**: Common Information Model (IEC 61970/61968 standards)
* **CGMES**: Common Grid Model Exchange Standard
* **RCP DES**: Regional Coordination Processes Data Exchange Specification

#### Grid Modeling & Infrastructure
* **TSO**: Transmission System Operator
* **RCC**: Regional Coordination Centre
* **IGM**: Individual Grid Model
* **CGM**: Common Grid Model
* **CCR**: Capacity Calculation Region
* **HVDC**: High-Voltage Direct Current
* **LCC / VSC**: Line-Commutated Converter / Voltage Source Converter (HVDC technologies)

#### Coordination Processes
* **CSA**: Coordinated Security Analysis
* **CCC**: Coordinated Capacity Calculation
* **OPC**: Outage Planning Coordination
* **STA**: Short-Term Adequacy

#### Network Code Profile (NCP) Instances
* **AE**: Assessed Element
* **CO**: Contingency
* **ER**: Equipment Reliability
* **RA / RAS**: Remedial Action / Remedial Action Schedule
* **SIS**: State Instruction Schedule
* **SSI**: Steady State Instruction
* **IAM**: Impact Assessment Matrix

#### Licensing
* **CC-BY-SA-4.0**: Creative Commons Attribution-ShareAlike 4.0 International License