# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestClassificationLevel(TransactionCase):
    """Tests for spp.data.classification.level model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Level = cls.env["spp.data.classification.level"]

        # Get default levels
        cls.level_public = cls.env.ref("spp_data_classification.level_public")
        cls.level_internal = cls.env.ref("spp_data_classification.level_internal")
        cls.level_confidential = cls.env.ref("spp_data_classification.level_confidential")
        cls.level_restricted = cls.env.ref("spp_data_classification.level_restricted")

    def test_default_levels_exist(self):
        """Test that default classification levels are created."""
        self.assertTrue(self.level_public)
        self.assertTrue(self.level_internal)
        self.assertTrue(self.level_confidential)
        self.assertTrue(self.level_restricted)

    def test_level_ordering(self):
        """Test that levels are ordered by sensitivity (sequence)."""
        self.assertLess(self.level_public.sequence, self.level_internal.sequence)
        self.assertLess(self.level_internal.sequence, self.level_confidential.sequence)
        self.assertLess(self.level_confidential.sequence, self.level_restricted.sequence)

    def test_get_level_by_code(self):
        """Test get_level_by_code method."""
        level = self.Level.get_level_by_code("RESTRICTED")
        self.assertEqual(level, self.level_restricted)

        level = self.Level.get_level_by_code("NONEXISTENT")
        self.assertFalse(level)

    def test_is_more_sensitive_than(self):
        """Test sensitivity comparison."""
        self.assertTrue(self.level_restricted.is_more_sensitive_than(self.level_confidential))
        self.assertTrue(self.level_confidential.is_more_sensitive_than(self.level_internal))
        self.assertFalse(self.level_internal.is_more_sensitive_than(self.level_confidential))
        # Any level is more sensitive than "no level at all"
        self.assertTrue(self.level_public.is_more_sensitive_than(self.Level.browse()))

    def test_policy_flags(self):
        """Test that policy flags are set correctly."""
        # Restricted requires encryption
        self.assertTrue(self.level_restricted.is_requires_encryption)
        self.assertTrue(self.level_restricted.is_requires_masking)
        self.assertTrue(self.level_restricted.is_requires_audit)

        # Public has minimal requirements
        self.assertFalse(self.level_public.is_requires_encryption)
        self.assertFalse(self.level_public.is_requires_masking)
        self.assertFalse(self.level_public.is_requires_audit)

    @mute_logger("odoo.sql_db")
    def test_unique_code_constraint(self):
        """Test that classification codes must be unique."""
        with self.assertRaises(Exception) as cm:
            self.Level.create(
                {
                    "name": "Duplicate",
                    "code": "PUBLIC",  # Already exists
                    "sequence": 100,
                }
            )
        # Should be either ValidationError or IntegrityError
        self.assertTrue(
            isinstance(cm.exception, (ValidationError, IntegrityError)),
            f"Expected ValidationError or IntegrityError, got {type(cm.exception)}",
        )

    def test_cannot_delete_used_level(self):
        """Test that levels in use cannot be deleted."""
        # Create a field classification using this level
        model = self.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        field = self.env["ir.model.fields"].search(
            [
                ("model_id", "=", model.id),
                ("name", "=", "name"),
            ],
            limit=1,
        )

        self.env["spp.field.classification"].create(
            {
                "model_id": model.id,
                "field_id": field.id,
                "classification_id": self.level_confidential.id,
            }
        )

        # Try to delete - should fail
        with self.assertRaises(UserError):
            self.level_confidential.unlink()
