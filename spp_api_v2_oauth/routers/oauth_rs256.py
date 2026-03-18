# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""RS256 OAuth token generation endpoint for API V2."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt as pyjwt

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.rate_limit import check_auth_rate_limit
from odoo.addons.spp_api_v2.routers.oauth import TokenRequest, TokenResponse, _parse_token_request
from odoo.addons.spp_oauth.tools import OpenSPPOAuthJWTException, get_private_key

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..constants import JWT_AUDIENCE, JWT_ISSUER

_logger = logging.getLogger(__name__)

oauth_rs256_router = APIRouter(tags=["OAuth RS256"])

DEFAULT_TOKEN_LIFETIME_HOURS = 24


@oauth_rs256_router.post("/oauth/token/rs256", response_model=TokenResponse)
async def get_rs256_token(
    http_request: Request,
    token_request: Annotated[TokenRequest, Depends(_parse_token_request)],
    env: Annotated[Environment, Depends(odoo_env)],
    _rate_limit: Annotated[None, Depends(check_auth_rate_limit)],
):
    """OAuth 2.0 Client Credentials flow with RS256 signing.

    Authenticates API client and returns a JWT access token signed with RS256.
    Requires RSA keys to be configured in spp_oauth settings.

    SECURITY: Rate limited to 5 requests/minute per IP to prevent brute force.
    """
    # Validate grant type
    if token_request.grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported grant_type. Only 'client_credentials' is supported.",
        )

    # Verify RSA private key is configured before authenticating
    try:
        private_key = get_private_key(env)
    except OpenSPPOAuthJWTException as e:
        _logger.warning("RS256 token generation failed: RSA keys not configured")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "RS256 token generation not available. RSA keys must be configured in Settings > SPP OAuth Settings."
            ),
        ) from e

    # Authenticate client (same scrypt verification as HS256 endpoint)
    # nosemgrep: odoo-sudo-without-context
    api_client = env["spp.api.client"].sudo().authenticate(token_request.client_id, token_request.client_secret)

    if not api_client:
        _logger.warning("Failed authentication attempt for client_id: %s", token_request.client_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
        )

    # Read configurable token lifetime (same config as HS256 endpoint)
    config_param = env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
    try:
        token_lifetime_hours = int(
            config_param.get_param("spp_api_v2.token_lifetime_hours", str(DEFAULT_TOKEN_LIFETIME_HOURS))
        )
    except (ValueError, TypeError):
        _logger.warning("Invalid token_lifetime_hours config, using default %s", DEFAULT_TOKEN_LIFETIME_HOURS)
        token_lifetime_hours = DEFAULT_TOKEN_LIFETIME_HOURS
    expires_in = token_lifetime_hours * 3600

    # Generate RS256 JWT token
    try:
        token = _generate_rs256_jwt_token(private_key, api_client, token_lifetime_hours)
    except (ValueError, TypeError, pyjwt.PyJWTError) as e:
        _logger.exception("Error generating RS256 JWT token")
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


def _generate_rs256_jwt_token(private_key: str, api_client, token_lifetime_hours: int) -> str:
    """Generate JWT access token signed with RS256.

    Payload structure is identical to the HS256 token from spp_api_v2
    to ensure all downstream logic works without modification.

    SECURITY: Never include database IDs in JWT - use client_id only.
    """
    now = datetime.now(tz=UTC)
    payload = {
        "iss": JWT_ISSUER,
        "sub": api_client.client_id,
        "aud": JWT_AUDIENCE,
        "exp": now + timedelta(hours=token_lifetime_hours),
        "iat": now,
        "client_id": api_client.client_id,
        "scopes": [f"{s.resource}:{s.action}" for s in api_client.scope_ids],
    }

    token = pyjwt.encode(payload, private_key, algorithm="RS256")

    _logger.info("Generated RS256 JWT token for client: %s", api_client.client_id)

    return token
