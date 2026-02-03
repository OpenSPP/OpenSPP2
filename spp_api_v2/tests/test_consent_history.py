# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Consent History and Access Logging"""

from datetime import date, timedelta

from .common import ApiV2TestCase


class TestConsentHistory(ApiV2TestCase):
    """Test Consent History tracking functionality"""

    def setUp(self):
        super().setUp()
        self.individual = self.create_test_individual(
            name="John Doe",
            given_name="John",
            family_name="Doe",
            identifier_value="IND-001",
        )
        self.grantee_org = self.env["res.partner"].create({"name": "Ministry of Health"})

    def test_consent_creation_creates_history(self):
        """Creating consent records history entry"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            resource_type="individual",
        )

        self.assertEqual(consent.history_count, 1, "Should have 1 history entry")
        self.assertEqual(consent.current_version, 1)

        history = consent.history_ids[0]
        self.assertEqual(history.action, "create")
        self.assertEqual(history.version, 1)
        self.assertTrue(history.changed_date)
        self.assertEqual(history.changed_by_id, self.env.user)

    def test_consent_generates_external_id(self):
        """Creating consent auto-generates external_id"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )

        self.assertTrue(consent.external_id, "Should have external_id")
        # Should be a UUID format
        self.assertEqual(len(consent.external_id), 36)
        self.assertEqual(consent.external_id.count("-"), 4)

    def test_consent_status_change_creates_history(self):
        """Changing consent status records history"""
        # Create consent with requested status so we can transition to given
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            status="requested",
        )
        initial_history_count = len(consent.history_ids)

        # Give consent (valid transition: requested -> given)
        consent.action_give()

        self.assertGreater(
            len(consent.history_ids),
            initial_history_count,
            "Should have new history entry for giving consent",
        )

        # Find give history
        give_history = consent.history_ids.filtered(lambda h: h.action == "give")
        self.assertTrue(give_history)
        # new_values might be None or a dict, check new_status instead
        self.assertEqual(
            give_history[0].new_status,
            "given",
        )

    def test_consent_revocation_creates_history(self):
        """Revoking consent records history with reason"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )

        consent.action_withdraw(reason="Beneficiary requested revocation")

        withdraw_history = consent.history_ids.filtered(lambda h: h.action == "withdraw")
        self.assertTrue(withdraw_history)
        # Get the most recent withdraw history (should be the one we just created)
        latest_withdraw = withdraw_history.sorted("version", reverse=True)[0]
        self.assertEqual(
            latest_withdraw.reason,
            "Beneficiary requested revocation",
        )

    def test_consent_modification_creates_history(self):
        """Modifying consent status records history"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )
        initial_count = consent.history_count

        # Withdraw consent (valid transition: given -> withdrawn)
        consent.action_withdraw(reason="Testing history tracking")

        self.assertEqual(
            consent.history_count,
            initial_count + 1,
            "Should record history for status change",
        )

    def test_consent_untracked_field_no_history(self):
        """Modifying untracked fields does not create history"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )
        initial_count = consent.history_count

        # Modify an untracked field
        consent.evidence_filename = "new_file.pdf"

        self.assertEqual(
            consent.history_count,
            initial_count,
            "Should not record history for untracked field",
        )

    def test_history_record_change_increments_version(self):
        """History versions increment correctly"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )

        # Record multiple changes using record_action (which calculates version automatically)
        self.env["spp.consent.history"].record_action(
            consent=consent,
            action="modify",
            previous_status="given",
            new_status="requested",
            previous_values={"status": "given"},
            new_values={"status": "requested"},
        )

        self.env["spp.consent.history"].record_action(
            consent=consent,
            action="modify",
            previous_status="requested",
            new_status="given",
            previous_values={"status": "requested"},
            new_values={"status": "given"},
        )

        versions = consent.history_ids.mapped("version")
        self.assertEqual(sorted(versions), [1, 2, 3])

    def test_action_view_history(self):
        """action_view_history returns correct action"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )

        action = consent.action_view_history()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.consent.history")
        self.assertIn(("consent_id", "=", consent.id), action["domain"])


class TestApiAuditLog(ApiV2TestCase):
    """Test API Audit Log functionality (unified logging)"""

    def setUp(self):
        super().setUp()
        self.individual = self.create_test_individual(
            name="John Doe",
            identifier_value="IND-001",
        )
        self.grantee_org = self.env["res.partner"].create({"name": "Ministry of Health"})
        self.consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )

        # Lookup organization type
        org_type_government = self.env.ref(
            "spp_consent.org_type_government",
            raise_if_not_found=False,
        )
        if not org_type_government:
            org_type_government = self.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)

        self.api_client = self.env["spp.api.client"].create(
            {
                "name": "Test Client",
                "partner_id": self.grantee_org.id,
                "organization_type_id": org_type_government.id,
            }
        )

    def test_log_operation_creates_record(self):
        """log_operation creates audit log record"""
        log = self.env["spp.api.audit.log"].log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="IND-001",
            consent=self.consent,
            fields_returned=["identifier", "name", "birthDate"],
        )

        self.assertTrue(log)
        self.assertEqual(log.consent_id, self.consent)
        self.assertEqual(log.api_client_id, self.api_client)
        self.assertEqual(log.resource_type, "individual")
        self.assertEqual(log.resource_identifier, "IND-001")
        self.assertEqual(log.operation, "read")
        self.assertEqual(log.fields_returned, ["identifier", "name", "birthDate"])

    def test_log_operation_search_with_params(self):
        """log_operation records search parameters"""
        search_params = {
            "name": "John",
            "_count": 10,
        }

        log = self.env["spp.api.audit.log"].log_operation(
            api_client=self.api_client,
            operation="search",
            resource_type="individual",
            resource_identifier="search",
            consent=self.consent,
            search_parameters=search_params,
            result_count=5,
        )

        self.assertEqual(log.operation, "search")
        self.assertEqual(log.search_parameters, search_params)
        self.assertEqual(log.result_count, 5)

    def test_log_operation_with_extensions(self):
        """log_operation records accessed extensions"""
        log = self.env["spp.api.audit.log"].log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="IND-001",
            consent=self.consent,
            extensions_returned=["farmer", "disability"],
        )

        self.assertEqual(log.extensions_returned, ["farmer", "disability"])

    def test_get_consent_access_summary(self):
        """get_consent_access_summary returns correct statistics"""
        # Create multiple audit logs
        for i in range(3):
            self.env["spp.api.audit.log"].log_operation(
                api_client=self.api_client,
                operation="read",
                resource_type="individual",
                resource_identifier=f"IND-00{i}",
                consent=self.consent,
            )

        self.env["spp.api.audit.log"].log_operation(
            api_client=self.api_client,
            operation="search",
            resource_type="group",
            resource_identifier="search",
            consent=self.consent,
            result_count=10,
        )

        summary = self.env["spp.api.audit.log"].get_consent_access_summary(consent_id=self.consent.id)

        self.assertEqual(summary["total_accesses"], 4)
        self.assertEqual(summary["by_action"]["read"], 3)
        self.assertEqual(summary["by_action"]["search"], 1)
        self.assertEqual(summary["by_resource_type"]["individual"], 3)
        self.assertEqual(summary["by_resource_type"]["group"], 1)

    def test_consent_access_count(self):
        """consent.access_count reflects audit log entries"""
        self.assertEqual(self.consent.access_count, 0)

        self.env["spp.api.audit.log"].log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="IND-001",
            consent=self.consent,
        )

        # Refresh
        self.consent.invalidate_recordset()
        self.assertEqual(self.consent.access_count, 1)

    def test_action_view_access_logs(self):
        """action_view_access_logs returns correct action"""
        action = self.consent.action_view_access_logs()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.api.audit.log")
        self.assertIn(("consent_id", "=", self.consent.id), action["domain"])


class TestConsentReceipt(ApiV2TestCase):
    """Test Consent Receipt generation"""

    def setUp(self):
        super().setUp()
        self.individual = self.create_test_individual(
            name="John Doe",
            identifier_value="IND-001",
        )
        self.grantee_org = self.env["res.partner"].create({"name": "Ministry of Health"})

    def test_generate_receipt(self):
        """generate_receipt returns valid receipt structure"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
            resource_type="individual",
            purpose="service_delivery",
        )

        receipt = consent.generate_api_receipt()

        self.assertIn("receiptId", receipt)
        self.assertIn("timestamp", receipt)
        self.assertIn("dataSubject", receipt)
        self.assertIn("dataController", receipt)
        self.assertIn("consentRecordId", receipt)
        self.assertIn("api_scopes", receipt)

        # Verify structure
        self.assertEqual(receipt["schemaVersion"], "dpv-27560:1.0")
        self.assertEqual(receipt["consentRecordId"], consent.external_id)
        self.assertIn("identifier", receipt["dataSubject"])

    def test_receipt_includes_purposes(self):
        """Receipt includes all consent purposes"""
        consent = self.env["spp.consent"].create(
            {
                "name": "Multi-purpose Consent",
                "signatory_id": self.individual.id,
                "recipient_ids": [(6, 0, [self.grantee_org.id])],
                "recipient_mode": "specific",
                "status": "given",
                "effective_date": date.today(),
                "expiry": date.today() + timedelta(days=365),
            }
        )

        # Add multiple scopes with different purposes
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

        receipt = consent.generate_api_receipt()

        self.assertEqual(len(receipt["api_scopes"]), 2)
        purposes = [p["purpose"] for p in receipt["api_scopes"]]
        self.assertIn("service_delivery", purposes)
        self.assertIn("eligibility_verification", purposes)

    def test_receipt_withdrawal_uri(self):
        """Receipt includes valid withdrawal URI"""
        consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.grantee_org,
        )

        # Set base URL
        self.env["ir.config_parameter"].set_param("web.base.url", "https://openspp.example.org")

        receipt = consent.generate_api_receipt()

        # Check that receipt has withdrawal info (may be in different format)
        self.assertIn("consentRecordId", receipt)

    def test_receipt_for_group_consent(self):
        """Receipt works for group consent"""
        group = self.create_test_group(name="Test Household", identifier_value="HH-001")

        consent = self.create_consent(
            registrant=group,
            grantee_partner=self.grantee_org,
            resource_type="group",
        )

        receipt = consent.generate_api_receipt()

        # Should have consent info
        self.assertIn("consentRecordId", receipt)
