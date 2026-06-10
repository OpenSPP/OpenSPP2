# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestFieldClassification(TransactionCase):
    """Tests for spp.field.classification model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Classification = cls.env["spp.field.classification"]
        cls.Level = cls.env["spp.data.classification.level"]

        # Get a model and field to test with
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.name_field = cls.env["ir.model.fields"].search(
            [
                ("model_id", "=", cls.partner_model.id),
                ("name", "=", "name"),
            ],
            limit=1,
        )
        cls.email_field = cls.env["ir.model.fields"].search(
            [
                ("model_id", "=", cls.partner_model.id),
                ("name", "=", "email"),
            ],
            limit=1,
        )

        cls.level_confidential = cls.env.ref("spp_data_classification.level_confidential")
        cls.level_restricted = cls.env.ref("spp_data_classification.level_restricted")

    def test_create_classification(self):
        """Test creating a field classification."""
        classification = self.Classification.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.name_field.id,
                "classification_id": self.level_confidential.id,
                "pii_category": "direct_id",
            }
        )

        self.assertTrue(classification)
        self.assertEqual(classification.model_name, "res.partner")
        self.assertEqual(classification.field_name, "name")

    @mute_logger("odoo.sql_db")
    def test_unique_constraint(self):
        """Test that each field can only have one classification."""
        # Use a different field to avoid conflicts with other tests
        phone_field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", self.partner_model.id),
                ("name", "=", "phone"),
            ],
            limit=1,
        )
        # Clean up any existing classification for this field
        self.Classification.search(
            [
                ("model_id", "=", self.partner_model.id),
                ("field_id", "=", phone_field.id),
            ]
        ).unlink()

        self.Classification.create(
            {
                "model_id": self.partner_model.id,
                "field_id": phone_field.id,
                "classification_id": self.level_confidential.id,
            }
        )

        with self.assertRaises(Exception) as cm:
            self.Classification.create(
                {
                    "model_id": self.partner_model.id,
                    "field_id": phone_field.id,
                    "classification_id": self.level_restricted.id,
                }
            )
        # Should be either ValidationError or IntegrityError
        self.assertTrue(
            isinstance(cm.exception, (ValidationError, IntegrityError)),
            f"Expected ValidationError or IntegrityError, got {type(cm.exception)}",
        )

    def test_get_classification(self):
        """Test get_classification method."""
        self.Classification.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.email_field.id,
                "classification_id": self.level_confidential.id,
            }
        )

        result = self.Classification.get_classification("res.partner", "email")
        self.assertTrue(result)
        self.assertEqual(result.classification_id, self.level_confidential)

        # Non-existent field
        result = self.Classification.get_classification("res.partner", "nonexistent")
        self.assertFalse(result)

    def test_get_model_classifications(self):
        """Test get_model_classifications method."""
        # Create multiple classifications
        self.Classification.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.name_field.id,
                "classification_id": self.level_confidential.id,
            }
        )
        self.Classification.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.email_field.id,
                "classification_id": self.level_confidential.id,
            }
        )

        results = self.Classification.get_model_classifications("res.partner")
        self.assertGreaterEqual(len(results), 2)

    def test_ensure_classification(self):
        """Test ensure_classification method."""
        # First call creates
        result1 = self.Classification.ensure_classification(
            "res.partner",
            "name",
            "CONFIDENTIAL",
            source="manual",
        )
        self.assertTrue(result1)

        # Second call returns existing
        result2 = self.Classification.ensure_classification(
            "res.partner",
            "name",
            "RESTRICTED",  # Different level - should be ignored
        )
        self.assertEqual(result1, result2)

    def test_get_fields_requiring_encryption(self):
        """Test get_fields_requiring_encryption method."""
        self.Classification.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.name_field.id,
                "classification_id": self.level_restricted.id,  # Requires encryption
            }
        )

        results = self.Classification.get_fields_requiring_encryption("res.partner")
        self.assertTrue(any(r.field_name == "name" for r in results))

    def test_is_pii_computed_and_searchable(self):
        """is_pii is True when a PII category is set, False otherwise, and searchable."""
        with_category = self.Classification.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.name_field.id,
                "classification_id": self.level_confidential.id,
                "pii_category": "direct_id",
            }
        )
        without_category = self.Classification.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.email_field.id,
                "classification_id": self.level_confidential.id,
            }
        )

        self.assertTrue(with_category.is_pii)
        self.assertFalse(without_category.is_pii)

        # Stored + searchable: the [("is_pii", "=", True)] domain (used by the
        # PII-encryption wizard and consent integration) must find it.
        found = self.Classification.search([("is_pii", "=", True)])
        self.assertIn(with_category, found)
        self.assertNotIn(without_category, found)
