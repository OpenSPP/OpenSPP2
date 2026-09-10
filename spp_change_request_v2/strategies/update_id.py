import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyUpdateID(models.AbstractModel):
    """Custom apply strategy for Update ID Document CR type."""

    _name = "spp.cr.apply.update_id"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Update ID Document"

    def apply(self, change_request):
        """Add, update, or remove ID document."""
        registrant = change_request.registrant_id
        if not registrant:
            raise UserError(_("No registrant found."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        operation = detail.operation

        if operation == "add":
            return self._apply_add(registrant, detail, change_request)
        elif operation == "update":
            return self._apply_update(registrant, detail, change_request)
        elif operation == "remove":
            return self._apply_remove(registrant, detail, change_request)
        else:
            raise UserError(_("Invalid operation: %s") % operation)

    def _apply_add(self, registrant, detail, change_request):
        """Add a new ID document."""
        if not detail.id_type_id:
            raise UserError(_("ID type is required."))
        if not detail.id_value:
            raise UserError(_("ID value is required."))

        # Check if a *live* ID of this type already exists for this registrant.
        # Removing an ID through a change request marks it Invalid rather than
        # deleting it, so an unscoped search counted those dead rows and left
        # the type permanently unusable — the same defect as the uniqueness
        # index on spp.registry.id (OP#1136).
        existing = self.env["spp.registry.id"].search(
            [
                ("partner_id", "=", registrant.id),
                ("id_type_id", "=", detail.id_type_id.id),
                ("status", "!=", "invalid"),
            ],
            limit=1,
        )
        if existing:
            raise UserError(
                _("Registrant already has an ID of type '%s'. Use 'Update' operation instead.")
                % detail.id_type_id.display_name
            )

        # Create new ID record
        self.env["spp.registry.id"].create(
            {
                "partner_id": registrant.id,
                "id_type_id": detail.id_type_id.id,
                "value": detail.id_value,
                "expiry_date": detail.expiry_date,
                "description": detail.description,
                "status": "valid",
            }
        )

        _logger.info(
            "Added ID type=%s for registrant partner_id=%s via CR %s",
            detail.id_type_id.display_name,
            registrant.id,
            change_request.name,
        )
        return True

    def _apply_update(self, registrant, detail, change_request):
        """Update an existing ID document."""
        if not detail.existing_id_record_id:
            raise UserError(_("No existing ID record selected for update."))

        id_record = detail.existing_id_record_id
        update_vals = {}

        if detail.id_value:
            update_vals["value"] = detail.id_value
        if detail.expiry_date:
            update_vals["expiry_date"] = detail.expiry_date
        if detail.description:
            update_vals["description"] = detail.description

        if update_vals:
            id_record.write(update_vals)

        _logger.info(
            "Updated ID record_id=%s for registrant partner_id=%s via CR %s",
            id_record.id,
            registrant.id,
            change_request.name,
        )
        return True

    def _apply_remove(self, registrant, detail, change_request):
        """Remove/invalidate an ID document."""
        if not detail.existing_id_record_id:
            raise UserError(_("No existing ID record selected for removal."))

        id_record = detail.existing_id_record_id

        # Mark as invalid rather than deleting for audit purposes
        id_record.write({"status": "invalid"})

        _logger.info(
            "Invalidated ID record_id=%s for registrant partner_id=%s via CR %s",
            id_record.id,
            registrant.id,
            change_request.name,
        )
        return True

    def preview(self, change_request):
        """Preview what will be changed, with different layouts per operation."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        operation = detail.operation

        if operation == "update":
            # Show old/new comparison for edit operations
            result = {
                "_action": "update_id",
                "_header": "Edit Existing ID",
            }
            if detail.existing_id_record_id:
                existing = detail.existing_id_record_id
                result["ID Type"] = {
                    "old": existing.id_type_id.display_name if existing.id_type_id else None,
                    "new": detail.id_type_id.display_name if detail.id_type_id else None,
                }
                result["ID Number/Value"] = {
                    "old": existing.value or None,
                    "new": detail.id_value or None,
                }
                result["Expiry Date"] = {
                    "old": str(existing.expiry_date) if existing.expiry_date else None,
                    "new": str(detail.expiry_date) if detail.expiry_date else None,
                }
            return result

        if operation == "add":
            return {
                "_action": "add_id",
                "_header": "Add New ID",
                "ID Type": detail.id_type_id.display_name if detail.id_type_id else None,
                "ID Number/Value": detail.id_value or None,
                "Expiry Date": str(detail.expiry_date) if detail.expiry_date else None,
            }

        if operation == "remove":
            result = {
                "_action": "remove_id",
                "_header": "Remove Existing ID",
            }
            if detail.existing_id_record_id:
                existing = detail.existing_id_record_id
                result["ID Type"] = existing.id_type_id.display_name if existing.id_type_id else None
                result["ID Number/Value"] = existing.value or None
            return result

        return {}
