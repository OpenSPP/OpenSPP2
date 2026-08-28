# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DataClassificationLevel(models.Model):
    """Data sensitivity classification levels.

    Defines the sensitivity levels for PII fields (e.g., PUBLIC, INTERNAL,
    CONFIDENTIAL, RESTRICTED) along with policies that apply at each level.

    Usage:
        Levels are typically defined via XML data and referenced by
        field classifications. Each level carries policy flags that
        determine how data should be handled.
    """

    _name = "spp.data.classification.level"
    _description = "Data Classification Level"
    _order = "sequence, id"

    name = fields.Char(
        required=True,
        translate=True,
        help="Human-readable name for this classification level",
    )
    code = fields.Char(
        required=True,
        help="Technical code (e.g., PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED)",
    )
    sequence = fields.Integer(
        default=10,
        help="Higher sequence = more sensitive. Used for access control comparison.",
    )
    color = fields.Integer(
        default=0,
        help="Color index for UI display",
    )
    description = fields.Text(
        translate=True,
        help="Detailed description of when to use this classification",
    )
    active = fields.Boolean(default=True)

    # === Policy Flags ===
    is_requires_encryption = fields.Boolean(
        string="Requires Encryption",
        default=False,
        help="Fields at this level must be encrypted at rest",
    )
    is_requires_masking = fields.Boolean(
        string="Requires Masking",
        default=False,
        help="Fields displayed with masking by default (e.g., ****1234)",
    )
    is_requires_audit = fields.Boolean(
        string="Requires Audit",
        default=False,
        help="All access to fields at this level is logged",
    )
    is_requires_consent = fields.Boolean(
        string="Requires Consent",
        default=False,
        help="Explicit consent required before collection/processing",
    )
    is_requires_purpose_limitation = fields.Boolean(
        string="Requires Purpose Limitation",
        default=False,
        help="Data can only be used for stated purposes",
    )

    # === Retention ===
    retention_days = fields.Integer(
        string="Retention Period (Days)",
        default=0,
        help="Auto-archive/delete after N days. 0 = indefinite retention.",
    )
    retention_action = fields.Selection(
        [
            ("none", "No Action"),
            ("anonymize", "Anonymize"),
            ("archive", "Archive"),
            ("delete", "Delete"),
        ],
        string="Retention Action",
        default="none",
        help="Action to take when retention period expires",
    )

    # === Access Control ===
    min_group_id = fields.Many2one(
        "res.groups",
        string="Minimum Access Group",
        help="Minimum security group required to view unmasked data at this level",
    )

    _unique_code = models.Constraint(
        "UNIQUE(code)",
        "Classification code must be unique",
    )

    def unlink(self):
        """Prevent deletion of levels that are in use."""
        for record in self:
            field_count = self.env["spp.field.classification"].search_count([("classification_id", "=", record.id)])
            if field_count > 0:
                raise UserError(
                    _(
                        "Cannot delete classification level '%(name)s' - "
                        "it is used by %(count)d field classification(s)."
                    )
                    % {"name": record.name, "count": field_count}
                )
        return super().unlink()

    @api.model
    def get_level_by_code(self, code):
        """Get classification level by code.

        Args:
            code: The classification code (e.g., 'RESTRICTED')

        Returns:
            recordset: The matching classification level or empty recordset
        """
        return self.search([("code", "=", code)], limit=1)

    def is_more_sensitive_than(self, other_level):
        """Compare sensitivity between two levels.

        Args:
            other_level: Another classification level to compare against

        Returns:
            bool: True if this level is more sensitive (higher sequence)
        """
        self.ensure_one()
        if not other_level:
            return True
        return self.sequence > other_level.sequence
