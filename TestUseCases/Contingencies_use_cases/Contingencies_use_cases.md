---
title: Contingencies use cases
---

# Contingencies use cases


This use case validates the handling of contingency data **Contingency (CO) Profile**, including import, execution, update, and export of contingencies against a CGM/IGM network model.


## Test flow


### Test data overview 

| UC ID | Title | Contingency type | EQ object (CGMES) | EQ mRID | Contingency description (CO) | CO mRID |
|---|---|---|---|---|---|---|
| CO_UC1 | Importing, executing, updating and exporting contingencies | Ordinary – loss of single line | Belgovia tie-line with Galia (ACLineSegment) | `d9622e7f-5bf0-4e7e-b766-b8596c6fe4ae` | Loss of TieLine between Belgovia and Galia | `7e31c67d-67ba-4592-8ac1-9e806d697c8e` |
| CO_UC2 | ″ | Ordinary – loss of single line | Belgovia tie-line with Svedala (ACLineSegment) | `ed0c5d75-4a54-43c8-b782-b20d7431630b` | Loss of TieLine between Belgovia and Svedala | `e9eab3fe-c328-4f78-9bc1-77adb59f6ba7` |
| CO_UC3 | ″ | Ordinary – loss of single line | Espheim tie-line with Svedala (ACLineSegment) | `b85e5fb8-7e2b-4264-a059-edab9a838116` | Loss of TieLine between Espheim and Svedala | `8cdec4c6-10c3-40c1-9eeb-7f6ae8d9b3fe` |
| CO_UC4 | ″ | Ordinary – loss of transformer | Svedala power transformer DALBO_G1_TRAFO | `f1c13f90-6d89-4a37-a51c-94742ad2dd72` | Loss of power transformer in Svedala | `e05bbe20-9d4a-40da-9777-8424d216785d` |
| CO_UC5 | ″ | Ordinary – loss of voltage compensation | Espheim LinearShuntCompensator “Roanoke SC” | `0489d903-c766-11e1-8775-005056c00008` | Loss of LinearShuntCompensator | `62eac668-82a1-4739-8cfc-de929b78ef7e` |
| CO_UC6 | ″ | Ordinary – loss of voltage compensation | Svedala NonlinearShuntCompensator “FT62_X3” | `8464a151-ec39-4e7a-8321-06c41e63958c` | Loss of NonlinearShuntCompensator | `ab92defa-ef8e-4d13-a242-5b1a9fe956f6` |
| CO_UC7 | ″ | Ordinary – loss of HVDC converter | HVDC Espheim–Svedala CsConverter | `038ce404-30dc-4289-b9db-7076cb870b8e` | Loss of HVDC converter DC-3P-Convert-1 | `66627b36-aecd-4141-ab99-4bd8a74d18a8` |
| CO_UC8 | ″ | Ordinary – loss of HVDC line | HVDC Espheim–Svedala DCLineSegment | `be09fc02-de3f-49e4-aa84-94803bcc5d76` | Loss of HVDC line | `504b48fb-de1f-4f7e-928f-8585daaf7b72` |
| CO_UC9 | ″ | Ordinary – loss of generation unit | Belgovia SynchronousMachine | `550ebe0d-f2b2-48c1-991f-cebea43a21aa` | Loss of synchronous machine | `37997e71-cb7d-4a8c-baa6-2a1594956da9` |
| CO_UC10 | ″ | Ordinary – loss of demand facility | Svedala ConformLoad CT72_T1_LAST | `ebf0cd8b-a357-4e97-aa67-de5b263733d6` | Loss of demand facility | `f3a8c241-7b5e-4d92-b1c6-8e3f092a4d71` |
| CO_UC11 | ″ | Out‑of‑range – N‑2 loss of lines | Espheim two independent tie-lines | `04566cf8-c766-11e1-8775-005056c00008`, `0475dbd8-c766-11e1-8775-005056c00008` | N‑2 loss of two tie-lines | `9d17b84c-33b5-4a68-b8b9-ed5b31038d40`, `13334fdf-9cc2-4341-adb6-1281269040b4` |



### Expected outcome

- Contingencies are correctly resolved against the CGMES network model
- Execution does not permanently modify the base network state 
- Updates to contingencies are preserved in the exported CO dataset
- Exported data remains compliant with the CGMES Contingency Profile
