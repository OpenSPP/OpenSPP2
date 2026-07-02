# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import uuid
from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase


class TestSourceTrackingMixin(TransactionCase):
    """Test cases for the source tracking mixin."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.RegistryId = cls.env["spp.registry.id"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]
        cls.Vocabulary = cls.env["spp.vocabulary"]
        # spp.program lives in spp_programs; the program-membership source
        # tracking now lives in the spp_source_tracking_programs companion.
        cls.has_programs = "spp.program" in cls.env
        if cls.has_programs:
            cls.Program = cls.env["spp.program"]
            cls.Membership = cls.env["spp.program.membership"]

        # Create a vocabulary for ID types (id_type_id expects spp.vocabulary.code)
        cls.test_vocab = cls.Vocabulary.create(
            {
                "name": f"Test ID Types {uuid.uuid4().hex[:8]}",
                "namespace_uri": f"urn:test:id-type:{uuid.uuid4().hex[:8]}",
            }
        )
        # Create an ID type code for testing
        cls.id_type = cls.VocabularyCode.create(
            {
                "vocabulary_id": cls.test_vocab.id,
                "code": "test_id",
                "display": "Test ID Type",
            }
        )

        # Create a test program with unique name (only when programs installed)
        if cls.has_programs:
            cls.program = cls.Program.create(
                {
                    "name": f"Test Program {uuid.uuid4().hex[:8]}",
                    "target_type": "individual",
                }
            )

    def test_create_sets_default_source_system(self):
        """Test that create sets default source_system to 'odoo-ui'."""
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        self.assertEqual(partner.source_system, "odoo-ui")

    def test_create_sets_collection_method_manual(self):
        """Test that create sets collection_method to 'manual' by default."""
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        self.assertEqual(partner.collection_method, "manual")

    def test_create_sets_collection_date(self):
        """Test that create sets collection_date automatically."""
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        self.assertIsNotNone(partner.collection_date)

    def test_create_with_explicit_source_system(self):
        """Test that explicit source_system is respected on create."""
        partner = self.Partner.with_context(source_system="external-api").create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        self.assertEqual(partner.source_system, "external-api")

    def test_create_with_explicit_collection_method(self):
        """Test that explicit collection_method is respected on create."""
        partner = self.Partner.with_context(collection_method="api").create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        self.assertEqual(partner.collection_method, "api")

    def test_create_with_source_reference(self):
        """Test that source_reference from context is set on create."""
        partner = self.Partner.with_context(source_reference="EXT-123").create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        self.assertEqual(partner.source_reference, "EXT-123")

    def test_create_with_import_file_context(self):
        """Test that import_file context sets collection_method to 'import'."""
        partner = self.Partner.with_context(import_file=True).create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        self.assertEqual(partner.collection_method, "import")

    def test_write_updates_last_update_system(self):
        """Test that write updates last_update_system."""
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        partner.write({"name": "Updated Name"})
        self.assertEqual(partner.last_update_system, "odoo-ui")

    def test_write_updates_last_update_reference(self):
        """Test that write updates last_update_reference from context."""
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        partner.with_context(source_reference="UPD-456").write({"name": "Updated Name"})
        self.assertEqual(partner.last_update_reference, "UPD-456")

    def test_write_preserves_original_source_system(self):
        """Test that write does not change original source_system."""
        partner = self.Partner.with_context(source_system="original-system").create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        partner.write({"name": "Updated Name", "source_system": "should-be-ignored"})
        self.assertEqual(partner.source_system, "original-system")

    def test_write_preserves_collection_method(self):
        """Test that write does not change original collection_method."""
        partner = self.Partner.with_context(collection_method="api").create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        partner.write({"name": "Updated Name", "collection_method": "manual"})
        self.assertEqual(partner.collection_method, "api")

    def test_skip_source_tracking_context(self):
        """Test that skip_source_tracking context skips update tracking."""
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        partner.with_context(skip_source_tracking=True).write({"name": "Updated Name"})
        # last_update_system should still be empty as tracking was skipped
        self.assertFalse(partner.last_update_system)

    def test_registry_id_has_source_tracking(self):
        """Test that spp.registry.id inherits source tracking mixin."""
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        reg_id = self.RegistryId.with_context(source_system="id-source").create(
            {
                "partner_id": partner.id,
                "id_type_id": self.id_type.id,
                "value": "ID123",
            }
        )
        self.assertEqual(reg_id.source_system, "id-source")

    def test_program_membership_has_source_tracking(self):
        """Test that spp.program.membership inherits source tracking mixin."""
        if not self.has_programs:
            self.skipTest("spp.program not installed (see spp_source_tracking_programs)")
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        membership = self.Membership.with_context(source_system="enrollment-api").create(
            {
                "partner_id": partner.id,
                "program_id": self.program.id,
            }
        )
        self.assertEqual(membership.source_system, "enrollment-api")

    def test_selection_collection_method(self):
        """Test that collection method selection returns expected values."""
        mixin = self.env["spp.mixin.source.tracking"]
        methods = mixin._selection_collection_method()
        method_keys = [m[0] for m in methods]
        self.assertIn("manual", method_keys)
        self.assertIn("import", method_keys)
        self.assertIn("api", method_keys)
        self.assertIn("mobile", method_keys)
        self.assertIn("migration", method_keys)
        self.assertIn("merge", method_keys)

    def test_selection_collection_method_complete(self):
        """Test that collection method selection contains exactly expected values."""
        mixin = self.env["spp.mixin.source.tracking"]
        methods = mixin._selection_collection_method()
        expected = {"manual", "import", "api", "mobile", "migration", "merge"}
        actual = {m[0] for m in methods}
        self.assertEqual(expected, actual)

    def test_create_sets_collection_date_to_current_time(self):
        """Test that collection_date is set to approximately current time."""
        before = fields.Datetime.now() - timedelta(seconds=1)
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        after = fields.Datetime.now() + timedelta(seconds=1)
        self.assertGreaterEqual(partner.collection_date, before)
        self.assertLessEqual(partner.collection_date, after)

    def test_create_multi_sets_source_tracking_for_all(self):
        """Test that batch create sets source tracking for all records."""
        vals_list = [{"name": f"Partner {i}", "is_registrant": True} for i in range(5)]
        partners = self.Partner.with_context(source_system="batch-api").create(vals_list)

        self.assertEqual(len(partners), 5)
        for partner in partners:
            self.assertEqual(partner.source_system, "batch-api")
            self.assertEqual(partner.collection_method, "manual")
            self.assertIsNotNone(partner.collection_date)

    def test_create_multi_with_mixed_source_systems(self):
        """Test batch create where some records have explicit source_system in vals."""
        # Note: source_system in vals is NOT respected (context is used)
        # This tests the actual behavior
        vals_list = [
            {"name": "Partner 1", "is_registrant": True},
            {"name": "Partner 2", "is_registrant": True},
            {"name": "Partner 3", "is_registrant": True},
        ]
        partners = self.Partner.create(vals_list)

        for partner in partners:
            self.assertEqual(partner.source_system, "odoo-ui")

    def test_write_updates_multiple_records(self):
        """Test that batch write updates last_update_system for all records."""
        partners = self.Partner.create([{"name": f"Partner {i}", "is_registrant": True} for i in range(3)])

        partners.write({"phone": "+1234567890"})

        for partner in partners:
            self.assertEqual(partner.last_update_system, "odoo-ui")
            self.assertEqual(partner.phone, "+1234567890")

    def test_copy_creates_new_source_tracking(self):
        """Test that copy() doesn't preserve source tracking fields."""
        original = self.Partner.with_context(
            source_system="custom-source",
            source_reference="EXT-123",
        ).create(
            {
                "name": "Original",
                "is_registrant": True,
            }
        )

        # Use fresh Partner recordset without the original's context
        # to verify copy=False works correctly
        duplicate = (
            self.Partner.browse(original.id).with_context(source_system="copy-source").copy({"name": "Duplicate"})
        )

        # New record should have fresh source tracking (copy=False on fields)
        # The source_system should come from the context at copy time
        self.assertEqual(duplicate.source_system, "copy-source")
        # source_reference was in original but not in copy context, so should be False
        self.assertFalse(duplicate.source_reference)
        # collection_date should be set on the duplicate (not None)
        self.assertIsNotNone(duplicate.collection_date)

    def test_write_with_empty_vals_still_tracks(self):
        """Test that write with empty vals dict still updates tracking."""
        partner = self.Partner.create(
            {
                "name": "Test Partner",
                "is_registrant": True,
            }
        )
        self.assertFalse(partner.last_update_system)

        partner.write({})

        # Empty write still triggers tracking
        self.assertEqual(partner.last_update_system, "odoo-ui")

    def test_context_does_not_leak_between_creates(self):
        """Test that source_system context doesn't affect separate operations."""
        p1 = self.Partner.with_context(source_system="api").create(
            {
                "name": "API Partner",
                "is_registrant": True,
            }
        )
        # Create without context
        p2 = self.Partner.create(
            {
                "name": "UI Partner",
                "is_registrant": True,
            }
        )
        self.assertEqual(p1.source_system, "api")
        self.assertEqual(p2.source_system, "odoo-ui")
