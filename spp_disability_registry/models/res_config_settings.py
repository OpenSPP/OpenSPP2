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
    # Char (not Integer) + managed manually so it is genuinely blank by default
    # rather than showing "0" or a stale value (BM reword). Stored as a plain
    # number string; readers parse it with int(value or 0).
    disability_self_report_min_age = fields.Char(
        string="Minimum age for self-report (CFM 5-17)",
        help="Minimum age at assessment at which self-report is allowed on CFM 5-17. "
        "Required when self-report is enabled; must be between 5 and 17. Blank by default.",
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

    # === Assessment Tabs (OP#1068) ===
    # Which of the three assessment tabs are displayed, and which are required
    # before an assessment can be submitted for approval. All default to True.
    disability_display_impairment = fields.Boolean(
        string="Show Impairment Classification tab",
        default=True,
    )
    disability_display_wg = fields.Boolean(
        string="Show WG/CFM Assessment tab",
        default=True,
    )
    disability_display_support = fields.Boolean(
        string="Show Support Needs tab",
        default=True,
    )
    disability_require_impairment = fields.Boolean(
        string="Require Impairment Classification to submit",
        default=True,
    )
    disability_require_wg = fields.Boolean(
        string="Require WG/CFM Assessment to submit",
        default=True,
    )
    disability_require_support = fields.Boolean(
        string="Require Support Needs to submit",
        default=True,
    )
    disability_support_show_devices = fields.Boolean(
        string="Show Assistive Devices on Support Needs",
        default=True,
    )

    # field name -> ir.config_parameter key, for default-True booleans that must
    # round-trip a False value (a config_parameter boolean cannot — see the note
    # on disability_allow_proxy_wg_ss above).
    _DEFAULT_TRUE_PARAMS = {
        "disability_allow_proxy_wg_ss": "spp_disability_registry.allow_proxy_wg_ss",
        "disability_display_impairment": "spp_disability_registry.display_impairment",
        "disability_display_wg": "spp_disability_registry.display_wg",
        "disability_display_support": "spp_disability_registry.display_support",
        "disability_require_impairment": "spp_disability_registry.require_impairment",
        "disability_require_wg": "spp_disability_registry.require_wg",
        "disability_require_support": "spp_disability_registry.require_support",
        "disability_support_show_devices": "spp_disability_registry.support_show_devices",
    }

    def get_values(self):
        res = super().get_values()
        # nosemgrep: odoo-sudo-without-context — standard Odoo pattern for system parameter access
        icp = self.env["ir.config_parameter"].sudo()
        for field_name, key in self._DEFAULT_TRUE_PARAMS.items():
            res[field_name] = icp.get_param(key, "True") == "True"
        # Blank by default (never "0"); stored only when self-report is enabled.
        res["disability_self_report_min_age"] = icp.get_param("spp_disability_registry.self_report_min_age", "")
        return res

    def set_values(self):
        # When self-report on CFM 5-17 is enabled, a minimum age between 5 and 17
        # must be provided.
        min_age = 0
        if self.disability_allow_self_report_cfm:
            try:
                min_age = int(self.disability_self_report_min_age or 0)
            except (TypeError, ValueError):
                min_age = 0
            if not (5 <= min_age <= 17):
                raise ValidationError(
                    _("Enter a minimum self-report age between 5 and 17 to allow self-report on CFM 5-17.")
                )
        super().set_values()
        # nosemgrep: odoo-sudo-without-context — standard Odoo pattern for system parameter access
        icp = self.env["ir.config_parameter"].sudo()
        for field_name, key in self._DEFAULT_TRUE_PARAMS.items():
            icp.set_param(key, "True" if self[field_name] else "False")
        # Store the validated age only while self-report is on; otherwise clear it
        # so the field is blank by default next time.
        icp.set_param(
            "spp_disability_registry.self_report_min_age",
            str(min_age) if self.disability_allow_self_report_cfm else "",
        )
