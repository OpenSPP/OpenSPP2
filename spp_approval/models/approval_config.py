from odoo import api, fields, models


class ApprovalConfig(models.Model):
    """System-wide approval configuration settings."""

    _name = "spp.approval.config"
    _description = "Approval Configuration"

    name = fields.Char(required=True, default="Default Configuration")
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    active = fields.Boolean(default=True)

    # Batch processing settings
    batch_size = fields.Integer(
        string="Batch Size",
        default=1000,
        help="Number of records to process in each batch for bulk operations",
    )
    async_threshold = fields.Integer(
        string="Async Threshold",
        default=500,
        help="Number of records above which batch operations run asynchronously",
    )

    # Notification settings
    send_digest = fields.Boolean(
        string="Send Daily Digest",
        default=True,
        help="Send daily digest of pending approvals instead of individual notifications",
    )
    digest_time = fields.Float(
        string="Digest Time",
        default=8.0,
        help="Time of day to send digest (in server timezone, 24h format)",
    )

    @api.model
    def get_config(self, company_id=None):
        """Get approval configuration for a company."""
        company_id = company_id or self.env.company.id
        config = self.search(
            [("company_id", "=", company_id), ("active", "=", True)],
            limit=1,
        )
        if not config:
            config = self.create({"company_id": company_id})
        return config
