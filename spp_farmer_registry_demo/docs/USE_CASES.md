# OpenSPP Farmer Registry Demo - Use Cases Guide

This document describes the demo use cases for the `spp_farmer_registry_demo` module.
The demo is set in the **Philippines** context, showcasing farmer registry and
agricultural subsidy programs for smallholder farmers.

## Table of Contents

1. [Overview](#overview)
2. [Philippines Context](#philippines-context)
3. [Demo Programs](#demo-programs)
4. [Demo Stories](#demo-stories)
5. [Logic Packs](#logic-packs)
6. [Use Cases by Audience](#use-cases-by-audience)
7. [Demo Scenarios](#demo-scenarios)
8. [Feature Demonstrations](#feature-demonstrations)

---

## Overview

The Farmer Registry Demo module provides realistic demo data that showcases OpenSPP's
capabilities for agricultural program management. It follows the "Fixed Stories +
Volume" architecture:

- **Fixed Stories**: 8 named farmer personas with predefined farm profiles and program
  journeys
- **GIS Data**: GPS coordinates and land parcel polygons across 8 Philippine provinces
- **Farm Cooperatives**: 2 cooperative personas demonstrating group hierarchy (group of
  groups)
- **Edge Cases**: 3 additional personas for testing eligibility boundaries
- **Volume Data**: Random farm registrations with GIS coordinates for realistic map
  views
- **Demo Programs**: 5 programs covering different agricultural subsidy scenarios
- **Logic Packs**: Pre-built CEL eligibility and benefit calculation rules

---

## Philippines Context

The demo simulates a **Department of Agriculture (DA)** farmer support initiative in the
Philippines, targeting smallholder farmers across multiple provinces.

### Setting

| Attribute             | Value                                                    |
| --------------------- | -------------------------------------------------------- |
| **Country**           | Philippines                                              |
| **Agency**            | Department of Agriculture (DA)                           |
| **Target Population** | Smallholder farmers (≤5 hectares)                        |
| **Registry System**   | Registry System for Basic Sectors in Agriculture (RSBSA) |
| **Currency**          | Philippine Peso (PHP)                                    |

### Agricultural Context

- **Major crops**: Rice (palay), corn, coconut, sugarcane, vegetables
- **Livestock**: Carabao (water buffalo), goats, chickens, swine
- **Aquaculture**: Tilapia, milkfish (bangus), shrimp
- **Farm sizes**: Typically 0.5-5 hectares for smallholders
- **Seasons**: Wet season (June-November), Dry season (December-May)

### Regions Represented

| Persona            | Province      | Region                       |
| ------------------ | ------------- | ---------------------------- |
| Maria Santos       | Nueva Ecija   | Central Luzon (Region III)   |
| Juan Dela Cruz     | Pangasinan    | Ilocos Region (Region I)     |
| Rosa Garcia        | Bukidnon      | Northern Mindanao (Region X) |
| Amir Mangudadatu   | Maguindanao   | BARMM                        |
| Sofia Martinez     | Laguna        | CALABARZON (Region IV-A)     |
| Ramon dela Cruz    | Pampanga      | Central Luzon (Region III)   |
| Sittie Pangandaman | Lanao del Sur | BARMM                        |
| Danilo Villanueva  | Davao del Sur | Davao Region (Region XI)     |

---

## Demo Programs

### 1. Input Subsidy Program

| Attribute           | Value                                                            |
| ------------------- | ---------------------------------------------------------------- |
| **Target Type**     | Households (Groups)                                              |
| **Eligibility**     | Smallholder (≤5 ha) with productive land                         |
| **Benefit Formula** | Base amount + (farm hectares x per-hectare rate)                 |
| **Example**         | PHP 5,000 + (2.0 ha x PHP 2,500) = PHP 10,000                    |
| **Stories**         | Maria Santos, Juan Dela Cruz, Sofia Martinez, Sittie Pangandaman |

**Use Cases:**

- Rice and corn seed subsidy distribution
- Fertilizer assistance for smallholders
- Seasonal input support (wet/dry season)
- Per-hectare scaling of benefits

**Features Demonstrated:**

- CEL-based eligibility evaluation
- Formula-based benefit calculation
- Group-based targeting
- Farm size-proportional entitlements

---

### 2. Equipment Grant Program

| Attribute       | Value                                        |
| --------------- | -------------------------------------------- |
| **Target Type** | Households (Groups)                          |
| **Eligibility** | Smallholder with 2+ years farming experience |
| **Benefit**     | Fixed grant amount                           |
| **Stories**     | Juan Dela Cruz, Sittie Pangandaman           |

**Use Cases:**

- Farm mechanization support (hand tractors, threshers)
- Post-harvest equipment grants
- Experience-based eligibility filtering
- One-time asset distribution

**Features Demonstrated:**

- Multi-criteria eligibility (size AND experience)
- Fixed-amount entitlements
- Edge case: new farmers excluded (experience < 2 years)

---

### 3. Livestock Support Program

| Attribute           | Value                                           |
| ------------------- | ----------------------------------------------- |
| **Target Type**     | Households (Groups)                             |
| **Eligibility**     | Farms with livestock activities                 |
| **Benefit Formula** | Base amount + (livestock count x per-head rate) |
| **Example**         | PHP 3,750 + (20 heads x PHP 500) = PHP 13,750   |
| **Stories**         | Rosa Garcia, Juan Dela Cruz, Danilo Villanueva  |

**Use Cases:**

- Livestock dispersal programs (carabao, goat)
- Animal health and veterinary support
- Per-head benefit scaling
- Mixed farm support

**Features Demonstrated:**

- Activity-based eligibility (livestock count > 0)
- Per-head benefit calculation
- Cross-activity farms (crops + livestock)

---

### 4. Climate Resilience Program

| Attribute       | Value                             |
| --------------- | --------------------------------- |
| **Target Type** | Households (Groups)               |
| **Eligibility** | Smallholder with idle/fallow land |
| **Benefit**     | Fixed climate adaptation amount   |
| **Stories**     | Amir Mangudadatu                  |

**Use Cases:**

- Drought-affected farmer support
- Climate adaptation assistance
- Fallow land rehabilitation
- Emergency agricultural response

**Features Demonstrated:**

- Climate vulnerability targeting
- Idle land as eligibility indicator
- Fixed emergency-style benefits
- BARMM conflict/climate overlap scenarios

---

### 5. Aquaculture Support Program

| Attribute       | Value                             |
| --------------- | --------------------------------- |
| **Target Type** | Households (Groups)               |
| **Eligibility** | Farms with aquaculture activities |
| **Benefit**     | Fixed aquaculture support amount  |
| **Stories**     | Ramon dela Cruz                   |

**Use Cases:**

- Fishpond development support
- Fingerling and feed subsidy
- Aquaculture-specific targeting
- Non-crop farming support

**Features Demonstrated:**

- Aquaculture activity detection
- Farm type differentiation
- Support for non-traditional farming

---

## Demo Stories

### Maria Santos - The Rice Farmer

**Profile:**

- 42-year-old female rice farmer
- 2 hectares in Nueva Ecija (rice granary of the Philippines)
- 10 years farming experience
- Smallholder, all land under crops

**Farm Data:**

| Attribute   | Value        |
| ----------- | ------------ |
| Farm Type   | Crop         |
| Total Size  | 2.0 ha       |
| Under Crops | 2.0 ha       |
| Crops       | Rice (palay) |
| Livestock   | None         |

**Program Eligibility:**

- Input Subsidy: Eligible (smallholder + productive land)
- Equipment Grant: Eligible (10 years experience)
- Livestock Support: Not eligible (no livestock)

**Demo Points:**

- Typical Filipino rice farmer profile
- Female farmer representation
- Multi-program eligibility
- Productive smallholder success story

---

### Juan Dela Cruz - The Mixed Farmer

**Profile:**

- 45-year-old male mixed farmer
- 3 hectares in Pangasinan
- 15 years experience, crops + chickens
- Experienced and diversified

**Farm Data:**

| Attribute       | Value                  |
| --------------- | ---------------------- |
| Farm Type       | Mixed                  |
| Total Size      | 3.0 ha                 |
| Under Crops     | 2.0 ha                 |
| Under Livestock | 1.0 ha                 |
| Crops           | Rice, corn, vegetables |
| Livestock       | 50 chickens            |

**Program Eligibility:**

- Input Subsidy: Eligible
- Equipment Grant: Eligible (15 years)
- Livestock Support: Eligible (50 heads)

**Demo Points:**

- Diversified farm operations
- Eligible for multiple programs simultaneously
- Highest combined benefit potential
- Demonstrates cross-program coordination

---

### Rosa Garcia - The Livestock Farmer

**Profile:**

- 67-year-old female farmer
- 1 hectare in Bukidnon, Mindanao
- 8 years experience, goat farming
- Female-headed household

**Farm Data:**

| Attribute       | Value      |
| --------------- | ---------- |
| Farm Type       | Mixed      |
| Total Size      | 1.0 ha     |
| Under Crops     | 0.5 ha     |
| Under Livestock | 0.5 ha     |
| Crops           | Vegetables |
| Livestock       | 20 goats   |

**Program Eligibility:**

- Input Subsidy: Eligible
- Equipment Grant: Eligible (8 years)
- Livestock Support: Eligible (20 heads)

**Demo Points:**

- Senior female farmer
- Livestock-focused livelihood
- Small but productive farm
- Multi-program beneficiary

---

### Amir Mangudadatu - The Climate-Affected Farmer

**Profile:**

- 50-year-old male crop farmer
- 4 hectares in Maguindanao (BARMM)
- 20 years experience, drought-affected
- 1 hectare idle/fallow land

**Farm Data:**

| Attribute   | Value  |
| ----------- | ------ |
| Farm Type   | Crop   |
| Total Size  | 4.0 ha |
| Under Crops | 3.0 ha |
| Idle/Fallow | 1.0 ha |
| Crops       | Rice   |
| Livestock   | None   |

**Program Eligibility:**

- Input Subsidy: Eligible
- Equipment Grant: Eligible (20 years)
- Climate Resilience: Eligible (idle land > 0)

**Demo Points:**

- Climate vulnerability scenario
- BARMM conflict-affected context
- Idle land as climate impact indicator
- Emergency program targeting

---

### Sofia Martinez - The Organic Transition Farmer

**Profile:**

- 42-year-old female farmer
- 2 hectares in Laguna (CALABARZON)
- 5 years experience, transitioning to organic
- Growing vegetables and maize

**Farm Data:**

| Attribute   | Value             |
| ----------- | ----------------- |
| Farm Type   | Crop              |
| Total Size  | 2.0 ha            |
| Under Crops | 2.0 ha            |
| Crops       | Vegetables, maize |
| Livestock   | None              |

**Program Eligibility:**

- Input Subsidy: Eligible
- Equipment Grant: Eligible (5 years)
- Livestock Support: Not eligible

**Demo Points:**

- Organic farming transition
- Near-urban agriculture (Laguna)
- Young female farmer
- Crop diversification

---

### Ramon dela Cruz - The Aquaculture Farmer

**Profile:**

- 35-year-old male aquaculture farmer
- 0.5 hectare fishpond in Pampanga
- 7 years experience, tilapia farming
- Leased land

**Farm Data:**

| Attribute         | Value                |
| ----------------- | -------------------- |
| Farm Type         | Aquaculture          |
| Total Size        | 0.5 ha               |
| Under Aquaculture | 0.5 ha               |
| Aquaculture       | 1 fishpond (tilapia) |
| Crops             | None                 |

**Program Eligibility:**

- Aquaculture Support: Eligible
- Input Subsidy: Not eligible (no crops)
- Livestock Support: Not eligible

**Demo Points:**

- Non-crop farming representation
- Aquaculture-specific programs
- Small-scale fishpond operations
- Central Luzon aquaculture belt

---

### Sittie Pangandaman - The Experienced Female Farmer

**Profile:**

- 32-year-old female farmer
- 1.5 hectares in Lanao del Sur (BARMM)
- 12 years experience
- Female-headed household

**Farm Data:**

| Attribute   | Value            |
| ----------- | ---------------- |
| Farm Type   | Crop             |
| Total Size  | 1.5 ha           |
| Under Crops | 1.5 ha           |
| Crops       | Rice, vegetables |
| Livestock   | None             |

**Program Eligibility:**

- Input Subsidy: Eligible
- Equipment Grant: Eligible (12 years)
- Livestock Support: Not eligible

**Demo Points:**

- Young but experienced farmer
- BARMM women in agriculture
- Multiple crop types
- Female farmer empowerment

---

### Danilo Villanueva - The Commercial-Edge Farmer

**Profile:**

- 38-year-old male mixed farmer
- 5 hectares in Davao del Sur (at smallholder threshold)
- 25 years experience, cattle and goats
- Edge case for program eligibility

**Farm Data:**

| Attribute       | Value                     |
| --------------- | ------------------------- |
| Farm Type       | Mixed                     |
| Total Size      | 5.0 ha                    |
| Under Crops     | 3.0 ha                    |
| Under Livestock | 2.0 ha                    |
| Crops           | Coconut, cacao            |
| Livestock       | 45 heads (cattle + goats) |

**Program Eligibility:**

- Input Subsidy: Eligible (at 5 ha threshold)
- Equipment Grant: Eligible (25 years)
- Livestock Support: Eligible (45 heads)

**Demo Points:**

- Threshold/edge case testing
- Large smallholder at boundary
- Highly diversified farm
- Davao agricultural economy

---

## Farm Cooperative Personas (Group Hierarchy)

Farm Cooperatives demonstrate the **group hierarchy** feature where a cooperative
(group) contains individual farms (groups) as members — a group of groups.

### Nueva Ecija Rice Cooperative

**Profile:**

- Rice farming cooperative in Nueva Ecija, Central Luzon
- Contains 2 member farms: Maria Santos + Sofia Martinez
- Combined area: 4.0 hectares
- All members are rice/crop farmers

**Hierarchy:**

```
Nueva Ecija Rice Cooperative (Group)
├── Maria Santos Farm (Group) ─── 2.0 ha rice
└── Sofia Martinez Farm (Group) ── 2.0 ha vegetables, maize
```

**Demo Points:**

- Group of groups hierarchy
- Cooperative-level aggregated data (combined hectares, member count)
- Cooperative registration and management
- Member farm listing within cooperative view

---

### BARMM Farmers Federation

**Profile:**

- Federation of farms in Bangsamoro Autonomous Region (BARMM)
- Contains 2 member farms: Amir Mangudadatu + Sittie Pangandaman
- Combined area: 5.5 hectares (including 1 ha idle)
- Mixed crop types across members

**Hierarchy:**

```
BARMM Farmers Federation (Group)
├── Amir Mangudadatu Farm (Group) ──── 4.0 ha (3.0 crops + 1.0 idle)
└── Sittie Pangandaman Farm (Group) ── 1.5 ha crops
```

**Demo Points:**

- Regional farmer federation
- BARMM-specific cooperative structures
- Federation exceeds smallholder threshold (5.5 ha combined) even though individual
  members qualify
- Climate-affected member (Ibrahim) within a broader federation

---

## Edge Case Personas

### AgriCorp Holdings - Large Commercial Farm

| Attribute       | Value                                  |
| --------------- | -------------------------------------- |
| Farm Size       | 50 ha                                  |
| Is Smallholder  | No                                     |
| Expected Result | Rejected from all smallholder programs |

**Demo Point:** Demonstrates proper targeting exclusion for large commercial operations.

---

### Idle Land Farm - No Productive Land

| Attribute           | Value                                                        |
| ------------------- | ------------------------------------------------------------ |
| Farm Size           | 3 ha (all idle/fallow)                                       |
| Has Productive Land | No                                                           |
| Expected Result     | Rejected from Input Subsidy, eligible for Climate Resilience |

**Demo Point:** Tests edge case where land exists but isn't productive.

---

### New Farmer - No Experience

| Attribute       | Value                                                     |
| --------------- | --------------------------------------------------------- |
| Farm Size       | 2 ha                                                      |
| Experience      | 1 year                                                    |
| Expected Result | Eligible for Input Subsidy, rejected from Equipment Grant |

**Demo Point:** Tests experience-based eligibility threshold.

---

## Logic Packs

Pre-built logic packages using CEL expressions for program eligibility and benefit
calculations.

### Pack 1: Input Subsidy Program

| Item                      | Type    | CEL Expression                                                    |
| ------------------------- | ------- | ----------------------------------------------------------------- |
| Smallholder Eligibility   | Filter  | `is_smallholder && has_productive_land`                           |
| Input Subsidy Calculation | Formula | `input_subsidy_base + (farm_size_hectares * per_hectare_subsidy)` |

### Pack 2: Equipment Grant Program

| Item                           | Type    | CEL Expression                            |
| ------------------------------ | ------- | ----------------------------------------- |
| Experienced Farmer Eligibility | Filter  | `is_smallholder && experience_years >= 2` |
| Equipment Grant Amount         | Formula | `equipment_grant_amount`                  |

### Pack 3: Livestock Support Program

| Item                          | Type    | CEL Expression                                         |
| ----------------------------- | ------- | ------------------------------------------------------ |
| Livestock Farmer Eligibility  | Filter  | `livestock_count > 0`                                  |
| Livestock Support Calculation | Formula | `livestock_base + (livestock_count * per_head_amount)` |

### Pack 4: Climate Resilience Program

| Item                              | Type    | CEL Expression                         |
| --------------------------------- | ------- | -------------------------------------- |
| Climate Vulnerability Eligibility | Filter  | `is_smallholder && farm_size_idle > 0` |
| Climate Adaptation Amount         | Formula | `climate_adaptation_amount`            |

### Pack 5: Aquaculture Support Program

| Item                           | Type    | CEL Expression               |
| ------------------------------ | ------- | ---------------------------- |
| Aquaculture Farmer Eligibility | Filter  | `aquaculture_count > 0`      |
| Aquaculture Support Amount     | Formula | `aquaculture_support_amount` |

---

## Use Cases by Audience

### For Sales Demos

**Quick Demo (15 minutes):**

1. Show farmer registry dashboard with farm statistics
2. Navigate to Maria Santos - show farm profile and eligibility
3. Show Juan Dela Cruz - demonstrate multi-program eligibility
4. Highlight aquaculture support (Ramon dela Cruz) for non-crop farming

**Comprehensive Demo (45 minutes):**

1. Farm registration workflow
2. Farm details and activity management
3. Agricultural season setup
4. Program eligibility evaluation using Logic Packs
5. Benefit calculation demonstration
6. Change request for farm data updates
7. Dashboard and reporting

### For Training

**Registry Officer Training:**

- Use all 8 personas to explain farm registration
- Demonstrate farm details entry (classification, acreage, experience)
- Practice adding farm activities (crops, livestock, aquaculture)
- Create agricultural seasons

**Program Officer Training:**

- Use Logic Packs to explain eligibility rules
- Walk through benefit calculations with concrete examples
- Demonstrate edge cases (large farm rejection, new farmer exclusion)
- Practice multi-program enrollment

**Change Request Training:**

- Submit farm detail updates via change request
- Add new farm activities through CR workflow
- Practice approval/rejection workflows

### For Testing

**Eligibility Testing:**

- 8 eligible personas with known expected results
- 3 edge case personas for boundary testing
- Each Logic Pack has clear input/output expectations

**Regression Testing:**

- Fixed personas ensure consistent test data
- CEL expressions can be validated against expected outcomes
- Farm data provides diverse test scenarios

---

## Demo Scenarios

### Scenario 1: Farm Registration and Program Enrollment

**Objective:** Show end-to-end farmer registration to program enrollment

**Steps:**

1. Open farmer registry list view
2. Create new farm registration (or open Maria Santos)
3. Fill in farm details (type, size, classification)
4. Add farm activities (crops grown, livestock held)
5. Navigate to programs and check eligibility
6. Enroll in Input Subsidy Program
7. Show calculated benefit amount

**Key Messages:**

- Streamlined farm registration process
- Automatic eligibility determination
- Transparent benefit calculation

---

### Scenario 2: Multi-Program Eligibility

**Objective:** Demonstrate how one farmer can qualify for multiple programs

**Steps:**

1. Open Juan Dela Cruz profile
2. Show farm data: 3 ha mixed farm, 15 years experience, 50 chickens
3. Check Input Subsidy eligibility: smallholder + productive land = eligible
4. Check Equipment Grant eligibility: smallholder + 15 years = eligible
5. Check Livestock Support eligibility: 50 livestock heads = eligible
6. Show consolidated benefit summary

**Key Messages:**

- Holistic farmer support
- Multiple program coordination
- No duplicate registration needed

---

### Scenario 3: Eligibility Edge Cases

**Objective:** Show how the system correctly handles boundary conditions

**Steps:**

1. Open "New Farmer" persona (1 year experience)
2. Show Input Subsidy: eligible (smallholder + productive land)
3. Show Equipment Grant: rejected (experience < 2 years)
4. Open "AgriCorp Holdings" (50 ha)
5. Show all programs: rejected (not smallholder)
6. Open "Idle Land Farm" (all fallow)
7. Show Input Subsidy: rejected (no productive land)
8. Show Climate Resilience: eligible (idle land > 0)

**Key Messages:**

- Transparent and auditable eligibility rules
- Proper targeting prevents leakage
- Edge cases handled correctly

---

### Scenario 4: Agricultural Season Management

**Objective:** Demonstrate seasonal farm activity tracking

**Steps:**

1. Navigate to Seasons configuration
2. Create a new wet season (June-November)
3. Open a farm and add seasonal activities
4. Show activity types: planting, harvesting, inputs applied
5. Close season and review summary

**Key Messages:**

- Temporal tracking of farm activities
- Season-based program cycles
- Historical data for trend analysis

---

### Scenario 5: Farm Data Change Request

**Objective:** Show the change request workflow for farm updates

**Steps:**

1. Open a farmer profile
2. Submit a change request to update farm size
3. Show the CR workflow (draft → pending → validated → applied)
4. Verify updated farm details after approval
5. Show audit trail of the change

**Key Messages:**

- Data integrity through approval workflows
- Complete audit trail
- Controlled updates to farm records

---

### Scenario 6: Farm Cooperative (Group Hierarchy)

**Objective:** Demonstrate group of groups hierarchy for farmer cooperatives

**Steps:**

1. Open the Nueva Ecija Rice Cooperative profile
2. Show it is a group with `allow_all_member_type` enabled
3. Navigate to the Members tab — show member farms (Maria Santos, Sofia Martinez)
4. Click into Maria Santos farm — show it is itself a group with individual members
5. Return to cooperative level — show aggregated data (combined hectares)
6. Open BARMM Farmers Federation — show federation-level view
7. Demonstrate that the federation exceeds smallholder threshold (5.5 ha) while
   individual members qualify

**Key Messages:**

- Cooperatives are represented as groups containing farm groups
- Multi-level hierarchy: Cooperative → Farm → Individual members
- Aggregated statistics at cooperative level
- Individual farm eligibility preserved within cooperative structure

---

### Scenario 7: GIS Farm Mapping

**Objective:** Demonstrate geospatial visualization of farm locations and land parcels

**Steps:**

1. Navigate to the GIS Map view of the farmer registry
2. View all 8 story farms plotted on the Philippine map
3. Zoom into the Nueva Ecija cluster (Maria Santos + Sofia Martinez area)
4. Click a farm marker to see farm details (name, size, type)
5. View the land parcel polygon for Santos Farm (2 ha rice paddy)
6. Zoom out to see the geographic distribution across Luzon, Visayas, and Mindanao
7. Compare BARMM farms (Mangudadatu, Pangandaman) vs Luzon farms
8. Navigate to a farm's Land Records tab to view parcel boundaries and land use

**Key Messages:**

- Every farm has GPS coordinates and land parcel boundaries
- Map view for geographic planning and disaster response
- Land use classification on each parcel
- Spatial queries possible (e.g., "find all farms within 50km of a typhoon path")

**Geographic Coverage:**

| Persona            | Region            | Province      | Coordinates       |
| ------------------ | ----------------- | ------------- | ----------------- |
| Maria Santos       | Central Luzon     | Nueva Ecija   | 15.59°N, 120.97°E |
| Juan Dela Cruz     | Southern Luzon    | Laguna        | 14.27°N, 121.41°E |
| Rosa Garcia        | Southern Luzon    | Batangas      | 13.76°N, 121.06°E |
| Sofia Martinez     | Cordillera        | Benguet       | 16.40°N, 120.60°E |
| Ramon dela Cruz    | Ilocos            | Pangasinan    | 16.02°N, 120.22°E |
| Amir Mangudadatu   | BARMM             | Maguindanao   | 7.05°N, 124.85°E  |
| Sittie Pangandaman | BARMM             | Lanao del Sur | 7.90°N, 124.29°E  |
| Danilo Villanueva  | Northern Mindanao | Bukidnon      | 8.05°N, 125.05°E  |

---

## Feature Demonstrations

### Farm Registry Features

| Feature           | Demo Persona                 | Description                              |
| ----------------- | ---------------------------- | ---------------------------------------- |
| Crop farming      | Maria Santos                 | Pure rice farming profile                |
| Mixed farming     | Juan Dela Cruz               | Crops + livestock combination            |
| Aquaculture       | Ramon dela Cruz              | Fishpond operations                      |
| Female farmers    | Maria, Rosa, Sofia, Sittie   | Gender-disaggregated data                |
| Climate impact    | Amir Mangudadatu             | Idle/fallow land tracking                |
| Edge threshold    | Danilo Villanueva            | At 5 ha smallholder boundary             |
| Farm cooperative  | Nueva Ecija Rice Cooperative | Group of groups hierarchy                |
| Farmer federation | BARMM Farmers Federation     | Regional multi-farm federation           |
| GIS mapping       | All 8 personas               | GPS coordinates across 8 provinces       |
| Land parcels      | All 8 personas               | Land records with polygon boundaries     |
| Land use          | All 8 personas               | Cultivation, pasture, aquaculture, mixed |

### Program Features

| Feature           | Demo Program        | Demo Persona               |
| ----------------- | ------------------- | -------------------------- |
| CEL eligibility   | Input Subsidy       | All personas               |
| Formula benefits  | Input Subsidy       | Maria Santos (per-hectare) |
| Fixed benefits    | Equipment Grant     | Juan Dela Cruz             |
| Per-head scaling  | Livestock Support   | Rosa Garcia (20 goats)     |
| Activity-based    | Aquaculture Support | Ramon dela Cruz            |
| Climate targeting | Climate Resilience  | Amir Mangudadatu           |

### Change Request Features

| Feature              | CR Type          | Description                        |
| -------------------- | ---------------- | ---------------------------------- |
| Update farm details  | Farm Details CR  | Change farm size, classification   |
| Add farm activity    | Farm Activity CR | Add new crop or livestock activity |
| Update farm activity | Farm Activity CR | Modify existing activity details   |

---

## Appendix: Data Generation Order

For optimal demo setup:

1. **First:** Install `spp_farmer_registry_demo` module (installs all dependencies)
2. **Second:** Run the Farmer Demo Wizard to generate demo data
3. **Third:** Verify farm registrations and program enrollments

### Prerequisites

The following modules are auto-installed as dependencies:

- `spp_starter_farmer_registry` - Core farmer registry modules
- `spp_farmer_registry_cr` - Change request types for farm data
- `spp_demo` - Demo infrastructure
- `spp_studio` - Logic Studio for Logic Packs
- `spp_registry_group_hierarchy` - Group hierarchy support
