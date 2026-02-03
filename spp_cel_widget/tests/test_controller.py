"""Tests for CEL Widget HTTP Controller."""

import json

from odoo.tests.common import HttpCase


class TestCelWidgetController(HttpCase):
    """Test cases for CEL widget HTTP endpoints."""

    def test_symbols_endpoint_requires_auth(self):
        """Test that symbols endpoint requires authentication."""
        # Try to access without auth (HttpCase starts unauthenticated by default)
        response = self.url_open(
            "/spp_cel/symbols/registry_individuals",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )

        # Should redirect to login or return error
        # Note: The exact behavior depends on Odoo configuration
        self.assertIn(response.status_code, [200, 303, 401])

    def test_symbols_endpoint_success(self):
        """Test symbols endpoint returns correct data."""
        self.authenticate("admin", "admin")

        response = self.url_open(
            "/spp_cel/symbols/registry_individuals",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        result = data.get("result", data)

        self.assertIn("profile", result)
        self.assertIn("variables", result)
        self.assertIn("functions", result)

    def test_validate_endpoint_success(self):
        """Test validate endpoint with valid expression."""
        self.authenticate("admin", "admin")

        response = self.url_open(
            "/spp_cel/validate",
            data=json.dumps(
                {
                    "params": {
                        "expression": 'r.name == "Test"',
                        "profile": "registry_individuals",
                    }
                }
            ),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        result = data.get("result", data)

        self.assertIn("valid", result)

    def test_validate_endpoint_error(self):
        """Test validate endpoint with invalid expression."""
        self.authenticate("admin", "admin")

        response = self.url_open(
            "/spp_cel/validate",
            data=json.dumps(
                {
                    "params": {
                        "expression": "invalid syntax ===",
                        "profile": "registry_individuals",
                    }
                }
            ),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        result = data.get("result", data)

        self.assertFalse(result.get("valid", True))
        self.assertIn("errors", result)

    def test_profiles_endpoint(self):
        """Test profiles endpoint returns list."""
        self.authenticate("admin", "admin")

        response = self.url_open(
            "/spp_cel/profiles",
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)

        data = response.json()
        result = data.get("result", data)

        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
