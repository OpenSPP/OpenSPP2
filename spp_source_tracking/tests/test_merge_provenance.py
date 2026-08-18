# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import uuid

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase


class TestMergeProvenance(TransactionCase):
    """Test cases for merge provenance functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.MergeProvenance = cls.env["spp.merge.provenance"]
        cls.RegistryId = cls.env["spp.registry.id"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]
        cls.Vocabulary = cls.env["spp.vocabulary"]
        # spp.program lives in spp_programs; program-membership merge handling
        # is exercised only when the programs stack is installed.
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
                "code": "national_id",
                "display": "Test National ID",
            }
        )

        # Create a test program with unique name (only when programs installed)
        if cls.has_programs:
            cls.program = cls.Program.create(
                {
                    "name": f"Test Social Program {uuid.uuid4().hex[:8]}",
                    "target_type": "individual",
                }
            )

    def _create_registrant(self, name, source_system="test-source", **kwargs):
        """Helper to create a registrant with source tracking."""
        vals = {
            "name": name,
            "is_registrant": True,
            **kwargs,
        }
        return self.Partner.with_context(source_system=source_system).create(vals)

    def test_merge_into_creates_provenance(self):
        """Test that merge_into creates a merge provenance record."""
        source = self._create_registrant("Source Partner", source_system="source-sys")
        target = self._create_registrant("Target Partner")

        target = source.merge_into(target, reason="Duplicate detected")

        provenance = self.MergeProvenance.search([("merged_id", "=", source.id)])
        self.assertEqual(len(provenance), 1)
        self.assertEqual(provenance.survivor_id, target)
        self.assertEqual(provenance.merged_source_system, "source-sys")
        self.assertEqual(provenance.merge_reason, "Duplicate detected")

    def test_merge_into_archives_source(self):
        """Test that merge_into archives the source partner."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        source.merge_into(target)

        self.assertFalse(source.active)
        self.assertEqual(source.merged_into_id, target)

    def test_merge_into_updates_target_provenance(self):
        """Test that merge_into updates target's last_update fields."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        source.merge_into(target)

        self.assertEqual(target.last_update_system, "merge")
        self.assertEqual(target.last_update_reference, f"merged-from-{source.id}")

    def test_merge_into_transfers_identifiers(self):
        """Test that merge_into transfers registry IDs to target."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        # Create an ID for source
        reg_id = self.RegistryId.create(
            {
                "partner_id": source.id,
                "id_type_id": self.id_type.id,
                "value": "SOURCE-ID-123",
            }
        )

        source.merge_into(target)

        self.assertEqual(reg_id.partner_id, target)

    def test_merge_into_transfers_memberships(self):
        """Test that merge_into transfers program memberships."""
        if not self.has_programs:
            self.skipTest("spp.program not installed (see spp_source_tracking_programs)")
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        # Create membership for source
        membership = self.Membership.create(
            {
                "partner_id": source.id,
                "program_id": self.program.id,
            }
        )

        source.merge_into(target)

        self.assertEqual(membership.partner_id, target)

    def test_merge_into_handles_duplicate_memberships(self):
        """Test that duplicate memberships are archived during merge."""
        if not self.has_programs:
            self.skipTest("spp.program not installed (see spp_source_tracking_programs)")
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        # Create memberships for both in same program
        source_membership = self.Membership.create(
            {
                "partner_id": source.id,
                "program_id": self.program.id,
            }
        )
        target_membership = self.Membership.create(
            {
                "partner_id": target.id,
                "program_id": self.program.id,
            }
        )

        source.merge_into(target)

        # Source membership should be archived
        self.assertFalse(source_membership.active)
        # Target membership should remain active
        self.assertTrue(target_membership.active)

    def test_merge_into_same_partner_raises_error(self):
        """Test that merging a partner into itself raises UserError."""
        partner = self._create_registrant("Test Partner")

        with self.assertRaises(UserError) as context:
            partner.merge_into(partner)

        self.assertIn("itself", str(context.exception))

    def test_merge_into_inactive_raises_error(self):
        """Test that merging an inactive partner raises UserError."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        source.active = False

        with self.assertRaises(UserError) as context:
            source.merge_into(target)

        self.assertIn("inactive", str(context.exception))

    def test_merge_into_already_merged_raises_error(self):
        """Test that merging an already merged partner raises UserError."""
        source = self._create_registrant("Source Partner")
        target1 = self._create_registrant("Target Partner 1")
        target2 = self._create_registrant("Target Partner 2")

        source.merge_into(target1)

        # Re-activate source for test (simulating edge case)
        source.active = True

        with self.assertRaises(UserError) as context:
            source.merge_into(target2)

        self.assertIn("already merged", str(context.exception))

    def test_merge_snapshot_contains_key_fields(self):
        """Test that merge snapshot contains essential fields."""
        source = self._create_registrant(
            "Source Partner",
            phone="+1234567890",
            email="source@example.com",
        )
        target = self._create_registrant("Target Partner")

        # Add an ID to source
        self.RegistryId.create(
            {
                "partner_id": source.id,
                "id_type_id": self.id_type.id,
                "value": "SNAPSHOT-ID",
            }
        )

        source.merge_into(target)

        provenance = self.MergeProvenance.search([("merged_id", "=", source.id)])
        snapshot = provenance.merged_data_snapshot

        self.assertEqual(snapshot["name"], "Source Partner")
        self.assertEqual(snapshot["phone"], "+1234567890")
        self.assertEqual(snapshot["email"], "source@example.com")
        self.assertEqual(len(snapshot["identifiers"]), 1)
        self.assertEqual(snapshot["identifiers"][0]["value"], "SNAPSHOT-ID")

    def test_resolve_partner_returns_self_if_not_merged(self):
        """Test that resolve_partner returns the same partner if not merged."""
        partner = self._create_registrant("Test Partner")

        resolved = self.Partner.resolve_partner(partner.id)

        self.assertEqual(resolved, partner)

    def test_resolve_partner_follows_merge_chain(self):
        """Test that resolve_partner follows the merge chain."""
        partner1 = self._create_registrant("Partner 1")
        partner2 = self._create_registrant("Partner 2")
        partner3 = self._create_registrant("Partner 3")

        # Merge chain: partner1 -> partner2 -> partner3
        partner1.merge_into(partner2)
        partner2.merge_into(partner3)

        resolved = self.Partner.resolve_partner(partner1.id)

        self.assertEqual(resolved, partner3)

    def test_merge_count_computed(self):
        """Test that merge_count is computed correctly."""
        target = self._create_registrant("Target Partner")

        self.assertEqual(target.merge_count, 0)

        source1 = self._create_registrant("Source Partner 1")
        source2 = self._create_registrant("Source Partner 2")

        source1.merge_into(target)
        source2.merge_into(target)

        self.assertEqual(target.merge_count, 2)

    def test_merge_provenance_display_name(self):
        """Test that merge provenance display_name is computed correctly."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        source.merge_into(target)

        provenance = self.MergeProvenance.search([("merged_id", "=", source.id)])

        self.assertIn(str(source.id), provenance.display_name)
        self.assertIn("Target Partner", provenance.display_name)

    def test_merge_into_already_merged_target_raises_error(self):
        """Test that merging into an already-merged target raises UserError."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")
        final_target = self._create_registrant("Final Target")

        # First merge target into final_target
        target.merge_into(final_target)

        # Re-activate target for test
        target.active = True

        # Now try to merge source into the already-merged target
        with self.assertRaises(UserError) as context:
            source.merge_into(target)

        self.assertIn("already been merged", str(context.exception))

    def test_merge_without_reason_succeeds(self):
        """Test that reason is optional in merge_into."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        result = source.merge_into(target)  # No reason provided

        self.assertEqual(result, target)
        provenance = self.MergeProvenance.search([("merged_id", "=", source.id)])
        self.assertFalse(provenance.merge_reason)

    def test_merge_sets_merged_by_to_current_user(self):
        """Test that merged_by_id is set to current user."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        source.merge_into(target)

        provenance = self.MergeProvenance.search([("merged_id", "=", source.id)])
        self.assertEqual(provenance.merged_by_id, self.env.user)

    def test_merge_sets_merge_date(self):
        """Test that merge_date is set automatically."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        source.merge_into(target)

        provenance = self.MergeProvenance.search([("merged_id", "=", source.id)])
        self.assertIsNotNone(provenance.merge_date)

    def test_merge_transfers_multiple_identifiers(self):
        """Test that merge transfers all identifiers from source."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        # Create a second ID type code
        id_type_2 = self.VocabularyCode.create(
            {
                "vocabulary_id": self.test_vocab.id,
                "code": "secondary_id",
                "display": "Secondary ID Type",
            }
        )

        # Create multiple IDs for source
        reg_ids = []
        for i, id_type in enumerate([self.id_type, id_type_2]):
            reg_id = self.RegistryId.create(
                {
                    "partner_id": source.id,
                    "id_type_id": id_type.id,
                    "value": f"ID-{i}",
                }
            )
            reg_ids.append(reg_id)

        source.merge_into(target)

        # All IDs should be transferred
        for reg_id in reg_ids:
            self.assertEqual(reg_id.partner_id, target)
        self.assertEqual(len(target.reg_ids), 2)

    def test_merge_access_control_admin_allowed(self):
        """Test that admin users can perform merges."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        # Test is run as admin, should succeed
        result = source.merge_into(target)
        self.assertEqual(result, target)

    def test_merge_access_control_regular_user_denied(self):
        """Test that regular users cannot perform merges."""
        source = self._create_registrant("Source Partner")
        target = self._create_registrant("Target Partner")

        # Create a regular user without admin or manager groups
        regular_user = self.env["res.users"].create(
            {
                "name": "Regular User",
                "login": "regular_test_user",
                "email": "regular@test.com",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

        # Try to merge as regular user
        with self.assertRaises(AccessError):
            source.with_user(regular_user).merge_into(target)

    def test_merge_snapshot_structure(self):
        """Test that merge snapshot has correct structure."""
        source = self._create_registrant(
            "Source Partner",
            phone="+1234567890",
            email="source@example.com",
        )
        target = self._create_registrant("Target Partner")

        # Add identifier
        self.RegistryId.create(
            {
                "partner_id": source.id,
                "id_type_id": self.id_type.id,
                "value": "STRUCT-ID",
            }
        )

        source.merge_into(target)

        provenance = self.MergeProvenance.search([("merged_id", "=", source.id)])
        snapshot = provenance.merged_data_snapshot

        # Verify structure
        expected_keys = {"name", "phone", "email", "identifiers"}
        self.assertEqual(set(snapshot.keys()), expected_keys)

        # Verify identifiers structure
        self.assertIsInstance(snapshot["identifiers"], list)
        for identifier in snapshot["identifiers"]:
            self.assertIn("type", identifier)
            self.assertIn("value", identifier)

    def test_merge_preserves_source_provenance(self):
        """Test that merge provenance preserves source's original tracking."""
        source = self._create_registrant(
            "Source Partner",
            source_system="external-system",
        )
        # Set source reference via context
        source = self.Partner.with_context(
            source_system="external-system",
            source_reference="EXT-REF-123",
            collection_method="api",
        ).create(
            {
                "name": "Source Partner 2",
                "is_registrant": True,
            }
        )
        target = self._create_registrant("Target Partner")

        source.merge_into(target)

        provenance = self.MergeProvenance.search([("merged_id", "=", source.id)])
        self.assertEqual(provenance.merged_source_system, "external-system")
        self.assertEqual(provenance.merged_source_reference, "EXT-REF-123")
        self.assertEqual(provenance.merged_collection_method, "api")
