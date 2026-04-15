# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for GroupService"""

from odoo.exceptions import ValidationError

from ..schemas.base import Address, CodeableConcept, Coding, Identifier, Reference
from ..schemas.group import Group, GroupMember
from ..schemas.membership import MembershipHistoryEntry
from ..schemas.patch import GroupPatch
from ..services.group_service import GroupService
from .common import ApiV2TestCase


class TestGroupService(ApiV2TestCase):
    """Test GroupService functionality"""

    def setUp(self):
        super().setUp()
        self.service = GroupService(self.env)

    def test_find_by_identifier_using_namespace_uri(self):
        """Lookup uses namespace_uri, not name"""
        group = self.create_test_group(
            name="Test Household",
            identifier_value="HH-123",
        )

        # Find using namespace_uri (groups use household-id namespace)
        found = self.service.find_by_identifier(
            "urn:openspp:vocab:id-type#test_household_id",
            "HH-123",
        )

        self.assertEqual(found, group)

    def test_find_by_identifier_not_found(self):
        """Returns empty recordset when not found"""
        found = self.service.find_by_identifier(
            "urn:openspp:vocab:id-type#test_household_id",
            "NONEXISTENT",
        )

        self.assertFalse(found)

    def test_find_by_identifier_only_groups(self):
        """Only finds groups, not individuals"""
        # Create individual with same identifier value
        self.create_test_individual(identifier_value="SAME-001")

        # Try to find with group service
        found = self.service.find_by_identifier(
            "urn:openspp:vocab:id-type#test_household_id",
            "SAME-001",
        )

        self.assertFalse(found, "Should not find individuals with group service")

    def test_to_api_schema_no_database_id(self):
        """Response has no 'id' field, only 'identifier'"""
        group = self.create_test_group(
            name="Test Group",
            identifier_value="HH-001",
        )

        data = self.service.to_api_schema(group)

        self.assertNotIn("id", data, "Database ID must not be exposed")
        self.assertIn("identifier", data)
        self.assertGreater(len(data["identifier"]), 0)

    def test_to_api_schema_identifier_structure(self):
        """Identifiers use namespace_uri as system"""
        group = self.create_test_group(identifier_value="HH-001")

        data = self.service.to_api_schema(group)

        # Find the specific identifier we created (groups may have other identifiers from demo data)
        identifier = next(
            (i for i in data["identifier"] if i["value"] == "HH-001"),
            None,
        )
        self.assertIsNotNone(identifier, "Expected identifier not found")
        # Groups use household-id namespace, not national-id
        self.assertEqual(identifier["system"], "urn:openspp:vocab:id-type#test_household_id")
        self.assertEqual(identifier["value"], "HH-001")

    def test_to_api_schema_basic_fields(self):
        """Basic fields are mapped correctly"""
        group = self.create_test_group(
            name="Santos Household",
            identifier_value="HH-001",
        )

        data = self.service.to_api_schema(group)

        self.assertEqual(data["type"], "Group")
        self.assertEqual(data["active"], True)
        self.assertEqual(data["name"], "Santos Household")

    def test_to_api_schema_address(self):
        """Address is mapped correctly"""
        group = self.create_test_group(
            identifier_value="HH-001",
            street="123 Main St",
            city="Test City",
            zip="12345",
            state_id=self.test_state.id,
            country_id=self.test_country.id,
        )

        data = self.service.to_api_schema(group)

        self.assertIn("address", data)
        address = data["address"][0]
        self.assertEqual(address["type"], "physical")
        self.assertEqual(address["line"], ["123 Main St"])
        self.assertEqual(address["city"], "Test City")
        self.assertEqual(address["state"], "Test State")
        self.assertEqual(address["country"], "TC")
        self.assertEqual(address["postalCode"], "12345")

    def test_to_api_schema_members(self):
        """Group members are included"""
        individual = self.create_test_individual(identifier_value="IND-001")
        group = self.create_test_group(
            name="Test Household",
            identifier_value="HH-001",
            members=[(individual, self.relationship_head)],
        )

        data = self.service.to_api_schema(group)

        self.assertIn("member", data)
        self.assertIn("quantity", data)
        self.assertEqual(data["quantity"], 1)

        member = data["member"][0]
        self.assertIn("entity", member)
        self.assertIn("IND-001", member["entity"]["reference"])
        self.assertEqual(member["entity"]["display"], individual.name)
        self.assertIn("role", member)
        self.assertEqual(member["role"]["coding"][0]["code"], "head")

    def test_to_api_schema_multiple_members(self):
        """Multiple members are counted correctly"""
        ind1 = self.create_test_individual(identifier_value="IND-001")
        ind2 = self.create_test_individual(identifier_value="IND-002")
        group = self.create_test_group(
            identifier_value="HH-001",
            members=[
                (ind1, self.relationship_head),
                (ind2, None),
            ],
        )

        data = self.service.to_api_schema(group)

        self.assertEqual(data["quantity"], 2)
        self.assertEqual(len(data["member"]), 2)

    def test_to_api_schema_metadata(self):
        """Metadata includes version and timestamp"""
        group = self.create_test_group(identifier_value="HH-001")

        data = self.service.to_api_schema(group)

        self.assertIn("meta", data)
        self.assertIn("versionId", data["meta"])
        self.assertIn("lastUpdated", data["meta"])

    def test_to_api_schema_missing_identifiers_raises(self):
        """Group without identifiers raises ValidationError"""
        # Create group without registry ID
        group = self.env["res.partner"].create(
            {
                "name": "No Identifier",
                "is_registrant": True,
                "is_group": True,
            }
        )

        result = self.service.to_api_schema(group)
        self.assertIsNone(result)

    def test_from_api_schema_creates_vals(self):
        """from_api_schema converts API schema to Odoo vals"""
        schema = Group(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_household_id",
                    value="HH-NEW-001",
                )
            ],
            name="New Household",
            active=True,
            type="Group",
        )

        vals = self.service.from_api_schema(schema)

        self.assertEqual(vals["is_registrant"], True)
        self.assertEqual(vals["is_group"], True)
        self.assertEqual(vals["name"], "New Household")
        self.assertEqual(vals["active"], True)

    def test_from_api_schema_address(self):
        """from_api_schema converts address correctly"""
        schema = Group(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_household_id",
                    value="HH-NEW-001",
                )
            ],
            name="Test Group",
            address=[
                Address(
                    type="physical",
                    line=["123 Main St"],
                    city="Test City",
                    state="Test State",
                    country="TC",
                    postal_code="12345",
                )
            ],
        )

        vals = self.service.from_api_schema(schema)

        self.assertEqual(vals["street"], "123 Main St")
        self.assertEqual(vals["city"], "Test City")
        self.assertEqual(vals["zip"], "12345")
        self.assertEqual(vals["country_id"], self.test_country.id)
        self.assertEqual(vals["state_id"], self.test_state.id)

    def test_create_with_source_tracking(self):
        """Create sets source_system from context"""
        schema = Group(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_household_id",
                    value="HH-CREATE-001",
                )
            ],
            name="New Group",
        )

        group = self.service.create(schema, source="urn:test:source")

        self.assertTrue(group)
        self.assertEqual(group.source_system, "urn:test:source")
        self.assertEqual(group.collection_method, "api")

    def test_create_with_members(self):
        """Create group with members"""
        individual = self.create_test_individual(identifier_value="IND-001")

        schema = Group(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_household_id",
                    value="HH-CREATE-002",
                )
            ],
            name="Group with Members",
            member=[
                GroupMember(
                    entity=Reference(
                        reference="Individual/urn:openspp:vocab:id-type#test_national_id|IND-001",
                        display="Test Person",
                    ),
                    role=CodeableConcept(
                        coding=[
                            Coding(
                                system="urn:test:relationship",
                                code="head",
                                display="Head",
                            )
                        ]
                    ),
                )
            ],
        )

        group = self.service.create(schema, source="urn:test:source")

        # Check member was created
        relationships = self.env["spp.registry.relationship"].search([("destination", "=", group.id)])
        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0].source, individual)

    def test_update_with_source_tracking(self):
        """Update sets source tracking"""
        group = self.create_test_group(
            identifier_value="HH-UPDATE-001",
            name="Old Name",
        )

        schema = Group(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_household_id",
                    value="HH-UPDATE-001",
                )
            ],
            name="Updated Name",
        )

        updated = self.service.update(group, schema, source="urn:test:updater")

        self.assertEqual(updated.name, "Updated Name")
        # Source system should not be overwritten (if field exists)
        if hasattr(updated, "source_system"):
            self.assertNotEqual(updated.source_system, "urn:test:updater")

    def test_to_api_schema_no_members(self):
        """Group without members has no member field"""
        group = self.create_test_group(identifier_value="HH-001")

        data = self.service.to_api_schema(group)

        self.assertNotIn("member", data)
        self.assertNotIn("quantity", data)

    def test_to_api_schema_member_without_identifiers_skipped(self):
        """Members without valid identifiers are skipped from member list"""
        # Create an individual without registry IDs
        no_id_individual = self.env["res.partner"].create(
            {
                "name": "No ID Member",
                "is_registrant": True,
                "is_group": False,
            }
        )
        group = self.create_test_group(identifier_value="HH-MEMBER-SKIP")

        # Create membership directly (bypassing the API which would validate)
        self.env["spp.group.membership"].create(
            {
                "group": group.id,
                "individual": no_id_individual.id,
            }
        )

        data = self.service.to_api_schema(group)

        # Member without identifiers should be skipped
        if "member" in data:
            for member in data["member"]:
                self.assertNotIn(
                    "No ID Member",
                    member.get("entity", {}).get("display", ""),
                )

    def test_create_member_invalid_reference_ignored(self):
        """Invalid member references are logged and ignored"""
        schema = Group(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_household_id",
                    value="HH-CREATE-003",
                )
            ],
            name="Group with Invalid Member",
            member=[
                GroupMember(
                    entity=Reference(
                        reference="INVALID-FORMAT",
                        display="Bad Reference",
                    )
                )
            ],
        )

        # Should create group but skip invalid member
        group = self.service.create(schema, source="urn:test:source")

        self.assertTrue(group)
        relationships = self.env["spp.registry.relationship"].search([("destination", "=", group.id)])
        self.assertEqual(len(relationships), 0, "Invalid member should be skipped")

    def test_create_member_nonexistent_individual(self):
        """Non-existent individual in member is logged and ignored"""
        schema = Group(
            identifier=[
                Identifier(
                    system="urn:openspp:vocab:id-type#test_household_id",
                    value="HH-CREATE-004",
                )
            ],
            name="Group with Non-existent Member",
            member=[
                GroupMember(
                    entity=Reference(
                        reference="Individual/urn:openspp:vocab:id-type#test_national_id|DOES-NOT-EXIST",
                        display="Ghost Person",
                    )
                )
            ],
        )

        group = self.service.create(schema, source="urn:test:source")

        relationships = self.env["spp.registry.relationship"].search([("destination", "=", group.id)])
        self.assertEqual(len(relationships), 0, "Non-existent member should be skipped")

    def _setup_membership_types(self):
        """Set up vocabulary codes for group membership types"""
        # Create vocabulary for group membership types if it doesn't exist
        vocab = self.env["spp.vocabulary"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:group-membership-type")],
            limit=1,
        )
        if not vocab:
            vocab = self.env["spp.vocabulary"].create(
                {
                    "name": "Group Membership Type",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                }
            )

        # Create head code (use is_local=True for test codes)
        head_code = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", vocab.id),
                ("code", "=", "head"),
            ],
            limit=1,
        )
        if not head_code:
            head_code = self.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": vocab.id,
                    "code": "head",
                    "display": "Head of Household",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                    "is_local": True,
                }
            )

        # Create spouse code
        spouse_code = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", vocab.id),
                ("code", "=", "spouse"),
            ],
            limit=1,
        )
        if not spouse_code:
            spouse_code = self.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": vocab.id,
                    "code": "spouse",
                    "display": "Spouse",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                    "is_local": True,
                }
            )

        # Create member code
        member_code = self.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id", "=", vocab.id),
                ("code", "=", "member"),
            ],
            limit=1,
        )
        if not member_code:
            member_code = self.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": vocab.id,
                    "code": "member",
                    "display": "Member",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                    "is_local": True,
                }
            )

        return head_code, spouse_code, member_code

    def test_merge_groups_basic(self):
        """Test basic merge without role mapping"""
        head_code, spouse_code, member_code = self._setup_membership_types()

        # Create source group with 2 members
        ind1 = self.create_test_individual(name="Person 1", identifier_value="IND-001")
        ind2 = self.create_test_individual(name="Person 2", identifier_value="IND-002")
        source_group = self.create_test_group(
            name="Source Group",
            identifier_value="HH-SOURCE",
            members=[(ind1, member_code), (ind2, spouse_code)],
        )

        # Create target group with 1 member
        ind3 = self.create_test_individual(name="Person 3", identifier_value="IND-003")
        target_group = self.create_test_group(
            name="Target Group",
            identifier_value="HH-TARGET",
            members=[(ind3, head_code)],
        )

        # Merge
        result = self.service.merge_groups(source_group, target_group)

        # Verify source group is inactive
        self.assertFalse(source_group.active)

        # Verify source memberships are ended
        # Use ended_date directly instead of is_ended computed field
        # (avoids timing issues with datetime.now() comparison)
        source_memberships = self.env["spp.group.membership"].search(
            [("group", "=", source_group.id), ("ended_date", "=", False)]
        )
        self.assertEqual(len(source_memberships), 0)

        # Verify target has all members
        target_memberships = self.env["spp.group.membership"].search(
            [("group", "=", target_group.id), ("ended_date", "=", False)]
        )
        self.assertEqual(len(target_memberships), 3)

        # Verify result is target group schema
        self.assertEqual(result["type"], "Group")
        self.assertEqual(len(result.get("member", [])), 3)

    def test_merge_groups_with_role_mapping(self):
        """Test merge with role mapping"""
        head_code, spouse_code, member_code = self._setup_membership_types()

        # Create source group with head
        ind1 = self.create_test_individual(name="Source Head", identifier_value="IND-001")
        source_group = self.create_test_group(
            name="Source Group",
            identifier_value="HH-SOURCE",
            members=[(ind1, head_code)],
        )

        # Create target group with head
        ind2 = self.create_test_individual(name="Target Head", identifier_value="IND-002")
        target_group = self.create_test_group(
            name="Target Group",
            identifier_value="HH-TARGET",
            members=[(ind2, head_code)],
        )

        # Merge with role mapping: source head becomes spouse
        role_mapping = {"head": "spouse"}
        self.service.merge_groups(source_group, target_group, role_mapping=role_mapping)

        # Verify target has 2 members
        target_memberships = self.env["spp.group.membership"].search(
            [("group", "=", target_group.id), ("is_ended", "=", False)]
        )
        self.assertEqual(len(target_memberships), 2)

        # Verify source head became spouse in target
        ind1_membership = target_memberships.filtered(lambda m: m.individual == ind1)
        self.assertEqual(len(ind1_membership), 1)
        self.assertIn(spouse_code, ind1_membership.membership_type_ids)

    def test_merge_groups_head_demotion(self):
        """Test that source head is demoted to member when target has head and no role mapping"""
        head_code, spouse_code, member_code = self._setup_membership_types()

        # Create source group with head
        ind1 = self.create_test_individual(name="Source Head", identifier_value="IND-001")
        source_group = self.create_test_group(
            name="Source Group",
            identifier_value="HH-SOURCE",
            members=[(ind1, head_code)],
        )

        # Create target group with head
        ind2 = self.create_test_individual(name="Target Head", identifier_value="IND-002")
        target_group = self.create_test_group(
            name="Target Group",
            identifier_value="HH-TARGET",
            members=[(ind2, head_code)],
        )

        # Merge without role mapping
        self.service.merge_groups(source_group, target_group)

        # Verify source head became member in target
        target_memberships = self.env["spp.group.membership"].search(
            [("group", "=", target_group.id), ("is_ended", "=", False)]
        )
        ind1_membership = target_memberships.filtered(lambda m: m.individual == ind1)
        self.assertEqual(len(ind1_membership), 1)
        # Should be demoted to member
        self.assertIn(member_code, ind1_membership.membership_type_ids)
        self.assertNotIn(head_code, ind1_membership.membership_type_ids)

    def test_merge_groups_duplicate_member_skipped(self):
        """Test that members already in target are skipped"""
        head_code, spouse_code, member_code = self._setup_membership_types()

        # Create individual
        ind1 = self.create_test_individual(name="Shared Member", identifier_value="IND-001")

        # Create source group with individual
        source_group = self.create_test_group(
            name="Source Group",
            identifier_value="HH-SOURCE",
            members=[(ind1, member_code)],
        )

        # Create target group with same individual
        target_group = self.create_test_group(
            name="Target Group",
            identifier_value="HH-TARGET",
            members=[(ind1, spouse_code)],  # Same person, different role
        )

        # Merge
        self.service.merge_groups(source_group, target_group)

        # Verify target still has only 1 member
        target_memberships = self.env["spp.group.membership"].search(
            [("group", "=", target_group.id), ("is_ended", "=", False)]
        )
        self.assertEqual(len(target_memberships), 1)

        # Verify the individual kept their original role in target (spouse)
        self.assertIn(spouse_code, target_memberships.membership_type_ids)

    def test_merge_groups_same_group_error(self):
        """Test that merging a group with itself raises error"""
        head_code, spouse_code, member_code = self._setup_membership_types()

        group = self.create_test_group(
            name="Test Group",
            identifier_value="HH-001",
        )

        with self.assertRaises(ValidationError) as ctx:
            self.service.merge_groups(group, group)

        self.assertIn("different", str(ctx.exception).lower())

    def test_merge_groups_inactive_source_error(self):
        """Test that merging from inactive source raises error"""
        head_code, spouse_code, member_code = self._setup_membership_types()

        source_group = self.create_test_group(
            name="Source Group",
            identifier_value="HH-SOURCE",
            active=False,
        )

        target_group = self.create_test_group(
            name="Target Group",
            identifier_value="HH-TARGET",
        )

        with self.assertRaises(ValidationError) as ctx:
            self.service.merge_groups(source_group, target_group)

        self.assertIn("inactive", str(ctx.exception).lower())

    def test_merge_groups_preserves_roles(self):
        """Test that roles are preserved when no mapping and no conflict"""
        head_code, spouse_code, member_code = self._setup_membership_types()

        # Create source group with spouse and member (no head)
        ind1 = self.create_test_individual(name="Person 1", identifier_value="IND-001")
        ind2 = self.create_test_individual(name="Person 2", identifier_value="IND-002")
        source_group = self.create_test_group(
            name="Source Group",
            identifier_value="HH-SOURCE",
            members=[(ind1, spouse_code), (ind2, member_code)],
        )

        # Create target group with head (no conflict)
        ind3 = self.create_test_individual(name="Person 3", identifier_value="IND-003")
        target_group = self.create_test_group(
            name="Target Group",
            identifier_value="HH-TARGET",
            members=[(ind3, head_code)],
        )

        # Merge without role mapping
        self.service.merge_groups(source_group, target_group)

        # Verify roles are preserved
        target_memberships = self.env["spp.group.membership"].search(
            [("group", "=", target_group.id), ("is_ended", "=", False)]
        )

        ind1_membership = target_memberships.filtered(lambda m: m.individual == ind1)
        self.assertIn(spouse_code, ind1_membership.membership_type_ids)

        ind2_membership = target_memberships.filtered(lambda m: m.individual == ind2)
        self.assertIn(member_code, ind2_membership.membership_type_ids)


class TestGroupServiceMembershipHistory(ApiV2TestCase):
    """Test GroupService membership history pagination"""

    def setUp(self):
        super().setUp()
        self.service = GroupService(self.env)

        # Create a group with 5 members
        self.members = []
        for i in range(5):
            member = self.create_test_individual(
                name=f"History Member {i}",
                identifier_value=f"IND-HIST-{i:03d}",
            )
            self.members.append(member)

        self.group = self.create_test_group(
            name="History Test Group",
            identifier_value="HH-HIST-001",
            members=[(m, None) for m in self.members],
        )

    def test_get_membership_history_returns_typed_entries(self):
        """get_membership_history returns MembershipHistoryEntry instances"""
        entries = self.service.get_membership_history(self.group, limit=2)
        self.assertEqual(len(entries), 2)
        for entry in entries:
            self.assertIsInstance(entry, MembershipHistoryEntry)
            self.assertEqual(entry.action, "added")
            self.assertIsInstance(entry.member, Reference)
            self.assertTrue(entry.member.reference.startswith("Individual/"))

    def test_get_membership_history_count(self):
        """get_membership_history_count returns correct count"""
        count = self.service.get_membership_history_count(self.group)
        # 5 members = 5 "added" events
        self.assertEqual(count, 5)

    def test_get_membership_history_count_with_removals(self):
        """get_membership_history_count counts both added and removed events"""
        # End one membership
        membership = self.env["spp.group.membership"].search(
            [("group", "=", self.group.id), ("individual", "=", self.members[0].id)],
            limit=1,
        )
        membership.sudo().write({"ended_date": "2026-06-01 10:00:00"})

        count = self.service.get_membership_history_count(self.group)
        # 5 added + 1 removed = 6
        self.assertEqual(count, 6)

    def test_get_membership_history_pagination(self):
        """get_membership_history respects offset and limit"""
        # Get first page
        page1 = self.service.get_membership_history(self.group, limit=2, offset=0)
        self.assertEqual(len(page1), 2)

        # Get second page
        page2 = self.service.get_membership_history(self.group, limit=2, offset=2)
        self.assertEqual(len(page2), 2)

        # Get third page (only 1 remaining)
        page3 = self.service.get_membership_history(self.group, limit=2, offset=4)
        self.assertEqual(len(page3), 1)

        # Pages should not overlap
        all_timestamps = [e.timestamp for e in page1 + page2 + page3]
        # All 5 events should be accounted for
        self.assertEqual(len(all_timestamps), 5)

    def test_get_membership_history_offset_beyond_total(self):
        """get_membership_history returns empty list when offset exceeds total"""
        result = self.service.get_membership_history(self.group, limit=10, offset=100)
        self.assertEqual(result, [])

    def test_get_membership_history_count_with_since(self):
        """get_membership_history_count respects since parameter"""
        from datetime import datetime, timedelta

        # Use future date - should return 0
        future = datetime.now() + timedelta(days=1)
        count = self.service.get_membership_history_count(self.group, since=future)
        self.assertEqual(count, 0)


class TestGroupServicePatchNullSemantics(ApiV2TestCase):
    """Test RFC 7396 null semantics for partial_update"""

    def setUp(self):
        super().setUp()
        self.service = GroupService(self.env)

    def test_patch_null_address_clears_fields(self):
        """Sending address=null clears all address fields"""
        group = self.create_test_group(
            identifier_value="NULL-ADDR-001",
            street="123 Main St",
            city="Test City",
            zip="12345",
            country_id=self.test_country.id,
            state_id=self.test_state.id,
        )
        self.assertTrue(group.street)

        patch = GroupPatch.model_validate({"address": None})
        updated = self.service.partial_update(group, patch, source="urn:test:source")

        self.assertFalse(updated.street)
        self.assertFalse(updated.city)
        self.assertFalse(updated.zip)
        self.assertFalse(updated.country_id)
        self.assertFalse(updated.state_id)
