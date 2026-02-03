# DRIMS Multi-Agency Coordination

This document describes the coordination features in DRIMS for managing multi-agency disaster response operations.

## OCHA/IASC Humanitarian Clusters

DRIMS implements the standard humanitarian cluster system defined by the UN Office for the Coordination of Humanitarian
Affairs (OCHA) and the Inter-Agency Standing Committee (IASC).

### What are Clusters?

When a major disaster occurs, humanitarian response is organized into **sector-based clusters**, each led by a
designated UN agency. This prevents duplication, identifies gaps, and ensures coordinated response.

### Cluster Reference

| Code                | Cluster                        | Lead Agency                | Focus Area                                                      |
| ------------------- | ------------------------------ | -------------------------- | --------------------------------------------------------------- |
| `food_security`     | Food Security                  | WFP / FAO                  | Food distribution, agricultural inputs, livelihood support      |
| `health`            | Health                         | WHO                        | Medical services, disease surveillance, health facility support |
| `nutrition`         | Nutrition                      | UNICEF                     | Treatment of malnutrition, supplementary feeding, infant care   |
| `wash`              | WASH                           | UNICEF                     | Water supply, sanitation facilities, hygiene promotion          |
| `shelter`           | Shelter                        | UNHCR / IFRC               | Emergency shelter, non-food items, housing reconstruction       |
| `protection`        | Protection                     | UNHCR                      | Safety, human rights, GBV prevention, child protection          |
| `education`         | Education                      | UNICEF / Save the Children | Learning continuity, temporary schools, supplies                |
| `early_recovery`    | Early Recovery                 | UNDP                       | Livelihoods restoration, debris removal, infrastructure         |
| `logistics`         | Logistics                      | WFP                        | Supply chain, warehousing, transport coordination               |
| `emergency_telecom` | Emergency Telecommunications   | WFP                        | Communications infrastructure, connectivity                     |
| `camp_coordination` | Camp Coordination & Management | UNHCR / IOM                | Displaced persons camps, site management                        |

### Usage in DRIMS

#### Requests

Each relief request can be tagged with a cluster to indicate which humanitarian sector it serves:

```
Request: REQ-2025-0042
Cluster: WASH
Items: Water purification tablets (5000), Jerry cans (200)
```

This enables:

- Filtering requests by sector
- Reporting to cluster leads
- Identifying sector-specific gaps

#### Personnel

Deployed personnel can be assigned to clusters:

```
Personnel: Dilani Perera
Role: Field Coordinator
Cluster: Health
Incident: 2025 Southwest Monsoon Floods
```

#### 4W Reporting

The 4W Report ("Who does What, Where, When") is a standard humanitarian reporting format. DRIMS generates 4W reports
that include cluster assignments for coordination meetings.

### Technical Implementation

**Vocabulary**: `urn:ocha:iasc:clusters`

Located in `spp_drims/data/vocabulary_codes.xml`, the clusters are defined as vocabulary codes that can be referenced
across the system.

**Fields**:

- `spp.drims.request.cluster_id` - Request's humanitarian cluster
- `spp.drims.personnel.cluster_id` - Personnel's cluster assignment

---

## Coordination Modes

DRIMS supports different coordination models for multi-agency response:

| Code          | Mode           | Description                                                 |
| ------------- | -------------- | ----------------------------------------------------------- |
| `lead_agency` | Lead Agency    | Single agency (usually government) coordinates all partners |
| `cluster`     | Cluster System | UN-led sector coordination with designated cluster leads    |
| `consortium`  | Consortium     | NGO-led coordination among partner organizations            |
| `bilateral`   | Bilateral      | Direct government-to-government or agency-to-agency         |

Each incident can be assigned a coordination mode to indicate how the response is being managed.

**Field**: `spp.hazard.incident.coordination_mode_id`

---

## Organization Roles

Partners can be assigned roles in disaster response:

| Code           | Role                 | Description                        |
| -------------- | -------------------- | ---------------------------------- |
| `lead`         | Lead Agency          | Primary coordinating organization  |
| `co_lead`      | Co-Lead              | Shares coordination responsibility |
| `implementing` | Implementing Partner | Delivers services on the ground    |
| `funding`      | Funding Partner      | Provides financial resources       |
| `technical`    | Technical Partner    | Provides expertise and guidance    |

**Field**: `res.partner.drims_organization_role_id`

---

## References

- [OCHA Cluster Coordination](https://www.humanitarianresponse.info/en/coordination/clusters)
- [IASC Reference Module](https://interagencystandingcommittee.org/iasc-transformative-agenda/iasc-reference-module-cluster-coordination-country-level-revised-july-2015)
- [4W Reporting Guidelines](https://www.humanitarianresponse.info/en/applications/tools/category/4w-who-does-what-where-when)
