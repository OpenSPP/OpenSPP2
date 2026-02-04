# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for ApiAuditService"""

from ..services.api_audit_service import ApiAuditService
from .common import ApiV2TestCase


class TestApiAuditService(ApiV2TestCase):
    """Test ApiAuditService functionality"""

    def setUp(self):
        super().setUp()
        self.individual = self.create_test_individual(
            name="John Doe",
            identifier_value="IND-001",
        )
        self.api_client = self.create_api_client(
            name="Test Audit Client",
            scopes=[
                {"resource": "individual", "action": "read"},
                {"resource": "individual", "action": "create"},
            ],
        )
        self.consent = self.create_consent(
            registrant=self.individual,
            grantee_partner=self.api_client.partner_id,
        )

    def test_log_read_creates_audit_record(self):
        """log_read creates audit record with correct fields"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
            request_id="test-request-123",
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
        )

        audit_service.log_read(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            consent=self.consent,
            purpose="service_delivery",
            legal_basis="consent",
            fields_returned=["name", "birthDate"],
            extensions_returned=["farmer"],
            status="success",
        )

        # Verify audit log was created
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "read"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log, "Audit log should be created")
        self.assertEqual(audit_log.operation, "read")
        self.assertEqual(audit_log.resource_type, "individual")
        self.assertEqual(
            audit_log.resource_identifier,
            "urn:openspp:vocab:id-type#test_national_id|IND-001",
        )
        self.assertEqual(audit_log.consent_id, self.consent)
        self.assertEqual(audit_log.purpose, "service_delivery")
        self.assertEqual(audit_log.legal_basis, "consent")
        self.assertEqual(audit_log.request_id, "test-request-123")
        self.assertEqual(audit_log.ip_address, "192.168.1.1")
        self.assertEqual(audit_log.user_agent, "TestAgent/1.0")
        self.assertEqual(audit_log.fields_returned, ["name", "birthDate"])
        self.assertEqual(audit_log.extensions_returned, ["farmer"])
        self.assertEqual(audit_log.status, "success")

    def test_log_search_creates_audit_record(self):
        """log_search creates audit record with search parameters and result count"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
            request_id="test-search-456",
        )

        search_params = {
            "birthDate[gte]": "1990-01-01",
            "gender": "male",
            "_page": 1,
            "_count": 10,
        }

        audit_service.log_search(
            resource_type="individual",
            search_parameters=search_params,
            result_count=15,
            consent=self.consent,
            purpose="research",
            legal_basis="legitimate_interests",
            status="success",
        )

        # Verify audit log
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "search"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.operation, "search")
        self.assertEqual(audit_log.resource_type, "individual")
        self.assertEqual(audit_log.resource_identifier, "search")
        self.assertEqual(audit_log.search_parameters, search_params)
        self.assertEqual(audit_log.result_count, 15)
        self.assertEqual(audit_log.consent_id, self.consent)
        self.assertEqual(audit_log.purpose, "research")
        self.assertEqual(audit_log.legal_basis, "legitimate_interests")

    def test_log_export_creates_audit_record(self):
        """log_export creates audit record with identifiers list"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        identifiers = [
            "urn:openspp:vocab:id-type#test_national_id|IND-001",
            "urn:openspp:vocab:id-type#test_national_id|IND-002",
            "urn:openspp:vocab:id-type#test_national_id|IND-003",
        ]

        audit_service.log_export(
            resource_type="individual",
            identifiers=identifiers,
            result_count=3,
            consent=self.consent,
            purpose="service_delivery",
            status="success",
        )

        # Verify audit log
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "export"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.operation, "export")
        self.assertEqual(audit_log.resource_type, "individual")
        self.assertEqual(audit_log.resource_identifier, "bulk:3")
        self.assertEqual(audit_log.search_parameters["identifiers"], identifiers)
        self.assertEqual(audit_log.result_count, 3)

    def test_log_create_creates_and_links(self):
        """log_create creates audit record and links to spp.audit.log"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        # Create a new individual
        new_individual = self.create_test_individual(
            name="Jane Smith",
            identifier_value="IND-002",
        )

        audit_service.log_create(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-002",
            record=new_individual,
            consent=self.consent,
            purpose="registration",
            legal_basis="consent",
            status="success",
        )

        # Verify audit log
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "create"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.operation, "create")
        self.assertEqual(audit_log.resource_type, "individual")
        self.assertEqual(
            audit_log.resource_identifier,
            "urn:openspp:vocab:id-type#test_national_id|IND-002",
        )
        self.assertEqual(audit_log.model_name, "res.partner")
        self.assertEqual(audit_log.res_id, new_individual.id)
        self.assertEqual(audit_log.status, "success")

        # Verify link to spp.audit.log (if exists)
        # The linking happens asynchronously via _link_audit_log
        # We verify model_name and res_id are set for linking
        self.assertIsNotNone(audit_log.model_name)
        self.assertIsNotNone(audit_log.res_id)

    def test_log_update_creates_and_links(self):
        """log_update creates audit record and links to spp.audit.log"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        # Update the individual
        self.individual.write({"given_name": "Johnny"})

        audit_service.log_update(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            record=self.individual,
            consent=self.consent,
            purpose="data_correction",
            legal_basis="consent",
            status="success",
        )

        # Verify audit log
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "update"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.operation, "update")
        self.assertEqual(audit_log.resource_type, "individual")
        self.assertEqual(audit_log.model_name, "res.partner")
        self.assertEqual(audit_log.res_id, self.individual.id)

    def test_log_patch_creates_and_links(self):
        """log_patch creates audit record and links to spp.audit.log"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        # Patch the individual
        self.individual.write({"family_name": "Doe-Smith"})

        audit_service.log_patch(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            record=self.individual,
            consent=self.consent,
            purpose="data_update",
            legal_basis="consent",
            status="success",
        )

        # Verify audit log
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "patch"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.operation, "patch")
        self.assertEqual(audit_log.resource_type, "individual")
        self.assertEqual(audit_log.model_name, "res.partner")
        self.assertEqual(audit_log.res_id, self.individual.id)

    def test_log_delete_creates_record(self):
        """log_delete creates audit record without linking"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        # Log delete before actually deleting
        audit_service.log_delete(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            record=self.individual,
            consent=self.consent,
            purpose="data_removal",
            legal_basis="consent",
            status="success",
        )

        # Verify audit log
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "delete"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.operation, "delete")
        self.assertEqual(audit_log.resource_type, "individual")
        self.assertEqual(audit_log.model_name, "res.partner")
        self.assertEqual(audit_log.res_id, self.individual.id)
        # Delete should not link to spp.audit.log
        self.assertFalse(audit_log.audit_log_id)

    def test_request_metadata_stored(self):
        """ip_address and user_agent are stored in audit records"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
            request_id="meta-test-789",
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0 TestBrowser",
        )

        audit_service.log_read(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
        )

        # Verify metadata
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("request_id", "=", "meta-test-789"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.request_id, "meta-test-789")
        self.assertEqual(audit_log.ip_address, "10.0.0.1")
        self.assertEqual(audit_log.user_agent, "Mozilla/5.0 TestBrowser")

    def test_auto_generated_request_id(self):
        """UUID is auto-generated when request_id not provided"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
            # No request_id provided
        )

        # Verify request_id was auto-generated
        self.assertIsNotNone(audit_service.request_id)
        self.assertTrue(len(audit_service.request_id) > 0)

        audit_service.log_read(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
        )

        # Verify auto-generated request_id was stored
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "read"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.request_id, audit_service.request_id)
        self.assertTrue(len(audit_log.request_id) > 0)

    def test_logging_failure_returns_none(self):
        """Logging failures return None and don't raise exceptions"""
        # Test that the _log method catches errors gracefully
        # Use an invalid api_client to trigger a TypeError/AttributeError
        bad_service = ApiAuditService(
            self.env,
            None,  # Invalid api_client - will cause error in log_operation
        )

        # This should not raise, should return None
        result = bad_service._log(
            operation="read",
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            status="success",
        )

        # Verify it returned None instead of raising
        self.assertIsNone(result)

    def test_log_with_consent(self):
        """Consent is properly stored in audit records"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        audit_service.log_read(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            consent=self.consent,
            purpose="healthcare",
            legal_basis="consent",
            status="success",
        )

        # Verify consent was stored
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "read"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.consent_id, self.consent)
        self.assertEqual(audit_log.purpose, "healthcare")
        self.assertEqual(audit_log.legal_basis, "consent")

    def test_log_with_error_status(self):
        """Error details are stored when status is not success"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        audit_service.log_read(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|INVALID",
            status="not_found",
            error_detail="Resource not found in registry",
        )

        # Verify error was logged
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "read"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.status, "not_found")
        self.assertEqual(audit_log.error_detail, "Resource not found in registry")

    def test_log_create_with_error_no_linking(self):
        """log_create with error status does not link to spp.audit.log"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        audit_service.log_create(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|INVALID",
            record=None,
            status="validation_error",
            error_detail="Invalid date format",
        )

        # Verify audit log created but not linked
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "create"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.status, "validation_error")
        self.assertFalse(audit_log.audit_log_id)
        self.assertFalse(audit_log.model_name)
        self.assertFalse(audit_log.res_id)

    def test_log_update_with_error_no_linking(self):
        """log_update with error status does not link to spp.audit.log"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        audit_service.log_update(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            record=self.individual,
            status="validation_error",
            error_detail="Invalid data",
        )

        # Verify audit log created but not linked
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "update"),
            ],
            limit=1,
        )

        self.assertTrue(audit_log)
        self.assertEqual(audit_log.status, "validation_error")
        # Even though record was provided, status != success so no linking
        self.assertFalse(audit_log.audit_log_id)

    def test_link_audit_log_failure_does_not_raise(self):
        """_link_audit_log failure does not raise exception"""
        audit_service = ApiAuditService(
            self.env,
            self.api_client,
        )

        # Create operation with success status - this will try to link audit log
        # Even without spp_audit module, this should not raise
        audit_service.log_create(
            resource_type="individual",
            resource_identifier="urn:openspp:vocab:id-type#test_national_id|IND-001",
            record=self.individual,
            status="success",
        )

        # Verify audit log was created
        audit_log = self.env["spp.api.audit.log"].search(
            [
                ("api_client_id", "=", self.api_client.id),
                ("operation", "=", "create"),
            ],
            limit=1,
        )
        self.assertTrue(audit_log)
