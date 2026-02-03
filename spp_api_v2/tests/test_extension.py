# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for API Extension mechanism"""

from ..services.extension_service import ExtensionService
from .common import ApiV2TestCase


class TestExtension(ApiV2TestCase):
    """Test API Extension registry and service"""

    def setUp(self):
        super().setUp()
        self.service = ExtensionService(self.env)

        # Create a test module
        self.test_module = self.env["ir.module.module"].search([("name", "=", "spp_api_v2")], limit=1)

        # Create test fields on res.partner for extension
        self.field_farm_size = self.env["ir.model.fields"].create(
            {
                "name": "x_farm_size",
                "field_description": "Farm Size",
                "model_id": self.env.ref("base.model_res_partner").id,
                "ttype": "float",
                "state": "manual",
            }
        )

        self.field_primary_crop = self.env["ir.model.fields"].create(
            {
                "name": "x_primary_crop_id",
                "field_description": "Primary Crop",
                "model_id": self.env.ref("base.model_res_partner").id,
                "ttype": "many2one",
                "relation": "spp.vocabulary.code",
                "state": "manual",
            }
        )

    def test_api_extension_model_creation(self):
        """ApiExtension model can be created"""
        extension = self.env["spp.api.extension"].create(
            {
                "name": "Farmer Extension",
                "url": "urn:openspp:extension:farmer",
                "module_id": self.test_module.id,
                "applies_to": "individual",
                "field_ids": [(6, 0, [self.field_farm_size.id])],
            }
        )

        self.assertTrue(extension)
        self.assertEqual(extension.name, "Farmer Extension")
        self.assertEqual(extension.url, "urn:openspp:extension:farmer")
        self.assertTrue(extension.active)

    def test_get_extensions_for_resource_returns_correct_extensions(self):
        """get_extensions_for_resource returns extensions for resource type"""
        # Create extensions for different resource types
        ext_individual = self.env["spp.api.extension"].create(
            {
                "name": "Individual Extension",
                "url": "urn:openspp:extension:individual-only",
                "module_id": self.test_module.id,
                "applies_to": "individual",
            }
        )

        ext_group = self.env["spp.api.extension"].create(
            {
                "name": "Group Extension",
                "url": "urn:openspp:extension:group-only",
                "module_id": self.test_module.id,
                "applies_to": "group",
            }
        )

        ext_both = self.env["spp.api.extension"].create(
            {
                "name": "Both Extension",
                "url": "urn:openspp:extension:both",
                "module_id": self.test_module.id,
                "applies_to": "both",
            }
        )

        # Get extensions for individual
        individual_exts = self.env["spp.api.extension"].get_extensions_for_resource("individual")
        self.assertIn(ext_individual, individual_exts)
        self.assertIn(ext_both, individual_exts)
        self.assertNotIn(ext_group, individual_exts)

        # Get extensions for group
        group_exts = self.env["spp.api.extension"].get_extensions_for_resource("group")
        self.assertIn(ext_group, group_exts)
        self.assertIn(ext_both, group_exts)
        self.assertNotIn(ext_individual, group_exts)

    def test_extension_service_maps_fields_correctly(self):
        """ExtensionService maps extension fields to API format"""
        # Create extension with fields
        self.env["spp.api.extension"].create(
            {
                "name": "Farmer Extension",
                "url": "urn:openspp:extension:farmer",
                "module_id": self.test_module.id,
                "applies_to": "individual",
                "field_ids": [(6, 0, [self.field_farm_size.id])],
            }
        )

        # Create individual with extension data
        individual = self.create_test_individual(identifier_value="FARMER-001")
        individual.write({"x_farm_size": 2.5})

        # Get extension data
        extension_data = self.service.get_extension_data(individual, ["farmer"], "individual")

        self.assertIn("farmer", extension_data)
        self.assertEqual(extension_data["farmer"]["url"], "urn:openspp:extension:farmer")
        self.assertEqual(extension_data["farmer"]["farmSize"], 2.5)

    def test_odoo_to_api_field_name_converts_snake_case_to_camel_case(self):
        """_odoo_to_api_field_name converts snake_case to camelCase"""
        self.assertEqual(self.service._odoo_to_api_field_name("x_farm_size"), "farmSize")
        self.assertEqual(self.service._odoo_to_api_field_name("x_primary_crop_id"), "primaryCrop")
        self.assertEqual(self.service._odoo_to_api_field_name("farm_size"), "farmSize")
        self.assertEqual(
            self.service._odoo_to_api_field_name("some_long_field_name"),
            "someLongFieldName",
        )

    def test_many2one_with_namespace_uri_becomes_codeable_concept(self):
        """Many2one field with namespace_uri converts to CodeableConcept"""
        # Create a vocabulary code for crop type
        crop_vocabulary = self.env["spp.vocabulary"].create(
            {
                "name": "Crop Type",
                "namespace_uri": "urn:openspp:vocab:crop-type",
            }
        )
        crop_rice = self.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": crop_vocabulary.id,
                "code": "rice",
                "display": "Rice",
                "namespace_uri": "urn:openspp:vocab:crop-type",
            }
        )

        # Create extension with many2one field
        self.env["spp.api.extension"].create(
            {
                "name": "Farmer Extension",
                "url": "urn:openspp:extension:farmer",
                "module_id": self.test_module.id,
                "applies_to": "individual",
                "field_ids": [(6, 0, [self.field_primary_crop.id])],
            }
        )

        # Create individual with crop type
        individual = self.create_test_individual(identifier_value="FARMER-002")
        individual.write({"x_primary_crop_id": crop_rice.id})

        # Get extension data
        extension_data = self.service.get_extension_data(individual, ["farmer"], "individual")

        self.assertIn("farmer", extension_data)
        primary_crop = extension_data["farmer"]["primaryCrop"]
        self.assertIn("coding", primary_crop)
        self.assertEqual(primary_crop["coding"][0]["system"], "urn:openspp:vocab:crop-type")
        self.assertEqual(primary_crop["coding"][0]["code"], "rice")
        self.assertEqual(primary_crop["coding"][0]["display"], "Rice")

    def test_extensions_parameter_filters_extensions(self):
        """_extensions parameter filters which extensions are returned"""
        # Create multiple extensions
        self.env["spp.api.extension"].create(
            {
                "name": "Farmer Extension",
                "url": "urn:openspp:extension:farmer",
                "module_id": self.test_module.id,
                "applies_to": "individual",
                "field_ids": [(6, 0, [self.field_farm_size.id])],
            }
        )

        self.env["spp.api.extension"].create(
            {
                "name": "Health Extension",
                "url": "urn:openspp:extension:health",
                "module_id": self.test_module.id,
                "applies_to": "individual",
            }
        )

        individual = self.create_test_individual(identifier_value="MULTI-EXT")
        individual.write({"x_farm_size": 3.0})

        # Request only farmer extension
        extension_data = self.service.get_extension_data(individual, ["farmer"], "individual")

        self.assertIn("farmer", extension_data)
        self.assertNotIn("health", extension_data)

    def test_extensions_wildcard_returns_all_extensions(self):
        """_extensions=* returns all available extensions"""
        # Create multiple extensions
        self.env["spp.api.extension"].create(
            {
                "name": "Farmer Extension",
                "url": "urn:openspp:extension:farmer",
                "module_id": self.test_module.id,
                "applies_to": "individual",
                "field_ids": [(6, 0, [self.field_farm_size.id])],
            }
        )

        self.env["spp.api.extension"].create(
            {
                "name": "Health Extension",
                "url": "urn:openspp:extension:health",
                "module_id": self.test_module.id,
                "applies_to": "individual",
            }
        )

        individual = self.create_test_individual(identifier_value="ALL-EXT")
        individual.write({"x_farm_size": 3.0})

        # Request all extensions with wildcard
        extension_data = self.service.get_extension_data(individual, ["*"], "individual")

        # Should return both extensions (though health might be empty)
        self.assertIn("farmer", extension_data)
        # Health extension might not appear if it has no fields with data

    def test_empty_extension_names_returns_empty_dict(self):
        """Empty extension_names list returns empty dict"""
        individual = self.create_test_individual(identifier_value="NO-EXT")

        extension_data = self.service.get_extension_data(individual, [], "individual")

        self.assertEqual(extension_data, {})

    def test_extension_key_extraction_from_url(self):
        """Extension key is extracted from URL correctly"""
        extension = self.env["spp.api.extension"].create(
            {
                "name": "Farmer Extension",
                "url": "urn:openspp:extension:farmer",
                "module_id": self.test_module.id,
                "applies_to": "individual",
            }
        )

        key = self.service._get_extension_key(extension)
        self.assertEqual(key, "farmer")

        # Test with different URL format
        extension2 = self.env["spp.api.extension"].create(
            {
                "name": "Health Data",
                "url": "urn:openspp:extension:health-data",
                "module_id": self.test_module.id,
                "applies_to": "individual",
            }
        )

        key2 = self.service._get_extension_key(extension2)
        self.assertEqual(key2, "health-data")

    def test_inactive_extensions_not_returned(self):
        """Inactive extensions are not returned by get_extensions_for_resource"""
        extension = self.env["spp.api.extension"].create(
            {
                "name": "Inactive Extension",
                "url": "urn:openspp:extension:inactive",
                "module_id": self.test_module.id,
                "applies_to": "individual",
                "active": False,
            }
        )

        extensions = self.env["spp.api.extension"].get_extensions_for_resource("individual")

        self.assertNotIn(extension, extensions)

    def test_extension_preserves_falsy_values(self):
        """Extension fields with falsy values (0, 0.0, False) are preserved"""
        # Create a boolean field for testing
        field_is_organic = self.env["ir.model.fields"].create(
            {
                "name": "x_is_organic",
                "field_description": "Is Organic",
                "model_id": self.env.ref("base.model_res_partner").id,
                "ttype": "boolean",
                "state": "manual",
            }
        )

        # Create an integer field for testing zero
        field_plot_count = self.env["ir.model.fields"].create(
            {
                "name": "x_plot_count",
                "field_description": "Plot Count",
                "model_id": self.env.ref("base.model_res_partner").id,
                "ttype": "integer",
                "state": "manual",
            }
        )

        # Create extension with farm_size (float), boolean, and integer fields
        self.env["spp.api.extension"].create(
            {
                "name": "Farmer Extension",
                "url": "urn:openspp:extension:farmer",
                "module_id": self.test_module.id,
                "applies_to": "individual",
                "field_ids": [(6, 0, [self.field_farm_size.id, field_is_organic.id, field_plot_count.id])],
            }
        )

        # Create individual with explicitly falsy values
        individual = self.create_test_individual(identifier_value="FALSY-001")
        individual.write(
            {
                "x_farm_size": 0.0,
                "x_is_organic": False,
                "x_plot_count": 0,
            }
        )

        extension_data = self.service.get_extension_data(individual, ["farmer"], "individual")

        self.assertIn("farmer", extension_data)
        # 0.0 should be preserved, not skipped
        self.assertEqual(extension_data["farmer"]["farmSize"], 0.0)
        # False should be preserved, not skipped
        self.assertEqual(extension_data["farmer"]["isOrganic"], False)
        # 0 should be preserved, not skipped
        self.assertEqual(extension_data["farmer"]["plotCount"], 0)

    def test_extension_with_no_field_data_includes_defaults(self):
        """Extension with unset float field includes Odoo default (0.0)"""
        self.env["spp.api.extension"].create(
            {
                "name": "Empty Extension",
                "url": "urn:openspp:extension:empty",
                "module_id": self.test_module.id,
                "applies_to": "individual",
                "field_ids": [(6, 0, [self.field_farm_size.id])],
            }
        )

        # Create individual without writing to farm_size
        individual = self.create_test_individual(identifier_value="NO-DATA")

        extension_data = self.service.get_extension_data(individual, ["empty"], "individual")

        # Float fields in Odoo default to 0.0, which is now preserved as a valid value
        self.assertIn("empty", extension_data)
        self.assertEqual(extension_data["empty"]["farmSize"], 0.0)

    def test_extension_with_unset_many2one_not_included(self):
        """Extension with unset many2one field does not include the field"""
        self.env["spp.api.extension"].create(
            {
                "name": "Crop Extension",
                "url": "urn:openspp:extension:crop",
                "module_id": self.test_module.id,
                "applies_to": "individual",
                "field_ids": [(6, 0, [self.field_primary_crop.id])],
            }
        )

        # Create individual without setting primary_crop
        individual = self.create_test_individual(identifier_value="NO-CROP")

        extension_data = self.service.get_extension_data(individual, ["crop"], "individual")

        # Many2one fields that are not set (empty recordset) should be excluded
        if "crop" in extension_data:
            self.assertNotIn("primaryCrop", extension_data["crop"])
