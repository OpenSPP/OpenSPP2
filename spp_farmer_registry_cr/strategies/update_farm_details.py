# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CR Apply Strategy: Update Farm Details."""

import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyUpdateFarmDetails(models.AbstractModel):
    """Custom apply strategy for Update Farm Details CR type."""

    _name = "spp.cr.apply.update_farm_details"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Update Farm Details"

    def apply(self, change_request):
        """Apply farm detail changes to the registrant."""
        farm = change_request.registrant_id
        if not farm.is_group:
            raise UserError(_("Registrant must be a group (farm)."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        # Build update values
        update_vals = {}

        if detail.farm_type_id:
            update_vals["farm_type_id"] = detail.farm_type_id.id
        if detail.holder_type_id:
            update_vals["holder_type_id"] = detail.holder_type_id.id
        if detail.land_tenure_id:
            update_vals["land_tenure_id"] = detail.land_tenure_id.id
        if detail.farm_total_size:
            update_vals["farm_total_size"] = detail.farm_total_size
        if detail.farm_size_under_crops:
            update_vals["farm_size_under_crops"] = detail.farm_size_under_crops
        if detail.farm_size_under_livestock:
            update_vals["farm_size_under_livestock"] = detail.farm_size_under_livestock
        if detail.farm_size_under_aquaculture:
            update_vals["farm_size_under_aquaculture"] = detail.farm_size_under_aquaculture
        if detail.farm_size_leased_out:
            update_vals["farm_size_leased_out"] = detail.farm_size_leased_out
        if detail.farm_size_idle:
            update_vals["farm_size_idle"] = detail.farm_size_idle
        if detail.experience_years:
            update_vals["experience_years"] = detail.experience_years
        if detail.data_source_id:
            update_vals["data_source_id"] = detail.data_source_id.id
        if detail.last_field_visit:
            update_vals["last_field_visit"] = detail.last_field_visit

        if not update_vals:
            _logger.info(
                "No changes to apply for farm id=%s via CR %s",
                farm.id,
                change_request.name,
            )
            return True

        _logger.info(
            "Updating farm details for id=%s from CR %s with fields: %s",
            farm.id,
            change_request.name,
            list(update_vals.keys()),
        )

        # Write directly to the farm — _inherits delegates to spp.farm.details
        farm.write(update_vals)

        _logger.info(
            "Updated farm details for id=%s via CR %s",
            farm.id,
            change_request.name,
        )

        return True

    def preview(self, change_request):
        """Preview what will be updated."""
        detail = change_request.get_detail()
        farm = change_request.registrant_id

        if not detail or not farm:
            return {}

        result = {
            "_action": "update_farm_details",
            "_header": "Update Farm Details",
        }

        # Vocabulary fields (Many2one)
        vocab_fields = {
            "farm_type_id": "Farm Type",
            "holder_type_id": "Holder Type",
            "land_tenure_id": "Land Tenure",
        }
        for field, label in vocab_fields.items():
            detail_val = getattr(detail, field, None)
            if detail_val:
                current_val = getattr(farm, field, None)
                if detail_val != current_val:
                    result[label] = {
                        "old": current_val.display_name if current_val else None,
                        "new": detail_val.display_name,
                    }

        # Numeric fields
        numeric_fields = {
            "farm_total_size": "Total Size (hectares)",
            "farm_size_under_crops": "Under Crops",
            "farm_size_under_livestock": "Under Livestock",
            "farm_size_under_aquaculture": "Under Aquaculture",
            "farm_size_leased_out": "Leased Out",
            "farm_size_idle": "Fallow/Idle",
            "experience_years": "Experience Years",
        }
        for field, label in numeric_fields.items():
            detail_val = getattr(detail, field, None)
            if detail_val:
                current_val = getattr(farm, field, None)
                if detail_val != current_val:
                    result[label] = {"old": current_val, "new": detail_val}

        return result
