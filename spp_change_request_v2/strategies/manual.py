from odoo import models


class SPPCRStrategyManual(models.AbstractModel):
    """Apply strategy: manual (no-op).

    Used for CR types where changes are applied manually by the user
    outside of the system, or where the CR is just for tracking/approval.
    """

    _name = "spp.cr.strategy.manual"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply Strategy: Manual"

    def apply(self, change_request):
        """Manual apply - just mark as applied without doing anything."""
        return True

    def preview(self, change_request):
        """Manual strategy has no automatic changes."""
        return {"_info": "Changes will be applied manually"}
