from odoo import _, models
from odoo.exceptions import AccessError


class SppProgramEntitlementManagerDefault(models.Model):
    _inherit = ["spp.program.entitlement.manager.default"]

    def prepare_entitlements(self, cycle, beneficiaries):
        # Only program managers are allowed to run compliance-based entitlement preparation
        if not self.env.user.has_group("spp_programs.group_programs_manager"):
            raise AccessError(
                _(
                    "You do not have permission to prepare entitlements using compliance criteria. "
                    "This operation is restricted to program managers."
                )
            )

        automated_beneficiaries_filtering_mechanism = (
            # nosemgrep: odoo-sudo-without-context — standard Odoo pattern for system parameter access
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(
                "spp_programs_compliance_criteria.beneficiaries_automated_filtering_mechanism",
                "0",
            )
        )
        has_compliance = bool(cycle.program_id.compliance_manager_ids)
        if automated_beneficiaries_filtering_mechanism == "2" and has_compliance:
            domain = cycle._get_compliance_criteria_domain()
            # Use sudo() for cross-program compliance lookup on registrants, restricted to authorized managers
            satisfied_registrant_ids = (
                # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
                self.env["res.partner"]
                .sudo()
                # Cross-program compliance beneficiary lookup; domain is built from
                # program-managed compliance criteria.
                .search(domain)
                .ids
            )
            beneficiaries = beneficiaries.filtered(lambda cm: cm.partner_id.id in satisfied_registrant_ids)
        return super().prepare_entitlements(cycle, beneficiaries)
