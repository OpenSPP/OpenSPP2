# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for BRN registry ID creation on CR apply."""

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestApplyCreatesBRN(TransactionCase):
    """Test that applying Add Member CR creates verified BRN registry ID."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.CRDetail = cls.env["spp.cr.detail.add_member"]
        cls.RegistryId = cls.env["spp.registry.id"]

        # Create a test data source
        cls.data_source = cls.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "our_sender_id": "openspp.test",
                "registry_type": "ns:org:RegistryType:Civil",
                "active": True,
            }
        )

        # Get or create a group for testing
        cls.test_group = cls.env["res.partner"].create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Get or create a change request type
        cls.request_type = cls.env["spp.change.request.type"].search([("code", "=", "add_member")], limit=1)
        if not cls.request_type:
            cls.request_type = cls.env["spp.change.request.type"].create(
                {
                    "name": "Add Member",
                    "code": "add_member",
                    "detail_model": "spp.cr.detail.add_member",
                    "strategy_model": "spp.cr.apply.add_member",
                }
            )

        # Get BRN ID type from vocabulary
        cls.brn_id_type = cls.env.ref(
            "spp_dci_demo.code_id_type_brn",
            raise_if_not_found=False,
        )

    def _create_test_cr_with_detail(self, **detail_kwargs):
        """Helper to create a CR with detail record."""
        cr = self.env["spp.change.request"].create(
            {
                "registrant_id": self.test_group.id,
                "request_type_id": self.request_type.id,
            }
        )

        detail_vals = {
            "registrant_id": self.test_group.id,
            "change_request_id": cr.id,
            "given_name": "Test",
            "family_name": "Child",
            "member_name": "CHILD, TEST",
        }
        detail_vals.update(detail_kwargs)
        detail = self.CRDetail.create(detail_vals)

        # Link the detail to the CR
        cr.write({"detail_res_id": detail.id})

        return cr

    def test_apply_creates_verified_brn_when_verified(self):
        """Test that applying a verified CR creates a verified BRN registry ID."""
        if not self.brn_id_type:
            self.skipTest("BRN ID type not found - module data may not be loaded")

        # Create CR with verified birth
        cr = self._create_test_cr_with_detail(
            birth_registration_number="UP7D57VSEAZM",
            birth_verification_status="verified",
            birth_verification_date=fields.Datetime.now(),
            birth_verification_response='{"test": "response"}',
            dci_data_source_id=self.data_source.id,
        )

        # Apply the change request
        apply_strategy = self.env["spp.cr.apply.add_member"]
        apply_strategy.apply(cr)

        # Get the created individual
        detail = cr.get_detail()
        individual = detail.created_individual_id
        self.assertTrue(individual, "Individual should be created")

        # Check registry ID was created
        registry_id = self.RegistryId.search(
            [
                ("partner_id", "=", individual.id),
                ("id_type_id", "=", self.brn_id_type.id),
            ]
        )

        self.assertTrue(registry_id, "BRN registry ID should be created")
        self.assertEqual(registry_id.value, "UP7D57VSEAZM")
        self.assertEqual(registry_id.status, "valid")
        self.assertEqual(registry_id.verification_method, "dci_api")
        self.assertTrue(registry_id.is_verified)
        self.assertTrue(registry_id.verification_date)
        self.assertEqual(registry_id.verification_source, self.data_source.name)
        self.assertTrue(registry_id.verification_response)

    def test_apply_no_brn_when_unverified(self):
        """Test that unverified CR does not create BRN registry ID."""
        if not self.brn_id_type:
            self.skipTest("BRN ID type not found - module data may not be loaded")

        # Create CR with unverified birth
        cr = self._create_test_cr_with_detail(
            birth_registration_number="UNVERIFIED123",
            birth_verification_status="unverified",
        )

        # Apply the change request
        apply_strategy = self.env["spp.cr.apply.add_member"]
        apply_strategy.apply(cr)

        # Get the created individual
        detail = cr.get_detail()
        individual = detail.created_individual_id
        self.assertTrue(individual, "Individual should be created")

        # Check registry ID was NOT created
        registry_id = self.RegistryId.search(
            [
                ("partner_id", "=", individual.id),
                ("id_type_id", "=", self.brn_id_type.id),
            ]
        )

        self.assertFalse(registry_id, "BRN registry ID should NOT be created for unverified")

    def test_apply_no_brn_when_not_found(self):
        """Test that 'not_found' verification does not create BRN registry ID."""
        if not self.brn_id_type:
            self.skipTest("BRN ID type not found - module data may not be loaded")

        # Create CR with not_found status
        cr = self._create_test_cr_with_detail(
            birth_registration_number="NOTFOUND123",
            birth_verification_status="not_found",
        )

        # Apply the change request
        apply_strategy = self.env["spp.cr.apply.add_member"]
        apply_strategy.apply(cr)

        # Get the created individual
        detail = cr.get_detail()
        individual = detail.created_individual_id

        # Check registry ID was NOT created
        registry_id = self.RegistryId.search(
            [
                ("partner_id", "=", individual.id),
                ("id_type_id", "=", self.brn_id_type.id),
            ]
        )

        self.assertFalse(registry_id, "BRN registry ID should NOT be created for not_found")

    def test_apply_no_brn_when_no_brn_number(self):
        """Test that verified CR without BRN number does not create registry ID."""
        if not self.brn_id_type:
            self.skipTest("BRN ID type not found - module data may not be loaded")

        # Create CR verified but no BRN
        cr = self._create_test_cr_with_detail(
            birth_verification_status="verified",
            birth_verification_date=fields.Datetime.now(),
            # No birth_registration_number
        )

        # Apply the change request
        apply_strategy = self.env["spp.cr.apply.add_member"]
        apply_strategy.apply(cr)

        # Get the created individual
        detail = cr.get_detail()
        individual = detail.created_individual_id

        # Check registry ID was NOT created
        registry_id = self.RegistryId.search(
            [
                ("partner_id", "=", individual.id),
                ("id_type_id", "=", self.brn_id_type.id),
            ]
        )

        self.assertFalse(registry_id, "BRN registry ID should NOT be created without BRN number")

    def test_apply_updates_existing_brn(self):
        """Test that applying updates existing BRN registry ID."""
        if not self.brn_id_type:
            self.skipTest("BRN ID type not found - module data may not be loaded")

        # First, create an individual with an existing BRN
        individual = self.env["res.partner"].create(
            {
                "name": "Existing Child",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Create an existing unverified BRN
        existing_brn = self.RegistryId.create(
            {
                "partner_id": individual.id,
                "id_type_id": self.brn_id_type.id,
                "value": "OLD_BRN",
                "status": "invalid",
            }
        )

        # Create CR with verified birth
        cr = self._create_test_cr_with_detail(
            birth_registration_number="NEW_BRN",
            birth_verification_status="verified",
            birth_verification_date=fields.Datetime.now(),
            birth_verification_response='{"new": "data"}',
            dci_data_source_id=self.data_source.id,
        )

        # Manually set the created_individual_id to our existing individual
        detail = cr.get_detail()
        detail.write(
            {
                "created_individual_id": individual.id,
            }
        )

        # Call the BRN creation method directly
        apply_strategy = self.env["spp.cr.apply.add_member"]
        apply_strategy._create_verified_brn_registry_id(detail)

        # Refresh existing BRN
        existing_brn.invalidate_recordset()

        # Check existing BRN was updated
        self.assertEqual(existing_brn.value, "NEW_BRN")
        self.assertEqual(existing_brn.status, "valid")
        self.assertEqual(existing_brn.verification_method, "dci_api")
        self.assertTrue(existing_brn.is_verified)


@tagged("post_install", "-at_install")
class TestRegistryIdVerification(TransactionCase):
    """Test verification fields on spp.registry.id model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.RegistryId = cls.env["spp.registry.id"]

        # Get an ID type
        cls.id_type = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:id-type"),
            ],
            limit=1,
        )
        if not cls.id_type:
            # Create a vocabulary and code for testing
            vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )
            cls.id_type = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": vocab.id,
                    "code": "test_id",
                    "display": "Test ID",
                }
            )

        # Create a test registrant
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_is_verified_computed_for_dci_api(self):
        """Test is_verified is True for dci_api verification method."""
        registry_id = self.RegistryId.create(
            {
                "partner_id": self.registrant.id,
                "id_type_id": self.id_type.id,
                "value": "TEST123",
                "verification_method": "dci_api",
            }
        )

        self.assertTrue(registry_id.is_verified)

    def test_is_verified_computed_for_physical_document(self):
        """Test is_verified is True for physical_document verification method."""
        registry_id = self.RegistryId.create(
            {
                "partner_id": self.registrant.id,
                "id_type_id": self.id_type.id,
                "value": "TEST456",
                "verification_method": "physical_document",
            }
        )

        self.assertTrue(registry_id.is_verified)

    def test_is_verified_false_for_verbal(self):
        """Test is_verified is False for verbal verification method."""
        registry_id = self.RegistryId.create(
            {
                "partner_id": self.registrant.id,
                "id_type_id": self.id_type.id,
                "value": "TEST789",
                "verification_method": "verbal",
            }
        )

        self.assertFalse(registry_id.is_verified)

    def test_is_verified_false_for_self_declared(self):
        """Test is_verified is False for self_declared verification method."""
        registry_id = self.RegistryId.create(
            {
                "partner_id": self.registrant.id,
                "id_type_id": self.id_type.id,
                "value": "TEST012",
                "verification_method": "self_declared",
            }
        )

        self.assertFalse(registry_id.is_verified)

    def test_is_verified_false_when_no_method(self):
        """Test is_verified is False when no verification method set."""
        registry_id = self.RegistryId.create(
            {
                "partner_id": self.registrant.id,
                "id_type_id": self.id_type.id,
                "value": "TEST345",
            }
        )

        self.assertFalse(registry_id.is_verified)
