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

        # Check if ID type already exists for this registrant
        existing = self.env["spp.registry.id"].search(
            [
                ("partner_id", "=", registrant.id),
                ("id_type_id", "=", detail.id_type_id.id),
            ],
            limit=1,
        )
        if existing:
            raise UserError(
                _("Registrant already has an ID of type '%s'. Use 'Update' operation instead.") % detail.id_type_id.name
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
            detail.id_type_id.name,
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
        """Preview what will be changed."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        return {
            "_action": f"{detail.operation}_id",
            "registrant": change_request.registrant_id.name,
            "operation": detail.operation,
            "id_type": detail.id_type_id.name if detail.id_type_id else None,
            "id_value": detail.id_value,
            "existing_value": detail.current_id_value,
        }
