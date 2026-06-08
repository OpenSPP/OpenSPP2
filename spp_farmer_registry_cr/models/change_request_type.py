# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend CR type with farm activity operation toggles."""

from odoo import fields, models


class ChangeRequestType(models.Model):
    """Add activity operation configuration to CR type."""

    _inherit = "spp.change.request.type"

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIVITY OPERATIONS CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    allow_activity_add = fields.Boolean(
        string="Allow Add Activity",
        default=True,
        help="Allow adding new farm activities via this CR type.",
    )
    allow_activity_update = fields.Boolean(
        string="Allow Edit Activity",
        default=True,
        help="Allow editing existing farm activities via this CR type.",
    )
    allow_activity_remove = fields.Boolean(
        string="Allow Remove Activity",
        default=True,
        help="Allow removing farm activities via this CR type.",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # LAND PARCEL OPERATIONS CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    allow_parcel_add = fields.Boolean(
        string="Allow Add Land Parcel",
        default=True,
        help="Allow adding new land parcels via this CR type.",
    )
    allow_parcel_update = fields.Boolean(
        string="Allow Edit Land Parcel",
        default=True,
        help="Allow editing existing land parcels via this CR type.",
    )
    allow_parcel_remove = fields.Boolean(
        string="Allow Remove Land Parcel",
        default=True,
        help="Allow removing land parcels via this CR type.",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ASSET OPERATIONS CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    allow_asset_add = fields.Boolean(
        string="Allow Add Asset",
        default=True,
        help="Allow adding new assets/machinery via this CR type.",
    )
    allow_asset_update = fields.Boolean(
        string="Allow Edit Asset",
        default=True,
        help="Allow editing existing assets/machinery via this CR type.",
    )
    allow_asset_remove = fields.Boolean(
        string="Allow Remove Asset",
        default=True,
        help="Allow removing assets/machinery via this CR type.",
    )
