from odoo import fields, models


class DCIDataSource(models.Model):
    """Add a ``vendor`` discriminator the bridge dispatcher uses to route
    requests to vendor-specific DCI client adapters.

    The DCI spec leaves several request/response shapes ambiguous (query
    types, response wrappers, consent block placement). Different
    deployments and vendors have picked different interpretations. Rather
    than fork the upstream DCIClient, sources are marked with a
    ``vendor`` value and the dispatcher's per-registry-type handlers
    (``_handler_dr``, ``_handler_sr``, etc.) consult it before delegating
    to the right adapter.

    The selection starts empty — each vendor preset module
    (``spp_dci_openg2p``, ``spp_dci_openspp_dr``, ...) extends it via
    ``selection_add`` when registering its own adapter.
    """

    _inherit = "spp.dci.data.source"

    vendor = fields.Selection(
        selection=[],
        string="Vendor Adapter",
        help=(
            "Optional vendor identifier. When set, the bridge dispatcher "
            "routes to a vendor-specific DCI client adapter instead of "
            "the generic registry-type service. Use only when a registry "
            "has known protocol-shape quirks that the standard client "
            "cannot absorb via configuration alone."
        ),
    )
