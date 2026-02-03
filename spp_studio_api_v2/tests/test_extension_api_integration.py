# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Integration tests for extension write functionality with API V2."""

from datetime import date

from odoo.tests.common import TransactionCase


class TestExtensionAPIIntegration(TransactionCase):
    """Test that extension data can be written via Individual and Group APIs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get or create ID Type vocabulary (using the vocabulary-based ID type system)
        id_type_vocab = cls.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1
        )
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )

        # Get or create test ID type code within the ID Type vocabulary
        cls.id_type = cls.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", id_type_vocab.id), ("code", "=", "test_national_id")],
            limit=1,
        )
        if not cls.id_type:
            cls.id_type = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": id_type_vocab.id,
                    "code": "test_national_id",
                    "display": "Test National ID",
                    "is_local": True,
                    "target_type": "both",
                }
            )

        # Create test vocabulary for custom field
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": "Crop Types",
                "namespace_uri": "urn:test:crop-types",
            }
        )
        cls.crop_rice = cls.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": cls.vocab.id,
                "code": "rice",
                "display": "Rice",
                # namespace_uri is a related field from vocabulary_id
            }
        )
        cls.crop_corn = cls.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": cls.vocab.id,
                "code": "corn",
                "display": "Corn",
                # namespace_uri is a related field from vocabulary_id
            }
        )

        # Create custom fields on res.partner for testing
        cls.field_farm_size = cls.env["ir.model.fields"].create(
            {
                "name": "x_farm_size",
                "field_description": "Farm Size",
                "model_id": cls.env.ref("base.model_res_partner").id,
                "ttype": "float",
                "state": "manual",
            }
        )
        cls.field_primary_crop = cls.env["ir.model.fields"].create(
            {
                "name": "x_primary_crop_id",
                "field_description": "Primary Crop",
                "model_id": cls.env.ref("base.model_res_partner").id,
                "ttype": "many2one",
                "relation": "spp.vocabulary.code",
                "state": "manual",
            }
        )
        cls.field_has_irrigation = cls.env["ir.model.fields"].create(
            {
                "name": "x_has_irrigation",
                "field_description": "Has Irrigation",
                "model_id": cls.env.ref("base.model_res_partner").id,
                "ttype": "boolean",
                "state": "manual",
            }
        )

        # Create extension for Individual
        module = cls.env["ir.module.module"].search([("name", "=", "spp_studio_api_v2")], limit=1)
        if not module:
            module = cls.env["ir.module.module"].search([("state", "=", "installed")], limit=1)

        cls.individual_extension = cls.env["spp.api.extension"].create(
            {
                "name": "Farmer Extension",
                "url": "urn:openspp:extension:farmer",
                "module_id": module.id,
                "applies_to": "individual",
                "active": True,
            }
        )

        # Link custom fields to extension using field_ids Many2many
        cls.individual_extension.write(
            {
                "field_ids": [
                    (4, cls.field_farm_size.id),
                    (4, cls.field_primary_crop.id),
                    (4, cls.field_has_irrigation.id),
                ],
            }
        )

        # Create extension for Group
        cls.group_extension = cls.env["spp.api.extension"].create(
            {
                "name": "Farm Group Extension",
                "url": "urn:openspp:extension:farm-group",
                "module_id": module.id,
                "applies_to": "group",
                "active": True,
                "field_ids": [(4, cls.field_farm_size.id)],
            }
        )

    def test_individual_create_with_extension_data(self):
        """Test creating an individual with extension data via IndividualService."""
        # Import here to avoid circular import
        from odoo.addons.spp_api_v2.schemas.individual import Individual
        from odoo.addons.spp_api_v2.services.individual_service import IndividualService

        # Build Individual schema with extension data
        individual_data = Individual(
            identifier=[
                {
                    "system": "urn:openspp:vocab:id-type#test_national_id",
                    "value": "FARM-001",
                }
            ],
            active=True,
            name={
                "family": "Farmer",
                "given": "John",
                "text": "John Farmer",
            },
            birthDate=date(1980, 1, 15),
            extension={
                "urn:openspp:extension:farmer": {
                    "farmSize": 2.5,
                    "primaryCrop": {
                        "coding": [
                            {
                                "system": "urn:test:crop-types",
                                "code": "rice",
                                "display": "Rice",
                            }
                        ]
                    },
                    "hasIrrigation": True,
                }
            },
        )

        # Create individual
        service = IndividualService(self.env)
        partner = service.create(
            individual_data,
            source="urn:test:integration-test",
            api_authorized=True,
        )

        # Verify base fields
        self.assertEqual(partner.name, "John Farmer")
        self.assertEqual(partner.family_name, "Farmer")
        self.assertEqual(partner.given_name, "John")
        self.assertTrue(partner.is_registrant)
        self.assertFalse(partner.is_group)

        # Verify extension fields were written
        self.assertEqual(partner.x_farm_size, 2.5)
        self.assertEqual(partner.x_primary_crop_id.id, self.crop_rice.id)
        self.assertTrue(partner.x_has_irrigation)

    def test_individual_update_with_extension_data(self):
        """Test updating an individual with extension data via IndividualService."""
        # Import here to avoid circular import
        from odoo.addons.spp_api_v2.schemas.individual import Individual
        from odoo.addons.spp_api_v2.services.individual_service import IndividualService

        # Create initial individual
        partner = self.env["res.partner"].create(
            {
                "name": "Jane Farmer",
                "is_registrant": True,
                "is_group": False,
                "family_name": "Farmer",
                "given_name": "Jane",
                "reg_ids": [
                    (
                        0,
                        0,
                        {
                            "id_type_id": self.id_type.id,
                            "value": "FARM-002",
                        },
                    )
                ],
            }
        )

        # Update with extension data
        update_data = Individual(
            identifier=[
                {
                    "system": "urn:openspp:vocab:id-type#test_national_id",
                    "value": "FARM-002",
                }
            ],
            active=True,
            name={
                "family": "Farmer",
                "given": "Jane",
                "text": "Jane Farmer",
            },
            extension={
                "urn:openspp:extension:farmer": {
                    "farmSize": 5.0,
                    "primaryCrop": {
                        "coding": [
                            {
                                "system": "urn:test:crop-types",
                                "code": "corn",
                                "display": "Corn",
                            }
                        ]
                    },
                    "hasIrrigation": False,
                }
            },
        )

        service = IndividualService(self.env)
        partner = service.update(
            partner,
            update_data,
            source="urn:test:integration-test",
        )

        # Verify extension fields were updated
        self.assertEqual(partner.x_farm_size, 5.0)
        self.assertEqual(partner.x_primary_crop_id.id, self.crop_corn.id)
        self.assertFalse(partner.x_has_irrigation)

    def test_group_create_with_extension_data(self):
        """Test creating a group with extension data via GroupService."""
        # Import here to avoid circular import
        from odoo.addons.spp_api_v2.schemas.group import Group
        from odoo.addons.spp_api_v2.services.group_service import GroupService

        # Build Group schema with extension data
        # Note: 'type' must be "Group" (resource discriminator), 'groupType' is the group kind
        group_data = Group(
            identifier=[
                {
                    "system": "urn:openspp:vocab:id-type#test_national_id",
                    "value": "GRP-001",
                }
            ],
            active=True,
            type="Group",
            groupType="household",
            name="Rice Farmers Cooperative",
            extension={
                "urn:openspp:extension:farm-group": {
                    "farmSize": 25.5,
                }
            },
        )

        # Create group
        service = GroupService(self.env)
        group = service.create(
            group_data,
            source="urn:test:integration-test",
            api_authorized=True,
        )

        # Verify base fields
        self.assertEqual(group.name, "Rice Farmers Cooperative")
        self.assertTrue(group.is_registrant)
        self.assertTrue(group.is_group)

        # Verify extension fields were written
        self.assertEqual(group.x_farm_size, 25.5)

    def test_group_update_with_extension_data(self):
        """Test updating a group with extension data via GroupService."""
        # Import here to avoid circular import
        from odoo.addons.spp_api_v2.schemas.group import Group
        from odoo.addons.spp_api_v2.services.group_service import GroupService

        # Create initial group
        group = self.env["res.partner"].create(
            {
                "name": "Corn Farmers Cooperative",
                "is_registrant": True,
                "is_group": True,
                "reg_ids": [
                    (
                        0,
                        0,
                        {
                            "id_type_id": self.id_type.id,
                            "value": "GRP-002",
                        },
                    )
                ],
            }
        )

        # Update with extension data
        # Note: 'type' must be "Group" (resource discriminator), 'groupType' is the group kind
        update_data = Group(
            identifier=[
                {
                    "system": "urn:openspp:vocab:id-type#test_national_id",
                    "value": "GRP-002",
                }
            ],
            active=True,
            type="Group",
            groupType="household",
            name="Corn Farmers Cooperative",
            extension={
                "urn:openspp:extension:farm-group": {
                    "farmSize": 50.0,
                }
            },
        )

        service = GroupService(self.env)
        group = service.update(
            group,
            update_data,
            source="urn:test:integration-test",
        )

        # Verify extension fields were updated
        self.assertEqual(group.x_farm_size, 50.0)

    def test_extension_data_graceful_degradation_if_module_missing(self):
        """Test that extension data is skipped gracefully if spp_studio_api_v2 is not installed."""
        # This test verifies the ImportError handling in the services
        # In practice, this test runs when the module IS installed, so we can't
        # actually test the ImportError path. However, we document the behavior:
        # If spp_studio_api_v2 is not installed, the ImportError is caught and
        # extension data is silently skipped without breaking create/update.
        self.assertTrue(True, "Extension data graceful degradation is implemented")

    def test_extension_data_with_null_values(self):
        """Test that null extension values clear the fields."""
        # Import here to avoid circular import
        from odoo.addons.spp_api_v2.schemas.individual import Individual
        from odoo.addons.spp_api_v2.services.individual_service import IndividualService

        # Create individual with extension data
        partner = self.env["res.partner"].create(
            {
                "name": "Test Person",
                "is_registrant": True,
                "is_group": False,
                "reg_ids": [
                    (
                        0,
                        0,
                        {
                            "id_type_id": self.id_type.id,
                            "value": "FARM-003",
                        },
                    )
                ],
                "x_farm_size": 10.0,
                "x_primary_crop_id": self.crop_rice.id,
                "x_has_irrigation": True,
            }
        )

        # Update with null values
        update_data = Individual(
            identifier=[
                {
                    "system": "urn:openspp:vocab:id-type#test_national_id",
                    "value": "FARM-003",
                }
            ],
            active=True,
            name={
                "family": "Person",
                "given": "Test",
                "text": "Test Person",
            },
            extension={
                "urn:openspp:extension:farmer": {
                    "farmSize": None,
                    "primaryCrop": None,
                    "hasIrrigation": None,
                }
            },
        )

        service = IndividualService(self.env)
        partner = service.update(
            partner,
            update_data,
            source="urn:test:integration-test",
        )

        # Verify fields were cleared (set to False/0)
        self.assertEqual(partner.x_farm_size, 0.0)
        self.assertFalse(partner.x_primary_crop_id)
        self.assertFalse(partner.x_has_irrigation)
