# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Comprehensive tests for API consent matching and filtering.

Tests check_api_consent(), scope filtering, legal basis bypass,
and group consent inheritance - all security-critical for API access control.
"""

from datetime import date, timedelta

from .common import ApiV2TestCase


class TestAPIConsentMatching(ApiV2TestCase):
    """Test API-specific consent checking with check_api_consent()"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create organization types for category-based consent (use search_or_create to avoid duplicates)
        cls.org_type_ngo = cls.env["spp.consent.org.type"].search([("code", "=", "ngo")], limit=1)
        if not cls.org_type_ngo:
            cls.org_type_ngo = cls.env["spp.consent.org.type"].create(
                {
                    "name": "Non-Governmental Organization",
                    "code": "ngo",
                }
            )
        cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].create(
                {
                    "name": "Government Agency",
                    "code": "government",
                }
            )
        cls.org_type_private = cls.env["spp.consent.org.type"].search([("code", "=", "private")], limit=1)
        if not cls.org_type_private:
            cls.org_type_private = cls.env["spp.consent.org.type"].create(
                {
                    "name": "Private Sector",
                    "code": "private",
                }
            )

        # Create data controller
        cls.controller = cls.env["res.partner"].create({"name": "National Registry"})

    def setUp(self):
        super().setUp()

        # Create test individual
        self.individual = self.create_test_individual(
            name="Jane Doe",
            identifier_value="IND-001",
        )

        # Create test group with individual as member
        self.group = self.create_test_group(
            name="Doe Household",
            identifier_value="HH-001",
            members=[(self.individual, None)],  # Add individual as member
        )

    def _create_api_consent(
        self,
        registrant,
        recipient_partner,
        resource_type="individual",
        purpose="service_delivery",
        field_access="all",
        recipient_mode="specific",
        allowed_org_types=None,
        status="given",
        expiry_days=365,
    ):
        """Helper to create API consent with scope"""
        today = date.today()
        vals = {
            "name": f"API Consent - {registrant.name}",
            "controller_id": self.controller.id,
            "status": status,
            "effective_date": today,
            "expiry": today + timedelta(days=expiry_days),
            "recipient_mode": recipient_mode,
        }

        # Set registrant (individual or group)
        if registrant.is_group:
            vals["group_id"] = registrant.id
        else:
            vals["signatory_id"] = registrant.id

        # Set recipients based on mode
        if recipient_mode == "specific":
            vals["recipient_ids"] = [(6, 0, [recipient_partner.id])]
        elif allowed_org_types:
            vals["allowed_recipient_types"] = [(6, 0, [t.id for t in allowed_org_types])]

        consent = self.env["spp.consent"].create(vals)

        # Create API scope
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": resource_type,
                "purpose": purpose,
                "field_access": field_access,
            }
        )

        return consent

    # ========================================================================
    # SPECIFIC RECIPIENT + API SCOPE TESTS
    # ========================================================================

    def test_check_api_consent_with_matching_scope(self):
        """check_api_consent finds consent with matching API scope"""
        ngo_client = self.create_api_client(
            name="NGO Client",
            organization_type="ngo",
        )

        consent = self._create_api_consent(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            resource_type="individual",
        )

        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        self.assertEqual(found, consent, "Should find consent with matching scope")

    def test_check_api_consent_scope_mismatch(self):
        """check_api_consent returns empty when scope doesn't match resource_type"""
        ngo_client = self.create_api_client(name="NGO Client")

        # Create consent with scope for "group" only
        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            resource_type="group",  # Scope only covers groups
        )

        # Try to access "individual" - should fail
        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",  # Requesting individual access
            api_client=ngo_client,
        )

        self.assertFalse(found, "Should not find consent when scope doesn't match")

    def test_check_api_consent_scope_all_matches_any_resource(self):
        """API scope with resource_type='all' matches any resource"""
        ngo_client = self.create_api_client(name="NGO Client")

        consent = self._create_api_consent(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            resource_type="all",  # Covers all resource types
        )

        # Should match individual
        found_individual = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        # Should match group
        found_group = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="group",
            api_client=ngo_client,
        )

        self.assertEqual(found_individual, consent)
        self.assertEqual(found_group, consent)

    def test_check_api_consent_no_scope(self):
        """Consent without API scope is not found by check_api_consent"""
        ngo_client = self.create_api_client(name="NGO Client")

        # Create base consent without API scope
        self.env["spp.consent"].create(
            {
                "name": "Consent Without Scope",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "specific",
                "recipient_ids": [(6, 0, [ngo_client.partner_id.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )
        # Note: No api_scope_ids created

        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        self.assertFalse(found, "Consent without API scope should not be found")

    # ========================================================================
    # CATEGORY-BASED RECIPIENT + API SCOPE TESTS
    # ========================================================================

    def test_category_consent_with_api_scope_matches_ngo(self):
        """Category consent to NGOs matches NGO client with API scope"""
        ngo_client = self.create_api_client(
            name="Red Cross",
            organization_type="ngo",
        )

        consent = self._create_api_consent(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo],
            resource_type="individual",
        )

        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        self.assertEqual(found, consent, "Should find category consent for NGO")

    def test_category_consent_blocks_non_matching_org_type(self):
        """Category consent to NGOs does NOT match government client"""
        # Create government client
        gov_client = self.create_api_client(
            name="Ministry of Health",
            organization_type="government",
        )

        # Create consent for NGOs only
        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=gov_client.partner_id,  # Partner doesn't matter for category
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo],
            resource_type="individual",
        )

        # Government client should NOT get access
        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=gov_client.partner_id.id,
            resource_type="individual",
            api_client=gov_client,  # org type is "government"
        )

        self.assertFalse(found, "Government client should not match NGO-only consent")

    def test_category_consent_multiple_types_with_scope(self):
        """Category consent to multiple org types with proper API scope"""
        # Create clients of different types
        ngo_client = self.create_api_client(name="NGO", organization_type="ngo")
        gov_client = self.create_api_client(name="Gov", organization_type="government")
        private_client = self.create_api_client(name="Private", organization_type="private")

        # Consent to NGOs and Government, but NOT private
        consent = self._create_api_consent(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo, self.org_type_government],
            resource_type="individual",
        )

        # NGO should match
        found_ngo = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        # Government should match
        found_gov = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=gov_client.partner_id.id,
            resource_type="individual",
            api_client=gov_client,
        )

        # Private should NOT match
        found_private = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=private_client.partner_id.id,
            resource_type="individual",
            api_client=private_client,
        )

        self.assertEqual(found_ngo, consent, "NGO should have access")
        self.assertEqual(found_gov, consent, "Government should have access")
        self.assertFalse(found_private, "Private sector should NOT have access")

    # ========================================================================
    # GROUP CONSENT INHERITANCE
    # ========================================================================

    def test_individual_inherits_group_consent(self):
        """Individual inherits consent from their group"""
        ngo_client = self.create_api_client(name="NGO Client")

        # Create consent for the GROUP, not the individual
        consent = self._create_api_consent(
            registrant=self.group,  # Group consent
            recipient_partner=ngo_client.partner_id,
            resource_type="individual",  # Covers individual data
        )

        # Try to access individual data - should find group consent
        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,  # Individual's ID
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        self.assertEqual(found, consent, "Individual should inherit group consent")

    def test_individual_consent_takes_precedence_over_group(self):
        """Individual's own consent is checked before group consent"""
        ngo_client = self.create_api_client(name="NGO Client")

        # Create individual consent
        consent_individual = self._create_api_consent(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            resource_type="individual",
            field_access="basic",  # Limited access
        )

        # Create group consent with more access
        self._create_api_consent(
            registrant=self.group,
            recipient_partner=ngo_client.partner_id,
            resource_type="individual",
            field_access="all",  # Full access
        )

        # Should find individual consent first
        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        self.assertEqual(found, consent_individual, "Individual consent should take precedence")

    def test_no_group_consent_inheritance_for_group_resource(self):
        """Group consent is not inherited when checking individual for group resource"""
        ngo_client = self.create_api_client(name="NGO Client")

        # Create consent for group, scope only covers "group" resource type
        consent = self._create_api_consent(
            registrant=self.group,
            recipient_partner=ngo_client.partner_id,
            resource_type="group",  # Only group data
        )

        # Try to access individual's group data - should work when checking group ID
        found_group = self.env["spp.consent"].check_api_consent(
            registrant_id=self.group.id,  # Using group ID
            recipient_id=ngo_client.partner_id.id,
            resource_type="group",
            api_client=ngo_client,
        )

        # But group consent for "group" resource shouldn't be inherited by individual
        found_individual = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,  # Using individual ID
            recipient_id=ngo_client.partner_id.id,
            resource_type="group",
            api_client=ngo_client,
        )

        self.assertEqual(found_group, consent)
        # Individual checking for group resource type should not inherit
        self.assertFalse(found_individual)

    # ========================================================================
    # LEGAL BASIS BYPASS TESTS
    # ========================================================================

    def test_legal_basis_bypass_no_consent_needed(self):
        """Client with legal_obligation basis doesn't need individual consent"""
        # This test is really about ConsentService, but we can test the principle
        # The check_api_consent still looks for consent, but ConsentService bypasses it
        gov_client = self.create_api_client(
            name="Government Agency",
            legal_basis="legal_obligation",
            legal_basis_reference="Data Protection Act 2024, Section 45",
            require_consent=False,
        )

        # No consent created

        # The base check_consent would return empty
        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=gov_client.partner_id.id,
            resource_type="individual",
            api_client=gov_client,
        )

        self.assertFalse(found, "No consent exists - check_api_consent returns empty")
        # But ConsentService.filter_response will bypass this check (tested in service tests)

    # ========================================================================
    # EDGE CASES
    # ========================================================================

    def test_expired_consent_not_found_by_api_check(self):
        """Expired consent is not found by check_api_consent"""
        ngo_client = self.create_api_client(name="NGO Client")

        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            resource_type="individual",
            expiry_days=-1,  # Already expired
        )

        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        self.assertFalse(found, "Expired consent should not be found")

    def test_withdrawn_consent_not_found_by_api_check(self):
        """Withdrawn consent is not found by check_api_consent"""
        ngo_client = self.create_api_client(name="NGO Client")

        consent = self._create_api_consent(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            resource_type="individual",
        )
        consent.action_withdraw(reason="User requested", channel="api")

        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        self.assertFalse(found, "Withdrawn consent should not be found")

    def test_multiple_scopes_any_matching_is_sufficient(self):
        """Consent with multiple scopes - any matching scope is sufficient"""
        ngo_client = self.create_api_client(name="NGO Client")

        consent = self.env["spp.consent"].create(
            {
                "name": "Multi-scope Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "specific",
                "recipient_ids": [(6, 0, [ngo_client.partner_id.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Create multiple scopes
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": "group",
                "purpose": "service_delivery",
                "field_access": "all",
            }
        )
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": "individual",
                "purpose": "eligibility_verification",
                "field_access": "basic",
            }
        )

        # Should find consent when checking for individual (second scope matches)
        found = self.env["spp.consent"].check_api_consent(
            registrant_id=self.individual.id,
            recipient_id=ngo_client.partner_id.id,
            resource_type="individual",
            api_client=ngo_client,
        )

        self.assertEqual(found, consent, "Should find consent with matching scope")


class TestConsentServiceFiltering(ApiV2TestCase):
    """Test ConsentService.filter_response() for data filtering"""

    def setUp(self):
        super().setUp()
        from ..services.consent_service import ConsentService

        self.service = ConsentService(self.env)
        self.individual = self.create_test_individual(identifier_value="IND-001")
        self.controller = self.env["res.partner"].create({"name": "National Registry"})

        # Create organization types (use search_or_create to avoid duplicates)
        self.org_type_ngo = self.env["spp.consent.org.type"].search([("code", "=", "ngo")], limit=1)
        if not self.org_type_ngo:
            self.org_type_ngo = self.env["spp.consent.org.type"].create({"name": "NGO", "code": "ngo"})
        self.org_type_government = self.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not self.org_type_government:
            self.org_type_government = self.env["spp.consent.org.type"].create(
                {"name": "Government", "code": "government"}
            )

    def _create_api_consent(
        self,
        registrant,
        recipient_partner,
        resource_type="individual",
        field_access="all",
        **kwargs,
    ):
        """Helper to create consent with API scope"""
        consent = self.env["spp.consent"].create(
            {
                "name": f"Consent - {registrant.name}",
                "signatory_id": registrant.id if not registrant.is_group else False,
                "group_id": registrant.id if registrant.is_group else False,
                "controller_id": self.controller.id,
                "recipient_mode": kwargs.get("recipient_mode", "specific"),
                "recipient_ids": [(6, 0, [recipient_partner.id])]
                if kwargs.get("recipient_mode", "specific") == "specific"
                else False,
                "allowed_recipient_types": kwargs.get("allowed_recipient_types", False),
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": resource_type,
                "purpose": kwargs.get("purpose", "service_delivery"),
                "field_access": field_access,
                "custom_fields": kwargs.get("custom_fields", ""),
                "include_extensions": kwargs.get("include_extensions", False),
                "allowed_extensions": kwargs.get("allowed_extensions", ""),
            }
        )

        return consent

    def test_filter_response_no_consent_returns_minimal(self):
        """Without consent, only identifier is returned"""
        client = self.create_api_client(name="Test Client")

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "birthDate": "1990-01-01",
        }

        filtered = self.service.filter_response(
            self.individual.id,
            client,
            "individual",
            data,
        )

        # Should only have identifier
        self.assertIn("identifier", filtered)
        self.assertNotIn("name", filtered)
        self.assertNotIn("birthDate", filtered)
        self.assertIn("_consent", filtered)
        self.assertEqual(filtered["_consent"]["status"], "no_consent")

    def test_filter_response_basic_fields(self):
        """Basic consent returns limited fields"""
        client = self.create_api_client(name="Test Client")
        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=client.partner_id,
            field_access="basic",
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "birthDate": "1990-01-01",
            "gender": {"coding": [{"code": "1"}]},
        }

        filtered = self.service.filter_response(
            self.individual.id,
            client,
            "individual",
            data,
        )

        # Basic fields
        self.assertIn("identifier", filtered)
        self.assertIn("name", filtered)
        self.assertIn("type", filtered)

        # Non-basic fields should be filtered out
        self.assertNotIn("birthDate", filtered)
        self.assertNotIn("gender", filtered)

    def test_filter_response_all_fields(self):
        """Full consent returns all fields"""
        client = self.create_api_client(name="Test Client")
        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=client.partner_id,
            field_access="all",
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "birthDate": "1990-01-01",
            "gender": {"coding": [{"code": "1"}]},
        }

        filtered = self.service.filter_response(
            self.individual.id,
            client,
            "individual",
            data,
        )

        # All fields should be present
        self.assertIn("identifier", filtered)
        self.assertIn("name", filtered)
        self.assertIn("birthDate", filtered)
        self.assertIn("gender", filtered)

    def test_filter_response_custom_fields(self):
        """Custom field list is respected"""
        client = self.create_api_client(name="Test Client")
        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=client.partner_id,
            field_access="custom",
            custom_fields="name,birthDate",
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
            client,
            "individual",
            data,
        )

        # Custom fields + identifier
        self.assertIn("identifier", filtered)
        self.assertIn("name", filtered)
        self.assertIn("birthDate", filtered)

        # Other fields filtered out
        self.assertNotIn("gender", filtered)
        self.assertNotIn("address", filtered)

    def test_filter_response_legal_basis_bypass(self):
        """Legal basis client gets data without consent"""
        client = self.create_api_client(
            name="Government Client",
            legal_basis="legal_obligation",
            legal_basis_reference="Act 123/2024",
            require_consent=False,
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "birthDate": "1990-01-01",
        }

        # No consent created
        filtered = self.service.filter_response(
            self.individual.id,
            client,
            "individual",
            data,
        )

        # Should have data (not just identifier)
        self.assertIn("name", filtered)
        self.assertIn("birthDate", filtered)
        self.assertIn("_consent", filtered)
        self.assertEqual(filtered["_consent"]["status"], "legal_basis")
        self.assertEqual(filtered["_consent"]["basis"], "legal_obligation")

    def test_filter_response_scope_mismatch(self):
        """Consent for wrong resource type returns minimal data"""
        client = self.create_api_client(name="Test Client")
        # Create consent for "group", not "individual"
        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=client.partner_id,
            resource_type="group",
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
        }

        filtered = self.service.filter_response(
            self.individual.id,
            client,
            "individual",
            data,
        )

        # Should only have identifier
        self.assertIn("identifier", filtered)
        self.assertNotIn("name", filtered)
        self.assertEqual(filtered["_consent"]["status"], "scope_mismatch")

    def test_filter_response_extensions_filtering(self):
        """Extensions are filtered based on consent"""
        client = self.create_api_client(name="Test Client")
        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=client.partner_id,
            field_access="all",
            include_extensions=True,
            allowed_extensions="farmer",  # Only farmer extension
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
            client,
            "individual",
            data,
        )

        # Should have farmer extension
        self.assertIn("extension", filtered)
        self.assertIn("farmer", filtered["extension"])

        # Should NOT have disability extension
        self.assertNotIn("disability", filtered["extension"])

    def test_filter_response_category_consent(self):
        """Category-based consent works with filter_response"""
        client = self.create_api_client(
            name="NGO Client",
            organization_type="ngo",
        )

        # Create category consent for NGOs
        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=client.partner_id,
            recipient_mode="category",
            allowed_recipient_types=[(6, 0, [self.org_type_ngo.id])],
            field_access="all",
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
            "birthDate": "1990-01-01",
        }

        filtered = self.service.filter_response(
            self.individual.id,
            client,
            "individual",
            data,
        )

        # Should have all data (category matches)
        self.assertIn("name", filtered)
        self.assertIn("birthDate", filtered)
        self.assertEqual(filtered["_consent"]["status"], "given")

    def test_filter_response_category_consent_no_match(self):
        """Category consent that doesn't match org type returns minimal data"""
        client = self.create_api_client(
            name="Private Client",
            organization_type="private",  # Not NGO
        )

        # Create category consent for NGOs only
        self._create_api_consent(
            registrant=self.individual,
            recipient_partner=client.partner_id,
            recipient_mode="category",
            allowed_recipient_types=[(6, 0, [self.org_type_ngo.id])],
            field_access="all",
        )

        data = {
            "type": "Individual",
            "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "IND-001"}],
            "name": {"given": "John", "family": "Doe"},
        }

        filtered = self.service.filter_response(
            self.individual.id,
            client,
            "individual",
            data,
        )

        # Should only have identifier (private not in allowed types)
        self.assertIn("identifier", filtered)
        self.assertNotIn("name", filtered)
        self.assertEqual(filtered["_consent"]["status"], "no_consent")
