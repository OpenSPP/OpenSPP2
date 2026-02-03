# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Response helper functions.

Centralizes common response building operations for DCI server endpoints.
"""

import logging
import uuid
from datetime import UTC, datetime

from odoo.api import Environment

from ..schemas import (
    DCICallbackHeader,
    DCIEnvelope,
    SearchResponseItem,
)
from ..schemas.constants import SearchStatusReasonCode

_logger = logging.getLogger(__name__)

# Maximum length for status_reason_message per SPDCI spec (DCIError.message)
MAX_STATUS_MESSAGE_LENGTH = 999


def get_sender_id(env: Environment) -> str:
    """Get configured DCI sender ID.

    Args:
        env: Odoo environment

    Returns:
        str: Configured sender ID or 'openspp' default
    """
    return env["ir.config_parameter"].sudo().get_param("dci.sender_id", "openspp")


def truncate_message(message: str, max_length: int = MAX_STATUS_MESSAGE_LENGTH) -> str:
    """Truncate message to maximum allowed length per SPDCI spec.

    Args:
        message: Message to truncate
        max_length: Maximum length (default: MAX_STATUS_MESSAGE_LENGTH)

    Returns:
        str: Truncated message with ellipsis if needed
    """
    if not message:
        return ""
    if len(message) <= max_length:
        return message
    return message[: max_length - 3] + "..."


def build_error_search_response_item(
    reference_id: str,
    status_reason_code: SearchStatusReasonCode,
    status_reason_message: str,
    locale: str | None = None,
) -> SearchResponseItem:
    """Build a rejected SearchResponseItem with proper SPDCI codes.

    Args:
        reference_id: Original request reference ID
        status_reason_code: SPDCI-compliant reason code enum value
        status_reason_message: Human-readable error message
        locale: Optional locale from original request

    Returns:
        SearchResponseItem with status='rjct'
    """
    return SearchResponseItem(
        reference_id=reference_id,
        timestamp=datetime.now(UTC),
        status="rjct",
        status_reason_code=status_reason_code.value,
        status_reason_message=truncate_message(status_reason_message),
        data=None,
        pagination=None,
        locale=locale,
    )


def sign_dci_envelope(
    env: Environment,
    header: DCICallbackHeader,
    message: dict,
) -> str:
    """Sign a DCI envelope using the active server signing key.

    Args:
        env: Odoo environment
        header: DCI callback header (Pydantic model)
        message: DCI message body dict

    Returns:
        str: Signature string, or empty string if signing fails
    """
    try:
        # Get active signing key
        signing_key_model = env["spp.dci.signing.key"].sudo()
        active_key = signing_key_model.get_active_key()

        if not active_key:
            _logger.warning("No active signing key found - response will be unsigned")
            return ""

        # Get signer and sign the response
        signer = active_key.get_signer()
        header_dict = header.model_dump(mode="json", exclude_none=True)
        signature = signer.sign(header_dict, message)
        _logger.debug("Response signed with key: %s", active_key.key_id)
        return signature

    except Exception as e:
        _logger.warning("Failed to sign response: %s - continuing with unsigned response", str(e))
        return ""


def get_response_action(request_action: str) -> str:
    """Get the response action based on request action per SPDCI spec.

    Special cases:
    - txn-status -> txn-on-status (not on-txn-status)
    - Others follow on-{action} pattern

    Args:
        request_action: The action from the incoming request header

    Returns:
        str: The appropriate response action
    """
    action_map = {"txn-status": "txn-on-status"}
    return action_map.get(request_action, f"on-{request_action}")


def build_signed_envelope(
    env: Environment,
    original_header,  # DCIMessageHeader
    response_message: dict,
    status_code: str,
    status_reason_code: str | None = None,
    status_reason_message: str | None = None,
    completed_count: int = 0,
) -> DCIEnvelope:
    """Build and sign a DCI response envelope.

    Args:
        env: Odoo environment
        original_header: DCIMessageHeader from incoming request
        response_message: Response message dict
        status_code: Overall status (succ, rjct, part)
        status_reason_code: Optional SPDCI reason code (use enum.value)
        status_reason_message: Optional human-readable message
        completed_count: Number of successfully completed items

    Returns:
        DCIEnvelope with signature (or empty signature if signing fails)
    """
    our_sender_id = get_sender_id(env)
    response_action = get_response_action(original_header.action)

    callback_header = DCICallbackHeader(
        version=original_header.version,
        message_id=str(uuid.uuid4()),
        message_ts=datetime.now(UTC),
        action=response_action,
        sender_id=our_sender_id,
        receiver_id=original_header.sender_id,
        total_count=original_header.total_count,
        status=status_code,
        status_reason_code=status_reason_code,
        status_reason_message=truncate_message(status_reason_message) if status_reason_message else None,
        completed_count=completed_count,
    )

    # Sign the response
    signature = sign_dci_envelope(env, callback_header, response_message)

    return DCIEnvelope(
        signature=signature,
        header=callback_header,
        message=response_message,
    )
