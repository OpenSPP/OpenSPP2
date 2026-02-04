# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class CRVSEvent(models.Model):
    """CRVS Event Log.

    Records vital events (birth, death, marriage, etc.) received from
    Civil Registration and Vital Statistics (CRVS) systems via DCI API.
    """

    _name = "spp.dci.crvs.event"
    _description = "CRVS Event"
    _order = "event_date desc, id desc"

    name = fields.Char(
        string="Event Reference",
        required=True,
        readonly=True,
        default=lambda self: _("New"),
        copy=False,
    )

    event_type = fields.Selection(
        [
            ("birth", "Birth"),
            ("death", "Death"),
            ("marriage", "Marriage"),
            ("divorce", "Divorce"),
        ],
        string="Event Type",
        required=True,
        help="Type of vital event received from CRVS",
    )

    person_id = fields.Many2one(
        "res.partner",
        string="Person",
        help="Person associated with this event (if matched to registry)",
        ondelete="restrict",
    )

    identifier_type = fields.Char(
        string="Identifier Type",
        help="Type of identifier (BRN, DRN, MRN, UIN, etc.)",
    )

    identifier_value = fields.Char(
        string="Identifier Value",
        help="The actual identifier value from CRVS",
    )

    event_date = fields.Date(
        string="Event Date",
        help="Date when the vital event occurred",
    )

    raw_data = fields.Text(
        string="Raw Data (JSON)",
        help="Original JSON data received from CRVS system",
    )

    state = fields.Selection(
        [
            ("received", "Received"),
            ("processing", "Processing"),
            ("processed", "Processed"),
            ("error", "Error"),
        ],
        string="Status",
        default="received",
        required=True,
        help="Processing status of this event",
    )

    error_message = fields.Text(
        string="Error Message",
        help="Error details if processing failed",
    )

    received_date = fields.Datetime(
        string="Received Date",
        default=fields.Datetime.now,
        required=True,
        help="Date and time when event was received",
    )

    processed_date = fields.Datetime(
        string="Processed Date",
        readonly=True,
        help="Date and time when event was processed",
    )

    processed_by = fields.Many2one(
        "res.users",
        string="Processed By",
        readonly=True,
        help="User who processed this event",
    )

    notes = fields.Text(
        string="Notes",
        help="Additional notes about this event",
    )

    active = fields.Boolean(
        default=True,
        help="Set to false to archive this event",
    )

    @api.constrains("identifier_type", "identifier_value", "event_type", "event_date")
    def _check_event_unique(self):
        """Ensure no duplicate events with same identifier, type, and date."""
        for record in self:
            if record.identifier_type and record.identifier_value and record.event_type and record.event_date:
                duplicate = self.search(
                    [
                        ("identifier_type", "=", record.identifier_type),
                        ("identifier_value", "=", record.identifier_value),
                        ("event_type", "=", record.event_type),
                        ("event_date", "=", record.event_date),
                        ("id", "!=", record.id),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(_("An event with this identifier, type, and date already exists."))

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to generate sequence-based name."""
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                event_type = vals.get("event_type", "event")
                vals["name"] = self.env["ir.sequence"].next_by_code(f"spp.dci.crvs.event.{event_type}") or self.env[
                    "ir.sequence"
                ].next_by_code("spp.dci.crvs.event")
                # If sequence doesn't exist, generate a simple reference
                if not vals["name"] or vals["name"] == _("New"):
                    vals["name"] = f"CRVS-{event_type.upper()}-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"

        return super().create(vals_list)

    @api.constrains("event_date")
    def _check_event_date(self):
        """Validate event date is not in the future."""
        for record in self:
            if record.event_date and record.event_date > fields.Date.today():
                raise ValidationError(_("Event date cannot be in the future."))

    def process_event(self):
        """Process CRVS event and update partner record.

        This method:
        1. Matches the person using identifier
        2. Updates partner record based on event type
        3. Marks event as processed or error

        Returns:
            bool: True if processing succeeded
        """
        self.ensure_one()

        if self.state == "processed":
            raise UserError(_("This event has already been processed."))

        # Mark as processing
        self.state = "processing"

        try:
            _logger.info(
                "Processing CRVS event %s (type: %s, identifier: %s:%s)",
                self.name,
                self.event_type,
                self.identifier_type,
                self.identifier_value,
            )

            # Try to find matching person by identifier
            person = self._find_person_by_identifier()

            if not person:
                _logger.warning(
                    "No matching person found for CRVS event %s (identifier: %s:%s)",
                    self.name,
                    self.identifier_type,
                    self.identifier_value,
                )
                # Mark as error - no match
                self.write(
                    {
                        "state": "error",
                        "error_message": _("No matching person found in registry"),
                        "processed_date": fields.Datetime.now(),
                        "processed_by": self.env.user.id,
                    }
                )
                return False

            # Link person if not already linked
            if not self.person_id:
                self.person_id = person

            # Process based on event type
            if self.event_type == "birth":
                self._process_birth_event(person)
            elif self.event_type == "death":
                self._process_death_event(person)
            elif self.event_type == "marriage":
                self._process_marriage_event(person)
            elif self.event_type == "divorce":
                self._process_divorce_event(person)

            # Mark as processed
            self.write(
                {
                    "state": "processed",
                    "error_message": False,
                    "processed_date": fields.Datetime.now(),
                    "processed_by": self.env.user.id,
                }
            )

            _logger.info("Successfully processed CRVS event ID %s", self.id)
            return True

        except Exception as e:
            _logger.error("Failed to process CRVS event ID %s: %s", self.id, str(e), exc_info=True)
            self.write(
                {
                    "state": "error",
                    "error_message": str(e),
                    "processed_date": fields.Datetime.now(),
                    "processed_by": self.env.user.id,
                }
            )
            return False

    def _find_person_by_identifier(self):
        """Find person in registry by identifier.

        Returns:
            res.partner: Matching partner record or None
        """
        if not self.identifier_type or not self.identifier_value:
            return None

        # Search in registry IDs
        reg_id = self.env["spp.registry.id"].search(
            [
                ("id_type_id.code", "=", self.identifier_type),
                ("value", "=", self.identifier_value),
            ],
            limit=1,
        )

        if reg_id and reg_id.partner_id:
            return reg_id.partner_id

        return None

    def _process_birth_event(self, person):
        """Process birth event - update birth date if not set.

        Args:
            person: res.partner record
        """
        if not person.birthdate and self.event_date:
            person.birthdate = self.event_date
            _logger.info("Updated birth date for partner %s", person.id)

        # Add birth registration ID if in raw data
        self._add_identifier_from_raw_data(person, "BRN")

    def _process_death_event(self, person):
        """Process death event - mark person as deceased.

        Args:
            person: res.partner record
        """
        # Check if person has death_date field (may be added by other modules)
        if hasattr(person, "death_date") and not person.death_date:
            person.death_date = self.event_date
            _logger.info("Updated death date for partner %s", person.id)

        # Disable the registrant
        if person.is_registrant and not person.disabled:
            person.write(
                {
                    "disabled": fields.Datetime.now(),
                    "disabled_reason": _("Deceased - CRVS notification received on %s") % fields.Date.today(),
                    "disabled_by": self.env.user.id,
                }
            )
            _logger.info("Disabled registrant %s due to death event", person.id)

        # Add death registration ID if in raw data
        self._add_identifier_from_raw_data(person, "DRN")

    def _process_marriage_event(self, person):
        """Process marriage event - update civil status.

        Args:
            person: res.partner record
        """
        if hasattr(person, "civil_status"):
            person.civil_status = "married"
            _logger.info("Updated civil status to married for partner %s", person.id)

        # Add marriage registration ID if in raw data
        self._add_identifier_from_raw_data(person, "MRN")

    def _process_divorce_event(self, person):
        """Process divorce event - update civil status.

        Args:
            person: res.partner record
        """
        if hasattr(person, "civil_status"):
            person.civil_status = "divorced"
            _logger.info("Updated civil status to divorced for partner %s", person.id)

    def _add_identifier_from_raw_data(self, person, id_type):
        """Extract and add identifier from raw data if available.

        Args:
            person: res.partner record
            id_type: Identifier type to extract (BRN, DRN, MRN)
        """
        if not self.raw_data:
            return

        try:
            raw_data_dict = json.loads(self.raw_data)

            # Try to extract identifier value from raw data
            # This depends on CRVS response format - adjust as needed
            identifier_value = None

            if "identifiers" in raw_data_dict:
                for identifier in raw_data_dict["identifiers"]:
                    if identifier.get("type") == id_type:
                        identifier_value = identifier.get("value")
                        break

            if identifier_value:
                # Check if identifier already exists
                id_type_record = self.env["spp.id.type"].search([("code", "=", id_type)], limit=1)
                if not id_type_record:
                    _logger.warning("Could not find ID type for code: %s", id_type)
                    return

                existing = self.env["spp.registry.id"].search(
                    [
                        ("partner_id", "=", person.id),
                        ("id_type_id", "=", id_type_record.id),
                        ("value", "=", identifier_value),
                    ],
                    limit=1,
                )

                if not existing:
                    self.env["spp.registry.id"].create(
                        {
                            "partner_id": person.id,
                            "id_type_id": id_type_record.id,
                            "value": identifier_value,
                        }
                    )
                    _logger.info(
                        "Added %s identifier %s to partner %s",
                        id_type,
                        identifier_value,
                        person.id,
                    )

        except json.JSONDecodeError:
            _logger.warning("Failed to parse raw_data JSON for event ID %s", self.id)
        except Exception as e:
            _logger.error("Error extracting identifier from raw_data: %s", str(e))

    def action_retry_processing(self):
        """Retry processing for failed events.

        This is a UI action that allows users to retry processing
        events that failed due to temporary issues.
        """
        failed_events = self.filtered(lambda e: e.state == "error")
        if not failed_events:
            raise UserError(_("No failed events selected for retry."))

        for event in failed_events:
            # Reset state to received
            event.state = "received"
            event.error_message = False
            # Process the event
            event.process_event()

        return True
