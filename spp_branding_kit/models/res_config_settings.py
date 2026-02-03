from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # OpenSPP Branding Settings
    spp_system_name = fields.Char(
        "System Name",
        help="Set your organization's system name for the interface",
        default="OpenSPP Platform",
        config_parameter="spp.system.name",
    )

    spp_documentation_url = fields.Char(
        "Documentation URL",
        help="Documentation URL for your OpenSPP implementation",
        default="https://docs.openspp.org",
        config_parameter="spp.documentation.url",
    )

    spp_support_url = fields.Char(
        "Support URL",
        help="Support website for your OpenSPP users",
        default="https://openspp.org",
        config_parameter="spp.support.url",
    )

    is_spp_show_powered_by = fields.Boolean(
        "Display OpenSPP Branding",
        help="Display 'Powered by OpenSPP' branding",
        default=True,
        config_parameter="spp.show.powered_by",
    )

    # Telemetry Settings
    is_spp_telemetry_enabled = fields.Boolean(
        "Enable Telemetry",
        help="Share anonymous usage statistics to improve OpenSPP",
        default=True,
        config_parameter="spp.telemetry.enabled",
    )

    spp_telemetry_endpoint = fields.Char(
        "Telemetry Endpoint",
        help="Endpoint for usage statistics collection",
        default="https://telemetry.openspp.org",
        config_parameter="spp.telemetry.endpoint",
    )

    is_spp_hide_odoo_referral = fields.Boolean(
        "OpenSPP Interface Mode",
        help="Optimize interface for OpenSPP-specific workflows",
        default=True,
        config_parameter="spp.ui.hide_odoo_referral",
    )
