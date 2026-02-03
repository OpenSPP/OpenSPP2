# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class DisabilityStatus(models.Model):
    """Disability Status Cache.

    Caches disability information received from Disability Registry (DR)
    systems via DCI API. Stores PWD status, disability types, and
    functional assessment scores.
    """

    _name = "spp.dci.disability.status"
    _description = "Disability Status"
    _order = "last_sync_date desc, id desc"
    _rec_name = "partner_id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Person",
        required=True,
        ondelete="cascade",
        index=True,
        help="Person associated with this disability status",
    )

    has_disability = fields.Boolean(
        string="Has Disability (PWD)",
        default=False,
        help="True if person is registered as PWD in Disability Registry",
    )

    disability_types = fields.Text(
        string="Disability Types (JSON)",
        help="JSON list of disability types: Vision, Hearing, Mobility, Cognition, SelfCare, Communication",
    )

    functional_scores = fields.Text(
        string="Functional Assessment Scores (JSON)",
        help=(
            "JSON dict with functional scores by domain. "
            "Severity: 1=No difficulty, 2=Some difficulty, "
            "3=A lot of difficulty, 4=Cannot do"
        ),
    )

    assessment_date = fields.Date(
        string="Assessment Date",
        help="Date when functional assessment was performed",
    )

    source_registry = fields.Char(
        string="Source Registry",
        help="Name or identifier of the source Disability Registry",
    )

    raw_data = fields.Text(
        string="Raw Data (JSON)",
        help="Original JSON data received from DR system",
    )

    state = fields.Selection(
        [
            ("synced", "Synced"),
            ("stale", "Stale"),
            ("error", "Error"),
        ],
        string="Status",
        default="synced",
        required=True,
        help="Status of this disability record",
    )

    error_message = fields.Text(
        string="Error Message",
        help="Error details if sync failed",
    )

    last_sync_date = fields.Datetime(
        string="Last Sync Date",
        default=fields.Datetime.now,
        required=True,
        help="Date and time when status was last synced from DR",
    )

    synced_by = fields.Many2one(
        "res.users",
        string="Synced By",
        default=lambda self: self.env.user,
        help="User who performed the sync",
    )

    notes = fields.Text(
        string="Notes",
        help="Additional notes about this disability status",
    )

    active = fields.Boolean(
        default=True,
        help="Set to false to archive this record",
    )

    @api.constrains("partner_id")
    def _check_partner_unique(self):
        """Ensure only one active disability status record per person."""
        for record in self:
            if record.partner_id and record.active:
                duplicate = self.search(
                    [
                        ("partner_id", "=", record.partner_id.id),
                        ("id", "!=", record.id),
                        ("active", "=", True),
                    ],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(_("Only one active disability status record per person is allowed."))

    @api.constrains("assessment_date")
    def _check_assessment_date(self):
        """Validate assessment date is not in the future."""
        for record in self:
            if record.assessment_date and record.assessment_date > fields.Date.today():
                raise ValidationError(_("Assessment date cannot be in the future."))

    def refresh_from_dr(self, data_source_code="dr_main"):
        """Refresh disability status from Disability Registry.

        Fetches latest disability information from DR system and updates
        this record with the new data.

        Args:
            data_source_code: Code of the DCI data source for DR (default: "dr_main")

        Returns:
            bool: True if refresh succeeded, False if failed

        Raises:
            UserError: If DR service is not available or request fails
        """
        self.ensure_one()

        if not self.partner_id:
            raise UserError(_("Cannot refresh disability status: no partner associated"))

        _logger.info(
            "Refreshing disability status from DR for partner %s (ID: %s)",
            self.partner_id.name,
            self.partner_id.id,
        )

        try:
            # Import DR service here to avoid circular imports
            from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

            # Initialize DR service
            dr_service = DRService(self.env, data_source_code=data_source_code)

            # Sync disability data
            result = dr_service.sync_disability_data(self.partner_id)

            if result:
                _logger.info(
                    "Successfully refreshed disability status for partner %s",
                    self.partner_id.id,
                )
                return True
            else:
                self.write(
                    {
                        "state": "error",
                        "error_message": _("Failed to retrieve disability data from DR"),
                        "last_sync_date": fields.Datetime.now(),
                        "synced_by": self.env.user.id,
                    }
                )
                return False

        except Exception as e:
            _logger.error(
                "Failed to refresh disability status for partner %s: %s",
                self.partner_id.id,
                str(e),
                exc_info=True,
            )
            self.write(
                {
                    "state": "error",
                    "error_message": str(e),
                    "last_sync_date": fields.Datetime.now(),
                    "synced_by": self.env.user.id,
                }
            )
            return False

    def get_disability_types_list(self):
        """Get disability types as Python list.

        Returns:
            list: List of disability type strings, or empty list if none
        """
        self.ensure_one()
        if not self.disability_types:
            return []

        try:
            return json.loads(self.disability_types)
        except (json.JSONDecodeError, TypeError):
            _logger.warning(
                "Failed to parse disability_types JSON for record %s",
                self.id,
            )
            return []

    def get_functional_scores_dict(self):
        """Get functional scores as Python dictionary.

        Returns:
            dict: Dictionary of functional domain -> score, or empty dict if none
        """
        self.ensure_one()
        if not self.functional_scores:
            return {}

        try:
            return json.loads(self.functional_scores)
        except (json.JSONDecodeError, TypeError):
            _logger.warning(
                "Failed to parse functional_scores JSON for record %s",
                self.id,
            )
            return {}

    def action_retry_sync(self):
        """Retry syncing disability status from DR.

        This is a UI action that allows users to retry syncing
        disability status after a failure.
        """
        for record in self:
            record.refresh_from_dr()

        return True

    def action_mark_outdated(self):
        """Mark disability status as stale.

        This allows users to flag records that need to be refreshed.
        """
        self.write({"state": "stale"})
        return True
