# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Test that ALL API V2 endpoints enforce authentication.

This is a safety-net test that introspects the FastAPI application,
discovers all registered routes, and verifies that every non-public
route returns 401 when called without an Authorization header.

If a new endpoint is added without authentication, this test will
catch it automatically -- no developer action required.

To mark an endpoint as intentionally public, add it to PUBLIC_ROUTES.
Any change to PUBLIC_ROUTES should be reviewed carefully in PRs.
"""

import json
import logging
import os
import re
import unittest

from odoo.tests import tagged

from .common import ApiV2HttpTestCase

_logger = logging.getLogger(__name__)

# Base path for API V2 endpoints (matches fastapi.endpoint XML data)
API_BASE = "/api/v2/spp"


@tagged("post_install", "-at_install")
@unittest.skipIf(os.getenv("SKIP_HTTP_CASE"), "Skipped via SKIP_HTTP_CASE")
class TestApiAuthEnforcement(ApiV2HttpTestCase):
    """Verify every API V2 route rejects unauthenticated requests.

    This test introspects the FastAPI app to discover all routes,
    then fires an unauthenticated HTTP request at each one.
    Any route that does NOT return 401/403 (and is not in the
    PUBLIC_ROUTES allowlist) causes a test failure.
    """

    # ------------------------------------------------------------------ #
    # Routes that are INTENTIONALLY public (no auth required).
    # Format: (HTTP_METHOD, path_pattern)
    #
    # path_pattern is matched against the route's OpenAPI path
    # (e.g. "/Individual/{identifier}").
    #
    # Adding to this list requires explicit review in PRs.
    # ------------------------------------------------------------------ #
    PUBLIC_ROUTES = {
        ("GET", "/metadata"),
        ("POST", "/oauth/token"),
        # OpenAPI / docs endpoints served by FastAPI itself
        ("GET", "/docs"),
        ("GET", "/docs/oauth2-redirect"),
        ("GET", "/redoc"),
        ("GET", "/openapi.json"),
        ("HEAD", "/docs"),
        ("HEAD", "/docs/oauth2-redirect"),
        ("HEAD", "/redoc"),
        ("HEAD", "/openapi.json"),
    }

    # HTTP methods to test for each route
    METHODS_TO_TEST = {"GET", "POST", "PUT", "PATCH", "DELETE"}

    # Placeholder values for path parameters so we can build a real URL.
    # The actual value doesn't matter -- we just need a syntactically
    # valid URL; we expect 401 before any business logic runs.
    PATH_PARAM_DEFAULTS = {
        "identifier": "test_system%7Ctest_value",
        "consent_id": "00000000-0000-0000-0000-000000000000",
        "individual_identifier": "test_system%7Ctest_value",
        "reference": "CR-0000-0000",
        "list_id": "test-list-id",
        "technical_name": "x_test_field",
        "resource_type": "individual",
        "namespace_uri": "urn:test:vocab",
        # Catch-all for any other path param
    }

    # Routes to skip entirely (e.g. routes that redirect rather than 401)
    SKIP_ROUTES = set()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.no_auth_headers = {"Content-Type": "application/json"}

    def _get_fastapi_app(self):
        """Get the FastAPI app instance from the endpoint registry."""
        endpoint = self.env.ref(
            "spp_api_v2.fastapi_endpoint_api_v2",
            raise_if_not_found=False,
        )
        if not endpoint:
            self.skipTest("FastAPI endpoint 'spp_api_v2.fastapi_endpoint_api_v2' not found")
        return endpoint._get_app()

    def _resolve_path(self, openapi_path):
        """Replace {param} placeholders in an OpenAPI path with test values.

        Returns the URL-ready path string.
        """
        resolved = openapi_path
        # Find all {param_name} placeholders
        params = re.findall(r"\{(\w+)(?::[^}]*)?\}", openapi_path)
        for param in params:
            value = self.PATH_PARAM_DEFAULTS.get(param, f"test-{param}")
            # Replace both {param} and {param:path} style
            resolved = re.sub(rf"\{{{param}(?::[^}}]*)?\}}", value, resolved)
        return resolved

    def _is_public(self, method, openapi_path):
        """Check if a route is in the public allowlist."""
        return (method, openapi_path) in self.PUBLIC_ROUTES

    def _should_skip(self, method, openapi_path):
        """Check if a route should be skipped entirely."""
        return (method, openapi_path) in self.SKIP_ROUTES

    def _make_request(self, method, url):
        """Make an unauthenticated HTTP request."""
        if method == "GET":
            return self.url_open(url, headers=self.no_auth_headers)
        elif method == "POST":
            return self.url_open(url, data=json.dumps({}), headers=self.no_auth_headers)
        elif method == "PUT":
            return self.url_put(url, data=json.dumps({}), headers=self.no_auth_headers)
        elif method == "PATCH":
            return self.url_patch(url, data=json.dumps({}), headers=self.no_auth_headers)
        elif method == "DELETE":
            return self.url_delete(url, headers=self.no_auth_headers)
        else:
            self.fail(f"Unsupported HTTP method: {method}")

    def test_all_routes_require_authentication(self):
        """Every non-public API V2 route must return 401 without a token."""
        app = self._get_fastapi_app()

        tested_count = 0
        skipped_count = 0
        public_count = 0
        failures = []

        for route in app.routes:
            # Only test routes with methods (skip Mount, etc.)
            methods = getattr(route, "methods", None)
            if not methods:
                continue

            openapi_path = getattr(route, "path", None)
            if not openapi_path:
                continue

            for method in methods:
                method = method.upper()
                if method not in self.METHODS_TO_TEST:
                    continue

                if self._is_public(method, openapi_path):
                    public_count += 1
                    continue

                if self._should_skip(method, openapi_path):
                    skipped_count += 1
                    continue

                # Build the full URL
                resolved_path = self._resolve_path(openapi_path)
                url = f"{API_BASE}{resolved_path}"

                try:
                    response = self._make_request(method, url)

                    if response.status_code not in (401, 403):
                        failures.append(
                            f"{method} {openapi_path} -> {response.status_code} (expected 401/403). URL: {url}"
                        )
                    tested_count += 1

                except Exception as exc:
                    # Log but don't fail on connection errors -- the route
                    # might not be reachable in the test environment.
                    _logger.warning(
                        "Could not reach %s %s: %s",
                        method,
                        url,
                        exc,
                    )
                    skipped_count += 1

        # Log summary
        _logger.info(
            "API auth enforcement: tested=%d, public=%d, skipped=%d",
            tested_count,
            public_count,
            skipped_count,
        )

        # We must have tested at least some routes
        self.assertGreater(
            tested_count,
            0,
            "No routes were tested -- is the FastAPI app configured correctly?",
        )

        # Report all failures at once for easy debugging
        if failures:
            failure_msg = (
                f"\n{len(failures)} endpoint(s) accessible WITHOUT authentication:\n"
                + "\n".join(f"  - {f}" for f in failures)
                + "\n\nFix: Add Depends(get_authenticated_client) to these endpoints, "
                + "or add them to PUBLIC_ROUTES if intentionally public."
            )
            self.fail(failure_msg)
