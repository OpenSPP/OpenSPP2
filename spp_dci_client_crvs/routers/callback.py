# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""CRVS Callback endpoint for receiving vital event notifications."""

import logging
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env
from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..middleware.signature import verify_crvs_signature

_logger = logging.getLogger(__name__)

crvs_callback_router = APIRouter(tags=["DCI CRVS Callback"])


@crvs_callback_router.post(
    "/crvs",
    response_model=None,
)
async def receive_crvs_notification(
    request: Request,
    envelope: DCIEnvelope,
    env: Annotated[Environment, Depends(odoo_env)],
    verified_sender_id: Annotated[str, Depends(verify_crvs_signature)],
):
    """
    Receive CRVS vital event notifications.

    This endpoint receives webhooks from CRVS registries notifying us of
    vital events (births, deaths, marriages, etc.) for registered beneficiaries.

    **Request Structure**:
    ```json
    {
        "signature": "namespace=\"dci\", kidId=\"...\", algorithm=\"ed25519\", ...",
        "header": {
            "version": "1.0.0",
            "message_id": "unique-msg-id",
            "message_ts": "2024-12-02T10:30:00Z",
            "action": "notify",
            "sender_id": "crvs-registry",
            "receiver_id": "openspp"
        },
        "message": {
            "event_type": "DEATH",
            "event_date": "2024-12-01",
            "identifiers": [
                {
                    "type": "UIN",
                    "value": "123456789"
                },
                {
                    "type": "DRN",
                    "value": "D-2024-12345"
                }
            ],
            "person": {
                "name": "John Doe",
                "birth_date": "1990-01-15"
            }
        }
    }
    ```

    **Response**: Acknowledgment with created event ID
    """
    try:
        _logger.info(
            "Received CRVS notification from %s (verified sender: %s)",
            request.client.host if request.client else "unknown",
            verified_sender_id,
        )

        # Signature has been verified by verify_crvs_signature dependency
        # Extract header and message. Use mode="json" so datetime fields
        # serialize to ISO strings - the fallback _create_event_directly
        # path json.dumps() this header into raw_data, which fails on raw
        # datetime objects.
        header = envelope.header.model_dump(mode="json")
        message = envelope.message

        sender_id = header.get("sender_id", "unknown")
        action = header.get("action", "unknown")
        event_type = message.get("event_type", "unknown")

        _logger.info(
            "Processing CRVS notification - sender: %s, action: %s, event_type: %s",
            sender_id,
            action,
            event_type,
        )

        # Import service here to avoid circular imports
        from ..services.crvs_service import CRVSService

        # Initialize CRVS service (use default data source)
        try:
            service = CRVSService(env)
        except Exception as e:
            _logger.error("Failed to initialize CRVS service: %s", str(e))
            # If we can't initialize service, try to process directly
            service = None

        # Reconstruct notification data from envelope for service
        notification_data = {
            "header": header,
            "message": message,
        }

        # Process notification
        if service:
            event_id = service.process_notification(notification_data)
        else:
            # Fallback: create event record directly
            event_id = _create_event_directly(env, notification_data)

        _logger.info("CRVS notification processed successfully - event ID: %s", event_id)

        # Return acknowledgment
        return {
            "status": "success",
            "message": "CRVS notification received and processed",
            "event_id": event_id,
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        _logger.error("Failed to process CRVS notification: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process CRVS notification: {str(e)}",
        ) from None


def _create_event_directly(env, notification_data: dict) -> int:
    """Fallback method to create event record directly.

    Used when CRVSService cannot be initialized (e.g., no data source configured).

    Args:
        env: Odoo environment
        notification_data: Notification data

    Returns:
        int: Created event ID
    """
    import json

    message = notification_data.get("message", {})

    # Extract event details
    event_type = message.get("event_type", "").lower()
    event_date = message.get("event_date")

    # Extract identifiers
    identifiers = message.get("identifiers", [])
    identifier_type = None
    identifier_value = None

    if identifiers:
        first_id = identifiers[0]
        identifier_type = first_id.get("type")
        identifier_value = first_id.get("value")

    # Create event record
    event = env["spp.dci.crvs.event"].create(
        {
            "event_type": event_type,
            "identifier_type": identifier_type,
            "identifier_value": identifier_value,
            "event_date": event_date,
            "raw_data": json.dumps(notification_data, indent=2),
            "state": "received",
        }
    )

    _logger.info(
        "Created CRVS event record %s (fallback method)",
        event.name,
    )

    # Try to process the event
    try:
        event.process_event()
    except Exception as e:
        _logger.error("Failed to auto-process event ID %s: %s", event.id, str(e))

    return event.id
