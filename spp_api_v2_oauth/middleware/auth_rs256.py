# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""RS256-aware authentication middleware for API V2.

Replaces get_authenticated_client via FastAPI dependency override.
Routes verification based on the JWT header `alg` and (for RS256) the `iss`
claim:

  alg == HS256   -> delegated to spp_api_v2 (unchanged)
  alg == RS256   -> iss == JWT_ISSUER             -> spp_oauth public key
                 -> iss matches spp.oauth.issuer  -> static PEM or JWKS for that record
                 -> otherwise                      -> 401
  other          -> 401
"""

import logging
from typing import Annotated

import jwt
from jwt.exceptions import PyJWKClientError

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_api_v2.middleware.auth import _validate_jwt_token
from odoo.addons.spp_oauth.tools import OpenSPPOAuthJWTException, get_public_key

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..constants import JWT_AUDIENCE, JWT_CLOCK_SKEW_LEEWAY_SECONDS, JWT_ISSUER
from ..tools.jwks_cache import get_jwks_client

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
    to route to the correct verification path; for RS256 it additionally
    routes by the `iss` claim to support multiple trusted issuers.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.exceptions.DecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            ) from e

        alg = header.get("alg", "")

        if alg == "RS256":
            payload, issuer_rec = _validate_rs256_token_with_issuer(env, token)
        elif alg == "HS256":
            payload = _validate_jwt_token(env, token)
            issuer_rec = None
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unsupported token algorithm: {alg}",
            )

        # Determine which claim holds the API client identifier.
        claim_name = issuer_rec.client_claim if issuer_rec else "client_id"
        client_id = payload.get(claim_name)
        if not client_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: missing {claim_name}",
            )

        # SECURITY: Scope the client lookup by the resolved issuer record.
        # Internal-path tokens (HS256 + internal RS256) only match clients with no
        # oauth_issuer_id. External-issuer tokens only match clients explicitly
        # linked to that issuer record. Without this, an external IdP that emits
        # a claim value colliding with an internal client_id would authenticate
        # as the internal client.
        domain = [
            ("client_id", "=", client_id),
            ("active", "=", True),
        ]
        if issuer_rec:
            domain.append(("oauth_issuer_id", "=", issuer_rec.id))
        else:
            domain.append(("oauth_issuer_id", "=", False))

        api_client = (
            env["spp.api.client"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(domain, limit=1)
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


def _validate_rs256_token_with_issuer(env: Environment, token: str):
    """Validate an RS256-signed JWT and return (payload, issuer_record_or_None).

    Routing by `iss`:
      - iss == JWT_ISSUER ("openspp-api-v2")  -> internal path, key from spp_oauth
      - iss matches an active spp.oauth.issuer -> external path, key per record
      - iss missing or not matched              -> 401
    """
    # SECURITY: We read the iss claim BEFORE signature verification solely to
    # decide which key to verify with. ALL claim checks (signature, exp, nbf,
    # iat, aud, iss) are disabled here and are run authoritatively by the
    # verifying jwt.decode() inside _validate_internal_rs256 /
    # _validate_external_rs256 below. Disabling them here also keeps this routing
    # step from producing misleading errors (e.g. an expired token would bubble
    # up as a generic "Authentication failed" instead of "Token expired").
    try:
        unverified = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_nbf": False,
                "verify_iat": False,
                "verify_aud": False,
                "verify_iss": False,
            },
        )
    except jwt.exceptions.DecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e

    iss = unverified.get("iss")

    if iss == JWT_ISSUER:
        return _validate_internal_rs256(env, token), None

    if not iss:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing iss claim",
        )

    issuer_rec = (
        env["spp.oauth.issuer"]  # nosemgrep: odoo-sudo-without-context
        .sudo()
        .search([("issuer", "=", iss), ("active", "=", True)], limit=1)
    )
    if not issuer_rec:
        _logger.warning("RS256 token from unknown issuer: %s", iss)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Untrusted issuer",
        )

    return _validate_external_rs256(issuer_rec, token), issuer_rec


def _validate_internal_rs256(env: Environment, token: str) -> dict:
    """Verify a token signed by the internal openspp-api-v2 issuer."""
    try:
        public_key = get_public_key(env)
    except OpenSPPOAuthJWTException as e:
        _logger.warning("RS256 verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="RS256 authentication not available",
        ) from e

    try:
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            leeway=JWT_CLOCK_SKEW_LEEWAY_SECONDS,
        )
    except jwt.ExpiredSignatureError as e:
        _logger.warning("Expired RS256 JWT credential")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from e
    except jwt.InvalidTokenError as e:
        _logger.warning("RS256 JWT verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e


def _validate_external_rs256(issuer_rec, token: str) -> dict:
    """Verify a token signed by an externally-trusted issuer record."""
    algorithms = issuer_rec.get_allowed_algorithms()

    try:
        if issuer_rec.key_source == "jwks_uri":
            try:
                signing_key = get_jwks_client(issuer_rec).get_signing_key_from_jwt(token)
            except PyJWKClientError as e:
                _logger.warning("JWKS key resolution failed for issuer %s: %s", issuer_rec.issuer, e)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                ) from e
            key = signing_key.key
        else:
            key = issuer_rec.public_key

        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=issuer_rec.audience,
            issuer=issuer_rec.issuer,
            leeway=JWT_CLOCK_SKEW_LEEWAY_SECONDS,
        )
    except jwt.ExpiredSignatureError as e:
        _logger.warning("Expired RS256 JWT from issuer %s", issuer_rec.issuer)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from e
    except jwt.InvalidTokenError as e:
        _logger.warning("RS256 JWT verification failed for issuer %s: %s", issuer_rec.issuer, e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from e
