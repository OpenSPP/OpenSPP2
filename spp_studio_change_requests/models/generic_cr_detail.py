"""Generic detail model for Studio-created change requests."""

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class GenericCRDetail(models.Model):
    """Generic detail model used as a template for Studio CR types.

    This model serves as a starting point for dynamically created
    detail models. Each Studio CR type will create its own detail
    model that inherits from spp.cr.detail.base.
    """

    _name = "spp.cr.detail.generic"
    _description = "Generic CR Detail (Studio Template)"
    _inherit = ["spp.cr.detail.base"]

    # This model is intentionally minimal - it just provides
    # the base structure. Specific fields are added dynamically
    # when a Studio CR type is activated.

    notes = fields.Text(
        string="Notes",
        help="Additional notes or comments about this change request",
    )
