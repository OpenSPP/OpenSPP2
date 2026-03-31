# MIS Demo V2 — Use Cases V3

## Design Principles

- Every story earns its place — if it doesn't demonstrate something unique, remove it
- Every person justifies their eligibility — CEL expressions produce expected pass/fail
- No super families — max 2 group programs per household, natural pairings only
- No dormant households — every household is enrolled in at least one program
- Change requests follow life events, not random data
- Country-aware names — each story has Filipino, Togolese, and Sri Lankan equivalents

---

## Country Name Equivalents

Each household and individual has locale-specific names. The demo generator selects
names based on the configured locale (`fil_PH`, `fr_TG`, `si_LK`).

### Household Surnames

| Story ID  | Filipino  | Togolese | Sri Lankan     |
| --------- | --------- | -------- | -------------- |
| dela_cruz | Dela Cruz | Mensah   | Silva          |
| santos    | Santos    | Koffi    | Perera         |
| reyes     | Reyes     | Agbeko   | Fernando       |
| gutierrez | Gutierrez | Amouzou  | Jayawardena    |
| martinez  | Martinez  | Dosseh   | Wickramasinghe |

### Individual Names

| Story ID       | Filipino      | Togolese        | Sri Lankan        |
| -------------- | ------------- | --------------- | ----------------- |
| rosa_elder     | Rosa Garcia   | Afi Kpodo       | Kamala Rathnayake |
| lorna_rejected | Lorna Pascual | Akossiwa Amevor | Nimali Bandara    |

### Rejection Household Surnames

| Story ID          | Filipino | Togolese | Sri Lankan |
| ----------------- | -------- | -------- | ---------- |
| castillo_rejected | Castillo | Sodji    | De Mel     |
| navarro_rejected  | Navarro  | Ayivi    | Gunasekara |

**Note:** First names within households also follow cultural norms per locale. The
implementation defines full member name sets for each country.

---

## Programs (7)

### 1. Cash Transfer Program (Group)

| Field             | Value                                                                                                                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Target            | Household (Group)                                                                                                                                                                              |
| CEL (Eligibility) | `r.is_group == true and hh_total_income < poverty_line and hh_size >= 2`                                                                                                                       |
| CEL (Compliance)  | `per_capita_income < poverty_line`                                                                                                                                                             |
| Constants         | `poverty_line` = 5,000; `cash_transfer_amount` = 150                                                                                                                                           |
| Entitlement       | $150/month                                                                                                                                                                                     |
| Cycle             | 30 days                                                                                                                                                                                        |
| Logic Pack        | `cash_transfer_basic`                                                                                                                                                                          |
| Compliance Note   | Rechecks per-capita income each cycle. If household income improves above threshold, members are marked `non_compliant` for that cycle — no entitlement generated. Used as graduation trigger. |

### 2. Universal Child Grant (Group)

| Field       | Value                                        |
| ----------- | -------------------------------------------- |
| Target      | Household (Group)                            |
| CEL         | `r.is_group == true and child_count > 0`     |
| Constants   | `base_child_grant` = 50                      |
| Entitlement | `base_child_grant * child_count` ($50/child) |
| Cycle       | 30 days                                      |
| Logic Pack  | `child_benefit`                              |

### 3. Conditional Child Grant (Group)

| Field             | Value                                                                                                                                                                                       |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Target            | Household (Group)                                                                                                                                                                           |
| CEL (Eligibility) | `r.is_group == true and members.exists(m, age_years(m.birthdate) < 2)`                                                                                                                      |
| CEL (Compliance)  | `per_capita_income < income_threshold`                                                                                                                                                      |
| Constants         | `first_1000_days_grant` = 10; `income_threshold` = 2,000                                                                                                                                    |
| Entitlement       | $10/month                                                                                                                                                                                   |
| Cycle             | 30 days                                                                                                                                                                                     |
| Logic Pack        | `child_benefit`                                                                                                                                                                             |
| Compliance Note   | Income cap on child benefit. Households with a baby under 2 qualify, but per-capita income must stay below the threshold each cycle. Prevents high-income families from claiming the grant. |

### 4. Elderly Social Pension (Individual)

| Field       | Value                                                 |
| ----------- | ----------------------------------------------------- |
| Target      | Individual                                            |
| CEL         | `r.is_group == false and age >= retirement_age`       |
| Constants   | `retirement_age` = 65; `elderly_pension_amount` = 100 |
| Entitlement | $100/month                                            |
| Cycle       | 30 days                                               |
| Logic Pack  | `social_pension`                                      |

### 5. Emergency Relief Fund (Group)

| Field       | Value                                                                                          |
| ----------- | ---------------------------------------------------------------------------------------------- |
| Target      | Household (Group)                                                                              |
| CEL         | `r.is_group == true and (dependency_ratio >= 1.5 or (is_female_headed and elderly_count > 0))` |
| Entitlement | Tiered: $500 (score >= 90), $400 (score >= 80), $300 (score >= 70)                             |
| Cycle       | 15 days (fast-track)                                                                           |
| Logic Pack  | `vulnerability_assessment`                                                                     |

### 6. Disability Support Grant (Group)

| Field       | Value                                                             |
| ----------- | ----------------------------------------------------------------- |
| Target      | Household (Group)                                                 |
| CEL         | `r.is_group == true and has_disabled_member`                      |
| Constants   | `disability_grant_base` = 100; `disability_grant_per_member` = 75 |
| Entitlement | $100 base + $75 per disabled member                               |
| Cycle       | 30 days                                                           |
| Logic Pack  | `disability_assistance`                                           |

### 7. Food Assistance (Individual)

| Field       | Value                                          |
| ----------- | ---------------------------------------------- |
| Target      | Individual                                     |
| CEL         | `r.is_registrant == true and r.active == true` |
| Entitlement | In-kind (Food Basket)                          |
| Cycle       | 30 days                                        |
| Logic Pack  | None (simple inline CEL)                       |

---

## Household Stories (5)

Each household is named by its family name. Programs that target groups enroll the
household — not individual members. Max 2 group programs per household.

### Story 1: Dela Cruz — Payment Failure, Recovery, and Compliance Pass

**Purpose:** Cash Transfer with a payment failure, GRM resolution, and successful
reprocessing. Also demonstrates compliance passing — Dela Cruz remains compliant each
cycle, contrasting with Santos who fails compliance and graduates.

**Household (4 members):**

| Member          | Role   | Age | Gender |
| --------------- | ------ | --- | ------ |
| Juan Dela Cruz  | Head   | 38  | Male   |
| Ana Dela Cruz   | Spouse | 35  | Female |
| Paolo Dela Cruz | Child  | 12  | Male   |
| Maria Dela Cruz | Child  | 8   | Female |

**Household Program:**

| Program       | Why Eligible                                   | Compliance                                                | Status   |
| ------------- | ---------------------------------------------- | --------------------------------------------------------- | -------- |
| Cash Transfer | income 4,000 < poverty_line 5,000, size 4 >= 2 | **Passed** — per_capita_income 1,000 < poverty_line 5,000 | Enrolled |

**Journey:**

1. Enrolled 100 days ago
2. Payment #1 ($150) — paid
3. Payment #2 ($150) — **failed** (bank issue)
4. GRM ticket filed for payment failure → resolved
5. Payment #3 ($150) — paid (reprocessed)
6. Compliance check passes each cycle (per_capita_income 1,000 < poverty_line 5,000)

**Change Request:**

- `update_id` (approved) — Correct national ID number after data entry error

**GIS:** Southern region (Batangas) — coastal area

---

### Story 2: Santos — Graduation and Partial Exit

**Purpose:** Complete program lifecycle — enrollment, payments, compliance failure
triggering graduation from one program while remaining in another. Shows that exiting
one program doesn't affect other enrollments. Primary story for demonstrating the
compliance manager.

**Household (5 members):**

| Member         | Role           | Age | Gender |
| -------------- | -------------- | --- | ------ |
| Maria Santos   | Head           | 42  | Female |
| Ricardo Santos | Spouse         | 44  | Male   |
| Lola Santos    | Parent (elder) | 68  | Female |
| Sofia Santos   | Child          | 14  | Female |
| Miguel Santos  | Child          | 10  | Male   |

**Household Programs:**

| Program               | Why Eligible                      | Compliance                                                                    | Status                 |
| --------------------- | --------------------------------- | ----------------------------------------------------------------------------- | ---------------------- |
| Cash Transfer         | income 3,500 < 5,000, size 5 >= 2 | **Failed** — per_capita_income exceeded poverty_line after income improvement | **Exited** (graduated) |
| Universal Child Grant | child_count 2 > 0                 | N/A (no compliance on this program)                                           | Enrolled               |

**Journey:**

1. Enrolled in Cash Transfer 180 days ago (hh_total_income 3,500, per_capita 700)
2. Also enrolled in Universal Child Grant
3. 3 Cash Transfer payments of $150 (compliant — per_capita_income < poverty_line)
4. Income improved → **compliance check fails** in cycle 4
5. Marked `non_compliant` on cycle membership → no entitlement generated
6. Non-compliance triggers graduation review → exited from Cash Transfer 30 days ago
7. Still receiving Universal Child Grant (2 children x $50 = $100/month)

**Individual Dual Enrollment:**

| Member               | Program         | Why Eligible      |
| -------------------- | --------------- | ----------------- |
| Maria Santos (42, F) | Food Assistance | active registrant |

Maria receives monthly food baskets individually. Continues after household Cash
Transfer graduation.

**Change Requests:**

- `edit_individual` (approved) — Maria's phone/address update after moving
- `edit_individual` (pending x2) — Conflict detection: two overlapping CRs for Maria

**GIS:** Northern region (Nueva Ecija) — agricultural area

---

### Story 3: Reyes — Multi-Generational Household

**Purpose:** Demonstrates a large multi-generational household with three generations
living together — grandparents, parents, and children. Shows household composition
complexity and how multiple individuals within a household can qualify for different
individual-targeting programs (e.g., elderly members for pension).

**Household (8 members):**

| Member         | Role                    | Age | Gender |
| -------------- | ----------------------- | --- | ------ |
| Jose Reyes Sr  | Head                    | 72  | Male   |
| Carmen Reyes   | Spouse                  | 68  | Female |
| Miguel Reyes   | Adult (son)             | 45  | Male   |
| Teresa Reyes   | Adult (daughter-in-law) | 42  | Female |
| Jose Reyes Jr  | Child                   | 18  | Male   |
| Lucia Reyes    | Child                   | 14  | Female |
| Antonio Reyes  | Child                   | 10  | Male   |
| Isabella Reyes | Child                   | 6   | Female |

**Household Programs:**

Not enrolled in group programs via named stories. Volume-generated households with
similar composition are enrolled based on blueprint eligibility flags.

**Demo Points:**

- Multi-generational household structure (grandparents + parents + children)
- Elderly head (72) and spouse (68) — both individually eligible for Elderly Social
  Pension
- child_count = 3 (under 18: Lucia 14, Antonio 10, Isabella 6; Jose Jr 18 excluded)
- Large household (8 members) for household composition analysis

**GIS:** Northern region (Nueva Ecija) — agricultural area

---

### Story 4: Gutierrez — Emergency Relief and Transition

**Purpose:** Emergency response with fast-track enrollment, then transition to
longer-term Cash Transfer support after stabilization. Shows how displaced families move
through the system.

**Household (7 members):**

| Member             | Role   | Age | Gender |
| ------------------ | ------ | --- | ------ |
| Ramon Gutierrez    | Head   | 50  | Male   |
| Elena Gutierrez    | Spouse | 45  | Female |
| Marco Gutierrez    | Child  | 18  | Male   |
| Isabella Gutierrez | Child  | 15  | Female |
| Jose Gutierrez     | Child  | 12  | Male   |
| Sofia Gutierrez    | Child  | 9   | Female |
| Miguel Gutierrez   | Child  | 5   | Male   |

**Household Programs:**

| Program          | Why Eligible                                           | Status   |
| ---------------- | ------------------------------------------------------ | -------- |
| Emergency Relief | dependency_ratio 5/2 = 2.5, displaced                  | Enrolled |
| Cash Transfer    | income 2,000 < 5,000, size 7 >= 2 (post-stabilization) | Enrolled |

**Journey:**

1. Typhoon displaces family → emergency registration 60 days ago
2. Vulnerability assessment: very_high (displaced, lost assets, score 85)
3. Emergency Relief enrolled (fast-track 15-day cycles)
4. 2 emergency payments of $400 (Tier 2)
5. 30 days later: stabilized, enrolled in Cash Transfer for longer-term support
6. 1 Cash Transfer payment of $150

**Individual Dual Enrollment:**

| Member                  | Program         | Why Eligible      |
| ----------------------- | --------------- | ----------------- |
| Ramon Gutierrez (50, M) | Food Assistance | active registrant |

Ramon receives food baskets individually during the emergency period.

**Change Request:**

- `edit_individual` (approved) — Ramon's address update after relocation to temporary
  shelter

**GIS:** Conflict-affected region (Mindanao) — displacement zone

---

### Story 5: Martinez — Disability Support

**Purpose:** Disability-focused support with per-member benefit calculation.
Demonstrates disability assessment and the pending reassessment workflow.

**Household (3 members):**

| Member          | Role   | Age | Gender | Notes                     |
| --------------- | ------ | --- | ------ | ------------------------- |
| David Martinez  | Head   | 48  | Male   |                           |
| Sofia Martinez  | Spouse | 45  | Female |                           |
| Miguel Martinez | Child  | 12  | Male   | Disabled (cerebral palsy) |

**Household Program:**

| Program            | Why Eligible                                   | Status   |
| ------------------ | ---------------------------------------------- | -------- |
| Disability Support | has_disabled_member = true, disabled_count = 1 | Enrolled |

**Journey:**

1. Enrolled 100 days ago
2. Disability assessment completed for Miguel
3. 3 monthly payments of $175 each (base $100 + 1 disabled member x $75)

**Change Request:**

- `edit_individual` (pending) — Disability reassessment for Miguel (updated medical
  documentation)

**GIS:** Urban (Metro Manila vicinity)

---

## Individual Stories

Individuals enrolled directly in individual-targeting programs. Some are also heads of
households listed above (dual enrollment).

### Rosa Garcia — Elder Living Alone

**Purpose:** Individual-only enrollment with no household. Multi-program beneficiary
receiving both cash (pension) and in-kind (food). GRM inquiry.

**Profile:** 72-year-old widow, lives alone, high vulnerability.

**Eligibility:**

| Program                | Why Eligible                |
| ---------------------- | --------------------------- |
| Elderly Social Pension | age 72 >= retirement_age 65 |
| Food Assistance        | active registrant           |

**Journey:**

1. Registered 200 days ago
2. Vulnerability assessment: high (elderly, alone, low income)
3. Enrolled in Elderly Social Pension 180 days ago
4. 4 monthly pension payments of $100
5. Enrolled in Food Assistance 175 days ago — receives monthly food baskets
6. GRM ticket: asked about available medication assistance (inquiry resolved)

**Change Request:**

- `exit_registrant` (pending) — Graduated from food assistance program (pending
  approval)

**GIS:** Elderly corridor (Pangasinan)

### Maria Santos — Dual Enrollment (from Santos household)

- Head of Santos household (enrolled in Cash Transfer graduated + Universal Child Grant)
- Individually enrolled in Food Assistance 120 days ago
- **Demo point:** Same person visible in both individual and household program contexts

### Ramon Gutierrez — Dual Enrollment (from Gutierrez household)

- Head of Gutierrez household (enrolled in Emergency Relief + Cash Transfer)
- Individually enrolled in Food Assistance 50 days ago
- **Demo point:** Displaced person receiving household emergency aid + individual food
  support

---

## Rejection Stories

### Lorna Pascual — Age Rejection

- 55-year-old woman
- Applied for Elderly Social Pension → **rejected** (age 55 < retirement_age 65)
- The only named story with an explicit rejection status in STORY_ENROLLMENTS

### Other Households (Not Rejected, Background Stories)

**Note:** Castillo and Navarro households exist as registered stories but are NOT
explicitly rejected in the demo generator. Castillo (`ahmed_said`) is enrolled in Cash
Transfer as a background story. Navarro has no program enrollments.

---

## Eligibility Test Matrix

Run CEL expressions on these registrants to verify expected pass/fail results. This
matrix is the source of truth for reproducibility testing.

### Cash Transfer Program

| Registrant  | is_group | hh_total_income | hh_size | Expected                                                                         |
| ----------- | -------- | --------------- | ------- | -------------------------------------------------------------------------------- |
| Dela Cruz   | true     | 4,000           | 4       | PASS                                                                             |
| Santos      | true     | 3,500           | 4       | PASS (graduated)                                                                 |
| Gutierrez   | true     | 2,000           | 7       | PASS (post-stabilization)                                                        |
| Castillo    | true     | 12,000          | 3       | PASS (enrolled as background story — high income but no CEL enforcement in demo) |
| Rosa Garcia | false    | -               | -       | FAIL (not group)                                                                 |

### Universal Child Grant

| Registrant | is_group | child_count | Expected                                                  |
| ---------- | -------- | ----------- | --------------------------------------------------------- |
| Santos     | true     | 2           | PASS                                                      |
| Reyes      | true     | 3           | PASS (not enrolled via stories — eligible by composition) |
| Navarro    | true     | 0           | FAIL (no children — not enrolled)                         |
| Martinez   | true     | 1           | PASS (eligible but not enrolled — single program focus)   |

### Conditional Child Grant

| Registrant | is_group | Has member under 2           | Expected |
| ---------- | -------- | ---------------------------- | -------- |
| Reyes      | true     | No (youngest is Isabella, 6) | FAIL     |
| Santos     | true     | No (youngest is 10)          | FAIL     |
| Dela Cruz  | true     | No (youngest is 8)           | FAIL     |

**Note:** No named story households have members under 2. Conditional Child Grant
enrollments come from volume-generated households (blueprints bp_01, bp_04, bp_06,
bp_28).

### Elderly Social Pension

| Registrant    | is_group | age | Expected         |
| ------------- | -------- | --- | ---------------- |
| Rosa Garcia   | false    | 72  | PASS             |
| Lorna Pascual | false    | 55  | FAIL (too young) |

### Emergency Relief Fund

| Registrant | is_group | dependency_ratio            | is_female_headed | Expected             |
| ---------- | -------- | --------------------------- | ---------------- | -------------------- |
| Gutierrez  | true     | 2.5 (5 children / 2 adults) | false            | PASS (ratio >= 1.5)  |
| Dela Cruz  | true     | 1.0 (2 children / 2 adults) | false            | FAIL (ratio too low) |

### Disability Support Grant

| Registrant | is_group | has_disabled_member | disabled_count | Expected          |
| ---------- | -------- | ------------------- | -------------- | ----------------- |
| Martinez   | true     | true                | 1              | PASS ($175/month) |
| Santos     | true     | false               | 0              | FAIL              |

### Food Assistance

| Registrant      | is_registrant | active | Expected |
| --------------- | ------------- | ------ | -------- |
| Maria Santos    | true          | true   | PASS     |
| Ramon Gutierrez | true          | true   | PASS     |
| Rosa Garcia     | true          | true   | PASS     |

---

## Compliance Test Matrix

Compliance is checked on **already-enrolled** beneficiaries each cycle. Only programs
with a compliance manager are tested here.

### Cash Transfer — Compliance: `per_capita_income < poverty_line`

| Registrant                 | hh_total_income | hh_size | per_capita_income | poverty_line | Expected  |
| -------------------------- | --------------- | ------- | ----------------- | ------------ | --------- |
| Dela Cruz                  | 4,000           | 4       | 1,000             | 5,000        | COMPLIANT |
| Santos (before graduation) | 3,500           | 4       | 875               | 5,000        | COMPLIANT |
| Santos (income improved)   | 6,500           | 4       | 1,625             | 5,000        | COMPLIANT |
| Gutierrez                  | 2,000           | 7       | 286               | 5,000        | COMPLIANT |

**Note:** Santos' compliance failure is demonstrated by changing `poverty_line` to a
lower program-specific value or by using a tighter compliance threshold. In the demo,
Santos' per-capita income rises above the compliance threshold after income improvement,
triggering `non_compliant` status and subsequent graduation.

### Conditional Child Grant — Compliance: `per_capita_income < income_threshold`

No named stories are enrolled in this program. The compliance manager is configured with
`per_capita_income < income_threshold` (threshold overridden to 2,000 for this program).
Volume-generated households that qualify (baby under 2) will be subject to this
compliance check during cycle processing.

---

## Change Request Lifecycle (13)

| #   | Type              | Registrant       | State    | Life Event                                        |
| --- | ----------------- | ---------------- | -------- | ------------------------------------------------- |
| 1   | edit_individual   | Santos (Maria)   | Approved | Phone/address update after moving                 |
| 2   | edit_individual   | Santos (Maria)   | Pending  | Conflict CR #1 — overlaps with #3                 |
| 3   | edit_individual   | Santos (Maria)   | Pending  | Conflict CR #2 — overlaps with #2                 |
| 4   | edit_group        | Aquino           | Draft    | Draft CR for UI workflow demo                     |
| 5   | update_id         | Dela Cruz (Juan) | Approved | Correct national ID after data entry error        |
| 6   | exit_registrant   | Rosa Garcia      | Pending  | Graduated from food assistance (pending approval) |
| 7   | add_member        | Morales          | Approved | Add newborn to Morales household                  |
| 8   | remove_member     | Morales          | Pending  | Adult child moving out for university             |
| 9   | transfer_member   | Bautista         | Pending  | Transfer child to elderly relatives               |
| 10  | change_hoh        | Navarro          | Approved | Set Lourdes Navarro as new head of household      |
| 11  | create_group      | Maricel Ramos    | Draft    | Register new household after marriage             |
| 12  | split_household   | Bautista         | Rejected | Incomplete documentation for property division    |
| 13  | merge_registrants | Luis Fernandez   | Revision | Merge duplicate registrations from data quality   |

**CR types covered:** edit_individual, edit_group, update_id, exit_registrant,
add_member, remove_member, transfer_member, change_hoh, create_group, split_household,
merge_registrants **CR states covered:** Draft, Pending, Approved, Applied (auto-applied
on approval for some CR types), Rejected, Revision

---

## Geographic Distribution

### Philippines (fil_PH) — Default

| Region   | Province     | Stories                      | Character                       |
| -------- | ------------ | ---------------------------- | ------------------------------- |
| Northern | Nueva Ecija  | Santos, Reyes                | Agricultural, family-focused    |
| Southern | Batangas     | Dela Cruz                    | Coastal, payment hub            |
| Conflict | Mindanao     | Gutierrez                    | Displaced, emergency response   |
| Urban    | Metro Manila | Martinez                     | Peri-urban, disability services |
| Elderly  | Pangasinan   | Rosa Garcia                  | Aging population                |
| Southern | Batangas     | Castillo, Navarro (rejected) | Rejection demonstrations        |

### Togo (fr_TG)

| Region   | Stories       | Character              |
| -------- | ------------- | ---------------------- |
| Maritime | Koffi, Agbeko | Coastal, agricultural  |
| Plateaux | Mensah        | Rural, trade hub       |
| Savanes  | Amouzou       | Northern, displacement |
| Lome     | Dosseh        | Urban                  |
| Kara     | Kpodo         | Elderly corridor       |

### Sri Lanka (si_LK)

| Region        | Stories          | Character                   |
| ------------- | ---------------- | --------------------------- |
| Western       | Perera, Fernando | Urban/suburban              |
| Southern      | Silva            | Coastal                     |
| Northern      | Jayawardena      | Post-conflict, displacement |
| Central       | Wickramasinghe   | Hill country                |
| North Western | Rathnayake       | Elderly corridor            |

---

## Demo Scenarios

### Scenario 1: Payment Failure and Recovery

Show Dela Cruz household payment issue and GRM resolution.

1. Open Dela Cruz household -> 4 members
2. Show Cash Transfer enrollment
3. Show payment history: paid -> **failed** -> paid (reprocessed)
4. Navigate to GRM ticket for the failed payment
5. Show resolution and successful reprocessing

### Scenario 2: Program Graduation via Compliance Failure

Show Santos household graduating from Cash Transfer after compliance failure.

1. Open Santos household -> 5 members
2. Cash Transfer program -> show compliance manager (`per_capita_income < poverty_line`)
3. Show cycle history: 3 cycles compliant, cycle 4 **non_compliant** (income improved)
4. Show cycle 4 membership state: `non_compliant` — no entitlement generated
5. Cash Transfer: **exited** (graduation triggered by compliance failure)
6. Universal Child Grant: still **enrolled** (2 children x $50) — unaffected
7. Open Maria Santos individually -> Food Assistance (dual enrollment continues)

### Scenario 3: Multi-Generational Household

Show Reyes household as a large multi-generational family.

1. Open Reyes household -> 8 members (3 generations)
2. Show household composition: grandparents (72, 68), parents (45, 42), children (18,
   14, 10, 6)
3. Show elderly members individually eligible for Elderly Social Pension
4. Demonstrate household composition analysis

### Scenario 4: Emergency to Long-Term Support

Show Gutierrez displaced family transitioning from emergency to cash transfer.

1. Open Gutierrez household -> 7 members, displaced
2. Show Emergency Relief enrollment (fast-track 15-day cycles)
3. Show vulnerability assessment (score: very_high)
4. Show $400 Tier 2 payments
5. Show transition to Cash Transfer (30-day cycles, $150)
6. Open Ramon Gutierrez individually -> Food Assistance

### Scenario 5: Disability Support

Show Martinez family with disabled child and pending reassessment.

1. Open Martinez household -> 3 members
2. Show Miguel's disability status
3. Show Disability Support Grant: $175 (base $100 + 1 member x $75)
4. Show 3 payment records
5. Show pending disability reassessment CR

### Scenario 6: Eligibility Enforcement

Show rejections working correctly.

1. Lorna Pascual -> rejected for Elderly Pension (age 55 < 65)
2. Castillo household -> rejected for Cash Transfer (income 12,000 > 5,000)
3. Navarro household -> rejected for Child Grant (0 children)

### Scenario 7: Dual Enrollment

Show same person in individual + household programs.

1. Open Maria Santos individual -> enrolled in Food Assistance
2. Open Santos household -> enrolled in Universal Child Grant, graduated from Cash
   Transfer
3. Show both visible from Maria's profile

### Scenario 8: Change Request Lifecycle

Show different CR types and states across 13 change requests.

1. Approved: Juan Dela Cruz `update_id` — corrected national ID
2. Approved: Maria Santos `edit_individual` — phone/address update
3. Pending (conflict): Maria Santos — two overlapping CRs
4. Draft: Aquino `edit_group` — UI workflow demo
5. Pending: Rosa Garcia `exit_registrant` — food assistance graduation (pending
   approval)
6. Approved: Morales `add_member` — newborn added
7. Pending: Morales `remove_member` — adult child moving out
8. Pending: Bautista `transfer_member` — child to elderly relatives
9. Approved: Navarro `change_hoh` — new head of household
10. Draft: Maricel Ramos `create_group` — new household after marriage
11. Rejected: Bautista `split_household` — incomplete documentation
12. Revision: Luis Fernandez `merge_registrants` — duplicate data quality

### Scenario 9: Compliance Manager Overview

Show how compliance criteria work on Cash Transfer — contrasting a failure (Santos) with
a pass (Dela Cruz) on the same program.

1. Open Cash Transfer program -> show compliance manager config
2. Show CEL expression: `per_capita_income < poverty_line`
3. Open Santos cycle membership -> state: `non_compliant` (income improved)
4. Contrast with Dela Cruz cycle membership -> state: `enrolled` (compliant, per_capita
   1,000 < 5,000)
5. Show Conditional Child Grant -> also has compliance manager
   (`per_capita_income < income_threshold`)
6. **Key point:** Eligibility gates enrollment; compliance gates each cycle's payment

---

## Program Coverage Summary

| Program                 | Enrolled Stories                                                                                 | Rejection Stories                   | Compliance                                  |
| ----------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------- | ------------------------------------------- |
| Cash Transfer           | Dela Cruz (active, **compliant**), Santos (graduated, **non_compliant**), Gutierrez (transition) | Castillo (income)                   | Dela Cruz passes, Santos fails → graduation |
| Universal Child Grant   | Santos (active)                                                                                  | Navarro (no children)               | None                                        |
| Conditional Child Grant | (volume data only)                                                                               | All named stories (no baby under 2) | Configured (volume data only)               |
| Elderly Social Pension  | Rosa Garcia (active)                                                                             | Lorna Pascual (age 55)              | None                                        |
| Emergency Relief        | Gutierrez (active)                                                                               | Dela Cruz (ratio too low)           | None                                        |
| Disability Support      | Martinez (active)                                                                                | Santos (no disabled)                | None                                        |
| Food Assistance         | Maria Santos, Ramon Gutierrez, Rosa Garcia                                                       | -                                   | None                                        |

## Totals

| Metric                         | Count                                                                       |
| ------------------------------ | --------------------------------------------------------------------------- |
| Story households               | 5 (Dela Cruz, Santos, Reyes, Gutierrez, Martinez)                           |
| Enrolled in programs (stories) | 4 (Dela Cruz, Santos, Gutierrez, Martinez) — Reyes not enrolled via stories |
| Standalone individuals         | 1 (Rosa Garcia)                                                             |
| Dual-enrolled individuals      | 2 (Maria Santos, Ramon Gutierrez)                                           |
| Rejection records              | 1 (Lorna Pascual age 55 < 65)                                               |
| Programs covered               | All 7                                                                       |
| Programs with compliance       | 2 (Cash Transfer, Conditional Child Grant)                                  |
| Compliance outcomes            | 1 non_compliant (Santos), 1 compliant (Dela Cruz) — same program contrast   |
| Change requests                | 13                                                                          |
| Demo scenarios                 | 9                                                                           |
| Locales                        | 3 (fil_PH, fr_TG, si_LK)                                                    |
| Seeded volume                  | ~680 (via SeededVolumeGenerator, seed=42)                                   |
