# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for simulation and aggregation scope registration."""

import logging

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestScopeRegistration(TransactionCase):
    """Test that simulation and aggregation scopes are properly registered."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Create partner and org type for API client
        partner = cls.env["res.partner"].create({"name": "Test Scope Organization"})
        org_type = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not org_type:
            org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not org_type:
            org_type = cls.env["spp.consent.org.type"].create({"name": "Government", "code": "government"})

        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Scope Client",
                "partner_id": partner.id,
                "organization_type_id": org_type.id,
            }
        )

    def test_simulation_scope_available(self):
        """Test that 'simulation' is available as a scope resource."""
        scope = self.env["spp.api.client.scope"].create(
            {
                "client_id": self.api_client.id,
                "resource": "simulation",
                "action": "read",
            }
        )
        self.assertEqual(scope.resource, "simulation")
        self.assertEqual(scope.action, "read")

    def test_aggregation_scope_available(self):
        """Test that 'aggregation' is available as a scope resource."""
        scope = self.env["spp.api.client.scope"].create(
            {
                "client_id": self.api_client.id,
                "resource": "aggregation",
                "action": "read",
            }
        )
        self.assertEqual(scope.resource, "aggregation")
        self.assertEqual(scope.action, "read")

    def test_simulation_has_scope_read(self):
        """Test that has_scope works for simulation:read."""
        self.env["spp.api.client.scope"].create(
            {
                "client_id": self.api_client.id,
                "resource": "simulation",
                "action": "read",
            }
        )
        self.assertTrue(self.api_client.has_scope("simulation", "read"))
        self.assertFalse(self.api_client.has_scope("simulation", "create"))

    def test_simulation_has_scope_create(self):
        """Test that has_scope works for simulation:create."""
        self.env["spp.api.client.scope"].create(
            {
                "client_id": self.api_client.id,
                "resource": "simulation",
                "action": "create",
            }
        )
        self.assertTrue(self.api_client.has_scope("simulation", "create"))

    def test_simulation_has_scope_update(self):
        """Test that has_scope works for simulation:update."""
        self.env["spp.api.client.scope"].create(
            {
                "client_id": self.api_client.id,
                "resource": "simulation",
                "action": "update",
            }
        )
        self.assertTrue(self.api_client.has_scope("simulation", "update"))

    def test_aggregation_has_scope_read(self):
        """Test that has_scope works for aggregation:read."""
        self.env["spp.api.client.scope"].create(
            {
                "client_id": self.api_client.id,
                "resource": "aggregation",
                "action": "read",
            }
        )
        self.assertTrue(self.api_client.has_scope("aggregation", "read"))

    def test_simulation_scope_all_action(self):
        """Test that 'all' action grants access to any simulation action."""
        self.env["spp.api.client.scope"].create(
            {
                "client_id": self.api_client.id,
                "resource": "simulation",
                "action": "all",
            }
        )
        self.assertTrue(self.api_client.has_scope("simulation", "read"))
        self.assertTrue(self.api_client.has_scope("simulation", "create"))
        self.assertTrue(self.api_client.has_scope("simulation", "update"))

    def test_no_cross_resource_access(self):
        """Test that simulation scope doesn't grant aggregation access."""
        self.env["spp.api.client.scope"].create(
            {
                "client_id": self.api_client.id,
                "resource": "simulation",
                "action": "all",
            }
        )
        self.assertFalse(self.api_client.has_scope("aggregation", "read"))
