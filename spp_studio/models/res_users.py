# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""User preferences for Studio module."""

from odoo import fields, models


class ResUsers(models.Model):
    """Extend res.users with Studio preferences."""

    _inherit = "res.users"

    spp_studio_show_advanced = fields.Boolean(
        string="Show Advanced Options in Studio",
        default=False,
        help="When enabled, shows advanced configuration options in Studio forms (Variables, Logic, etc.)",
    )

    @property
    def SELF_READABLE_FIELDS(self):
        """Allow users to read their own Studio preferences."""
        return super().SELF_READABLE_FIELDS + ["spp_studio_show_advanced"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        """Allow users to update their own Studio preferences."""
        return super().SELF_WRITEABLE_FIELDS + ["spp_studio_show_advanced"]
