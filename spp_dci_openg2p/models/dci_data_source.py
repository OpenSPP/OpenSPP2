from odoo import fields, models


class DCIDataSource(models.Model):
    """Register the OpenG2P vendor adapter on the shared vendor selection.

    The ``vendor`` field is defined by ``spp_cel_dci_bridge``; this
    preset only adds its own selection value. Once set on a data source,
    the bridge dispatcher delegates to the OpenG2P-specific service for
    that source's registry-type handler.
    """

    _inherit = "spp.dci.data.source"

    vendor = fields.Selection(
        selection_add=[("openg2p", "OpenG2P")],
        ondelete={"openg2p": "set null"},
    )
