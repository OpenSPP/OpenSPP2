# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Test trigger controller for DCI client compliance testing.

This controller exposes endpoints that trigger DCI client actions,
allowing external compliance test frameworks to validate client behavior.

IMPORTANT: This controller uses the actual DCIClient class from spp_dci_client,
so compliance tests validate the production client implementation.
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class DCIClientTriggerController(http.Controller):
    """Controller for triggering DCI client actions during compliance testing.

    These endpoints are called by the spdci-compliance test framework
    to trigger client actions against a mock registry server.

    The controller uses the actual DCIClient implementation, ensuring
    that compliance tests validate the production code path.
    """

    def _get_test_data_source(self):
        """Get the test data source configured for compliance testing.

        Returns:
            spp.dci.data.source record configured for mock registry

        Raises:
            ValueError: If no test data source is found
        """
        DataSource = request.env["spp.dci.data.source"].sudo()

        # First try to find one marked for compliance testing
        test_ds = DataSource.search(
            [("is_compliance_test", "=", True)],
            limit=1,
        )

        if not test_ds:
            # Fall back to one named "DCI Compliance Test"
            test_ds = DataSource.search(
                [("name", "=", "DCI Compliance Test")],
                limit=1,
            )

        if not test_ds:
            # Create one pointing to mock registry if none exists
            test_ds = self._create_test_data_source()

        return test_ds

    def _create_test_data_source(self):
        """Create a test data source pointing to mock registry.

        Returns:
            Newly created spp.dci.data.source record
        """
        ICP = request.env["ir.config_parameter"].sudo()
        mock_url = ICP.get_param(
            "dci.client_compliance.mock_registry_url",
            "http://mock_registry:3335",
        )

        # Get the compliance test bearer token
        bearer_token = ICP.get_param(
            "dci.client_compliance.bearer_token",
            "compliance-test-api-key-12345",
        )

        DataSource = request.env["spp.dci.data.source"].sudo()
        return DataSource.create(
            {
                "name": "DCI Compliance Test",
                "code": "dci_compliance_test",
                "base_url": mock_url,
                "registry_type": "social",
                "our_sender_id": "spmis.compliance.test",
                "our_callback_uri": "http://openspp.dci.local:8069/dci/callback",
                "is_compliance_test": True,
                "state": "active",
                "auth_type": "bearer",
                "bearer_token": bearer_token,
            }
        )

    def _get_client(self):
        """Get DCIClient instance for the test data source.

        Returns:
            DCIClient instance
        """
        from odoo.addons.spp_dci_client.services import DCIClient

        data_source = self._get_test_data_source()
        return DCIClient(data_source, request.env)

    def _json_response(self, data, status=200):
        """Create JSON response with proper headers.

        Args:
            data: Response data dict
            status: HTTP status code

        Returns:
            Response object
        """
        return request.make_response(
            json.dumps(data),
            headers=[
                ("Content-Type", "application/json"),
            ],
            status=status,
        )

    @http.route(
        "/dci/test/trigger/search",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def trigger_search(self, **kwargs):
        """Trigger a DCI async search request using DCIClient.

        Uses DCIClient.search_async() to send request to /registry/search.

        Request body (JSON):
            {
                "query_type": "idtype-value",
                "query": {"type": "UIN", "value": "TEST-001"},
                "record_type": "PERSON",
                "page": 1,
                "page_size": 10
            }

        Returns:
            JSON response from the DCI registry (or error details)
        """
        try:
            body = json.loads(request.httprequest.data or "{}")

            query_type = body.get("query_type", "idtype-value")
            query = body.get("query", {})
            record_type = body.get("record_type", "PERSON")
            page = body.get("page", 1)
            page_size = body.get("page_size", 10)

            # Build query_value from query object for DCIClient
            if query_type == "idtype-value":
                if isinstance(query, dict):
                    query_value = f"{query.get('type', 'UIN')}:{query.get('value', 'TEST')}"
                else:
                    query_value = str(query)
            else:
                query_value = query if isinstance(query, str) else str(query)

            _logger.info(
                "[compliance-trigger] Triggering search_async via DCIClient: type=%s, query=%s",
                query_type,
                query_value,
            )

            # Use DCIClient to make the request
            client = self._get_client()
            result = client.search_async(
                query_type=query_type,
                query_value=query_value,
                record_type=record_type,
                page=page,
                page_size=page_size,
            )

            _logger.info("[compliance-trigger] Search completed successfully")
            return self._json_response({"success": True, "result": result})

        except Exception as e:
            _logger.error("[compliance-trigger] Search failed: %s", str(e), exc_info=True)
            return self._json_response(
                {"success": False, "error": str(e), "error_type": type(e).__name__},
                status=500,
            )

    @http.route(
        "/dci/test/trigger/subscribe",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def trigger_subscribe(self, **kwargs):
        """Trigger a DCI subscribe request using DCIClient.

        Uses DCIClient.subscribe() with proper subscribe_request format.

        Request body (JSON):
            {
                "event_type": "REGISTER",
                "filter": {"type": "UIN", "value": "*"}
            }

        Returns:
            JSON response from the DCI registry (or error details)
        """
        try:
            body = json.loads(request.httprequest.data or "{}")

            event_type = body.get("event_type", "REGISTER")
            filter_query = body.get("filter")

            _logger.info(
                "[compliance-trigger] Triggering subscribe via DCIClient: event_type=%s",
                event_type,
            )

            # Use DCIClient to make the request
            client = self._get_client()
            result = client.subscribe(
                event_type=event_type,
                filter_query=filter_query,
            )

            _logger.info("[compliance-trigger] Subscribe completed successfully")
            return self._json_response({"success": True, "result": result})

        except Exception as e:
            _logger.error("[compliance-trigger] Subscribe failed: %s", str(e), exc_info=True)
            return self._json_response(
                {"success": False, "error": str(e), "error_type": type(e).__name__},
                status=500,
            )

    @http.route(
        "/dci/test/trigger/unsubscribe",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def trigger_unsubscribe(self, **kwargs):
        """Trigger a DCI unsubscribe request using DCIClient.

        Request body (JSON):
            {
                "subscription_codes": ["sub-001", "sub-002"]
            }

        Returns:
            JSON response from the DCI registry (or error details)
        """
        try:
            body = json.loads(request.httprequest.data or "{}")

            subscription_codes = body.get("subscription_codes", [])
            if isinstance(subscription_codes, str):
                subscription_codes = [subscription_codes]

            _logger.info(
                "[compliance-trigger] Triggering unsubscribe via DCIClient: codes=%s",
                subscription_codes,
            )

            # Use DCIClient to make the request
            client = self._get_client()
            result = client.unsubscribe(subscription_codes=subscription_codes)

            _logger.info("[compliance-trigger] Unsubscribe completed successfully")
            return self._json_response({"success": True, "result": result})

        except Exception as e:
            _logger.error("[compliance-trigger] Unsubscribe failed: %s", str(e), exc_info=True)
            return self._json_response(
                {"success": False, "error": str(e), "error_type": type(e).__name__},
                status=500,
            )

    @http.route(
        "/dci/test/trigger/txn_status",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def trigger_txn_status(self, **kwargs):
        """Trigger a DCI transaction status request using DCIClient.

        Request body (JSON):
            {
                "transaction_id": "txn-001",
                "attribute_type": "transaction_id"
            }

        Returns:
            JSON response from the DCI registry (or error details)
        """
        try:
            body = json.loads(request.httprequest.data or "{}")

            attribute_value = body.get("transaction_id", body.get("attribute_value", ""))
            attribute_type = body.get("attribute_type", "transaction_id")

            _logger.info(
                "[compliance-trigger] Triggering txn_status via DCIClient: %s=%s",
                attribute_type,
                attribute_value,
            )

            # Use DCIClient to make the request
            client = self._get_client()
            result = client.txn_status(
                attribute_value=attribute_value,
                attribute_type=attribute_type,
            )

            _logger.info("[compliance-trigger] Txn status completed successfully")
            return self._json_response({"success": True, "result": result})

        except Exception as e:
            _logger.error("[compliance-trigger] Txn status failed: %s", str(e), exc_info=True)
            return self._json_response(
                {"success": False, "error": str(e), "error_type": type(e).__name__},
                status=500,
            )

    @http.route(
        "/dci/test/trigger/health",
        type="http",
        auth="none",
        methods=["GET"],
        csrf=False,
    )
    def health_check(self, **kwargs):
        """Health check endpoint for compliance test framework.

        Returns:
            JSON with status and data source info
        """
        try:
            data_source = self._get_test_data_source()
            return self._json_response(
                {
                    "status": "ok",
                    "data_source": {
                        "name": data_source.name,
                        "base_url": data_source.base_url,
                        "sender_id": data_source.our_sender_id,
                        "auth_type": data_source.auth_type,
                    },
                    "client_version": "DCIClient",
                }
            )
        except Exception as e:
            return self._json_response(
                {"status": "error", "error": str(e)},
                status=500,
            )
