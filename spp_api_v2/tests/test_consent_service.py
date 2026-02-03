# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ConsentService"""

from ..services.consent_service import ConsentService
from .common import ApiV2TestCase


class TestConsentService(ApiV2TestCase):
    """Test ConsentService functionality"""

    def setUp(self):
        super().setUp()
        self.service = ConsentService(self.env)
        self.individual = self.create_test_individual(identifier_value="IND-001")
        self.client = self.create_api_client(
            name="Test Client",
            scopes=[
                {"resource": "individual", "action": "read"},
            ],
        )

    def test_filter_no_consent_returns_minimal(self):
        """Without consent, only identifier returned"""
        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "birthDate": "1990-01-01",
            "gender": {"coding": [{"code": "1"}]},
        }

        filtered = self.service.filter_response(
            self.individual.id,
            self.client,
            "individual",
            data,
        )

        # Should only have identifier
        self.assertIn("identifier", filtered)
        self.assertNotIn("name", filtered)
        self.assertNotIn("birthDate", filtered)
        self.assertIn("_consent", filtered)
        self.assertEqual(filtered["_consent"]["status"], "no_consent")

    def test_filter_with_consent_basic_fields(self):
        """Basic consent returns limited fields"""
        # Create consent with basic field access
        self.create_consent(
            registrant=self.individual,
            grantee_partner=self.client.partner_id,
            field_access="basic",
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "active": True,
            "birthDate": "1990-01-01",
            "gender": {"coding": [{"code": "1"}]},
            "address": [{"city": "Test City"}],
        }

        filtered = self.service.filter_response(
            self.individual.id,
            self.client,
            "individual",
            data,
        )

        # Should have basic fields
        self.assertIn("identifier", filtered)
        self.assertIn("name", filtered)
        self.assertIn("active", filtered)
        self.assertIn("type", filtered)

        # Should NOT have non-basic fields
        self.assertNotIn("birthDate", filtered)
        self.assertNotIn("gender", filtered)
        self.assertNotIn("address", filtered)

        # Should have consent metadata
        self.assertIn("_consent", filtered)
        self.assertEqual(filtered["_consent"]["status"], "given")

    def test_filter_with_consent_all_fields(self):
        """Full consent returns all fields"""
        self.create_consent(
            registrant=self.individual,
            grantee_partner=self.client.partner_id,
            field_access="all",
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "birthDate": "1990-01-01",
            "gender": {"coding": [{"code": "1"}]},
            "address": [{"city": "Test City"}],
        }

        filtered = self.service.filter_response(
            self.individual.id,
            self.client,
            "individual",
            data,
        )

        # Should have all fields
        self.assertIn("identifier", filtered)
        self.assertIn("name", filtered)
        self.assertIn("birthDate", filtered)
        self.assertIn("gender", filtered)
        self.assertIn("address", filtered)

    def test_filter_with_consent_custom_fields(self):
        """Custom field list is respected"""
        # Create consent with custom fields
        consent = self.env["spp.consent"].create(
            {
                "name": "Custom Fields Consent",
                "signatory_id": self.individual.id,
                "recipient_ids": [(6, 0, [self.client.partner_id.id])],
                "recipient_mode": "specific",
                "status": "given",
                "effective_date": "2024-01-01",
                "expiry": "2030-12-31",
            }
        )
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": "individual",
                "field_access": "custom",
                "custom_fields": "name,birthDate",  # Only name and birthDate
                "purpose": "service_delivery",
            }
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "birthDate": "1990-01-01",
            "gender": {"coding": [{"code": "1"}]},
            "address": [{"city": "Test City"}],
        }

        filtered = self.service.filter_response(
            self.individual.id,
            self.client,
            "individual",
            data,
        )

        # Should have custom fields + identifier
        self.assertIn("identifier", filtered)
        self.assertIn("name", filtered)
        self.assertIn("birthDate", filtered)

        # Should NOT have other fields
        self.assertNotIn("gender", filtered)
        self.assertNotIn("address", filtered)

    def test_filter_legal_basis_bypasses_consent(self):
        """legal_obligation client gets data without consent"""
        legal_client = self.create_api_client(
            name="Legal Basis Client",
            legal_basis="legal_obligation",
            legal_basis_reference="Law 123/2024",
            scopes=[{"resource": "individual", "action": "read"}],
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "birthDate": "1990-01-01",
        }

        # No consent created, but should still get data
        filtered = self.service.filter_response(
            self.individual.id,
            legal_client,
            "individual",
            data,
        )

        # Should have data (not just identifier)
        self.assertIn("name", filtered)
        self.assertIn("birthDate", filtered)
        self.assertIn("_consent", filtered)
        self.assertEqual(filtered["_consent"]["status"], "legal_basis")
        self.assertEqual(filtered["_consent"]["basis"], "legal_obligation")

    def test_filter_with_extensions(self):
        """Extensions are filtered based on consent"""
        consent = self.env["spp.consent"].create(
            {
                "name": "Extension Consent",
                "signatory_id": self.individual.id,
                "recipient_ids": [(6, 0, [self.client.partner_id.id])],
                "recipient_mode": "specific",
                "status": "given",
                "effective_date": "2024-01-01",
                "expiry": "2030-12-31",
            }
        )
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": "individual",
                "field_access": "all",
                "purpose": "service_delivery",
                "include_extensions": True,
                "allowed_extensions": "farmer",  # Only farmer extension
            }
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "extension": {
                "farmer": {"farmSize": 2.5},
                "disability": {"type": "visual"},
            },
        }

        filtered = self.service.filter_response(
            self.individual.id,
            self.client,
            "individual",
            data,
        )

        # Should have farmer extension
        self.assertIn("extension", filtered)
        self.assertIn("farmer", filtered["extension"])

        # Should NOT have disability extension
        self.assertNotIn("disability", filtered["extension"])

    def test_check_access_no_scope(self):
        """check_access returns False without scope"""
        result = self.service.check_access(
            self.individual.id,
            self.client,
            "group",  # Client doesn't have group scope
            "read",
        )

        self.assertFalse(result)

    def test_check_access_with_scope_and_consent(self):
        """check_access returns True with both scope and consent"""
        self.create_consent(
            registrant=self.individual,
            grantee_partner=self.client.partner_id,
        )

        result = self.service.check_access(
            self.individual.id,
            self.client,
            "individual",
            "read",
        )

        self.assertTrue(result)

    def test_check_access_with_scope_no_consent(self):
        """check_access returns False without consent"""
        result = self.service.check_access(
            self.individual.id,
            self.client,
            "individual",
            "read",
        )

        self.assertFalse(result)

    def test_check_access_create_action_no_consent_required(self):
        """Create/update actions don't require consent check"""
        create_client = self.create_api_client(
            name="Create Client",
            scopes=[{"resource": "individual", "action": "create"}],
        )

        # Create doesn't check consent
        result = self.service.check_access(
            self.individual.id,
            create_client,
            "individual",
            "create",
        )

        self.assertTrue(result)

    def test_filter_scope_mismatch(self):
        """Consent for wrong resource type returns minimal data"""
        # Create consent for group, not individual
        self.create_consent(
            registrant=self.individual,
            grantee_partner=self.client.partner_id,
            resource_type="group",  # Wrong type
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
        }

        filtered = self.service.filter_response(
            self.individual.id,
            self.client,
            "individual",
            data,
        )

        # Should only have identifier
        self.assertIn("identifier", filtered)
        self.assertNotIn("name", filtered)
        self.assertIn("_consent", filtered)
        self.assertEqual(filtered["_consent"]["status"], "scope_mismatch")
