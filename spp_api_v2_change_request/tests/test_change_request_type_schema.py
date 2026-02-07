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
        self.assertIn("fields", result)
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
    # Field definition tests
    # ──────────────────────────────────────────────────────────────────────

    def test_field_definitions_include_expected_fields(self):
        """given_name, family_name, birthdate are present in the schema."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")

        field_names = [f["name"] for f in result["fields"]]
        self.assertIn("given_name", field_names)
        self.assertIn("family_name", field_names)
        self.assertIn("birthdate", field_names)

    def test_field_definitions_exclude_internal_fields(self):
        """Internal fields like id, create_uid, message_ids, change_request_id are absent."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")

        field_names = {f["name"] for f in result["fields"]}
        self.assertNotIn("id", field_names)
        self.assertNotIn("create_uid", field_names)
        self.assertNotIn("message_ids", field_names)
        self.assertNotIn("change_request_id", field_names)
        self.assertNotIn("registrant_id", field_names)
        self.assertNotIn("approval_state", field_names)
        self.assertNotIn("is_applied", field_names)

    def test_field_types_mapped_correctly(self):
        """Odoo field types map to the correct API types."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")

        fields_by_name = {f["name"]: f for f in result["fields"]}

        # char -> string
        self.assertEqual(fields_by_name["given_name"]["type"], "string")
        # date -> date
        self.assertEqual(fields_by_name["birthdate"]["type"], "date")
        # many2one vocabulary -> code
        self.assertEqual(fields_by_name["gender_id"]["type"], "code")

    def test_vocabulary_field_includes_namespace(self):
        """A vocabulary many2one field has vocabulary with namespaceUri and codes."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")

        fields_by_name = {f["name"]: f for f in result["fields"]}
        gender_field = fields_by_name["gender_id"]

        self.assertIsNotNone(gender_field.get("vocabulary"))
        vocab = gender_field["vocabulary"]
        self.assertEqual(vocab["namespaceUri"], "urn:iso:std:iso:5218")
        self.assertIsInstance(vocab["codes"], list)
        self.assertTrue(len(vocab["codes"]) > 0)

        # Check code structure
        code_values = [c["value"] for c in vocab["codes"]]
        self.assertIn("1", code_values)
        self.assertIn("2", code_values)

    def test_selection_field_includes_choices(self):
        """Selection fields have a choices array (if any exist on the model)."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")

        # edit_individual may not have selection fields, so just verify the
        # structure: if any field has type "selection", it must have choices
        for field_def in result["fields"]:
            if field_def["type"] == "selection":
                self.assertIsNotNone(field_def.get("choices"))
                self.assertIsInstance(field_def["choices"], list)
                if field_def["choices"]:
                    self.assertIn("value", field_def["choices"][0])
                    self.assertIn("label", field_def["choices"][0])

    def test_computed_stored_field_is_readonly(self):
        """Fields with a compute method are marked readonly."""
        service = self._get_service()
        # Test the logic directly via _build_field_definitions to check
        # that computed fields are marked as readonly.
        detail_model = self.env["spp.cr.detail.edit_individual"]
        field_defs = service._build_field_definitions(self.cr_type_edit, detail_model)

        for field_def in field_defs:
            field_name = field_def["name"]
            odoo_field = detail_model._fields.get(field_name)
            if odoo_field and odoo_field.compute:
                self.assertTrue(
                    field_def["readonly"],
                    f"Computed field {field_name} should be readonly",
                )

    def test_dynamic_domain_does_not_crash(self):
        """A domain containing Python name references does not crash vocabulary extraction."""
        service = self._get_service()
        # Simulate a domain string with a Python variable reference
        info = service._extract_vocabulary_info_from_domain(
            "[('id', '!=', registrant_id)]",
            "spp.vocabulary.code",
        )
        # Should return None gracefully, not crash
        self.assertIsNone(info)

    def test_field_definition_has_label(self):
        """All field definitions have a non-empty label."""
        service = self._get_service()
        result = service.get_type_schema("edit_individual")

        for field_def in result["fields"]:
            self.assertTrue(
                field_def.get("label"),
                f"Field {field_def['name']} should have a non-empty label",
            )
