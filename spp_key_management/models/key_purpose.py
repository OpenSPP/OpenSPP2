"""Key Purpose Definitions.

Defines the different purposes for which encryption keys can be used.
This allows segregation of keys by purpose for better security.
"""

from odoo import fields, models


class KeyPurpose(models.Model):
    """Defines purposes for encryption keys."""

    _name = "spp.key.purpose"
    _description = "Encryption Key Purpose"
    _order = "sequence, name"

    name = fields.Char(
        string="Name",
        required=True,
        translate=True,
    )

    code = fields.Char(
        string="Code",
        required=True,
        index=True,
        help="Technical code for the purpose (e.g., 'pii', 'financial')",
    )

    description = fields.Text(
        string="Description",
        translate=True,
    )

    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )

    active = fields.Boolean(
        default=True,
    )

    # Key settings
    key_rotation_days = fields.Integer(
        string="Key Rotation (Days)",
        default=365,
        help="Recommended key rotation period in days. 0 = no automatic rotation.",
    )

    require_hardware_key = fields.Boolean(
        string="Require Hardware Key",
        default=False,
        help="Require keys to be stored in HSM or cloud KMS",
    )

    _code_unique = models.Constraint("UNIQUE(code)", "Purpose code must be unique")
