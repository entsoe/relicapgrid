## Use Case: Boundary Dataset 

---

### Definition 
Boundary data represents power system elements that are considered common border objects between adjacent modelling authorities. 
These elements are jointly governed by the involved parties to ensure that adjacent network models can be consistently assembled. 
A boundary dataset may contain one or more modelling objects, agreed upon by the primary stakeholders, that define the shared model scope.

---
### Scope
- Import Boundary dataset (BDS)
- Checking the consitency 

---

### Main Flow


#### Step 1: Boundary Import
1. Receiving TSO loads Boundary dataset.
2. Merge Boundary with IGM.
3. Verify connectivity consistency.

#### Step 2: Consistency Check
1. Check matching nodes and terminals.
2. Verify no duplication or mismatch.
3. Ensure full interconnection topology.

---

### Expected Outcome
- Interconnection between TSOs is correctly represented
- No topology gaps at borders

## Use Case: Common Data Dataset 

---

### Definition 
Common data refers to structured data that is shared and jointly governed by all participants within a specific CGMES exchange context or process. 
All relevant objects in common data shall be governed by a common change process where the object is defined once, with unique identifiers and agreed attribute values, to ensure consistency and prevent duplication.

---

### Scope
- Common Data (CD)
- Shared definitions across TSOs 


---


### Main Flow


#### Step 1: Common Data Import
1. Load Common Data dataset.


#### Step 2: Consistency Check
1. Verify: BiddingZone; BiddingZoneBorder; CapacityCalculationRegion; CapacityCalculationCalculator; Organisation; TransmissionSystemOperator; SecurityCoordinator; LoadFrequencyControlArea; SynchronousArea; SchedulingArea; LoadFrequencyControlBlock; TieCorridor.

---

### Expected Outcome
- No ambiguity in time, process, or identifiers
- Interoperability between TSOs and tools


## Use Case: Reference Data  

---

### Definition 
Reference data refers to relatively static, shared information that defines standardised, reusable concepts applied across multiple processes and model exchanges.


---


### Scope
- Reference Data (RD)

---

### Main Flow


#### Step 1: Reference Data Import
1. Load Reference Data dataset.

#### Step 2: Consistency Check
1. Verify consistency with other instace files.

---

### Expected Outcome
- Consistent use of reference datasets