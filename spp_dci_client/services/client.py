"""DCI Client Service for making signed API requests."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from odoo import _
from odoo.exceptions import UserError, ValidationError

from odoo.addons.spp_dci.schemas import (
    DCIMessageHeader,
    PaginationRequest,
    QueryType,
    RegistryType,
    SearchCriteria,
    SearchRequest,
    SearchRequestItem,
)
from odoo.addons.spp_dci.services import DCISigner

from ..services.errors import format_connection_error, format_http_error

_logger = logging.getLogger(__name__)

# DCI endpoint constants
ENDPOINT_SYNC_SEARCH = "/registry/sync/search"
ENDPOINT_ASYNC_SEARCH = "/registry/search"


class DCIClient:
    """Generic DCI API client for making signed requests.

    Handles building DCI envelopes, signing messages, and making HTTP requests
    to external DCI-compliant registries.

    Supports both synchronous and asynchronous DCI endpoints.
    """

    def __init__(self, data_source, env):
        """Initialize DCI client.

        Args:
            data_source: spp.dci.data.source record
            env: Odoo environment
        """
        if not data_source:
            raise ValueError("data_source is required")

        self.data_source = data_source
        self.env = env

        # Validate required configuration
        self._validate_configuration()

    def _validate_configuration(self):
        """Validate that data source has required configuration."""
        required_fields = ["base_url", "our_sender_id"]
        missing = [f for f in required_fields if not getattr(self.data_source, f, None)]

        if missing:
            raise ValidationError(
                f"Data source '{self.data_source.name}' is missing required fields: {', '.join(missing)}"
            )

    # =========================================================================
    # SEARCH METHODS
    # =========================================================================

    def search(
        self,
        query_type: str,
        query_value: str,
        record_type: str = "PERSON",
        page: int = 1,
        page_size: int = 10,
        registry_type: str | None = None,
        registry_event_type: str | None = None,
    ) -> dict:
        """Execute synchronous search request.

        Uses ENDPOINT_SYNC_SEARCH endpoint - returns results directly.

        Args:
            query_type: "idtype-value" or "predicate"
            query_value: Query string or expression
            record_type: PERSON, GROUP, etc.
            page: Page number (1-indexed)
            page_size: Records per page
            registry_type: Registry type (defaults to data source registry type)
            registry_event_type: Optional event type filter

        Returns:
            SearchResponse dict with results

        Raises:
            UserError: If request fails or returns error status
            ValidationError: If parameters are invalid
        """
        query = self._parse_query(query_type, query_value)
        envelope = self._build_search_envelope(
            query_type=query_type,
            query=query,
            registry_type=registry_type or self._get_registry_type(),
            registry_event_type=registry_event_type,
            record_type=record_type,
            page=page,
            page_size=page_size,
        )

        endpoint = self.data_source.search_endpoint or ENDPOINT_SYNC_SEARCH
        return self._make_request(endpoint, envelope)

    def search_async(
        self,
        query_type: str,
        query_value: str,
        record_type: str = "PERSON",
        page: int = 1,
        page_size: int = 10,
        registry_type: str | None = None,
        registry_event_type: str | None = None,
        callback_url: str | None = None,
    ) -> dict:
        """Execute asynchronous search request.

        Uses ENDPOINT_ASYNC_SEARCH endpoint - returns ACK, results sent via callback.

        Args:
            query_type: "idtype-value" or "predicate"
            query_value: Query string or expression
            record_type: PERSON, GROUP, etc.
            page: Page number (1-indexed)
            page_size: Records per page
            registry_type: Registry type (defaults to data source registry type)
            registry_event_type: Optional event type filter
            callback_url: URL to receive results (defaults to data source callback URI)

        Returns:
            ACK response dict with correlation_id

        Raises:
            UserError: If request fails or returns error status
            ValidationError: If parameters are invalid
        """
        query = self._parse_query(query_type, query_value)
        envelope = self._build_search_envelope(
            query_type=query_type,
            query=query,
            registry_type=registry_type or self._get_registry_type(),
            registry_event_type=registry_event_type,
            record_type=record_type,
            page=page,
            page_size=page_size,
            callback_url=callback_url,
        )

        return self._make_request(ENDPOINT_ASYNC_SEARCH, envelope)

    def search_by_id(
        self,
        identifier_type: str,
        identifier_value: str,
        record_type: str = "PERSON",
        page: int = 1,
        page_size: int = 10,
        async_mode: bool = False,
    ) -> dict:
        """Search by identifier type and value (convenience method).

        Args:
            identifier_type: Identifier type (UIN, BRN, MRN, DRN, etc.)
            identifier_value: Identifier value
            record_type: PERSON, GROUP, etc.
            page: Page number (1-indexed)
            page_size: Records per page
            async_mode: If True, use async endpoint

        Returns:
            SearchResponse or ACK dict
        """
        query_value = f"{identifier_type}:{identifier_value}"
        method = self.search_async if async_mode else self.search
        return method(
            query_type=QueryType.IDTYPE_VALUE,
            query_value=query_value,
            record_type=record_type,
            page=page,
            page_size=page_size,
        )

    def search_by_predicate(
        self,
        predicate: str,
        record_type: str = "PERSON",
        page: int = 1,
        page_size: int = 10,
        async_mode: bool = False,
    ) -> dict:
        """Search using CEL predicate expression.

        Args:
            predicate: CEL expression (e.g., "person.age >= 18")
            record_type: PERSON, GROUP, etc.
            page: Page number (1-indexed)
            page_size: Records per page
            async_mode: If True, use async endpoint

        Returns:
            SearchResponse or ACK dict
        """
        method = self.search_async if async_mode else self.search
        return method(
            query_type=QueryType.PREDICATE,
            query_value=predicate,
            record_type=record_type,
            page=page,
            page_size=page_size,
        )

    def search_by_expression(
        self,
        expression: dict | list,
        record_type: str = "PERSON",
        page: int = 1,
        page_size: int = 10,
        registry_type: str | None = None,
        registry_event_type: str | None = None,
        async_mode: bool = False,
    ) -> dict:
        """Search using expression query (e.g., date range filters).

        This supports DCI-compliant expression queries using ExpPredicate format.

        Args:
            expression: DCI ExpPredicateWithCondition list, e.g.:
                [
                    {
                        "seq_num": 1,
                        "expression1": {
                            "attribute_name": "dateOfEvent",
                            "operator": "ge",
                            "attribute_value": "2020-01-01"
                        },
                        "condition": "and",
                        "expression2": {
                            "attribute_name": "dateOfEvent",
                            "operator": "le",
                            "attribute_value": "2026-02-10"
                        }
                    }
                ]
            record_type: PERSON, GROUP, etc.
            page: Page number (1-indexed)
            page_size: Records per page
            registry_type: Registry type (defaults to data source registry type)
            registry_event_type: Optional event type filter (e.g., "BIRTH", "DEATH")
            async_mode: If True, use async endpoint

        Returns:
            SearchResponse or ACK dict
        """
        # Build envelope directly with expression query (bypass _parse_query)
        envelope = self._build_search_envelope(
            query_type=QueryType.EXPRESSION,
            query=expression,
            registry_type=registry_type or self._get_registry_type(),
            registry_event_type=registry_event_type,
            record_type=record_type,
            page=page,
            page_size=page_size,
        )

        if async_mode:
            return self._make_request(ENDPOINT_ASYNC_SEARCH, envelope)
        else:
            endpoint = self.data_source.search_endpoint or ENDPOINT_SYNC_SEARCH
            return self._make_request(endpoint, envelope)

    def search_by_date_range(
        self,
        start_date: str,
        end_date: str,
        attribute_name: str = "dateOfEvent",
        event_type: str | None = None,
        record_type: str = "PERSON",
        page: int = 1,
        page_size: int = 10,
        async_mode: bool = False,
        use_opencrvs_format: bool = False,
    ) -> dict:
        """Search by date range.

        This is a simplified interface for date range searches commonly used
        with CRVS registries to find events within a date range.

        Args:
            start_date: Start date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
            end_date: End date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
            attribute_name: Attribute to filter on (default: dateOfEvent)
            event_type: Registry event type filter (BIRTH, DEATH, etc.)
            record_type: PERSON, GROUP, etc.
            page: Page number (1-indexed)
            page_size: Records per page
            async_mode: If True, use async endpoint
            use_opencrvs_format: If True, use OpenCRVS's non-standard expression format.
                If False (default), use DCI-compliant predicate format.

        Returns:
            SearchResponse or ACK dict

        Note:
            - DCI-compliant format uses query_type "predicate" with ExpPredicateWithConditionList
            - OpenCRVS format uses query_type "expression" with their custom range syntax
            - Use use_opencrvs_format=True when connecting to OpenCRVS servers
        """
        if use_opencrvs_format:
            return self._search_by_date_range_opencrvs(
                start_date=start_date,
                end_date=end_date,
                attribute_name=attribute_name,
                event_type=event_type,
                record_type=record_type,
                page=page,
                page_size=page_size,
                async_mode=async_mode,
            )

        # Build DCI-compliant predicate query using ExpPredicateWithConditionList format
        # Operators per DCI spec: gt, lt, eq, ge, le, in
        predicate = [
            {
                "seq_num": 1,
                "expression1": {
                    "attribute_name": attribute_name,
                    "operator": "ge",
                    "attribute_value": start_date,
                },
                "condition": "and",
                "expression2": {
                    "attribute_name": attribute_name,
                    "operator": "le",
                    "attribute_value": end_date,
                },
            }
        ]

        # Build envelope with predicate query type (DCI-compliant)
        envelope = self._build_search_envelope(
            query_type=QueryType.PREDICATE,
            query=predicate,
            registry_type=self._get_registry_type(),
            registry_event_type=event_type,
            record_type=record_type,
            page=page,
            page_size=page_size,
        )

        if async_mode:
            return self._make_request(ENDPOINT_ASYNC_SEARCH, envelope)
        else:
            endpoint = self.data_source.search_endpoint or ENDPOINT_SYNC_SEARCH
            return self._make_request(endpoint, envelope)

    def _search_by_date_range_opencrvs(
        self,
        start_date: str,
        end_date: str,
        attribute_name: str = "dateOfEvent",
        event_type: str | None = None,
        record_type: str = "PERSON",
        page: int = 1,
        page_size: int = 10,
        async_mode: bool = False,
    ) -> dict:
        """Search by date range using OpenCRVS's non-standard envelope format.

        OpenCRVS uses a custom format that differs from DCI spec:
        - reg_type: lowercase event type (e.g., "birth") instead of registry type
        - No reg_event_type field
        - Requires consent object and locale field
        - Expression query format: { type: "ns:org:QueryType:expression", value: { <attr>: { type: "range", ... } } }

        This method exists for interoperability with OpenCRVS servers that don't
        follow the standard DCI envelope format.

        Args:
            start_date: Start date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
            end_date: End date in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SSZ)
            attribute_name: Attribute to filter on (default: dateOfEvent)
            event_type: Registry event type filter (BIRTH, DEATH, etc.)
            record_type: PERSON, GROUP, etc.
            page: Page number (1-indexed)
            page_size: Records per page
            async_mode: If True, use async endpoint

        Returns:
            SearchResponse or ACK dict
        """
        # Build envelope directly in OpenCRVS format (bypassing standard _build_search_envelope)
        envelope = self._build_search_envelope_opencrvs(
            start_date=start_date,
            end_date=end_date,
            attribute_name=attribute_name,
            event_type=event_type,
            page=page,
            page_size=page_size,
        )

        if async_mode:
            return self._make_request(ENDPOINT_ASYNC_SEARCH, envelope)
        else:
            endpoint = self.data_source.search_endpoint or ENDPOINT_SYNC_SEARCH
            return self._make_request(endpoint, envelope)

    def _build_search_envelope_opencrvs(
        self,
        start_date: str,
        end_date: str,
        attribute_name: str,
        event_type: str | None,
        page: int,
        page_size: int,
    ) -> dict:
        """Build search envelope in OpenCRVS's non-standard format.

        OpenCRVS expects:
        - reg_type: lowercase event type (e.g., "birth"), NOT registry type
        - No reg_event_type field
        - Required consent object
        - Required locale field
        - Expression query with range syntax

        Args:
            start_date: Start date
            end_date: End date
            attribute_name: Attribute to filter on
            event_type: Event type (BIRTH, DEATH, etc.)
            page: Page number
            page_size: Page size

        Returns:
            Envelope dict in OpenCRVS format
        """
        now = datetime.now(UTC)
        transaction_id = str(uuid.uuid4())
        reference_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        # OpenCRVS uses lowercase event type for reg_type (e.g., "birth" not "BIRTH" or "CRVS")
        reg_type = (event_type or "birth").lower()

        # Build OpenCRVS-style expression query
        expression_query = {
            "type": "ns:org:QueryType:expression",
            "value": {
                attribute_name: {
                    "type": "range",
                    "gte": start_date,
                    "lte": end_date,
                }
            },
        }

        # Build search criteria in OpenCRVS format (no reg_event_type)
        search_criteria = {
            "version": "1.0.0",
            "reg_type": reg_type,
            "query_type": "expression",
            "query": expression_query,
            "sort": [
                {
                    "attribute_name": "createdAt",
                    "sort_order": "asc",
                }
            ],
            "pagination": {
                "page_size": page_size,
                "page_number": page,
            },
        }

        # Build search request item with consent and locale (required by OpenCRVS)
        search_request_item = {
            "reference_id": reference_id,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "search_criteria": search_criteria,
            "consent": {
                "id": "consent-openspp",
                "ts": now.isoformat().replace("+00:00", "Z"),
                "purpose": {
                    "text": "Social protection program verification",
                    "code": "SPP",
                    "refUri": self.data_source.our_callback_uri or "http://openspp.org",
                },
            },
            "locale": "eng",
        }

        # Build message
        message = {
            "transaction_id": transaction_id,
            "search_request": [search_request_item],
        }

        # Build header as plain dict (OpenCRVS format - no is_msg_encrypted field)
        header = {
            "version": "1.0.0",
            "message_id": message_id,
            "message_ts": now.isoformat().replace("+00:00", "Z"),
            "action": "search",
            "sender_id": self.data_source.our_sender_id,
            "sender_uri": self.data_source.our_callback_uri or "",
            "receiver_id": self.data_source.receiver_id or self.data_source.base_url,
            "total_count": 1,
        }

        # Build envelope (no signature wrapper for OpenCRVS)
        envelope = {
            "header": header,
            "message": message,
        }

        return envelope

    def _parse_query(self, query_type: str, query_value: str) -> Any:
        """Parse query value based on query type.

        Args:
            query_type: Query type (idtype-value, predicate, etc.)
            query_value: Raw query value

        Returns:
            Parsed query object

        Raises:
            ValidationError: If query format is invalid
        """
        if query_type == QueryType.IDTYPE_VALUE:
            if ":" in query_value:
                id_type, id_value = query_value.split(":", 1)
                return {
                    "type": id_type.strip(),
                    "value": id_value.strip(),
                }
            else:
                raise ValidationError(
                    f"For query_type 'idtype-value', query_value must be in format 'TYPE:VALUE', got: {query_value}"
                )
        elif query_type == QueryType.PREDICATE:
            # For predicate, query_value is the CEL expression string
            return query_value
        else:
            # For other types (expression, graphql), pass through as-is
            return query_value

    # =========================================================================
    # SUBSCRIPTION METHODS
    # =========================================================================

    def subscribe(
        self,
        event_type: str,
        filter_query: dict | None = None,
        notify_record_type: str = "Person",
    ) -> dict:
        """Subscribe to registry events.

        Args:
            event_type: Event type to subscribe to (e.g., 'REGISTER', 'UPDATE', 'DELETE')
            filter_query: Optional filter criteria (type/value dict for idtype-value)
            notify_record_type: Record type for notifications (default: Person)

        Returns:
            Subscribe response dict with subscription details

        Raises:
            UserError: If request fails
            ValidationError: If parameters are invalid
        """
        if not event_type:
            raise ValidationError("event_type is required")

        now = datetime.now(UTC)
        transaction_id = str(uuid.uuid4())
        reference_id = str(uuid.uuid4())

        # Build subscribe_criteria per DCI spec
        subscribe_criteria = {
            "reg_event_type": event_type,
            "notify_record_type": notify_record_type,
        }

        # Filter is required by OpenAPI spec and must have type/value structure
        if filter_query:
            subscribe_criteria["filter"] = filter_query
        else:
            # Default "match all" filter per DCI spec
            subscribe_criteria["filter"] = {
                "type": "*",
                "value": "*",
            }

        # Build message with subscribe_request array (required by spec)
        message = {
            "transaction_id": transaction_id,
            "subscribe_request": [
                {
                    "reference_id": reference_id,
                    "timestamp": now.isoformat().replace("+00:00", "Z"),
                    "subscribe_criteria": subscribe_criteria,
                }
            ],
        }

        envelope = self._build_envelope(action="subscribe", message=message)
        endpoint = self.data_source.subscribe_endpoint or "/registry/subscribe"
        return self._make_request(endpoint, envelope)

    def unsubscribe(self, subscription_codes: list[str]) -> dict:
        """Unsubscribe from registry events.

        Args:
            subscription_codes: List of subscription codes to unsubscribe

        Returns:
            Unsubscribe response dict

        Raises:
            UserError: If request fails
            ValidationError: If parameters are invalid
        """
        if not subscription_codes:
            raise ValidationError("At least one subscription_code is required")

        now = datetime.now(UTC)
        transaction_id = str(uuid.uuid4())

        message = {
            "transaction_id": transaction_id,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "subscription_code": subscription_codes,
        }

        envelope = self._build_envelope(action="unsubscribe", message=message)
        return self._make_request("/registry/unsubscribe", envelope)

    # =========================================================================
    # TRANSACTION STATUS METHODS
    # =========================================================================

    def txn_status(
        self,
        attribute_value: str,
        attribute_type: str = "transaction_id",
    ) -> dict:
        """Check transaction status.

        Args:
            attribute_value: Transaction ID or reference ID to check
            attribute_type: Type of ID ('transaction_id' or 'reference_id')

        Returns:
            Transaction status response dict

        Raises:
            UserError: If request fails
            ValidationError: If parameters are invalid
        """
        if not attribute_value:
            raise ValidationError("attribute_value is required")

        if attribute_type not in ("transaction_id", "reference_id"):
            raise ValidationError("attribute_type must be 'transaction_id' or 'reference_id'")

        transaction_id = str(uuid.uuid4())
        reference_id = str(uuid.uuid4())

        message = {
            "transaction_id": transaction_id,
            "txnstatus_request": {
                "reference_id": reference_id,
                "attribute_type": attribute_type,
                "attribute_value": attribute_value,
            },
        }

        envelope = self._build_envelope(action="txn_status", message=message)
        return self._make_request("/registry/txn/status", envelope)

    # =========================================================================
    # ENVELOPE BUILDING
    # =========================================================================

    def _build_search_envelope(
        self,
        query_type: str,
        query: Any,
        registry_type: str,
        registry_event_type: str | None,
        record_type: str,
        page: int,
        page_size: int,
        callback_url: str | None = None,
    ) -> dict:
        """Build search request envelope.

        Args:
            query_type: Query type
            query: Query object
            registry_type: Registry type
            registry_event_type: Optional event type
            record_type: Record type
            page: Page number
            page_size: Page size
            callback_url: Optional callback URL for async

        Returns:
            Envelope dict ready to be sent
        """
        # Validate parameters
        if page < 1:
            raise ValidationError("Page must be >= 1")
        if page_size < 1 or page_size > 1000:
            raise ValidationError("Page size must be between 1 and 1000")

        now = datetime.now(UTC)
        transaction_id = str(uuid.uuid4())
        reference_id = str(uuid.uuid4())

        # Build search criteria
        search_criteria = SearchCriteria(
            version="1.0.0",
            reg_type=registry_type,
            reg_event_type=registry_event_type,
            query_type=query_type,
            query=query,
            pagination=PaginationRequest(
                page_size=page_size,
                page_number=page,
            ),
        )

        # Build search request item
        search_request_item = SearchRequestItem(
            reference_id=reference_id,
            timestamp=now,
            search_criteria=search_criteria,
        )

        # Build search request message
        search_request = SearchRequest(
            transaction_id=transaction_id,
            search_request=[search_request_item],
        )

        # Build envelope with header
        # Use exclude_none=True to avoid sending null values that fail OpenAPI validation
        message = search_request.model_dump(mode="json", by_alias=True, exclude_none=True)
        envelope = self._build_envelope(
            action="search",
            message=message,
            callback_url=callback_url,
        )

        return envelope

    def _build_envelope(
        self,
        action: str,
        message: dict,
        callback_url: str | None = None,
    ) -> dict:
        """Build DCI message envelope with header.

        Args:
            action: DCI action (search, subscribe, notify, etc.)
            message: Message payload
            callback_url: Optional callback URL override

        Returns:
            Envelope dict with signature, header, and message
        """
        now = datetime.now(UTC)
        message_id = str(uuid.uuid4())

        # Determine sender URI (handle Odoo's False for empty Char fields)
        sender_uri = callback_url or self.data_source.our_callback_uri or ""

        # Get sender ID (handle Odoo's False for empty Char fields)
        sender_id = self.data_source.our_sender_id or ""

        # Build header using Pydantic model
        header = DCIMessageHeader(
            version="1.0.0",
            message_id=message_id,
            message_ts=now,
            action=action,
            sender_id=sender_id,
            sender_uri=sender_uri,
            receiver_id=self._get_receiver_id(),
            total_count=1,
            is_msg_encrypted=False,
        )

        # Convert header to dict and ensure meta is present
        header_dict = header.model_dump(mode="json", by_alias=True)

        # Ensure meta is an empty object (required by DCI spec)
        if "meta" not in header_dict or header_dict["meta"] is None:
            header_dict["meta"] = {}

        # Sign the envelope
        envelope = self._sign_request(header_dict, message)

        return envelope

    def _sign_request(self, header: dict, message: dict) -> dict:
        """Sign envelope and add signature block.

        Args:
            header: Message header dict
            message: Message payload dict

        Returns:
            Complete envelope dict with signature, header, and message
        """
        signature = ""

        # Sign if signing key is configured
        if self.data_source.signing_key_id:
            signing_key = self.data_source.signing_key_id

            # Validate signing key state
            if signing_key.state != "active":
                raise UserError(f"Signing key '{signing_key.name}' is not active (state: {signing_key.state})")

            # Get private key bytes
            try:
                private_key_pem = signing_key.private_key
                if not private_key_pem:
                    raise UserError(f"Signing key '{signing_key.name}' has no private key")

                # Convert PEM to bytes
                private_key_bytes = private_key_pem.encode("utf-8")

                # Create signer
                signer = DCISigner(
                    private_key=private_key_bytes,
                    sender_id=self.data_source.our_sender_id,
                    key_id=signing_key.key_id,
                    algorithm=signing_key.algorithm,
                )

                # Sign the message
                signature = signer.sign(header, message)

                _logger.debug(
                    "Signed DCI message with key '%s' (algorithm: %s)",
                    signing_key.key_id,
                    signing_key.algorithm,
                )

            except Exception as e:
                _logger.error("Failed to sign DCI message: %s", str(e))
                raise UserError(f"Failed to sign DCI message: {str(e)}") from e
        else:
            _logger.debug(
                "No signing key configured for data source '%s' - sending unsigned request",
                self.data_source.name,
            )

        # Build envelope
        envelope = {
            "signature": signature,
            "header": header,
            "message": message,
        }

        return envelope

    # =========================================================================
    # HTTP REQUEST HANDLING
    # =========================================================================

    def _make_request(self, endpoint: str, envelope: dict, _retry_auth: bool = True) -> dict:
        """Make HTTP POST request with signed envelope.

        Args:
            endpoint: API endpoint path (e.g., 'ENDPOINT_SYNC_SEARCH')
            envelope: Signed envelope dict
            _retry_auth: Internal flag to prevent infinite retry loops on 401

        Returns:
            Response data as dict

        Raises:
            UserError: If request fails or returns error
        """
        url = f"{self.data_source.base_url.rstrip('/')}{endpoint}"

        # Get headers from data source (includes auth)
        headers = self.data_source.get_headers()

        try:
            _logger.info(
                "Making DCI request to %s (action: %s)",
                url,
                envelope["header"]["action"],
            )
            _logger.debug(
                "Request headers: %s",
                {k: (v[:20] + "...") if k == "Authorization" and v else v for k, v in headers.items()},
            )

            # Make synchronous HTTP request
            timeout = self.data_source.timeout or 60
            with httpx.Client(
                timeout=float(timeout),
                verify=self.data_source.verify_ssl,
            ) as client:
                response = client.post(
                    url,
                    json=envelope,
                    headers=headers,
                )

                # Handle 401 Unauthorized - try refreshing token once
                if response.status_code == 401 and _retry_auth and self.data_source.auth_type == "oauth2":
                    _logger.warning("Got 401 Unauthorized, clearing OAuth2 token cache and retrying with fresh token")
                    self.data_source.clear_oauth2_token_cache()
                    return self._make_request(endpoint, envelope, _retry_auth=False)

                # Check for HTTP errors
                response.raise_for_status()

                # Parse response
                response_data = response.json()

                _logger.info(
                    "DCI request successful (status: %s, message_id: %s)",
                    response.status_code,
                    envelope["header"]["message_id"],
                )
                _logger.debug("Response data: %s", response_data)

                return response_data

        except httpx.HTTPStatusError as e:
            # Log technical details for troubleshooting
            technical_detail = f"DCI request failed with status {e.response.status_code}"
            response_text = e.response.text
            try:
                error_data = e.response.json()
                if "header" in error_data and "status_reason_message" in error_data["header"]:
                    technical_detail += f": {error_data['header']['status_reason_message']}"
                else:
                    technical_detail += f": {response_text}"
            except Exception:
                technical_detail += f": {response_text}"

            _logger.error(technical_detail)
            _logger.error("Full response body: %s", response_text)
            _logger.error("Request envelope was: %s", envelope)

            # Show user-friendly message
            user_msg = format_http_error(e.response.status_code, technical_detail)
            raise UserError(user_msg) from e

        except httpx.RequestError as e:
            # Log technical details for troubleshooting
            technical_detail = f"DCI request failed: {str(e)}"
            _logger.error(technical_detail)

            # Determine error type for user-friendly message
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                connection_type = "timeout"
            elif "ssl" in error_str or "certificate" in error_str:
                connection_type = "ssl"
            elif "name or service not known" in error_str or "nodename nor servname" in error_str:
                connection_type = "dns"
            else:
                connection_type = "connection"

            # Show user-friendly message
            user_msg = format_connection_error(connection_type, technical_detail)
            raise UserError(user_msg) from e

        except Exception as e:
            # Log technical details for troubleshooting
            technical_detail = f"Unexpected error during DCI request: {str(e)}"
            _logger.error(technical_detail, exc_info=True)

            # Show generic user-friendly message
            user_msg = _("An unexpected error occurred. Please contact your administrator.")
            raise UserError(user_msg) from e

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _get_receiver_id(self) -> str:
        """Get receiver ID for the target registry.

        Returns:
            Receiver ID string
        """
        if hasattr(self.data_source, "receiver_id") and self.data_source.receiver_id:
            return self.data_source.receiver_id
        return self.data_source.base_url.rstrip("/")

    def _get_registry_type(self) -> str:
        """Get registry type from data source configuration.

        Returns:
            Registry type string (SOCIAL_REGISTRY, CRVS, etc.)
        """
        data_source_type = getattr(self.data_source, "registry_type", None)

        # Return the registry type directly if it matches a known value
        valid_types = {
            RegistryType.CRVS.value,
            RegistryType.SOCIAL_REGISTRY.value,
            RegistryType.IBR.value,
            RegistryType.FUNCTIONAL_REGISTRY.value,
            RegistryType.DISABILITY_REGISTRY.value,
        }

        if data_source_type in valid_types:
            return data_source_type

        _logger.warning(
            "Registry type not configured for data source '%s', defaulting to SOCIAL_REGISTRY",
            self.data_source.name,
        )
        return RegistryType.SOCIAL_REGISTRY.value
