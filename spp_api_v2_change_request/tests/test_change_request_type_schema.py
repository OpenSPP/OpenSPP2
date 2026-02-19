# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Change Request type schema endpoints."""

from .common import ChangeRequestTestCase


class TestChangeRequestTypeSchema(ChangeRequestTestCase):
    """Tests for CR type list and schema service methods."""

    # ──────────────────────────────────────────────────────────────────────
    # get_type_list tests
    # ──────────────────────────────────────────────────────────────────────

    def test_get_type_list(self):
        """get_type_list returns a list including our known type."""
        service = self._get_service()
        result = service.get_type_list()

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

        codes = [t["code"] for t in result]
        self.assertIn("edit_individual", codes)

    def test_get_type_list_only_contains_valid_models(self):
        """All returned types have detail models that exist in the Odoo registry."""
        service = self._get_service()
        result = service.get_type_list()

        for type_info in result:
            cr_type = self.env["spp.change.request.type"].search([("code", "=", type_info["code"])], limit=1)
            self.assertTrue(
                cr_type.detail_model in self.env,
                f"Type {type_info['code']} has invalid detail_model {cr_type.detail_model}",
            )

    # ──────────────────────────────────────────────────────────────────────
    # get_type_schema tests
    # ──────────────────────────────────────────────────────────────────────

    def test_get_type_schema(self):
        """get_type_schema returns full schema with expected structure."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")

        self.assertIsNotNone(result)
        self.assertIn("typeInfo", result)
        self.assertIn("detailSchema", result)
        self.assertIn("availableDocuments", result)
        self.assertIn("requiredDocuments", result)

        type_info = result["typeInfo"]
        self.assertEqual(type_info["code"], "edit_individual")
        self.assertEqual(type_info["name"], "Edit Individual")
        self.assertEqual(type_info["targetType"], "individual")

    def test_get_type_schema_not_found(self):
        """get_type_schema returns None for an invalid code."""
        service = self._get_service()
        result = service.get_type_schema("totally_fake_type_xyz")
        self.assertIsNone(result)

    # ──────────────────────────────────────────────────────────────────────
    # JSON Schema structure tests
    # ──────────────────────────────────────────────────────────────────────

    def test_detail_schema_is_valid_json_schema(self):
        """detailSchema has $schema, type=object, and properties."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        schema = result["detailSchema"]

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["type"], "object")
        self.assertIn("properties", schema)
        self.assertIsInstance(schema["properties"], dict)

    def test_detail_schema_has_title(self):
        """detailSchema has a title derived from the CR type name."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        schema = result["detailSchema"]

        self.assertEqual(schema["title"], "Edit Individual Detail")

    # ──────────────────────────────────────────────────────────────────────
    # Field property tests
    # ──────────────────────────────────────────────────────────────────────

    def test_properties_include_expected_fields(self):
        """given_name, family_name, birthdate are present in the schema properties."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        properties = result["detailSchema"]["properties"]

        self.assertIn("given_name", properties)
        self.assertIn("family_name", properties)
        self.assertIn("birthdate", properties)

    def test_properties_exclude_internal_fields(self):
        """Internal fields like id, create_uid, message_ids, change_request_id are absent."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        properties = result["detailSchema"]["properties"]

        self.assertNotIn("id", properties)
        self.assertNotIn("create_uid", properties)
        self.assertNotIn("message_ids", properties)
        self.assertNotIn("change_request_id", properties)
        self.assertNotIn("registrant_id", properties)
        self.assertNotIn("approval_state", properties)
        self.assertNotIn("is_applied", properties)

    def test_field_types_mapped_correctly(self):
        """Odoo field types map to the correct JSON Schema types."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        properties = result["detailSchema"]["properties"]

        # char -> {"type": "string"}
        self.assertEqual(properties["given_name"]["type"], "string")
        # date -> {"type": "string", "format": "date"}
        self.assertEqual(properties["birthdate"]["type"], "string")
        self.assertEqual(properties["birthdate"]["format"], "date")
        # many2one vocabulary -> {"type": "object", "x-field-type": "vocabulary"}
        self.assertEqual(properties["gender_id"]["type"], "object")
        self.assertEqual(properties["gender_id"]["x-field-type"], "vocabulary")

    def test_vocabulary_field_includes_namespace(self):
        """A vocabulary field has system const and oneOf codes."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        properties = result["detailSchema"]["properties"]
        gender_prop = properties["gender_id"]

        self.assertEqual(gender_prop.get("x-vocabulary-uri"), "urn:iso:std:iso:5218")

        # system property should have const with the namespace URI
        system_prop = gender_prop["properties"]["system"]
        self.assertEqual(system_prop["const"], "urn:iso:std:iso:5218")

        # code property should have oneOf with vocabulary codes
        code_prop = gender_prop["properties"]["code"]
        self.assertIn("oneOf", code_prop)
        code_values = [entry["const"] for entry in code_prop["oneOf"]]
        self.assertIn("1", code_values)
        self.assertIn("2", code_values)

    def test_selection_field_includes_choices(self):
        """Selection fields have oneOf with const/title entries (if any exist on the model)."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        properties = result["detailSchema"]["properties"]

        # Check any selection-type Odoo field on the detail model
        detail_model = self.env["spp.cr.detail.edit_individual"]
        for field_name, field in detail_model._fields.items():
            if field.type == "selection" and field_name in properties:
                prop = properties[field_name]
                if "oneOf" in prop:
                    for entry in prop["oneOf"]:
                        self.assertIn("const", entry)
                        self.assertIn("title", entry)

    def test_computed_stored_field_is_readonly(self):
        """Fields with a compute method are marked readOnly in the schema."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        properties = result["detailSchema"]["properties"]

        detail_model = self.env["spp.cr.detail.edit_individual"]
        for field_name, prop in properties.items():
            odoo_field = detail_model._fields.get(field_name)
            if odoo_field and odoo_field.compute:
                self.assertTrue(
                    prop.get("readOnly"),
                    f"Computed field {field_name} should have readOnly=true",
                )

    def test_required_fields_in_required_array(self):
        """Required Odoo fields appear in the schema's required array."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        schema = result["detailSchema"]

        required = schema.get("required", [])
        detail_model = self.env["spp.cr.detail.edit_individual"]
        for field_name in required:
            odoo_field = detail_model._fields.get(field_name)
            self.assertTrue(
                odoo_field and odoo_field.required,
                f"Field {field_name} is in 'required' but Odoo field is not required",
            )

    def test_field_property_has_title(self):
        """All field properties have a non-empty title."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")
        properties = result["detailSchema"]["properties"]

        for field_name, prop in properties.items():
            self.assertTrue(
                prop.get("title"),
                f"Property {field_name} should have a non-empty title",
            )

    # ──────────────────────────────────────────────────────────────────────
    # Vocabulary extraction edge cases
    # ──────────────────────────────────────────────────────────────────────

    def test_dynamic_domain_does_not_crash(self):
        """A domain containing Python name references does not crash vocabulary extraction."""
        from odoo.addons.spp_api_v2.services.schema_builder import OdooModelSchemaBuilder

        builder = OdooModelSchemaBuilder(self.env)
        info = builder._extract_vocabulary_info_from_domain(
            "[('id', '!=', registrant_id)]",
            "spp.vocabulary.code",
        )
        # Should return None gracefully, not crash
        self.assertIsNone(info)
