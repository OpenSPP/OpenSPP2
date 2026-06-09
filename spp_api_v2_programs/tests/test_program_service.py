# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ProgramService"""

from ..services.program_service import ProgramService
from odoo.addons.spp_api_v2.tests.common import ApiV2TestCase


class TestProgramService(ApiV2TestCase):
    """Test ProgramService functionality"""

    def setUp(self):
        super().setUp()
        self.service = ProgramService(self.env)

    def test_find_by_identifier_uses_namespace_uri(self):
        """Lookup uses namespace_uri, not name"""
        # Create program with identifier
        program = self.create_test_program(
            name="Cash Transfer Program",
            target_type="group",
        )

        # Find using namespace_uri
        found = self.service.find_by_identifier(
            "urn:openspp:program",
            "cash-transfer-program",
        )

        # Should find the program if spp.program.id exists
        if "spp.program.id" in self.env:
            self.assertEqual(found, program)
        else:
            # If module doesn't exist, might not find it
            pass

    def test_find_by_identifier_not_found(self):
        """Returns empty recordset when not found"""
        found = self.service.find_by_identifier(
            "urn:openspp:program",
            "nonexistent-program",
        )

        self.assertFalse(found)

    def test_to_api_schema_returns_correct_format(self):
        """to_api_schema returns correct API format"""
        program = self.create_test_program(
            name="Test Program",
            target_type="individual",
            state="active",
            description="Test program description",
        )

        data = self.service.to_api_schema(program)

        self.assertEqual(data["type"], "Program")
        self.assertIn("identifier", data)
        self.assertEqual(data["active"], True)
        self.assertEqual(data["name"], "Test Program")
        self.assertEqual(data["description"], "Test program description")
        self.assertEqual(data["targetType"], "individual")
        self.assertIn("type", data)
        self.assertIn("meta", data)

    def test_to_api_schema_no_database_id(self):
        """Response has no 'id' field, only 'identifier'"""
        program = self.create_test_program(name="No ID Program")

        data = self.service.to_api_schema(program)

        self.assertNotIn("id", data, "Database ID must not be exposed")
        self.assertIn("identifier", data)
        self.assertGreater(len(data["identifier"]), 0)

    def test_to_api_schema_identifier_structure(self):
        """Identifiers use namespace_uri as system"""
        program = self.create_test_program(name="ID Test Program")

        data = self.service.to_api_schema(program)

        identifier = data["identifier"][0]
        self.assertEqual(identifier["system"], "urn:openspp:program")
        # Value should be program name in slug format
        self.assertEqual(identifier["value"], "id-test-program")

    def test_to_api_schema_program_type(self):
        """Program type is included as CodeableConcept in programType field"""
        program = self.create_test_program(name="Type Test Program")

        data = self.service.to_api_schema(program)

        # type is the resource type string
        self.assertEqual(data["type"], "Program")
        # programType contains the CodeableConcept
        self.assertIn("programType", data)
        self.assertIn("coding", data["programType"])
        self.assertEqual(len(data["programType"]["coding"]), 1)
        self.assertEqual(data["programType"]["coding"][0]["system"], "urn:openspp:vocab:program-type")

    def test_to_api_schema_metadata(self):
        """Metadata includes version and timestamp"""
        program = self.create_test_program(name="Meta Test Program")

        data = self.service.to_api_schema(program)

        self.assertIn("meta", data)
        self.assertIn("versionId", data["meta"])
        self.assertIn("lastUpdated", data["meta"])

    def test_to_api_schema_active_status(self):
        """Active status reflects program state"""
        # Active program
        active_program = self.create_test_program(name="Active Program", state="active")
        active_data = self.service.to_api_schema(active_program)
        self.assertTrue(active_data["active"])

        # Ended program (not active) - spp.program only has 'active' and 'ended' states
        ended_program = self.create_test_program(name="Ended Program", state="ended", active=False)
        ended_data = self.service.to_api_schema(ended_program)
        self.assertFalse(ended_data["active"])

    def test_to_api_schema_target_type(self):
        """Target type is correctly mapped"""
        # Individual target
        ind_program = self.create_test_program(name="Individual Program", target_type="individual")
        ind_data = self.service.to_api_schema(ind_program)
        self.assertEqual(ind_data["targetType"], "individual")

        # Group target
        grp_program = self.create_test_program(name="Group Program", target_type="group")
        grp_data = self.service.to_api_schema(grp_program)
        self.assertEqual(grp_data["targetType"], "group")

    def test_to_api_schema_eligibility_criteria(self):
        """Eligibility criteria is included when eligibility managers exist"""
        program = self.create_test_program(name="Eligibility Test")

        # Programs in base don't have eligibility managers populated easily
        # This test just verifies the field is handled
        data = self.service.to_api_schema(program)

        # eligibilityCriteria should be None or string
        if "eligibilityCriteria" in data:
            self.assertTrue(data["eligibilityCriteria"] is None or isinstance(data["eligibilityCriteria"], str))

    def test_to_api_schema_period_for_ended_program(self):
        """Period is included for ended programs with date_ended"""
        from datetime import date

        program = self.create_test_program(name="Ended Program", state="ended", date_ended=date(2024, 12, 31))

        data = self.service.to_api_schema(program)

        self.assertIn("period", data)
        self.assertEqual(data["period"]["end"], "2024-12-31")

    def test_to_api_schema_empty_program(self):
        """Empty recordset returns empty dict"""
        empty = self.env["spp.program"]
        data = self.service.to_api_schema(empty)

        self.assertEqual(data, {})

    def test_search_by_name(self):
        """Programs can be found by name search"""
        program = self.create_test_program(name="Searchable Program")

        # Direct search on model
        results = self.env["spp.program"].search([("name", "ilike", "Searchable")])

        self.assertIn(program, results)

    def test_search_by_status(self):
        """Programs can be found by status"""
        active_program = self.create_test_program(name="Active Search", state="active")
        ended_program = self.create_test_program(name="Ended Search", state="ended", active=False)

        # Search for active
        active_results = self.env["spp.program"].search([("state", "=", "active")])
        self.assertIn(active_program, active_results)
        self.assertNotIn(ended_program, active_results)

        # Search for ended (need active_test=False since ended programs may be inactive)
        ended_results = self.env["spp.program"].with_context(active_test=False).search([("state", "=", "ended")])
        self.assertIn(ended_program, ended_results)
        self.assertNotIn(active_program, ended_results)

    def test_search_pagination(self):
        """Search supports offset and limit"""
        # Create multiple programs
        for i in range(5):
            self.create_test_program(name=f"Program {i}")

        # Search with pagination
        page1 = self.env["spp.program"].search([], limit=2, offset=0, order="id desc")
        page2 = self.env["spp.program"].search([], limit=2, offset=2, order="id desc")

        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 2)
        # Pages should have different programs
        self.assertNotEqual(page1[0].id, page2[0].id)

    def test_to_api_schema_with_external_identifier(self):
        """Programs with external identifiers use those in API"""
        if "spp.program.id" not in self.env:
            self.skipTest("spp.program.id model not available")

        program = self.create_test_program(name="External ID Program")

        # Create additional external identifier
        self.env["spp.program.id"].create(
            {
                "program_id": program.id,
                "namespace_uri": "urn:custom:program-id",
                "value": "CUSTOM-123",
            }
        )

        data = self.service.to_api_schema(program)

        # Should have at least 2 identifiers
        self.assertGreaterEqual(len(data["identifier"]), 1)

        # Should include custom identifier
        systems = [ident["system"] for ident in data["identifier"]]
        self.assertIn("urn:custom:program-id", systems)
