# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCIVocabularyAdapter.

Maps OpenSPP vocabulary codes (gender, marital_status, relationship,
disability_type) to DCI standard namespaces. When spp.vocabulary.mapping
resolves a mapping, that wins; otherwise we fall back to hardcoded
lookup tables.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from .common import DCIServerCommon


def _fake_code(code=None, name=None, vocab_uri="urn:openspp:vocab:test"):
    """Build a duck-typed stand-in for spp.vocabulary.code."""
    rec = SimpleNamespace(
        code=code,
        name=name,
        vocabulary_id=SimpleNamespace(namespace_uri=vocab_uri),
    )
    return rec


@tagged("post_install", "-at_install")
class TestVocabularyAdapter(DCIServerCommon):
    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.services.vocabulary_adapter import (
            DCIVocabularyAdapter,
        )

        self.DCIVocabularyAdapter = DCIVocabularyAdapter
        self.adapter = DCIVocabularyAdapter(self.env)

    # --- mapping_model lazy load --------------------------------------------

    def test_mapping_model_returns_real_model_when_installed(self):
        # spp.vocabulary.mapping ships with spp_vocabulary which is a
        # dependency of spp_dci_server.
        if "spp.vocabulary.mapping" not in self.env:
            self.skipTest("spp.vocabulary.mapping not installed in this env")
        self.assertIsNotNone(self.adapter.mapping_model)
        # Idempotent: second access returns the cached value.
        self.assertIs(self.adapter.mapping_model, self.adapter._mapping_model)

    def test_mapping_model_none_when_not_installed(self):
        from odoo.addons.spp_dci_server.services.vocabulary_adapter import (
            DCIVocabularyAdapter,
        )

        adapter = DCIVocabularyAdapter(self.env)
        # Force the env-membership check to be False.
        with patch(
            "odoo.api.Environment.__contains__",
            return_value=False,
        ):
            self.assertIsNone(adapter.mapping_model)

    # --- gender mapping ------------------------------------------------------

    def test_map_gender_to_dci_via_mapping(self):
        """When the vocabulary mapping returns a target code, the adapter
        uses it verbatim."""
        target = SimpleNamespace(code="female")
        mock_mapping = MagicMock()
        mock_mapping.map_code.return_value = target
        with patch.object(
            self.DCIVocabularyAdapter,
            "mapping_model",
            mock_mapping,
        ):
            result = self.adapter.map_gender_to_dci(_fake_code(code="F"))
        self.assertEqual(result, "female")
        mock_mapping.map_code.assert_called_once()

    def test_map_gender_to_dci_falls_back_when_mapping_returns_none(self):
        mock_mapping = MagicMock()
        mock_mapping.map_code.return_value = None
        with patch.object(
            self.DCIVocabularyAdapter,
            "mapping_model",
            mock_mapping,
        ):
            result = self.adapter.map_gender_to_dci(_fake_code(code="m"))
        # Fallback table maps "m" -> "male"
        self.assertEqual(result, "male")

    def test_map_gender_to_dci_falls_back_when_mapping_raises(self):
        mock_mapping = MagicMock()
        mock_mapping.map_code.side_effect = RuntimeError("mapping fail")
        with patch.object(
            self.DCIVocabularyAdapter,
            "mapping_model",
            mock_mapping,
        ):
            result = self.adapter.map_gender_to_dci(_fake_code(code="female"))
        self.assertEqual(result, "female")

    def test_map_gender_to_dci_none_input(self):
        self.assertIsNone(self.adapter.map_gender_to_dci(None))

    def test_map_gender_from_string(self):
        self.assertEqual(self.adapter.map_gender_from_string("M"), "male")
        self.assertEqual(self.adapter.map_gender_from_string("Female"), "female")
        self.assertEqual(self.adapter.map_gender_from_string("3"), "other")
        # Unknown maps to "unknown"
        self.assertEqual(self.adapter.map_gender_from_string("zz"), "unknown")
        self.assertIsNone(self.adapter.map_gender_from_string(""))
        self.assertIsNone(self.adapter.map_gender_from_string(None))

    # --- marital status ------------------------------------------------------

    def test_map_marital_status_via_mapping(self):
        target = SimpleNamespace(code="W")
        mock_mapping = MagicMock()
        mock_mapping.map_code.return_value = target
        with patch.object(self.DCIVocabularyAdapter, "mapping_model", mock_mapping):
            self.assertEqual(
                self.adapter.map_marital_status_to_dci(_fake_code(code="WIDOW")),
                "W",
            )

    def test_map_marital_status_falls_back_to_table(self):
        mock_mapping = MagicMock()
        mock_mapping.map_code.return_value = None
        with patch.object(self.DCIVocabularyAdapter, "mapping_model", mock_mapping):
            self.assertEqual(
                self.adapter.map_marital_status_to_dci(_fake_code(code="married")),
                "M",
            )

    def test_map_marital_status_falls_back_when_raises(self):
        mock_mapping = MagicMock()
        mock_mapping.map_code.side_effect = ValueError("nope")
        with patch.object(self.DCIVocabularyAdapter, "mapping_model", mock_mapping):
            self.assertEqual(
                self.adapter.map_marital_status_to_dci(_fake_code(code="single")),
                "S",
            )

    def test_map_marital_status_none_input(self):
        self.assertIsNone(self.adapter.map_marital_status_to_dci(None))

    # --- relationship --------------------------------------------------------

    def test_map_relationship_via_mapping(self):
        target = SimpleNamespace(code="spouse")
        mock_mapping = MagicMock()
        mock_mapping.map_code.return_value = target
        with patch.object(self.DCIVocabularyAdapter, "mapping_model", mock_mapping):
            self.assertEqual(
                self.adapter.map_relationship_to_dci(_fake_code(code="husband")),
                "spouse",
            )

    def test_map_relationship_returns_raw_code_as_fallback(self):
        """No mapping match -> return the source code verbatim."""
        mock_mapping = MagicMock()
        mock_mapping.map_code.return_value = None
        with patch.object(self.DCIVocabularyAdapter, "mapping_model", mock_mapping):
            self.assertEqual(
                self.adapter.map_relationship_to_dci(_fake_code(code="cousin")),
                "cousin",
            )

    def test_map_relationship_handles_plain_string(self):
        self.assertEqual(self.adapter.map_relationship_to_dci("uncle"), "uncle")

    def test_map_relationship_none_input(self):
        self.assertIsNone(self.adapter.map_relationship_to_dci(None))

    # --- disability ----------------------------------------------------------

    def test_map_disability_via_mapping(self):
        target = SimpleNamespace(code="Vision")
        mock_mapping = MagicMock()
        mock_mapping.map_code.return_value = target
        with patch.object(self.DCIVocabularyAdapter, "mapping_model", mock_mapping):
            self.assertEqual(
                self.adapter.map_disability_type_to_dci(_fake_code(code="blindness")),
                "Vision",
            )

    def test_map_disability_returns_raw_code_as_fallback(self):
        mock_mapping = MagicMock()
        mock_mapping.map_code.return_value = None
        with patch.object(self.DCIVocabularyAdapter, "mapping_model", mock_mapping):
            self.assertEqual(
                self.adapter.map_disability_type_to_dci(_fake_code(code="hearing")),
                "hearing",
            )

    def test_map_disability_none_input(self):
        self.assertIsNone(self.adapter.map_disability_type_to_dci(None))

    # --- private fallback helpers --------------------------------------------

    def test_fallback_gender_via_name(self):
        # code is empty but name exists -> name lookup branch
        rec = SimpleNamespace(code=None, name="Female")
        self.assertEqual(self.adapter._fallback_gender_map(rec), "female")

    def test_fallback_gender_none_when_no_code_or_name(self):
        rec = SimpleNamespace(code=None, name=None)
        self.assertIsNone(self.adapter._fallback_gender_map(rec))

    def test_fallback_marital_status_via_name(self):
        rec = SimpleNamespace(code=None, name="divorced")
        self.assertEqual(self.adapter._fallback_marital_status_map(rec), "D")

    def test_fallback_marital_status_none_when_no_code_or_name(self):
        rec = SimpleNamespace(code=None, name=None)
        self.assertIsNone(self.adapter._fallback_marital_status_map(rec))
