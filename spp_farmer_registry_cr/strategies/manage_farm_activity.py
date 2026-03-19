# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CR Apply Strategy: Manage Farm Activity (Add/Update/Remove)."""

import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyManageFarmActivity(models.AbstractModel):
    """Custom apply strategy for Manage Farm Activity CR type.

    Dispatches to add, update, or remove based on the operation field.
    """

    _name = "spp.cr.apply.manage_farm_activity"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Manage Farm Activity"

    def apply(self, change_request):
        """Route to the correct operation handler."""
        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        operation = detail.operation
        if operation == "add":
            return self._apply_add(change_request, detail)
        elif operation == "update":
            return self._apply_update(change_request, detail)
        elif operation == "remove":
            return self._apply_remove(change_request, detail)
        else:
            raise UserError(_("Unknown operation: %s") % operation)

    # ══════════════════════════════════════════════════════════════════════════
    # ADD
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_add(self, change_request, detail):
        """Create a new farm activity record."""
        farm = change_request.registrant_id
        if not farm.is_group:
            raise UserError(_("Registrant must be a group (farm)."))

        if not detail.activity_type:
            raise UserError(_("Activity type is required."))

        activity_vals = {
            "activity_type": detail.activity_type,
            "species_id": detail.species_id.id if detail.species_id else False,
            "purpose_id": detail.purpose_id.id if detail.purpose_id else False,
            "quantity": detail.quantity,
            "quantity_unit": detail.quantity_unit,
            "area_planted": detail.area_planted,
            "expected_yield": detail.expected_yield,
            "season_id": detail.season_id.id if detail.season_id else False,
            "land_id": detail.land_id.id if detail.land_id else False,
        }

        if detail.activity_type == "crop" and detail.cultivation_method_id:
            activity_vals["cultivation_method_id"] = detail.cultivation_method_id.id

        # Link to farm based on activity type
        farm_field_map = {
            "crop": "crop_farm_id",
            "livestock": "livestock_farm_id",
            "aquaculture": "aquaculture_farm_id",
        }
        farm_field = farm_field_map.get(detail.activity_type)
        if farm_field:
            activity_vals[farm_field] = farm.id

        _logger.info(
            "Creating farm activity from CR %s for farm_id=%s, type=%s",
            change_request.name,
            farm.id,
            detail.activity_type,
        )

        self.env["spp.farm.activity"].create(activity_vals)
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # UPDATE
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_update(self, change_request, detail):
        """Update an existing farm activity record."""
        if not detail.activity_id:
            raise UserError(_("Activity to update is required."))

        activity = detail.activity_id
        update_vals = {}

        if detail.species_id:
            update_vals["species_id"] = detail.species_id.id
        if detail.purpose_id:
            update_vals["purpose_id"] = detail.purpose_id.id
        if detail.cultivation_method_id:
            update_vals["cultivation_method_id"] = detail.cultivation_method_id.id
        if detail.quantity:
            update_vals["quantity"] = detail.quantity
        if detail.quantity_unit:
            update_vals["quantity_unit"] = detail.quantity_unit
        if detail.area_planted:
            update_vals["area_planted"] = detail.area_planted
        if detail.expected_yield:
            update_vals["expected_yield"] = detail.expected_yield
        if detail.actual_yield:
            update_vals["actual_yield"] = detail.actual_yield

        if not update_vals:
            _logger.info(
                "No changes to apply for activity id=%s via CR %s",
                activity.id,
                change_request.name,
            )
            return True

        _logger.info(
            "Updating farm activity id=%s from CR %s with fields: %s",
            activity.id,
            change_request.name,
            list(update_vals.keys()),
        )

        activity.write(update_vals)
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # REMOVE
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_remove(self, change_request, detail):
        """Remove (unlink) an existing farm activity record."""
        if not detail.activity_id:
            raise UserError(_("Activity to remove is required."))

        activity = detail.activity_id
        _logger.info(
            "Removing farm activity id=%s (%s) via CR %s",
            activity.id,
            activity.display_name,
            change_request.name,
        )

        activity.unlink()
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # PREVIEW
    # ══════════════════════════════════════════════════════════════════════════

    def preview(self, change_request):
        """Preview what will happen based on operation."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        operation = detail.operation
        if operation == "add":
            return self._preview_add(detail, change_request)
        elif operation == "update":
            return self._preview_update(detail)
        elif operation == "remove":
            return self._preview_remove(detail)
        return {}

    def _preview_add(self, detail, change_request):
        """Preview for add operation."""
        type_labels = dict(detail._fields["activity_type"].selection)
        result = {
            "_action": "add_farm_activity",
            "_header": "Add Farm Activity",
            "Farm": change_request.registrant_id.name,
            "Activity Type": type_labels.get(detail.activity_type, detail.activity_type),
        }

        if detail.species_id:
            result["Species"] = detail.species_id.display_name
        if detail.purpose_id:
            result["Purpose"] = detail.purpose_id.display_name
        if detail.cultivation_method_id:
            result["Cultivation Method"] = detail.cultivation_method_id.display_name
        if detail.quantity:
            result["Quantity"] = detail.quantity
        if detail.quantity_unit:
            result["Unit"] = detail.quantity_unit
        if detail.area_planted:
            result["Area Planted"] = detail.area_planted
        if detail.expected_yield:
            result["Expected Yield"] = detail.expected_yield
        if detail.season_id:
            result["Season"] = detail.season_id.name
        if detail.land_id:
            result["Land Parcel"] = detail.land_id.display_name

        return result

    def _preview_update(self, detail):
        """Preview for update operation."""
        if not detail.activity_id:
            return {}

        activity = detail.activity_id
        result = {
            "_action": "update_farm_activity",
            "_header": "Edit Farm Activity",
            "Activity": activity.display_name,
        }

        if detail.species_id and detail.species_id != activity.species_id:
            result["Species"] = {
                "old": activity.species_id.display_name if activity.species_id else None,
                "new": detail.species_id.display_name,
            }
        if detail.purpose_id and detail.purpose_id != activity.purpose_id:
            result["Purpose"] = {
                "old": activity.purpose_id.display_name if activity.purpose_id else None,
                "new": detail.purpose_id.display_name,
            }
        if detail.cultivation_method_id and detail.cultivation_method_id != activity.cultivation_method_id:
            result["Cultivation Method"] = {
                "old": (activity.cultivation_method_id.display_name if activity.cultivation_method_id else None),
                "new": detail.cultivation_method_id.display_name,
            }
        if detail.quantity and detail.quantity != activity.quantity:
            result["Quantity"] = {"old": activity.quantity, "new": detail.quantity}
        if detail.quantity_unit and detail.quantity_unit != activity.quantity_unit:
            result["Unit"] = {"old": activity.quantity_unit or None, "new": detail.quantity_unit}
        if detail.area_planted and detail.area_planted != activity.area_planted:
            result["Area Planted"] = {"old": activity.area_planted, "new": detail.area_planted}
        if detail.expected_yield and detail.expected_yield != activity.expected_yield:
            result["Expected Yield"] = {"old": activity.expected_yield, "new": detail.expected_yield}
        if detail.actual_yield and detail.actual_yield != activity.actual_yield:
            result["Actual Yield"] = {"old": activity.actual_yield, "new": detail.actual_yield}

        return result

    def _preview_remove(self, detail):
        """Preview for remove operation."""
        if not detail.activity_id:
            return {}

        activity = detail.activity_id
        type_labels = dict(detail._fields["activity_type"].selection)
        return {
            "_action": "remove_farm_activity",
            "_header": "Remove Farm Activity",
            "Activity": activity.display_name,
            "Activity Type": type_labels.get(activity.activity_type, activity.activity_type),
            "Species": activity.species_id.display_name if activity.species_id else None,
        }
