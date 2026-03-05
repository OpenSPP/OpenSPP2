# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OAuth 2.0 endpoints for API V2"""

import base64
import logging
import os
from datetime import datetime, timedelta
from typing import Annotated

from pydantic import BaseModel

from odoo.api import Environment
from odoo.exceptions import UserError

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..middleware.rate_limit import check_auth_rate_limit

_logger = logging.getLogger(__name__)

oauth_router = APIRouter(tags=["OAuth"])


class TokenRequest(BaseModel):
    """OAuth token request"""

    grant_type: str
    client_id: str
    client_secret: str


class TokenResponse(BaseModel):
    """OAuth token response"""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str


async def _parse_token_request(http_request: Request) -> TokenRequest:
    """Parse token request from JSON, form-encoded body, or HTTP Basic Auth.

    Supports three client authentication methods per RFC 6749:
    1. HTTP Basic Auth header (Section 2.3.1) - used by QGIS native OAuth2
    2. Form-encoded body with client_id/client_secret (Section 2.3.1)
    3. JSON body (non-standard, for backwards compatibility)
    """
    # Extract client credentials from Authorization: Basic header if present
    # (RFC 6749 Section 2.3.1 - preferred method for confidential clients)
    basic_client_id = ""
    basic_client_secret = ""
    auth_header = http_request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            if ":" in decoded:
                basic_client_id, basic_client_secret = decoded.split(":", 1)
        except (ValueError, UnicodeDecodeError) as e:
            _logger.debug("Failed to decode Basic Auth header: %s", e)

    content_type = http_request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form = await http_request.form()
        return TokenRequest(
            grant_type=form.get("grant_type", ""),
            client_id=form.get("client_id", "") or basic_client_id,
            client_secret=form.get("client_secret", "") or basic_client_secret,
        )

    # Try JSON body
    try:
        body = await http_request.json()
        return TokenRequest(**body)
    except Exception as e:
        _logger.debug("Could not parse token request from JSON body, falling back: %s", e)

    # Fall back to Basic Auth only (grant_type defaults to client_credentials)
    if basic_client_id:
        return TokenRequest(
            grant_type="client_credentials",
            client_id=basic_client_id,
            client_secret=basic_client_secret,
        )

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unable to parse token request. Send credentials via HTTP Basic Auth header, "
        "form-encoded body, or JSON body.",
    )


@oauth_router.post("/oauth/token", response_model=TokenResponse)
async def get_token(
    http_request: Request,
    token_request: Annotated[TokenRequest, Depends(_parse_token_request)],
    env: Annotated[Environment, Depends(odoo_env)],
    _rate_limit: Annotated[None, Depends(check_auth_rate_limit)],
):
    """
    OAuth 2.0 Client Credentials flow.

    Authenticates API client and returns JWT access token.
    Accepts both JSON and form-encoded request bodies (RFC 6749).

    SECURITY: Rate limited to 5 requests/minute per IP to prevent brute force.
    """
    # Validate grant type
    if token_request.grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported grant_type. Only 'client_credentials' is supported.",
        )

    # Authenticate client
    # nosemgrep: odoo-sudo-without-context
    api_client = env["spp.api.client"].sudo().authenticate(token_request.client_id, token_request.client_secret)

    if not api_client:
        _logger.warning("Failed authentication attempt for client_id: %s", token_request.client_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
        )

    # Read configurable token lifetime (default: 24 hours for long-lived sessions)
    # nosemgrep: odoo-sudo-without-context
    token_lifetime_hours = int(env["ir.config_parameter"].sudo().get_param("spp_api_v2.token_lifetime_hours", "24"))
    expires_in = token_lifetime_hours * 3600

    # Generate JWT token
    try:
        token = _generate_jwt_token(env, api_client, token_lifetime_hours)
    except Exception as e:
        _logger.exception("Error generating JWT token")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate access token",
        ) from e

    # Build scope string from client scopes
    scope_str = " ".join(f"{s.resource}:{s.action}" for s in api_client.scope_ids)

    return TokenResponse(
        access_token=token,
        token_type="Bearer",
        expires_in=expires_in,
        scope=scope_str,
    )


def _get_jwt_secret(env: Environment) -> str:
    """
    Get JWT secret from environment variable or config parameter.

    SECURITY: Environment variable is preferred for production as it:
    - Is not stored in database
    - Is not visible to Odoo users
    - Can be rotated without database access

    Priority:
    1. OPENSPP_JWT_SECRET environment variable
    2. spp_api_v2.jwt_secret system parameter

    Returns:
        JWT secret string

    Raises:
        UserError: If no secret is configured
    """
    # Try environment variable first (preferred for production)
    secret = os.environ.get("OPENSPP_JWT_SECRET")

    if not secret:
        # Fall back to config parameter
        # nosemgrep: odoo-sudo-without-context
        secret = env["ir.config_parameter"].sudo().get_param("spp_api_v2.jwt_secret")

    if not secret:
        raise UserError(
            "JWT secret not configured. "
            "Set OPENSPP_JWT_SECRET environment variable (recommended) "
            "or 'spp_api_v2.jwt_secret' in System Parameters."
        )

    return secret


def _generate_jwt_token(env: Environment, api_client, token_lifetime_hours: int) -> str:
    """
    Generate JWT access token for API client.

    Token contains:
    - client_id (external identifier, NOT database ID)
    - scopes
    - expiration time determined by token_lifetime_hours

    SECURITY: Never include database IDs in JWT.
    The auth middleware loads the full api_client record from DB using client_id.
    CRITICAL: JWT secret from environment variable or ir.config_parameter.
    """
    import jwt

    # Get JWT secret
    secret = _get_jwt_secret(env)

    # SECURITY: Validate secret strength before signing tokens
    from ..middleware.auth import _validate_jwt_secret_strength

    _validate_jwt_secret_strength(secret)

    # Build payload
    # SECURITY: Never include database IDs in JWT - use client_id only
    # The auth middleware looks up the full api_client record using client_id
    now = datetime.utcnow()
    payload = {
        "iss": "openspp-api-v2",  # Issuer
        "sub": api_client.client_id,  # Subject (client_id)
        "aud": "openspp",  # Audience
        "exp": now + timedelta(hours=token_lifetime_hours),  # Expiration
        "iat": now,  # Issued at
        "client_id": api_client.client_id,
        "scopes": [f"{s.resource}:{s.action}" for s in api_client.scope_ids],
    }

    # Sign token
    token = jwt.encode(payload, secret, algorithm="HS256")

    _logger.info("Generated JWT token for client: %s", api_client.client_id)

    return token
