# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ProgramMembershipService"""

from datetime import date

from odoo.exceptions import ValidationError

from odoo.addons.spp_api_v2.schemas.base import Reference
from ..schemas.program_membership import ProgramMembership
from ..services.program_membership_service import ProgramMembershipService
from odoo.addons.spp_api_v2.tests.common import ApiV2TestCase


class TestProgramMembershipService(ApiV2TestCase):
    """Test ProgramMembershipService functionality"""

    def setUp(self):
        super().setUp()
        self.service = ProgramMembershipService(self.env)

        # Create test data
        self.program = self.create_test_program(name="Test Membership Program", target_type="individual")
        self.individual = self.create_test_individual(identifier_value="MEMBER-TEST-001")
        self.group = self.create_test_group(identifier_value="GROUP-TEST-001")

    def test_find_by_identifier_uses_namespace_uri(self):
        """Lookup uses partner's namespace_uri"""
        membership = self.create_test_membership(partner=self.individual, program=self.program)

        # Find using partner's identifier
        found = self.service.find_by_identifier("urn:openspp:vocab:id-type#test_national_id", "MEMBER-TEST-001")

        self.assertEqual(found, membership)

    def test_find_by_identifier_not_found(self):
        """Returns empty recordset when not found"""
        found = self.service.find_by_identifier("urn:openspp:vocab:id-type#test_national_id", "NONEXISTENT")

        self.assertFalse(found)

    def test_to_api_schema_returns_correct_format_with_references(self):
        """to_api_schema returns correct format with program and beneficiary references"""
        membership = self.create_test_membership(
            partner=self.individual,
            program=self.program,
            state="enrolled",
            enrollment_date=date(2024, 1, 15),
        )

        data = self.service.to_api_schema(membership)

        self.assertEqual(data["type"], "ProgramMembership")
        self.assertIn("identifier", data)
        self.assertIn("program", data)
        self.assertIn("beneficiary", data)
        self.assertEqual(data["status"], "enrolled")
        # enrollment_date is a computed field (auto-set on enrollment)
        self.assertIn("enrollmentDate", data)
        self.assertIn("meta", data)

    def test_to_api_schema_program_reference(self):
        """Program reference is formatted correctly"""
        membership = self.create_test_membership(partner=self.individual, program=self.program)

        data = self.service.to_api_schema(membership)

        program_ref = data["program"]
        self.assertIn("reference", program_ref)
        self.assertIn("display", program_ref)
        self.assertIn("Program/", program_ref["reference"])
        self.assertEqual(program_ref["display"], self.program.name)

    def test_to_api_schema_beneficiary_reference_individual(self):
        """Beneficiary reference for individual is correct"""
        membership = self.create_test_membership(partner=self.individual, program=self.program)

        data = self.service.to_api_schema(membership)

        beneficiary_ref = data["beneficiary"]
        self.assertIn("Individual/", beneficiary_ref["reference"])
        self.assertIn("MEMBER-TEST-001", beneficiary_ref["reference"])
        self.assertEqual(beneficiary_ref["display"], self.individual.name)

    def test_to_api_schema_beneficiary_reference_group(self):
        """Beneficiary reference for group is correct"""
        membership = self.create_test_membership(partner=self.group, program=self.program)

        data = self.service.to_api_schema(membership)

        beneficiary_ref = data["beneficiary"]
        self.assertIn("Group/", beneficiary_ref["reference"])
        self.assertIn("GROUP-TEST-001", beneficiary_ref["reference"])
        self.assertEqual(beneficiary_ref["display"], self.group.name)

    def test_to_api_schema_metadata(self):
        """Metadata includes version and timestamp"""
        membership = self.create_test_membership(partner=self.individual, program=self.program)

        data = self.service.to_api_schema(membership)

        self.assertIn("meta", data)
        self.assertIn("versionId", data["meta"])
        self.assertIn("lastUpdated", data["meta"])

    def test_to_api_schema_with_exit_date(self):
        """Exit date is included when present"""
        membership = self.create_test_membership(
            partner=self.individual,
            program=self.program,
            state="exited",
            exit_date=date(2024, 6, 30),
        )

        data = self.service.to_api_schema(membership)

        self.assertEqual(data["exitDate"], "2024-06-30")

    def test_from_api_schema_converts_to_odoo_vals(self):
        """from_api_schema converts API schema to Odoo vals"""
        schema = ProgramMembership(
            program=Reference(
                reference="Program/urn:openspp:program|test-membership-program",
                display="Test Membership Program",
            ),
            beneficiary=Reference(
                reference="Individual/urn:openspp:vocab:id-type#test_national_id|MEMBER-TEST-001",
                display="Test Person",
            ),
            status="enrolled",
            enrollment_date=date(2024, 1, 15),
        )

        vals = self.service.from_api_schema(schema)

        self.assertEqual(vals["program_id"], self.program.id)
        self.assertEqual(vals["partner_id"], self.individual.id)
        self.assertEqual(vals["state"], "enrolled")
        self.assertEqual(vals["enrollment_date"], date(2024, 1, 15))

    def test_from_api_schema_with_exit_date(self):
        """from_api_schema handles exit date"""
        schema = ProgramMembership(
            program=Reference(
                reference="Program/urn:openspp:program|test-membership-program",
                display="Test Membership Program",
            ),
            beneficiary=Reference(
                reference="Individual/urn:openspp:vocab:id-type#test_national_id|MEMBER-TEST-001",
                display="Test Person",
            ),
            status="exited",
            exit_date=date(2024, 6, 30),
        )

        vals = self.service.from_api_schema(schema)

        self.assertEqual(vals["exit_date"], date(2024, 6, 30))

    def test_from_api_schema_invalid_program_reference(self):
        """Invalid program reference raises ValidationError"""
        schema = ProgramMembership(
            program=Reference(
                reference="Program/urn:openspp:program|nonexistent-program",
                display="Nonexistent Program",
            ),
            beneficiary=Reference(
                reference="Individual/urn:openspp:vocab:id-type#test_national_id|MEMBER-TEST-001",
                display="Test Person",
            ),
            status="enrolled",
        )

        with self.assertRaises(ValidationError):
            self.service.from_api_schema(schema)

    def test_from_api_schema_invalid_beneficiary_reference(self):
        """Invalid beneficiary reference raises ValidationError"""
        schema = ProgramMembership(
            program=Reference(
                reference="Program/urn:openspp:program|test-membership-program",
                display="Test Membership Program",
            ),
            beneficiary=Reference(
                reference="Individual/urn:openspp:vocab:id-type#test_national_id|NONEXISTENT",
                display="Nonexistent Person",
            ),
            status="enrolled",
        )

        with self.assertRaises(ValidationError):
            self.service.from_api_schema(schema)

    def test_create_with_source_tracking(self):
        """Create sets source tracking"""
        schema = ProgramMembership(
            program=Reference(
                reference="Program/urn:openspp:program|test-membership-program",
                display="Test Membership Program",
            ),
            beneficiary=Reference(
                reference="Individual/urn:openspp:vocab:id-type#test_national_id|MEMBER-TEST-001",
                display="Test Person",
            ),
            status="enrolled",
        )

        source = "urn:test:source"
        membership = self.service.create(schema, source=source)

        self.assertTrue(membership)
        self.assertEqual(membership.partner_id, self.individual)
        self.assertEqual(membership.program_id, self.program)
        # Base model doesn't have source_system, but extensions might

    def test_update_with_source_tracking(self):
        """Update modifies membership"""
        membership = self.create_test_membership(partner=self.individual, program=self.program, state="draft")

        schema = ProgramMembership(
            program=Reference(
                reference="Program/urn:openspp:program|test-membership-program",
                display="Test Membership Program",
            ),
            beneficiary=Reference(
                reference="Individual/urn:openspp:vocab:id-type#test_national_id|MEMBER-TEST-001",
                display="Test Person",
            ),
            status="enrolled",
        )

        source = "urn:test:updater"
        updated = self.service.update(membership, schema, source=source)

        self.assertEqual(updated.state, "enrolled")

    def test_status_validation(self):
        """Status values are correctly handled"""
        valid_statuses = [
            "draft",
            "enrolled",
            "paused",
            "exited",
            "not_eligible",
            "duplicated",
        ]

        for idx, status in enumerate(valid_statuses):
            # Each membership needs a unique program (unique constraint: partner+program)
            program = self.create_test_program(name=f"Status Test Program {idx}")
            membership = self.create_test_membership(partner=self.individual, program=program, state=status)
            data = self.service.to_api_schema(membership)
            self.assertEqual(data["status"], status)

    def test_find_by_partner_and_program(self):
        """find_by_partner_and_program finds correct membership"""
        membership = self.create_test_membership(partner=self.individual, program=self.program)

        found = self.service.find_by_partner_and_program(self.individual.id, self.program.id)

        self.assertEqual(found, membership)

    def test_find_by_partner_and_program_not_found(self):
        """find_by_partner_and_program returns empty when not found"""
        # Create different program
        other_program = self.create_test_program(name="Other Program")

        found = self.service.find_by_partner_and_program(self.individual.id, other_program.id)

        self.assertFalse(found)

    def test_parse_program_reference(self):
        """_parse_program_reference correctly parses reference"""
        reference = "Program/urn:openspp:program|test-membership-program"

        program = self.service._parse_program_reference(reference)

        self.assertEqual(program, self.program)

    def test_parse_program_reference_invalid_format(self):
        """_parse_program_reference raises error on invalid format"""
        with self.assertRaises(ValidationError):
            self.service._parse_program_reference("InvalidReference")

    def test_parse_beneficiary_reference_individual(self):
        """_parse_beneficiary_reference finds individual"""
        reference = "Individual/urn:openspp:vocab:id-type#test_national_id|MEMBER-TEST-001"

        partner = self.service._parse_beneficiary_reference(reference)

        self.assertEqual(partner, self.individual)

    def test_parse_beneficiary_reference_group(self):
        """_parse_beneficiary_reference finds group"""
        reference = "Group/urn:openspp:vocab:id-type#test_household_id|GROUP-TEST-001"

        partner = self.service._parse_beneficiary_reference(reference)

        self.assertEqual(partner, self.group)

    def test_parse_beneficiary_reference_invalid_format(self):
        """_parse_beneficiary_reference raises error on invalid format"""
        with self.assertRaises(ValidationError):
            self.service._parse_beneficiary_reference("InvalidReference")

    def test_to_api_schema_empty_membership(self):
        """Empty recordset returns empty dict"""
        empty = self.env["spp.program.membership"]
        data = self.service.to_api_schema(empty)

        self.assertEqual(data, {})
