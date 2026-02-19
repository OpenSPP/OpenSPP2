from odoo import _, models
from odoo.exceptions import AccessError
from odoo.osv.expression import AND


class SppCycleManagerDefault(models.Model):
    _inherit = "spp.cycle.manager.default"

    def _add_beneficiaries(self, cycle, beneficiaries, state="draft", do_count=False):
        # Only program managers and validators are allowed to run compliance-based beneficiary filtering
        if not (
            self.env.user.has_group("spp_programs.group_programs_manager")
            or self.env.user.has_group("spp_programs.group_programs_validator")
        ):
            raise AccessError(
                _(
                    "You do not have permission to filter beneficiaries using compliance criteria. "
                    "This operation is restricted to program managers and validators."
                )
            )

        automated_beneficiaries_filtering_mechanism = (
            self.env["ir.config_parameter"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .get_param(
                "spp_programs_compliance_criteria.beneficiaries_automated_filtering_mechanism",
                "0",
            )
        )
        has_compliance = bool(cycle.program_id.compliance_manager_ids)
        if automated_beneficiaries_filtering_mechanism == "1" and has_compliance:
            domain = cycle._get_compliance_criteria_domain()
            new_domain = AND([domain, [["id", "in", beneficiaries]]])
            # Use sudo() for cross-program compliance lookup on registrants,
            # restricted to authorized managers and validators
            beneficiaries = (
                self.env["res.partner"]  # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
                .sudo()  # nosemgrep: odoo-sudo-on-sensitive-models
                .search(
                    # Cross-program compliance beneficiary lookup; caller restricted to
                    # group_programs_manager and group_programs_validator. Domain is
                    # built from program-managed compliance criteria.
                    new_domain
                )
                .ids
            )
        res = super()._add_beneficiaries(cycle, beneficiaries, state, do_count)
        return res
