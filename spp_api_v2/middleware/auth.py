# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Authentication middleware for API V2"""

import logging
import os
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2

_logger = logging.getLogger(__name__)

# OAuth2 Client Credentials scheme.
# This produces an "oauth2" entry in the OpenAPI securitySchemes with the
# clientCredentials flow pointing at our token endpoint, so API consumers
# (Swagger UI, QGIS, etc.) can discover how to authenticate.
# auto_error=False allows us to handle authentication errors with proper status codes.
security = OAuth2(
    flows={
        "clientCredentials": {
            "tokenUrl": "oauth/token",
            "scopes": {},
        },
    },
    auto_error=False,
)

# Cache for JWT secret validation results, keyed by hash of the secret.
# Avoids recomputing Shannon entropy on every API request.
_validated_jwt_secrets: set[str] = set()


def get_authenticated_client(
    token: Annotated[str | None, Depends(security)],
    env: Annotated[Environment, Depends(odoo_env)],
):
    """
    Validate JWT token and return authenticated API client.

    This dependency is used by all protected endpoints to:
    1. Extract Bearer token from Authorization header
    2. Validate JWT signature and expiration
    3. Load spp.api.client record
    4. Return client record for use in endpoint

    Raises:
        HTTPException: If token is invalid, expired, or client not found
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # OAuth2 dependency returns the full Authorization header value
    # (e.g. "Bearer eyJ..."). Strip the scheme prefix to get the raw JWT.
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    try:
        # Decode and validate JWT
        payload = _validate_jwt_token(env, token)

        # Load API client
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


def get_current_client(
    token: Annotated[str | None, Depends(security)],
    env: Annotated[Environment, Depends(odoo_env)],
) -> dict:
    """
    Get authenticated client with environment.

    Returns dict with both env and client for endpoints that need both.
    Used by consent router endpoints.

    Returns:
        dict: {"env": Environment, "client": spp.api.client record}
    """
    client = get_authenticated_client(token, env)
    return {"env": env, "client": client}


def _validate_jwt_secret_strength(secret: str) -> bool:
    """
    Validate JWT secret meets security requirements.

    SECURITY: Weak secrets can be brute-forced, enabling token forgery.
    Results are cached per secret to avoid recomputing entropy on every request.

    Args:
        secret: JWT secret string

    Returns:
        True if valid

    Raises:
        HTTPException: If secret is too weak
    """
    import hashlib
    import math
    from collections import Counter

    # Check cache — use hash of secret as key to avoid storing secrets in memory
    secret_hash = hashlib.sha256(secret.encode()).hexdigest()
    if secret_hash in _validated_jwt_secrets:
        return True

    # Minimum length: 32 characters (256 bits for HS256)
    if len(secret) < 32:
        _logger.error(
            "SECURITY: JWT secret is too short (%d chars). Must be >= 32 chars.",
            len(secret),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error",
        )

    # Check entropy (detect weak patterns like "aaaaaaa..." or "12345678...")
    char_counts = Counter(secret)
    entropy = -sum((count / len(secret)) * math.log2(count / len(secret)) for count in char_counts.values())

    # Minimum entropy of 3.0 bits per character (good randomness)
    if entropy < 3.0:
        _logger.error(
            "SECURITY: JWT secret has low entropy (%.2f). Use a cryptographically random value.",
            entropy,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error",
        )

    # Cache successful validation
    _validated_jwt_secrets.add(secret_hash)
    return True


def _validate_jwt_token(env: Environment, token: str) -> dict:
    """
    Validate JWT token and return payload.

    SECURITY: JWT secret is loaded from environment variable (preferred) or config parameter.

    Args:
        env: Odoo environment
        token: JWT token string

    Returns:
        Decoded payload dict

    Raises:
        HTTPException: If token is invalid or expired
    """
    import jwt

    # Get JWT secret - prefer environment variable for production security
    secret = os.environ.get("OPENSPP_JWT_SECRET")

    if not secret:
        # Fall back to config parameter
        # nosemgrep: odoo-sudo-without-context
        secret = env["ir.config_parameter"].sudo().get_param("spp_api_v2.jwt_secret")

    if not secret:
        _logger.error("JWT secret not configured - set OPENSPP_JWT_SECRET env var or spp_api_v2.jwt_secret")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error",
        )

    # SECURITY: Validate secret strength to prevent brute-force attacks
    _validate_jwt_secret_strength(secret)

    try:
        # Decode and validate token
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="openspp",
            issuer="openspp-api-v2",
        )

        return payload

    except jwt.ExpiredSignatureError as e:
        _logger.warning("Expired JWT token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from e

    except jwt.InvalidTokenError as e:
        _logger.warning("Invalid JWT token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e
