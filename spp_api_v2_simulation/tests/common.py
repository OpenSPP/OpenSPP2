# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared test fixtures for spp_api_v2_simulation tests."""

import logging
from datetime import datetime

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


class SimulationApiTestCase(TransactionCase):
    """Shared test fixtures for simulation API tests (REST endpoints)."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        # Get or create organization type for API client
        cls.org_type = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type:
            cls.org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

        # Create partner for API client
        cls.api_partner = cls.env["res.partner"].create(
            {
                "name": "Test API Partner",
                "is_registrant": False,
                "is_group": False,
            }
        )

        # Create test API client with simulation scopes
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Simulation Client",
                "partner_id": cls.api_partner.id,
                "organization_type_id": cls.org_type.id,
            }
        )

        # Create simulation:all scope (gives all permissions)
        cls.scope_all = cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "simulation",
                "action": "all",
            }
        )

        # Create test area
        cls.area = cls.env["spp.area"].create(
            {
                "draft_name": "Test Area",
            }
        )

        # Create test registrants (groups)
        cls.group_registrants = cls.env["res.partner"]
        for i in range(5):
            partner = cls.env["res.partner"].create(
                {
                    "name": f"Test Household {i + 1}",
                    "is_registrant": True,
                    "is_group": True,
                    "area_id": cls.area.id,
                }
            )
            cls.group_registrants |= partner

        # Create test registrants (individuals)
        cls.individual_registrants = cls.env["res.partner"]
        for i in range(10):
            partner = cls.env["res.partner"].create(
                {
                    "name": f"Test Individual {i + 1}",
                    "is_registrant": True,
                    "is_group": False,
                }
            )
            cls.individual_registrants |= partner

        # Create a basic scenario in draft state
        cls.scenario_draft = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Draft Test Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "draft",
            }
        )

        # Create entitlement rule for the draft scenario
        cls.rule_draft = cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.scenario_draft.id,
                "amount_mode": "fixed",
                "amount": 1000.0,
            }
        )

        # Create a scenario in ready state
        cls.scenario_ready = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Ready Test Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
                "budget_amount": 5000.0,
                "budget_strategy": "none",
            }
        )

        # Create entitlement rule for the ready scenario
        cls.rule_ready = cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.scenario_ready.id,
                "amount_mode": "fixed",
                "amount": 500.0,
            }
        )

        # Create a completed simulation run
        cls.run_completed = cls.env["spp.simulation.run"].create(
            {
                "scenario_id": cls.scenario_ready.id,
                "state": "completed",
                "beneficiary_count": 5,
                "total_cost": 2500.0,
                "coverage_rate": 50.0,
                "equity_score": 85.0,
                "gini_coefficient": 0.15,
                "total_registry_count": 10,
                "budget_utilization": 50.0,
                "has_disparity": False,
                "leakage_rate": 0.0,
                "undercoverage_rate": 0.0,
                "executed_at": datetime(2024, 1, 1, 0, 0, 0),
                "execution_duration_seconds": 1.5,
            }
        )

        # Create a second completed run for comparison tests
        cls.run_completed_2 = cls.env["spp.simulation.run"].create(
            {
                "scenario_id": cls.scenario_ready.id,
                "state": "completed",
                "beneficiary_count": 4,
                "total_cost": 2000.0,
                "coverage_rate": 40.0,
                "equity_score": 90.0,
                "gini_coefficient": 0.10,
                "total_registry_count": 10,
                "budget_utilization": 40.0,
                "has_disparity": False,
                "leakage_rate": 0.0,
                "undercoverage_rate": 0.0,
                "executed_at": datetime(2024, 1, 2, 0, 0, 0),
                "execution_duration_seconds": 1.2,
            }
        )

        # Create a failed run
        cls.run_failed = cls.env["spp.simulation.run"].create(
            {
                "scenario_id": cls.scenario_ready.id,
                "state": "failed",
                "beneficiary_count": 0,
                "total_cost": 0.0,
                "error_message": "Test error message",
                "executed_at": datetime(2024, 1, 3, 0, 0, 0),
            }
        )


@tagged("post_install", "-at_install")
class SimulationApiTestCommon(TransactionCase):
    """Base test class with shared test data for service-level tests."""

    @classmethod
    def setUpClass(cls):
        """Set up shared test data."""
        super().setUpClass()

        # Create partner and org type for API client
        cls.api_partner = cls.env["res.partner"].create({"name": "Test Simulation Organization"})
        cls.org_type = cls.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not cls.org_type:
            cls.org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not cls.org_type:
            cls.org_type = cls.env["spp.consent.org.type"].create({"name": "Government", "code": "government"})

        # Create an API client for scope testing
        cls.api_client = cls.env["spp.api.client"].create(
            {
                "name": "Test Simulation API Client",
                "partner_id": cls.api_partner.id,
                "organization_type_id": cls.org_type.id,
            }
        )

        # Create test registrants (groups)
        cls.group1 = cls.env["res.partner"].create(
            {
                "name": "Test Group 1",
                "is_registrant": True,
                "is_group": True,
            }
        )
        cls.group2 = cls.env["res.partner"].create(
            {
                "name": "Test Group 2",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create test simulation template
        cls.template = cls.env["spp.simulation.scenario.template"].create(
            {
                "name": "Test Template",
                "description": "A test scenario template",
                "category": "age",
                "target_type": "group",
                "targeting_expression": "age_years(r.birthdate) >= 60",
                "default_amount": 1000.0,
                "default_amount_mode": "fixed",
                "active": True,
            }
        )

        # Create test scenario
        cls.scenario = cls.env["spp.simulation.scenario"].create(
            {
                "name": "Test Scenario",
                "description": "A test scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "budget_amount": 50000.0,
                "budget_strategy": "none",
                "state": "draft",
            }
        )

        # Create entitlement rule for the scenario
        cls.entitlement_rule = cls.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": cls.scenario.id,
                "name": "Base entitlement",
                "amount_mode": "fixed",
                "amount": 500.0,
                "sequence": 10,
            }
        )
