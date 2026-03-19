# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CR Apply Strategy: Manage Farm Asset (Add/Update/Remove)."""

import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyManageFarmAsset(models.AbstractModel):
    """Custom apply strategy for Manage Farm Asset CR type."""

    _name = "spp.cr.apply.manage_farm_asset"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Manage Farm Asset"

    def _get_record(self, detail):
        """Get the existing asset/machinery record from the detail."""
        if detail.asset_category == "asset":
            return detail.farm_asset_id
        return detail.farm_machinery_id

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

    def _apply_add(self, change_request, detail):
        """Create a new farm asset record."""
        farm = change_request.registrant_id
        if not farm.is_group:
            raise UserError(_("Registrant must be a group (farm)."))

        vals = {"quantity": detail.quantity}

        if detail.asset_category == "asset":
            vals["asset_farm_id"] = farm.id
            if detail.asset_type_id:
                vals["asset_type_id"] = detail.asset_type_id.id
            if detail.technology_used:
                vals["technology_used"] = detail.technology_used
        else:
            vals["machinery_farm_id"] = farm.id
            if detail.machinery_type_id:
                vals["machinery_type_id"] = detail.machinery_type_id.id
            if detail.machine_working_status:
                vals["machine_working_status"] = detail.machine_working_status

        _logger.info(
            "Creating farm %s from CR %s for farm_id=%s",
            detail.asset_category,
            change_request.name,
            farm.id,
        )

        self.env["spp.farm.asset"].create(vals)
        return True

    def _apply_update(self, change_request, detail):
        """Update an existing farm asset record."""
        record = self._get_record(detail)
        if not record:
            raise UserError(_("Asset/machinery to update is required."))

        update_vals = {}

        if detail.asset_category == "asset":
            if detail.asset_type_id:
                update_vals["asset_type_id"] = detail.asset_type_id.id
            if detail.technology_used:
                update_vals["technology_used"] = detail.technology_used
        else:
            if detail.machinery_type_id:
                update_vals["machinery_type_id"] = detail.machinery_type_id.id
            if detail.machine_working_status:
                update_vals["machine_working_status"] = detail.machine_working_status

        if detail.quantity:
            update_vals["quantity"] = detail.quantity

        if not update_vals:
            _logger.info(
                "No changes to apply for %s id=%s via CR %s",
                detail.asset_category,
                record.id,
                change_request.name,
            )
            return True

        _logger.info(
            "Updating farm %s id=%s from CR %s with fields: %s",
            detail.asset_category,
            record.id,
            change_request.name,
            list(update_vals.keys()),
        )

        record.write(update_vals)
        return True

    def _apply_remove(self, change_request, detail):
        """Remove (unlink) an existing farm asset record."""
        record = self._get_record(detail)
        if not record:
            raise UserError(_("Asset/machinery to remove is required."))

        _logger.info(
            "Removing farm %s id=%s via CR %s",
            detail.asset_category,
            record.id,
            change_request.name,
        )

        record.unlink()
        return True

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
        category_label = "Asset" if detail.asset_category == "asset" else "Machinery"
        result = {
            "_action": "add_farm_asset",
            "_header": f"Add Farm {category_label}",
            "Farm": change_request.registrant_id.name,
            "Category": category_label,
        }

        if detail.asset_category == "asset":
            if detail.asset_type_id:
                result["Asset Type"] = detail.asset_type_id.name
            if detail.technology_used:
                result["Technology Used"] = detail.technology_used
        else:
            if detail.machinery_type_id:
                result["Machinery Type"] = detail.machinery_type_id.name
            if detail.machine_working_status:
                result["Working Status"] = detail.machine_working_status

        if detail.quantity:
            result["Quantity"] = detail.quantity

        return result

    def _preview_update(self, detail):
        """Preview for update operation."""
        record = self._get_record(detail)
        if not record:
            return {}

        category_label = "Asset" if detail.asset_category == "asset" else "Machinery"
        result = {
            "_action": "update_farm_asset",
            "_header": f"Edit Farm {category_label}",
            "Record": record.display_name,
        }

        if detail.quantity and detail.quantity != record.quantity:
            result["Quantity"] = {"old": record.quantity, "new": detail.quantity}

        return result

    def _preview_remove(self, detail):
        """Preview for remove operation."""
        record = self._get_record(detail)
        if not record:
            return {}

        category_label = "Asset" if detail.asset_category == "asset" else "Machinery"
        return {
            "_action": "remove_farm_asset",
            "_header": f"Remove Farm {category_label}",
            "Record": record.display_name,
            "Quantity": record.quantity,
        }
