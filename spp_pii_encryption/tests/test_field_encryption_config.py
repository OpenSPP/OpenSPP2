# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.field.encryption.config (UI-based encryption configuration)."""

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestFieldEncryptionConfig(TransactionCase):
    """Public helpers and constraints of the field-encryption config model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env["spp.field.encryption.config"]
        cls.partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")], limit=1)
        cls.name_field = cls.env["ir.model.fields"].search(
            [("model_id", "=", cls.partner_model.id), ("name", "=", "name")],
            limit=1,
        )
        # A non char/text field to exercise the type constraint.
        cls.bool_field = cls.env["ir.model.fields"].search(
            [("model_id", "=", cls.partner_model.id), ("ttype", "=", "boolean")],
            limit=1,
        )

    def test_create_computes_and_helpers(self):
        cfg = self.Config.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.name_field.id,
                "encryption_enabled": True,
                "blind_index_enabled": True,
                "index_type": "exact",
            }
        )
        self.assertEqual(cfg.model_name, "res.partner")
        self.assertEqual(cfg.field_name, "name")
        self.assertEqual(cfg.display_name, "res.partner.name")
        self.assertEqual(cfg.index_field_name, "name_index")

        self.assertIn("name", self.Config.get_encrypted_fields("res.partner"))
        self.assertTrue(self.Config.is_field_encrypted("res.partner", "name"))
        self.assertEqual(self.Config.get_index_type("res.partner", "name"), "exact")
        self.assertEqual(self.Config.get_field_config("res.partner", "name"), cfg)

    def test_index_field_name_partial(self):
        cfg = self.Config.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.name_field.id,
                "index_type": "partial",
            }
        )
        self.assertEqual(cfg.index_field_name, "name_last4")

    def test_disabled_blind_index_has_no_index_type(self):
        self.Config.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.name_field.id,
                "blind_index_enabled": False,
            }
        )
        self.assertIsNone(self.Config.get_index_type("res.partner", "name"))

    def test_toggle_actions(self):
        cfg = self.Config.create(
            {
                "model_id": self.partner_model.id,
                "field_id": self.name_field.id,
            }
        )
        before_enc = cfg.encryption_enabled
        cfg.action_toggle_encryption()
        self.assertNotEqual(cfg.encryption_enabled, before_enc)

        before_bi = cfg.blind_index_enabled
        cfg.action_toggle_blind_index()
        self.assertNotEqual(cfg.blind_index_enabled, before_bi)

    def test_non_text_field_rejected(self):
        with self.assertRaises(ValidationError):
            self.Config.create(
                {
                    "model_id": self.partner_model.id,
                    "field_id": self.bool_field.id,
                }
            )

    def test_size_limited_field_rejected(self):
        """Char fields with a size limit would silently truncate ciphertext."""
        country_model = self.env["ir.model"]._get("res.country")
        code_field = self.env["ir.model.fields"]._get("res.country", "code")
        self.assertTrue(code_field.size, "res.country.code should have a size limit")
        with self.assertRaises(ValidationError):
            self.Config.create(
                {
                    "model_id": country_model.id,
                    "field_id": code_field.id,
                }
            )

    def test_translated_field_rejected(self):
        """Translated fields store per-language values and cannot be encrypted."""
        country_model = self.env["ir.model"]._get("res.country")
        name_field = self.env["ir.model.fields"]._get("res.country", "name")
        self.assertTrue(name_field.translate, "res.country.name should be translatable")
        with self.assertRaises(ValidationError):
            self.Config.create(
                {
                    "model_id": country_model.id,
                    "field_id": name_field.id,
                }
            )
