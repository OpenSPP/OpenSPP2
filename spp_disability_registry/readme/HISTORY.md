### 19.0.3.1.0

- fix(security): the **Approver** role now carries the rights approving actually needs. Approving writes to the approval framework's own review records, and `_do_approve` does so without sudo, so the button appeared and then failed on click with "You are not allowed to modify 'Approval Review Record'". Disability Approver implies `spp_approval`'s approver group, which grants read and write on reviews but not create or unlink, so an approval trail still cannot be fabricated or deleted. Existing holders of the role gain this on upgrade without a migration, because implied groups are computed rather than stored (#1173)
- feat(security): simplify the disability roles to **Viewer**, **Assessor** and **Approver**, and make approving actually depend on the Approver role. Assessor and Validator carried identical access rights on every model, so Validator drew a distinction the system never made; it is removed and its holders become Assessors, which is the access they in fact had. Manager is renamed Approver, keeping the same group so existing assignments are untouched. The module now ships the approval workflow assessments use, bound to the Approver role: previously nothing shipped one, the Submit button stayed hidden until an admin created and selected a definition, and so no assessment could reach a state where Approve was offered. The Settings field remains, now as an override rather than a prerequisite (#1173)

### 19.0.3.0.1

- fix(disability_registry): remove the "Disability / No Disability" status smart button from the registrant form. It read "No Disability" whenever no approved assessment crossed the WG/CFM threshold, which was misleading for people who had an approved assessment recording an impairment — the full status is already shown on the Disability tab and its Assessment History (#1129)

### 19.0.3.0.0

- feat(disability_registry): age-driven assessment type selection with manual override (#1050)
- feat(disability_registry): CFM 2-4 and CFM 5-17 questionnaires (#1048, #1049)
- feat(disability_registry): configurable assessment approval workflow (#1060)
- feat(disability_registry): impairment classification on its own multi-row tab (#1054)
- feat(disability_registry): improved assistive-device management + proxy response by assessment type (#1052, #1053)
- fix(disability_registry): recognise approved assessments in the registry (#1022)

### 19.0.2.0.1

- fix(views): apply `spp_registry.x2many_no_padding` widget to the disability assessments list on registrant forms, and hide the table when empty (showing a muted info line instead) (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
