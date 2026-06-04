from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # === Assessment Type ===
    disability_disregard_age = fields.Boolean(
        string="Allow manual assessment type",
        config_parameter="spp_disability_registry.disregard_age",
        help="When enabled, the assessment type can be selected manually and the "
        "registrant's date of birth is not required. When disabled, the assessment "
        "type is determined automatically from the registrant's age and a date of "
        "birth is required.",
    )

    # === Proxy Response ===
    disability_allow_self_report_cfm = fields.Boolean(
        string="Allow self-report on CFM 5-17",
        config_parameter="spp_disability_registry.allow_self_report_cfm_5_17",
        help="When enabled, the proxy response flag can be unticked on CFM 5-17 "
        "assessments (subject to the minimum self-report age below).",
    )
    disability_self_report_min_age = fields.Integer(
        string="Minimum age for self-report (CFM 5-17)",
        config_parameter="spp_disability_registry.self_report_min_age",
        help="Minimum age at assessment at which self-report is allowed on CFM 5-17. "
        "Required when self-report is enabled; must be between 5 and 17.",
    )
    # NB: managed manually below (not via config_parameter). A config_parameter
    # Boolean defaulting to True cannot persist a False value: set_param(key, False)
    # DELETES the parameter, and get_values then falls back to the field default
    # (True), so the box re-ticks itself on save. Storing an explicit "True"/"False"
    # string avoids the delete.
    disability_allow_proxy_wg_ss = fields.Boolean(
        string="Allow proxy report on WG-SS",
        default=True,
        help="When enabled, the proxy response flag can be ticked on adult WG-SS "
        "assessments. When disabled, WG-SS assessments are self-report only.",
    )

    # === Approval ===
    # The approval workflow applied to disability assessments. Create the workflow in
    # Approvals > Approval Definitions (Model = Disability Assessment), then select it
    # here. The assessment reads it via _get_approval_definition().
    disability_approval_definition_id = fields.Many2one(
        "spp.approval.definition",
        string="Assessment approval workflow",
        domain="[('model', '=', 'spp.disability.assessment')]",
        config_parameter="spp_disability_registry.approval_definition_id",
        help="Approval workflow applied to disability assessments. Create it under "
        "Approvals > Approval Definitions (with Model = Disability Assessment), then "
        "select it here. Until one is selected, assessments cannot be submitted for "
        "approval.",
    )

    def get_values(self):
        res = super().get_values()
        # nosemgrep: odoo-sudo-without-context — standard Odoo pattern for system parameter access
        icp = self.env["ir.config_parameter"].sudo()
        res["disability_allow_proxy_wg_ss"] = (
            icp.get_param("spp_disability_registry.allow_proxy_wg_ss", "True") == "True"
        )
        return res

    def set_values(self):
        # When self-report on CFM 5-17 is enabled, a minimum age between 5 and 17
        # must be provided.
        if self.disability_allow_self_report_cfm and not (5 <= self.disability_self_report_min_age <= 17):
            raise ValidationError(
                _("Enter a minimum self-report age between 5 and 17 to allow self-report on CFM 5-17.")
            )
        super().set_values()
        # nosemgrep: odoo-sudo-without-context — standard Odoo pattern for system parameter access
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(
            "spp_disability_registry.allow_proxy_wg_ss",
            "True" if self.disability_allow_proxy_wg_ss else "False",
        )
