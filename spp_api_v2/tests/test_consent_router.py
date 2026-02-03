# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Tests for Consent API Router endpoints.

Tests the consent router's security-critical features:
- _find_consent_for_client() helper function
- External ID lookups (not DB IDs)
- Category-based consent access
- Consent status checking
- Consent revocation
"""

from datetime import date, timedelta

from .common import ApiV2HttpTestCase


class TestConsentRouterSecurity(ApiV2HttpTestCase):
    """Test consent router endpoints with security focus"""

    def setUp(self):
        super().setUp()

        # Get or create organization types (may already exist from module data)
        self.org_type_ngo = self.env["spp.consent.org.type"].search([("code", "=", "ngo")], limit=1)
        if not self.org_type_ngo:
            self.org_type_ngo = self.env["spp.consent.org.type"].create({"name": "NGO", "code": "ngo"})
        self.org_type_government = self.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not self.org_type_government:
            self.org_type_government = self.env["spp.consent.org.type"].create(
                {"name": "Government", "code": "government"}
            )

        # Create individual
        self.individual = self.create_test_individual(identifier_value="IND-001")

        # Create controller
        self.controller = self.env["res.partner"].create({"name": "National Registry"})

    def _create_consent_with_external_id(
        self,
        registrant,
        recipient_partner=None,
        recipient_mode="specific",
        allowed_org_types=None,
        status="given",
    ):
        """Helper to create consent with external_id"""
        vals = {
            "name": f"Consent - {registrant.name}",
            "controller_id": self.controller.id,
            "status": status,
            "effective_date": date.today(),
            "expiry": date.today() + timedelta(days=365),
            "recipient_mode": recipient_mode,
        }

        if registrant.is_group:
            vals["group_id"] = registrant.id
        else:
            vals["signatory_id"] = registrant.id

        if recipient_mode == "specific" and recipient_partner:
            vals["recipient_ids"] = [(6, 0, [recipient_partner.id])]
        elif allowed_org_types:
            vals["allowed_recipient_types"] = [(6, 0, [t.id for t in allowed_org_types])]

        consent = self.env["spp.consent"].create(vals)

        # Create API scope
        self.env["spp.consent.scope"].create(
            {
                "consent_id": consent.id,
                "resource_type": "individual",
                "purpose": "service_delivery",
                "field_access": "all",
            }
        )

        return consent

    def test_find_consent_for_client_specific_recipient(self):
        """_find_consent_for_client finds consent by external_id for specific recipient"""
        from ..routers.consent import _find_consent_for_client

        ngo_client = self.create_api_client(name="NGO Client", organization_type="ngo")

        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            recipient_mode="specific",
        )

        # Find by external_id
        found = _find_consent_for_client(self.env, consent.external_id, ngo_client, require_active=False)

        self.assertEqual(found, consent, "Should find consent by external_id")

    def test_find_consent_for_client_wrong_recipient(self):
        """_find_consent_for_client returns empty for non-recipient client"""
        from ..routers.consent import _find_consent_for_client

        ngo_client = self.create_api_client(name="NGO Client", organization_type="ngo")
        other_client = self.create_api_client(name="Other Client", organization_type="private")

        # Create consent for NGO client only
        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            recipient_mode="specific",
        )

        # Other client should NOT find it
        found = _find_consent_for_client(self.env, consent.external_id, other_client, require_active=False)

        self.assertFalse(found, "Should not find consent for non-recipient")

    def test_find_consent_for_client_category_based_match(self):
        """_find_consent_for_client finds category-based consent by org type"""
        from ..routers.consent import _find_consent_for_client

        ngo_client = self.create_api_client(name="NGO Client", organization_type="ngo")

        # Create category-based consent for all NGOs
        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo],
        )

        # NGO client should find it via org type matching
        found = _find_consent_for_client(self.env, consent.external_id, ngo_client, require_active=False)

        self.assertEqual(found, consent, "Should find consent via org type match")

    def test_find_consent_for_client_category_no_match(self):
        """_find_consent_for_client returns empty when org type doesn't match"""
        from ..routers.consent import _find_consent_for_client

        gov_client = self.create_api_client(name="Government Client", organization_type="government")

        # Create category-based consent for NGOs only
        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo],
        )

        # Government client should NOT find it
        found = _find_consent_for_client(self.env, consent.external_id, gov_client, require_active=False)

        self.assertFalse(found, "Should not find consent with wrong org type")

    def test_find_consent_for_client_require_active_given(self):
        """_find_consent_for_client with require_active=True finds 'given' status"""
        from ..routers.consent import _find_consent_for_client

        ngo_client = self.create_api_client(name="NGO Client", organization_type="ngo")

        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            status="given",
        )

        found = _find_consent_for_client(self.env, consent.external_id, ngo_client, require_active=True)

        self.assertEqual(found, consent, "Should find 'given' consent when active required")

    def test_find_consent_for_client_require_active_withdrawn(self):
        """_find_consent_for_client with require_active=True excludes withdrawn"""
        from ..routers.consent import _find_consent_for_client

        ngo_client = self.create_api_client(name="NGO Client", organization_type="ngo")

        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            status="given",
        )

        # Withdraw it
        consent.action_withdraw(reason="Test withdrawal")

        # Should not find withdrawn consent when require_active=True
        found = _find_consent_for_client(self.env, consent.external_id, ngo_client, require_active=True)

        self.assertFalse(found, "Should not find withdrawn consent when active required")

    def test_find_consent_for_client_require_active_false_finds_withdrawn(self):
        """_find_consent_for_client with require_active=False finds withdrawn"""
        from ..routers.consent import _find_consent_for_client

        ngo_client = self.create_api_client(name="NGO Client", organization_type="ngo")

        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            status="given",
        )

        consent.action_withdraw(reason="Test")

        # Should find withdrawn consent when require_active=False
        found = _find_consent_for_client(self.env, consent.external_id, ngo_client, require_active=False)

        self.assertEqual(found, consent, "Should find withdrawn consent when active not required")

    def test_find_consent_for_client_legacy_consent_without_mode(self):
        """_find_consent_for_client handles legacy consents without recipient_mode"""
        from ..routers.consent import _find_consent_for_client

        ngo_client = self.create_api_client(name="NGO Client", organization_type="ngo")

        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
            recipient_mode="specific",
        )

        # Simulate legacy consent by removing recipient_mode
        # Use SQL to bypass the consent immutability constraint
        self.env.cr.execute(
            "UPDATE spp_consent SET recipient_mode = NULL WHERE id = %s",
            (consent.id,),
        )
        consent.invalidate_recordset()

        # Should still find it
        found = _find_consent_for_client(self.env, consent.external_id, ngo_client, require_active=False)

        self.assertEqual(found, consent, "Should find legacy consent without mode")

    def test_find_consent_for_client_external_id_not_db_id(self):
        """_find_consent_for_client uses external_id, not database ID"""
        from ..routers.consent import _find_consent_for_client

        ngo_client = self.create_api_client(name="NGO Client", organization_type="ngo")

        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_partner=ngo_client.partner_id,
        )

        # Try to find with DB ID (should fail)
        found_by_db_id = _find_consent_for_client(self.env, str(consent.id), ngo_client, require_active=False)

        # Should NOT find by DB ID
        self.assertFalse(found_by_db_id, "Should not find consent by DB ID")

        # Should find by external_id
        found_by_external_id = _find_consent_for_client(self.env, consent.external_id, ngo_client, require_active=False)

        self.assertEqual(
            found_by_external_id,
            consent,
            "Should find consent by external_id",
        )

    def test_find_consent_for_client_multiple_recipients(self):
        """_find_consent_for_client finds consent when client is one of multiple recipients"""
        from ..routers.consent import _find_consent_for_client

        ngo1 = self.create_api_client(name="NGO 1", organization_type="ngo")
        ngo2 = self.create_api_client(name="NGO 2", organization_type="ngo")
        ngo3 = self.create_api_client(name="NGO 3", organization_type="ngo")

        # Create consent for NGO 1 and NGO 2 (not NGO 3)
        consent = self.env["spp.consent"].create(
            {
                "name": "Multi-recipient Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "specific",
                "recipient_ids": [(6, 0, [ngo1.partner_id.id, ngo2.partner_id.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # NGO 1 should find it
        found1 = _find_consent_for_client(self.env, consent.external_id, ngo1, require_active=False)
        self.assertEqual(found1, consent)

        # NGO 2 should find it
        found2 = _find_consent_for_client(self.env, consent.external_id, ngo2, require_active=False)
        self.assertEqual(found2, consent)

        # NGO 3 should NOT find it
        found3 = _find_consent_for_client(self.env, consent.external_id, ngo3, require_active=False)
        self.assertFalse(found3)

    def test_find_consent_for_client_multiple_org_types(self):
        """_find_consent_for_client matches consent with multiple org types"""
        from ..routers.consent import _find_consent_for_client

        ngo_client = self.create_api_client(name="NGO", organization_type="ngo")
        gov_client = self.create_api_client(name="Government", organization_type="government")
        private_client = self.create_api_client(name="Private", organization_type="private")

        # Create consent for NGOs and Government (not private)
        consent = self._create_consent_with_external_id(
            registrant=self.individual,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo, self.org_type_government],
        )

        # NGO should find it
        found_ngo = _find_consent_for_client(self.env, consent.external_id, ngo_client, require_active=False)
        self.assertEqual(found_ngo, consent)

        # Government should find it
        found_gov = _find_consent_for_client(self.env, consent.external_id, gov_client, require_active=False)
        self.assertEqual(found_gov, consent)

        # Private should NOT find it
        found_private = _find_consent_for_client(self.env, consent.external_id, private_client, require_active=False)
        self.assertFalse(found_private)
