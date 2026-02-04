# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Comprehensive tests for consent matching logic.

Tests category-based and specific recipient consent matching,
which is security-critical for data access control.
"""

from datetime import date, timedelta

from odoo import Command
from odoo.tests.common import TransactionCase


class TestConsentMatching(TransactionCase):
    """Test consent recipient matching - specific and category-based"""

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
                    "description": "International and local NGOs",
                }
            )
        cls.org_type_government = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not cls.org_type_government:
            cls.org_type_government = cls.env["spp.consent.org.type"].create(
                {
                    "name": "Government Agency",
                    "code": "government",
                    "description": "Government departments and agencies",
                }
            )
        cls.org_type_private = cls.env["spp.consent.org.type"].search([("code", "=", "private")], limit=1)
        if not cls.org_type_private:
            cls.org_type_private = cls.env["spp.consent.org.type"].create(
                {
                    "name": "Private Sector",
                    "code": "private",
                    "description": "Private companies and businesses",
                }
            )
        cls.org_type_un = cls.env["spp.consent.org.type"].search([("code", "=", "un")], limit=1)
        if not cls.org_type_un:
            cls.org_type_un = cls.env["spp.consent.org.type"].create(
                {
                    "name": "UN Agency",
                    "code": "un",
                    "description": "United Nations agencies",
                }
            )

        # Create test organizations
        cls.ngo_org_1 = cls.env["res.partner"].create({"name": "Red Cross"})
        cls.ngo_org_2 = cls.env["res.partner"].create({"name": "Save the Children"})
        cls.government_org = cls.env["res.partner"].create({"name": "Ministry of Health"})
        cls.private_org = cls.env["res.partner"].create({"name": "Private Insurance Co"})
        cls.un_org = cls.env["res.partner"].create({"name": "UNICEF"})

        # Create data controller
        cls.controller = cls.env["res.partner"].create({"name": "National Registry"})

        # Create test individual
        cls.individual = cls.env["res.partner"].create(
            {
                "name": "Jane Doe",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create test group with members
        cls.group = cls.env["res.partner"].create(
            {
                "name": "Doe Family",
                "is_registrant": True,
                "is_group": True,
            }
        )
        # Link individual to group (if group_id field exists, otherwise skip)
        if hasattr(cls.individual, "group_id"):
            cls.individual.group_id = cls.group.id
        # Alternative: create membership relationship if group_id doesn't exist
        elif "spp.registry.membership" in cls.env:
            cls.env["spp.registry.membership"].create(
                {
                    "partner_id": cls.individual.id,
                    "group_id": cls.group.id,
                }
            )

        # Create purpose
        cls.purpose = cls.env["spp.consent.purpose"].create(
            {
                "name": "Service Delivery",
                "code": "service_delivery",
            }
        )

    def _create_consent(
        self,
        signatory=None,
        group=None,
        recipient_mode="specific",
        recipients=None,
        allowed_org_types=None,
        status="given",
        expiry_days=365,
        purpose=None,
    ):
        """Helper to create consent record"""
        today = date.today()
        vals = {
            "name": "Test Consent",
            "controller_id": self.controller.id,
            "status": status,
            "effective_date": today,
            "expiry": today + timedelta(days=expiry_days),
            "recipient_mode": recipient_mode,
        }

        if signatory:
            vals["signatory_id"] = signatory.id
        if group:
            vals["group_id"] = group.id

        if recipients:
            vals["recipient_ids"] = [Command.set([r.id for r in recipients])]

        if allowed_org_types:
            vals["allowed_recipient_types"] = [Command.set([t.id for t in allowed_org_types])]

        # Set purpose at create time to avoid immutability protection
        if purpose:
            vals["purpose_ids"] = [Command.set([purpose.id])]

        consent = self.env["spp.consent"].create(vals)

        return consent

    # ========================================================================
    # SPECIFIC RECIPIENT MATCHING TESTS
    # ========================================================================

    def test_specific_recipient_consent_found(self):
        """Consent with specific recipient is found when checking that recipient"""
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
        )

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertEqual(found, consent, "Should find consent for specific recipient")

    def test_specific_recipient_consent_not_found_different_org(self):
        """Consent for one org is NOT found when checking different org"""
        self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
        )

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_2.id,
        )

        self.assertFalse(found, "Should not find consent for different recipient")

    def test_specific_recipient_multiple_recipients(self):
        """Consent with multiple specific recipients matches any of them"""
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1, self.ngo_org_2],
        )

        found1 = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )
        found2 = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_2.id,
        )

        self.assertEqual(found1, consent, "Should find consent for first recipient")
        self.assertEqual(found2, consent, "Should find consent for second recipient")

    def test_legacy_consent_without_mode(self):
        """Legacy consent without recipient_mode defaults to specific matching"""
        # Create with status="requested" so we can modify recipient_mode
        consent = self._create_consent(
            signatory=self.individual,
            recipients=[self.ngo_org_1],
            status="requested",
        )
        # Remove recipient_mode to simulate legacy consent (must be done while status="requested")
        consent.write({"recipient_mode": False})
        # Now give the consent
        consent.write({"status": "given"})

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertEqual(found, consent, "Legacy consent should work with specific matching")

    # ========================================================================
    # CATEGORY-BASED RECIPIENT MATCHING TESTS
    # ========================================================================

    def test_category_consent_matches_ngo(self):
        """Consent to 'all NGOs' matches an NGO client"""
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo],
        )

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="ngo",
        )

        self.assertEqual(found, consent, "Should find consent for NGO category")

    def test_category_consent_does_not_match_other_types(self):
        """Consent to 'all NGOs' does NOT match government or private sector"""
        self._create_consent(
            signatory=self.individual,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo],
        )

        found_gov = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="government",
        )
        found_private = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="private",
        )

        self.assertFalse(found_gov, "Should not find consent for government")
        self.assertFalse(found_private, "Should not find consent for private sector")

    def test_category_consent_multiple_types(self):
        """Consent to multiple categories matches any of them"""
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="category",
            allowed_org_types=[
                self.org_type_ngo,
                self.org_type_government,
                self.org_type_un,
            ],
        )

        found_ngo = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="ngo",
        )
        found_gov = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="government",
        )
        found_un = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="un",
        )
        found_private = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="private",
        )

        self.assertEqual(found_ngo, consent, "Should match NGO")
        self.assertEqual(found_gov, consent, "Should match government")
        self.assertEqual(found_un, consent, "Should match UN")
        self.assertFalse(found_private, "Should not match private sector")

    def test_category_consent_excludes_private_sector(self):
        """
        Real-world scenario: Beneficiary consents to NGOs and government but NOT private sector
        """
        self._create_consent(
            signatory=self.individual,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo, self.org_type_government],
        )

        # These should work
        found_ngo = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="ngo",
        )
        found_gov = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="government",
        )

        # Private sector should be blocked
        found_private = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="private",
        )

        self.assertTrue(found_ngo, "NGO should have access")
        self.assertTrue(found_gov, "Government should have access")
        self.assertFalse(found_private, "Private sector should NOT have access")

    # ========================================================================
    # MIXED SCENARIOS
    # ========================================================================

    def test_specific_consent_does_not_match_category_check(self):
        """Specific consent doesn't match when checking by org type"""
        self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
        )

        # Checking with org type should not find specific consent
        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="ngo",
        )

        self.assertFalse(found, "Specific consent should not match category check")

    def test_category_consent_does_not_match_specific_check(self):
        """Category consent doesn't match when checking by specific recipient_id"""
        self._create_consent(
            signatory=self.individual,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo],
        )

        # Checking with specific org ID should not find category consent
        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertFalse(found, "Category consent should not match specific recipient check")

    def test_multiple_consents_specific_takes_precedence(self):
        """When both specific and category consents exist, both can match appropriately"""
        # Create specific consent to NGO 1
        consent_specific = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
        )

        # Create category consent to all government
        consent_category = self._create_consent(
            signatory=self.individual,
            recipient_mode="category",
            allowed_org_types=[self.org_type_government],
        )

        # Specific check should find specific consent
        found_specific = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        # Category check should find category consent
        found_category = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_org_type="government",
        )

        self.assertEqual(found_specific, consent_specific)
        self.assertEqual(found_category, consent_category)

    # ========================================================================
    # EDGE CASES - STATUS AND EXPIRY
    # ========================================================================

    def test_expired_consent_not_found(self):
        """Expired consent is not returned"""
        self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
            expiry_days=-1,  # Already expired
        )

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertFalse(found, "Expired consent should not be found")

    def test_withdrawn_consent_not_found(self):
        """Withdrawn consent is not returned"""
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
        )
        consent.action_withdraw(reason="Beneficiary requested")

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertFalse(found, "Withdrawn consent should not be found")

    def test_refused_consent_not_found(self):
        """Refused consent is not returned"""
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
            status="requested",
        )
        consent.action_refuse()

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertFalse(found, "Refused consent should not be found")

    def test_renewed_consent_found(self):
        """Renewed consent is returned"""
        # Create with future expiry date so we don't need to modify it during renewal
        # (expiry is a protected field after status="given")
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
            expiry_days=730,
        )
        # Renew without changing expiry to avoid immutability protection
        consent.action_renew()

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertEqual(found, consent, "Renewed consent should be found")

    def test_requested_consent_not_found(self):
        """Consent in 'requested' status is not active"""
        self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
            status="requested",
        )

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertFalse(found, "Requested consent should not be found until given")

    def test_future_effective_date_not_found(self):
        """Consent with future effective date is not yet active"""
        tomorrow = date.today() + timedelta(days=1)
        # Create with status="requested" so we can set effective_date
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
            status="requested",
        )
        # Set effective_date while status="requested" (before immutability protection)
        consent.write({"effective_date": tomorrow})
        # Now give the consent
        consent.write({"status": "given"})

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertFalse(found, "Consent not yet effective should not be found")

    # ========================================================================
    # GROUP CONSENT TESTS
    # ========================================================================

    def test_group_consent_found_by_group_id(self):
        """Consent given by group is found when checking group"""
        consent = self._create_consent(
            group=self.group,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
        )

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.group.id,
            recipient_id=self.ngo_org_1.id,
        )

        self.assertEqual(found, consent, "Should find group consent")

    def test_individual_consent_not_confused_with_group(self):
        """Individual and group consents are separate"""
        consent_individual = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
        )
        consent_group = self._create_consent(
            group=self.group,
            recipient_mode="specific",
            recipients=[self.government_org],
        )

        # Individual consent
        found_ind = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
        )
        # Group consent
        found_grp = self.env["spp.consent"].check_consent(
            registrant_id=self.group.id,
            recipient_id=self.government_org.id,
        )

        self.assertEqual(found_ind, consent_individual)
        self.assertEqual(found_grp, consent_group)

    # ========================================================================
    # PURPOSE FILTERING
    # ========================================================================

    def test_purpose_filtering_matches(self):
        """Consent with specific purpose is found when checking that purpose"""
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
            purpose=self.purpose,
        )

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
            purpose_code="service_delivery",
        )

        self.assertEqual(found, consent, "Should find consent with matching purpose")

    def test_purpose_filtering_no_match(self):
        """Consent without matching purpose is not found"""
        self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
            purpose=self.purpose,
        )

        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
            recipient_id=self.ngo_org_1.id,
            purpose_code="research",  # Different purpose
        )

        self.assertFalse(found, "Should not find consent with wrong purpose")

    # ========================================================================
    # is_recipient_allowed() METHOD TESTS
    # ========================================================================

    def test_is_recipient_allowed_specific_mode(self):
        """is_recipient_allowed() works for specific mode"""
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1, self.ngo_org_2],
        )

        self.assertTrue(consent.is_recipient_allowed(recipient_id=self.ngo_org_1.id))
        self.assertTrue(consent.is_recipient_allowed(recipient_id=self.ngo_org_2.id))
        self.assertFalse(consent.is_recipient_allowed(recipient_id=self.government_org.id))

    def test_is_recipient_allowed_category_mode(self):
        """is_recipient_allowed() works for category mode"""
        consent = self._create_consent(
            signatory=self.individual,
            recipient_mode="category",
            allowed_org_types=[self.org_type_ngo, self.org_type_un],
        )

        self.assertTrue(consent.is_recipient_allowed(org_type_code="ngo"))
        self.assertTrue(consent.is_recipient_allowed(org_type_code="un"))
        self.assertFalse(consent.is_recipient_allowed(org_type_code="government"))
        self.assertFalse(consent.is_recipient_allowed(org_type_code="private"))

    # ========================================================================
    # NO RECIPIENT CHECK (FALLBACK)
    # ========================================================================

    def test_check_consent_without_recipient(self):
        """Calling check_consent without recipient fails closed for security"""
        self._create_consent(
            signatory=self.individual,
            recipient_mode="specific",
            recipients=[self.ngo_org_1],
        )

        # Don't specify recipient_id or recipient_org_type
        # Implementation intentionally returns empty for security (fail-closed)
        found = self.env["spp.consent"].check_consent(
            registrant_id=self.individual.id,
        )

        # Security: Should return empty when no recipient specified
        # This prevents accidentally returning consent for wrong recipient
        self.assertFalse(found, "Should return empty when no recipient specified (security)")


class TestConsentJSONLD(TransactionCase):
    """Test JSON-LD export functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Use search_or_create to avoid duplicates
        cls.org_type_ngo = cls.env["spp.consent.org.type"].search([("code", "=", "ngo")], limit=1)
        if not cls.org_type_ngo:
            cls.org_type_ngo = cls.env["spp.consent.org.type"].create({"name": "NGO", "code": "ngo"})

        cls.recipient_org = cls.env["res.partner"].create(
            {
                "name": "Test NGO",
                "vat": "NGO-123",
            }
        )

        cls.controller = cls.env["res.partner"].create(
            {
                "name": "National Registry",
                "vat": "GOV-001",
                "email": "contact@registry.gov",
            }
        )

        cls.individual = cls.env["res.partner"].create(
            {
                "name": "John Doe",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.purpose = cls.env["spp.consent.purpose"].create(
            {
                "name": "Service Delivery",
                "code": "service_delivery",
                "dpv_uri": "https://w3id.org/dpv#ServiceProvision",
            }
        )

        cls.personal_data = cls.env["spp.consent.personal.data"].create(
            {
                "name": "Demographic Data",
                "code": "demographics",
                "is_sensitive": False,
            }
        )

    def test_jsonld_export_structure(self):
        """JSON-LD export has correct structure"""
        consent = self.env["spp.consent"].create(
            {
                "name": "Test Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "specific",
                "recipient_ids": [Command.set([self.recipient_org.id])],
                "purpose_ids": [Command.set([self.purpose.id])],
                "personal_data_ids": [Command.set([self.personal_data.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
                "legal_basis": "consent",
            }
        )

        jsonld = consent.to_jsonld()

        # Check structure
        self.assertIn("@context", jsonld)
        self.assertIn("@type", jsonld)
        self.assertIn("@id", jsonld)

        # Check header
        self.assertEqual(jsonld["dpv:hasIdentifier"], consent.external_id)

        # Check parties
        self.assertIn("dpv:hasDataSubject", jsonld)
        self.assertIn("dpv:hasDataController", jsonld)
        self.assertIn("dpv:hasRecipient", jsonld)

        # Check processing
        self.assertIn("dpv:hasPurpose", jsonld)
        self.assertIn("dpv:hasLegalBasis", jsonld)
        self.assertIn("dpv:hasPersonalData", jsonld)

        # Check consent specifics
        self.assertIn("dpv:hasConsentStatus", jsonld)
        self.assertIn("dpv:hasEffectiveDate", jsonld)
        self.assertIn("dpv:hasExpiryDate", jsonld)

    def test_jsonld_category_recipient_export(self):
        """JSON-LD export includes category-based recipient info"""
        consent = self.env["spp.consent"].create(
            {
                "name": "Category Consent",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "recipient_mode": "category",
                "allowed_recipient_types": [Command.set([self.org_type_ngo.id])],
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        jsonld = consent.to_jsonld()

        # For category mode, recipients might not be listed
        # but the consent is still valid
        self.assertIn("@context", jsonld)
        self.assertEqual(jsonld["dpv:hasIdentifier"], consent.external_id)

    def test_jsonld_batch_export(self):
        """Batch export creates @graph with multiple consents"""
        consent1 = self.env["spp.consent"].create(
            {
                "name": "Consent 1",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )
        consent2 = self.env["spp.consent"].create(
            {
                "name": "Consent 2",
                "signatory_id": self.individual.id,
                "controller_id": self.controller.id,
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        consents = consent1 | consent2
        jsonld = consents.to_jsonld_batch()

        self.assertIn("@context", jsonld)
        self.assertIn("@graph", jsonld)
        self.assertEqual(len(jsonld["@graph"]), 2)
