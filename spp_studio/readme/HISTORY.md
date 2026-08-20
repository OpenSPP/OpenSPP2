### 19.0.2.0.2

- fix(data): repair the 24 shipped logic-pack filter items whose CEL expressions referenced registrant fields or studio variables that exist in no module, so they could never translate or evaluate (#431). 4 items are rewritten to the working part of their expression (OVC Child Age Eligibility, OVC Vulnerable Household Check, GMI Residency Requirement, Public Works Poverty Status Check); the other 20 are removed because no near-equivalent field or variable exists (Disability Status Verification, OVC Orphan Status Check, OVC School Enrollment Requirement, Social Pension No Formal Pension Check, GMI Employment Barriers Check, Public Works Physical Work Capability and Seasonal Availability, CCT Health Conditionality Compliance, Geographic Limited Service Access, and 11 Exclusion Criteria items: Government Employee, Formal Sector, Vehicle Ownership, Business Ownership, Housing Quality, Pension Receipt, Duplicate Program, Income Tax Payer, Bank Balance, Livestock Ownership, Institutional Residence). Pack data is `noupdate`, so a migration applies the same removals/rewrites to existing databases.

### 19.0.2.0.1

- fix(security): drop the Program Manager → `group_studio_viewer` extension per the OP#951 menu audit (Program Manager should NOT see the Studio top-level menu). Removes `data/user_roles.xml` from the module entirely; System Admin retains Studio visibility via `spp_security.group_spp_admin` → `group_studio_manager` (wired in `spp_studio/security/groups.xml`).

### 19.0.2.0.0

- Initial migration to OpenSPP2
