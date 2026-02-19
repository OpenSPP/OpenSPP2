# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import base64
import hashlib
import logging
import os
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Scrypt parameters (memory-hard, resistant to GPU attacks)
# Similar security to bcrypt with better memory-hardness
SCRYPT_N = 16384  # CPU/memory cost factor (must be power of 2)
SCRYPT_R = 8  # Block size
SCRYPT_P = 1  # Parallelization factor
SCRYPT_DKLEN = 64  # Derived key length


class ApiClient(models.Model):
    """API Client for V2 API.

    Supports multiple authentication types:
    - OAuth 2.0 (client credentials flow)
    - HTTP Signatures (DCI protocol)

    This is the base model for all API clients. DCI sender registry
    inherits from this to share organization_type and consent features.
    """

    _name = "spp.api.client"
    _description = "API V2 Client"
    _order = "name"

    name = fields.Char(required=True, help="Client name for identification")

    # Authentication type - determines which auth fields are used
    auth_type = fields.Selection(
        [
            ("oauth2", "OAuth 2.0"),
            ("http_signature", "HTTP Signature (DCI)"),
            ("none", "No Authentication"),
        ],
        string="Authentication Type",
        default="oauth2",
        required=True,
        help="Authentication method used by this client. "
        "OAuth 2.0 for standard REST clients, HTTP Signature for DCI protocol.",
    )

    # OAuth credentials (used when auth_type='oauth2')
    client_id = fields.Char(
        copy=False,
        default=lambda self: self._generate_client_id(),
        help="OAuth client_id used for authentication (required for OAuth clients)",
    )
    # SECURITY: client_secret is only used temporarily during create/regenerate
    # The plaintext is shown once and then cleared; only the hash is stored
    client_secret = fields.Char(
        copy=False,
        help="OAuth client_secret - shown only once on creation/regeneration",
    )
    # SECURITY: Scrypt hash of client_secret for secure storage
    client_secret_hash = fields.Char(
        copy=False,
        help="Scrypt hash of client_secret (never exposed via API)",
    )

    # Organization this client represents
    partner_id = fields.Many2one(
        "res.partner",
        string="Organization",
        required=True,
        help="Organization this API client represents",
    )

    # Organization classification for category-based consent
    # SECURITY: Once verified, organization_type_id cannot be changed without admin override
    # Uses spp.consent.org.type for single source of truth and database-level integrity
    organization_type_id = fields.Many2one(
        "spp.consent.org.type",
        string="Organization Type",
        required=True,
        ondelete="restrict",
        help="Classification of the organization for consent matching. "
        "Beneficiaries can consent to share data with specific organization types.",
    )

    # Computed field storing the organization type CODE (string, e.g., "ngo", "government")
    # READ-ONLY: To change, update organization_type_id instead
    # Stored for search/filter performance in consent matching
    organization_type = fields.Char(
        compute="_compute_organization_type",
        store=True,
        readonly=True,
        string="Organization Type Code",
        help="Code of the organization type (computed from organization_type_id). "
        "READ-ONLY: Update organization_type_id to change.",
    )

    @api.depends("organization_type_id.code")
    def _compute_organization_type(self):
        """Compute organization type code from the Many2one relationship."""
        for record in self:
            record.organization_type = record.organization_type_id.code or ""

    # Organization type verification (prevents spoofing attacks)
    is_organization_type_verified = fields.Boolean(
        default=False,
        help="Whether organization type has been verified by administrator",
    )
    is_organization_type_verified_by = fields.Many2one(
        "res.users",
        string="Verified By",
        readonly=True,
    )
    is_organization_type_verified_date = fields.Datetime(
        string="Verified Date",
        readonly=True,
    )

    def write(self, vals):
        """
        Override write to prevent organization type changes after verification.

        SECURITY: This prevents attackers from changing their org type
        (e.g., from 'private' to 'ngo') to bypass category-based consent.
        """
        if "organization_type_id" in vals:
            for record in self:
                if (
                    record.is_organization_type_verified
                    and record.organization_type_id.id != vals["organization_type_id"]
                ):
                    raise ValidationError(
                        "Cannot change organization type after verification. "
                        "Contact administrator to request a change with proper justification."
                    )
        return super().write(vals)

    def action_verify_organization_type(self):
        """Mark organization type as verified (admin action)"""
        self.ensure_one()
        self.write(
            {
                "is_organization_type_verified": True,
                "is_organization_type_verified_by": self.env.user.id,
                "is_organization_type_verified_date": fields.Datetime.now(),
            }
        )
        _logger.info(
            "Organization type '%s' (%s) verified for client %s by %s",
            self.organization_type_id.name,
            self.organization_type,
            self.client_id or self.name,
            self.env.user.name,
        )

    # Scopes and permissions
    scope_ids = fields.One2many(
        "spp.api.client.scope",
        "client_id",
        string="Scopes",
    )
    scope_count = fields.Integer(compute="_compute_scope_count", string="Scope Count")

    # Rate limiting
    rate_limit_per_minute = fields.Integer(
        default=60,
        help="Maximum requests per minute",
    )
    rate_limit_per_day = fields.Integer(
        default=10000,
        help="Maximum requests per day",
    )

    # Consent requirements
    # GDPR Article 6 / DPV LegalBasis aligned
    is_require_consent = fields.Boolean(
        default=True,
        help="Whether explicit individual consent is required for data access. "
        "Set to False for legal_obligation, public_interest, or vital_interest bases.",
    )
    legal_basis = fields.Selection(
        [
            # Requires individual consent
            ("consent", "Explicit Consent (GDPR A6-1-a)"),
            # Does NOT require individual consent
            ("contract", "Contractual Necessity (GDPR A6-1-b)"),
            ("legal_obligation", "Legal Obligation (GDPR A6-1-c)"),
            ("vital_interest", "Vital Interest (GDPR A6-1-d)"),
            ("public_interest", "Public Interest (GDPR A6-1-e)"),
            ("public_task", "Public Task / Official Authority"),
            ("legitimate_interest", "Legitimate Interest (GDPR A6-1-f)"),
        ],
        default="consent",
        help="Legal basis for data processing per GDPR Article 6. "
        "For interagency data exchange, use 'Legal Obligation' or 'Public Interest' "
        "with a reference to the authorizing law.",
    )
    legal_basis_reference = fields.Char(
        string="Legal Reference",
        help="Reference to law, regulation, MOU, or contract authorizing access. "
        "E.g., 'Data Protection Act 2019, Section 45' or 'MOU-2024-001'",
    )

    # Status and metadata
    active = fields.Boolean(default=True)
    description = fields.Text()

    # Tracking
    last_used_date = fields.Datetime(readonly=True)
    request_count = fields.Integer(default=0, readonly=True)

    @api.constrains("auth_type", "client_id", "client_secret_hash")
    def _check_oauth_fields_required(self):
        """Ensure OAuth fields are present when auth_type is oauth2."""
        for record in self:
            if record.auth_type == "oauth2":
                if not record.client_id:
                    raise ValidationError(_("Client ID is required for OAuth 2.0 authentication."))
                # Note: client_secret_hash is set during create, so we only check
                # on existing records that have been saved
                if record.id and not record.client_secret_hash:
                    raise ValidationError(
                        _("Client secret is required for OAuth 2.0 authentication. Please regenerate the secret.")
                    )

    @api.constrains("client_id")
    def _check_unique_client_id(self):
        """Ensure client_id is unique (when set)."""
        for record in self:
            if not record.client_id:
                continue

            domain = [
                ("client_id", "=", record.client_id),
                ("id", "!=", record.id),
            ]
            if self.search(domain, limit=1):
                raise ValidationError(
                    _("Client ID must be unique. A client with ID '%s' already exists.") % record.client_id
                )

    @api.depends("scope_ids")
    def _compute_scope_count(self):
        for rec in self:
            rec.scope_count = len(rec.scope_ids)

    @api.model
    def _generate_client_id(self):
        """Generate a unique client_id"""
        return f"client_{secrets.token_urlsafe(16)}"

    @api.model
    def _generate_client_secret(self):
        """Generate a cryptographically secure client secret"""
        return secrets.token_urlsafe(32)

    @api.model
    def _hash_secret(self, secret):
        """
        Hash a secret using scrypt (memory-hard, GPU-resistant).

        Format: $scrypt$salt_base64$hash_base64

        Args:
            secret: Plaintext secret string

        Returns:
            Hash string in format $scrypt$salt$hash
        """
        # Generate random salt (16 bytes = 128 bits)
        salt = os.urandom(16)

        # Compute scrypt hash
        hash_bytes = hashlib.scrypt(
            secret.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
        )

        # Encode salt and hash as base64
        salt_b64 = base64.b64encode(salt).decode("ascii")
        hash_b64 = base64.b64encode(hash_bytes).decode("ascii")

        return f"$scrypt${salt_b64}${hash_b64}"

    @api.model
    def _verify_secret(self, secret, secret_hash):
        """
        Verify a secret against its scrypt hash.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            secret: Plaintext secret to verify
            secret_hash: Hash string from _hash_secret

        Returns:
            True if secret matches, False otherwise
        """
        if not secret or not secret_hash:
            return False

        # Parse hash format: $scrypt$salt_base64$hash_base64
        try:
            parts = secret_hash.split("$")
            if len(parts) != 4 or parts[1] != "scrypt":
                # Invalid hash format - reject
                _logger.warning("Invalid secret hash format")
                return False

            salt = base64.b64decode(parts[2])
            stored_hash = base64.b64decode(parts[3])

            # Compute hash of provided secret
            computed_hash = hashlib.scrypt(
                secret.encode("utf-8"),
                salt=salt,
                n=SCRYPT_N,
                r=SCRYPT_R,
                p=SCRYPT_P,
                dklen=SCRYPT_DKLEN,
            )

            # Constant-time comparison to prevent timing attacks
            return secrets.compare_digest(computed_hash, stored_hash)

        except (ValueError, TypeError):
            return False

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to hash client secret for OAuth clients."""
        for vals in vals_list:
            # Only generate OAuth credentials for OAuth clients
            auth_type = vals.get("auth_type", "oauth2")

            if auth_type == "oauth2":
                # Generate and hash secret if not provided
                if "client_secret" not in vals or not vals.get("client_secret"):
                    vals["client_secret"] = self._generate_client_secret()

                # Hash the secret
                secret = vals["client_secret"]
                vals["client_secret_hash"] = self._hash_secret(secret)
                # Keep plaintext temporarily for display on creation
                # Will be cleared after user copies it

                # Ensure client_id is generated
                if "client_id" not in vals or not vals.get("client_id"):
                    vals["client_id"] = self._generate_client_id()
            else:
                # Non-OAuth clients don't need OAuth credentials
                # Clear any OAuth fields that might have been set
                vals.pop("client_secret", None)
                vals.pop("client_secret_hash", None)

        return super().create(vals_list)

    def action_regenerate_secret(self):
        """Regenerate client secret and show in wizard for copying."""
        self.ensure_one()
        new_secret = self._generate_client_secret()
        self.write(
            {
                "client_secret": new_secret,  # Temporary for display in wizard
                "client_secret_hash": self._hash_secret(new_secret),
            }
        )
        _logger.info("Regenerated client secret for client ID %s", self.id)

        # Create wizard to show credentials
        wizard = self.env["spp.api.client.show.secret.wizard"].create(
            {
                "client_id": self.id,
                "client_name": self.name,
                "oauth_client_id": self.client_id,
                "client_secret": new_secret,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": "API Client Credentials",
            "res_model": "spp.api.client.show.secret.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "view_id": self.env.ref("spp_api_v2.view_show_secret_wizard_form").id,
            "target": "new",
            "context": {"dialog_size": "medium"},
        }

    def action_view_scopes(self):
        """Open scopes for this client"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Scopes: {self.name}",
            "res_model": "spp.api.client.scope",
            "view_mode": "list,form",
            "domain": [("client_id", "=", self.id)],
            "context": {"default_client_id": self.id},
        }

    @api.model
    def authenticate(self, client_id, client_secret):
        """
        Authenticate API client using scrypt hash verification.

        SECURITY: Uses constant-time comparison to prevent timing attacks.

        Args:
            client_id: OAuth client_id
            client_secret: Plaintext client_secret

        Returns:
            spp.api.client record if valid, empty recordset otherwise
        """
        # Find client by client_id only (no plaintext secret comparison)
        client = self.search(
            [
                ("client_id", "=", client_id),
                ("active", "=", True),
            ],
            limit=1,
        )

        if not client:
            return self.env["spp.api.client"]

        # Verify secret against hash
        # SECURITY: Only hashed secrets are supported - no plaintext fallback
        secret_hash = client.client_secret_hash
        if not secret_hash:
            _logger.error(
                "Client %s has no hashed secret - regenerate required",
                client_id,
            )
            return self.env["spp.api.client"]

        if not self._verify_secret(client_secret, secret_hash):
            return self.env["spp.api.client"]

        # Update last used timestamp and count
        client.sudo().write(  # nosemgrep: odoo-sudo-without-context
            {
                "last_used_date": fields.Datetime.now(),
                "request_count": client.request_count + 1,
            }
        )
        return client

    def has_scope(self, resource, action):
        """Check if client has permission for resource/action"""
        self.ensure_one()
        return bool(self.scope_ids.filtered(lambda s: s.resource == resource and s.action in (action, "all")))

    def has_scope_string(self, scope_string):
        """
        Check if client has a specific scope by string.

        Supports formats:
        - "resource:action" (e.g., "Individual:read")
        - "resource" (implies any action on that resource)
        - "resource:*" (any action on that resource)

        Args:
            scope_string: Scope string to check

        Returns:
            True if client has the specified scope
        """
        self.ensure_one()
        if not scope_string:
            return False

        # Parse scope string
        if ":" in scope_string:
            parts = scope_string.split(":", 1)
            resource = parts[0]
            action = parts[1] if len(parts) > 1 else "*"
        else:
            resource = scope_string
            action = "*"

        # Check if action is wildcard
        if action == "*":
            # Any action on this resource
            return bool(self.scope_ids.filtered(lambda s: s.resource == resource))

        return self.has_scope(resource, action)

    def get_allowed_fields(self, resource):
        """Get list of allowed fields for a resource"""
        self.ensure_one()
        scopes = self.scope_ids.filtered(lambda s: s.resource == resource)
        if not scopes:
            # No scopes means no restrictions - all fields allowed
            return None

        # If any scope allows all fields, return None (meaning all allowed)
        if any(not scope.field_filter_ids for scope in scopes):
            return None

        # Otherwise return union of allowed fields
        allowed = set()
        for scope in scopes:
            if scope.field_filter_ids:
                allowed.update(scope.field_filter_ids.mapped("name"))
        # SECURITY: Return the set directly, not `allowed or None`
        # An empty set means no fields allowed, None means all fields allowed
        # Using `or` would incorrectly convert empty set to None (all access)
        return allowed
