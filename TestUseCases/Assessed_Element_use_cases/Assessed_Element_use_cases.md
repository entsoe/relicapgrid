# Assessed Elements – Use Cases

This section documents the modeling and processing of **Assessed Elements (AE)** using examples from the **ReliCapGrid Belgovia datasets**.

---

## 1 Secured Assessed Element

### Description
This use case illustrates how to define a **Secured Assessed Element**.  
The example is indicative and may not cover all regional specificities.

### Dataset Reference
- **File:** `Belgovia_AE.xml`
- **AssessedElement rdf:ID:** `_992c2de6-e206-45b3-a76a-f4a691e8839a`

### Validation Steps

#### Step 1: Dataset Import
1. Load the **Assessed Element dataset** (`Belgovia_AE.xml`).
2. Identify the AssessedElement object.

#### Step 2: Base Case Configuration
1. Verify that:
   - `AssessedElement.inBaseCase = true`
2. Confirm that the element is included in the base‑case assessment.

#### Step 3: Secured for region configuration
1. Verify that:
   - there is a reference to `nc:AssessedElement.SecuredForRegion` to the region with ID: `56d81c91-4fb8-47a2-9d7c-baa13dedd605`
2. Confirm that the element is assigned to be secured for the region's assessment.

### Expected Outcome
- The assessed element is evaluated in the base case.
- The element is treated as secured for the relevant region.

---

## 2 Scanned Assessed Element

### Description
This use case illustrates how to define a **Scanned Assessed Element** which is secured in another region.

### Dataset Reference
- **File:** `Belgovia_AE.xml`
- **AssessedElement rdf:ID:** `_1eb2eb03-dda6-4e59-b7c8-a2edb117d676`

### Validation Steps

#### Step 1: Dataset Import
1. Load the Assessed Element dataset.
2. Identify the scanned AssessedElement object.

#### Step 2: Attribute Verification
1. Verify that:
   - `AssessedElement.inBaseCase = false`
2. Check that:
   - `ScannedForRegion` is set.
   - `SecuredForRegion` is set.

Note:for _d463cbba-c89c-4199-bbb9-1a33d90cae2c can be checked that:
   - `ScannedForRegion` is set.
   - `SecuredForRegion` is not set.

#### Step 3: Exclusion Reason
1. Verify that `exclusionReason` is defined.

### Expected Outcome
- The element is scanned (monitored) but not secured in the given region.

---

## 3 Disable an Assessed Element

### Description
This use case illustrates how to **temporarily disable** an Assessed Element using SIS or SSI.

### Dataset References
- **Assessed Element:** `Belgovia_AE.xml`
- **SIS Dataset:** `Belgovia_SIS.xml`

**Objects**
- `AssessedElementSchedule` rdf:ID `_7221ae31-f736-4ae2-8ce1-f3dd605cefd6`
- `AssessedElementTimePoint` rdf:ID `_a26e3ae0-0a7d-4f42-ad64-e9105ec3cd41`

### Validation Steps

#### Step 1: Structural Data
1. Load the Assessed Element dataset.
2. Identify the secured AssessedElement.

#### Step 2: Schedule Import
1. Load the SIS dataset.
2. Verify the AssessedElementSchedule object.

#### Step 3: Time‑Based Disabling
1. Check the AssessedElementTimePoint.
2. Confirm that the element is disabled for the specified time periods.

### Expected Outcome
- The Assessed Element is temporarily disabled for defined time intervals.

---

## 4 Exclude an Assessed Element

### Description
This use case illustrates how to **exclude** an Assessed Element from RAO optimization, while still allowing security analysis.

### Dataset Reference
- **File:** `Belgovia_AE.xml`
- **AssessedElement rdf:ID:** `_1eb2eb03-dda6-4e59-b7c8-a2edb117d676`

### Validation Steps

#### Step 1: Dataset Import
1. Load the Assessed Element dataset.
2. Identify the element to be excluded.

#### Step 2: Exclusion Configuration
1. Verify exclusion via:
   - `ScannedForRegion`

### Expected Outcome
- The element is excluded from RAO optimization.
- Security analysis calculations can still reference it.

---

## 5 Assessed Element with Contingency

### Description
This section describes how to model combinations of **Assessed Elements and Contingencies**.

### General Validation Rules
- `isCombinableWithContingency = true`
  - AE is assessed for all contingencies unless exclusions are defined.
- `isCombinableWithContingency = false`
  - Only explicitly included combinations are assessed.

---

### 5.1 Scenario 1 – Full Scope

**Dataset**
- `AssessedElement` rdf:ID `_d17943b5-9d10-4f8b-bb07-18c3a3822348`

#### Steps
1. Load the AE dataset.
2. Verify:
   - `inBaseCase = true`
   - `isCombinableWithContingency = true`

**Outcome**
- AE is assessed against all contingencies.

---

### 5.2 Scenario 2 – Limited Exclusion

**Dataset**
- `AssessedElement` rdf:ID `_992c2de6-e206-45b3-a76a-f4a691e8839a`
- `AssessedElementWithContingency` rdf:ID `_1f38d403-a822-4c24-93c0-0f18ac699ef1`

#### Steps
1. Load AE and CO datasets.
2. Verify that the AE‑CO combination is marked as excluded.

**Outcome**
- Specific contingency is excluded from assessment.

---

### 5.3 Scenario 3 – Limited Inclusion

**Dataset**
- `AssessedElement` rdf:ID `_663c6c3c-1777-4eb7-98b0-c23233ce0f71`
- `AssessedElementWithContingency` rdf:ID `_deb4c65f-c3fc-414e-baa3-692829e3eec2`

#### Steps
1. Verify:
   - `isCombinableWithContingency = false`
2. Check explicitly included AE‑CO pairs.

**Outcome**
- AE is assessed only for explicitly defined contingencies.

---

## 6 Assessed Element with Remedial Action

### Description
This use case illustrates linking **Assessed Elements with Remedial Actions**.

### Dataset References
- `AssessedElement` rdf:ID `_13d17257-977e-43bc-971a-25022282688a`
- `AssessedElementWithRemedialAction` rdf:ID `_66f786ce-5e2a-427d-9eb8-4e1462045c27`
- `GridStateAlterationRemedialAction` rdf:ID `_70b696ac-c38f-4528-8d65-ba707c0b72e1`

### Validation Steps

1. Load AE and RA datasets.
2. Verify the AE‑RA association.
3. Check inclusion, exclusion, or consideration logic.

### Expected Outcome
- RAO considers only allowed remedial actions for the assessed element.

---
``