from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # === Assessment Type ===
    disability_disregard_age = fields.Boolean(
        string="Allow manual assessment type",
        config_parameter="spp_disability_registry.disregard_age",
        help="When enabled, the assessment type can be selected manually and the "
        "registrant's date of birth is not required. When disabled (default), the "
        "assessment type is determined automatically from the registrant's age and "
        "a date of birth is required.",
    )
