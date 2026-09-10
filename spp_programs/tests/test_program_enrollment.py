# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import uuid

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestProgramEnrollment(TransactionCase):
    """Tests for program-level enrollment and deduplication workflows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env["spp.program"].create(
            {"name": f"Enrollment Test {uuid.uuid4().hex[:8]}", "target_type": "group"}
        )

        # Create program manager
        cls.pm_default = cls.env["spp.program.manager.default"].create(
            {"name": "Default PM", "program_id": cls.program.id}
        )
        pm = cls.env["spp.program.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"{cls.pm_default._name},{cls.pm_default.id}",
            }
        )
        cls.program.write({"program_manager_ids": [(4, pm.id)]})

        # Create eligibility manager
        cls.em_default = cls.env["spp.program.membership.manager.default"].create(
            {"name": "Default EM", "program_id": cls.program.id}
        )
        em = cls.env["spp.eligibility.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"{cls.em_default._name},{cls.em_default.id}",
            }
        )
        cls.program.write({"eligibility_manager_ids": [(4, em.id)]})

        # Create deduplication manager
        cls.dedup_default = cls.env["spp.deduplication.manager.default"].create(
            {"name": "Default Dedup", "program_id": cls.program.id}
        )
        dm = cls.env["spp.deduplication.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"{cls.dedup_default._name},{cls.dedup_default.id}",
            }
        )
        cls.program.write({"deduplication_manager_ids": [(4, dm.id)]})

    def _create_group(self, name):
        return self.env["res.partner"].create({"name": name, "is_registrant": True, "is_group": True})

    def _enroll(self, partner, state="draft"):
        return self.env["spp.program.membership"].create(
            {"partner_id": partner.id, "program_id": self.program.id, "state": state}
        )

    def test_enroll_eligible_registrants_no_beneficiaries_raises(self):
        """Enrollment raises error when no beneficiaries exist."""
        program = self.env["spp.program"].create({"name": f"Empty {uuid.uuid4().hex[:8]}"})
        with self.assertRaises(UserError):
            program.enroll_eligible_registrants()

    def test_enroll_eligible_registrants_no_manager_raises(self):
        """Enrollment raises error when no program manager exists."""
        program = self.env["spp.program"].create({"name": f"No PM {uuid.uuid4().hex[:8]}"})
        group = self._create_group("Group")
        self.env["spp.program.membership"].create({"partner_id": group.id, "program_id": program.id})
        with self.assertRaises(UserError):
            program.enroll_eligible_registrants()

    def test_enrollment_skips_duplicated(self):
        """Enrollment does not change duplicated state to enrolled."""
        group = self._create_group("Duplicated Group")
        membership = self._enroll(group, "duplicated")

        # Run enrollment
        self.pm_default._enroll_eligible_registrants(["duplicated"])

        membership.invalidate_recordset()
        self.assertEqual(membership.state, "duplicated")

    def test_enrollment_skips_exited(self):
        """Enrollment does not change exited state to enrolled."""
        group = self._create_group("Exited Group")
        membership = self._enroll(group, "exited")

        self.pm_default._enroll_eligible_registrants(["exited"])

        membership.invalidate_recordset()
        self.assertEqual(membership.state, "exited")

    def test_enrollment_skips_paused(self):
        """OP#1117: enrollment does not change paused state to enrolled.

        A pause is a deliberate decision by a program officer and may only be
        undone through Resume, so re-running eligibility must step over it —
        the same treatment duplicated and exited already get above.
        """
        group = self._create_group("Paused Group")
        membership = self._enroll(group, "paused")

        self.pm_default._enroll_eligible_registrants(["paused"])

        membership.invalidate_recordset()
        self.assertEqual(membership.state, "paused")

    def test_enroll_eligible_button_leaves_paused_alone(self):
        """OP#1117 as reported: via the program's Enroll Eligible button.

        The button passes no state, so every membership is considered — which
        is how a paused one was being swept back into enrolled.
        """
        group = self._create_group("Paused Via Button")
        membership = self._enroll(group, "enrolled")
        membership.action_pause()
        self.assertEqual(membership.state, "paused", "precondition: membership is paused")

        self.program.enroll_eligible_registrants()

        membership.invalidate_recordset()
        self.assertEqual(
            membership.state,
            "paused",
            "Enroll Eligible re-enrolled a paused membership, undoing the pause",
        )

    def test_paused_is_not_demoted_to_not_eligible(self):
        """OP#1117, second path: the disenrollment sweep must skip paused too.

        A paused member the eligibility manager does not return was being
        written to not_eligible, which destroys the pause just as thoroughly as
        re-enrolling it.
        """
        group = self._create_group("Paused Ineligible")
        membership = self._enroll(group, "paused")

        # Empty state list -> the manager returns nothing, so every member is a
        # demotion candidate.
        self.pm_default._enroll_eligible_registrants(["paused"])

        membership.invalidate_recordset()
        self.assertEqual(membership.state, "paused")

    def test_paused_skip_does_not_block_other_members(self):
        """Guard the fix: skipping paused must not skip everyone else."""
        draft_group = self._create_group("Draft Alongside Paused")
        draft = self._enroll(draft_group, "draft")
        paused_group = self._create_group("Paused Alongside Draft")
        paused = self._enroll(paused_group, "paused")

        self.pm_default._enroll_eligible_registrants(["draft", "paused"])

        draft.invalidate_recordset()
        paused.invalidate_recordset()
        self.assertEqual(draft.state, "enrolled", "a draft member should still be enrolled")
        self.assertEqual(paused.state, "paused")

    def test_membership_level_enroll_refuses_a_paused_member(self):
        """OP#1117, third path: the per-membership Enroll button.

        Its button is hidden unless the membership is draft, but the method is
        public and reachable over RPC or from a server action, so it is guarded
        rather than left to the view.
        """
        group = self._create_group("Paused Single Enroll")
        membership = self._enroll(group, "enrolled")
        membership.action_pause()

        membership.enroll_eligible_registrants()

        membership.invalidate_recordset()
        self.assertEqual(membership.state, "paused")

    def test_membership_level_verify_does_not_demote_a_paused_member(self):
        """OP#1117: per-membership Verify must not push paused to not_eligible."""
        group = self._create_group("Paused Single Verify")
        membership = self._enroll(group, "enrolled")
        membership.action_pause()

        membership.verify_eligibility()

        membership.invalidate_recordset()
        self.assertEqual(membership.state, "paused")

    def test_resume_remains_the_only_way_back(self):
        """Pause is undone deliberately, through Resume."""
        group = self._create_group("Resumable Group")
        membership = self._enroll(group, "enrolled")
        membership.action_pause()
        self.program.enroll_eligible_registrants()

        membership.invalidate_recordset()
        membership.action_resume()

        self.assertEqual(membership.state, "enrolled")

    def test_enrollment_enrolls_draft(self):
        """Enrollment changes draft state to enrolled."""
        group = self._create_group("Draft Group")
        membership = self._enroll(group, "draft")

        self.pm_default._enroll_eligible_registrants(["draft"], do_count=True)

        membership.invalidate_recordset()
        self.assertEqual(membership.state, "enrolled")

    def test_disenrollment_skips_duplicated(self):
        """Disenrollment does not change duplicated to not_eligible."""
        group = self._create_group("Dup Group")
        membership = self._enroll(group, "duplicated")

        self.pm_default._enroll_eligible_registrants(["duplicated"])

        membership.invalidate_recordset()
        # Should NOT be changed to not_eligible
        self.assertNotEqual(membership.state, "not_eligible")

    def test_program_deduplicate_no_duplicates(self):
        """Program-level deduplication shows no duplicates message."""
        group = self._create_group("Solo Group")
        self._enroll(group, "enrolled")

        result = self.program.deduplicate_beneficiaries()
        self.assertEqual(result["params"]["type"], "success")
        self.assertIn("No duplicates", result["params"]["message"])

    def test_program_deduplicate_with_duplicates(self):
        """Program-level deduplication shows warning with counts."""
        ind = self.env["res.partner"].create({"name": "Shared", "is_registrant": True, "is_group": False})
        group1 = self._create_group("Group 1")
        group2 = self._create_group("Group 2")
        self.env["spp.group.membership"].create({"group": group1.id, "individual": ind.id})
        self.env["spp.group.membership"].create({"group": group2.id, "individual": ind.id})
        self._enroll(group1, "enrolled")
        self._enroll(group2, "enrolled")

        result = self.program.deduplicate_beneficiaries()
        self.assertEqual(result["params"]["type"], "warning")

    def test_program_deduplicate_shows_new_vs_existing(self):
        """Deduplication message distinguishes new from existing duplicates."""
        ind = self.env["res.partner"].create({"name": "Shared", "is_registrant": True, "is_group": False})
        group1 = self._create_group("Group A")
        group2 = self._create_group("Group B")
        self.env["spp.group.membership"].create({"group": group1.id, "individual": ind.id})
        self.env["spp.group.membership"].create({"group": group2.id, "individual": ind.id})
        m1 = self._enroll(group1, "enrolled")
        m2 = self._enroll(group2, "enrolled")

        # First run
        self.program.deduplicate_beneficiaries()

        # Reset states to run again
        m1.write({"state": "enrolled"})
        m2.write({"state": "enrolled"})

        # Second run - should show already flagged
        result = self.program.deduplicate_beneficiaries()
        self.assertEqual(result["params"]["type"], "warning")

    def test_program_deduplicate_no_manager_raises(self):
        """Deduplication raises error when no manager defined."""
        program = self.env["spp.program"].create({"name": f"No Dedup {uuid.uuid4().hex[:8]}"})
        with self.assertRaises(UserError):
            program.deduplicate_beneficiaries()

    def test_verify_eligibility_no_manager_raises(self):
        """verify_eligibility raises error when no program manager."""
        program = self.env["spp.program"].create({"name": f"No PM V {uuid.uuid4().hex[:8]}"})
        with self.assertRaises(UserError):
            program.verify_eligibility()


class TestProgramManagerDefault(TransactionCase):
    """Tests for spp.program.manager.default."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env["spp.program"].create({"name": f"PM Test {uuid.uuid4().hex[:8]}", "target_type": "group"})
        cls.pm = cls.env["spp.program.manager.default"].create({"name": "Default PM", "program_id": cls.program.id})
        pm_manager = cls.env["spp.program.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"{cls.pm._name},{cls.pm.id}",
            }
        )
        cls.program.write({"program_manager_ids": [(4, pm_manager.id)]})

        # Eligibility manager
        em_default = cls.env["spp.program.membership.manager.default"].create(
            {"name": "Default EM", "program_id": cls.program.id}
        )
        em = cls.env["spp.eligibility.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"{em_default._name},{em_default.id}",
            }
        )
        cls.program.write({"eligibility_manager_ids": [(4, em.id)]})

    def test_enroll_no_eligibility_manager_raises(self):
        """Enrollment raises error when no eligibility manager."""
        program = self.env["spp.program"].create({"name": f"No EM {uuid.uuid4().hex[:8]}"})
        pm = self.env["spp.program.manager.default"].create({"name": "PM", "program_id": program.id})
        with self.assertRaises(UserError):
            pm.enroll_eligible_registrants()

    def test_selection_includes_default(self):
        """Program manager selection includes default."""
        selection = self.env["spp.program.manager"]._selection_manager_ref_id()
        names = [s[0] for s in selection]
        self.assertIn("spp.program.manager.default", names)


class TestProgramModel(TransactionCase):
    """Tests for spp.program model methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env["spp.program"].create(
            {"name": f"Program Model {uuid.uuid4().hex[:8]}", "target_type": "group"}
        )

    def test_unique_program_name(self):
        """Program names must be unique."""
        with self.assertRaises(UserError):
            self.env["spp.program"].create({"name": self.program.name})

    def test_compute_has_members(self):
        """has_members is True when memberships exist."""
        self.assertFalse(self.program.has_members)
        group = self.env["res.partner"].create({"name": "Group", "is_registrant": True, "is_group": True})
        self.env["spp.program.membership"].create({"partner_id": group.id, "program_id": self.program.id})
        self.program.invalidate_recordset()
        self.assertTrue(self.program.has_members)

    def test_count_beneficiaries(self):
        """count_beneficiaries returns correct count."""
        result = self.program.count_beneficiaries()
        self.assertEqual(result["value"], 0)

    def test_count_beneficiaries_by_state(self):
        """count_beneficiaries filters by state."""
        group = self.env["res.partner"].create({"name": "G", "is_registrant": True, "is_group": True})
        self.env["spp.program.membership"].create(
            {
                "partner_id": group.id,
                "program_id": self.program.id,
                "state": "enrolled",
            }
        )
        result = self.program.count_beneficiaries(["enrolled"])
        self.assertEqual(result["value"], 1)
        result_draft = self.program.count_beneficiaries(["draft"])
        self.assertEqual(result_draft["value"], 0)

    def test_get_beneficiaries(self):
        """get_beneficiaries returns correct recordset."""
        group = self.env["res.partner"].create({"name": "G", "is_registrant": True, "is_group": True})
        self.env["spp.program.membership"].create(
            {
                "partner_id": group.id,
                "program_id": self.program.id,
                "state": "enrolled",
            }
        )
        result = self.program.get_beneficiaries("enrolled")
        self.assertEqual(len(result), 1)

    def test_get_beneficiaries_count(self):
        """get_beneficiaries with count=True returns integer."""
        result = self.program.get_beneficiaries(count=True)
        self.assertIsInstance(result, int)

    def test_get_beneficiaries_cursor_pagination(self):
        """get_beneficiaries supports cursor-based pagination."""
        result = self.program.get_beneficiaries(last_id=0, limit=10)
        self.assertEqual(len(result), 0)

    def test_open_eligible_beneficiaries_form(self):
        """open_eligible_beneficiaries_form returns action."""
        result = self.program.open_eligible_beneficiaries_form()
        self.assertEqual(result["type"], "ir.actions.act_window")

    def test_open_duplicate_membership_form(self):
        """open_duplicate_membership_form returns action."""
        result = self.program.open_duplicate_membership_form()
        self.assertIn("duplicated", str(result["domain"]))

    def test_open_cycles_form(self):
        """open_cycles_form returns action."""
        result = self.program.open_cycles_form()
        self.assertEqual(result["type"], "ir.actions.act_window")

    def test_open_program_form(self):
        """open_program_form returns action."""
        result = self.program.open_program_form()
        self.assertEqual(result["res_id"], self.program.id)

    def test_action_refresh_record(self):
        """action_refresh_record returns None so the framework triggers a
        soft model.load() (preserving breadcrumbs and dialog context)."""
        self.assertIsNone(self.program.action_refresh_record())

    def test_end_program(self):
        """end_program changes state to ended."""
        self.program.with_context(active_ids=[self.program.id]).end_program()
        self.assertEqual(self.program.state, "ended")

    def test_end_program_already_ended(self):
        """end_program shows error for already ended program."""
        self.program.write({"state": "ended"})
        result = self.program.with_context(active_ids=[self.program.id]).end_program()
        self.assertEqual(result["params"]["type"], "danger")

    def test_reactivate_program(self):
        """reactivate_program changes state back to active."""
        self.program.write({"state": "ended"})
        self.program.with_context(active_ids=[self.program.id]).reactivate_program()
        self.assertEqual(self.program.state, "active")

    def test_reactivate_active_program(self):
        """reactivate_program shows error for active program."""
        result = self.program.with_context(active_ids=[self.program.id]).reactivate_program()
        self.assertEqual(result["params"]["type"], "danger")

    def test_check_managers_limit(self):
        """Cannot have more than one program manager."""
        pm1 = self.env["spp.program.manager.default"].create({"name": "PM1", "program_id": self.program.id})
        pm2 = self.env["spp.program.manager.default"].create({"name": "PM2", "program_id": self.program.id})
        mgr1 = self.env["spp.program.manager"].create(
            {
                "program_id": self.program.id,
                "manager_ref_id": f"{pm1._name},{pm1.id}",
            }
        )
        mgr2 = self.env["spp.program.manager"].create(
            {
                "program_id": self.program.id,
                "manager_ref_id": f"{pm2._name},{pm2.id}",
            }
        )
        with self.assertRaises(UserError):
            self.program.write({"program_manager_ids": [(6, 0, [mgr1.id, mgr2.id])]})

    def test_unlink_program(self):
        """Program can be deleted with its managers."""
        program = self.env["spp.program"].create({"name": f"Delete Me {uuid.uuid4().hex[:8]}"})
        program.unlink()
        self.assertFalse(program.exists())

    def test_compute_has_compliance_criteria(self):
        """has_compliance_criteria reflects manager presence."""
        self.assertFalse(self.program.has_compliance_criteria)

    def test_get_manager_unsupported_raises(self):
        """get_manager raises for unsupported manager type."""
        with self.assertRaises(NotImplementedError):
            self.program.get_manager("unsupported_type")

    def test_get_managers_unsupported_raises(self):
        """get_managers raises for unsupported manager type."""
        with self.assertRaises(NotImplementedError):
            self.program.get_managers("unsupported_type")
