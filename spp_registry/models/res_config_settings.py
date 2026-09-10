# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

# Legacy config-parameter keys this toggle keeps in sync. The starter modules'
# controllers still read their own key (spp_farmer_registry reads the first,
# spp_starter_sp_mis reads the second), so the central "Registry Settings"
# toggle writes both — no migration or controller change needed, and neither
# deployment's enforcement breaks.
_LEGACY_KEYS = (
    "spp_farmer_registry.registry_admin_only_crud",
    "spp_starter.registry_admin_only_crud",
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_registry_admin_only_crud = fields.Boolean(
        "Restrict Registry Create/Edit/Delete to Admin Only",
        default=True,
        help=(
            "Only administrators can add, modify, or remove registrants. "
            "Other users can still view all registry data but cannot make changes."
        ),
    )

    def get_values(self):
        res = super().get_values()
        # ir.config_parameter is a global system setting; sudo is the standard
        # access pattern for reading it.
        icp = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        # A deployment ships only one of the two starter controllers, so at most
        # one key is set. Reflect an explicit value if present; otherwise fall
        # back to the secure default (True), matching the legacy
        # config_parameter default the starters used.
        explicit = [v for v in (icp.get_param(key) for key in _LEGACY_KEYS) if v is not False]
        res["is_registry_admin_only_crud"] = any(v == "True" for v in explicit) if explicit else True
        return res

    def set_values(self):
        res = super().set_values()
        # ir.config_parameter is a global system setting; sudo is the standard
        # access pattern for writing it.
        icp = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        value = "True" if self.is_registry_admin_only_crud else "False"
        # Keep both legacy keys in sync so whichever starter controller is
        # installed reads the value the operator set here.
        for key in _LEGACY_KEYS:
            icp.set_param(key, value)
        return res
