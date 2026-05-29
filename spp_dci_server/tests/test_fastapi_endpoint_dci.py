# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI FastAPI endpoint extension and error middleware."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from fastapi import APIRouter

from odoo.tests import tagged

from .common import DCIServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _build_response(status_code, body):
    """Build a minimal stand-in for starlette.Response that the
    middleware can read as body_iterator."""

    response = MagicMock()
    response.status_code = status_code
    response.media_type = "application/json"
    response.headers = {"content-type": "application/json"}

    async def body_iter():
        yield body if isinstance(body, bytes) else body.encode("utf-8")

    response.body_iterator = body_iter()
    return response


@tagged("post_install", "-at_install")
class TestFormatDCIErrorResponse(DCIServerCommon):
    def test_format_dci_error_response_shape(self):
        from odoo.addons.spp_dci_server.models.fastapi_endpoint_dci import (
            _format_dci_error_response,
        )

        result = _format_dci_error_response(400, "bad request")
        self.assertEqual(result["message"]["ack_status"], "ERR")
        self.assertEqual(result["message"]["error"]["code"], "err.400")
        self.assertEqual(result["message"]["error"]["message"], "bad request")
        # Has timestamp + correlation_id
        self.assertIn("timestamp", result["message"])
        self.assertIn("correlation_id", result["message"])


@tagged("post_install", "-at_install")
class TestDCIErrorResponseMiddleware(DCIServerCommon):
    """The middleware reformats 4xx/5xx responses to the DCI envelope
    shape unless they're already in that shape."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.models.fastapi_endpoint_dci import (
            DCIErrorResponseMiddleware,
        )

        self.middleware = DCIErrorResponseMiddleware(app=None)

    def _dispatch(self, response):
        async def call_next(request):
            return response

        return _run(self.middleware.dispatch(MagicMock(), call_next))

    def test_passthrough_for_success(self):
        original = _build_response(200, '{"ok": true}')
        result = self._dispatch(original)
        # 2xx responses are returned untouched (same object).
        self.assertIs(result, original)

    def test_transforms_plain_detail_error(self):
        original = _build_response(400, '{"detail": "bad input"}')
        result = self._dispatch(original)
        self.assertEqual(result.status_code, 400)
        body = json.loads(result.body.decode("utf-8"))
        self.assertEqual(body["message"]["ack_status"], "ERR")
        self.assertEqual(body["message"]["error"]["code"], "err.400")
        self.assertEqual(body["message"]["error"]["message"], "bad input")

    def test_transforms_dict_detail(self):
        """When detail is a dict (FastAPI structured error), the middleware
        serialises it to a string before embedding."""
        original = _build_response(429, '{"detail": {"code": "rate_limit"}}')
        result = self._dispatch(original)
        body = json.loads(result.body.decode("utf-8"))
        self.assertEqual(body["message"]["error"]["code"], "err.429")
        # The detail dict is JSON-encoded into the message string.
        self.assertIn("rate_limit", body["message"]["error"]["message"])

    def test_already_dci_formatted_passes_through_body(self):
        """If the body already has 'message' (DCI shape), the middleware
        does NOT re-wrap - the original payload survives."""
        dci_body = json.dumps(
            {
                "message": {
                    "ack_status": "ERR",
                    "error": {"code": "err.signature.invalid", "message": "bad sig"},
                }
            }
        )
        original = _build_response(401, dci_body)
        result = self._dispatch(original)
        self.assertEqual(result.status_code, 401)
        # The body is returned as-is (no re-wrap)
        body = json.loads(result.body.decode("utf-8"))
        self.assertEqual(
            body["message"]["error"]["code"], "err.signature.invalid"
        )

    def test_non_json_body_returned_as_is(self):
        original = _build_response(500, b"<html>fatal</html>")
        result = self._dispatch(original)
        self.assertEqual(result.status_code, 500)
        self.assertIn(b"<html>", result.body)


@tagged("post_install", "-at_install")
class TestSppDciServerEndpoint(DCIServerCommon):
    """Test the FastAPI endpoint extension itself."""

    def setUp(self):
        super().setUp()
        self.Endpoint = self.env["fastapi.endpoint"]

    def test_dci_api_app_choice_is_registered(self):
        """The selection_add must add 'dci_api' to fastapi.endpoint.app."""
        field = self.Endpoint._fields["app"]
        keys = [k for k, _ in field.selection]
        self.assertIn("dci_api", keys)

    def test_get_fastapi_routers_returns_dci_routers(self):
        """A DCI endpoint must include the JWKS and registry-aliases routers."""
        endpoint = self.Endpoint.create(
            {
                "name": "test-dci-endpoint",
                "app": "dci_api",
                "root_path": "/test-dci",
            }
        )
        routers = endpoint._get_fastapi_routers()
        # Find the JWKS router by checking for the well-known path.
        all_paths = []
        for router in routers:
            if isinstance(router, APIRouter):
                for route in router.routes:
                    all_paths.append(getattr(route, "path", ""))
        self.assertTrue(
            any("/.well-known/jwks.json" in p for p in all_paths),
            f"JWKS path not found in DCI router paths: {all_paths}",
        )
        # Disability/CRVS/Farmer alias prefixes
        all_paths_str = " ".join(all_paths)
        self.assertIn("/disability/registry", all_paths_str)
        self.assertIn("/crvs/registry", all_paths_str)
        self.assertIn("/farmer/registry", all_paths_str)

    def test_dci_routers_carry_expected_prefixes(self):
        """The 'social/registry' prefix wraps every router except JWKS and
        the registry alias stubs (which carry their own prefixes)."""
        endpoint = self.Endpoint.create(
            {
                "name": "test-dci-endpoint-prefixes",
                "app": "dci_api",
                "root_path": "/test-dci-prefix",
            }
        )
        routers = endpoint._get_fastapi_routers()
        prefix_routers = [r for r in routers if isinstance(r, APIRouter) and r.prefix]
        prefixes = {r.prefix for r in prefix_routers}
        self.assertIn("/social/registry", prefixes)
        self.assertIn("/disability/registry", prefixes)
        self.assertIn("/crvs/registry", prefixes)
        self.assertIn("/farmer/registry", prefixes)
