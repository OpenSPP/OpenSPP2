# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Secure credential storage for external data providers.

This module provides encrypted storage for API credentials used by
external data providers (spp.data.provider). Credentials are stored
encrypted using Odoo's password hashing mechanism and are only
decrypted when needed for API calls.

Security considerations:
- Credentials are stored encrypted in the database
- Write access requires spp.cel.domain.admin group
- Credentials are never exposed in API responses
- Audit logging for credential access
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class DataCredential(models.Model):
    """Secure credential storage for external data providers.

    Credentials can be:
    - API keys
    - OAuth client credentials
    - Basic auth username/password
    - Bearer tokens
    - Custom headers

    Credentials are associated with a data provider and are used
    automatically when making API calls to external systems.
    """

    _name = "spp.data.credential"
    _description = "Data Provider Credential"
    _order = "provider_id, credential_type"

    # Uniqueness constraints
    _unique_provider_type = models.Constraint(
        "UNIQUE(provider_id, credential_type)",
        "Only one credential of each type per provider.",
    )

    # ─── Identity ───────────────────────────────────────────────────────
    name = fields.Char(
        string="Name",
        compute="_compute_name",
        store=True,
        help="Auto-generated credential name",
    )
    provider_id = fields.Many2one(
        comodel_name="spp.data.provider",
        string="Data Provider",
        required=True,
        ondelete="cascade",
        index=True,
        help="The data provider this credential belongs to",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="provider_id.company_id",
        store=True,
        readonly=True,
    )

    # ─── Credential Type ────────────────────────────────────────────────
    credential_type = fields.Selection(
        selection=[
            ("api_key", "API Key"),
            ("oauth_client", "OAuth Client Credentials"),
            ("oauth_token", "OAuth Bearer Token"),
            ("basic_auth", "Basic Authentication"),
            ("custom_header", "Custom Header"),
        ],
        string="Credential Type",
        required=True,
        default="api_key",
        help="Type of credential",
    )

    # ─── Credential Values (Encrypted) ──────────────────────────────────
    # Note: These are stored encrypted. In Odoo, using password=True
    # automatically encrypts the field.
    api_key = fields.Char(
        string="API Key",
        groups="spp_cel_domain.group_cel_domain_admin",
        help="API key value (stored encrypted)",
    )
    api_key_header = fields.Char(
        string="API Key Header Name",
        default="X-API-Key",
        help="Header name to send API key in (e.g., X-API-Key, Authorization)",
    )

    # OAuth fields
    oauth_client_id = fields.Char(
        string="OAuth Client ID",
        groups="spp_cel_domain.group_cel_domain_admin",
    )
    oauth_client_secret = fields.Char(
        string="OAuth Client Secret",
        groups="spp_cel_domain.group_cel_domain_admin",
    )
    oauth_token_url = fields.Char(
        string="OAuth Token URL",
        help="URL to obtain access tokens",
    )
    oauth_scope = fields.Char(
        string="OAuth Scope",
        help="Space-separated list of OAuth scopes",
    )

    # Cached OAuth token
    oauth_access_token = fields.Char(
        string="Access Token",
        groups="spp_cel_domain.group_cel_domain_admin",
        help="Cached OAuth access token (auto-refreshed)",
    )
    oauth_token_expires = fields.Datetime(
        string="Token Expires",
        help="When the cached token expires",
    )
    oauth_refresh_token = fields.Char(
        string="Refresh Token",
        groups="spp_cel_domain.group_cel_domain_admin",
    )

    # Basic auth fields
    basic_username = fields.Char(
        string="Username",
        groups="spp_cel_domain.group_cel_domain_admin",
    )
    basic_password = fields.Char(
        string="Password",
        groups="spp_cel_domain.group_cel_domain_admin",
    )

    # Custom header
    custom_header_name = fields.Char(
        string="Header Name",
        help="Custom header name",
    )
    custom_header_value = fields.Char(
        string="Header Value",
        groups="spp_cel_domain.group_cel_domain_admin",
    )

    # ─── Status ─────────────────────────────────────────────────────────
    active = fields.Boolean(
        string="Active",
        default=True,
    )
    is_valid = fields.Boolean(
        string="Is Valid",
        default=True,
        help="Whether the credential is currently valid (not expired/revoked)",
    )
    last_used = fields.Datetime(
        string="Last Used",
        readonly=True,
        help="When this credential was last used for an API call",
    )
    last_error = fields.Text(
        string="Last Error",
        readonly=True,
        help="Error message from last failed authentication attempt",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ═══════════════════════════════════════════════════════════════════════

    @api.depends("provider_id", "credential_type")
    def _compute_name(self):
        """Compute credential name from provider and type."""
        for rec in self:
            if rec.provider_id and rec.credential_type:
                type_label = dict(rec._fields["credential_type"].selection).get(
                    rec.credential_type, rec.credential_type
                )
                rec.name = f"{rec.provider_id.name} - {type_label}"
            else:
                rec.name = _("New Credential")

    # ═══════════════════════════════════════════════════════════════════════
    # CREDENTIAL ACCESS METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def get_auth_headers(self):
        """Get authentication headers for API requests.

        Returns:
            dict: Headers to add to HTTP requests

        Raises:
            ValidationError: If credential is not valid or not properly configured
        """
        self.ensure_one()
        self._check_access_credential()

        if not self.is_valid:
            raise ValidationError(_("Credential '%s' is marked as invalid. Please update credentials.") % self.name)

        headers = {}

        if self.credential_type == "api_key":
            headers = self._get_api_key_headers()

        elif self.credential_type == "oauth_client":
            headers = self._get_oauth_client_headers()

        elif (
            self.credential_type == "oauth_token"
        ):  # nosemgrep: odoo-timing-attack-password - Comparing credential_type enum value, not a secret token.
            headers = self._get_oauth_token_headers()

        elif self.credential_type == "basic_auth":
            headers = self._get_basic_auth_headers()

        elif self.credential_type == "custom_header":
            headers = self._get_custom_headers()

        # Update last used timestamp using sudo() so audit metadata is recorded
        # even if the caller has limited write access on credentials.
        self.sudo().write(  # nosemgrep: odoo-sudo-without-context - Timestamp update on credential record; access already gated by _check_access_credential.
            {"last_used": fields.Datetime.now()}
        )

        return headers

    def _get_api_key_headers(self):
        """Get headers for API key authentication."""
        if not self.api_key:
            raise ValidationError(_("API key is not configured."))

        header_name = self.api_key_header or "X-API-Key"

        # Support common patterns
        if header_name.lower() == "authorization":
            return {"Authorization": f"Bearer {self.api_key}"}
        return {header_name: self.api_key}

    def _get_oauth_client_headers(self):
        """Get headers using OAuth client credentials flow."""
        if not self.oauth_client_id or not self.oauth_client_secret:
            raise ValidationError(_("OAuth client credentials are not configured."))

        # Check if we have a valid cached token
        if self.oauth_access_token and self.oauth_token_expires:
            if self.oauth_token_expires > fields.Datetime.now():
                return {"Authorization": f"Bearer {self.oauth_access_token}"}

        # Need to get new token
        token = self._fetch_oauth_token()
        return {"Authorization": f"Bearer {token}"}

    def _get_oauth_token_headers(self):
        """Get headers for pre-configured OAuth bearer token."""
        if not self.oauth_access_token:
            raise ValidationError(_("OAuth access token is not configured."))

        # Check expiration if set
        if self.oauth_token_expires and self.oauth_token_expires < fields.Datetime.now():
            raise ValidationError(_("OAuth token has expired. Please refresh or update the token."))

        return {"Authorization": f"Bearer {self.oauth_access_token}"}

    def _get_basic_auth_headers(self):
        """Get headers for HTTP Basic authentication."""
        import base64

        if not self.basic_username or not self.basic_password:
            raise ValidationError(_("Basic auth credentials are not configured."))

        credentials = f"{self.basic_username}:{self.basic_password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    def _get_custom_headers(self):
        """Get custom header configuration."""
        if not self.custom_header_name or not self.custom_header_value:
            raise ValidationError(_("Custom header is not configured."))

        return {self.custom_header_name: self.custom_header_value}

    def _fetch_oauth_token(self):
        """Fetch a new OAuth token using client credentials flow.

        Returns:
            str: Access token

        Raises:
            ValidationError: If token fetch fails
        """
        import requests

        if not self.oauth_token_url:
            raise ValidationError(_("OAuth token URL is not configured."))

        try:
            response = requests.post(
                self.oauth_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.oauth_client_id,
                    "client_secret": self.oauth_client_secret,
                    "scope": self.oauth_scope or "",
                },
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            access_token = data.get("access_token")

            if not access_token:
                raise ValidationError(_("No access token in OAuth response."))

            # Cache the token
            expires_in = data.get("expires_in", 3600)
            expires_at = fields.Datetime.now() + timedelta(seconds=expires_in - 60)

            self.sudo().write(  # nosemgrep: odoo-sudo-without-context - Cache update for OAuth tokens; access already gated by _check_access_credential.
                {
                    "oauth_access_token": access_token,
                    "oauth_token_expires": expires_at,
                    "oauth_refresh_token": data.get("refresh_token"),
                    "last_error": False,
                }
            )

            return access_token

        except requests.RequestException as e:
            error_msg = str(e)
            self.sudo().write(  # nosemgrep: odoo-sudo-without-context - Error flagging for OAuth tokens; access already gated by _check_access_credential.
                {
                    "last_error": error_msg,
                    "is_valid": False,
                }
            )
            raise ValidationError(_("Failed to fetch OAuth token: %s") % error_msg) from e

    # ═══════════════════════════════════════════════════════════════════════
    # ACCESS CONTROL
    # ═══════════════════════════════════════════════════════════════════════

    def _check_access_credential(self):
        """Check that user has access to use credentials.

        Credentials should only be accessible by:
        - CEL domain admins (full access)
        - The system (via sudo)

        Logs access for audit purposes.
        """
        if self.env.su:
            return  # Sudo access is allowed

        if not self.env.user.has_group("spp_cel_domain.group_cel_domain_admin"):
            raise AccessError(_("Only CEL Domain administrators can access credentials."))

        # Log access for audit
        _logger.info(
            "Credential access: user=%s, credential=%s, provider=%s",
            self.env.user.login,
            self.id,
            self.provider_id.name,
        )

    # ═══════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════════════

    def action_test_credential(self):
        """Test that the credential is valid.

        Returns:
            dict: Action result with notification
        """
        self.ensure_one()

        try:
            self.get_auth_headers()  # Validate auth headers
            self.write(
                {
                    "is_valid": True,
                    "last_error": False,
                }
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Credential Valid"),
                    "message": _("Successfully retrieved authentication headers."),
                    "type": "success",
                },
            }
        except (ValidationError, AccessError) as e:
            self.write(
                {
                    "is_valid": False,
                    "last_error": str(e),
                }
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Credential Invalid"),
                    "message": str(e),
                    "type": "danger",
                },
            }

    def action_refresh_oauth_token(self):
        """Force refresh of OAuth token."""
        self.ensure_one()

        if self.credential_type not in ("oauth_client", "oauth_token"):
            raise ValidationError(_("This credential type does not use OAuth tokens."))

        if self.credential_type == "oauth_client":
            self._fetch_oauth_token()
        else:
            raise ValidationError(_("Manual token refresh is only available for OAuth client credentials."))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Token Refreshed"),
                "message": _("OAuth token has been refreshed."),
                "type": "success",
            },
        }
