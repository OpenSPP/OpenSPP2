# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""JWKS (JSON Web Key Set) endpoint for DCI API public key distribution."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends

_logger = logging.getLogger(__name__)

jwks_router = APIRouter(tags=["JWKS"])


@jwks_router.get("/.well-known/jwks.json")
async def get_jwks(
    env: Annotated[Environment, Depends(odoo_env)],
):
    """
    Get JSON Web Key Set (JWKS) containing active signing keys.

    Returns public keys in JWKS format for signature verification.
    External systems use these keys to verify signatures on messages from this server.

    **Authentication**: None (public endpoint)

    **Response Structure**:
    ```json
    {
        "keys": [
            {
                "kty": "OKP",
                "kid": "openspp|key1|ed25519",
                "use": "sig",
                "alg": "EdDSA",
                "crv": "Ed25519",
                "x": "base64url-encoded-public-key"
            }
        ]
    }
    ```

    **Key ID Format**: `{sender_id}|{key_id}|{algorithm}`

    **Supported Algorithms**:
    - Ed25519 (EdDSA) - Recommended
    - RSA-256 (RS256) - Legacy support
    """
    try:
        # Get active signing keys from database
        SigningKey = env["spp.dci.signing.key"].sudo()  # nosemgrep: odoo-sudo-without-context
        active_keys = SigningKey.search([("state", "=", "active")])

        if not active_keys:
            _logger.warning("No active DCI signing keys found for JWKS endpoint")
            return {"keys": []}

        # Build JWKS response
        jwks_keys = []
        for key in active_keys:
            try:
                jwks_entry = key.get_jwks_entry()
                jwks_keys.append(jwks_entry)
                _logger.debug(
                    "Added key to JWKS - kid: %s, algorithm: %s",
                    jwks_entry.get("kid"),
                    jwks_entry.get("alg"),
                )
            except Exception as e:
                _logger.error(
                    "Failed to generate JWKS entry for key %s: %s",
                    key.key_id,
                    str(e),
                )
                # Skip this key and continue with others
                continue

        _logger.info("JWKS endpoint served %d active keys", len(jwks_keys))

        return {"keys": jwks_keys}

    except Exception as e:
        _logger.error("Error generating JWKS response: %s", str(e), exc_info=True)
        # Return empty key set on error rather than failing
        # This prevents breaking external systems that cache JWKS
        return {"keys": []}
