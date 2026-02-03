# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for BundleProcessor (transaction and batch operations)"""

from odoo.exceptions import ValidationError

from ..schemas.bundle import Bundle, BundleEntry, BundleRequest
from ..services.bundle_service import BundleProcessor
from .common import ApiV2TestCase


class TestBundleService(ApiV2TestCase):
    """Test BundleProcessor for transaction and batch operations"""

    def setUp(self):
        super().setUp()
        self.processor = BundleProcessor(self.env)

        # Create API client with all scopes
        self.api_client = self.create_api_client(
            name="Bundle Test Client",
            scopes=[
                {"resource": "individual", "action": "create"},
                {"resource": "individual", "action": "read"},
                {"resource": "individual", "action": "update"},
                {"resource": "individual", "action": "delete"},
                {"resource": "group", "action": "create"},
                {"resource": "group", "action": "read"},
                {"resource": "group", "action": "update"},
                {"resource": "group", "action": "delete"},
            ],
        )
        self.source = f"urn:openspp:api-client:{self.api_client.client_id}"

    def test_transaction_with_single_entry_succeeds(self):
        """Transaction with single entry succeeds"""
        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    full_url="urn:uuid:individual-1",
                    request=BundleRequest(
                        method="POST",
                        url="Individual",
                    ),
                    resource={
                        "type": "Individual",
                        "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "TXN-001"}],
                        "name": {"given": "John", "family": "Doe"},
                        "active": True,
                    },
                )
            ],
        )

        result = self.processor.process_transaction(bundle, self.api_client, self.source)

        self.assertEqual(result["type"], "transaction-response")
        self.assertEqual(len(result["entry"]), 1)
        self.assertEqual(result["entry"][0]["response"]["status"], "201 Created")

        # Verify individual was created
        partner = self.env["res.partner"].search([("reg_ids.value", "=", "TXN-001")])
        self.assertTrue(partner)
        self.assertEqual(partner.given_name, "John")

    def test_transaction_with_multiple_entries_succeeds(self):
        """Transaction with multiple entries succeeds"""
        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    full_url="urn:uuid:individual-1",
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        "identifier": [
                            {"system": "urn:openspp:vocab:id-type#test_national_id", "value": "TXN-MULTI-1"}
                        ],
                        "name": {"given": "Alice", "family": "Smith"},
                    },
                ),
                BundleEntry(
                    full_url="urn:uuid:individual-2",
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        "identifier": [
                            {"system": "urn:openspp:vocab:id-type#test_national_id", "value": "TXN-MULTI-2"}
                        ],
                        "name": {"given": "Bob", "family": "Jones"},
                    },
                ),
            ],
        )

        result = self.processor.process_transaction(bundle, self.api_client, self.source)

        self.assertEqual(len(result["entry"]), 2)
        self.assertEqual(result["entry"][0]["response"]["status"], "201 Created")
        self.assertEqual(result["entry"][1]["response"]["status"], "201 Created")

        # Verify both individuals were created
        partner1 = self.env["res.partner"].search([("reg_ids.value", "=", "TXN-MULTI-1")])
        partner2 = self.env["res.partner"].search([("reg_ids.value", "=", "TXN-MULTI-2")])
        self.assertTrue(partner1)
        self.assertTrue(partner2)

    def test_transaction_with_placeholder_uuid_resolution(self):
        """Transaction resolves placeholder UUIDs in references"""
        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    full_url="urn:uuid:individual-1",
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        "identifier": [
                            {"system": "urn:openspp:vocab:id-type#test_national_id", "value": "PLACEHOLDER-IND"}
                        ],
                        "name": {"given": "Head", "family": "Person"},
                    },
                ),
                BundleEntry(
                    full_url="urn:uuid:group-1",
                    request=BundleRequest(method="POST", url="Group"),
                    resource={
                        "type": "Group",
                        "identifier": [
                            {"system": "urn:openspp:vocab:id-type#test_household_id", "value": "PLACEHOLDER-GRP"}
                        ],
                        "name": "Test Household",
                        "member": [
                            {
                                "entity": {
                                    "reference": "urn:uuid:individual-1",
                                    "display": "Head Person",
                                }
                            }
                        ],
                    },
                ),
            ],
        )

        result = self.processor.process_transaction(bundle, self.api_client, self.source)

        self.assertEqual(len(result["entry"]), 2)
        self.assertEqual(result["entry"][0]["response"]["status"], "201 Created")
        self.assertEqual(result["entry"][1]["response"]["status"], "201 Created")

        # Verify group was created with member
        group = self.env["res.partner"].search([("reg_ids.value", "=", "PLACEHOLDER-GRP")])
        self.assertTrue(group)
        self.assertTrue(group.is_group)

    def test_transaction_rolls_back_on_failure(self):
        """Transaction rolls back all changes on failure (all-or-nothing)"""
        # Create a valid first entry and invalid second entry
        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    full_url="urn:uuid:individual-1",
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "ROLLBACK-1"}],
                        "name": {"given": "Valid", "family": "Entry"},
                    },
                ),
                BundleEntry(
                    full_url="urn:uuid:individual-2",
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        # Missing required identifier - should fail
                        "name": {"given": "Invalid", "family": "Entry"},
                    },
                ),
            ],
        )

        with self.assertRaises(ValidationError):
            self.processor.process_transaction(bundle, self.api_client, self.source)

        # Verify first entry was also rolled back
        partner = self.env["res.partner"].search([("reg_ids.value", "=", "ROLLBACK-1")])
        self.assertFalse(partner, "Transaction should have rolled back all entries")

    def test_batch_with_single_entry_succeeds(self):
        """Batch with single entry succeeds"""
        bundle = Bundle(
            type="batch",
            entry=[
                BundleEntry(
                    full_url="urn:uuid:individual-1",
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "BATCH-001"}],
                        "name": {"given": "Batch", "family": "Test"},
                    },
                )
            ],
        )

        result = self.processor.process_batch(bundle, self.api_client, self.source)

        self.assertEqual(result["type"], "batch-response")
        self.assertEqual(len(result["entry"]), 1)
        self.assertEqual(result["entry"][0]["response"]["status"], "201 Created")

    def test_batch_continues_on_partial_failure(self):
        """Batch continues processing even when some entries fail"""
        bundle = Bundle(
            type="batch",
            entry=[
                BundleEntry(
                    full_url="urn:uuid:individual-1",
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        "identifier": [
                            {"system": "urn:openspp:vocab:id-type#test_national_id", "value": "BATCH-SUCCESS"}
                        ],
                        "name": {"given": "Valid", "family": "Entry"},
                    },
                ),
                BundleEntry(
                    full_url="urn:uuid:individual-2",
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        # Missing required identifier - should fail
                        "name": {"given": "Invalid", "family": "Entry"},
                    },
                ),
                BundleEntry(
                    full_url="urn:uuid:individual-3",
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        "identifier": [
                            {"system": "urn:openspp:vocab:id-type#test_national_id", "value": "BATCH-SUCCESS-2"}
                        ],
                        "name": {"given": "Another", "family": "Valid"},
                    },
                ),
            ],
        )

        result = self.processor.process_batch(bundle, self.api_client, self.source)

        self.assertEqual(len(result["entry"]), 3)

        # First entry should succeed
        self.assertEqual(result["entry"][0]["response"]["status"], "201 Created")

        # Second entry should fail (missing identifier → error response)
        error_status = result["entry"][1]["response"]["status"]
        self.assertTrue(
            "422" in error_status or "500" in error_status,
            f"Expected error status, got: {error_status}",
        )
        self.assertEqual(result["entry"][1]["resource"]["resourceType"], "OperationOutcome")

        # Third entry should still succeed
        self.assertEqual(result["entry"][2]["response"]["status"], "201 Created")

        # Verify successful entries were created
        partner1 = self.env["res.partner"].search([("reg_ids.value", "=", "BATCH-SUCCESS")])
        partner3 = self.env["res.partner"].search([("reg_ids.value", "=", "BATCH-SUCCESS-2")])
        self.assertTrue(partner1)
        self.assertTrue(partner3)

    def test_invalid_bundle_type_returns_error(self):
        """Invalid bundle type raises ValidationError"""
        import pydantic

        # Pydantic validates the type field pattern during construction
        with self.assertRaises(pydantic.ValidationError):
            Bundle(
                type="invalid-type",
                entry=[],
            )

    def test_missing_request_method_returns_error(self):
        """Bundle entry without request raises ValidationError"""
        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    full_url="urn:uuid:individual-1",
                    # Missing request
                    resource={
                        "type": "Individual",
                        "identifier": [{"system": "urn:openspp:vocab:id-type#test_national_id", "value": "NO-REQUEST"}],
                        "name": {"given": "Test", "family": "Test"},
                    },
                )
            ],
        )

        with self.assertRaises(ValidationError):
            self.processor.process_transaction(bundle, self.api_client, self.source)

    def test_create_individual_via_bundle(self):
        """POST Individual via bundle creates individual"""
        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    request=BundleRequest(method="POST", url="Individual"),
                    resource={
                        "type": "Individual",
                        "identifier": [
                            {"system": "urn:openspp:vocab:id-type#test_national_id", "value": "CREATE-VIA-BUNDLE"}
                        ],
                        "name": {"given": "Created", "family": "ViaBundel"},
                        "birthDate": "1990-01-01",
                    },
                )
            ],
        )

        result = self.processor.process_transaction(bundle, self.api_client, self.source)

        self.assertEqual(result["entry"][0]["response"]["status"], "201 Created")
        self.assertIn("location", result["entry"][0]["response"])

        partner = self.env["res.partner"].search([("reg_ids.value", "=", "CREATE-VIA-BUNDLE")])
        self.assertTrue(partner)
        self.assertEqual(partner.source_system, self.source)

    def test_create_group_via_bundle_with_member_reference(self):
        """POST Group via bundle with member reference"""
        # First create individual
        individual = self.create_test_individual(identifier_value="MEMBER-001")

        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    request=BundleRequest(method="POST", url="Group"),
                    resource={
                        "type": "Group",
                        "identifier": [
                            {"system": "urn:openspp:vocab:id-type#test_household_id", "value": "GROUP-WITH-MEMBER"}
                        ],
                        "name": "Test Group",
                        "member": [
                            {
                                "entity": {
                                    "reference": "Individual/urn:openspp:vocab:id-type#test_national_id|MEMBER-001",
                                    "display": individual.name,
                                }
                            }
                        ],
                    },
                )
            ],
        )

        result = self.processor.process_transaction(bundle, self.api_client, self.source)

        self.assertEqual(result["entry"][0]["response"]["status"], "201 Created")

        group = self.env["res.partner"].search([("reg_ids.value", "=", "GROUP-WITH-MEMBER")])
        self.assertTrue(group)
        self.assertTrue(group.is_group)

    def test_update_via_bundle(self):
        """PUT Individual via bundle updates individual"""
        # Create individual first
        individual = self.create_test_individual(
            identifier_value="UPDATE-VIA-BUNDLE",
            given_name="Original",
            family_name="Name",
        )

        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    request=BundleRequest(
                        method="PUT",
                        url="Individual/urn:openspp:vocab:id-type#test_national_id|UPDATE-VIA-BUNDLE",
                    ),
                    resource={
                        "type": "Individual",
                        "identifier": [
                            {"system": "urn:openspp:vocab:id-type#test_national_id", "value": "UPDATE-VIA-BUNDLE"}
                        ],
                        "name": {"given": "Updated", "family": "Name"},
                    },
                )
            ],
        )

        result = self.processor.process_transaction(bundle, self.api_client, self.source)

        self.assertEqual(result["entry"][0]["response"]["status"], "200 OK")

        # Verify update
        individual.invalidate_recordset()
        self.assertEqual(individual.given_name, "Updated")

    def test_delete_via_bundle(self):
        """DELETE Individual via bundle soft-deletes individual"""
        # Create individual first
        individual = self.create_test_individual(identifier_value="DELETE-VIA-BUNDLE")

        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    request=BundleRequest(
                        method="DELETE",
                        url="Individual/urn:openspp:vocab:id-type#test_national_id|DELETE-VIA-BUNDLE",
                    ),
                )
            ],
        )

        result = self.processor.process_transaction(bundle, self.api_client, self.source)

        self.assertEqual(result["entry"][0]["response"]["status"], "204 No Content")

        # Verify soft delete
        individual.invalidate_recordset()
        self.assertFalse(individual.active)

    def test_get_via_bundle(self):
        """GET Individual via bundle reads individual"""
        # Create individual first
        self.create_test_individual(
            identifier_value="READ-VIA-BUNDLE",
            given_name="ReadMe",
        )

        bundle = Bundle(
            type="transaction",
            entry=[
                BundleEntry(
                    request=BundleRequest(
                        method="GET",
                        url="Individual/urn:openspp:vocab:id-type#test_national_id|READ-VIA-BUNDLE",
                    ),
                )
            ],
        )

        result = self.processor.process_transaction(bundle, self.api_client, self.source)

        self.assertEqual(result["entry"][0]["response"]["status"], "200 OK")
        self.assertIn("resource", result["entry"][0])
        self.assertEqual(result["entry"][0]["resource"]["type"], "Individual")
        self.assertEqual(result["entry"][0]["resource"]["name"]["given"], "ReadMe")
