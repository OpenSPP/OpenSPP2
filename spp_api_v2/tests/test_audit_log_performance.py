# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Performance tests for API Audit Log optimizations"""

from .common import ApiV2TestCase


class TestApiAuditLogPerformance(ApiV2TestCase):
    """Test API Audit Log performance optimizations using read_group()"""

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

        # Create another client for multi-client tests
        self.api_client2 = self.env["spp.api.client"].create(
            {
                "name": "Test Client 2",
                "partner_id": self.grantee_org.id,
                "organization_type_id": org_type_government.id,
            }
        )

    def test_get_activity_summary_with_read_group(self):
        """get_activity_summary uses read_group() for scalability"""
        # Create diverse audit logs
        operations = ["read", "search", "export", "create", "update"]
        resource_types = ["individual", "group", "program"]
        statuses = ["success", "access_denied", "not_found"]

        for i, op in enumerate(operations):
            for j, rt in enumerate(resource_types):
                self.env["spp.api.audit.log"].log_operation(
                    api_client=self.api_client if i % 2 == 0 else self.api_client2,
                    operation=op,
                    resource_type=rt,
                    resource_identifier=f"{rt.upper()}-{i}-{j}",
                    status=statuses[j % len(statuses)],
                )

        summary = self.env["spp.api.audit.log"].get_activity_summary()

        # Verify total count
        expected_total = len(operations) * len(resource_types)
        self.assertEqual(summary["total_operations"], expected_total)

        # Verify operation counts
        for op in operations:
            self.assertEqual(
                summary["by_operation"][op],
                len(resource_types),
                f"Operation {op} should have {len(resource_types)} entries",
            )

        # Verify resource type counts
        for rt in resource_types:
            self.assertEqual(
                summary["by_resource_type"][rt],
                len(operations),
                f"Resource type {rt} should have {len(operations)} entries",
            )

        # Verify status counts
        self.assertGreater(summary["by_status"]["success"], 0)
        self.assertGreater(summary["by_status"]["access_denied"], 0)
        self.assertGreater(summary["by_status"]["not_found"], 0)

        # Verify client counts
        self.assertEqual(len(summary["by_client"]), 2)
        self.assertIn("Test Client", summary["by_client"])
        self.assertIn("Test Client 2", summary["by_client"])

        # Verify date range
        self.assertIsNotNone(summary["date_range"]["first"])
        self.assertIsNotNone(summary["date_range"]["last"])

    def test_get_consent_access_summary_with_read_group(self):
        """get_consent_access_summary uses read_group() and search_count() for scalability"""
        # Create diverse audit logs for consent
        operations = [
            ("read", "read"),
            ("create", "read"),  # Maps to "read" action
            ("update", "read"),  # Maps to "read" action
            ("search", "search"),  # Maps to "search" action
            ("export", "export"),  # Maps to "export" action
        ]
        resource_types = ["individual", "group"]

        for op, _ in operations:
            for rt in resource_types:
                self.env["spp.api.audit.log"].log_operation(
                    api_client=self.api_client,
                    operation=op,
                    resource_type=rt,
                    resource_identifier=f"{rt.upper()}-{op}",
                    consent=self.consent,
                )

        summary = self.env["spp.api.audit.log"].get_consent_access_summary(consent_id=self.consent.id)

        # Verify total count
        expected_total = len(operations) * len(resource_types)
        self.assertEqual(summary["total_accesses"], expected_total)

        # Verify action mapping:
        # - "read" action includes: read, create, update
        # - "search" action includes: search
        # - "export" action includes: export
        expected_read = 3 * len(resource_types)  # read, create, update
        expected_search = 1 * len(resource_types)  # search
        expected_export = 1 * len(resource_types)  # export

        self.assertEqual(
            summary["by_action"]["read"],
            expected_read,
            "read action should include read/create/update operations",
        )
        self.assertEqual(summary["by_action"]["search"], expected_search)
        self.assertEqual(summary["by_action"]["export"], expected_export)

        # Verify resource type counts
        for rt in resource_types:
            self.assertEqual(
                summary["by_resource_type"][rt],
                len(operations),
                f"Resource type {rt} should have {len(operations)} entries",
            )

        # Verify client counts
        self.assertEqual(len(summary["by_client"]), 1)
        self.assertIn("Test Client", summary["by_client"])

        # Verify date range
        self.assertIsNotNone(summary["date_range"]["first"])
        self.assertIsNotNone(summary["date_range"]["last"])

    def test_activity_summary_with_filters(self):
        """get_activity_summary respects filter parameters"""
        # Create logs for different clients and resources
        self.env["spp.api.audit.log"].log_operation(
            api_client=self.api_client,
            operation="read",
            resource_type="individual",
            resource_identifier="IND-001",
        )
        self.env["spp.api.audit.log"].log_operation(
            api_client=self.api_client2,
            operation="search",
            resource_type="group",
            resource_identifier="search",
        )

        # Filter by client
        summary = self.env["spp.api.audit.log"].get_activity_summary(api_client_id=self.api_client.id)
        self.assertEqual(summary["total_operations"], 1)
        self.assertEqual(summary["by_operation"]["read"], 1)

        # Filter by resource_identifier
        summary = self.env["spp.api.audit.log"].get_activity_summary(resource_identifier="IND-001")
        self.assertEqual(summary["total_operations"], 1)
        self.assertEqual(summary["by_resource_type"]["individual"], 1)

    def test_empty_results(self):
        """Summary methods handle empty result sets correctly"""
        # Test get_activity_summary with no matching records
        summary = self.env["spp.api.audit.log"].get_activity_summary(resource_identifier="NONEXISTENT")
        self.assertEqual(summary["total_operations"], 0)
        self.assertIsNone(summary["date_range"]["first"])
        self.assertIsNone(summary["date_range"]["last"])

        # Test get_consent_access_summary with no matching records
        fake_consent_id = 999999
        summary = self.env["spp.api.audit.log"].get_consent_access_summary(consent_id=fake_consent_id)
        self.assertEqual(summary["total_accesses"], 0)
        self.assertIsNone(summary["date_range"]["first"])
        self.assertIsNone(summary["date_range"]["last"])
