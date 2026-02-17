# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class HxlAreaIndicator(models.Model):
    """Aggregated indicator value per area.

    Stores the result of HXL import aggregation at the area level.
    Can be synced to spp.data.value for use in CEL expressions.
    """

    _name = "spp.hxl.area.indicator"
    _description = "HXL Area Indicator"
    _order = "area_id, variable_id, period_key"

    batch_id = fields.Many2one(
        "spp.hxl.import.batch",
        ondelete="cascade",
        index=True,
    )

    area_id = fields.Many2one(
        "spp.area",
        required=True,
        index=True,
        ondelete="cascade",
    )
    area_name = fields.Char(
        related="area_id.name",
        string="Area",
        store=True,
    )

    variable_id = fields.Many2one(
        "spp.cel.variable",
        index=True,
        ondelete="set null",
        help="CEL variable for semantic meaning and expression access",
    )
    variable_name = fields.Char(
        related="variable_id.name",
        string="Variable",
        store=True,
    )

    rule_id = fields.Many2one(
        "spp.hxl.aggregation.rule",
        ondelete="set null",
        help="Aggregation rule that generated this indicator",
    )

    period_key = fields.Char(
        index=True,
        help="Period identifier (e.g., '2024-03' for monthly data)",
    )

    incident_id = fields.Many2one(
        "spp.hazard.incident",
        index=True,
        help="Related incident/disaster event",
    )

    # ─── Values ───────────────────────────────────────
    value = fields.Float(
        string="Value",
        help="Aggregated numeric value",
    )

    value_count = fields.Integer(
        string="Record Count",
        help="Number of source records aggregated to produce this value",
    )

    # Disaggregation stored as JSON
    disaggregation_json = fields.Text(
        string="Disaggregation",
        help="JSON with disaggregated values (e.g., {'+f': 120, '+m': 130})",
    )

    # For re-export
    hxl_tag = fields.Char(
        string="HXL Tag",
        help="HXL hashtag for re-exporting this indicator",
    )

    # ─── Metadata ───────────────────────────────────────
    source_type = fields.Char(
        string="Source Type",
        default="hxl_import",
        help="How this indicator was generated",
    )

    notes = fields.Text(
        string="Notes",
        help="Additional notes or context about this indicator",
    )

    _unique_indicator = models.Constraint(
        "UNIQUE(area_id, variable_id, period_key, incident_id, batch_id)",
        "Indicator must be unique per area/variable/period/incident/batch",
    )

    @api.model
    def create(self, vals):
        """Auto-sync to data value on create."""
        indicator = super().create(vals)
        indicator.sync_to_data_value()
        return indicator

    def write(self, vals):
        """Auto-sync to data value on write."""
        res = super().write(vals)
        if any(key in vals for key in ["value", "variable_id", "area_id", "period_key"]):
            self.sync_to_data_value()
        return res

    def sync_to_data_value(self):
        """Sync indicator values to spp.data.value for CEL expression access.

        This allows area-level indicators to be used in eligibility criteria
        and other CEL expressions.
        """
        DataValue = self.env["spp.data.value"]

        for indicator in self:
            if not indicator.variable_id:
                continue

            # Prepare value JSON
            value_json = {
                "value": indicator.value,
                "count": indicator.value_count,
            }

            # Add disaggregation if present
            if indicator.disaggregation_json:
                try:
                    disagg = json.loads(indicator.disaggregation_json)
                    value_json["disaggregation"] = disagg
                except json.JSONDecodeError:
                    _logger.warning(
                        "Failed to parse disaggregation JSON for indicator %s",
                        indicator.id,
                    )

            # Upsert to data value
            DataValue.upsert_values(
                [
                    {
                        "variable_name": indicator.variable_id.name,
                        "subject_model": "spp.area",
                        "subject_id": indicator.area_id.id,
                        "period_key": indicator.period_key or "current",
                        "value_json": value_json,
                        "value_type": "number",
                        "source_type": "external",
                        "provider": "hxl_import",
                    }
                ]
            )

            _logger.debug(
                "Synced indicator %s to data value for area %s",
                indicator.id,
                indicator.area_id.name,
            )

    def action_sync_all(self):
        """Manually sync all indicators to data values."""
        self.sync_to_data_value()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sync Complete"),
                "message": _("Synced %d indicators to data values") % len(self),
                "type": "success",
                "sticky": False,
            },
        }

    def name_get(self):
        """Display indicator with area and variable context."""
        result = []
        for rec in self:
            parts = [rec.area_name or f"Area#{rec.area_id.id}"]

            if rec.variable_name:
                parts.append(rec.variable_name)

            if rec.period_key:
                parts.append(f"({rec.period_key})")

            parts.append(f"= {rec.value}")

            name = " ".join(parts)
            result.append((rec.id, name))
        return result
