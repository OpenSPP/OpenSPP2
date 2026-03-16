# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""RS256-aware authentication middleware for API V2.

Replaces get_authenticated_client via FastAPI dependency override.
Routes to RS256 or HS256 verification based on the JWT header's `alg` field.
"""

import logging
from typing import Annotated

import jwt

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import _validate_jwt_token
from odoo.addons.spp_oauth.tools import OpenSPPOAuthJWTException, get_public_key

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..constants import JWT_AUDIENCE, JWT_ISSUER

_logger = logging.getLogger(__name__)

# Must match the original security object's configuration
security = HTTPBearer(auto_error=False)


def get_authenticated_client_rs256(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    env: Annotated[Environment, Depends(odoo_env)],
):
    """Validate JWT token (RS256 or HS256) and return authenticated API client.

    This function replaces spp_api_v2's get_authenticated_client via
    FastAPI dependency_overrides. It reads the JWT header's `alg` field
    to route to the correct verification path.

    RS256 tokens are verified using the RSA public key from spp_oauth.
    HS256 tokens are delegated to the original spp_api_v2 verification.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Read the algorithm from the JWT header (unverified) to route verification
        try:
            header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from e

        alg = header.get("alg", "")

        if alg == "RS256":
            payload = _validate_rs256_token(env, token)
        elif alg == "HS256":
            payload = _validate_jwt_token(env, token)
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unsupported token algorithm: {alg}",
            )

        # Look up API client by client_id from payload
        client_id = payload.get("client_id")
        if not client_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing client_id",
            )

        api_client = (
            env["spp.api.client"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [
                    ("client_id", "=", client_id),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )

        if not api_client:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Client not found or inactive",
            )

        return api_client

    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Authentication error")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        ) from e


def _validate_rs256_token(env: Environment, token: str) -> dict:
    """Validate an RS256-signed JWT token.

    Uses the RSA public key from spp_oauth and validates audience, issuer,
    and expiration claims to match the same security requirements as the
    HS256 path in spp_api_v2.
    """
    try:
        public_key = get_public_key(env)
    except OpenSPPOAuthJWTException as e:
        _logger.warning("RS256 verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="RS256 authentication not available",
        ) from e

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        return payload

    except jwt.ExpiredSignatureError as e:
        _logger.warning("Expired RS256 JWT token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from e

    except jwt.InvalidTokenError as e:
        _logger.warning("Invalid RS256 JWT token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e
