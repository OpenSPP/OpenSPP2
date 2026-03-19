# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Integration between spp_scoring and the Unified Variable System.

This module provides:
1. Auto-creation of scoring variables when scoring models are activated
2. Storage of scoring results in spp.data.value for CEL access
3. Helper methods to manage score caching
4. Extends spp.cel.variable with scoring_model_id field

Variables created for scoring models allow scores to be accessed in CEL
expressions like: r.pmt_score >= 50
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class CelVariableScoringExtension(models.Model):
    """Extend spp.cel.variable with scoring model link.

    This adds the scoring_model_id field that allows CEL variables
    to reference the scoring model they represent.
    """

    _inherit = "spp.cel.variable"

    scoring_model_id = fields.Many2one(
        comodel_name="spp.scoring.model",
        string="Scoring Model",
        help="For scoring type: the scoring model that computes this variable",
        ondelete="set null",
    )


class ScoringModelDataIntegration(models.Model):
    """Extend spp.scoring.model with unified variable system integration."""

    _inherit = "spp.scoring.model"

    # Link to the auto-created variable
    variable_id = fields.Many2one(
        comodel_name="spp.cel.variable",
        string="Score Variable",
        ondelete="set null",
        help="Auto-created variable that exposes this score in CEL expressions",
    )
    auto_create_variable = fields.Boolean(
        string="Create Score Variable",
        default=True,
        help="Automatically create a CEL variable for this scoring model",
    )
    cache_scores = fields.Boolean(
        string="Cache Scores",
        default=True,
        help="Store scoring results in the unified data cache for CEL access",
    )

    def write(self, vals):
        """Override write to create variable when model is activated."""
        result = super().write(vals)

        # Check if model was just activated
        if vals.get("is_active") is True:
            for model in self.filtered(lambda m: m.auto_create_variable and not m.variable_id):
                model._create_score_variable()

        return result

    def _create_score_variable(self):
        """Create a CEL variable for this scoring model.

        The variable allows the score to be accessed in CEL expressions
        like: r.pmt_score >= 50
        """
        self.ensure_one()

        Variable = self.env["spp.cel.variable"]
        Category = self.env["spp.cel.variable.category"]

        # Get or create the scoring category
        category = Category.search([("name", "=", "Scoring")], limit=1)
        if not category:
            category = Category.create(
                {
                    "name": "Scoring",
                    "code": "scoring",
                }
            )

        # Build variable name from model code
        var_name = f"{self.code.lower()}_score"
        cel_accessor = var_name

        # Check if variable already exists
        existing = Variable.search([("name", "=", var_name)], limit=1)
        if existing:
            self.variable_id = existing
            _logger.info("Score variable '%s' already exists for model '%s'", var_name, self.code)
            return

        # Create the variable
        variable = Variable.create(
            {
                "name": var_name,
                "cel_accessor": cel_accessor,
                "source_type": "scoring",
                "scoring_model_id": self.id,
                "value_type": "number",
                "category_id": category.id,
                "applies_to": "both",
                "state": "active",
                "active": True,
                "is_system": True,  # System-generated
                # Caching configuration
                "cache_strategy": "manual",  # Refreshed on scoring run
                "period_granularity": "current",  # Always latest score
            }
        )

        self.variable_id = variable

        _logger.info("Created score variable '%s' for model '%s'", var_name, self.code)

    def action_create_variable(self):
        """Manual action to create/recreate the score variable."""
        for model in self:
            model._create_score_variable()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Variable Created"),
                "message": _("Score variable has been created."),
                "type": "success",
            },
        }


class ScoringEngineDataIntegration(models.AbstractModel):
    """Extend scoring engine to store results in the data cache."""

    _inherit = "spp.scoring.engine"

    @api.model
    def calculate_score(self, registrant, scoring_model, mode="manual"):
        """Override to also store score in data cache."""
        # Call original method
        result = super().calculate_score(registrant, scoring_model, mode)

        # Store in unified cache if enabled
        if scoring_model.cache_scores:
            self._store_score_in_cache(result, registrant, scoring_model)

        return result

    def _store_score_in_cache(self, result, registrant, scoring_model):
        """Store the scoring result in spp.data.value.

        Args:
            result: spp.scoring.result record
            registrant: res.partner record
            scoring_model: spp.scoring.model record
        """
        try:
            DataValue = self.env["spp.data.value"]

            # Get the variable name
            if scoring_model.variable_id:
                var_name = scoring_model.variable_id.name
            else:
                var_name = f"{scoring_model.code.lower()}_score"

            # Store the score
            DataValue.sudo().upsert_values(  # nosemgrep
                [
                    {
                        "variable_name": var_name,
                        "subject_model": "res.partner",
                        "subject_id": registrant.id,
                        "period_key": "current",  # Always current for scoring
                        "value_json": {
                            "value": result.score,
                            "classification_code": result.classification_code,
                            "classification_label": result.classification_label,
                            "calculation_date": fields.Datetime.now().isoformat(),
                            "model_version": scoring_model.version,
                        },
                        "value_type": "number",
                        "source_type": "scoring",
                        "ttl_seconds": None,  # Manual refresh only
                    }
                ]
            )

            _logger.debug(
                "Stored score %.2f for %s in data cache (variable: %s)", result.score, registrant.id, var_name
            )

        except Exception as e:
            # Don't fail scoring if cache storage fails
            _logger.warning("Failed to store score in data cache: %s", str(e))
