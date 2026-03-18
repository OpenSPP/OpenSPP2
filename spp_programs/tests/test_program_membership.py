# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import uuid

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestProgramMembership(TransactionCase):
    """Tests for spp.program.membership model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.program = cls.env["spp.program"].create(
            {"name": f"Membership Test {uuid.uuid4().hex[:8]}", "target_type": "group"}
        )

        # Create eligibility manager so enrollment works
        manager_default = cls.env["spp.program.membership.manager.default"].create(
            {"name": "Default", "program_id": cls.program.id}
        )
        eligibility_manager = cls.env["spp.eligibility.manager"].create(
            {
                "program_id": cls.program.id,
                "manager_ref_id": f"{manager_default._name},{manager_default.id}",
            }
        )
        cls.program.write({"eligibility_manager_ids": [(4, eligibility_manager.id)]})

        cls.group = cls.env["res.partner"].create({"name": "Test Group", "is_registrant": True, "is_group": True})

    def _create_membership(self, partner=None, state="draft"):
        partner = partner or self.group
        return self.env["spp.program.membership"].create(
            {
                "partner_id": partner.id,
                "program_id": self.program.id,
                "state": state,
            }
        )

    def test_unique_partner_per_program(self):
        """Cannot have duplicate memberships for same partner+program."""
        self._create_membership()
        with self.assertRaises(ValidationError):
            self._create_membership()

    def test_enrollment_date_set_on_enrolled(self):
        """Enrollment date is set when state becomes enrolled."""
        membership = self._create_membership(state="enrolled")
        self.assertTrue(membership.enrollment_date)

    def test_duplicate_reason_computed(self):
        """Duplicate reason shows the reason from the duplicate record."""
        membership = self._create_membership(state="duplicated")
        self.env["spp.program.membership.duplicate"].create(
            {
                "beneficiary_ids": [(6, 0, [membership.id])],
                "state": "duplicate",
                "reason": "Test duplicate reason",
                "deduplication_manager_id": 1,
            }
        )
        membership.invalidate_recordset()
        self.assertEqual(membership.duplicate_reason, "Test duplicate reason")

    def test_duplicate_reason_empty_when_not_duplicated(self):
        """Duplicate reason is False when state is not duplicated."""
        membership = self._create_membership(state="enrolled")
        self.assertFalse(membership.duplicate_reason)

    def test_enroll_prevents_duplicated_state(self):
        """Cannot enroll a beneficiary that is in duplicated state."""
        membership = self._create_membership(state="duplicated")
        result = membership.enroll_eligible_registrants()
        self.assertEqual(result["params"]["type"], "warning")
        self.assertIn("duplicated", result["params"]["message"].lower())
        membership.invalidate_recordset()
        self.assertEqual(membership.state, "duplicated")

    def test_enroll_prevents_exited_state(self):
        """Cannot enroll a beneficiary that is in exited state."""
        membership = self._create_membership(state="exited")
        result = membership.enroll_eligible_registrants()
        self.assertEqual(result["params"]["type"], "warning")
        membership.invalidate_recordset()
        self.assertEqual(membership.state, "exited")

    def test_enroll_already_enrolled_shows_info(self):
        """Enrolling an already enrolled beneficiary shows info message."""
        membership = self._create_membership(state="enrolled")
        result = membership.enroll_eligible_registrants()
        self.assertEqual(result["params"]["type"], "info")

    def test_verify_eligibility_marks_not_eligible(self):
        """verify_eligibility marks as not_eligible when no match."""
        # Create individual (won't match group target_type eligibility)
        individual = self.env["res.partner"].create(
            {
                "name": "Individual Wrong Type",
                "is_registrant": True,
                "is_group": False,
            }
        )
        ind_membership = self.env["spp.program.membership"].create(
            {
                "partner_id": individual.id,
                "program_id": self.program.id,
            }
        )
        ind_membership.verify_eligibility()
        self.assertEqual(ind_membership.state, "not_eligible")

    def test_back_to_draft(self):
        """Back to draft resets state."""
        membership = self._create_membership(state="not_eligible")
        membership.back_to_draft()
        self.assertEqual(membership.state, "draft")

    def test_action_pause(self):
        """Pausing an enrolled membership."""
        membership = self._create_membership(state="enrolled")
        membership.action_pause()
        self.assertEqual(membership.state, "paused")

    def test_action_pause_non_enrolled_raises(self):
        """Cannot pause a non-enrolled membership."""
        membership = self._create_membership(state="draft")
        with self.assertRaises(UserError):
            membership.action_pause()

    def test_action_resume(self):
        """Resuming a paused membership."""
        membership = self._create_membership(state="paused")
        membership.action_resume()
        self.assertEqual(membership.state, "enrolled")

    def test_action_resume_non_paused_raises(self):
        """Cannot resume a non-paused membership."""
        membership = self._create_membership(state="enrolled")
        with self.assertRaises(UserError):
            membership.action_resume()

    def test_action_exit(self):
        """Exiting an enrolled membership."""
        membership = self._create_membership(state="enrolled")
        membership.action_exit()
        self.assertEqual(membership.state, "exited")
        self.assertEqual(membership.exit_date, fields.Date.today())

    def test_action_exit_non_enrolled_raises(self):
        """Cannot exit a draft membership."""
        membership = self._create_membership(state="draft")
        with self.assertRaises(UserError):
            membership.action_exit()

    def test_open_beneficiaries_form(self):
        """open_beneficiaries_form returns an action."""
        membership = self._create_membership()
        result = membership.open_beneficiaries_form()
        self.assertEqual(result["res_model"], "spp.program.membership")
        self.assertEqual(result["res_id"], membership.id)

    def test_open_registrant_form_group(self):
        """open_registrant_form returns an action for groups."""
        membership = self._create_membership()
        result = membership.open_registrant_form()
        self.assertEqual(result["res_model"], "res.partner")
        self.assertEqual(result["res_id"], self.group.id)

    def test_open_registrant_form_individual(self):
        """open_registrant_form returns an action for individuals."""
        individual = self.env["res.partner"].create({"name": "Individual", "is_registrant": True, "is_group": False})
        ind_program = self.env["spp.program"].create(
            {
                "name": f"Ind Program {uuid.uuid4().hex[:8]}",
                "target_type": "individual",
            }
        )
        membership = self.env["spp.program.membership"].create(
            {"partner_id": individual.id, "program_id": ind_program.id}
        )
        result = membership.open_registrant_form()
        self.assertEqual(result["res_model"], "res.partner")
        self.assertEqual(result["res_id"], individual.id)

    def test_display_name(self):
        """display_name is set on membership."""
        membership = self._create_membership()
        self.assertTrue(membership.display_name)

    def test_deduplicate_from_membership(self):
        """Deduplication can be triggered from membership."""
        membership = self._create_membership()

        # Set up deduplication manager
        dedup_default = self.env["spp.deduplication.manager.default"].create(
            {"name": "Default Dedup", "program_id": self.program.id}
        )
        dedup_manager = self.env["spp.deduplication.manager"].create(
            {
                "program_id": self.program.id,
                "manager_ref_id": f"{dedup_default._name},{dedup_default.id}",
            }
        )
        self.program.write({"deduplication_manager_ids": [(4, dedup_manager.id)]})

        result = membership.deduplicate_beneficiaries()
        self.assertEqual(result["tag"], "display_notification")

    def test_deduplicate_no_manager_raises(self):
        """Deduplication raises error when no manager is set."""
        program_no_dedup = self.env["spp.program"].create({"name": f"No Dedup {uuid.uuid4().hex[:8]}"})
        membership = self.env["spp.program.membership"].create(
            {"partner_id": self.group.id, "program_id": program_no_dedup.id}
        )
        with self.assertRaises(UserError):
            membership.deduplicate_beneficiaries()

    def test_get_view_form_group_context(self):
        """_get_view applies group domain in context."""
        Membership = self.env["spp.program.membership"].with_context(target_type="group")
        arch, view = Membership._get_view(view_type="form")
        self.assertIn("is_group", arch)

    def test_get_view_form_individual_context(self):
        """_get_view applies individual domain in context."""
        Membership = self.env["spp.program.membership"].with_context(target_type="individual")
        arch, view = Membership._get_view(view_type="form")
        self.assertIn("is_group", arch)
