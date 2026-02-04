import logging
from datetime import timedelta

import httpx

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services.errors import format_connection_error, format_http_error

_logger = logging.getLogger(__name__)


class DCIDataSource(models.Model):
    """DCI Data Source Configuration.

    Manages connection configuration for external DCI registries including
    OAuth2 authentication, SSL verification, and request signing.
    """

    _name = "spp.dci.data.source"
    _description = "DCI Data Source"
    _order = "name"

    name = fields.Char(
        required=True,
        string="Name",
        help="Descriptive name for this data source",
    )
    code = fields.Char(
        required=True,
        string="Code",
        help="Short code identifier (e.g., 'crvs_main', 'ibr_national')",
    )
    registry_type = fields.Selection(
        selection="_get_registry_types",
        string="Registry Type",
        help="Type of DCI registry",
    )
    base_url = fields.Char(
        required=True,
        string="Base URL",
        help="Base URL of the DCI API (e.g., https://crvs.example.org/api/v1)",
    )
    auth_type = fields.Selection(
        [
            ("none", "None"),
            ("bearer", "Bearer Token"),
            ("basic", "Basic Authentication"),
            ("oauth2", "OAuth2"),
        ],
        default="oauth2",
        required=True,
        string="Authentication Type",
        help="Authentication method for API requests",
    )
    bearer_token = fields.Char(
        string="Bearer Token",
        groups="base.group_system",
        help="Static Bearer token for API authentication (visible only to system administrators)",
    )
    oauth2_token_url = fields.Char(
        string="OAuth2 Token URL",
        help="OAuth2 token endpoint URL",
    )
    oauth2_client_id = fields.Char(
        string="OAuth2 Client ID",
        help="OAuth2 client identifier",
    )
    oauth2_client_secret = fields.Char(
        string="OAuth2 Client Secret",
        groups="base.group_system",
        help="OAuth2 client secret (visible only to system administrators)",
    )
    oauth2_scope = fields.Char(
        string="OAuth2 Scope",
        help="OAuth2 scope (space-separated if multiple)",
    )
    oauth2_credential_location = fields.Selection(
        [
            ("body", "Request Body (RFC 6749 Standard)"),
            ("query", "Query Parameters (OpenCRVS Workaround)"),
        ],
        default="body",
        string="OAuth2 Credential Location",
        help="Where to send OAuth2 credentials. RFC 6749 standard is request body, "
        "but some servers (e.g., OpenCRVS) require query parameters.",
    )
    signing_key_id = fields.Many2one(
        "spp.dci.signing.key",
        string="Signing Key",
        help="Cryptographic key for signing outgoing requests",
        domain=[("state", "=", "active")],
    )
    verify_ssl = fields.Boolean(
        default=True,
        string="Verify SSL",
        help="Verify SSL certificates when making requests",
    )
    timeout = fields.Integer(
        default=30,
        string="Timeout (seconds)",
        help="Request timeout in seconds",
    )
    active = fields.Boolean(
        default=True,
        string="Active",
        help="Set to false to deactivate this data source",
    )
    notes = fields.Text(
        string="Notes",
        help="Optional notes about this data source",
    )

    # DCI Protocol fields
    our_sender_id = fields.Char(
        string="Our Sender ID",
        help="Our organization's sender ID for DCI messages (e.g., 'openspp.example.org')",
    )
    our_callback_uri = fields.Char(
        string="Callback URI",
        help="Our callback URI for receiving async responses and notifications",
    )
    receiver_id = fields.Char(
        string="Receiver ID",
        help="Target registry's receiver ID (defaults to base URL if not set)",
    )

    # API Endpoint paths (optional, defaults provided)
    search_endpoint = fields.Char(
        string="Search Endpoint",
        default="/registry/sync/search",
        help="Path to search endpoint (default: /registry/sync/search)",
    )
    subscribe_endpoint = fields.Char(
        string="Subscribe Endpoint",
        default="/registry/subscribe",
        help="Path to subscribe endpoint (default: /registry/subscribe)",
    )
    auth_endpoint = fields.Char(
        string="Auth Endpoint",
        default="/oauth2/client/token",
        help="Path to OAuth2 token endpoint (default: /oauth2/client/token)",
    )

    # Connection status tracking
    state = fields.Selection(
        [
            ("draft", "Not Configured"),
            ("testing", "Testing"),
            ("active", "Active"),
            ("error", "Connection Error"),
        ],
        default="draft",
        string="Status",
        tracking=True,
        help="Connection status",
    )
    last_test_date = fields.Datetime(
        string="Last Test",
        readonly=True,
        help="Last successful connection test",
    )
    last_error = fields.Text(
        string="Last Error",
        readonly=True,
        help="Last connection error message",
    )

    # OAuth2 token cache fields (transient storage)
    _oauth2_access_token = fields.Char(
        string="Cached Access Token",
        help="Cached OAuth2 access token (internal use only)",
    )
    _oauth2_token_expires_at = fields.Datetime(
        string="Token Expiry",
        help="Cached token expiration timestamp (internal use only)",
    )

    @api.constrains("code")
    def _check_code_unique(self):
        """Ensure code is unique across all data sources."""
        for record in self:
            if record.code:
                duplicate = self.search(
                    [("code", "=", record.code), ("id", "!=", record.id)],
                    limit=1,
                )
                if duplicate:
                    raise ValidationError(_("Data source code must be unique. Please choose a different code."))

    @api.model
    def _get_registry_types(self):
        """Get registry type selection values from DCI constants."""
        from odoo.addons.spp_dci.schemas.constants import RegistryType

        return [
            (RegistryType.SOCIAL_REGISTRY.value, "Social Registry"),
            (RegistryType.IBR.value, "Integrated Beneficiary Registry (IBR)"),
            (RegistryType.CRVS.value, "Civil Registration and Vital Statistics (CRVS)"),
            (RegistryType.DISABILITY_REGISTRY.value, "Disability Registry (DR)"),
            (RegistryType.FUNCTIONAL_REGISTRY.value, "Functional Registry (FR)"),
        ]

    @api.constrains("code")
    def _check_code_format(self):
        """Validate code format - lowercase alphanumeric and underscores only."""
        for record in self:
            if record.code and not all(c.isalnum() or c == "_" for c in record.code):
                raise ValidationError(_("Code must contain only lowercase alphanumeric characters and underscores."))
            if record.code and not record.code.islower():
                raise ValidationError(_("Code must be lowercase."))

    @api.constrains("base_url")
    def _check_base_url_format(self):
        """Validate base URL format."""
        for record in self:
            if record.base_url:
                if not record.base_url.startswith(("http://", "https://")):
                    raise ValidationError(_("Base URL must start with http:// or https://"))
                if record.base_url.endswith("/"):
                    raise ValidationError(_("Base URL should not end with a slash"))

    @api.constrains("auth_type", "oauth2_token_url", "oauth2_client_id", "oauth2_client_secret")
    def _check_oauth2_fields(self):
        """Validate OAuth2 configuration fields."""
        for record in self:
            if record.auth_type == "oauth2":
                if not record.oauth2_token_url:
                    raise ValidationError(_("OAuth2 Token URL is required when using OAuth2 authentication."))
                if not record.oauth2_client_id:
                    raise ValidationError(_("OAuth2 Client ID is required when using OAuth2 authentication."))
                if not record.oauth2_client_secret:
                    raise ValidationError(_("OAuth2 Client Secret is required when using OAuth2 authentication."))

    @api.constrains("auth_type", "bearer_token")
    def _check_bearer_token(self):
        """Validate Bearer token configuration."""
        for record in self:
            if record.auth_type == "bearer" and not record.bearer_token:
                raise ValidationError(_("Bearer Token is required when using Bearer Token authentication."))

    @api.constrains("timeout")
    def _check_timeout_value(self):
        """Validate timeout value - must be positive."""
        for record in self:
            # Check for non-positive values (including 0 and negative)
            if record.timeout is not False and record.timeout <= 0:
                raise ValidationError(_("Timeout must be a positive integer."))

    @api.constrains("auth_type", "our_sender_id")
    def _check_sender_id(self):
        """Validate sender ID is set for authenticated connections."""
        for record in self:
            if record.auth_type != "none" and not record.our_sender_id:
                raise ValidationError(_("Sender ID is required for authenticated connections."))

    def clear_oauth2_token_cache(self):
        """Clear cached OAuth2 token, forcing a fresh token request on next use.

        This can be useful when the cached token becomes invalid or when
        troubleshooting authentication issues.
        """
        self.ensure_one()
        self.write(
            {
                "_oauth2_access_token": False,
                "_oauth2_token_expires_at": False,
            }
        )
        _logger.info("Cleared OAuth2 token cache for data source: %s", self.code)

    def get_oauth2_token(self, force_refresh=False):
        """Get or refresh OAuth2 access token.

        Args:
            force_refresh: If True, skip cache and fetch a new token

        Returns:
            str: Valid OAuth2 access token

        Raises:
            UserError: If token request fails or configuration is invalid
        """
        self.ensure_one()

        if self.auth_type != "oauth2":
            raise UserError(_("This data source does not use OAuth2 authentication."))

        # Check if cached token is still valid (with 60 second buffer)
        now = fields.Datetime.now()
        if not force_refresh and self._oauth2_access_token and self._oauth2_token_expires_at:
            expiry_with_buffer = self._oauth2_token_expires_at - timedelta(seconds=60)
            if now < expiry_with_buffer:
                _logger.info(
                    "Using cached OAuth2 token for data source: %s (expires at %s)",
                    self.code,
                    self._oauth2_token_expires_at,
                )
                return self._oauth2_access_token

        # Request new token
        _logger.info("Requesting new OAuth2 token for data source: %s", self.code)

        try:
            token_data = {
                "grant_type": "client_credentials",
                "client_id": self.oauth2_client_id,
                "client_secret": self.oauth2_client_secret,
            }

            if self.oauth2_scope:
                token_data["scope"] = self.oauth2_scope

            with httpx.Client(verify=self.verify_ssl, timeout=self.timeout) as client:
                # RFC 6749 standard: credentials in request body
                # Some servers (OpenCRVS) require query parameters instead
                if self.oauth2_credential_location == "query":
                    response = client.post(
                        self.oauth2_token_url,
                        params=token_data,
                    )
                else:
                    response = client.post(
                        self.oauth2_token_url,
                        data=token_data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                response.raise_for_status()

            token_response = response.json()
            access_token = token_response.get("access_token")
            expires_in = token_response.get("expires_in", 3600)  # Default 1 hour

            if not access_token:
                raise UserError(_("OAuth2 token response did not contain access_token"))

            # Cache token with expiry
            expires_at = now + timedelta(seconds=expires_in)
            self.write(
                {
                    "_oauth2_access_token": access_token,
                    "_oauth2_token_expires_at": expires_at,
                }
            )

            _logger.info(
                "Successfully obtained OAuth2 token for data source: %s (expires in %s seconds)",
                self.code,
                expires_in,
            )

            return access_token

        except httpx.HTTPStatusError as e:
            # Log technical details for troubleshooting
            _logger.error(
                "OAuth2 token request failed for data source %s: HTTP %s - %s",
                self.code,
                e.response.status_code,
                e.response.text,
            )
            # Show user-friendly message
            user_msg = format_http_error(e.response.status_code, e.response.text)
            raise UserError(user_msg) from e

        except httpx.RequestError as e:
            # Log technical details for troubleshooting
            _logger.error("OAuth2 token request failed for data source %s: %s", self.code, str(e))

            # Determine error type for user-friendly message
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                connection_type = "timeout"
            elif "ssl" in error_str or "certificate" in error_str:
                connection_type = "ssl"
            elif "name or service not known" in error_str or "nodename nor servname" in error_str:
                connection_type = "dns"
            else:
                connection_type = "connection"

            # Show user-friendly message
            user_msg = format_connection_error(connection_type, str(e))
            raise UserError(user_msg) from e

        except Exception as e:
            # Log technical details for troubleshooting
            _logger.error(
                "Unexpected error during OAuth2 token request for data source %s: %s",
                self.code,
                str(e),
            )
            # Show generic user-friendly message
            raise UserError(_("An unexpected error occurred. Please contact your administrator.")) from e

    def get_headers(self, force_refresh_token=False):
        """Get HTTP headers for API requests including authentication.

        Args:
            force_refresh_token: If True, force refresh OAuth2 token (skip cache)

        Returns:
            dict: HTTP headers for API requests

        Raises:
            UserError: If authentication setup fails
        """
        self.ensure_one()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        _logger.debug(
            "get_headers() called for data source %s, auth_type=%s, force_refresh=%s",
            self.code,
            self.auth_type,
            force_refresh_token,
        )

        if self.auth_type == "oauth2":
            _logger.info("Fetching OAuth2 token for data source %s", self.code)
            token = self.get_oauth2_token(force_refresh=force_refresh_token)
            headers["Authorization"] = f"Bearer {token}"
            _logger.info(
                "Added OAuth2 Authorization header for data source %s (token length: %d)",
                self.code,
                len(token) if token else 0,
            )
        elif self.auth_type == "bearer":
            if not self.bearer_token:
                raise UserError(_("Bearer token is not configured for this data source."))
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        elif self.auth_type == "basic":
            # Basic auth would require username/password fields (not in current spec)
            raise UserError(_("Basic authentication is not yet implemented."))

        return headers

    def test_connection(self):
        """Test connection to the DCI endpoint.

        This action tests the connection configuration by attempting to reach
        the base URL with proper authentication.

        Returns:
            dict: Action notification with test results
        """
        self.ensure_one()

        _logger.info("Testing connection to data source: %s (%s)", self.name, self.code)

        try:
            headers = self.get_headers()

            # Test connection with a simple request to base URL
            # Most DCI APIs have a health or info endpoint at root
            test_url = f"{self.base_url}/health"

            with httpx.Client(verify=self.verify_ssl, timeout=self.timeout) as client:
                response = client.get(test_url, headers=headers)

                # Consider 200, 404, and 405 as "connection successful"
                # (404/405 mean we reached the server, just wrong endpoint)
                if response.status_code in (200, 404, 405):
                    _logger.info(
                        "Connection test successful for data source %s: HTTP %s",
                        self.code,
                        response.status_code,
                    )
                    # Update state to active and record test date
                    self.write(
                        {
                            "state": "active",
                            "last_test_date": fields.Datetime.now(),
                            "last_error": False,
                        }
                    )
                    return {
                        "type": "ir.actions.client",
                        "tag": "display_notification",
                        "params": {
                            "title": _("Connection Successful"),
                            "message": _("Successfully connected to %s at %s (HTTP %s)")
                            % (self.name, self.base_url, response.status_code),
                            "type": "success",
                            "sticky": False,
                        },
                    }
                else:
                    raise httpx.HTTPStatusError(
                        f"Unexpected status code: {response.status_code}",
                        request=response.request,
                        response=response,
                    )

        except httpx.HTTPStatusError as e:
            # Log technical details for troubleshooting
            _logger.error(
                "Connection test failed for data source %s: HTTP %s - %s",
                self.code,
                e.response.status_code,
                e.response.text[:200],
            )
            # Show user-friendly message
            error_msg = format_http_error(e.response.status_code, e.response.text[:200])
            # Update state to error and record error message
            self.write(
                {
                    "state": "error",
                    "last_error": str(error_msg),
                }
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Failed"),
                    "message": error_msg,
                    "type": "danger",
                    "sticky": True,
                },
            }

        except httpx.RequestError as e:
            # Log technical details for troubleshooting
            _logger.error("Connection test failed for data source %s: %s", self.code, str(e))

            # Determine error type for user-friendly message
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                connection_type = "timeout"
            elif "ssl" in error_str or "certificate" in error_str:
                connection_type = "ssl"
            elif "name or service not known" in error_str or "nodename nor servname" in error_str:
                connection_type = "dns"
            else:
                connection_type = "connection"

            # Show user-friendly message
            error_msg = format_connection_error(connection_type, str(e))
            # Update state to error and record error message
            self.write(
                {
                    "state": "error",
                    "last_error": str(error_msg),
                }
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Failed"),
                    "message": error_msg,
                    "type": "danger",
                    "sticky": True,
                },
            }

        except Exception as e:
            # Log technical details for troubleshooting
            _logger.error("Connection test failed for data source %s: %s", self.code, str(e))
            # Show generic user-friendly message
            error_msg = _("An unexpected error occurred. Please contact your administrator.")
            # Update state to error and record error message
            self.write(
                {
                    "state": "error",
                    "last_error": str(error_msg),
                }
            )
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Connection Test Error"),
                    "message": error_msg,
                    "type": "danger",
                    "sticky": True,
                },
            }

    def action_test_connection(self):
        """Button action to test connection (alias for test_connection)."""
        return self.test_connection()

    @api.model
    def get_by_code(self, code):
        """Get data source by code.

        Args:
            code (str): Data source code

        Returns:
            spp.dci.data.source: Data source record

        Raises:
            UserError: If data source not found
        """
        data_source = self.search([("code", "=", code), ("active", "=", True)], limit=1)
        if not data_source:
            raise UserError(_("Data source with code '%s' not found or is inactive.") % code)
        return data_source

    @api.model
    def get_by_registry_type(self, registry_type):
        """Get all data sources for a specific registry type.

        Args:
            registry_type (str): Registry type from RegistryType enum

        Returns:
            spp.dci.data.source: Recordset of data sources
        """
        return self.search([("registry_type", "=", registry_type), ("active", "=", True)])
