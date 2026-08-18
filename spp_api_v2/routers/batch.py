# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Batch and transaction bundle endpoints"""

import logging
from typing import Annotated

from odoo.api import Environment
from odoo.exceptions import ValidationError

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends, HTTPException, status

from ..middleware.auth import get_authenticated_client
from ..schemas.bundle import RegistrantBundle
from ..services.bundle_service import BundleProcessor

_logger = logging.getLogger(__name__)

batch_router = APIRouter(tags=["Batch"], prefix="/$batch")


@batch_router.post("", response_model=RegistrantBundle)
async def process_bundle(
    bundle: RegistrantBundle,
    env: Annotated[Environment, Depends(odoo_env)],
    api_client: Annotated[dict, Depends(get_authenticated_client)],
):
    """
    Process a transaction or batch bundle.

    **Bundle Types:**
    - `transaction`: All-or-nothing. If any entry fails, all changes are rolled back.
    - `batch`: Independent operations. Partial success is allowed.

    **Request Format:**
    ```json
    {
      "resourceType": "Bundle",
      "type": "transaction",
      "entry": [
        {
          "fullUrl": "urn:uuid:individual-1",
          "request": {
            "method": "POST",
            "url": "Individual"
          },
          "resource": {
            "resourceType": "Individual",
            ...
          }
        },
        {
          "fullUrl": "urn:uuid:group-1",
          "request": {
            "method": "POST",
            "url": "Group"
          },
          "resource": {
            "resourceType": "Group",
            "member": [
              {
                "entity": {"reference": "urn:uuid:individual-1"}
              }
            ]
          }
        }
      ]
    }
    ```

    **Placeholder Resolution:**
    - Use `urn:uuid:*` in `fullUrl` to create placeholders
    - Reference placeholders in subsequent entries
    - Placeholders are resolved to actual identifiers after creation

    **Supported Operations:**
    - `POST {ResourceType}` - Create resource
    - `PUT {ResourceType}/{system}|{value}` - Update resource
    - `GET {ResourceType}/{system}|{value}` - Read resource
    - `DELETE {ResourceType}/{system}|{value}` - Delete resource (soft delete)

    **Response:**
    Returns Bundle with type `transaction-response` or `batch-response`.
    Each entry contains:
    - `response.status`: HTTP status (e.g., "201 Created")
    - `response.location`: URL of created/updated resource
    - `response.etag`: Version ID for optimistic locking
    - `resource`: Created/updated resource (for successful operations)

    **Error Handling:**
    - Transaction: Returns 422 with OperationOutcome if any entry fails
    - Batch: Failed entries have OperationOutcome in resource field
    """
    # Validate bundle type
    if bundle.type not in ("transaction", "batch"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bundle type: {bundle.type}. Must be 'transaction' or 'batch'.",
        )

    # Validate bundle has entries
    if not bundle.entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bundle must contain at least one entry",
        )

    # Create source tracking URI
    source = f"urn:openspp:api-client:{api_client.client_id}"

    # Process bundle
    processor = BundleProcessor(env)

    try:
        if bundle.type == "transaction":
            _logger.info(
                f"Processing transaction bundle with {len(bundle.entry)} entries from client {api_client.client_id}"
            )
            result = processor.process_transaction(bundle, api_client, source)
            _logger.info(f"Transaction bundle completed successfully for client {api_client.client_id}")
            return result

        else:  # batch
            _logger.info(f"Processing batch bundle with {len(bundle.entry)} entries from client {api_client.client_id}")
            result = processor.process_batch(bundle, api_client, source)
            _logger.info(f"Batch bundle completed for client {api_client.client_id}")
            return result

    except ValidationError as e:
        _logger.error(f"Bundle processing failed for client {api_client.client_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "error",
                        "code": "invalid",
                        "diagnostics": str(e),
                    }
                ],
            },
        ) from e

    except Exception as e:
        _logger.exception(f"Unexpected error processing bundle for client {api_client.client_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "resourceType": "OperationOutcome",
                "issue": [
                    {
                        "severity": "fatal",
                        "code": "exception",
                        "diagnostics": f"Internal server error: {str(e)}",
                    }
                ],
            },
        ) from e
