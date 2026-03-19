# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CR Apply Strategy: Manage Land Parcel (Add/Update/Remove)."""

import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyManageLandParcel(models.AbstractModel):
    """Custom apply strategy for Manage Land Parcel CR type."""

    _name = "spp.cr.apply.manage_land_parcel"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Manage Land Parcel"

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
        """Create a new land parcel record."""
        farm = change_request.registrant_id
        if not farm.is_group:
            raise UserError(_("Registrant must be a group (farm)."))

        parcel_vals = {
            "land_farm_id": farm.id,
            "land_name": detail.land_name,
            "land_acreage": detail.land_acreage,
        }

        if detail.land_use_id:
            parcel_vals["land_use_id"] = detail.land_use_id.id
        if detail.owner_id:
            parcel_vals["owner_id"] = detail.owner_id.id
        if detail.lessee_id:
            parcel_vals["lessee_id"] = detail.lessee_id.id
        if detail.lease_start:
            parcel_vals["lease_start"] = detail.lease_start
        if detail.lease_end:
            parcel_vals["lease_end"] = detail.lease_end

        _logger.info(
            "Creating land parcel from CR %s for farm_id=%s, name=%s",
            change_request.name,
            farm.id,
            detail.land_name,
        )

        self.env["spp.land.record"].create(parcel_vals)
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # UPDATE
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_update(self, change_request, detail):
        """Update an existing land parcel record."""
        if not detail.land_record_id:
            raise UserError(_("Land parcel to update is required."))

        parcel = detail.land_record_id
        update_vals = {}

        if detail.land_name:
            update_vals["land_name"] = detail.land_name
        if detail.land_acreage:
            update_vals["land_acreage"] = detail.land_acreage
        if detail.land_use_id:
            update_vals["land_use_id"] = detail.land_use_id.id
        if detail.owner_id:
            update_vals["owner_id"] = detail.owner_id.id
        if detail.lessee_id:
            update_vals["lessee_id"] = detail.lessee_id.id
        if detail.lease_start:
            update_vals["lease_start"] = detail.lease_start
        if detail.lease_end:
            update_vals["lease_end"] = detail.lease_end

        if not update_vals:
            _logger.info(
                "No changes to apply for land parcel id=%s via CR %s",
                parcel.id,
                change_request.name,
            )
            return True

        _logger.info(
            "Updating land parcel id=%s from CR %s with fields: %s",
            parcel.id,
            change_request.name,
            list(update_vals.keys()),
        )

        parcel.write(update_vals)
        return True

    # ══════════════════════════════════════════════════════════════════════════
    # REMOVE
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_remove(self, change_request, detail):
        """Remove (unlink) an existing land parcel record."""
        if not detail.land_record_id:
            raise UserError(_("Land parcel to remove is required."))

        parcel = detail.land_record_id
        _logger.info(
            "Removing land parcel id=%s (%s) via CR %s",
            parcel.id,
            parcel.land_name,
            change_request.name,
        )

        parcel.unlink()
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
        result = {
            "_action": "add_land_parcel",
            "_header": "Add Land Parcel",
            "Farm": change_request.registrant_id.name,
            "Parcel Name": detail.land_name,
        }

        if detail.land_acreage:
            result["Acreage"] = detail.land_acreage
        if detail.land_use_id:
            result["Land Use"] = detail.land_use_id.display_name
        if detail.owner_id:
            result["Owner"] = detail.owner_id.name
        if detail.lessee_id:
            result["Lessee"] = detail.lessee_id.name

        return result

    def _preview_update(self, detail):
        """Preview for update operation."""
        if not detail.land_record_id:
            return {}

        parcel = detail.land_record_id
        result = {
            "_action": "update_land_parcel",
            "_header": "Edit Land Parcel",
            "Parcel": parcel.land_name,
        }

        if detail.land_name and detail.land_name != parcel.land_name:
            result["Name"] = {"old": parcel.land_name, "new": detail.land_name}
        if detail.land_acreage and detail.land_acreage != parcel.land_acreage:
            result["Acreage"] = {"old": parcel.land_acreage, "new": detail.land_acreage}
        if detail.land_use_id and detail.land_use_id != parcel.land_use_id:
            result["Land Use"] = {
                "old": parcel.land_use_id.display_name if parcel.land_use_id else None,
                "new": detail.land_use_id.display_name,
            }

        return result

    def _preview_remove(self, detail):
        """Preview for remove operation."""
        if not detail.land_record_id:
            return {}

        parcel = detail.land_record_id
        return {
            "_action": "remove_land_parcel",
            "_header": "Remove Land Parcel",
            "Parcel": parcel.land_name,
            "Acreage": parcel.land_acreage,
            "Land Use": parcel.land_use_id.display_name if parcel.land_use_id else None,
        }
