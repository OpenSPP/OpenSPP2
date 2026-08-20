### 19.0.2.0.2

- fix(data): repair the 24 shipped logic-pack filter items whose CEL expressions referenced registrant fields or studio variables that exist in no module, so they could never translate or evaluate (#431). 1 item is fixed properly: Institutional Residence Exclusion keeps its expression, backed by a new `in_institutional_care` standard variable over the existing `spp_registry` field of the same name. 4 items are rewritten to the working part of their expression (OVC Child Age Eligibility, OVC Vulnerable Household Check, GMI Residency Requirement, Public Works Poverty Status Check). The other 19 are removed because no near-equivalent field or variable exists anywhere in the platform (Disability Status Verification, OVC Orphan Status Check, OVC School Enrollment Requirement, Social Pension No Formal Pension Check, GMI Employment Barriers Check, Public Works Physical Work Capability and Seasonal Availability, CCT Health Conditionality Compliance, Geographic Limited Service Access, and 10 Exclusion Criteria items: Government Employee, Formal Sector, Vehicle Ownership, Business Ownership, Housing Quality, Pension Receipt, Duplicate Program, Income Tax Payer, Bank Balance, Livestock Ownership). Pack data is `noupdate`, so a migration applies the same removals/rewrites to existing databases.

### 19.0.2.0.1

- fix(security): drop the Program Manager → `group_studio_viewer` extension per the OP#951 menu audit (Program Manager should NOT see the Studio top-level menu). Removes `data/user_roles.xml` from the module entirely; System Admin retains Studio visibility via `spp_security.group_spp_admin` → `group_studio_manager` (wired in `spp_studio/security/groups.xml`).

### 19.0.2.0.0

- Initial migration to OpenSPP2
