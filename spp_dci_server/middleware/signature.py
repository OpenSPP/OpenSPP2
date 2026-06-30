# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI API signature verification middleware and dependencies."""

import hmac
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import Depends, Header, HTTPException, status

_logger = logging.getLogger(__name__)


# Fail-closed defaults for every dev-mode flag the middleware honours.
# Bypass flags default to "false" (no bypass); the new
# ``dci.api_tokens_required`` defaults to "true" (required) so an empty
# token list rejects all traffic rather than accepting any token.
_SECURITY_FLAG_DEFAULTS = {
    "dci.allow_unsigned_requests": "false",
    "dci.bypass_bearer_auth": "false",
    "dci.allow_http_callbacks": "false",
    "dci.allow_internal_callback_ips": "false",
    "dci.api_tokens_required": "true",
}


def _read_security_flag(env: Environment, key: str) -> str:
    """Read a DCI security flag, applying the fail-closed in-code default.

    Centralising the defaults makes the pinning tests in
    ``test_bearer_middleware.TestSecurityDefaults`` straightforward and
    keeps every call site honest about what "unset" means.
    """
    default = _SECURITY_FLAG_DEFAULTS[key]
    # nosemgrep: odoo-sudo-without-context
    value = env["ir.config_parameter"].sudo().get_param(key, default)
    return (value or default).lower()


class DCIHTTPException(HTTPException):
    """Custom HTTPException that formats errors according to DCI specification.

    This exception stores the error in DCI-compliant format. The body is stored
    in a special attribute `dci_body` that is recognized by our patched
    convert_exception_to_status_body function.
    """

    def __init__(
        self,
        status_code: int,
        error_message: str,
        error_code: str | None = None,
        headers: dict[str, str] | None = None,
    ):
        # Build DCI-compliant error response body
        self.dci_body = {
            "message": {
                "ack_status": "ERR",
                "timestamp": datetime.now(UTC).isoformat(),
                "correlation_id": str(uuid.uuid4()),
                "error": {
                    "code": error_code or f"err.{status_code}",
                    "message": error_message,
                },
            }
        }
        # Keep standard detail for logging purposes
        super().__init__(status_code=status_code, detail=error_message, headers=headers)


# Monkey-patch convert_exception_to_status_body to handle DCIHTTPException
# We need to patch it in multiple places since it's imported directly
from odoo.addons.fastapi import error_handlers as fastapi_error_handlers  # noqa: E402
from odoo.addons.fastapi import fastapi_dispatcher as fastapi_dispatcher_module  # noqa: E402

_original_convert_exception = fastapi_error_handlers.convert_exception_to_status_body


def _patched_convert_exception_to_status_body(exc: Exception) -> tuple[int, dict]:
    """Patched version that handles DCIHTTPException specially."""
    # Handle DCIHTTPException with proper DCI format
    if isinstance(exc, DCIHTTPException):
        return exc.status_code, exc.dci_body

    # Fall back to original implementation
    return _original_convert_exception(exc)


# Apply the patch to both the error_handlers module and the dispatcher module
fastapi_error_handlers.convert_exception_to_status_body = _patched_convert_exception_to_status_body
fastapi_dispatcher_module.convert_exception_to_status_body = _patched_convert_exception_to_status_body

# Track if we've already logged the dev mode warning this session
_dev_mode_warning_logged = False


def _check_and_warn_dev_mode(env: Environment) -> bool:
    """Check if dev mode is enabled and log appropriate warnings.

    Args:
        env: Odoo environment

    Returns:
        bool: True if dev mode (allow_unsigned) is enabled
    """
    global _dev_mode_warning_logged

    allow_unsigned = _read_security_flag(env, "dci.allow_unsigned_requests") == "true"

    if allow_unsigned and not _dev_mode_warning_logged:
        # Log CRITICAL warning once per session
        _logger.critical(
            "SECURITY WARNING: DCI signature verification is DISABLED! "
            "The system parameter 'dci.allow_unsigned_requests' is set to 'true'. "
            "This allows ANY request to bypass signature verification. "
            "SET THIS TO 'false' IN PRODUCTION ENVIRONMENTS!"
        )
        _dev_mode_warning_logged = True

    return allow_unsigned


async def verify_dci_signature(
    request_envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
) -> str:
    """
    Verify DCI HTTP Signature and return sender_id.

    This dependency validates the signature in the DCI envelope using the
    sender's registered public key.

    Args:
        request_envelope: DCI envelope with signature, header, and message
        env: Odoo environment

    Returns:
        str: Validated sender_id

    Raises:
        HTTPException: If signature verification fails (401) or other errors
    """
    try:
        # Check if unsigned requests are allowed (development mode)
        # This also logs a CRITICAL warning if dev mode is enabled
        allow_unsigned = _check_and_warn_dev_mode(env)

        # Extract sender_id from header
        sender_id = request_envelope.header.sender_id
        if not sender_id:
            _logger.warning("DCI request missing sender_id in header")
            raise DCIHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_message="Missing sender_id in message header",
                error_code="err.request.missing_sender_id",
            )

        # Check if signature is present
        if not request_envelope.signature or request_envelope.signature == "unsigned-stub":
            if allow_unsigned:
                _logger.warning(
                    "Accepting unsigned DCI request from %s (development mode enabled)",
                    sender_id,
                )
                return sender_id
            else:
                _logger.warning("DCI request from %s is missing signature", sender_id)
                raise DCIHTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    error_message="Missing signature in envelope",
                    error_code="err.signature.missing",
                )

        # Look up sender in registry. Require an ACTIVE record: a deactivated
        # sender must not authenticate (and downstream consent resolution also
        # requires active, so accepting an inactive sender here would desync).
        # nosemgrep: odoo-sudo-without-context
        sender_registry = (
            env["spp.dci.sender.registry"]
            .sudo()
            .search([("sender_id", "=", sender_id), ("active", "=", True)], limit=1)
        )

        if not sender_registry:
            _logger.warning("Unknown sender_id (inactive or unregistered) in DCI request: %s", sender_id)
            raise DCIHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_message=f"Unknown sender_id: {sender_id}",
                error_code="err.sender.unknown",
            )

        # Get DCIVerifier from the sender registry record
        try:
            verifier = sender_registry.get_verifier()
        except Exception as e:
            # Verifier initialization failure is an auth failure (sender not properly configured)
            _logger.warning(
                "Failed to get verifier for sender %s: %s",
                sender_id,
                str(e),
            )
            raise DCIHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_message="Sender signature verification not configured",
                error_code="err.signature.verifier_not_configured",
            ) from e

        # Verify signature against header and message
        # Use mode="json" to ensure datetime fields are serialized to ISO strings
        # matching the format used when signing the original request
        is_valid = verifier.verify(
            request_envelope.signature,
            request_envelope.header.model_dump(mode="json"),
            request_envelope.message,
        )

        if not is_valid:
            _logger.warning(
                "Invalid signature for DCI request from sender_id: %s",
                sender_id,
            )
            raise DCIHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_message="Invalid signature",
                error_code="err.signature.invalid",
            )

        _logger.info("DCI signature verified successfully for sender: %s", sender_id)
        return sender_id

    except (HTTPException, DCIHTTPException):
        raise
    except Exception as e:
        _logger.error("Error verifying DCI signature: %s", str(e), exc_info=True)
        raise DCIHTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_message="Signature verification error",
            error_code="err.signature.verification_error",
        ) from e


# Track if we've already logged the bearer auth bypass warning
_bearer_bypass_warning_logged = False

# Track if we've already logged the empty-tokens-but-not-required warning
_empty_tokens_warning_logged = False


def _validate_oauth2_jwt(env: Environment, token: str) -> str | None:
    """Return the client_id when ``token`` is a valid OAuth2 access token.

    Lets a DCI caller authenticate with an OAuth2 client-credentials JWT issued
    by spp_api_v2 (``POST /api_v2/oauth/token``) instead of a static bearer
    token. The JWT is validated with spp_api_v2's own verifier (HS256 signature,
    ``iss``/``aud``, expiry), then the ``client_id`` claim must resolve to an
    active ``spp.api.client``.

    Returns the client_id on success, or ``None`` on any failure (bad signature,
    expired, wrong issuer/audience, secret unset, unknown/inactive client, or a
    non-JWT opaque token) so the caller can fall back to other auth paths.
    """
    try:
        from odoo.addons.spp_api_v2.middleware.auth import _validate_jwt_token
    except ImportError:
        return None
    try:
        payload = _validate_jwt_token(env, token)
    except Exception:
        # Not a valid spp_api_v2 JWT — fall back to static-token handling.
        return None
    client_id = payload.get("client_id")
    if not client_id:
        return None
    # nosemgrep: odoo-sudo-without-context
    client = env["spp.api.client"].sudo().search([("client_id", "=", client_id), ("active", "=", True)], limit=1)
    if not client:
        _logger.warning("OAuth2 JWT names unknown/inactive client_id: %s", client_id)
        return None
    _logger.debug("DCI request authenticated via OAuth2 JWT for client %s", client_id)
    return client_id


async def verify_bearer_token(
    env: Annotated[Environment, Depends(odoo_env)],
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """
    Verify Bearer token authentication.

    This dependency validates the Authorization header contains a valid Bearer token.
    The accepted tokens can be configured via system parameter 'dci.api_tokens'.

    Args:
        env: Odoo environment
        authorization: Authorization header value

    Returns:
        str: The validated token (without 'Bearer ' prefix)

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    global _bearer_bypass_warning_logged

    # Check if bearer auth is bypassed (development mode)
    bypass_bearer = _read_security_flag(env, "dci.bypass_bearer_auth") == "true"

    if bypass_bearer:
        if not _bearer_bypass_warning_logged:
            _logger.critical(
                "SECURITY WARNING: DCI Bearer token authentication is DISABLED! "
                "The system parameter 'dci.bypass_bearer_auth' is set to 'true'. "
                "This allows ANY request without authentication. "
                "SET THIS TO 'false' IN PRODUCTION ENVIRONMENTS!"
            )
            _bearer_bypass_warning_logged = True
        return "development-bypass"

    # Check if Authorization header is present
    if not authorization:
        _logger.warning("DCI request missing Authorization header")
        raise DCIHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_message="Missing Authorization header",
            error_code="err.auth.missing_header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check Bearer prefix
    if not authorization.startswith("Bearer "):
        _logger.warning("DCI request has invalid Authorization format (not Bearer)")
        raise DCIHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_message="Invalid authorization format. Expected: Bearer <token>",
            error_code="err.auth.invalid_format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Strip "Bearer " prefix

    if not token:
        _logger.warning("DCI request has empty Bearer token")
        raise DCIHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_message="Empty Bearer token",
            error_code="err.auth.empty_token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get accepted tokens from config (comma-separated list). An empty
    # config used to mean "accept any non-empty token" - a fail-open
    # default that exposed every bearer-authenticated route the moment
    # the module was installed. The new behaviour is to reject when the
    # list is empty unless the operator explicitly opts out via
    # ``dci.api_tokens_required=false`` (mirrors the existing
    # ``dci.bypass_bearer_auth`` pattern).
    # nosemgrep: odoo-sudo-without-context
    accepted_tokens_str = env["ir.config_parameter"].sudo().get_param("dci.api_tokens", "")
    if accepted_tokens_str:
        accepted_tokens = [t.strip() for t in accepted_tokens_str.split(",") if t.strip()]
        # Constant-time comparison against every configured token. Using
        # ``token in accepted_tokens`` would short-circuit on the first
        # mismatch and leak token-prefix information through response
        # latency.
        matched = False
        for candidate in accepted_tokens:
            if hmac.compare_digest(token, candidate):
                matched = True
        if matched:
            _logger.debug("Bearer token validated against configured tokens")
            return token
        # Not a configured static token — it may be an OAuth2 access token.
        if _validate_oauth2_jwt(env, token):
            return token
        _logger.warning("DCI request has invalid Bearer token")
        raise DCIHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_message="Invalid Bearer token",
            error_code="err.auth.invalid_token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # No static tokens configured: still accept a valid OAuth2 access token.
    if _validate_oauth2_jwt(env, token):
        return token

    # nosemgrep: odoo-timing-attack-password  # not a token compare; matches a config flag value
    tokens_required = _read_security_flag(env, "dci.api_tokens_required") == "true"
    if tokens_required:
        _logger.warning(
            "DCI request rejected: 'dci.api_tokens' is empty. "
            "Configure the parameter or set 'dci.api_tokens_required=false' "
            "for development."
        )
        raise DCIHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_message="No accepted Bearer tokens configured",
            error_code="err.auth.no_tokens_configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    global _empty_tokens_warning_logged
    if not _empty_tokens_warning_logged:
        _logger.critical(
            "SECURITY WARNING: DCI Bearer token list is empty and "
            "'dci.api_tokens_required' is 'false'. Any non-empty token is "
            "being accepted. CONFIGURE 'dci.api_tokens' AND SET "
            "'dci.api_tokens_required' TO 'true' IN PRODUCTION."
        )
        _empty_tokens_warning_logged = True
    return token
