# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Encryption Key Storage Model.

Stores encrypted data encryption keys (DEKs) in the database.
Keys are encrypted with a master key (KEK) from configuration.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class EncryptionKey(models.Model):
    """Encrypted key storage for database key provider.

    Stores data encryption keys encrypted by the master key.
    Supports multiple versions per key for rotation.
    """

    _name = "spp.encryption.key"
    _description = "Encryption Key"
    _order = "key_id, version desc"
    _rec_name = "display_name"

    key_id = fields.Char(
        required=True,
        index=True,
        help="Identifier for this key (e.g., 'pii', 'financial')",
    )
    version = fields.Integer(
        required=True,
        default=1,
        help="Version number (increments on rotation)",
    )
    is_current = fields.Boolean(
        default=True,
        index=True,
        help="Is this the current version for encryption?",
    )
    encrypted_key = fields.Char(
        required=True,
        groups="base.group_system",
        help="Base64-encoded encrypted key material",
    )
    algorithm = fields.Char(
        default="AES-256-GCM",
        readonly=True,
    )
    purpose = fields.Char(
        help="Description of what this key is used for",
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
    )
    expires_date = fields.Datetime(
        help="Optional expiration date for this key version",
    )

    _unique_key_version = models.Constraint("UNIQUE(key_id, version)", "Key version must be unique")

    @api.depends("key_id", "version", "is_current")
    def _compute_display_name(self):
        for record in self:
            current_marker = " (current)" if record.is_current else ""
            record.display_name = f"{record.key_id} v{record.version}{current_marker}"

    @api.constrains("is_current")
    def _check_single_current(self):
        """Ensure only one current version per key_id."""
        for record in self:
            if record.is_current:
                others = self.search(
                    [
                        ("key_id", "=", record.key_id),
                        ("is_current", "=", True),
                        ("id", "!=", record.id),
                    ]
                )
                if others:
                    raise UserError(
                        _(
                            "Only one version of key '%(key_id)s' can be current. "
                            "Found %(count)d other current versions."
                        )
                        % {"key_id": record.key_id, "count": len(others)}
                    )

    def unlink(self):
        """Prevent deletion of encryption keys."""
        raise UserError(_("Encryption keys cannot be deleted. " "Archive old versions by setting is_current=False."))

    @api.model
    def get_current_version(self, key_id):
        """Get the current version number for a key.

        Args:
            key_id: Key identifier

        Returns:
            int: Current version number, or 0 if not found
        """
        key = self.search(
            [
                ("key_id", "=", key_id),
                ("is_current", "=", True),
            ],
            limit=1,
        )
        return key.version if key else 0
