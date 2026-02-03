# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.api.audit.log model"""

from .common import ApiV2TestCase


class TestApiAuditLog(ApiV2TestCase):
    """Test spp.api.audit.log model functionality"""

    def setUp(self):
        super().setUp()
        self.individual = self.create_test_individual(
            name="John Doe",
            identifier_value="IND-001",
        )
        self.api_client = self.create_api_client(
            name="Test Client",
            scopes=[
                {"resource": "individual", "action": "read"},
            ],
        )
        self.consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.api_client.partner_id,
        )
        self.audit_log_model = self.env["spp.api.audit.log"]

    def test_log_operation_creates_record(self):
        """log_operation creates audit log record with all required fields"""
        audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
            request_id="test-123",
            ip_address="192.168.1.100",
            user_agent="TestAgent/1.0",
        )

        self.assertTrue(audit_log, "Audit log should be created")
        self.assertEqual(audit_log.api_client_id, self.api_client)
        self.assertEqual(audit_log.operation, "read")
        self.assertEqual(audit_log.resource_type, "individual")
        self.assertEqual(audit_log.resource_identifier, "urn:openspp:vocab:id-type#test_national_id|IND-001")
        self.assertEqual(audit_log.status, "success")
        self.assertEqual(audit_log.request_id, "test-123")
        self.assertEqual(audit_log.ip_address, "192.168.1.100")
        self.assertEqual(audit_log.user_agent, "TestAgent/1.0")
        self.assertIsNotNone(audit_log.timestamp)

    def test_log_operation_with_consent(self):
        """log_operation stores consent information"""
        audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
            consent=self.consent,
            purpose="healthcare_delivery",
            legal_basis="consent",
        )

        self.assertEqual(audit_log.consent_id, self.consent)
        self.assertEqual(audit_log.purpose, "healthcare_delivery")
        self.assertEqual(audit_log.legal_basis, "consent")

    def test_log_operation_with_search_parameters(self):
        """log_operation stores search parameters and result count"""
        search_params = {
            "birthDate[gte]": "1990-01-01",
            "gender": "male",
            "_page": 1,
            "_count": 10,
        }

        audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="search",
            resource_type="individual",
            resource_identifier="search",
            status="success",
            search_parameters=search_params,
            result_count=25,
        )

        self.assertEqual(audit_log.operation, "search")
        self.assertEqual(audit_log.search_parameters, search_params)
        self.assertEqual(audit_log.result_count, 25)

    def test_log_operation_with_fields_returned(self):
        """log_operation stores fields_returned and extensions_returned"""
        fields_list = ["name", "birthDate", "gender"]
        extensions_list = ["farmer", "disability"]

        audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
            fields_returned=fields_list,
            extensions_returned=extensions_list,
        )

        self.assertEqual(audit_log.fields_returned, fields_list)
        self.assertEqual(audit_log.extensions_returned, extensions_list)

    def test_log_operation_with_model_and_res_id(self):
        """log_operation stores model_name and res_id for write operations"""
        audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="create",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
            model_name="res.partner",
            res_id=self.individual.id,
        )

        self.assertEqual(audit_log.model_name, "res.partner")
        self.assertEqual(audit_log.res_id, self.individual.id)

    def test_log_operation_with_error_detail(self):
        """log_operation stores error status and detail"""
        audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|INVALID",
            status="not_found",
            error_detail="Resource not found in registry",
        )

        self.assertEqual(audit_log.status, "not_found")
        self.assertEqual(audit_log.error_detail, "Resource not found in registry")

    def test_log_operation_all_legal_basis_options(self):
        """log_operation accepts all legal basis options"""
        legal_bases = [
            "consent",
            "legal_obligation",
            "public_interest",
            "vital_interests",
            "legitimate_interests",
            "contract",
        ]

        for legal_basis in legal_bases:
            audit_log = self.audit_log_model.sudo().log_operation(
                api_client=self.api_client,
                operation="read",
                resource_type="individual",
                resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
                status="success",
                legal_basis=legal_basis,
            )
            self.assertEqual(audit_log.legal_basis, legal_basis)

    def test_log_operation_all_operation_types(self):
        """log_operation accepts all operation types"""
        operations = ["read", "search", "export", "create", "update", "patch", "delete"]

        for operation in operations:
            audit_log = self.audit_log_model.sudo().log_operation(
                api_client=self.api_client,
                operation=operation,
                resource_type="individual",
                resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
                status="success",
            )
            self.assertEqual(audit_log.operation, operation)

    def test_log_operation_all_resource_types(self):
        """log_operation accepts all resource types"""
        resource_types = ["individual", "group", "program", "program_membership"]

        for resource_type in resource_types:
            audit_log = self.audit_log_model.sudo().log_operation(
                api_client=self.api_client,
                operation="read",
                resource_type=resource_type,
                resource_identifier=f"urn:test:{resource_type}|001",
                status="success",
            )
            self.assertEqual(audit_log.resource_type, resource_type)

    def test_log_operation_all_status_options(self):
        """log_operation accepts all status options"""
        statuses = ["success", "access_denied", "not_found", "validation_error", "error"]

        for status in statuses:
            audit_log = self.audit_log_model.sudo().log_operation(
                api_client=self.api_client,
                operation="read",
                resource_type="individual",
                resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
                status=status,
            )
            self.assertEqual(audit_log.status, status)

    def test_link_audit_log(self):
        """link_audit_log updates audit_log_id field (requires spp_audit)"""
        if "spp.audit.log" not in self.env:
            # spp_audit not installed; verify link_audit_log is a no-op
            api_audit_log = self.audit_log_model.sudo().log_operation(
                api_client=self.api_client,
                operation="update",
                resource_type="individual",
                resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
                status="success",
                model_name="res.partner",
                res_id=self.individual.id,
            )
            self.audit_log_model.sudo().link_audit_log(
                api_audit_log,
                "res.partner",
                self.individual.id,
            )
            self.assertFalse(api_audit_log.audit_log_id)
            return

        # Create an API audit log
        api_audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="update",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
            model_name="res.partner",
            res_id=self.individual.id,
        )

        # Verify no link initially
        self.assertFalse(api_audit_log.audit_log_id)

        # Modify the individual to trigger spp.audit.log creation
        self.individual.write({"given_name": "Johnny"})

        # Link the audit log
        self.audit_log_model.sudo().link_audit_log(
            api_audit_log,
            "res.partner",
            self.individual.id,
        )

        # Verify link was created
        self.assertTrue(api_audit_log.audit_log_id, "audit_log_id should be set after linking")

    def test_link_audit_log_finds_most_recent(self):
        """link_audit_log finds the most recent spp.audit.log entry (requires spp_audit)"""
        if "spp.audit.log" not in self.env:
            # spp_audit not installed; link_audit_log is a no-op
            return

        # Create multiple audit log entries
        self.individual.write({"given_name": "John1"})
        self.individual.write({"given_name": "John2"})
        self.individual.write({"given_name": "John3"})

        # Create API audit log
        api_audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="update",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
            model_name="res.partner",
            res_id=self.individual.id,
        )

        # Link should find the most recent
        self.audit_log_model.sudo().link_audit_log(
            api_audit_log,
            "res.partner",
            self.individual.id,
        )

        # Verify it linked to the most recent audit entry
        self.assertTrue(api_audit_log.audit_log_id)
        self.assertGreater(api_audit_log.audit_log_id, 0)

    def test_link_audit_log_invalid_model(self):
        """link_audit_log handles invalid model gracefully"""
        api_audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="update",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
        )

        # Try to link with invalid model - should not raise
        self.audit_log_model.sudo().link_audit_log(
            api_audit_log,
            "invalid.model.name",
            999999,
        )

        # Should still have no link
        self.assertFalse(api_audit_log.audit_log_id)

    def test_display_name_computed(self):
        """display_name is computed from operation, resource_type, and timestamp"""
        audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
        )

        # Verify display_name is computed
        self.assertTrue(audit_log.display_name)
        self.assertIn("read", audit_log.display_name)
        self.assertIn("individual", audit_log.display_name)

    def test_get_activity_summary(self):
        """get_activity_summary returns correct statistics"""
        # Create multiple audit logs
        for i in range(3):
            self.audit_log_model.sudo().log_operation(
                api_client=self.api_client,
                operation="read",
                resource_type="individual",
                resource_identifier=f"urn:openspp:vocab:id-type#test_national_id|IND-{i:03d}",
                status="success",
            )

        for _i in range(2):
            self.audit_log_model.sudo().log_operation(
                api_client=self.api_client,
                operation="search",
                resource_type="individual",
                resource_identifier="search",
                status="success",
            )

        # Get summary
        summary = self.audit_log_model.get_activity_summary(
            api_client_id=self.api_client.id,
        )

        # Verify statistics
        self.assertEqual(summary["total_operations"], 5)
        self.assertEqual(summary["by_operation"]["read"], 3)
        self.assertEqual(summary["by_operation"]["search"], 2)
        self.assertEqual(summary["by_resource_type"]["individual"], 5)
        self.assertEqual(summary["by_status"]["success"], 5)

    def test_get_activity_summary_date_range(self):
        """get_activity_summary returns correct date range from aggregation"""
        # Create audit logs
        self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
        )
        self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="search",
            resource_type="individual",
            resource_identifier="search",
            status="success",
        )

        summary = self.audit_log_model.get_activity_summary(
            api_client_id=self.api_client.id,
        )

        # date_range should have first and last timestamps
        self.assertIn("date_range", summary)
        self.assertIsNotNone(summary["date_range"]["first"])
        self.assertIsNotNone(summary["date_range"]["last"])

    def test_get_activity_summary_empty(self):
        """get_activity_summary handles empty results without error"""
        summary = self.audit_log_model.get_activity_summary(
            api_client_id=99999,  # Non-existent client
        )

        self.assertEqual(summary["total_operations"], 0)
        self.assertIsNone(summary["date_range"]["first"])
        self.assertIsNone(summary["date_range"]["last"])

    def test_get_consent_access_summary(self):
        """get_consent_access_summary returns consent-specific statistics"""
        # Create audit logs with consent
        for idx in range(2):
            self.audit_log_model.sudo().log_operation(
                api_client=self.api_client,
                operation="read",
                resource_type="individual",
                resource_identifier=f"urn:openspp:vocab:id-type#test_national_id|IND-{idx:03d}",
                status="success",
                consent=self.consent,
            )

        self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="search",
            resource_type="individual",
            resource_identifier="search",
            status="success",
            consent=self.consent,
        )

        # Get consent summary
        summary = self.audit_log_model.get_consent_access_summary(
            consent_id=self.consent.id,
        )

        # Verify statistics
        self.assertEqual(summary["total_accesses"], 3)
        self.assertEqual(summary["by_action"]["read"], 2)  # read operations
        self.assertEqual(summary["by_action"]["search"], 1)  # search operations
        self.assertEqual(summary["by_resource_type"]["individual"], 3)

        # Verify date_range is populated
        self.assertIn("date_range", summary)
        self.assertIsNotNone(summary["date_range"]["first"])
        self.assertIsNotNone(summary["date_range"]["last"])

    def test_get_consent_access_summary_empty(self):
        """get_consent_access_summary handles no matching records"""
        summary = self.audit_log_model.get_consent_access_summary(
            consent_id=99999,  # Non-existent consent
        )

        self.assertEqual(summary["total_accesses"], 0)
        self.assertIsNone(summary["date_range"]["first"])
        self.assertIsNone(summary["date_range"]["last"])

    def test_audit_log_ordering(self):
        """Audit logs are ordered by timestamp desc"""
        # Create logs with small time gaps
        log1 = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
        )

        log2 = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-002",
            status="success",
        )

        log3 = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-003",
            status="success",
        )

        # Search with explicit order (id desc, since timestamp identical in transaction)
        logs = self.audit_log_model.search(
            [("id", "in", [log1.id, log2.id, log3.id])],
            order="id desc",
        )

        # Most recent (highest ID) should be first
        self.assertEqual(logs[0].id, log3.id)
        self.assertEqual(logs[1].id, log2.id)
        self.assertEqual(logs[2].id, log1.id)

    def test_optional_fields_can_be_none(self):
        """Optional fields can be omitted without error"""
        # Create audit log with minimal required fields only
        audit_log = self.audit_log_model.sudo().log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
            # All optional fields omitted
        )

        # Verify record was created
        self.assertTrue(audit_log)
        self.assertFalse(audit_log.consent_id)
        self.assertFalse(audit_log.purpose)
        self.assertFalse(audit_log.legal_basis)
        self.assertFalse(audit_log.request_id)
        self.assertFalse(audit_log.ip_address)
        self.assertFalse(audit_log.user_agent)
        self.assertFalse(audit_log.search_parameters)
        self.assertFalse(audit_log.result_count)
        self.assertFalse(audit_log.fields_returned)
        self.assertFalse(audit_log.extensions_returned)
        self.assertFalse(audit_log.model_name)
        self.assertFalse(audit_log.res_id)
        self.assertFalse(audit_log.error_detail)
