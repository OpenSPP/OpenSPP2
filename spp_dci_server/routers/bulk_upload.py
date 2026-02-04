# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""DCI Bulk Upload API endpoint for file-based operations.

Implements SPDCI-compliant file upload for batch operations:
- POST /registry/upload/search - Bulk search via file upload
- Supports JSON and CSV file formats per SPDCI FileInfo schema
"""

import csv
import io
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from odoo.api import Environment

from odoo.addons.fastapi.dependencies import odoo_env

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from ..middleware.rate_limit import check_dci_rate_limit
from ..middleware.signature import verify_bearer_token

_logger = logging.getLogger(__name__)

# Maximum file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Maximum identifiers per file
MAX_IDENTIFIERS_PER_FILE = 100000

# Maximum pending jobs per sender
MAX_PENDING_JOBS_PER_SENDER = 10

dci_bulk_upload_router = APIRouter(tags=["DCI Bulk Operations"])


class BulkUploadError(Exception):
    """Custom exception for bulk upload errors."""

    def __init__(self, message: str, code: str = "err.file.invalid"):
        self.message = message
        self.code = code
        super().__init__(message)


def _parse_json_file(content: bytes) -> list[dict]:
    """Parse JSON file content.

    Supports two formats:
    1. Full DCI envelope with search_request array
    2. Simple array of identifier objects

    Args:
        content: Raw file bytes

    Returns:
        List of search criteria dicts
    """
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise BulkUploadError(f"Invalid JSON format: {str(e)}", "err.file.parse_error")

    # Check if it's a full DCI envelope
    if isinstance(data, dict):
        if "message" in data and "search_request" in data.get("message", {}):
            # Full envelope format
            return data["message"]["search_request"]
        elif "search_request" in data:
            # Message-only format
            return data["search_request"]
        elif "identifiers" in data:
            # Simple identifiers array format
            return _identifiers_to_search_requests(data["identifiers"])
        else:
            raise BulkUploadError(
                "JSON must contain 'search_request' or 'identifiers' array",
                "err.file.format_invalid",
            )
    elif isinstance(data, list):
        # Direct array of search requests or identifiers
        if data and isinstance(data[0], dict):
            if "search_criteria" in data[0]:
                # Array of search request items
                return data
            elif "type" in data[0] or "namespace" in data[0]:
                # Array of identifier objects
                return _identifiers_to_search_requests(data)
        raise BulkUploadError(
            "Array must contain search request items or identifier objects",
            "err.file.format_invalid",
        )
    else:
        raise BulkUploadError("Invalid JSON structure", "err.file.format_invalid")


def _parse_csv_file(content: bytes) -> list[dict]:
    """Parse CSV file content.

    Expected CSV format:
    identifier_type,identifier_value[,reg_type]

    Example:
    urn:gov:id:national,12345,SOCIAL_REGISTRY
    urn:gov:id:national,12346,SOCIAL_REGISTRY

    Args:
        content: Raw file bytes

    Returns:
        List of search request dicts
    """
    try:
        text = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        identifiers = []
        for row in reader:
            if len(identifiers) >= MAX_IDENTIFIERS_PER_FILE:
                raise BulkUploadError(
                    f"File exceeds maximum of {MAX_IDENTIFIERS_PER_FILE} identifiers",
                    "err.file.too_large",
                )

            # Support both camelCase and snake_case headers
            id_type = row.get("identifier_type") or row.get("identifierType") or row.get("type")
            id_value = row.get("identifier_value") or row.get("identifierValue") or row.get("value")
            reg_type = row.get("reg_type") or row.get("regType") or "SOCIAL_REGISTRY"

            if not id_type or not id_value:
                continue  # Skip incomplete rows

            identifiers.append(
                {
                    "type": id_type,
                    "value": id_value,
                    "reg_type": reg_type,
                }
            )

        if not identifiers:
            raise BulkUploadError(
                "CSV file contains no valid identifier rows",
                "err.file.empty",
            )

        return _identifiers_to_search_requests(identifiers)

    except UnicodeDecodeError as e:
        raise BulkUploadError(f"Invalid CSV encoding: {str(e)}", "err.file.parse_error")
    except csv.Error as e:
        raise BulkUploadError(f"Invalid CSV format: {str(e)}", "err.file.parse_error")


def _identifiers_to_search_requests(identifiers: list[dict]) -> list[dict]:
    """Convert identifier objects to search request items.

    Args:
        identifiers: List of identifier dicts with type, value, and optional reg_type

    Returns:
        List of search request item dicts
    """
    requests = []
    for i, ident in enumerate(identifiers):
        if len(requests) >= MAX_IDENTIFIERS_PER_FILE:
            break

        id_type = ident.get("type") or ident.get("namespace")
        id_value = ident.get("value")
        reg_type = ident.get("reg_type") or ident.get("regType") or "SOCIAL_REGISTRY"

        if not id_type or not id_value:
            continue

        requests.append(
            {
                "reference_id": f"bulk-{i:06d}",
                "timestamp": datetime.now(UTC).isoformat(),
                "search_criteria": {
                    "reg_type": reg_type,
                    "reg_event_type": "ACTIVE",
                    "query_type": "namedQuery",
                    "query": {
                        "query_name": "identifier",
                        "query_params": {
                            "identifier_type": id_type,
                            "identifier_value": id_value,
                        },
                    },
                },
            }
        )

    return requests


async def _read_file_with_limit(file: UploadFile, max_size: int) -> bytes:
    """Read file with incremental size checking to prevent decompression bombs.

    Args:
        file: Uploaded file
        max_size: Maximum allowed size in bytes

    Returns:
        File content as bytes

    Raises:
        HTTPException: If file exceeds max_size
    """
    content = b""
    chunk_size = 64 * 1024  # 64KB chunks

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content += chunk
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum size of {max_size // (1024 * 1024)}MB",
            )

    return content


@dci_bulk_upload_router.post(
    "/upload/search",
    status_code=status.HTTP_202_ACCEPTED,
    response_model_exclude_none=True,
)
async def bulk_search_upload(
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    _rate_limit_check: Annotated[None, Depends(check_dci_rate_limit)],
    file: UploadFile = File(..., description="JSON or CSV file with search requests"),
    file_format: str = Form("json", description="File format: json or csv"),
    action: str = Form("search", description="DCI action type"),
    sender_id: str = Form(..., description="Sender identifier"),
    callback_uri: str = Form(None, description="Optional callback URL for async results"),
):
    """
    Bulk search via file upload (SPDCI FileInfo format).

    Upload a JSON or CSV file containing multiple identifier searches.
    The search is processed asynchronously and results are delivered
    via callback if callback_uri is provided.

    **File Formats:**

    JSON (array of identifiers):
    ```json
    {
      "identifiers": [
        {"type": "urn:gov:id:national", "value": "12345"},
        {"type": "urn:gov:id:national", "value": "12346"}
      ]
    }
    ```

    CSV:
    ```csv
    identifier_type,identifier_value,reg_type
    urn:gov:id:national,12345,SOCIAL_REGISTRY
    urn:gov:id:national,12346,SOCIAL_REGISTRY
    ```

    **Response**: 202 Accepted with transaction ID for tracking
    """
    try:
        # Read file with decompression bomb protection
        content = await _read_file_with_limit(file, MAX_FILE_SIZE)

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file uploaded",
            )

        # Parse file based on format
        file_format_lower = file_format.lower()
        if file_format_lower == "json":
            search_items = _parse_json_file(content)
        elif file_format_lower == "csv":
            search_items = _parse_csv_file(content)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {file_format}. Use 'json' or 'csv'.",
            )

        _logger.info(
            "Bulk upload received: %d items from sender %s",
            len(search_items),
            sender_id,
        )

        # Look up sender
        sender = env["spp.dci.sender.registry"].sudo().search([("sender_id", "=", sender_id)], limit=1)

        # Check per-sender concurrency limits
        if sender:
            pending_jobs = (
                env["spp.dci.transaction"]
                .sudo()
                .search_count(
                    [
                        ("sender_id", "=", sender.id),
                        ("state", "in", ["pending", "processing"]),
                    ]
                )
            )
            if pending_jobs >= MAX_PENDING_JOBS_PER_SENDER:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many pending operations ({pending_jobs}). Please wait for existing jobs to complete.",
                )

        # Generate IDs once to avoid duplicates
        transaction_id = f"bulk-{uuid.uuid4()}"
        correlation_id = str(uuid.uuid4())
        message_id = f"upload-{uuid.uuid4()}"

        # Build search request
        search_request_data = {
            "transaction_id": transaction_id,
            "search_request": search_items,
        }

        # Create transaction record for tracking
        transaction = (
            env["spp.dci.transaction"]
            .sudo()
            .create(
                {
                    "transaction_id": transaction_id,
                    "message_id": message_id,
                    "correlation_id": correlation_id,
                    "action": "search",
                    "reg_type": "SOCIAL_REGISTRY",
                    "sender_id": sender.id if sender else False,
                    "sender_uri": sender_id,
                    "callback_uri": callback_uri,
                    "request_payload": json.dumps(
                        {
                            "header": {
                                "action": action,
                                "sender_id": sender_id,
                                "message_id": message_id,
                                "message_ts": datetime.now(UTC).isoformat(),
                            },
                            "message": search_request_data,
                        }
                    ),
                    "state": "received",
                }
            )
        )

        # Queue the async search job
        job = transaction.with_delay(
            channel="root.dci",
            description=f"DCI Bulk Search {transaction_id} ({len(search_items)} items)",
        ).process_async_search()

        transaction.job_uuid = job.uuid
        transaction.state = "pending"

        _logger.info(
            "Bulk search queued: transaction_id=%s, items=%d, job=%s",
            transaction_id,
            len(search_items),
            job.uuid,
        )

        return {
            "status": "accepted",
            "transaction_id": transaction_id,
            "correlation_id": correlation_id,
            "item_count": len(search_items),
            "message": f"Bulk search queued with {len(search_items)} items",
        }

    except BulkUploadError as e:
        _logger.warning("Bulk upload error: %s", e.message)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.code, "message": e.message},
        )
    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Bulk upload failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing bulk upload",
        )


@dci_bulk_upload_router.post(
    "/upload/verify",
    status_code=status.HTTP_200_OK,
    response_model_exclude_none=True,
)
async def bulk_verify_identifiers(
    env: Annotated[Environment, Depends(odoo_env)],
    _bearer_token: Annotated[str, Depends(verify_bearer_token)],
    _rate_limit_check: Annotated[None, Depends(check_dci_rate_limit)],
    file: UploadFile = File(..., description="JSON or CSV file with identifiers"),
    file_format: str = Form("json", description="File format: json or csv"),
    sender_id: str = Form(..., description="Sender identifier"),
):
    """
    Bulk verify identifiers - check which IDs exist in registry.

    This is a synchronous operation for smaller batches (up to 10,000 IDs).
    Returns immediate response with found/not_found lists.

    For larger batches, use /upload/search with callback_uri.

    **Response format:**
    ```json
    {
      "found": [
        {"identifier_type": "...", "identifier_value": "...", "registry_id": "..."}
      ],
      "not_found": [
        {"identifier_type": "...", "identifier_value": "..."}
      ],
      "total": 1000,
      "found_count": 850,
      "not_found_count": 150
    }
    ```
    """
    try:
        # Permission check - require registry viewer role
        if not env.user.has_group("spp_registry.group_registry_viewer"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to verify registry identifiers",
            )

        # Read file with decompression bomb protection (smaller limit for sync)
        max_sync_size = 5 * 1024 * 1024  # 5MB for sync
        content = await _read_file_with_limit(file, max_sync_size)

        # Parse file
        file_format_lower = file_format.lower()
        if file_format_lower == "json":
            search_items = _parse_json_file(content)
        elif file_format_lower == "csv":
            search_items = _parse_csv_file(content)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: {file_format}",
            )

        # Limit for sync operation
        max_sync_items = 10000
        if len(search_items) > max_sync_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Too many items ({len(search_items)}) for sync verify. Max {max_sync_items}. Use /upload/search.",
            )

        _logger.info(
            "Bulk verify: %d identifiers from sender %s",
            len(search_items),
            sender_id,
        )

        # Extract all identifier pairs for batch query
        lookup_requests = {}  # (type, value) -> original item
        for item in search_items:
            criteria = item.get("search_criteria", {})
            query = criteria.get("query", {})
            query_params = query.get("query_params", {})

            id_type = query_params.get("identifier_type")
            id_value = query_params.get("identifier_value")

            if id_type and id_value:
                lookup_requests[(id_type, id_value)] = item

        if not lookup_requests:
            return {
                "status": "success",
                "found": [],
                "not_found": [],
                "total": 0,
                "found_count": 0,
                "not_found_count": 0,
            }

        # Batch query - single database query instead of N queries
        all_types = list(set(k[0] for k in lookup_requests.keys()))
        all_values = list(set(k[1] for k in lookup_requests.keys()))

        RegID = env["spp.registry.id"].sudo()
        reg_ids = RegID.search(
            [
                ("id_type_id.namespace_uri", "in", all_types),
                ("value", "in", all_values),
            ]
        )

        # Build lookup map from results
        found_map = {}
        for reg_id in reg_ids:
            if reg_id.partner_id and reg_id.id_type_id:
                key = (reg_id.id_type_id.namespace_uri, reg_id.value)
                # Only include if partner has external ID (never expose DB ID)
                if reg_id.partner_id.spp_reg_id:
                    found_map[key] = {
                        "registry_id": reg_id.partner_id.spp_reg_id,
                    }

        # Build response lists
        found = []
        not_found = []

        for id_type, id_value in lookup_requests.keys():
            if (id_type, id_value) in found_map:
                found.append(
                    {
                        "identifier_type": id_type,
                        "identifier_value": id_value,
                        "registry_id": found_map[(id_type, id_value)]["registry_id"],
                    }
                )
            else:
                not_found.append(
                    {
                        "identifier_type": id_type,
                        "identifier_value": id_value,
                    }
                )

        return {
            "status": "success",
            "found": found,
            "not_found": not_found,
            "total": len(lookup_requests),
            "found_count": len(found),
            "not_found_count": len(not_found),
        }

    except BulkUploadError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.code, "message": e.message},
        )
    except HTTPException:
        raise
    except Exception as e:
        _logger.exception("Bulk verify failed: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
