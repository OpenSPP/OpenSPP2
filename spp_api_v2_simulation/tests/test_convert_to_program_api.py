# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the convert-to-program API endpoint."""

from odoo.tests import tagged

from .common import SimulationApiTestCase


@tagged("-at_install", "post_install")
class TestConvertToProgramApi(SimulationApiTestCase):
    """Test convert-to-program endpoint logic and schemas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a client with only simulation:read scope
        cls.read_only_client = cls.env["spp.api.client"].create(
            {
                "name": "Read Only Client",
                "partner_id": cls.api_partner.id,
                "organization_type_id": cls.org_type.id,
            }
        )
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.read_only_client.id,
                "resource": "simulation",
                "action": "read",
            }
        )

        # Create a client with only simulation:convert scope (but not "all")
        # This tests that convert alone is not sufficient - write is also needed
        cls.convert_only_client = cls.env["spp.api.client"].create(
            {
                "name": "Convert Only Client",
                "partner_id": cls.api_partner.id,
                "organization_type_id": cls.org_type.id,
            }
        )
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.convert_only_client.id,
                "resource": "simulation",
                "action": "convert",
            }
        )

    def test_convert_to_program_request_schema(self):
        """Test ConvertToProgramRequest schema with defaults."""
        from ..schemas.scenario import ConvertToProgramRequest

        request = ConvertToProgramRequest()
        self.assertIsNone(request.name)
        self.assertIsNone(request.currency_code)
        self.assertFalse(request.is_one_time_distribution)
        self.assertFalse(request.import_beneficiaries)
        self.assertIsNone(request.rrule_type)

    def test_convert_to_program_request_with_overrides(self):
        """Test ConvertToProgramRequest schema with overrides."""
        from ..schemas.scenario import ConvertToProgramRequest

        request = ConvertToProgramRequest(
            name="Custom Program",
            currency_code="USD",
            is_one_time_distribution=True,
            import_beneficiaries=True,
            rrule_type="weekly",
            mon=True,
            wed=True,
            fri=True,
        )
        self.assertEqual(request.name, "Custom Program")
        self.assertEqual(request.currency_code, "USD")
        self.assertTrue(request.is_one_time_distribution)
        self.assertTrue(request.import_beneficiaries)
        self.assertEqual(request.rrule_type, "weekly")
        self.assertTrue(request.mon)
        self.assertTrue(request.wed)
        self.assertTrue(request.fri)
        self.assertFalse(request.tue)

    def test_convert_to_program_response_schema(self):
        """Test ConvertToProgramResponse schema."""
        from ..schemas.scenario import ConvertToProgramResponse

        response = ConvertToProgramResponse(
            program_id=1,
            program_name="Test Program",
            scenario_id=5,
            warnings=["Some warning"],
        )
        self.assertEqual(response.program_id, 1)
        self.assertEqual(response.program_name, "Test Program")
        self.assertEqual(response.scenario_id, 5)
        self.assertEqual(len(response.warnings), 1)

    def test_convert_to_program_response_empty_warnings(self):
        """Test ConvertToProgramResponse with no warnings."""
        from ..schemas.scenario import ConvertToProgramResponse

        response = ConvertToProgramResponse(
            program_id=1,
            program_name="Test Program",
            scenario_id=5,
        )
        self.assertEqual(len(response.warnings), 0)

    def test_scope_model_has_convert_action(self):
        """Test that the convert action is available on scope model."""
        self.assertTrue(
            self.convert_only_client.has_scope("simulation", "convert"),
            "Convert client should have simulation:convert scope",
        )

    def test_all_scope_includes_convert(self):
        """Test that simulation:all scope includes convert permission."""
        self.assertTrue(
            self.api_client.has_scope("simulation", "convert"),
            "Client with simulation:all should have convert scope",
        )

    def test_read_only_client_lacks_convert(self):
        """Test that read-only client cannot convert."""
        self.assertFalse(
            self.read_only_client.has_scope("simulation", "convert"),
            "Read-only client should not have simulation:convert scope",
        )

    def test_convert_only_client_lacks_write(self):
        """Test that convert-only client lacks write scope (needs both)."""
        self.assertTrue(
            self.convert_only_client.has_scope("simulation", "convert"),
            "Convert client should have simulation:convert scope",
        )
        self.assertFalse(
            self.convert_only_client.has_scope("simulation", "write"),
            "Convert-only client should not have simulation:write scope",
        )

    def test_convert_options_building(self):
        """Test that options dict is built correctly from request schema."""
        from ..schemas.scenario import ConvertToProgramRequest

        request = ConvertToProgramRequest(
            name="Override Name",
            currency_code="EUR",
            rrule_type="monthly",
            cycle_duration=2,
            day=15,
            month_by="date",
        )

        # Build options dict as the endpoint helper does
        from ..routers.scenario import _build_convert_options

        options = _build_convert_options(request)

        self.assertEqual(options["name"], "Override Name")
        self.assertEqual(options["currency_code"], "EUR")
        self.assertEqual(options["rrule_type"], "monthly")
        self.assertEqual(options["cycle_duration"], 2)
        self.assertEqual(options["day"], 15)
        self.assertEqual(options["month_by"], "date")

    def test_convert_options_weekly_flags(self):
        """Test that weekly day flags are included in options."""
        from ..routers.scenario import _build_convert_options
        from ..schemas.scenario import ConvertToProgramRequest

        request = ConvertToProgramRequest(
            rrule_type="weekly",
            mon=True,
            wed=True,
            fri=True,
        )
        options = _build_convert_options(request)

        self.assertTrue(options.get("mon"))
        self.assertTrue(options.get("wed"))
        self.assertTrue(options.get("fri"))
        self.assertNotIn("tue", options)
        self.assertNotIn("thu", options)

    def test_convert_options_defaults(self):
        """Test that empty request produces minimal options."""
        from ..routers.scenario import _build_convert_options
        from ..schemas.scenario import ConvertToProgramRequest

        request = ConvertToProgramRequest()
        options = _build_convert_options(request)

        self.assertEqual(options, {})

    def test_convert_endpoint_integration(self):
        """Integration test: convert a ready scenario via the service."""
        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "API Integration Test Scenario",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": scenario.id,
                "amount_mode": "fixed",
                "amount": 500.0,
            }
        )

        service = self.env["spp.simulation.service"]
        result = service.convert_to_program(scenario, {})

        self.assertTrue(result["program"].exists())
        self.assertEqual(result["program"].name, "API Integration Test Scenario")
        self.assertEqual(scenario.converted_program_id, result["program"])

    def test_convert_non_ready_scenario_error(self):
        """Test that converting a draft scenario raises error."""
        from odoo.exceptions import UserError

        service = self.env["spp.simulation.service"]
        with self.assertRaises(UserError):
            service.convert_to_program(self.scenario_draft, {})

    def test_convert_already_converted_error(self):
        """Test that converting an already-converted scenario raises error."""
        from odoo.exceptions import UserError

        scenario = self.env["spp.simulation.scenario"].create(
            {
                "name": "Already Converted Test",
                "target_type": "group",
                "targeting_expression": "true",
                "state": "ready",
            }
        )
        self.env["spp.simulation.entitlement.rule"].create(
            {
                "scenario_id": scenario.id,
                "amount_mode": "fixed",
                "amount": 100.0,
            }
        )

        service = self.env["spp.simulation.service"]
        service.convert_to_program(scenario, {})

        with self.assertRaises(UserError):
            service.convert_to_program(scenario, {})
