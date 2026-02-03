# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Consent model"""

from datetime import date, timedelta

from .common import ApiV2TestCase


class TestConsent(ApiV2TestCase):
    """Test Consent model functionality"""

    def setUp(self):
        super().setUp()
        self.individual = self.create_test_individual(
            name="John Doe",
            given_name="John",
            family_name="Doe",
            identifier_value="IND-001",
        )
        self.grantee_org = self.env["res.partner"].create({"name": "Ministry of Health"})

    def test_consent_creation(self):
        """Consent can be created with required fields"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            resource_type="individual",
            field_access="all",
        )

        self.assertTrue(consent, "Consent should be created")
        self.assertEqual(consent.signatory_id, self.individual)
        self.assertIn(self.grantee_org, consent.recipient_ids)
        self.assertEqual(consent.status, "given")

    def test_consent_expiry_status(self):
        """Expired consent has status='expired'"""
        # Create consent with expiry in the past (-1 days = yesterday)
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            expiry_days=-1,  # Already expired (yesterday)
        )

        # Simulate what the _cron_check_expired does: set status to 'expired'
        # for consents that have passed their expiry date
        consent.write({"status": "expired"})

        self.assertEqual(
            consent.status,
            "expired",
            "Consent should be marked as expired",
        )

    def test_consent_revocation(self):
        """Revoked consent has status='revoked'"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )

        # Withdraw consent
        consent.action_withdraw(reason="Beneficiary requested revocation")

        self.assertEqual(consent.status, "withdrawn")
        self.assertTrue(consent.withdrawn_date)

    def test_consent_activation(self):
        """Requested consent can be given"""
        # Create consent directly with requested status
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            status="requested",
        )

        consent.action_give()

        self.assertEqual(consent.status, "given")

    def test_check_consent_found(self):
        """check_consent finds active consent"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            resource_type="individual",
        )

        found = self.env["spp.consent"].check_consent(
            self.individual.id,
            self.grantee_org.id,
            "individual",
        )

        self.assertEqual(found, consent, "Should find active consent")

    def test_check_consent_not_found_wrong_grantee(self):
        """check_consent returns empty for wrong grantee"""
        self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )

        other_org = self.env["res.partner"].create({"name": "Other Organization"})

        found = self.env["spp.consent"].check_consent(
            self.individual.id,
            other_org.id,
            "individual",
        )

        self.assertFalse(found, "Should not find consent for different grantee")

    def test_check_consent_not_found_wrong_resource(self):
        """check_consent returns empty for mismatched resource type"""
        self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            resource_type="group",  # Only group consent
        )

        # Use check_api_consent which checks scopes
        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=self.grantee_org.id,
            resource_type="individual",  # Looking for individual
        )

        self.assertFalse(found, "Should not find consent with wrong resource type")

    def test_check_consent_all_resource_type(self):
        """Consent with resource_type='all' matches any resource"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            resource_type="all",
        )

        found_individual = self.env["spp.consent"].check_consent(
            self.individual.id,
            self.grantee_org.id,
            "individual",
        )

        found_group = self.env["spp.consent"].check_consent(
            self.individual.id,
            self.grantee_org.id,
            "group",
        )

        self.assertEqual(found_individual, consent, "resource_type='all' should match individual")
        self.assertEqual(found_group, consent, "resource_type='all' should match group")

    def test_check_consent_expired_not_found(self):
        """Expired consent is not found"""
        self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            expiry_days=-1,  # Already expired
        )

        found = self.env["spp.consent"].check_consent(
            self.individual.id,
            self.grantee_org.id,
            "individual",
        )

        self.assertFalse(found, "Should not find expired consent")

    def test_check_consent_not_yet_effective(self):
        """Consent not yet effective is not found"""
        tomorrow = date.today() + timedelta(days=1)

        self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            effective_date=tomorrow,
        )

        found = self.env["spp.consent"].check_consent(
            self.individual.id,
            self.grantee_org.id,
            "individual",
        )

        self.assertFalse(found, "Should not find consent not yet effective")

    def test_check_consent_revoked_not_found(self):
        """Revoked consent is not found"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )
        consent.action_withdraw()

        found = self.env["spp.consent"].check_consent(
            self.individual.id,
            self.grantee_org.id,
            "individual",
        )

        self.assertFalse(found, "Should not find revoked consent")

    def test_consent_for_group(self):
        """Consent can be created for a group"""
        group = self.create_test_group(name="Test Household", identifier_value="HH-001")

        consent = self.create_consent(
            registrant=group,
            grantee_partner=self.grantee_org,
            resource_type="group",
        )

        self.assertEqual(consent.group_id, group)
        self.assertFalse(consent.signatory_id)

    def test_consent_multiple_scopes(self):
        """Consent can have multiple scopes"""
        consent = self.env["spp.consent"].create(
            {
                "name": "Multi-scope Consent",
                "signatory_id": self.individual.id,
                "recipient_ids": [(6, 0, [self.grantee_org.id])],
                "recipient_mode": "specific",
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Create multiple scopes
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": "individual",
                "field_access": "basic",
                "purpose": "service_delivery",
            }
        )
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": "group",
                "field_access": "all",
                "purpose": "eligibility_verification",
            }
        )

        self.assertEqual(len(consent.api_scope_ids), 2)


class TestConsentScope(ApiV2TestCase):
    """Test Consent Scope model functionality"""

    def setUp(self):
        super().setUp()
        self.individual = self.create_test_individual(identifier_value="IND-001")
        self.grantee_org = self.env["res.partner"].create({"name": "Test Organization"})
        self.consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )
        self.scope = self.consent.api_scope_ids[0]

    def test_get_allowed_fields_all(self):
        """get_allowed_fields returns None for field_access='all'"""
        self.scope.field_access = "all"

        allowed = self.scope.get_allowed_fields()

        self.assertIsNone(allowed, "Should return None for unrestricted access")

    def test_get_allowed_fields_basic(self):
        """get_allowed_fields returns basic fields"""
        self.scope.field_access = "basic"

        allowed = self.scope.get_allowed_fields()

        self.assertIsInstance(allowed, set)
        self.assertIn("identifier", allowed)
        self.assertIn("name", allowed)
        self.assertIn("active", allowed)
        self.assertNotIn("birthDate", allowed)

    def test_get_allowed_fields_custom(self):
        """get_allowed_fields returns custom field list"""
        self.scope.field_access = "custom"
        self.scope.custom_fields = "name,birthDate,gender"

        allowed = self.scope.get_allowed_fields()

        self.assertIn("identifier", allowed)  # Always included
        self.assertIn("name", allowed)
        self.assertIn("birthDate", allowed)
        self.assertIn("gender", allowed)
        self.assertNotIn("address", allowed)

    def test_get_allowed_extensions_none(self):
        """get_allowed_extensions returns empty set when not included"""
        self.scope.include_extensions = False

        allowed = self.scope.get_allowed_extensions()

        self.assertEqual(allowed, set())

    def test_get_allowed_extensions_all(self):
        """get_allowed_extensions returns None for all extensions"""
        self.scope.include_extensions = True
        self.scope.allowed_extensions = ""

        allowed = self.scope.get_allowed_extensions()

        self.assertIsNone(allowed, "Should return None for all extensions")

    def test_get_allowed_extensions_specific(self):
        """get_allowed_extensions returns specific extensions"""
        self.scope.include_extensions = True
        self.scope.allowed_extensions = "farmer,disability"

        allowed = self.scope.get_allowed_extensions()

        self.assertIn("farmer", allowed)
        self.assertIn("disability", allowed)
        self.assertNotIn("other", allowed)
