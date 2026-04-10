# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for pack vocabulary provisioning.

Tests cover:
- Model creation and constraints
- Installation wizard vocabulary/concept provisioning
- Idempotency (re-install cycles)
- Error handling (unresolvable URIs, system vocab constraints)
- ACL enforcement
"""

import logging

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestPackVocabularyModels(TransactionCase):
    """Tests for pack vocabulary model creation and constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Pack = cls.env["spp.studio.pack"]
        cls.PackVocab = cls.env["spp.studio.pack.vocabulary"]
        cls.PackVocabCode = cls.env["spp.studio.pack.vocabulary.code"]
        cls.PackConcept = cls.env["spp.studio.pack.concept"]
        cls.PackConceptCode = cls.env["spp.studio.pack.concept.code"]
        cls.Vocabulary = cls.env["spp.vocabulary"]

        # Create a test pack
        cls.test_pack = cls.Pack.create(
            {
                "name": "Test Vocab Pack",
                "code": "test_vocab_pack",
                "category": "other",
                "version": "1.0",
                "author": "Test",
            }
        )

        # Create a non-system vocabulary for testing
        cls.test_vocab = cls.Vocabulary.create(
            {
                "name": "Test Vocabulary",
                "namespace_uri": "urn:test:pack-vocab-test",
                "domain": "core",
            }
        )

        # Create a system vocabulary for testing
        cls.system_vocab = cls.Vocabulary.create(
            {
                "name": "Test System Vocabulary",
                "namespace_uri": "urn:test:pack-vocab-system",
                "domain": "core",
                "is_system": True,
            }
        )

    def test_pack_vocabulary_item_add_codes_mode(self):
        """Pack vocabulary item can target an existing vocabulary."""
        vocab_item = self.PackVocab.create(
            {
                "pack_id": self.test_pack.id,
                "name": "Add test codes",
                "vocabulary_id": self.test_vocab.id,
            }
        )
        self.assertTrue(vocab_item)
        self.assertEqual(vocab_item.get_target_vocabulary(), self.test_vocab)

    def test_pack_vocabulary_item_create_new_mode(self):
        """Pack vocabulary item can define a new vocabulary."""
        vocab_item = self.PackVocab.create(
            {
                "pack_id": self.test_pack.id,
                "name": "New vocab",
                "new_vocabulary_name": "Crop Types",
                "new_vocabulary_namespace": "urn:test:crop-types",
                "new_vocabulary_domain": "agriculture",
            }
        )
        self.assertTrue(vocab_item)
        self.assertFalse(vocab_item.vocabulary_id)

    def test_pack_vocabulary_item_mutual_exclusion_both_set(self):
        """Cannot set both vocabulary_id and new_vocabulary_* fields."""
        with self.assertRaises(ValidationError):
            self.PackVocab.create(
                {
                    "pack_id": self.test_pack.id,
                    "name": "Invalid",
                    "vocabulary_id": self.test_vocab.id,
                    "new_vocabulary_name": "Conflict",
                    "new_vocabulary_namespace": "urn:test:conflict",
                }
            )

    def test_pack_vocabulary_item_mutual_exclusion_neither_set(self):
        """Must set either vocabulary_id or new_vocabulary_* fields."""
        with self.assertRaises(ValidationError):
            self.PackVocab.create(
                {
                    "pack_id": self.test_pack.id,
                    "name": "Invalid",
                }
            )

    def test_pack_vocabulary_item_new_mode_requires_both_fields(self):
        """New vocabulary mode requires both name and namespace."""
        with self.assertRaises(ValidationError):
            self.PackVocab.create(
                {
                    "pack_id": self.test_pack.id,
                    "name": "Invalid",
                    "new_vocabulary_namespace": "urn:test:no-name",
                }
            )

    def test_pack_vocabulary_code_creation(self):
        """Pack vocabulary codes can be created."""
        vocab_item = self.PackVocab.create(
            {
                "pack_id": self.test_pack.id,
                "name": "Test codes",
                "vocabulary_id": self.test_vocab.id,
            }
        )
        code = self.PackVocabCode.create(
            {
                "vocabulary_item_id": vocab_item.id,
                "code": "test_code",
                "display": "Test Code",
                "definition": "A test code",
                "sequence": 20,
            }
        )
        self.assertTrue(code)
        self.assertEqual(vocab_item.code_count, 1)

    def test_system_vocabulary_requires_is_local(self):
        """Codes targeting system vocabularies must have is_local=True."""
        vocab_item = self.PackVocab.create(
            {
                "pack_id": self.test_pack.id,
                "name": "System vocab codes",
                "vocabulary_id": self.system_vocab.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.PackVocabCode.create(
                {
                    "vocabulary_item_id": vocab_item.id,
                    "code": "test_sys",
                    "display": "Test System",
                    "is_local": False,
                }
            )

    def test_system_vocabulary_with_is_local(self):
        """Codes targeting system vocabularies with is_local=True are accepted."""
        vocab_item = self.PackVocab.create(
            {
                "pack_id": self.test_pack.id,
                "name": "System vocab codes local",
                "vocabulary_id": self.system_vocab.id,
            }
        )
        code = self.PackVocabCode.create(
            {
                "vocabulary_item_id": vocab_item.id,
                "code": "test_sys_local",
                "display": "Test System Local",
                "is_local": True,
            }
        )
        self.assertTrue(code)

    def test_pack_concept_creation(self):
        """Pack concept groups can be created with code references."""
        concept = self.PackConcept.create(
            {
                "pack_id": self.test_pack.id,
                "name": "test_concept",
                "label": "Test Concept",
                "cel_function": "is_test",
                "target_field": "test_field",
            }
        )
        code_ref = self.PackConceptCode.create(
            {
                "concept_id": concept.id,
                "uri": "urn:test:pack-vocab-test#some_code",
            }
        )
        self.assertTrue(concept)
        self.assertTrue(code_ref)
        self.assertEqual(len(concept.code_ref_ids), 1)

    def test_pack_vocabulary_count_and_concept_count(self):
        """Pack vocabulary_count and concept_count are computed correctly."""
        pack = self.Pack.create(
            {
                "name": "Count Test Pack",
                "code": "count_test_pack",
                "category": "other",
                "version": "1.0",
                "author": "Test",
            }
        )
        self.assertEqual(pack.vocabulary_count, 0)
        self.assertEqual(pack.concept_count, 0)

        self.PackVocab.create(
            {
                "pack_id": pack.id,
                "name": "Vocab 1",
                "vocabulary_id": self.test_vocab.id,
            }
        )
        pack.invalidate_recordset(["vocabulary_count"])
        self.assertEqual(pack.vocabulary_count, 1)

        self.PackConcept.create(
            {
                "pack_id": pack.id,
                "name": "concept_1",
                "label": "Concept 1",
                "cel_function": "is_c1",
            }
        )
        pack.invalidate_recordset(["concept_count"])
        self.assertEqual(pack.concept_count, 1)


@tagged("post_install", "-at_install")
class TestPackVocabularyInstallation(TransactionCase):
    """Tests for vocabulary provisioning during pack installation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Pack = cls.env["spp.studio.pack"]
        cls.PackVocab = cls.env["spp.studio.pack.vocabulary"]
        cls.PackVocabCode = cls.env["spp.studio.pack.vocabulary.code"]
        cls.PackConcept = cls.env["spp.studio.pack.concept"]
        cls.PackConceptCode = cls.env["spp.studio.pack.concept.code"]
        cls.Vocabulary = cls.env["spp.vocabulary"]
        cls.VocabCode = cls.env["spp.vocabulary.code"]
        cls.ConceptGroup = cls.env["spp.vocabulary.concept.group"]
        cls.Wizard = cls.env["spp.studio.pack.install.wizard"]

        # Create a non-system vocabulary
        cls.test_vocab = cls.Vocabulary.create(
            {
                "name": "Install Test Vocabulary",
                "namespace_uri": "urn:test:install-vocab",
                "domain": "core",
            }
        )

        # Create a system vocabulary with a code via XML-loading context
        cls.system_vocab = cls.Vocabulary.create(
            {
                "name": "Install System Vocabulary",
                "namespace_uri": "urn:test:install-system",
                "domain": "core",
                "is_system": True,
            }
        )
        cls.system_code = cls.VocabCode.with_context(install_xmlid=True).create(
            {
                "vocabulary_id": cls.system_vocab.id,
                "code": "existing_sys",
                "display": "Existing System Code",
            }
        )

    def _create_pack_with_vocab(self, pack_code, vocab_items=None, concept_items=None, logic_items=None):
        """Helper to create a pack with vocabulary items."""
        pack = self.Pack.create(
            {
                "name": f"Test Pack {pack_code}",
                "code": pack_code,
                "category": "other",
                "version": "1.0",
                "author": "Test",
            }
        )

        if vocab_items:
            for vi in vocab_items:
                codes = vi.pop("codes", [])
                vi["pack_id"] = pack.id
                vocab_item = self.PackVocab.create(vi)
                for code_vals in codes:
                    code_vals["vocabulary_item_id"] = vocab_item.id
                    self.PackVocabCode.create(code_vals)

        if concept_items:
            for ci in concept_items:
                code_refs = ci.pop("code_refs", [])
                ci["pack_id"] = pack.id
                concept = self.PackConcept.create(ci)
                for uri in code_refs:
                    self.PackConceptCode.create({"concept_id": concept.id, "uri": uri})

        if logic_items:
            PackItem = self.env["spp.studio.pack.item"]
            for li in logic_items:
                li["pack_id"] = pack.id
                PackItem.create(li)

        return pack

    def _install_pack(self, pack):
        """Helper to run the install wizard on a pack."""
        wizard = self.Wizard.create({"pack_id": pack.id})
        wizard.action_install()
        return wizard

    def test_install_adds_codes_to_existing_vocabulary(self):
        """Install wizard adds codes to an existing vocabulary."""
        pack = self._create_pack_with_vocab(
            "install_add_codes",
            vocab_items=[
                {
                    "name": "Add codes",
                    "vocabulary_id": self.test_vocab.id,
                    "codes": [
                        {"code": "add_test_1", "display": "Added Code 1"},
                        {"code": "add_test_2", "display": "Added Code 2"},
                    ],
                }
            ],
        )

        wizard = self._install_pack(pack)

        # Verify codes were created
        code1 = self.VocabCode.search([("namespace_uri", "=", "urn:test:install-vocab"), ("code", "=", "add_test_1")])
        code2 = self.VocabCode.search([("namespace_uri", "=", "urn:test:install-vocab"), ("code", "=", "add_test_2")])
        self.assertTrue(code1)
        self.assertTrue(code2)
        self.assertEqual(code1.display, "Added Code 1")

        # Verify tracking references
        vocab_item = pack.vocabulary_ids[0]
        for code_item in vocab_item.code_ids:
            self.assertTrue(code_item.installed_code_id)
            self.assertTrue(code_item.is_installed)

        # Verify pack is installed
        self.assertEqual(pack.state, "installed")
        self.assertIn("Vocabulary codes provisioned: 2", wizard.result_message)

    def test_install_creates_new_vocabulary(self):
        """Install wizard creates a new vocabulary with codes."""
        pack = self._create_pack_with_vocab(
            "install_new_vocab",
            vocab_items=[
                {
                    "name": "New crop vocab",
                    "new_vocabulary_name": "Crop Types",
                    "new_vocabulary_namespace": "urn:test:crop-types-install",
                    "new_vocabulary_domain": "agriculture",
                    "codes": [
                        {"code": "rice", "display": "Rice", "sequence": 1},
                        {"code": "maize", "display": "Maize", "sequence": 2},
                    ],
                }
            ],
        )

        wizard = self._install_pack(pack)

        # Verify vocabulary was created
        new_vocab = self.Vocabulary.search([("namespace_uri", "=", "urn:test:crop-types-install")])
        self.assertTrue(new_vocab)
        self.assertEqual(new_vocab.name, "Crop Types")
        self.assertEqual(new_vocab.domain, "agriculture")

        # Verify codes
        codes = self.VocabCode.search([("namespace_uri", "=", "urn:test:crop-types-install")])
        self.assertEqual(len(codes), 2)

        # Verify tracking
        vocab_item = pack.vocabulary_ids[0]
        self.assertEqual(vocab_item.installed_vocabulary_id, new_vocab)
        self.assertTrue(vocab_item.is_installed)

        self.assertIn("Vocabularies created: 1", wizard.result_message)

    def test_install_system_vocabulary_local_codes(self):
        """Install wizard creates local codes for system vocabularies."""
        pack = self._create_pack_with_vocab(
            "install_sys_local",
            vocab_items=[
                {
                    "name": "Local sys codes",
                    "vocabulary_id": self.system_vocab.id,
                    "codes": [
                        {
                            "code": "local_ext_1",
                            "display": "Local Extension 1",
                            "is_local": True,
                        },
                    ],
                }
            ],
        )

        self._install_pack(pack)

        # Verify code was created as local
        code = self.VocabCode.search([("namespace_uri", "=", "urn:test:install-system"), ("code", "=", "local_ext_1")])
        self.assertTrue(code)
        self.assertTrue(code.is_local)

    def test_install_creates_concept_groups(self):
        """Install wizard creates concept groups with resolved code URIs."""
        # First create a vocabulary with codes that have URIs
        pack = self._create_pack_with_vocab(
            "install_concepts",
            vocab_items=[
                {
                    "name": "Concept test codes",
                    "vocabulary_id": self.test_vocab.id,
                    "codes": [
                        {"code": "concept_code_a", "display": "Code A"},
                        {"code": "concept_code_b", "display": "Code B"},
                    ],
                }
            ],
            concept_items=[
                {
                    "name": "test_concept_group",
                    "label": "Test Concept",
                    "cel_function": "is_test_concept",
                    "target_field": "test_field",
                    "code_refs": [
                        "urn:test:install-vocab#concept_code_a",
                        "urn:test:install-vocab#concept_code_b",
                    ],
                }
            ],
        )

        wizard = self._install_pack(pack)

        # Verify concept group was created
        group = self.ConceptGroup.search([("name", "=", "test_concept_group")])
        self.assertTrue(group)
        self.assertEqual(group.label, "Test Concept")
        self.assertEqual(group.cel_function, "is_test_concept")
        self.assertEqual(len(group.code_ids), 2)

        # Verify tracking
        concept = pack.concept_ids[0]
        self.assertEqual(concept.installed_group_id, group)
        self.assertTrue(concept.is_installed)

        self.assertIn("Concept groups provisioned: 1", wizard.result_message)

    def test_install_merges_into_existing_concept_group(self):
        """Install wizard merges codes into an existing concept group."""
        # Create an existing concept group with one code
        existing_code = self.VocabCode.create(
            {
                "vocabulary_id": self.test_vocab.id,
                "code": "merge_existing",
                "display": "Existing Merge Code",
            }
        )
        existing_group = self.ConceptGroup.create(
            {
                "name": "merge_test_group",
                "label": "Merge Test",
                "code_ids": [(6, 0, [existing_code.id])],
            }
        )
        self.assertEqual(len(existing_group.code_ids), 1)

        # Create a pack that adds a new code and references it in the same concept group name
        new_code = self.VocabCode.create(
            {
                "vocabulary_id": self.test_vocab.id,
                "code": "merge_new",
                "display": "New Merge Code",
            }
        )

        pack = self._create_pack_with_vocab(
            "install_merge_concept",
            concept_items=[
                {
                    "name": "merge_test_group",
                    "label": "Merge Test Updated",
                    "cel_function": "is_merge",
                    "code_refs": [new_code.uri],
                }
            ],
        )

        self._install_pack(pack)

        # Verify the existing group now has both codes
        existing_group.invalidate_recordset(["code_ids"])
        self.assertEqual(len(existing_group.code_ids), 2)
        self.assertIn(existing_code, existing_group.code_ids)
        self.assertIn(new_code, existing_group.code_ids)

        # Verify tracking points to existing group
        concept = pack.concept_ids[0]
        self.assertEqual(concept.installed_group_id, existing_group)

    def test_uninstall_clears_refs_keeps_vocabulary(self):
        """Uninstall clears code/concept refs but keeps installed_vocabulary_id."""
        pack = self._create_pack_with_vocab(
            "install_uninstall_test",
            vocab_items=[
                {
                    "name": "Uninstall test",
                    "new_vocabulary_name": "Uninstall Vocab",
                    "new_vocabulary_namespace": "urn:test:uninstall-vocab",
                    "codes": [
                        {"code": "uninst_1", "display": "Uninstall Code 1"},
                    ],
                }
            ],
            concept_items=[
                {
                    "name": "uninstall_concept",
                    "label": "Uninstall Concept",
                    "cel_function": "is_uninst",
                    "code_refs": ["urn:test:uninstall-vocab#uninst_1"],
                }
            ],
        )

        self._install_pack(pack)

        vocab_item = pack.vocabulary_ids[0]
        code_item = vocab_item.code_ids[0]
        concept = pack.concept_ids[0]

        self.assertTrue(vocab_item.installed_vocabulary_id)
        self.assertTrue(code_item.installed_code_id)
        self.assertTrue(concept.installed_group_id)

        # Uninstall
        pack.action_uninstall()

        vocab_item.invalidate_recordset()
        code_item.invalidate_recordset()
        concept.invalidate_recordset()

        # installed_vocabulary_id is preserved
        self.assertTrue(vocab_item.installed_vocabulary_id)
        # Code and concept refs are cleared
        self.assertFalse(code_item.installed_code_id)
        self.assertFalse(concept.installed_group_id)

    def test_uninstall_reinstall_cycle(self):
        """Uninstall then reinstall works without errors (idempotent)."""
        pack = self._create_pack_with_vocab(
            "install_reinstall_test",
            vocab_items=[
                {
                    "name": "Reinstall test",
                    "new_vocabulary_name": "Reinstall Vocab",
                    "new_vocabulary_namespace": "urn:test:reinstall-vocab",
                    "codes": [
                        {"code": "reinst_1", "display": "Reinstall Code 1"},
                    ],
                }
            ],
        )

        # First install
        self._install_pack(pack)
        self.assertEqual(pack.state, "installed")

        # Uninstall
        pack.action_uninstall()
        self.assertEqual(pack.state, "available")

        # Reinstall should work without namespace conflict
        self._install_pack(pack)
        self.assertEqual(pack.state, "installed")

        # Vocab should still exist and be the same one
        vocab_item = pack.vocabulary_ids[0]
        self.assertTrue(vocab_item.installed_vocabulary_id)
        vocab = self.Vocabulary.search([("namespace_uri", "=", "urn:test:reinstall-vocab")])
        self.assertEqual(len(vocab), 1)

    def test_error_unresolvable_code_uris(self):
        """Install raises UserError when concept group has unresolvable URIs."""
        pack = self._create_pack_with_vocab(
            "install_bad_uris",
            concept_items=[
                {
                    "name": "bad_concept",
                    "label": "Bad Concept",
                    "cel_function": "is_bad",
                    "code_refs": [
                        "urn:nonexistent:vocab#code1",
                        "urn:nonexistent:vocab#code2",
                    ],
                }
            ],
        )

        with self.assertRaises(UserError) as cm:
            self._install_pack(pack)

        # Both missing URIs should be listed
        self.assertIn("urn:nonexistent:vocab#code1", str(cm.exception))
        self.assertIn("urn:nonexistent:vocab#code2", str(cm.exception))

    def test_partial_uri_resolution_lists_all_missing(self):
        """When some URIs resolve and some don't, all missing are reported."""
        # Create a code that will resolve
        self.VocabCode.create(
            {
                "vocabulary_id": self.test_vocab.id,
                "code": "partial_existing",
                "display": "Partial Existing",
            }
        )

        pack = self._create_pack_with_vocab(
            "install_partial_uris",
            concept_items=[
                {
                    "name": "partial_concept",
                    "label": "Partial Concept",
                    "cel_function": "is_partial",
                    "code_refs": [
                        "urn:test:install-vocab#partial_existing",
                        "urn:nonexistent:vocab#missing1",
                        "urn:nonexistent:vocab#missing2",
                    ],
                }
            ],
        )

        with self.assertRaises(UserError) as cm:
            self._install_pack(pack)

        error_msg = str(cm.exception)
        self.assertIn("urn:nonexistent:vocab#missing1", error_msg)
        self.assertIn("urn:nonexistent:vocab#missing2", error_msg)
        # The existing URI should NOT be listed as missing
        self.assertNotIn("partial_existing", error_msg)

    def test_extra_fields_set_on_fresh_create(self):
        """Extra fields (definition, sequence, target_type) are set on freshly created codes."""
        pack = self._create_pack_with_vocab(
            "install_extra_fields",
            vocab_items=[
                {
                    "name": "Extra fields test",
                    "vocabulary_id": self.test_vocab.id,
                    "codes": [
                        {
                            "code": "extra_field_code",
                            "display": "Extra Field Code",
                            "definition": "A test definition",
                            "sequence": 42,
                            "target_type": "individual",
                        },
                    ],
                }
            ],
        )

        self._install_pack(pack)

        code = self.VocabCode.search(
            [("namespace_uri", "=", "urn:test:install-vocab"), ("code", "=", "extra_field_code")]
        )
        self.assertEqual(code.definition, "A test definition")
        self.assertEqual(code.sequence, 42)
        self.assertEqual(code.target_type, "individual")

    def test_extra_fields_not_overwritten_on_existing(self):
        """Extra fields are not overwritten when code already exists."""
        # Pre-create the code with custom values
        self.VocabCode.create(
            {
                "vocabulary_id": self.test_vocab.id,
                "code": "preexisting_code",
                "display": "Pre-existing",
                "definition": "Original definition",
                "sequence": 99,
                "target_type": "group",
            }
        )

        pack = self._create_pack_with_vocab(
            "install_no_overwrite",
            vocab_items=[
                {
                    "name": "No overwrite test",
                    "vocabulary_id": self.test_vocab.id,
                    "codes": [
                        {
                            "code": "preexisting_code",
                            "display": "Different Display",
                            "definition": "Pack definition",
                            "sequence": 1,
                            "target_type": "individual",
                        },
                    ],
                }
            ],
        )

        self._install_pack(pack)

        code = self.VocabCode.search(
            [("namespace_uri", "=", "urn:test:install-vocab"), ("code", "=", "preexisting_code")]
        )
        # Original values preserved
        self.assertEqual(code.definition, "Original definition")
        self.assertEqual(code.sequence, 99)
        self.assertEqual(code.target_type, "group")

    def test_acl_viewer_cannot_create_pack_vocabulary(self):
        """Viewer group cannot create pack vocabulary records."""
        viewer_group = self.env.ref("spp_studio.group_studio_viewer")
        base_user_group = self.env.ref("base.group_user")

        test_user = self.env["res.users"].create(
            {
                "name": "Test Viewer",
                "login": "test_pack_vocab_viewer",
                "email": "test_pack_vocab_viewer@example.com",
                "group_ids": [
                    Command.link(base_user_group.id),
                    Command.link(viewer_group.id),
                ],
            }
        )

        pack = self._create_pack_with_vocab("acl_test_pack")
        PackVocab = self.env["spp.studio.pack.vocabulary"].with_user(test_user)
        with self.assertRaises(AccessError):
            PackVocab.create(
                {
                    "pack_id": pack.id,
                    "name": "Should fail",
                    "vocabulary_id": self.test_vocab.id,
                }
            )

    def test_install_vocabulary_only_pack(self):
        """Pack with only vocabulary items (no logic items) installs correctly."""
        pack = self._create_pack_with_vocab(
            "install_vocab_only",
            vocab_items=[
                {
                    "name": "Vocab only",
                    "vocabulary_id": self.test_vocab.id,
                    "codes": [
                        {"code": "vocab_only_code", "display": "Vocab Only"},
                    ],
                }
            ],
        )

        wizard = self._install_pack(pack)

        self.assertEqual(pack.state, "installed")
        self.assertIn("Vocabulary codes provisioned: 1", wizard.result_message)
        self.assertIn("Logic items installed: 0", wizard.result_message)

    def test_new_vocabulary_idempotent_on_reinstall(self):
        """Reinstalling a pack with new_vocabulary reuses existing vocab, doesn't duplicate."""
        pack = self._create_pack_with_vocab(
            "install_idem_new_vocab",
            vocab_items=[
                {
                    "name": "Idempotent new vocab",
                    "new_vocabulary_name": "Idempotent Vocab",
                    "new_vocabulary_namespace": "urn:test:idempotent-vocab",
                    "codes": [
                        {"code": "idem_1", "display": "Idempotent 1"},
                    ],
                }
            ],
        )

        # First install
        self._install_pack(pack)
        vocab_item = pack.vocabulary_ids[0]
        first_vocab_id = vocab_item.installed_vocabulary_id.id

        # Uninstall and reinstall
        pack.action_uninstall()
        self._install_pack(pack)

        # Should reuse the same vocabulary (no duplicate)
        vocab_item.invalidate_recordset()
        self.assertEqual(vocab_item.installed_vocabulary_id.id, first_vocab_id)
        all_vocabs = self.Vocabulary.search([("namespace_uri", "=", "urn:test:idempotent-vocab")])
        self.assertEqual(len(all_vocabs), 1)
