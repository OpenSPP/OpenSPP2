# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    is_registry_admin_only_crud = fields.Boolean(
        "Restrict Registry Create/Edit/Delete to Admin Only",
        help=(
            "Only administrators can add, modify, or remove registrants. "
            "Other users can still view all registry data but cannot make changes."
        ),
        default=True,
        config_parameter="spp_starter.registry_admin_only_crud",
    )
