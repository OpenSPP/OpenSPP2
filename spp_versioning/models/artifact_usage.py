"""Artifact Usage model for tracking where artifacts are used."""

from odoo import _, api, fields, models


class ArtifactUsage(models.Model):
    """Track where artifacts are used (prevents orphan archiving).

    This model uses polymorphic references to track:
    - What artifact is being used (artifact_model + artifact_res_id)
    - What is using it (consumer_model + consumer_res_id)
    - What type of usage (eligibility, entitlement, etc.)

    This enables:
    - Preventing archiving of in-use artifacts
    - Understanding artifact dependencies
    - Impact analysis before changes
    """

    _name = "spp.artifact.usage"
    _description = "Artifact Usage"
    _order = "artifact_model, artifact_res_id, consumer_model"

    # === What's being used ===
    artifact_model = fields.Char(
        string="Artifact Model",
        required=True,
        index=True,
        help="Technical name of the artifact model",
    )
    artifact_res_id = fields.Many2oneReference(
        string="Artifact",
        model_field="artifact_model",
        index=True,
        help="Reference to the artifact record",
    )
    artifact_name = fields.Char(
        string="Artifact Name",
        compute="_compute_artifact_name",
        store=True,
    )

    # === What's using it ===
    consumer_model = fields.Char(
        string="Consumer Model",
        required=True,
        index=True,
        help="Technical name of the model using the artifact",
    )
    consumer_res_id = fields.Many2oneReference(
        string="Consumer",
        model_field="consumer_model",
        index=True,
        help="Reference to the record using the artifact",
    )
    consumer_name = fields.Char(
        string="Consumer Name",
        compute="_compute_consumer_name",
        store=True,
    )

    # === Usage Type ===
    usage_type = fields.Selection(
        selection=[
            ("eligibility", "Eligibility Criteria"),
            ("entitlement", "Entitlement Calculation"),
            ("compliance", "Compliance Check"),
            ("scoring", "Scoring"),
            ("validation", "Data Validation"),
            ("other", "Other"),
        ],
        string="Usage Type",
        default="other",
        help="How the artifact is being used",
    )

    @api.depends("artifact_model", "artifact_res_id")
    def _compute_artifact_name(self):
        """Compute the display name of the artifact."""
        for record in self:
            if record.artifact_model and record.artifact_res_id:
                try:
                    artifact = self.env[record.artifact_model].browse(record.artifact_res_id)
                    record.artifact_name = artifact.display_name if artifact.exists() else _("Deleted")
                except (KeyError, ValueError):
                    record.artifact_name = _("Unknown Model")
            else:
                record.artifact_name = ""

    @api.depends("consumer_model", "consumer_res_id")
    def _compute_consumer_name(self):
        """Compute the display name of the consumer."""
        for record in self:
            if record.consumer_model and record.consumer_res_id:
                try:
                    consumer = self.env[record.consumer_model].browse(record.consumer_res_id)
                    record.consumer_name = consumer.display_name if consumer.exists() else _("Deleted")
                except (KeyError, ValueError):
                    record.consumer_name = _("Unknown Model")
            else:
                record.consumer_name = ""

    # Odoo 19: Use models.Constraint instead of _sql_constraints
    _unique_usage = models.Constraint(
        "UNIQUE(artifact_model, artifact_res_id, consumer_model, consumer_res_id, usage_type)",
        "This usage relationship already exists.",
    )

    @api.model
    def register_usage(self, artifact_model, artifact_res_id, consumer_model, consumer_res_id, usage_type="other"):
        """Register a usage relationship between an artifact and consumer.

        This is a convenience method that handles duplicates gracefully.

        Args:
            artifact_model: Model name of the artifact
            artifact_res_id: Record ID of the artifact
            consumer_model: Model name of the consumer
            consumer_res_id: Record ID of the consumer
            usage_type: Type of usage (eligibility, entitlement, etc.)

        Returns:
            spp.artifact.usage: The existing or created usage record
        """
        existing = self.search(
            [
                ("artifact_model", "=", artifact_model),
                ("artifact_res_id", "=", artifact_res_id),
                ("consumer_model", "=", consumer_model),
                ("consumer_res_id", "=", consumer_res_id),
                ("usage_type", "=", usage_type),
            ],
            limit=1,
        )
        if existing:
            return existing

        return self.create(
            {
                "artifact_model": artifact_model,
                "artifact_res_id": artifact_res_id,
                "consumer_model": consumer_model,
                "consumer_res_id": consumer_res_id,
                "usage_type": usage_type,
            }
        )

    @api.model
    def unregister_usage(self, artifact_model, artifact_res_id, consumer_model, consumer_res_id, usage_type=None):
        """Remove a usage relationship.

        Args:
            artifact_model: Model name of the artifact
            artifact_res_id: Record ID of the artifact
            consumer_model: Model name of the consumer
            consumer_res_id: Record ID of the consumer
            usage_type: Optional - if provided, only removes this specific type

        Returns:
            int: Number of records deleted
        """
        domain = [
            ("artifact_model", "=", artifact_model),
            ("artifact_res_id", "=", artifact_res_id),
            ("consumer_model", "=", consumer_model),
            ("consumer_res_id", "=", consumer_res_id),
        ]
        if usage_type:
            domain.append(("usage_type", "=", usage_type))

        records = self.search(domain)
        count = len(records)
        records.unlink()
        return count

    def action_view_artifact(self):
        """View the artifact record.

        Returns:
            dict: Window action to view the artifact
        """
        self.ensure_one()
        if not self.artifact_model or not self.artifact_res_id:
            return {"type": "ir.actions.act_window_close"}

        return {
            "type": "ir.actions.act_window",
            "res_model": self.artifact_model,
            "res_id": self.artifact_res_id,
            "view_mode": "form",
        }

    def action_view_consumer(self):
        """View the consumer record.

        Returns:
            dict: Window action to view the consumer
        """
        self.ensure_one()
        if not self.consumer_model or not self.consumer_res_id:
            return {"type": "ir.actions.act_window_close"}

        return {
            "type": "ir.actions.act_window",
            "res_model": self.consumer_model,
            "res_id": self.consumer_res_id,
            "view_mode": "form",
        }
