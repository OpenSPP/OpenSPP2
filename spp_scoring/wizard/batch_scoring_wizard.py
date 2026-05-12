import ast
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BatchScoringWizard(models.TransientModel):
    """Wizard for batch scoring operations."""

    _name = "spp.batch.scoring.wizard"
    _description = "Batch Scoring Wizard"

    model_id = fields.Many2one(
        comodel_name="spp.scoring.model",
        string="Scoring Model",
        required=True,
        domain="[('is_active', '=', True)]",
    )
    registrant_domain = fields.Char(
        string="Registrant Filter",
        default="[('is_registrant', '=', True)]",
        help="Domain filter for selecting registrants",
    )
    registrant_ids = fields.Many2many(
        comodel_name="res.partner",
        string="Specific Registrants",
        domain="[('is_registrant', '=', True)]",
        help="Leave empty to use domain filter",
    )
    is_fail_fast = fields.Boolean(
        string="Stop on Error",
        default=False,
        help="Stop processing if an error occurs",
    )
    max_records = fields.Integer(
        string="Maximum Records",
        default=1000,
        help="Maximum number of registrants to process (0 for no limit)",
    )

    # Results
    state = fields.Selection(
        selection=[
            ("draft", "Configuration"),
            ("done", "Completed"),
        ],
        default="draft",
    )
    result_summary = fields.Text(
        string="Result Summary",
        readonly=True,
    )
    result_count = fields.Integer(
        string="Records Processed",
        readonly=True,
    )
    error_count = fields.Integer(
        string="Errors",
        readonly=True,
    )

    def action_run_batch_scoring(self):
        """Execute batch scoring."""
        self.ensure_one()

        # Determine registrants to process
        if self.registrant_ids:
            registrants = self.registrant_ids
            # Apply max records limit for specific registrants
            if self.max_records > 0 and len(registrants) > self.max_records:
                registrants = registrants[: self.max_records]
        else:
            try:
                # Parse user-provided domain safely as a Python literal
                domain = ast.literal_eval(self.registrant_domain or "[]")
                # Validate domain is a list
                if not isinstance(domain, list):
                    raise ValueError(_("Domain must be a list"))
            except Exception as e:
                raise UserError(_("Invalid registrant domain filter: %s") % str(e)) from e

            # Use limit in search for efficiency (don't load all then slice)
            limit = self.max_records if self.max_records > 0 else None
            registrants = self.env["res.partner"].search(domain, limit=limit)

        if not registrants:
            raise UserError(_("No registrants found matching the criteria."))

        # Run batch scoring
        engine = self.env["spp.scoring.engine"]
        result = engine.batch_score(
            registrants,
            self.model_id,
            options={
                "fail_fast": self.is_fail_fast,
            },
        )

        # Update wizard with results
        summary_parts = [
            _("Batch scoring completed."),
            _("Total: %d") % result["summary"]["total"],
            _("Successful: %d") % result["summary"]["successful"],
            _("Failed: %d") % result["summary"]["failed"],
        ]

        if result["errors"]:
            summary_parts.append("")
            summary_parts.append(_("Errors:"))
            for error in result["errors"][:10]:
                summary_parts.append(f"  - {error['registrant_name']}: {error['error']}")
            if len(result["errors"]) > 10:
                summary_parts.append(_("  ... and %d more errors") % (len(result["errors"]) - 10))

        self.write(
            {
                "state": "done",
                "result_summary": "\n".join(summary_parts),
                "result_count": result["summary"]["successful"],
                "error_count": result["summary"]["failed"],
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_results(self):
        """View the scoring results created by this batch."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Batch Scoring Results"),
            "res_model": "spp.scoring.result",
            "view_mode": "list,form",
            "domain": [
                ("model_id", "=", self.model_id.id),
                ("calculation_mode", "=", "batch"),
            ],
            "context": {"default_model_id": self.model_id.id},
        }
