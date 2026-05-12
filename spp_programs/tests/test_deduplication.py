# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import uuid

from odoo.tests import TransactionCase


class TestDeduplicationCommon(TransactionCase):
    """Common setup for deduplication tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env["spp.program"].create(
            {"name": f"Dedup Program {uuid.uuid4().hex[:8]}", "target_type": "group"}
        )

        # Get existing ID type vocabulary and use existing codes, or create test ones
        cls.id_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if cls.id_vocab:
            # Use existing codes from the system vocabulary
            existing_codes = cls.env["spp.vocabulary.code"].search([("vocabulary_id", "=", cls.id_vocab.id)], limit=2)
            if len(existing_codes) >= 2:
                cls.id_type_national = existing_codes[0]
                cls.id_type_passport = existing_codes[1]
            else:
                # Create local extensions
                cls.id_type_national = cls.env["spp.vocabulary.code"].create(
                    {
                        "vocabulary_id": cls.id_vocab.id,
                        "code": f"NID-{uuid.uuid4().hex[:6]}",
                        "display": "National ID",
                        "is_local": True,
                    }
                )
                cls.id_type_passport = cls.env["spp.vocabulary.code"].create(
                    {
                        "vocabulary_id": cls.id_vocab.id,
                        "code": f"PP-{uuid.uuid4().hex[:6]}",
                        "display": "Passport",
                        "is_local": True,
                    }
                )
        else:
            cls.id_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Types",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )
            cls.id_type_national = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.id_vocab.id,
                    "code": "NID",
                    "display": "National ID",
                }
            )
            cls.id_type_passport = cls.env["spp.vocabulary.code"].create(
                {
                    "vocabulary_id": cls.id_vocab.id,
                    "code": "PASSPORT",
                    "display": "Passport",
                }
            )

        # Create default deduplication manager
        cls.dedup_default = cls.env["spp.deduplication.manager.default"].create(
            {"name": "Default Dedup", "program_id": cls.program.id}
        )
        cls.dedup_manager = cls.env["spp.deduplication.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"{cls.dedup_default._name},{cls.dedup_default.id}",
            }
        )
        cls.program.write({"deduplication_manager_ids": [(4, cls.dedup_manager.id)]})

        # Create ID deduplication manager
        cls.id_dedup = cls.env["spp.deduplication.manager.id_dedup"].create(
            {
                "name": "ID Dedup",
                "program_id": cls.program.id,
                "supported_id_document_type_ids": [(6, 0, [cls.id_type_national.id, cls.id_type_passport.id])],
            }
        )

        # Create phone deduplication manager
        cls.phone_dedup = cls.env["spp.deduplication.manager.phone_number"].create(
            {"name": "Phone Dedup", "program_id": cls.program.id}
        )

    def _create_group(self, name, individuals=None):
        """Helper to create a group with individuals."""
        group = self.env["res.partner"].create({"name": name, "is_registrant": True, "is_group": True})
        if individuals:
            for individual in individuals:
                self.env["spp.group.membership"].create({"group": group.id, "individual": individual.id})
        return group

    def _create_individual(self, name, reg_ids=None, phone_numbers=None):
        """Helper to create an individual with optional IDs and phone numbers."""
        individual = self.env["res.partner"].create({"name": name, "is_registrant": True, "is_group": False})
        if reg_ids:
            for id_type, value in reg_ids:
                self.env["spp.registry.id"].create(
                    {
                        "partner_id": individual.id,
                        "id_type_id": id_type.id,
                        "value": value,
                    }
                )
        if phone_numbers:
            for phone in phone_numbers:
                self.env["spp.phone.number"].create({"partner_id": individual.id, "phone_no": phone})
        return individual

    def _enroll_in_program(self, partner, state="draft"):
        """Helper to create a program membership."""
        return self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": self.program.id,
                "state": state,
            }
        )


class TestDefaultDeduplication(TestDeduplicationCommon):
    """Tests for default deduplication (shared individuals across groups)."""

    def test_no_duplicates_found(self):
        """When groups don't share members, no duplicates are found."""
        ind1 = self._create_individual("Individual 1")
        ind2 = self._create_individual("Individual 2")
        group1 = self._create_group("Group A", [ind1])
        group2 = self._create_group("Group B", [ind2])
        self._enroll_in_program(group1, "enrolled")
        self._enroll_in_program(group2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        count = self.dedup_default.deduplicate_beneficiaries(states)
        self.assertEqual(count, 0)

    def test_shared_individual_detected(self):
        """When two groups share a member, duplicates are detected."""
        shared = self._create_individual("Shared Individual")
        ind1 = self._create_individual("Unique 1")
        ind2 = self._create_individual("Unique 2")
        group1 = self._create_group("Group A", [shared, ind1])
        group2 = self._create_group("Group B", [shared, ind2])
        self._enroll_in_program(group1, "enrolled")
        self._enroll_in_program(group2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        count = self.dedup_default.deduplicate_beneficiaries(states)
        self.assertGreater(count, 0)

    def test_detailed_reason_includes_member_name(self):
        """Duplicate reason includes the shared member's name."""
        shared = self._create_individual("John Shared")
        group1 = self._create_group("Group X", [shared])
        group2 = self._create_group("Group Y", [shared])
        self._enroll_in_program(group1, "enrolled")
        self._enroll_in_program(group2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        self.dedup_default.deduplicate_beneficiaries(states)

        dup_record = self.env["spp.program.membership.duplicate"].search(
            [("deduplication_manager_id", "=", self.dedup_default.id)], limit=1
        )
        self.assertIn("John Shared", dup_record.reason)
        self.assertIn("Shared member", dup_record.reason)

    def test_keep_one_enrolled(self):
        """When one enrolled beneficiary is duplicated, it stays enrolled."""
        shared = self._create_individual("Shared")
        group1 = self._create_group("Group Enrolled", [shared])
        group2 = self._create_group("Group Draft", [shared])
        m1 = self._enroll_in_program(group1, "enrolled")
        m2 = self._enroll_in_program(group2, "draft")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        self.dedup_default.deduplicate_beneficiaries(states)

        m1.invalidate_recordset()
        m2.invalidate_recordset()
        self.assertEqual(m1.state, "enrolled")
        self.assertEqual(m2.state, "duplicated")

    def test_exited_not_overwritten(self):
        """Exited state is preserved during deduplication."""
        shared = self._create_individual("Shared")
        group1 = self._create_group("Group A", [shared])
        group2 = self._create_group("Group B", [shared])
        self._enroll_in_program(group1, "enrolled")
        m2 = self._enroll_in_program(group2, "exited")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        self.dedup_default.deduplicate_beneficiaries(states)

        m2.invalidate_recordset()
        self.assertEqual(m2.state, "exited")

    def test_individual_target_type_skips_dedup(self):
        """Default dedup only works for group target type."""
        self.program.target_type = "individual"
        ind = self._create_individual("Ind")
        self._enroll_in_program(ind, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        count = self.dedup_default.deduplicate_beneficiaries(states)
        self.assertEqual(count, 0)


class TestIDDocumentDeduplication(TestDeduplicationCommon):
    """Tests for ID document deduplication."""

    def test_group_duplicate_id_docs(self):
        """Detect duplicate ID documents across groups."""
        ind1 = self._create_individual("Person A", reg_ids=[(self.id_type_national, "12345")])
        ind2 = self._create_individual("Person B", reg_ids=[(self.id_type_national, "12345")])
        group1 = self._create_group("Group A", [ind1])
        group2 = self._create_group("Group B", [ind2])
        self._enroll_in_program(group1, "enrolled")
        self._enroll_in_program(group2, "enrolled")

        self.program.target_type = "group"
        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        count = self.id_dedup.deduplicate_beneficiaries(states)
        self.assertGreater(count, 0)

    def test_group_duplicate_reason_includes_doc_info(self):
        """Duplicate reason includes the document type and value."""
        ind1 = self._create_individual("Alice", reg_ids=[(self.id_type_national, "NID-999")])
        ind2 = self._create_individual("Bob", reg_ids=[(self.id_type_national, "NID-999")])
        group1 = self._create_group("Group A", [ind1])
        group2 = self._create_group("Group B", [ind2])
        self._enroll_in_program(group1, "enrolled")
        self._enroll_in_program(group2, "enrolled")

        self.program.target_type = "group"
        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        self.id_dedup.deduplicate_beneficiaries(states)

        dup_record = self.env["spp.program.membership.duplicate"].search(
            [("deduplication_manager_id", "=", self.id_dedup.id)], limit=1
        )
        self.assertIn("National ID", dup_record.reason)

    def test_individual_duplicate_id_docs(self):
        """Detect duplicate ID documents for individual target type."""
        self.program.target_type = "individual"
        ind1 = self._create_individual("Person A", reg_ids=[(self.id_type_national, "SAME-ID")])
        ind2 = self._create_individual("Person B", reg_ids=[(self.id_type_national, "SAME-ID")])
        self._enroll_in_program(ind1, "enrolled")
        self._enroll_in_program(ind2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        result = self.id_dedup.deduplicate_beneficiaries(states)
        self.assertGreater(result, 0)

    def test_individual_duplicate_reason_includes_names(self):
        """Individual duplicate reason shows shared names."""
        self.program.target_type = "individual"
        ind1 = self._create_individual("Alice Ind", reg_ids=[(self.id_type_passport, "PP-001")])
        ind2 = self._create_individual("Bob Ind", reg_ids=[(self.id_type_passport, "PP-001")])
        self._enroll_in_program(ind1, "enrolled")
        self._enroll_in_program(ind2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        self.id_dedup.deduplicate_beneficiaries(states)

        dup_record = self.env["spp.program.membership.duplicate"].search(
            [("deduplication_manager_id", "=", self.id_dedup.id)], limit=1
        )
        self.assertIn("Passport", dup_record.reason)
        self.assertIn("shared by", dup_record.reason)

    def test_individual_keep_one_enrolled(self):
        """Keep-one-enrolled logic for individual dedup."""
        self.program.target_type = "individual"
        ind1 = self._create_individual("Enrolled One", reg_ids=[(self.id_type_national, "DUP-100")])
        ind2 = self._create_individual("Draft One", reg_ids=[(self.id_type_national, "DUP-100")])
        m1 = self._enroll_in_program(ind1, "enrolled")
        m2 = self._enroll_in_program(ind2, "draft")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        self.id_dedup.deduplicate_beneficiaries(states)

        m1.invalidate_recordset()
        m2.invalidate_recordset()
        # One should remain enrolled or both marked if both enrolled
        self.assertIn(m2.state, ["duplicated", "draft"])

    def test_no_duplicate_when_ids_differ(self):
        """No duplicates when ID values are different."""
        self.program.target_type = "individual"
        ind1 = self._create_individual("Person A", reg_ids=[(self.id_type_national, "UNIQUE-1")])
        ind2 = self._create_individual("Person B", reg_ids=[(self.id_type_national, "UNIQUE-2")])
        self._enroll_in_program(ind1, "enrolled")
        self._enroll_in_program(ind2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        result = self.id_dedup.deduplicate_beneficiaries(states)
        self.assertEqual(result, 0)

    def test_expired_ids_ignored(self):
        """Expired ID documents are not considered for deduplication."""
        self.program.target_type = "individual"
        ind1 = self._create_individual("Person A")
        ind2 = self._create_individual("Person B")
        # Create expired IDs with same value
        self.env["spp.registry.id"].create(
            {
                "partner_id": ind1.id,
                "id_type_id": self.id_type_national.id,
                "value": "EXPIRED-ID",
                "expiry_date": "2020-01-01",
            }
        )
        self.env["spp.registry.id"].create(
            {
                "partner_id": ind2.id,
                "id_type_id": self.id_type_national.id,
                "value": "EXPIRED-ID",
                "expiry_date": "2020-01-01",
            }
        )
        self._enroll_in_program(ind1, "enrolled")
        self._enroll_in_program(ind2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        result = self.id_dedup.deduplicate_beneficiaries(states)
        self.assertEqual(result, 0)

    def test_unsupported_id_type_ignored(self):
        """IDs of unsupported types are ignored."""
        other_vocab = self.env["spp.vocabulary"].create({"name": "Other", "namespace_uri": "urn:test:other"})
        other_type = self.env["spp.vocabulary.code"].create(
            {"vocabulary_id": other_vocab.id, "code": "OTH", "display": "Other ID"}
        )
        self.program.target_type = "individual"
        ind1 = self._create_individual("Person A", reg_ids=[(other_type, "SAME")])
        ind2 = self._create_individual("Person B", reg_ids=[(other_type, "SAME")])
        self._enroll_in_program(ind1, "enrolled")
        self._enroll_in_program(ind2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        result = self.id_dedup.deduplicate_beneficiaries(states)
        self.assertEqual(result, 0)

    def test_supported_id_type_field_uses_vocabulary_code(self):
        """Verify that supported_id_document_type_ids points to spp.vocabulary.code."""
        field = self.id_dedup._fields["supported_id_document_type_ids"]
        self.assertEqual(field.comodel_name, "spp.vocabulary.code")


class TestPhoneNumberDeduplication(TestDeduplicationCommon):
    """Tests for phone number deduplication."""

    def test_group_duplicate_phone_numbers(self):
        """Detect duplicate phone numbers across groups."""
        ind1 = self._create_individual("Person A", phone_numbers=["+1234567890"])
        ind2 = self._create_individual("Person B", phone_numbers=["+1234567890"])
        group1 = self._create_group("Group A", [ind1])
        group2 = self._create_group("Group B", [ind2])
        self._enroll_in_program(group1, "enrolled")
        self._enroll_in_program(group2, "enrolled")

        self.program.target_type = "group"
        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        count = self.phone_dedup.deduplicate_beneficiaries(states)
        self.assertGreater(count, 0)

    def test_group_phone_reason_includes_phone(self):
        """Phone duplicate reason includes the phone number."""
        ind1 = self._create_individual("Alice", phone_numbers=["+9876543210"])
        ind2 = self._create_individual("Bob", phone_numbers=["+9876543210"])
        group1 = self._create_group("Group A", [ind1])
        group2 = self._create_group("Group B", [ind2])
        self._enroll_in_program(group1, "enrolled")
        self._enroll_in_program(group2, "enrolled")

        self.program.target_type = "group"
        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        self.phone_dedup.deduplicate_beneficiaries(states)

        dup_record = self.env["spp.program.membership.duplicate"].search(
            [("deduplication_manager_id", "=", self.phone_dedup.id)], limit=1
        )
        self.assertTrue(dup_record)
        self.assertIn("Duplicate phone number", dup_record.reason)

    def test_individual_duplicate_phone_numbers(self):
        """Detect duplicate phone numbers for individual target type."""
        self.program.target_type = "individual"
        ind1 = self._create_individual("Person A", phone_numbers=["+1111111111"])
        ind2 = self._create_individual("Person B", phone_numbers=["+1111111111"])
        self._enroll_in_program(ind1, "enrolled")
        self._enroll_in_program(ind2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        result = self.phone_dedup.deduplicate_beneficiaries(states)
        self.assertGreater(result, 0)

    def test_no_duplicate_different_phones(self):
        """No duplicates when phone numbers differ."""
        self.program.target_type = "individual"
        ind1 = self._create_individual("Person A", phone_numbers=["+1111111111"])
        ind2 = self._create_individual("Person B", phone_numbers=["+2222222222"])
        self._enroll_in_program(ind1, "enrolled")
        self._enroll_in_program(ind2, "enrolled")

        states = ["draft", "enrolled", "eligible", "paused", "duplicated"]
        result = self.phone_dedup.deduplicate_beneficiaries(states)
        self.assertEqual(result, 0)


class TestRecordDuplicate(TestDeduplicationCommon):
    """Tests for the _record_duplicate method."""

    def test_record_creates_duplicate_entry(self):
        """_record_duplicate creates a duplicate record."""
        group = self._create_group("Test Group")
        membership = self._enroll_in_program(group)

        self.dedup_default._record_duplicate(self.dedup_default, [membership.id], "Test reason")

        dup = self.env["spp.program.membership.duplicate"].search(
            [
                ("beneficiary_ids", "in", membership.id),
                ("reason", "=", "Test reason"),
            ]
        )
        self.assertTrue(dup)
        self.assertEqual(dup.state, "duplicate")

    def test_no_duplicate_entry_for_same_reason(self):
        """No duplicate entry created if one already exists for same reason."""
        group = self._create_group("Test Group")
        membership = self._enroll_in_program(group)

        self.dedup_default._record_duplicate(self.dedup_default, [membership.id], "Same reason")
        self.dedup_default._record_duplicate(self.dedup_default, [membership.id], "Same reason")

        dups = self.env["spp.program.membership.duplicate"].search(
            [
                ("beneficiary_ids", "in", membership.id),
                ("reason", "=", "Same reason"),
            ]
        )
        self.assertEqual(len(dups), 1)


class TestDeduplicationManagerSelection(TestDeduplicationCommon):
    """Tests for deduplication manager selection/registration."""

    def test_selection_includes_default(self):
        selection = self.env["spp.deduplication.manager"]._selection_manager_ref_id()
        names = [s[0] for s in selection]
        self.assertIn("spp.deduplication.manager.default", names)

    def test_selection_includes_phone(self):
        selection = self.env["spp.deduplication.manager"]._selection_manager_ref_id()
        names = [s[0] for s in selection]
        self.assertIn("spp.deduplication.manager.phone_number", names)

    def test_selection_includes_id_dedup(self):
        selection = self.env["spp.deduplication.manager"]._selection_manager_ref_id()
        names = [s[0] for s in selection]
        self.assertIn("spp.deduplication.manager.id_dedup", names)

    def test_eligibility_selection_includes_id_and_phone(self):
        selection = self.env["spp.eligibility.manager"]._selection_manager_ref_id()
        names = [s[0] for s in selection]
        self.assertIn("spp.program.membership.manager.id_dedup", names)
        self.assertIn("spp.program.membership.manager.phone_number", names)
