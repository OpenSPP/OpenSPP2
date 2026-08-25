# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the encrypted field mixin with spp_key_management integration."""

import base64
from unittest.mock import patch

from odoo import models
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase
from odoo.tools import config, mute_logger


class TestEncryptedFieldMixin(TransactionCase):
    """Tests for spp.encrypted.field.mixin."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Configure master key for key management
        # Set in odoo config (not ir.config_parameter) as required by key provider
        cls._original_master_key = config.get("spp_master_key")
        test_master_key = base64.b64encode(b"M" * 32).decode()
        config["spp_master_key"] = test_master_key

        # Set up default key provider
        existing_default = cls.env["spp.key.provider.registry"].search([("is_default", "=", True)])
        if not existing_default:
            cls.env["spp.key.provider.registry"].create(
                {
                    "name": "Test Default Provider",
                    "provider_type": "database",
                    "is_default": True,
                }
            )

        cls.Mixin = cls.env["spp.encrypted.field.mixin"]

    @classmethod
    def tearDownClass(cls):
        # Restore original master key configuration
        if cls._original_master_key:
            config["spp_master_key"] = cls._original_master_key
        elif "spp_master_key" in config.options:
            del config.options["spp_master_key"]
        super().tearDownClass()

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption are reversible."""
        mixin = self.Mixin

        plaintext = "123-456-789"
        field_name = "test_field"

        # Encrypt
        encrypted = mixin._encrypt_value(plaintext, field_name)
        self.assertIsNotNone(encrypted)
        self.assertNotEqual(encrypted, plaintext)

        # Decrypt
        decrypted = mixin._decrypt_value(encrypted, field_name)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_empty_value(self):
        """Test that empty values are handled correctly."""
        mixin = self.Mixin

        result = mixin._encrypt_value(None, "test_field")
        self.assertIsNone(result)

        result = mixin._encrypt_value("", "test_field")
        self.assertEqual(result, "")

    def test_blind_index_consistency(self):
        """Test that blind indexes are deterministic."""
        mixin = self.Mixin

        value = "123-456-789"
        field_name = "national_id"

        index1 = mixin._compute_blind_index(value, field_name)
        index2 = mixin._compute_blind_index(value, field_name)

        self.assertEqual(index1, index2)

    def test_blind_index_normalization(self):
        """Test that normalized values produce same index."""
        mixin = self.Mixin

        # These should produce the same index (exact matching)
        index1 = mixin._compute_blind_index("123-456-789", "test", "exact")
        index2 = mixin._compute_blind_index("123 456 789", "test", "exact")
        index3 = mixin._compute_blind_index("123.456.789", "test", "exact")

        self.assertEqual(index1, index2)
        self.assertEqual(index2, index3)

    def test_partial_index(self):
        """Test partial index (last N chars)."""
        mixin = self.Mixin

        normalized = mixin._normalize_for_index("123-456-7890", "partial")
        self.assertEqual(normalized, "7890")

    def test_soundex(self):
        """Test Soundex phonetic encoding."""
        mixin = self.Mixin

        # Same pronunciation should have same Soundex
        self.assertEqual(mixin._soundex("Robert"), mixin._soundex("Rupert"))
        self.assertEqual(mixin._soundex("Smith"), mixin._soundex("Smythe"))

        # Different names should have different Soundex (usually)
        self.assertNotEqual(mixin._soundex("Robert"), mixin._soundex("Michael"))

    def test_different_fields_different_encryption(self):
        """Test that same value encrypted for different fields is different."""
        mixin = self.Mixin

        plaintext = "same-value"

        encrypted1 = mixin._encrypt_value(plaintext, "field_a")
        encrypted2 = mixin._encrypt_value(plaintext, "field_b")

        # Different AAD means different ciphertext
        # (Actually the nonce makes them different anyway)
        self.assertNotEqual(encrypted1, encrypted2)

        # But both should decrypt to same value
        self.assertEqual(mixin._decrypt_value(encrypted1, "field_a"), plaintext)
        self.assertEqual(mixin._decrypt_value(encrypted2, "field_b"), plaintext)

    def test_get_encrypted_fields_default_empty(self):
        """With no configuration, the mixin reports no encrypted fields."""
        self.assertEqual(self.Mixin._get_encrypted_fields(), [])

    def test_get_index_type_defaults_to_exact(self):
        """An unconfigured field defaults to the 'exact' index type."""
        self.assertEqual(self.Mixin._get_index_type("national_id"), "exact")

    def test_normalize_phonetic_and_passthrough(self):
        """Phonetic normalization uses Soundex; unknown index types pass through."""
        mixin = self.Mixin
        self.assertEqual(
            mixin._normalize_for_index("Smith", "phonetic"),
            mixin._soundex("Smith"),
        )
        # An unrecognized index type returns the stripped value unchanged.
        self.assertEqual(mixin._normalize_for_index("  abc  ", "unknown"), "abc")

    def test_decrypt_invalid_returns_none(self):
        """Decrypting non-decryptable data fails gracefully and returns None."""
        with mute_logger("odoo.addons.spp_pii_encryption.models.encrypted_field_mixin"):
            self.assertIsNone(self.Mixin._decrypt_value("not-valid-ciphertext", "national_id"))

    def test_search_helpers_without_index_field(self):
        """Search helpers return an empty recordset when the index column is absent."""
        with mute_logger("odoo.addons.spp_pii_encryption.models.encrypted_field_mixin"):
            self.assertFalse(self.Mixin._search_by_blind_index("national_id", "123"))
            self.assertFalse(self.Mixin._search_by_partial("national_id", "0123"))

    def _mixin_with_index_fields(self):
        """Return a patcher exposing national_id blind-index fields on the mixin.

        The vals-preparation helper only checks field *presence* in
        ``self._fields``, so registering placeholder entries is enough to
        exercise the index-maintenance branches on the abstract mixin.
        """
        mixin_cls = type(self.Mixin)
        fields_map = dict(mixin_cls._fields)
        # Reuse a real Field object as placeholder in case anything iterates
        # the mapping while the patch is active.
        placeholder = next(iter(fields_map.values()))
        fields_map["national_id_index"] = placeholder
        fields_map["national_id_last4"] = placeholder
        return patch.object(mixin_cls, "_fields", fields_map)

    def test_apply_encryption_to_vals_encrypts_and_indexes(self):
        """Truthy values are encrypted and both blind indexes are computed."""
        mixin = self.Mixin
        plaintext = "123-456-7890"
        # Materialize key and salt records before patching _fields so no ORM
        # writes happen while the placeholder mapping is active.
        mixin._get_encryption_key("national_id")
        mixin._get_index_salt("national_id")

        with self._mixin_with_index_fields():
            vals = {"national_id": plaintext, "other": "untouched"}
            mixin._apply_encryption_to_vals(vals, ["national_id"])

        self.assertNotEqual(vals["national_id"], plaintext)
        self.assertEqual(mixin._decrypt_value(vals["national_id"], "national_id"), plaintext)
        self.assertEqual(
            vals["national_id_index"],
            mixin._compute_blind_index(plaintext, "national_id", "exact"),
        )
        self.assertEqual(
            vals["national_id_last4"],
            mixin._compute_blind_index(plaintext, "national_id", "partial"),
        )
        self.assertEqual(vals["other"], "untouched")

    def test_apply_encryption_to_vals_clears_stale_indexes(self):
        """Clearing an encrypted field must also clear its blind indexes.

        Otherwise the old HMAC hashes stay searchable after the PII itself
        has been removed.
        """
        mixin = self.Mixin
        for cleared in (False, "", None):
            with self._mixin_with_index_fields():
                vals = {"national_id": cleared}
                mixin._apply_encryption_to_vals(vals, ["national_id"])
            self.assertFalse(vals["national_id"])
            self.assertIn("national_id_index", vals)
            self.assertFalse(vals["national_id_index"])
            self.assertIn("national_id_last4", vals)
            self.assertFalse(vals["national_id_last4"])

    def _config_display_name_encryption(self):
        """Configure encryption on the mixin's own reflected display_name field.

        display_name is the only char field the abstract mixin exposes, so it
        is the one field a spp.field.encryption.config row can target without
        a concrete inheriting model.
        """
        model = self.env["ir.model"]._get("spp.encrypted.field.mixin")
        self.assertTrue(model, "abstract mixin should be reflected in ir.model")
        field = self.env["ir.model.fields"]._get("spp.encrypted.field.mixin", "display_name")
        self.assertTrue(field, "display_name should be reflected in ir.model.fields")
        return self.env["spp.field.encryption.config"].create(
            {
                "model_id": model.id,
                "field_id": field.id,
            }
        )

    def test_write_encrypts_via_db_config(self):
        """The write() override picks up spp.field.encryption.config rows.

        The whole config-lookup -> vals-encryption path runs through the real
        ORM override (write on an empty recordset is a no-op past that point).
        """
        cfg = self._config_display_name_encryption()
        self.assertEqual(cfg.model_name, "spp.encrypted.field.mixin")
        self.assertEqual(cfg.field_name, "display_name")

        self.assertEqual(self.Mixin._get_encrypted_fields(), ["display_name"])

        vals = {"display_name": "secret-123"}
        self.Mixin.browse().write(vals)
        self.assertNotEqual(vals["display_name"], "secret-123")
        self.assertEqual(
            self.Mixin._decrypt_value(vals["display_name"], "display_name"),
            "secret-123",
        )

    def test_create_encrypts_via_db_config(self):
        """create() encrypts configured fields in every vals dict."""
        self._config_display_name_encryption()
        mixin = self.Mixin
        # Materialize the key before patching so no key records are created
        # while BaseModel.create is mocked out.
        mixin._get_encryption_key("display_name")

        vals_list = [{"display_name": "secret-A"}, {"display_name": ""}]
        with patch.object(models.BaseModel, "create", return_value=mixin.browse()):
            mixin.create(vals_list)

        self.assertNotEqual(vals_list[0]["display_name"], "secret-A")
        self.assertEqual(
            mixin._decrypt_value(vals_list[0]["display_name"], "display_name"),
            "secret-A",
        )
        # Falsy values are passed through unencrypted.
        self.assertEqual(vals_list[1]["display_name"], "")

    def test_read_decrypts_via_db_config(self):
        """read() decrypts configured fields and leaves other data as-is."""
        self._config_display_name_encryption()
        mixin = self.Mixin
        encrypted = mixin._encrypt_value("secret-R", "display_name")

        fake_rows = [
            {"id": 1, "display_name": encrypted},
            {"id": 2, "display_name": "not-ciphertext"},
            {"id": 3, "display_name": False},
        ]
        with (
            patch.object(models.BaseModel, "read", return_value=fake_rows),
            mute_logger("odoo.addons.spp_pii_encryption.models.encrypted_field_mixin"),
        ):
            # Keyword call mirrors core callers like res.users read(fields=...)
            result = mixin.browse().read(fields=["display_name"])

        self.assertEqual(result[0]["display_name"], "secret-R")
        # Undecryptable data is left as-is (backwards compatibility with
        # plaintext rows that predate encryption).
        self.assertEqual(result[1]["display_name"], "not-ciphertext")
        self.assertFalse(result[2]["display_name"])

    def test_read_skips_unrequested_encrypted_fields(self):
        """read() leaves the result untouched when no encrypted field is requested."""
        self._config_display_name_encryption()
        fake_rows = [{"id": 1, "create_date": "2020-01-01"}]
        with patch.object(models.BaseModel, "read", return_value=fake_rows):
            result = self.Mixin.browse().read(["create_date"])
        self.assertEqual(result, [{"id": 1, "create_date": "2020-01-01"}])

    def test_search_by_blind_index_builds_hashed_domain(self):
        """_search_by_blind_index searches on the HMAC, never the plaintext."""
        mixin = self.Mixin
        mixin._get_index_salt("national_id")  # materialize salt pre-patch
        expected = mixin._compute_blind_index("123-456-7890", "national_id", "exact")

        with (
            self._mixin_with_index_fields(),
            patch.object(type(mixin), "search", return_value=mixin.browse()) as mock_search,
        ):
            result = mixin._search_by_blind_index("national_id", "123-456-7890")

        self.assertFalse(result)
        mock_search.assert_called_once_with([("national_id_index", "=", expected)])

    def test_search_by_partial_builds_hashed_domain(self):
        """_search_by_partial hashes the search value before searching."""
        mixin = self.Mixin
        mixin._get_index_salt("national_id")
        expected = mixin._compute_blind_index("7890", "national_id", "partial")

        with (
            self._mixin_with_index_fields(),
            patch.object(type(mixin), "search", return_value=mixin.browse()) as mock_search,
        ):
            result = mixin._search_by_partial("national_id", "7890")

        self.assertFalse(result)
        mock_search.assert_called_once_with([("national_id_last4", "=", expected)])

    def test_encrypt_value_failure_raises_sanitized_error(self):
        """Encryption failures raise a UserError without crypto internals."""
        mixin = self.Mixin
        with (
            mute_logger("odoo.addons.spp_pii_encryption.models.encrypted_field_mixin"),
            patch.object(type(mixin), "_get_encryption_key", side_effect=RuntimeError("boom")),
            self.assertRaises(UserError) as cm,
        ):
            mixin._encrypt_value("x", "national_id")
        self.assertNotIn("boom", str(cm.exception))
        self.assertIn("national_id", str(cm.exception))

    def test_encrypt_value_propagates_access_error(self):
        """A missing key permission surfaces as AccessError, not a crypto error."""
        mixin = self.Mixin
        with (
            patch.object(type(mixin), "_get_encryption_key", side_effect=AccessError("no key for you")),
            self.assertRaises(AccessError),
        ):
            mixin._encrypt_value("x", "national_id")

    def test_soundex_empty_value(self):
        """Empty input yields the neutral Soundex code."""
        self.assertEqual(self.Mixin._soundex(""), "0000")

    def test_apply_encryption_to_vals_untouched_field_stays_untouched(self):
        """A field absent from vals is left alone entirely."""
        mixin = self.Mixin
        with self._mixin_with_index_fields():
            vals = {"other": "abc"}
            mixin._apply_encryption_to_vals(vals, ["national_id"])
        self.assertEqual(vals, {"other": "abc"})
