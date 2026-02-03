# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Tests for organization type immutability security constraint.

SECURITY: Organization type verification prevents attackers from changing
their org type (e.g., from 'private' to 'ngo') to bypass category-based consent.

NOTE: organization_type is a COMPUTED field from organization_type_id.
Tests must update organization_type_id (Many2one) to change the type.
"""

from odoo.exceptions import ValidationError

from .common import ApiV2TestCase


class TestOrganizationTypeImmutability(ApiV2TestCase):
    """Test organization type immutability constraint"""

    def _get_org_type(self, code):
        """Helper to get organization type by code."""
        return self.env["spp.consent.org.type"].search([("code", "=", code)], limit=1)

    def test_create_client_with_organization_type(self):
        """Client can be created with organization_type"""
        client = self.create_api_client(
            name="NGO Client",
            organization_type="ngo",
        )

        self.assertEqual(client.organization_type, "ngo")
        self.assertFalse(client.is_organization_type_verified)

    def test_change_organization_type_before_verification(self):
        """Organization type CAN be changed before verification"""
        client = self.create_api_client(
            name="Test Client",
            organization_type="private",
        )

        # Should be able to change before verification via organization_type_id
        ngo_type = self._get_org_type("ngo")
        client.write({"organization_type_id": ngo_type.id})

        self.assertEqual(client.organization_type, "ngo")

    def test_verify_organization_type(self):
        """Administrator can verify organization type"""
        client = self.create_api_client(
            name="Verified Client",
            organization_type="government",
        )

        # Verify organization type
        client.action_verify_organization_type()

        self.assertTrue(client.is_organization_type_verified)
        self.assertEqual(client.is_organization_type_verified_by, self.env.user)
        self.assertTrue(client.is_organization_type_verified_date)

    def test_cannot_change_organization_type_after_verification(self):
        """Organization type CANNOT be changed after verification (SECURITY)"""
        client = self.create_api_client(
            name="Verified NGO",
            organization_type="ngo",
        )

        # Verify it
        client.action_verify_organization_type()

        # Try to change to private (should fail)
        private_type = self._get_org_type("private")
        with self.assertRaises(
            ValidationError,
            msg="Should not allow org type change after verification",
        ):
            client.write({"organization_type_id": private_type.id})

    def test_cannot_change_verified_ngo_to_government(self):
        """Verified NGO cannot become government (attack scenario)"""
        client = self.create_api_client(
            name="Malicious NGO",
            organization_type="ngo",
        )

        client.action_verify_organization_type()

        # Attacker tries to change to government to get broader consent access
        gov_type = self._get_org_type("government")
        with self.assertRaises(ValidationError):
            client.write({"organization_type_id": gov_type.id})

    def test_cannot_change_verified_private_to_ngo(self):
        """Verified private sector cannot become NGO (attack scenario)"""
        client = self.create_api_client(
            name="Private Company",
            organization_type="private",
        )

        client.action_verify_organization_type()

        # Attacker tries to change to NGO to bypass consent restrictions
        ngo_type = self._get_org_type("ngo")
        with self.assertRaises(ValidationError):
            client.write({"organization_type_id": ngo_type.id})

    def test_validation_error_message(self):
        """Validation error has clear message for administrators"""
        client = self.create_api_client(
            name="Verified Client",
            organization_type="un",
        )

        client.action_verify_organization_type()

        other_type = self._get_org_type("other")
        try:
            client.write({"organization_type_id": other_type.id})
            self.fail("Should have raised ValidationError")
        except ValidationError as e:
            self.assertIn("Cannot change organization type", str(e))
            self.assertIn("after verification", str(e))
            self.assertIn("administrator", str(e))

    def test_constraint_only_checks_on_update_not_create(self):
        """Constraint is skipped on create (no _origin)"""
        # This should not raise an error
        client = self.create_api_client(
            name="New Client",
            organization_type="research",
        )

        self.assertEqual(client.organization_type, "research")

    def test_multiple_clients_different_types(self):
        """Multiple clients can have different verified types"""
        ngo_client = self.create_api_client(name="NGO", organization_type="ngo")
        gov_client = self.create_api_client(name="Government", organization_type="government")
        un_client = self.create_api_client(name="UN", organization_type="un")

        ngo_client.action_verify_organization_type()
        gov_client.action_verify_organization_type()
        un_client.action_verify_organization_type()

        # All should be verified with their respective types
        self.assertEqual(ngo_client.organization_type, "ngo")
        self.assertEqual(gov_client.organization_type, "government")
        self.assertEqual(un_client.organization_type, "un")

        # None should be able to change
        private_type = self._get_org_type("private")
        ngo_type = self._get_org_type("ngo")
        gov_type = self._get_org_type("government")

        with self.assertRaises(ValidationError):
            ngo_client.write({"organization_type_id": private_type.id})
        with self.assertRaises(ValidationError):
            gov_client.write({"organization_type_id": ngo_type.id})
        with self.assertRaises(ValidationError):
            un_client.write({"organization_type_id": gov_type.id})
