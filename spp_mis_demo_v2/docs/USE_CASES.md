# MIS Demo V2 — Use cases

## Household stories

Each household is named by its family name. Programs that target groups enroll the
household — not individual members. Max 2 group programs per household.

### Story 1: HH1 — Payment failure, recovery, and compliance pass

**Demonstration purpose:** Cash Transfer with a payment failure and successful
reprocessing. Also demonstrates compliance passing — HH1 remains compliant each cycle,
contrasting with HH2 who fails compliance and graduates.

**Program(s) that the household is enrolled in:**

| Program       | Reason for eligibility                         | Compliance                                                | Status   |
| ------------- | ---------------------------------------------- | --------------------------------------------------------- | -------- |
| Cash Transfer | income 4,000 < poverty_line 5,000, size 4 >= 2 | **Passed** — per_capita_income 1,000 < poverty_line 5,000 | Enrolled |

**Household journey:**

1. Enrolled 100 days ago
2. Payment #1 ($150) — paid
3. Payment #2 ($150) — **failed** (bank issue)
4. Payment #3 ($150) — paid (reprocessed)
5. Compliance check passes each cycle (per_capita_income 1,000 < poverty_line 5,000)

**Existing change requests for the household:**

- `update_id` (approved) — Correct national ID number after data entry error

**Geographical location:** Coastal area

---

### Story 2: HH2 — Graduation and partial exit

**Demonstration purpose:** Complete program lifecycle — enrollment, payments, compliance
failure triggering graduation from one program while remaining in another. Shows that
exiting one program doesn't affect other enrollments. Primary story for demonstrating
the compliance manager.

**Program(s) that the household is enrolled in:**

| Program               | Reason for eligibility            | Compliance                                                                    | Status                 |
| --------------------- | --------------------------------- | ----------------------------------------------------------------------------- | ---------------------- |
| Cash Transfer         | income 3,500 < 5,000, size 5 >= 2 | **Failed** — per_capita_income exceeded poverty_line after income improvement | **Exited** (graduated) |
| Universal Child Grant | child_count 2 > 0                 | N/A (no compliance on this program)                                           | Enrolled               |

**Household journey:**

1. Enrolled in Cash Transfer 180 days ago (hh_total_income 3,500, per_capita 700)
2. Also enrolled in Universal Child Grant
3. 3 Cash Transfer payments of $150 (compliant — per_capita_income < poverty_line)
4. Income improved → **compliance check fails** in cycle 4
5. Marked `non_compliant` on cycle membership → no entitlement generated
6. Non-compliance triggers graduation review → exited from Cash Transfer 30 days ago
7. Still receiving Universal Child Grant (2 children x $50 = $100/month)

**Individual dual enrollment:**

| Member        | Program         | Reason for eligibility |
| ------------- | --------------- | ---------------------- |
| HH2M1 (42, F) | Food Assistance | active registrant      |

HH2M1 receives monthly food baskets individually. Continues after household Cash
Transfer graduation.

**Existing change requests for the household:**

- `edit_individual` (approved) — HH2M1's phone/address update after moving
- `edit_individual` (pending x2) — Conflict detection: two overlapping CRs for HH2M1

**Geographical location:** Agricultural area

---

### Story 3: HH3 — Multi-generational household

**Demonstration purpose:** Demonstrates a large multi-generational household with three
generations living together — grandparents, parents, and children. Shows household
composition complexity and how multiple individuals within a household can qualify for
different individual-targeting programs (e.g., elderly members for pension).

**Program(s) that the household is enrolled in:**

Not enrolled in group programs via named stories. Volume-generated households with
similar composition are enrolled based on blueprint eligibility flags.

**Demo points:**

- Multi-generational household structure (grandparents + parents + children)
- Elderly head (72) and spouse (68) — both individually eligible for Elderly Social
  Pension
- child_count = 3 (under 18: HH3M6 - 14y, HH3M7 - 10y, HH3M8 - 6y; HH3M5 - 18y excluded)
- Large household (8 members) for household composition analysis

**Geographical location:** Agricultural area

---

### Story 4: HH4 — Emergency relief and transition

**Demonstration purpose:** Emergency response with fast-track enrollment, then
transition to longer-term Cash Transfer support after stabilization. Shows how displaced
families move through the system.

**Program(s) that the household is enrolled in:**

| Program          | Reason for eligibility                                 | Status   |
| ---------------- | ------------------------------------------------------ | -------- |
| Emergency Relief | dependency_ratio 5/2 = 2.5, displaced                  | Enrolled |
| Cash Transfer    | income 2,000 < 5,000, size 7 >= 2 (post-stabilization) | Enrolled |

**Household journey:**

1. Typhoon displaces family → emergency registration 60 days ago
2. Vulnerability assessment: very_high (displaced, lost assets, score 85)
3. Emergency Relief enrolled (fast-track 15-day cycles)
4. 2 emergency payments of $400 (Tier 2)
5. 30 days later: stabilized, enrolled in Cash Transfer for longer-term support
6. 1 Cash Transfer payment of $150

**Individual dual enrollment:**

| Member        | Program         | Reason for eligibility |
| ------------- | --------------- | ---------------------- |
| HH4M1 (50, M) | Food Assistance | active registrant      |

HH4M1 receives food baskets individually during the emergency period.

**Existing change requests for the household:**

- `edit_individual` (approved) — HH4M1's address update after relocation to temporary
  shelter

**Geographical location:** Conflict-affected region — displacement zone

---

### Story 5: HH5 — Disability support

**Demonstration purpose:** Disability-focused support with per-member benefit
calculation. Demonstrates disability assessment and the pending reassessment workflow.

**Program(s) that the household is enrolled in:**

| Program            | Reason for eligibility                         | Status   |
| ------------------ | ---------------------------------------------- | -------- |
| Disability Support | has_disabled_member = true, disabled_count = 1 | Enrolled |

**Household journey:**

1. Enrolled 100 days ago
2. Disability assessment completed for HH5M3
3. 3 monthly payments of $175 each (base $100 + 1 disabled member x $75)

**Existing change requests for the household:**

- `edit_individual` (pending) — Disability reassessment for HH5M3 (updated medical
  documentation)

**Geographical location:** Urban

---

## Individual stories

Individuals enrolled directly in individual-targeting programs.

### Story 6: HH6M1 — Elder living alone

**Demonstration purpose:** Individual-only enrollment with no household. Multi-program
beneficiary receiving both cash (pension) and in-kind (food).

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

**Change request:**

- `exit_registrant` (pending) — Graduated from food assistance program (pending
  approval)

**Geographical location:** Elderly corridor

---

## Rejection stories

### Story 7: HH7M1 — Age rejection

- 55-year-old woman
- Applied for Elderly Social Pension → **rejected** (age 55 < retirement_age 65)
- The only named story with an explicit rejection status in STORY_ENROLLMENTS

---

## Dual enrolment

### Story 8: HH2M1 — Dual enrollment (from HH2)

- Head of HH2 (enrolled in Cash Transfer graduated + Universal Child Grant)
- Individually enrolled in Food Assistance 120 days ago
- **Demo point:** Same person visible in both individual and household program contexts

### Story 9: HH4M1 — Dual enrollment (from HH4)

- Head of HH4 (enrolled in Emergency Relief + Cash Transfer)
- Individually enrolled in Food Assistance 50 days ago
- **Demo point:** Displaced person receiving household emergency aid + individual food
  support

---

## Demo scenarios

### Scenario 1: Payment failure and recovery

Show HH1 household payment failure and recovery.

1. Open HH1 household -> 4 members
2. Show Cash Transfer enrollment
3. Show payment history: paid -> **failed** -> paid (reprocessed)
4. Show successful reprocessing of failed payment

### Scenario 2: Program graduation via compliance failure

Show HH2 household graduating from Cash Transfer after compliance failure.

1. Open HH2 household -> 5 members
2. Cash Transfer program -> show compliance manager (`per_capita_income < poverty_line`)
3. Show cycle history: 3 cycles compliant, cycle 4 **non_compliant** (income improved)
4. Show cycle 4 membership state: `non_compliant` — no entitlement generated
5. Cash Transfer: **exited** (graduation triggered by compliance failure)
6. Universal Child Grant: still **enrolled** (2 children x $50) — unaffected
7. Open HH2M1 individually -> Food Assistance (dual enrollment continues)

### Scenario 3: Multi-generational household

Show HH3 household as a large multi-generational family.

1. Open HH3 household -> 8 members (3 generations)
2. Show household composition: grandparents (72, 68), parents (45, 42), children (18,
   14, 10, 6)
3. Show elderly members individually eligible for Elderly Social Pension
4. Demonstrate household composition analysis

### Scenario 4: Emergency to long-term support

Show HH4 displaced family transitioning from emergency to cash transfer.

1. Open HH4 household -> 7 members, displaced
2. Show Emergency Relief enrollment (fast-track 15-day cycles)
3. Show vulnerability assessment (score: very_high)
4. Show $400 Tier 2 payments
5. Show transition to Cash Transfer (30-day cycles, $150)
6. Open HH4M1 individually -> Food Assistance

### Scenario 5: Disability support

Show HH5 family with disabled child and pending reassessment.

1. Open HH5 household -> 3 members
2. Show HH5M3's disability status
3. Show Disability Support Grant: $175 (base $100 + 1 member x $75)
4. Show 3 payment records
5. Show pending disability reassessment CR

### Scenario 6: Eligibility enforcement

Show rejections working correctly.

1. HH7M1 -> rejected for Elderly Pension (age 55 < 65)
2. HH8 household -> rejected for Cash Transfer (income 12,000 > 5,000)
3. HH9 household -> rejected for Child Grant (0 children)

### Scenario 7: Dual enrollment

Show same person in individual + household programs.

1. Open HH2M1 individual -> enrolled in Food Assistance
2. Open HH2 household -> enrolled in Universal Child Grant, graduated from Cash Transfer
3. Show both visible from HH2M1's profile

### Scenario 8: Change request lifecycle

Show different CR types and states across 13 change requests.

1. Approved: HH1M1 `update_id` — corrected national ID
2. Approved: HH2M1 `edit_individual` — phone/address update
3. Pending (conflict): HH2M1 — two overlapping CRs
4. Draft: HH10 `edit_group` — UI workflow demo
5. Pending: HH6M1 `exit_registrant` — food assistance graduation (pending approval)
6. Approved: HH11 `add_member` — newborn added
7. Pending: HH11 `remove_member` — adult child moving out
8. Pending: HH12 `transfer_member` — child to elderly relatives
9. Approved: HH9 `change_hoh` — set HH9M2 as new head of household
10. Draft: IND1 `create_group` — register new household
11. Rejected: HH12 `split_household` — incomplete documentation
12. Revision: IND2 `merge_registrants` — duplicate data quality

### Scenario 9: Compliance manager overview

Show how compliance criteria work on Cash Transfer — contrasting a failure (HH2) with a
pass (HH1) on the same program.

1. Open Cash Transfer program -> show compliance manager config
2. Show CEL expression: `per_capita_income < poverty_line`
3. Open HH2 cycle membership -> state: `non_compliant` (income improved)
4. Contrast with HH1 cycle membership -> state: `enrolled` (compliant, per_capita 1,000
   < 5,000)
5. Show Conditional Child Grant -> also has compliance manager
   (`per_capita_income < income_threshold`)
6. **Key point:** Eligibility gates enrollment; compliance gates each cycle's payment

---

## References

### Constellation of included registrants

Each household and individual has locale-specific names. The demo generator selects
names based on the configured locale (`fil_PH`, `fr_TG`, `si_LK`).

#### Households used in stories

| HH NN | Filipino      | Togolese        | Sri Lankan      |
| ----- | ------------- | --------------- | --------------- |
| HH1   | Dela Cruz     | Mensah          | Bandara         |
| HH2   | Santos        | Koffi           | Perera          |
| HH3   | Reyes         | Lawson          | Rathnayake      |
| HH4   | Gutierrez     | Deku            | Kumara          |
| HH5   | Martinez      | Koudawo         | Wickramasinghe  |
| HH6M1 | Rosa Garcia   | Adzo Amegah     | Malini Silva    |
| HH7M1 | Lorna Pascual | Ablavi Gbeassor | Priyanka Mendis |
| HH8   | Castillo      | Agbodjan        | Weerasinghe     |
| HH9   | Navarro       | Gbeho           | Amarasinghe     |
| HH10  | Aquino        | Tetteh          | Herath          |
| HH11  | Morales       | Agbeko          | Fernando        |
| HH12  | Bautista      | Akakpo          | Gunasekara      |

#### Household information

##### Information about HH1

| HH NN | Filipino  | Togolese | Sri Lankan |
| ----- | --------- | -------- | ---------- |
| HH1   | Dela Cruz | Mensah   | Bandara    |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Calamba City        |
| Togolese   | Tokoin              |
| Sri Lankan | Moratuwa            |

| Member ID | Role   | Age | Gender | Filipino | Togolese | Sri Lankan |
| --------- | ------ | --- | ------ | -------- | -------- | ---------- |
| HH1M1     | Head   | 38  | Male   | Juan     | Kofi     | Nimal      |
| HH1M2     | Spouse | 35  | Female | Ana      | Akosua   | Kamani     |
| HH1M3     | Child  | 12  | Male   | Paolo    | Yao      | Lahiru     |
| HH1M4     | Child  | 8   | Female | Maria    | Ama      | Sanduni    |

##### Information about HH2

| HH NN | Filipino | Togolese | Sri Lankan |
| ----- | -------- | -------- | ---------- |
| HH2   | Santos   | Koffi    | Perera     |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Santa Rosa City     |
| Togolese   | Aflao Sagbado       |
| Sri Lankan | Kolonnawa           |

| Member ID | Role           | Age | Gender | Filipino | Togolese | Sri Lankan |
| --------- | -------------- | --- | ------ | -------- | -------- | ---------- |
| HH2M1     | Head           | 42  | Female | Maria    | Ama      | Kumari     |
| HH2M2     | Spouse         | 44  | Male   | Ricardo  | Kokou    | Sunil      |
| HH2M3     | Parent (elder) | 68  | Female | Lola     | Adjo     | Padma      |
| HH2M4     | Child          | 14  | Female | Sofia    | Esi      | Nimali     |
| HH2M5     | Child          | 10  | Male   | Miguel   | Kweku    | Kasun      |

##### Information about HH3

| HH NN | Filipino | Togolese | Sri Lankan |
| ----- | -------- | -------- | ---------- |
| HH3   | Reyes    | Lawson   | Rathnayake |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | San Pablo City      |
| Togolese   | Kpalime             |
| Sri Lankan | Kandy Four Gravets  |

| Member ID | Role                    | Age | Gender | Filipino | Togolese | Sri Lankan |
| --------- | ----------------------- | --- | ------ | -------- | -------- | ---------- |
| HH3M1     | Head                    | 72  | Male   | Jose Sr  | Kwame    | Kamal      |
| HH3M2     | Spouse                  | 68  | Female | Carmen   | Afia     | Ramya      |
| HH3M3     | Adult (son)             | 45  | Male   | Miguel   | Kossi    | Ajith      |
| HH3M4     | Adult (daughter-in-law) | 42  | Female | Teresa   | Ayoko    | Sanduni    |
| HH3M5     | Child                   | 18  | Male   | Jose Jr  | Dela     | Pradeep    |
| HH3M6     | Child                   | 14  | Female | Lucia    | Dzidzor  | Wasana     |
| HH3M7     | Child                   | 10  | Male   | Antonio  | Kokou    | Ruwan      |
| HH3M8     | Child                   | 6   | Female | Isabella | Ewoenam  | Nimali     |

##### Information about HH4

| HH NN | Filipino  | Togolese | Sri Lankan |
| ----- | --------- | -------- | ---------- |
| HH4   | Gutierrez | Deku     | Kumara     |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Antipolo City       |
| Togolese   | Sokode              |
| Sri Lankan | Galle Four Gravets  |

| Member ID | Role   | Age | Gender | Filipino | Togolese | Sri Lankan |
| --------- | ------ | --- | ------ | -------- | -------- | ---------- |
| HH4M1     | Head   | 50  | Male   | Ramon    | Kosi     | Asanka     |
| HH4M2     | Spouse | 45  | Female | Elena    | Akua     | Chamari    |
| HH4M3     | Child  | 18  | Male   | Marco    | Komla    | Dinesh     |
| HH4M4     | Child  | 15  | Female | Isabella | Ablavi   | Nishadi    |
| HH4M5     | Child  | 12  | Male   | Jose     | Kofi     | Tharindu   |
| HH4M6     | Child  | 9   | Female | Sofia    | Ama      | Dilhani    |
| HH4M7     | Child  | 5   | Male   | Miguel   | Edem     | Ravindu    |

##### Information about HH5

| HH NN | Filipino | Togolese | Sri Lankan     |
| ----- | -------- | -------- | -------------- |
| HH5   | Martinez | Koudawo  | Wickramasinghe |

|            | Geographic location    |
| ---------- | ---------------------- |
| Filipino   | Makati City            |
| Togolese   | Lome Commune           |
| Sri Lankan | Dehiwala Mount Lavinia |

| Member ID | Role   | Age | Gender | Filipino | Togolese | Sri Lankan | Notes                     |
| --------- | ------ | --- | ------ | -------- | -------- | ---------- | ------------------------- |
| HH5M1     | Head   | 48  | Male   | David    | Ata      | Sanjeewa   |                           |
| HH5M2     | Spouse | 45  | Female | Sofia    | Ama      | Nisansala  |                           |
| HH5M3     | Child  | 12  | Male   | Miguel   | Kofi     | Charitha   | Disabled (cerebral palsy) |

##### Information about HH6

| HH NN | Filipino    | Togolese    | Sri Lankan   |
| ----- | ----------- | ----------- | ------------ |
| HH6M1 | Rosa Garcia | Adzo Amegah | Malini Silva |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Quezon City         |
| Togolese   | Be                  |
| Sri Lankan | Fort                |

| Member ID | Role       | Age | Gender | Filipino    | Togolese    | Sri Lankan   |
| --------- | ---------- | --- | ------ | ----------- | ----------- | ------------ |
| HH6M1     | Individual | 72  | Female | Rosa Garcia | Adzo Amegah | Malini Silva |

##### Information about HH7

| HH NN | Filipino      | Togolese        | Sri Lankan      |
| ----- | ------------- | --------------- | --------------- |
| HH7M1 | Lorna Pascual | Ablavi Gbeassor | Priyanka Mendis |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Pasig City          |
| Togolese   | Nyekonakpoe         |
| Sri Lankan | Pettah              |

| Member ID | Role       | Age | Gender | Filipino      | Togolese        | Sri Lankan      |
| --------- | ---------- | --- | ------ | ------------- | --------------- | --------------- |
| HH7M1     | Individual | 55  | Female | Lorna Pascual | Ablavi Gbeassor | Priyanka Mendis |

##### Information about HH8

| HH NN | Filipino | Togolese | Sri Lankan  |
| ----- | -------- | -------- | ----------- |
| HH8   | Castillo | Agbodjan | Weerasinghe |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Taguig City         |
| Togolese   | Adidogome           |
| Sri Lankan | Dehiwala            |

| Member ID | Role   | Age | Gender | Filipino | Togolese | Sri Lankan |
| --------- | ------ | --- | ------ | -------- | -------- | ---------- |
| HH8M1     | Head   | 45  | Male   | Roberto  | Komla    | Ruwan      |
| HH8M2     | Spouse | 40  | Female | Linda    | Adjoa    | Nilmini    |
| HH8M3     | Child  | 14  | Male   | Paolo    | Messan   | Sampath    |

##### Information about HH9

| HH NN | Filipino | Togolese | Sri Lankan  |
| ----- | -------- | -------- | ----------- |
| HH9   | Navarro  | Gbeho    | Amarasinghe |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Bacoor City         |
| Togolese   | Baguida Centre      |
| Sri Lankan | Hikkaduwa           |

| Member ID | Role          | Age | Gender | Filipino | Togolese | Sri Lankan | Notes    |
| --------- | ------------- | --- | ------ | -------- | -------- | ---------- | -------- |
| HH9M1     | Head          | 52  | Male   | Ricardo  | Selom    | Ranjith    |          |
| HH9M2     | Spouse        | 48  | Female | Lourdes  | Mawusi   | Champa     |          |
| HH9M3     | Brother       | 46  | Male   | Eduardo  | Senyo    | Chandana   | Disabled |
| HH9M4     | Sister-in-law | 44  | Female | Cristina | Ayele    | Nadeesha   |          |

##### Information about HH10

| HH NN | Filipino | Togolese | Sri Lankan |
| ----- | -------- | -------- | ---------- |
| HH10  | Aquino   | Tetteh   | Herath     |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Manila              |
| Togolese   | Kpalime Centre      |
| Sri Lankan | Mount Lavinia       |

| Member ID | Role  | Age | Gender | Filipino | Togolese | Sri Lankan |
| --------- | ----- | --- | ------ | -------- | -------- | ---------- |
| HH10M1    | Head  | 38  | Female | Rosario  | Adjoa    | Anoma      |
| HH10M2    | Child | 15  | Male   | Daniel   | Messan   | Lahiru     |
| HH10M3    | Child | 11  | Female | Angela   | Akossiwa | Hiruni     |
| HH10M4    | Child | 7   | Male   | Rafael   | Edem     | Dinesh     |

##### Information about HH11

| HH NN | Filipino | Togolese | Sri Lankan |
| ----- | -------- | -------- | ---------- |
| HH11  | Morales  | Agbeko   | Fernando   |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Dasmarinas          |
| Togolese   | Tove                |
| Sri Lankan | Galle Fort          |

| Member ID | Role   | Age | Gender | Filipino | Togolese | Sri Lankan |
| --------- | ------ | --- | ------ | -------- | -------- | ---------- |
| HH11M1    | Head   | 45  | Male   | Carlos   | Kodjo    | Kasun      |
| HH11M2    | Spouse | 42  | Female | Elena    | Esi      | Dilani     |
| HH11M3    | Child  | 16  | Male   | Marco    | Komla    | Nuwan      |
| HH11M4    | Child  | 12  | Female | Sofia    | Ablavi   | Nethmi     |
| HH11M5    | Child  | 8   | Male   | Luis     | Koku     | Chamara    |

##### Information about HH12

| HH NN | Filipino | Togolese | Sri Lankan |
| ----- | -------- | -------- | ---------- |
| HH12  | Bautista | Akakpo   | Gunasekara |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Commonwealth        |
| Togolese   | Zio                 |
| Sri Lankan | Gampaha             |

| Member ID | Role   | Age | Gender | Filipino | Togolese | Sri Lankan |
| --------- | ------ | --- | ------ | -------- | -------- | ---------- |
| HH12M1    | Head   | 48  | Male   | Eduardo  | Mawuli   | Thilak     |
| HH12M2    | Spouse | 44  | Female | Carmen   | Kafui    | Kusum      |
| HH12M3    | Child  | 22  | Female | Patricia | Dede     | Gayani     |
| HH12M4    | Child  | 19  | Male   | Fernando | Yaovi    | Ashan      |
| HH12M5    | Child  | 16  | Female | Lucia    | Yawa     | Chathurika |
| HH12M6    | Child  | 13  | Female | Rosalie  | Abla     | Ruwanthi   |
| HH12M7    | Child  | 9   | Male   | Antonio  | Komi     | Mahesh     |

---

#### Individuals used in stories

| ID   | Filipino       | Togolese         | Sri Lankan          |
| ---- | -------------- | ---------------- | ------------------- |
| IND1 | Maricel Ramos  | Akossiwa Adjakly | Sanduni Karunaratne |
| IND2 | Luis Fernandez | Messan Ameganvi  | Dinesh Rajapaksa    |

#### Individual information

##### Information about IND1

| ID   | Age | Gender | Filipino      | Togolese         | Sri Lankan          |
| ---- | --- | ------ | ------------- | ---------------- | ------------------- |
| IND1 | 35  | Female | Maricel Ramos | Akossiwa Adjakly | Sanduni Karunaratne |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Poblacion           |
| Togolese   | Ogou                |
| Sri Lankan | Kalutara            |

##### Information about IND2

| ID   | Age | Gender | Filipino       | Togolese        | Sri Lankan       |
| ---- | --- | ------ | -------------- | --------------- | ---------------- |
| IND2 | 40  | Male   | Luis Fernandez | Messan Ameganvi | Dinesh Rajapaksa |

|            | Geographic location |
| ---------- | ------------------- |
| Filipino   | Real                |
| Togolese   | Lacs                |
| Sri Lankan | Matara              |

---

### Configuration of included programs

#### 1. Cash Transfer Program (Group)

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

#### 2. Universal Child Grant (Group)

| Field       | Value                                        |
| ----------- | -------------------------------------------- |
| Target      | Household (Group)                            |
| CEL         | `r.is_group == true and child_count > 0`     |
| Constants   | `base_child_grant` = 50                      |
| Entitlement | `base_child_grant * child_count` ($50/child) |
| Cycle       | 30 days                                      |
| Logic Pack  | `child_benefit`                              |

#### 3. Conditional Child Grant (Group)

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

#### 4. Elderly Social Pension (Individual)

| Field       | Value                                                 |
| ----------- | ----------------------------------------------------- |
| Target      | Individual                                            |
| CEL         | `r.is_group == false and age >= retirement_age`       |
| Constants   | `retirement_age` = 65; `elderly_pension_amount` = 100 |
| Entitlement | $100/month                                            |
| Cycle       | 30 days                                               |
| Logic Pack  | `social_pension`                                      |

#### 5. Emergency Relief Fund (Group)

| Field       | Value                                                                                          |
| ----------- | ---------------------------------------------------------------------------------------------- |
| Target      | Household (Group)                                                                              |
| CEL         | `r.is_group == true and (dependency_ratio >= 1.5 or (is_female_headed and elderly_count > 0))` |
| Entitlement | Tiered: $500 (score >= 90), $400 (score >= 80), $300 (score >= 70)                             |
| Cycle       | 15 days (fast-track)                                                                           |
| Logic Pack  | `vulnerability_assessment`                                                                     |

#### 6. Disability Support Grant (Group)

| Field       | Value                                                             |
| ----------- | ----------------------------------------------------------------- |
| Target      | Household (Group)                                                 |
| CEL         | `r.is_group == true and has_disabled_member`                      |
| Constants   | `disability_grant_base` = 100; `disability_grant_per_member` = 75 |
| Entitlement | $100 base + $75 per disabled member                               |
| Cycle       | 30 days                                                           |
| Logic Pack  | `disability_assistance`                                           |

#### 7. Food Assistance (Individual)

| Field       | Value                                          |
| ----------- | ---------------------------------------------- |
| Target      | Individual                                     |
| CEL         | `r.is_registrant == true and r.active == true` |
| Entitlement | In-kind (Food Basket)                          |
| Cycle       | 30 days                                        |
| Logic Pack  | None (simple inline CEL)                       |

---

### Overview of included change requests

| #   | Type                     | Target     | Registrant | State    | Life Event                                        |
| --- | ------------------------ | ---------- | ---------- | -------- | ------------------------------------------------- |
| 1   | Edit individual          | Individual | HH2M1      | Applied  | Phone/address update after moving (auto-applied)  |
| 2   | Edit individual          | Individual | HH2M1      | Pending  | Conflict CR #1 — overlaps with #3                 |
| 3   | Edit individual          | Individual | HH2M1      | Pending  | Conflict CR #2 — overlaps with #2                 |
| 4   | Edit group               | Group      | HH10       | Draft    | Draft CR for UI workflow demo                     |
| 5   | Update ID                | Individual | HH1M1      | Approved | Correct national ID after data entry error        |
| 6   | Exit registrant          | Individual | HH6M1      | Pending  | Graduated from food assistance (pending approval) |
| 7   | Add member               | Group      | HH11       | Approved | Add newborn to Morales household                  |
| 8   | Remove member            | Group      | HH11       | Pending  | Adult child moving out for university             |
| 9   | Transfer member          | Group      | HH12       | Pending  | Transfer child to elderly relatives               |
| 10  | Change head of household | Group      | HH9        | Approved | Set HH9M2 as new head of household                |
| 11  | Create group             | Group      | IND1       | Draft    | Register new household                            |
| 12  | Split household          | Group      | HH12       | Rejected | Incomplete documentation for property division    |
| 13  | Merge registrants        | Individual | IND2       | Revision | Merge duplicate registrations from data quality   |

**CR types covered:** edit_individual, edit_group, update_id, exit_registrant,
add_member, remove_member, transfer_member, change_hoh, create_group, split_household,
merge_registrants

**CR states covered:** Draft, Pending, Approved, Applied (auto-applied on approval for
some CR types), Rejected, Revision

**Note:** CR #1 state is "Applied" (not "Approved") because the edit_individual CR type
auto-applies when all approval tiers are completed.

---

### Geographic distribution

Each story registrant is assigned to an administrative area appropriate to its locale
from the demo area data.

| Character                        | HH    | Philippines (fil_PH) | Togo (fr_TG)   | Sri Lanka (si_LK)      |
| -------------------------------- | ----- | -------------------- | -------------- | ---------------------- |
| Coastal, payment hub             | HH1   | Calamba City         | Tokoin         | Moratuwa               |
| Agricultural, family-focused     | HH2   | Santa Rosa City      | Aflao Sagbado  | Kolonnawa              |
| Agricultural, multi-generational | HH3   | San Pablo City       | Kpalime        | Kandy Four Gravets     |
| Displaced, emergency response    | HH4   | Antipolo City        | Sokode         | Galle Four Gravets     |
| Urban, disability services       | HH5   | Makati City          | Lome Commune   | Dehiwala Mount Lavinia |
| Elderly, aging population        | HH6M1 | Quezon City          | Be             | Fort                   |
| Rejection demonstration          | HH7M1 | Pasig City           | Nyekonakpoe    | Pettah                 |
| Background story                 | HH8   | Taguig City          | Adidogome      | Dehiwala               |
| Extended family, disability      | HH9   | Bacoor City          | Baguida Centre | Hikkaduwa              |
| Single mother, CR demo           | HH10  | Manila               | Kpalime Centre | Mount Lavinia          |
| Family, add/remove member CR     | HH11  | Dasmarinas           | Tove           | Galle Fort             |
| Large family, transfer/split CR  | HH12  | Commonwealth         | Zio            | Gampaha                |
| Individual, create group CR      | IND1  | Poblacion            | Ogou           | Kalutara               |
| Individual, merge CR             | IND2  | Real                 | Lacs           | Matara                 |

---

### Overview

| Metric                   | Count                                      |
| ------------------------ | ------------------------------------------ |
| Total programs included  | 7                                          |
| Programs with compliance | 2 (Cash Transfer, Conditional Child Grant) |
| Change requests          | 13 (11 types, 6 states)                    |
| Demo scenarios           | 9                                          |
| Locales                  | 3 (fil_PH, fr_TG, si_LK)                   |
| Seeded volume            | ~680 households, ~2,100 individuals        |
