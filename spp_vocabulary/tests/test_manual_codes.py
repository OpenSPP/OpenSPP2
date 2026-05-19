"""Manual codes on SYSTEM vocabularies (OP#954 round-3).

System vocabularies (`is_system=True`) ship immutable system codes via module
data files. Admins must still be able to layer their own *manual* codes
(`is_local=True`) on top — these are fully editable and deletable. This test
file covers the UI-facing additions:

- `code_source` Selection field is computed correctly from `is_local`.
- Manual codes can be created in a system vocab.
- Manual codes in a system vocab can be edited (identifying fields included)
  and deleted, without tripping the system-code guards.
- `action_add_manual_code` on `spp.vocabulary` returns an action whose context
  pre-seeds `default_is_local=True` and `default_vocabulary_id` for the form.
"""

from odoo.tests.common import TransactionCase


class TestManualCodesOnSystemVocabulary(TransactionCase):
    """Manual (is_local=True) codes on a system vocabulary stay fully editable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

        cls.system_vocab = cls.Vocabulary.create(
            {
                "name": "Manual-Code Host Vocab",
                "namespace_uri": "urn:test:manual-codes-host",
                "is_system": True,
            }
        )

    def test_code_source_computed_from_is_local(self):
        """code_source reflects is_local: True -> manual, False -> system."""
        system_code = self.VocabularyCode.with_context(_test_bypass_system_protection=True).create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "SYS_FOR_SOURCE",
                "display": "System For Source",
            }
        )
        manual_code = self.VocabularyCode.create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "MANUAL_FOR_SOURCE",
                "display": "Manual For Source",
                "is_local": True,
            }
        )

        self.assertEqual(system_code.code_source, "system")
        self.assertEqual(manual_code.code_source, "manual")

    def test_manual_code_create_allowed_on_system_vocab(self):
        """is_local=True codes can be created on a system vocabulary."""
        manual = self.VocabularyCode.create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "MANUAL_NEW",
                "display": "Manual New",
                "is_local": True,
            }
        )
        self.assertTrue(manual.id)
        self.assertTrue(manual.is_local)
        self.assertEqual(manual.code_source, "manual")

    def test_manual_code_identifying_fields_editable(self):
        """Manual codes keep `code`, `display`, `definition` writeable on a system vocab."""
        manual = self.VocabularyCode.create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "MANUAL_EDIT",
                "display": "Manual Edit",
                "is_local": True,
            }
        )
        manual.write(
            {
                "code": "MANUAL_EDIT_RENAMED",
                "display": "Manual Edit Renamed",
                "definition": "Edited definition",
            }
        )
        self.assertEqual(manual.code, "MANUAL_EDIT_RENAMED")
        self.assertEqual(manual.display, "Manual Edit Renamed")
        self.assertEqual(manual.definition, "Edited definition")

    def test_manual_code_can_be_deleted(self):
        """Manual codes on a system vocabulary can be unlinked."""
        manual = self.VocabularyCode.create(
            {
                "vocabulary_id": self.system_vocab.id,
                "code": "MANUAL_DEL",
                "display": "Manual Del",
                "is_local": True,
            }
        )
        manual_id = manual.id
        manual.unlink()
        self.assertFalse(self.VocabularyCode.search([("id", "=", manual_id)]))

    def test_action_add_manual_code_seeds_context(self):
        """action_add_manual_code returns an act_window with the right defaults."""
        action = self.system_vocab.action_add_manual_code()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.vocabulary.code")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["context"]["default_vocabulary_id"], self.system_vocab.id)
        self.assertTrue(action["context"]["default_is_local"])
