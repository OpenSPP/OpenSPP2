### 19.0.2.0.3

- fix(variables): the `has_disability` and `has_disabled_member` standard variables resolved against `is_person_with_disability`, a field that exists nowhere in the codebase. Any program filtering on either silently matched nothing. Both now use `has_disability`, the real field on `res.partner` (#955)

### 19.0.2.0.2

- fix(data): repair the 24 shipped logic-pack filter items whose CEL expressions referenced registrant fields that exist in no module — in several cases through catalogued variables whose `source_field` is dangling (#446) — so they could never translate or evaluate (#431). 1 item is fixed properly: Institutional Residence Exclusion keeps its expression, backed by a new `in_institutional_care` standard variable over the existing `spp_registry` field of the same name (both scoped to individual context). 3 items are rewritten to the stricter working part of their expression (OVC Child Age Eligibility, OVC Vulnerable Household Check, Public Works Poverty Status Check). The other 20 are removed because no working near-equivalent exists, or, for GMI Residency Requirement, because the only surviving sub-expression would be more permissive than the shipped rule (Disability Status Verification, OVC Orphan Status Check, OVC School Enrollment Requirement, Social Pension No Formal Pension Check, GMI Employment Barriers Check and Residency Requirement, Public Works Physical Work Capability and Seasonal Availability, CCT Health Conditionality Compliance, Geographic Limited Service Access, and 10 Exclusion Criteria items: Government Employee, Formal Sector, Vehicle Ownership, Business Ownership, Housing Quality, Pension Receipt, Duplicate Program, Income Tax Payer, Bank Balance, Livestock Ownership). Pack data is `noupdate`, so a migration applies the same removals/rewrites to existing databases; every migration write is guarded on the item still carrying the known-broken shipped expression, so locally repaired items are left untouched. Logic already installed from removed items (`installed_logic_id`) is deliberately not deleted — once installed it is the deployment's own data.

### 19.0.2.0.1

- fix(security): drop the Program Manager → `group_studio_viewer` extension per the OP#951 menu audit (Program Manager should NOT see the Studio top-level menu). Removes `data/user_roles.xml` from the module entirely; System Admin retains Studio visibility via `spp_security.group_spp_admin` → `group_studio_manager` (wired in `spp_studio/security/groups.xml`).

### 19.0.2.0.0

- Initial migration to OpenSPP2
