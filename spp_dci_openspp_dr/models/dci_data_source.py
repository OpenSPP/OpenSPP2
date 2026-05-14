from odoo import fields, models


class DCIDataSource(models.Model):
    """Register the OpenSPP-DR vendor adapter on the shared vendor selection.

    The ``vendor`` field is defined by ``spp_cel_dci_bridge``; this
    preset only adds its own selection value. Once set on a data source,
    the bridge dispatcher delegates to ``OpenSPPDRService`` for the DR
    handler. See ADR-024 for the federated demo topology.
    """

    _inherit = "spp.dci.data.source"

    vendor = fields.Selection(
        selection_add=[("openspp", "OpenSPP")],
        ondelete={"openspp": "set null"},
    )
