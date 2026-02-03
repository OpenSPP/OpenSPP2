"""Tests for relation versioning strategies."""

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestRelationVersioning(TransactionCase):
    """Test cases for relation versioning strategies."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ArtifactVersion = cls.env["spp.artifact.version"]
        cls.Partner = cls.env["res.partner"]
        cls.Country = cls.env["res.country"]
        cls.PartnerCategory = cls.env["res.partner.category"]

    def test_parse_field_spec_string(self):
        """Test parsing simple string field spec."""
        partner = self.Partner.create({"name": "Test Partner"})
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test",
            }
        )
        field_name, options = version._parse_field_spec("name")
        self.assertEqual(field_name, "name")
        self.assertEqual(options["strategy"], "shallow")

    def test_parse_field_spec_tuple_strategy(self):
        """Test parsing tuple with strategy string."""
        partner = self.Partner.create({"name": "Test Partner"})
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test",
            }
        )
        field_name, options = version._parse_field_spec(("category_id", "embed"))
        self.assertEqual(field_name, "category_id")
        self.assertEqual(options["strategy"], "embed")

    def test_parse_field_spec_tuple_options(self):
        """Test parsing tuple with options dict."""
        partner = self.Partner.create({"name": "Test Partner"})
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test",
            }
        )
        field_name, options = version._parse_field_spec(("tag_ids", {"strategy": "embed", "fields": ["name", "code"]}))
        self.assertEqual(field_name, "tag_ids")
        self.assertEqual(options["strategy"], "embed")
        self.assertEqual(options["fields"], ["name", "code"])

    def test_shallow_strategy_many2one(self):
        """Test shallow strategy for Many2one field."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        partner.write({"country_id": country.id})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test shallow",
            }
        )

        snapshot = version._serialize_snapshot(partner, ["name", "country_id"])
        self.assertEqual(snapshot["country_id"], country.id)

    def test_shallow_strategy_many2many(self):
        """Test shallow strategy for Many2many field."""
        partner = self.Partner.create({"name": "Test Partner"})
        tag1 = self.PartnerCategory.create({"name": "Tag 1"})
        tag2 = self.PartnerCategory.create({"name": "Tag 2"})
        partner.write({"category_id": [Command.set([tag1.id, tag2.id])]})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test shallow m2m",
            }
        )

        snapshot = version._serialize_snapshot(partner, ["name", "category_id"])
        self.assertEqual(snapshot["category_id"], [tag1.id, tag2.id])

    def test_embed_strategy_many2one(self):
        """Test embed strategy for Many2one field."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        partner.write({"country_id": country.id})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test embed",
            }
        )

        snapshot = version._serialize_snapshot(partner, [("country_id", "embed")])
        self.assertIn("_ref", snapshot["country_id"])
        self.assertIn("_data", snapshot["country_id"])
        self.assertEqual(snapshot["country_id"]["_ref"], country.id)
        self.assertIn("name", snapshot["country_id"]["_data"])
        self.assertEqual(snapshot["country_id"]["_data"]["name"], "United States")

    def test_embed_strategy_many2one_with_custom_fields(self):
        """Test embed strategy with custom field list."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        partner.write({"country_id": country.id})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test embed custom",
            }
        )

        snapshot = version._serialize_snapshot(
            partner, [("country_id", {"strategy": "embed", "fields": ["name", "code"]})]
        )
        self.assertEqual(snapshot["country_id"]["_ref"], country.id)
        self.assertIn("name", snapshot["country_id"]["_data"])
        self.assertIn("code", snapshot["country_id"]["_data"])

    def test_embed_strategy_many2many(self):
        """Test embed strategy for Many2many field."""
        partner = self.Partner.create({"name": "Test Partner"})
        tag1 = self.PartnerCategory.create({"name": "Tag 1"})
        tag2 = self.PartnerCategory.create({"name": "Tag 2"})
        partner.write({"category_id": [Command.set([tag1.id, tag2.id])]})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test embed m2m",
            }
        )

        snapshot = version._serialize_snapshot(partner, [("category_id", "embed")])
        self.assertIn("_refs", snapshot["category_id"])
        self.assertIn("_data", snapshot["category_id"])
        self.assertEqual(snapshot["category_id"]["_refs"], [tag1.id, tag2.id])
        self.assertEqual(len(snapshot["category_id"]["_data"]), 2)
        self.assertEqual(snapshot["category_id"]["_data"][0]["name"], "Tag 1")
        self.assertEqual(snapshot["category_id"]["_data"][1]["name"], "Tag 2")

    def test_deserialize_shallow(self):
        """Test deserializing shallow strategy."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        partner.write({"country_id": country.id})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test deserialize",
            }
        )

        snapshot = version._serialize_snapshot(partner, ["name", "country_id"])
        values = version._deserialize_snapshot(partner, snapshot, ["name", "country_id"])
        self.assertEqual(values["country_id"], country.id)

    def test_deserialize_embed_existing_record(self):
        """Test deserializing embed strategy when record still exists."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        partner.write({"country_id": country.id})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test deserialize embed",
            }
        )

        snapshot = version._serialize_snapshot(partner, [("country_id", "embed")])
        values = version._deserialize_snapshot(partner, snapshot, [("country_id", "embed")])
        self.assertEqual(values["country_id"], country.id)

    def test_deserialize_embed_deleted_record(self):
        """Test deserializing embed strategy when record is deleted."""
        partner = self.Partner.create({"name": "Test Partner"})
        category = self.PartnerCategory.create({"name": "Temp Category"})
        partner.write({"category_id": [Command.set([category.id])]})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test deleted embed",
            }
        )

        snapshot = version._serialize_snapshot(partner, [("category_id", "embed")])
        category.unlink()

        values = version._deserialize_snapshot(partner, snapshot, [("category_id", "embed")])
        self.assertEqual(values["category_id"], [])

    def test_record_exists_helper(self):
        """Test _record_exists helper method."""
        partner = self.Partner.create({"name": "Test Partner"})
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test exists",
            }
        )

        self.assertTrue(version._record_exists("res.partner", partner.id))
        self.assertFalse(version._record_exists("res.partner", 999999999))
        self.assertFalse(version._record_exists("res.partner", False))

    def test_get_embed_fields_default(self):
        """Test _get_embed_fields with default behavior."""
        partner = self.Partner.create({"name": "Test Partner"})
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test embed fields",
            }
        )

        field = partner._fields["country_id"]
        embed_fields = version._get_embed_fields(field, {})
        self.assertIn("name", embed_fields)
        self.assertIn("code", embed_fields)

    def test_get_embed_fields_custom(self):
        """Test _get_embed_fields with custom fields."""
        partner = self.Partner.create({"name": "Test Partner"})
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test custom embed fields",
            }
        )

        field = partner._fields["country_id"]
        options = {"fields": ["name", "phone_code"]}
        embed_fields = version._get_embed_fields(field, options)
        self.assertEqual(embed_fields, ["name", "phone_code"])

    def test_backward_compatibility_string_specs(self):
        """Test that existing string-based field specs still work."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        partner.write({"country_id": country.id})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test backward compat",
            }
        )

        snapshot = version._serialize_snapshot(partner, ["name", "country_id"])
        self.assertEqual(snapshot["name"], "Test Partner")
        self.assertEqual(snapshot["country_id"], country.id)

    def test_mixed_field_specs(self):
        """Test mixing string and tuple field specs."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        tag1 = self.PartnerCategory.create({"name": "Tag 1"})
        partner.write({"country_id": country.id, "category_id": [Command.set([tag1.id])]})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test mixed specs",
            }
        )

        snapshot = version._serialize_snapshot(
            partner,
            [
                "name",
                ("country_id", "embed"),
                ("category_id", {"strategy": "embed", "fields": ["name"]}),
            ],
        )

        self.assertEqual(snapshot["name"], "Test Partner")
        self.assertIn("_ref", snapshot["country_id"])
        self.assertIn("_data", snapshot["country_id"])
        self.assertIn("_refs", snapshot["category_id"])
        self.assertIn("_data", snapshot["category_id"])

    def test_follow_strategy_fallback_to_shallow(self):
        """Test follow strategy falls back to shallow for non-versioned models."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        partner.write({"country_id": country.id})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test follow fallback",
            }
        )

        # res.country doesn't inherit from spp.versioned.mixin
        # So follow should fall back to shallow (just store ID)
        snapshot = version._serialize_snapshot(partner, [("country_id", "follow")])
        # Should store just the ID since country doesn't support versioning
        self.assertEqual(snapshot["country_id"], country.id)

    def test_follow_strategy_many2many_fallback(self):
        """Test follow strategy for Many2many falls back to shallow."""
        partner = self.Partner.create({"name": "Test Partner"})
        tag1 = self.PartnerCategory.create({"name": "Tag 1"})
        tag2 = self.PartnerCategory.create({"name": "Tag 2"})
        partner.write({"category_id": [Command.set([tag1.id, tag2.id])]})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test follow m2m fallback",
            }
        )

        # res.partner.category doesn't support versioning
        snapshot = version._serialize_snapshot(partner, [("category_id", "follow")])
        # Should return dict with refs and version_ids (with False for non-versioned)
        self.assertIn("_refs", snapshot["category_id"])
        self.assertIn("_version_ids", snapshot["category_id"])
        self.assertEqual(snapshot["category_id"]["_refs"], [tag1.id, tag2.id])
        # Version IDs should be False since category doesn't support versioning
        self.assertEqual(snapshot["category_id"]["_version_ids"], [False, False])

    def test_metadata_stored_in_snapshot(self):
        """Test that field specs metadata is stored in snapshot."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        partner.write({"country_id": country.id})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test metadata",
            }
        )

        field_specs = ["name", ("country_id", "embed")]
        snapshot = version._serialize_snapshot(partner, field_specs)

        # Metadata should be stored
        self.assertIn("_meta", snapshot)
        self.assertIn("field_specs", snapshot["_meta"])
        # Tuples converted to lists for JSON
        self.assertEqual(snapshot["_meta"]["field_specs"], ["name", ["country_id", "embed"]])

    def test_deserialize_uses_stored_metadata(self):
        """Test that deserialization uses stored field specs from metadata."""
        partner = self.Partner.create({"name": "Test Partner"})
        country = self.env.ref("base.us")
        partner.write({"country_id": country.id})

        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test metadata deserialize",
            }
        )

        field_specs = ["name", ("country_id", "embed")]
        snapshot = version._serialize_snapshot(partner, field_specs)

        # Deserialize without passing field_specs - should use stored metadata
        values = version._deserialize_snapshot(partner, snapshot)
        self.assertEqual(values["name"], "Test Partner")
        self.assertEqual(values["country_id"], country.id)

    def test_invalid_field_spec_raises_error(self):
        """Test that invalid field specs raise ValidationError."""
        from odoo.exceptions import ValidationError

        partner = self.Partner.create({"name": "Test Partner"})
        version = self.ArtifactVersion.create(
            {
                "model": "res.partner",
                "res_id": partner.id,
                "version": 1,
                "change_summary": "Test invalid spec",
            }
        )

        # Invalid spec (not string or tuple)
        with self.assertRaises(ValidationError):
            version._parse_field_spec(123)

        with self.assertRaises(ValidationError):
            version._parse_field_spec(["name"])  # List instead of tuple
