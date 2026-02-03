# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OAuth 2.0 endpoints for API V2"""

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


@oauth_router.post("/oauth/token", response_model=TokenResponse)
async def get_token(
    http_request: Request,
    request: TokenRequest,
    env: Annotated[Environment, Depends(odoo_env)],
    _rate_limit: Annotated[None, Depends(check_auth_rate_limit)],
):
    """
    OAuth 2.0 Client Credentials flow.

    Authenticates API client and returns JWT access token.

    SECURITY: Rate limited to 5 requests/minute per IP to prevent brute force.
    """
    # Validate grant type
    if request.grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported grant_type. Only 'client_credentials' is supported.",
        )

    # Authenticate client
    api_client = env["spp.api.client"].sudo().authenticate(request.client_id, request.client_secret)

    if not api_client:
        _logger.warning("Failed authentication attempt for client_id: %s", request.client_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
        )

    # Generate JWT token
    try:
        token = _generate_jwt_token(env, api_client)
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
        expires_in=3600,  # 1 hour
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
        secret = env["ir.config_parameter"].sudo().get_param("spp_api_v2.jwt_secret")

    if not secret:
        raise UserError(
            "JWT secret not configured. "
            "Set OPENSPP_JWT_SECRET environment variable (recommended) "
            "or 'spp_api_v2.jwt_secret' in System Parameters."
        )

    return secret


def _generate_jwt_token(env: Environment, api_client) -> str:
    """
    Generate JWT access token for API client.

    Token contains:
    - client_id (external identifier, NOT database ID)
    - scopes
    - expiration (1 hour)

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
        "exp": now + timedelta(hours=1),  # Expiration
        "iat": now,  # Issued at
        "client_id": api_client.client_id,
        "scopes": [f"{s.resource}:{s.action}" for s in api_client.scope_ids],
    }

    # Sign token
    token = jwt.encode(payload, secret, algorithm="HS256")

    _logger.info("Generated JWT token for client: %s", api_client.client_id)

    return token
