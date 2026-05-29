# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""SR Record - Cached data from external Social Registries."""

import json
import logging
from datetime import UTC, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SRRecord(models.Model):
    """Cached record from an external Social Registry.

    Stores demographic and program enrollment data retrieved from
    external Social Registries via DCI API queries.
    """

    _name = "spp.dci.sr.record"
    _description = "Social Registry Record"
    _order = "last_sync_date desc"
    _rec_name = "display_name"

    # Link to local partner
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Registrant",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('is_registrant', '=', True)]",
        help="Local registrant linked to this SR record",
    )

    # External identifiers
    external_id = fields.Char(
        string="External ID",
        index=True,
        help="ID of this person in the external SR",
    )
    identifier_type = fields.Char(
        string="Identifier Type",
        help="Type of identifier used (UIN, NIN, etc.)",
    )
    identifier_value = fields.Char(
        string="Identifier Value",
        help="Value of the identifier",
    )

    # Demographic data from SR
    sr_name = fields.Char(
        string="Name (SR)",
        help="Full name as stored in the SR",
    )
    sr_birth_date = fields.Date(
        string="Birth Date (SR)",
        help="Birth date as stored in the SR",
    )
    sr_gender = fields.Char(
        string="Gender (SR)",
        help="Gender as stored in the SR",
    )
    sr_address = fields.Text(
        string="Address (SR)",
        help="Address as stored in the SR",
    )

    # Program enrollment data
    enrolled_programs = fields.Text(
        string="Enrolled Programs",
        help="JSON list of programs the person is enrolled in",
    )
    program_count = fields.Integer(
        string="Program Count",
        compute="_compute_program_count",
        store=True,
        help="Number of programs enrolled in",
    )

    # Household data
    household_id = fields.Char(
        string="Household ID (SR)",
        help="Household ID in the SR",
    )
    household_size = fields.Integer(
        string="Household Size",
        help="Number of members in household",
    )
    is_head_of_household = fields.Boolean(
        string="Head of Household",
        help="Whether this person is the household head",
    )

    # Sync metadata
    source_registry = fields.Char(
        string="Source Registry",
        required=True,
        index=True,
        help="Sender ID of the SR that provided this data",
    )
    last_sync_date = fields.Datetime(
        string="Last Sync",
        help="When this record was last synchronized",
    )
    synced_by = fields.Many2one(
        comodel_name="res.users",
        string="Synced By",
        help="User who triggered the last sync",
    )
    state = fields.Selection(
        selection=[
            ("synced", "Synced"),
            ("stale", "Stale"),
            ("error", "Error"),
        ],
        string="Status",
        default="synced",
        required=True,
        help="Sync status of this record",
    )
    error_message = fields.Text(
        string="Error Message",
        help="Error details if sync failed",
    )

    # Raw data
    raw_data = fields.Text(
        string="Raw Data",
        help="Complete JSON response from SR",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
    )

    display_name = fields.Char(
        string="Display Name",
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("partner_id", "source_registry")
    def _compute_display_name(self):
        """Compute display name."""
        for rec in self:
            partner_name = rec.partner_id.name or "Unknown"
            rec.display_name = f"{partner_name} ({rec.source_registry})"

    @api.depends("enrolled_programs")
    def _compute_program_count(self):
        """Compute number of enrolled programs."""
        for rec in self:
            if rec.enrolled_programs:
                try:
                    programs = json.loads(rec.enrolled_programs)
                    rec.program_count = len(programs) if isinstance(programs, list) else 0
                except (json.JSONDecodeError, TypeError):
                    rec.program_count = 0
            else:
                rec.program_count = 0

    def get_enrolled_programs(self):
        """Get list of enrolled programs.

        Returns:
            list: List of program names/IDs
        """
        self.ensure_one()
        if not self.enrolled_programs:
            return []
        try:
            programs = json.loads(self.enrolled_programs)
            return programs if isinstance(programs, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def is_enrolled_in(self, program_name):
        """Check if enrolled in a specific program.

        Args:
            program_name: Name or ID of the program

        Returns:
            bool: True if enrolled
        """
        self.ensure_one()
        programs = self.get_enrolled_programs()
        # Check both name and id fields in program entries
        for prog in programs:
            if isinstance(prog, dict):
                if prog.get("name") == program_name or prog.get("id") == program_name:
                    return True
            elif prog == program_name:
                return True
        return False

    def refresh_from_sr(self):
        """Refresh data from the Social Registry.

        Returns:
            bool: True if successful
        """
        self.ensure_one()

        try:
            from odoo.addons.spp_dci_client_sr.services import SRService

            # Find data source for this SR
            data_source = self.env["spp.dci.data.source"].search(
                [
                    ("registry_type", "=", "sr"),
                    ("state", "=", "active"),
                ],
                limit=1,
            )

            if not data_source:
                raise UserError(_("No active SR data source configured"))

            service = SRService(self.env, data_source.code)

            # Query SR for updated data
            result = service.search_person(
                self.identifier_type or "UIN",
                self.identifier_value or self.external_id,
            )

            if result:
                self._update_from_sr_response(result)
                return True
            else:
                self.write(
                    {
                        "state": "error",
                        "error_message": "Person not found in SR",
                    }
                )
                return False

        except Exception as e:
            _logger.error("Failed to refresh SR record: %s", str(e), exc_info=True)
            self.write(
                {
                    "state": "error",
                    "error_message": str(e),
                }
            )
            return False

    def _update_from_sr_response(self, data):
        """Update record from SR API response.

        Args:
            data: Dictionary with SR data
        """
        self.ensure_one()

        vals = {
            "state": "synced",
            "error_message": False,
            "last_sync_date": datetime.now(UTC),
            "synced_by": self.env.user.id,
            "raw_data": json.dumps(data),
        }

        # Extract demographic data
        if "name" in data:
            vals["sr_name"] = data["name"]
        if "birth_date" in data:
            vals["sr_birth_date"] = data["birth_date"]
        if "gender" in data:
            vals["sr_gender"] = data["gender"]
        if "address" in data:
            vals["sr_address"] = json.dumps(data["address"]) if isinstance(data["address"], dict) else data["address"]

        # Extract program enrollment
        if "enrolled_programs" in data:
            vals["enrolled_programs"] = json.dumps(data["enrolled_programs"])

        # Extract household data
        if "household_id" in data:
            vals["household_id"] = data["household_id"]
        if "household_size" in data:
            vals["household_size"] = data["household_size"]
        if "is_head_of_household" in data:
            vals["is_head_of_household"] = data["is_head_of_household"]

        self.write(vals)

    def action_mark_stale(self):
        """Mark record as stale (needs refresh)."""
        self.write({"state": "stale"})

    def action_retry_sync(self):
        """Retry sync for records in error state."""
        for rec in self.filtered(lambda r: r.state == "error"):
            rec.refresh_from_sr()
