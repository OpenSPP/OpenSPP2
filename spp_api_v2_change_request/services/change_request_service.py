# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Change Request API operations."""

import logging
from typing import Any

from odoo.api import Environment
from odoo.exceptions import UserError, ValidationError

from ..schemas.change_request import (
    ChangeRequestCreate,
)

_logger = logging.getLogger(__name__)


class ChangeRequestService:
    """Service for Change Request resource CRUD and mapping."""

    def __init__(self, env: Environment):
        ctx = dict(env.context, mail_create_nolog=True, tracking_disable=True)
        self.env = env(context=ctx)

    def find_by_reference(self, reference: str):
        """
        Find change request by reference (e.g., CR/2024/00001).

        Args:
            reference: CR reference number

        Returns:
            spp.change.request record or empty recordset
        """
        return self.env["spp.change.request"].search(
            [("name", "=", reference)],
            limit=1,
        )

    def find_registrant_by_identifier(self, system: str, value: str):
        """
        Find registrant by external identifier.

        Args:
            system: Namespace URI
            value: Identifier value

        Returns:
            res.partner record or empty recordset
        """
        reg_id = self.env["spp.registry.id"].search(
            [
                ("namespace_uri", "=", system),
                ("value", "=", value),
            ],
            limit=1,
        )
        if reg_id and reg_id.partner_id:
            return reg_id.partner_id
        return self.env["res.partner"]

    def get_primary_identifier(self, partner):
        """Get primary external identifier for a partner."""
        if partner.reg_ids:
            reg_id = partner.reg_ids[0]
            return {
                "system": reg_id.namespace_uri or "",
                "value": reg_id.value or "",
                "display": partner.name,
            }
        return None

    def to_api_schema(self, cr) -> dict[str, Any]:
        """
        Convert Odoo CR record to API schema.

        Args:
            cr: spp.change.request record

        Returns:
            Dictionary matching ChangeRequestResponse schema
        """
        if not cr:
            return {}

        # Build registrant reference
        registrant_ref = self.get_primary_identifier(cr.registrant_id)
        if not registrant_ref:
            _logger.warning("CR ID %s registrant has no external identifier", cr.id)
            registrant_ref = {
                "system": "urn:openspp:internal",
                "value": f"partner-{cr.registrant_id.id}",
                "display": cr.registrant_id.name,
            }

        # Build response
        response = {
            "type": "ChangeRequest",
            "reference": cr.name,
            "requestType": {
                "code": cr.request_type_code,
                "name": cr.request_type_id.name,
            },
            "status": cr.display_state,
            "registrant": registrant_ref,
            "isApplied": cr.is_applied,
        }

        # Applicant
        if cr.applicant_id:
            applicant_ref = self.get_primary_identifier(cr.applicant_id)
            if applicant_ref:
                response["applicant"] = applicant_ref
        if cr.applicant_phone:
            response["applicantPhone"] = cr.applicant_phone

        # Detail data
        detail = cr.get_detail()
        if detail:
            response["detail"] = self._serialize_detail(detail)

        # Dates
        if cr.applied_date:
            response["appliedDate"] = cr.applied_date.isoformat()
        if cr.apply_error:
            response["applyError"] = cr.apply_error
        if cr.submitted_date:
            response["submittedDate"] = cr.submitted_date.isoformat()
        if cr.approved_date:
            response["approvedDate"] = cr.approved_date.isoformat()
        if cr.rejected_date:
            response["rejectedDate"] = cr.rejected_date.isoformat()
        if cr.rejection_reason:
            response["rejectionReason"] = cr.rejection_reason
        if hasattr(cr, "revision_notes") and cr.revision_notes:
            response["revisionNotes"] = cr.revision_notes

        # Description and notes
        if cr.description:
            response["description"] = cr.description
        if cr.notes:
            response["notes"] = cr.notes

        # Metadata
        version_id = str(int(cr.write_date.timestamp() * 1000000)) if cr.write_date else "1"
        response["meta"] = {
            "versionId": version_id,
            "lastUpdated": cr.write_date.isoformat() if cr.write_date else None,
            "source": cr.source_reference or None,
        }

        return response

    def _serialize_detail(self, detail) -> dict[str, Any]:
        """
        Serialize detail record to dictionary.

        Only includes fields defined on the detail model,
        excludes internal Odoo fields.
        """
        result = {}

        # Get fields from the model
        model_fields = detail._fields

        # Skip internal, computed, and mail.thread fields
        skip_fields = {
            "id",
            "create_uid",
            "create_date",
            "write_uid",
            "write_date",
            "__last_update",
            "display_name",
            "change_request_id",
            # Convenience computed fields from base
            "registrant_id",
            "approval_state",
            "is_applied",
            # mail.thread fields
            "message_ids",
            "message_follower_ids",
            "message_partner_ids",
            "message_is_follower",
            "has_message",
            "message_needaction",
            "message_needaction_counter",
            "message_has_error",
            "message_has_error_counter",
            "message_attachment_count",
            "message_has_sms_error",
            "message_main_attachment_id",
            "website_message_ids",
        }

        for field_name, field in model_fields.items():
            if field_name.startswith("_") or field_name in skip_fields:
                continue

            value = getattr(detail, field_name)

            if field.type == "many2one":
                # For Many2one, return the external identifier or code
                if value:
                    if hasattr(value, "namespace_uri") and hasattr(value, "code"):
                        # It's a vocabulary code
                        result[field_name] = {
                            "system": value.namespace_uri,
                            "code": value.code,
                            "display": value.display or value.name,
                        }
                    elif hasattr(value, "reg_ids") and value.reg_ids:
                        # It's a partner with identifiers
                        reg_id = value.reg_ids[0]
                        result[field_name] = {
                            "system": reg_id.namespace_uri,
                            "value": reg_id.value,
                            "display": value.name,
                        }
                    else:
                        result[field_name] = value.name if hasattr(value, "name") else str(value.id)
            elif field.type == "many2many":
                # Skip many2many for now
                continue
            elif field.type == "one2many":
                # Skip one2many for now
                continue
            elif field.type == "date":
                result[field_name] = value.isoformat() if value else None
            elif field.type == "datetime":
                result[field_name] = value.isoformat() if value else None
            elif field.type == "binary":
                # Skip binary fields in API
                continue
            else:
                result[field_name] = value

        return result

    def create(self, schema: ChangeRequestCreate, source: str) -> Any:
        """
        Create new change request.

        Args:
            schema: ChangeRequestCreate schema
            source: Source system URI

        Returns:
            Created spp.change.request record
        """
        # Find request type
        cr_type = self.env["spp.change.request.type"].search(
            [("code", "=", schema.request_type.code)],
            limit=1,
        )
        if not cr_type:
            raise ValidationError(f"Unknown request type: {schema.request_type.code}")

        # Find registrant
        registrant = self.find_registrant_by_identifier(
            schema.registrant.system,
            schema.registrant.value,
        )
        if not registrant:
            raise ValidationError(f"Registrant not found: {schema.registrant.system}|{schema.registrant.value}")

        # Build vals
        vals = {
            "request_type_id": cr_type.id,
            "registrant_id": registrant.id,
            "source_type": "api",
            "source_reference": source,
        }

        # Applicant
        if schema.applicant:
            applicant = self.find_registrant_by_identifier(
                schema.applicant.system,
                schema.applicant.value,
            )
            if applicant:
                vals["applicant_id"] = applicant.id
        if schema.applicant_phone:
            vals["applicant_phone"] = schema.applicant_phone

        # Description and notes
        if schema.description:
            vals["description"] = schema.description
        if schema.notes:
            vals["notes"] = schema.notes

        # Create CR (this also creates the detail record)
        cr = self.env["spp.change.request"].create(vals)

        # Update detail with provided data
        if schema.detail:
            self.update_detail(cr, schema.detail)

        _logger.info(
            "Created change request %s via API from %s",
            cr.name,
            source,
        )
        return cr

    def update_detail(self, cr, detail_data: dict[str, Any]):
        """
        Update detail record with provided data.

        Args:
            cr: Change request record
            detail_data: Dictionary of field values
        """
        detail = cr.get_detail()
        if not detail:
            raise ValidationError("Change request has no detail record")

        # Convert API data to Odoo vals
        vals = self._deserialize_detail(detail, detail_data)
        if vals:
            detail.write(vals)

    def _deserialize_detail(self, detail, data: dict[str, Any]) -> dict[str, Any]:
        """
        Convert API detail data to Odoo vals.

        Handles Many2one lookups by namespace_uri/code.
        """
        vals = {}
        model_fields = detail._fields

        for field_name, value in data.items():
            if field_name not in model_fields:
                _logger.warning(
                    "Unknown field %s for detail model %s",
                    field_name,
                    detail._name,
                )
                continue

            field = model_fields[field_name]

            if field.type == "many2one" and isinstance(value, dict):
                # Lookup by namespace_uri/code or system/value
                if "system" in value and "code" in value:
                    # Vocabulary code
                    code_rec = self.env["spp.vocabulary.code"].search(
                        [
                            ("namespace_uri", "=", value["system"]),
                            ("code", "=", value["code"]),
                        ],
                        limit=1,
                    )
                    if code_rec:
                        vals[field_name] = code_rec.id
                elif "system" in value and "value" in value:
                    # Partner identifier
                    partner = self.find_registrant_by_identifier(
                        value["system"],
                        value["value"],
                    )
                    if partner:
                        vals[field_name] = partner.id
            elif field.type == "date" and isinstance(value, str):
                from datetime import date as dt_date

                vals[field_name] = dt_date.fromisoformat(value)
            elif field.type == "datetime" and isinstance(value, str):
                from datetime import datetime as dt_datetime

                vals[field_name] = dt_datetime.fromisoformat(value)
            else:
                vals[field_name] = value

        return vals

    def search(self, params: dict[str, Any]) -> tuple[list, int]:
        """
        Search change requests.

        Args:
            params: Search parameters

        Returns:
            Tuple of (records, total_count)
        """
        domain = []

        # Registrant filter
        if params.get("registrant"):
            if "|" in params["registrant"]:
                system, value = params["registrant"].split("|", 1)
                registrant = self.find_registrant_by_identifier(system, value)
                if registrant:
                    domain.append(("registrant_id", "=", registrant.id))
                else:
                    # No matching registrant - return empty
                    return [], 0

        # Type filter
        if params.get("request_type"):
            domain.append(("request_type_code", "=", params["request_type"]))

        # Status filter
        if params.get("status"):
            domain.append(("display_state", "=", params["status"]))

        # Date filters
        if params.get("created_after"):
            domain.append(("create_date", ">=", params["created_after"]))
        if params.get("created_before"):
            domain.append(("create_date", "<=", params["created_before"]))

        # Pagination
        offset = params.get("_offset", 0)
        limit = params.get("_count", 20)

        # Get total
        total = self.env["spp.change.request"].search_count(domain)

        # Get records
        records = self.env["spp.change.request"].search(
            domain,
            offset=offset,
            limit=limit,
            order="create_date desc",
        )

        return records, total

    def submit(self, cr):
        """Submit change request for approval."""
        if cr.approval_state != "draft":
            raise UserError("Only draft change requests can be submitted")
        cr.action_submit_for_approval()

    def approve(self, cr, comment: str = None):
        """Approve change request."""
        if cr.approval_state != "pending":
            raise UserError("Only pending change requests can be approved")
        cr.action_approve(comment=comment)

    def reject(self, cr, reason: str):
        """Reject change request."""
        if cr.approval_state != "pending":
            raise UserError("Only pending change requests can be rejected")
        if not reason:
            raise ValidationError("Rejection reason is required")
        cr._do_reject(reason)

    def request_revision(self, cr, notes: str):
        """Request revision on change request."""
        if cr.approval_state != "pending":
            raise UserError("Only pending change requests can have revision requested")
        if not notes:
            raise ValidationError("Revision notes are required")
        cr._do_request_revision(notes)

    def apply(self, cr):
        """Apply approved change request."""
        if cr.approval_state != "approved":
            raise UserError("Only approved change requests can be applied")
        if cr.is_applied:
            raise UserError("Change request has already been applied")
        cr.action_apply()

    def reset_to_draft(self, cr):
        """Reset rejected/revision CR to draft."""
        if cr.approval_state not in ("rejected", "revision"):
            raise UserError("Only rejected or revision-requested change requests can be reset to draft")
        cr.action_reset_to_draft()
