# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models

# Storage key for the registry access-control setting. Imported by res_partner
# so the toggle and its enforcement can never drift apart.
REGISTRY_ADMIN_ONLY_CRUD_PARAM = "spp_starter.registry_admin_only_crud"


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_registry_admin_only_crud = fields.Boolean(
        "Restrict Registry Create/Edit/Delete to Admin Only",
        help=(
            "Only administrators can add, modify, or remove registrants. "
            "Other users can still view all registry data but cannot make changes."
        ),
        config_parameter=REGISTRY_ADMIN_ONLY_CRUD_PARAM,
    )

    def set_values(self):
        """Persist the toggle explicitly, including when it is off (OP#1142).

        Odoo stores a False ``config_parameter`` by *deleting* the row, and
        ``default_get`` falls back to the field's ``default`` when the row is
        missing. Pairing that with ``default=True`` made "off" unrepresentable:
        the toggle sprang back on at every reload, while enforcement — which
        reads a missing row as False — quietly went unrestricted, so the form
        claimed the registry was locked when it was open.

        Writing the value as a string keeps "off" a stored fact rather than an
        absence, which is what makes the two sides agree. The install default
        now comes from ``data/config_parameters.xml`` instead of a field
        default, so a missing row can no longer mean "on".
        """
        super().set_values()
        # Writing a system configuration parameter. ir.config_parameter is
        # restricted to Settings managers, and the settings form is already
        # gated on that group, so this widens nothing.
        # nosemgrep: odoo-sudo-without-context
        self.env["ir.config_parameter"].sudo().set_param(
            REGISTRY_ADMIN_ONLY_CRUD_PARAM,
            "True" if self.is_registry_admin_only_crud else "False",
        )
