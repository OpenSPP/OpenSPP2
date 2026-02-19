# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the generic OdooModelSchemaBuilder."""

from odoo.tests import TransactionCase

from ..services.schema_builder import OdooModelSchemaBuilder


class TestSchemaBuilder(TransactionCase):
    """Unit tests for OdooModelSchemaBuilder using res.partner as a real model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.builder = OdooModelSchemaBuilder(cls.env)

        # Gender vocabulary (needed for vocabulary field tests on res.partner)
        gender_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:iso:std:iso:5218")], limit=1)
        if not gender_vocab:
            gender_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "Gender (ISO 5218)",
                    "namespace_uri": "urn:iso:std:iso:5218",
                }
            )
        for code, display in [("1", "Male"), ("2", "Female")]:
            existing = cls.env["spp.vocabulary.code"].search(
                [("vocabulary_id", "=", gender_vocab.id), ("code", "=", code)],
                limit=1,
            )
            if not existing:
                cls.env["spp.vocabulary.code"].create(
                    {
                        "vocabulary_id": gender_vocab.id,
                        "code": code,
                        "display": display,
                    }
                )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_field_property(self, schema, odoo_type, *, comodel_name=None):
        """Find the first schema property whose Odoo field matches a given type.

        Returns (field_name, property_dict) or (None, None).
        """
        partner_fields = self.env["res.partner"]._fields
        for fname, prop in schema["properties"].items():
            odoo_field = partner_fields.get(fname)
            if not odoo_field or odoo_field.type != odoo_type:
                continue
            if comodel_name and odoo_field.comodel_name != comodel_name:
                continue
            return fname, prop
        return None, None

    # ------------------------------------------------------------------
    # Top-level schema structure
    # ------------------------------------------------------------------

    def test_schema_has_json_schema_keywords(self):
        """The generated schema contains $schema, type, and properties."""
        schema = self.builder.build_schema(self.env["res.partner"])
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["type"], "object")
        self.assertIn("properties", schema)

    def test_title_defaults_to_model_description(self):
        """When no title is given, the model's _description is used."""
        schema = self.builder.build_schema(self.env["res.partner"])
        self.assertIn("title", schema)
        self.assertTrue(len(schema["title"]) > 0)

    def test_title_override(self):
        """An explicit title overrides the default."""
        schema = self.builder.build_schema(
            self.env["res.partner"],
            title="Custom Title",
        )
        self.assertEqual(schema["title"], "Custom Title")

    # ------------------------------------------------------------------
    # Skip logic
    # ------------------------------------------------------------------

    def test_skip_fields_are_excluded(self):
        """Fields listed in skip_fields do not appear in properties."""
        schema = self.builder.build_schema(
            self.env["res.partner"],
            skip_fields={"name", "email"},
        )
        self.assertNotIn("name", schema["properties"])
        self.assertNotIn("email", schema["properties"])

    def test_binary_fields_skipped(self):
        """Binary fields (e.g. image_1920) are not in the schema."""
        schema = self.builder.build_schema(self.env["res.partner"])
        self.assertNotIn("image_1920", schema["properties"])

    def test_many2many_fields_skipped(self):
        """Many2many fields are not in the schema."""
        schema = self.builder.build_schema(self.env["res.partner"])
        # category_id is a many2many on res.partner
        self.assertNotIn("category_id", schema["properties"])

    def test_one2many_fields_skipped(self):
        """One2many fields are not in the schema."""
        schema = self.builder.build_schema(self.env["res.partner"])
        self.assertNotIn("child_ids", schema["properties"])

    def test_non_stored_fields_skipped(self):
        """Non-stored (non-persisted) fields are not in the schema."""
        schema = self.builder.build_schema(self.env["res.partner"])
        partner_fields = self.env["res.partner"]._fields
        for field_name in schema.get("properties", {}):
            odoo_field = partner_fields.get(field_name)
            if odoo_field:
                self.assertTrue(
                    odoo_field.store,
                    f"Non-stored field {field_name} should not appear in schema",
                )

    # ------------------------------------------------------------------
    # Field type mapping
    # ------------------------------------------------------------------

    def test_char_maps_to_string(self):
        """Char fields map to {"type": "string"}."""
        schema = self.builder.build_schema(self.env["res.partner"])
        name_prop = schema["properties"].get("name")
        self.assertIsNotNone(name_prop, "res.partner should have a 'name' field")
        self.assertEqual(name_prop["type"], "string")

    def test_date_maps_to_string_date(self):
        """Date fields map to {"type": "string", "format": "date"}."""
        schema = self.builder.build_schema(self.env["res.partner"])
        fname, prop = self._find_field_property(schema, "date")
        self.assertIsNotNone(fname, "res.partner should have at least one date field in schema")
        self.assertEqual(prop["type"], "string")
        self.assertEqual(prop["format"], "date")

    def test_integer_maps_to_integer(self):
        """Integer fields map to {"type": "integer"}."""
        schema = self.builder.build_schema(self.env["res.partner"])
        fname, prop = self._find_field_property(schema, "integer")
        self.assertIsNotNone(fname, "res.partner should have at least one integer field in schema")
        self.assertEqual(prop["type"], "integer")

    def test_float_maps_to_number(self):
        """Float fields map to {"type": "number"}."""
        schema = self.builder.build_schema(self.env["res.partner"])
        fname, prop = self._find_field_property(schema, "float")
        self.assertIsNotNone(fname, "res.partner should have at least one float field in schema")
        self.assertEqual(prop["type"], "number")

    def test_monetary_maps_to_number(self):
        """Monetary fields map to {"type": "number"} (same as float)."""
        schema = self.builder.build_schema(self.env["res.partner"])
        fname, prop = self._find_field_property(schema, "monetary")
        if fname is None:
            # monetary fields may not exist on res.partner; verify the handler directly
            handler_result = self.builder._handle_float(
                self.env["res.partner"]._fields.get("name")  # placeholder
            )
            self.assertEqual(handler_result["type"], "number")
            return
        self.assertEqual(prop["type"], "number")

    def test_boolean_maps_to_boolean(self):
        """Boolean fields map to {"type": "boolean"}."""
        schema = self.builder.build_schema(self.env["res.partner"])
        fname, prop = self._find_field_property(schema, "boolean")
        self.assertIsNotNone(fname, "res.partner should have at least one boolean field in schema")
        self.assertEqual(prop["type"], "boolean")

    def test_text_maps_to_string_multiline(self):
        """Text fields map to {"type": "string", "x-display": "multiline"}."""
        schema = self.builder.build_schema(self.env["res.partner"])
        fname, prop = self._find_field_property(schema, "text")
        self.assertIsNotNone(fname, "res.partner should have at least one text field in schema")
        self.assertEqual(prop["type"], "string")
        self.assertEqual(prop.get("x-display"), "multiline")

    def test_html_maps_to_string_multiline(self):
        """Html fields map to {"type": "string", "x-display": "multiline"} (same as text)."""
        schema = self.builder.build_schema(self.env["res.partner"])
        fname, prop = self._find_field_property(schema, "html")
        if fname is None:
            # html fields may not exist on res.partner; verify the handler directly
            handler_result = self.builder._handle_text(
                self.env["res.partner"]._fields.get("name")  # placeholder
            )
            self.assertEqual(handler_result["type"], "string")
            self.assertEqual(handler_result["x-display"], "multiline")
            return
        self.assertEqual(prop["type"], "string")
        self.assertEqual(prop.get("x-display"), "multiline")

    def test_selection_maps_to_oneof(self):
        """Selection fields map to oneOf with const/title entries."""
        schema = self.builder.build_schema(self.env["res.partner"])
        fname, prop = self._find_field_property(schema, "selection")
        self.assertIsNotNone(fname, "res.partner should have at least one selection field in schema")
        # Should have oneOf or fallback type: string
        if "oneOf" in prop:
            for entry in prop["oneOf"]:
                self.assertIn("const", entry)
                self.assertIn("title", entry)
        else:
            self.assertEqual(prop["type"], "string")

    # ------------------------------------------------------------------
    # Many2one handling
    # ------------------------------------------------------------------

    def test_vocabulary_field_produces_object(self):
        """A many2one to spp.vocabulary.code produces an object with x-field-type=vocabulary."""
        schema = self.builder.build_schema(self.env["res.partner"])
        gender_prop = schema["properties"].get("gender_id")
        self.assertIsNotNone(gender_prop, "res.partner should have a gender_id field in schema")
        self.assertEqual(gender_prop["type"], "object")
        self.assertEqual(gender_prop.get("x-field-type"), "vocabulary")
        self.assertIn("system", gender_prop["properties"])
        self.assertIn("code", gender_prop["properties"])

    def test_vocabulary_field_has_oneof_codes(self):
        """A vocabulary field with a parseable domain includes oneOf codes."""
        schema = self.builder.build_schema(self.env["res.partner"])
        gender_prop = schema["properties"].get("gender_id")
        self.assertIsNotNone(gender_prop, "res.partner should have a gender_id field in schema")
        code_prop = gender_prop["properties"].get("code", {})
        self.assertIn("oneOf", code_prop, "Vocabulary code property should have oneOf with choices")
        values = [e["const"] for e in code_prop["oneOf"]]
        self.assertIn("1", values)
        self.assertIn("2", values)

    def test_reference_field_uses_anyof(self):
        """A many2one to a non-vocabulary model uses anyOf with string and integer types."""
        schema = self.builder.build_schema(self.env["res.partner"])
        partner_fields = self.env["res.partner"]._fields
        found = False
        for fname, prop in schema["properties"].items():
            odoo_field = partner_fields.get(fname)
            if odoo_field and odoo_field.type == "many2one" and odoo_field.comodel_name != "spp.vocabulary.code":
                self.assertIn("anyOf", prop, f"Reference field {fname} should use anyOf")
                type_set = {entry["type"] for entry in prop["anyOf"]}
                self.assertEqual(type_set, {"string", "integer"})
                self.assertEqual(prop.get("x-field-type"), "reference")
                self.assertEqual(prop.get("x-reference-model"), odoo_field.comodel_name)
                found = True
                break
        self.assertTrue(found, "res.partner should have at least one non-vocabulary many2one field")

    # ------------------------------------------------------------------
    # Metadata keywords
    # ------------------------------------------------------------------

    def test_required_fields_in_required_array(self):
        """Fields with required=True appear in the schema's required array."""
        schema = self.builder.build_schema(self.env["res.partner"])
        required = schema.get("required", [])
        partner_fields = self.env["res.partner"]._fields
        for field_name in required:
            odoo_field = partner_fields.get(field_name)
            self.assertTrue(
                odoo_field.required,
                f"Field {field_name} is in 'required' but Odoo field is not required",
            )

    def test_readonly_or_computed_fields_marked(self):
        """Fields that are readonly or computed have readOnly: true."""
        schema = self.builder.build_schema(self.env["res.partner"])
        partner_fields = self.env["res.partner"]._fields
        for field_name, prop in schema["properties"].items():
            odoo_field = partner_fields.get(field_name)
            if odoo_field and (odoo_field.readonly or odoo_field.compute):
                self.assertTrue(
                    prop.get("readOnly"),
                    f"Field {field_name} (readonly={odoo_field.readonly}, "
                    f"compute={bool(odoo_field.compute)}) should have readOnly=true",
                )

    def test_title_from_field_string(self):
        """Each property has a 'title' taken from the Odoo field string."""
        schema = self.builder.build_schema(self.env["res.partner"])
        for fname, prop in schema["properties"].items():
            self.assertIn("title", prop, f"Property {fname} should have a title")

    def test_description_from_help(self):
        """Fields with help text have a 'description' property."""
        schema = self.builder.build_schema(self.env["res.partner"])
        partner_fields = self.env["res.partner"]._fields
        for fname, prop in schema["properties"].items():
            odoo_field = partner_fields.get(fname)
            if odoo_field and odoo_field.help:
                self.assertEqual(
                    prop.get("description"),
                    odoo_field.help,
                    f"Property {fname} description should match field help",
                )

    # ------------------------------------------------------------------
    # Vocabulary extraction edge cases
    # ------------------------------------------------------------------

    def test_dynamic_domain_does_not_crash(self):
        """A domain containing Python variable references returns None gracefully."""
        info = self.builder._extract_vocabulary_info_from_domain(
            "[('id', '!=', registrant_id)]",
            "spp.vocabulary.code",
        )
        self.assertIsNone(info)

    def test_empty_domain_returns_none(self):
        """An empty domain string returns None."""
        info = self.builder._extract_vocabulary_info_from_domain("", "spp.vocabulary.code")
        self.assertIsNone(info)

    def test_domain_without_namespace_returns_none(self):
        """A domain without namespace_uri returns None."""
        info = self.builder._extract_vocabulary_info_from_domain(
            "[('active', '=', True)]",
            "spp.vocabulary.code",
        )
        self.assertIsNone(info)
