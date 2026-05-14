from odoo import fields, models


class DCIDataSource(models.Model):
    """Add a vendor discriminator so the bridge can route to vendor-specific
    DCI clients when a deployment's source has known quirks.

    The DCI spec leaves several request/response shapes ambiguous (notably
    the `idtype-value` query and the `data.reg_records[]` wrapper). Vendors
    have picked different interpretations. Rather than fork the upstream
    DCIClient, we mark sources with a `vendor` and let the dispatcher pick
    the right adapter.

    Selection values:
        - openg2p: OpenG2P Partner Registry / Farmer Registry shape. Query
          uses nested {id_type, id_value} payload; response wraps records
          in data.reg_records[].
    """

    _inherit = "spp.dci.data.source"

    vendor = fields.Selection(
        selection=[
            ("openg2p", "OpenG2P"),
        ],
        string="Vendor Adapter",
        help=(
            "Optional vendor identifier. When set, the bridge dispatcher "
            "routes to a vendor-specific DCI client adapter instead of the "
            "generic registry-type service. Use only when a registry has "
            "known protocol-shape quirks that the standard client cannot "
            "absorb via configuration alone."
        ),
    )
