"""DCI IBR Duplication Check Model."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class DCIDuplicationCheck(models.Model):
    """DCI Duplication Check.

    Stores results of duplication checks performed against Integrated
    Beneficiary Registry (IBR) systems via DCI API.
    """

    _name = "spp.dci.duplication.check"
    _description = "DCI Duplication Check"
    _order = "check_date desc, id desc"
    _rec_name = "partner_id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        required=True,
        ondelete="cascade",
        index=True,
        help="The registrant being checked for duplicates",
    )
    identifier_type = fields.Char(
        string="Identifier Type",
        required=True,
        help="Type of identifier used for the check (e.g., UIN, BRN, MRN, DRN)",
    )
    identifier_value = fields.Char(
        string="Identifier Value",
        required=True,
        help="Value of the identifier used for the check",
    )
    check_date = fields.Datetime(
        string="Check Date",
        required=True,
        default=fields.Datetime.now,
        help="Date and time when the duplication check was performed",
    )
    result = fields.Selection(
        [
            ("no_match", "No Match"),
            ("possible_match", "Possible Match"),
            ("confirmed_match", "Confirmed Match"),
        ],
        string="Result",
        required=True,
        help="Result of the duplication check",
    )
    matched_programs = fields.Text(
        string="Matched Programs",
        help="List of programs where potential duplicates were found",
    )
    raw_response = fields.Text(
        string="Raw Response",
        help="Raw JSON response from the DCI API for debugging",
    )
    state = fields.Selection(
        [
            ("ready", "Ready"),
            ("checking", "Checking"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        string="State",
        default="ready",
        required=True,
        help="State of the duplication check process",
    )
    data_source_id = fields.Many2one(
        "spp.dci.data.source",
        string="Data Source",
        help="The IBR data source that was queried",
    )
    error_message = fields.Text(
        string="Error Message",
        help="Error message if the check failed",
    )
    notes = fields.Text(
        string="Notes",
        help="Additional notes about this duplication check",
    )

    @api.constrains("result")
    def _check_result_not_empty(self):
        """Validate result is not empty."""
        for record in self:
            if not record.result:
                raise ValidationError(_("Result cannot be empty."))

    @api.constrains("identifier_type", "identifier_value")
    def _check_identifier_fields(self):
        """Validate identifier fields are not empty."""
        for record in self:
            if not record.identifier_type or not record.identifier_type.strip():
                raise ValidationError(_("Identifier type cannot be empty."))
            if not record.identifier_value or not record.identifier_value.strip():
                raise ValidationError(_("Identifier value cannot be empty."))

    def name_get(self):
        """Custom name_get to display meaningful name."""
        result = []
        for record in self:
            name = f"{record.partner_id.name} - {record.identifier_type}:{record.identifier_value}"
            if record.check_date:
                name += f" ({record.check_date.strftime('%Y-%m-%d %H:%M')})"
            result.append((record.id, name))
        return result

    def action_run_check(self):
        """Run duplication check against IBR.

        This method is typically called from the UI or as part of an
        automated workflow. It uses the IBRService to perform the actual check.
        """
        self.ensure_one()

        if self.state in ("completed", "failed"):
            _logger.warning(
                "Duplication check %s is already in state '%s', skipping re-check",
                self.id,
                self.state,
            )
            return

        try:
            # Import here to avoid circular dependency
            from ..services import IBRService

            # Mark as checking
            self.write({"state": "checking"})

            # Get IBR data source
            if not self.data_source_id:
                data_source = self.env["spp.dci.data.source"].search(
                    [("registry_type", "=", "ibr"), ("active", "=", True)],
                    limit=1,
                )
                if not data_source:
                    raise UserError(_("No active IBR data source found. Please configure an IBR data source first."))
                self.data_source_id = data_source

            # Create IBR service
            ibr_service = IBRService(self.data_source_id, self.env)

            # Perform duplication check
            duplication_result = ibr_service.check_duplication(self.partner_id)

            # Update record with results
            self.write(
                {
                    "result": ("confirmed_match" if duplication_result.get("is_duplicate") else "no_match"),
                    "matched_programs": "\n".join(duplication_result.get("matched_programs", [])),
                    "raw_response": str(duplication_result.get("raw_response", "")),
                    "state": "completed",
                }
            )

            _logger.info(
                "Duplication check %s completed successfully for partner %s",
                self.id,
                self.partner_id.id,
            )

        except UserError:
            # Re-raise configuration errors to show to user
            raise
        except Exception as e:
            error_msg = str(e)
            _logger.error(
                "Duplication check %s failed for partner %s: %s",
                self.id,
                self.partner_id.id,
                error_msg,
                exc_info=True,
            )
            self.write(
                {
                    "state": "failed",
                    "error_message": error_msg,
                }
            )

    def action_reset_to_draft(self):
        """Reset check to ready state."""
        for record in self:
            record.write(
                {
                    "state": "ready",
                    "error_message": False,
                }
            )
        _logger.info("Reset %d duplication check(s) to ready state", len(self))
