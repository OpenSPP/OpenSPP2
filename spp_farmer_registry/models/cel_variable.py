# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CEL Variable Extension for Farmer Registry.

Extends the aggregate_target Selection to support farm-specific aggregations:
- farm_crop_activities: Aggregate over crop activities
- farm_livestock_activities: Aggregate over livestock activities
- farm_aquaculture_activities: Aggregate over aquaculture activities
- land_parcels: Aggregate over land records
"""

from odoo import fields, models


class CELVariableFarmerExtension(models.Model):
    """Extend CEL Variable with farmer-specific aggregate targets."""

    _inherit = "spp.cel.variable"

    aggregate_target = fields.Selection(
        selection_add=[
            ("farm_crop_activities", "Farm Crop Activities"),
            ("farm_livestock_activities", "Farm Livestock Activities"),
            ("farm_aquaculture_activities", "Farm Aquaculture Activities"),
            ("land_parcels", "Land Parcels"),
        ],
        ondelete={
            "farm_crop_activities": "set default",
            "farm_livestock_activities": "set default",
            "farm_aquaculture_activities": "set default",
            "land_parcels": "set default",
        },
    )

    def _build_aggregate_cel(self):
        """Override to handle farm-specific aggregate targets.

        Maps farmer targets to their One2many field names on res.partner:
        - farm_crop_activities → farm_crop_act_ids
        - farm_livestock_activities → farm_livestock_act_ids
        - farm_aquaculture_activities → farm_aquaculture_act_ids
        - land_parcels → farm_land_rec_ids
        """
        self.ensure_one()

        # Map farmer targets to field names
        target_field_map = {
            "farm_crop_activities": "farm_crop_act_ids",
            "farm_livestock_activities": "farm_livestock_act_ids",
            "farm_aquaculture_activities": "farm_aquaculture_act_ids",
            "land_parcels": "farm_land_rec_ids",
        }

        target = self.aggregate_target or "members"

        # If using farm target, use the appropriate field relation
        if target in target_field_map:
            field_name = target_field_map[target]
            agg_type = self.aggregate_type or "count"
            filter_expr = self.aggregate_filter or "true"
            field_expr = self.aggregate_field

            # Use r. prefix for record field access
            if agg_type == "count":
                return f"r.{field_name}.count({filter_expr})"
            elif agg_type == "exists":
                return f"r.{field_name}.exists({filter_expr})"
            elif agg_type in ("sum", "avg", "min", "max"):
                if field_expr:
                    # a. prefix for activity/record fields
                    field_ref = f"a.{field_expr}" if not field_expr.startswith("a.") else field_expr
                    return f"r.{field_name}.{agg_type}({field_ref}, {filter_expr})"
                return self.cel_accessor

            return self.cel_accessor

        # Fall back to parent implementation for standard targets
        return super()._build_aggregate_cel()
