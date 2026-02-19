# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CRVS DCI signature verification middleware for callback endpoints."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import Depends, HTTPException, status

_logger = logging.getLogger(__name__)


async def verify_crvs_signature(
    envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
) -> str:
    """
    Verify CRVS callback signature and return sender_id.

    This dependency validates the signature in the DCI envelope using the
    CRVS sender's registered public key from spp.dci.crvs.sender model.

    Args:
        envelope: DCI envelope with signature, header, and message
        env: Odoo environment

    Returns:
        str: Validated sender_id

    Raises:
        HTTPException: If signature verification fails (401) or other errors
    """
    try:
        # Check if unsigned requests are allowed (development mode)
        allow_unsigned = (
            # nosemgrep: odoo-sudo-without-context
            env["ir.config_parameter"].sudo().get_param("dci.allow_unsigned_requests", "false").lower() == "true"
        )

        # Extract sender_id from header
        sender_id = envelope.header.sender_id
        if not sender_id:
            _logger.warning("CRVS callback missing sender_id in header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing sender_id in message header",
            )

        # Check if signature is present
        if not envelope.signature or envelope.signature == "unsigned-stub":
            if allow_unsigned:
                _logger.warning(
                    "Accepting unsigned CRVS callback from %s (development mode enabled)",
                    sender_id,
                )
                return sender_id
            else:
                _logger.warning("CRVS callback from %s is missing signature", sender_id)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing signature in envelope",
                )

        # Look up CRVS sender in registry
        # nosemgrep: odoo-sudo-without-context
        crvs_sender = env["spp.dci.crvs.sender"].sudo().search([("sender_id", "=", sender_id)], limit=1)

        if not crvs_sender:
            _logger.warning("Unknown CRVS sender_id in callback: %s", sender_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Unknown CRVS sender_id: {sender_id}",
            )

        # Get DCIVerifier from the CRVS sender record
        try:
            verifier = crvs_sender.get_verifier()
        except Exception as e:
            _logger.error(
                "Failed to get verifier for CRVS sender %s: %s",
                sender_id,
                str(e),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize signature verifier",
            ) from e

        # Verify signature against header and message
        # Use mode="json" to ensure datetime fields are serialized to ISO strings
        # matching the format used when signing the original request
        is_valid = verifier.verify(
            envelope.signature,
            envelope.header.model_dump(mode="json"),
            envelope.message,
        )

        if not is_valid:
            _logger.warning(
                "Invalid signature for CRVS callback from sender_id: %s",
                sender_id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

        _logger.info("CRVS signature verified successfully for sender: %s", sender_id)
        return sender_id

    except HTTPException:
        raise
    except Exception as e:
        _logger.error("Error verifying CRVS signature: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signature verification error",
        ) from e
