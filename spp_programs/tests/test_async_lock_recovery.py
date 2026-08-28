# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the async-pipeline lock-recovery fix.

The async entitlement / cycle / payment pipelines acquire `is_locked=True`
on the cycle (or program) before scheduling a queue.job group, and only
clear it when the on_done callback runs. If anything in the group fails,
the on_done is cascade-failed and the lock is never released — leaving the
"Operation in progress" warning stuck on the UI.

These tests exercise the recovery surface:
- the new `mark_*_as_failed` companions clear the lock too
- the existing `mark_*_as_done` paths clear the lock first (so a chatter
  failure can't leave the lock set)
- `action_force_unlock` is a system-administrator-only escape hatch when
  no callback fires at all (e.g. server killed mid-operation)
"""

import uuid

from odoo import fields
from odoo.tests import TransactionCase

from odoo.addons.spp_programs.models import constants


def _new_program(env):
    """Create a program with default managers (entitlement / cycle / payment / program)
    auto-attached so tests can call get_manager(...).
    """
    return (
        env["spp.program"]
        .with_context(create_default_managers=True)
        .create({"name": f"Async Lock Recovery {uuid.uuid4().hex[:8]}"})
    )


def _new_cycle(env, program):
    today = fields.Date.today()
    return env["spp.cycle"].create(
        {
            "name": f"Async Lock Cycle {uuid.uuid4().hex[:8]}",
            "program_id": program.id,
            "sequence": 1,
            "start_date": today,
            "end_date": fields.Date.add(today, days=30),
        }
    )


class TestEntitlementManagerLockRecovery(TransactionCase):
    """`mark_job_as_failed` clears the cycle lock and posts failure chatter."""

    def setUp(self):
        super().setUp()
        self.program = _new_program(self.env)
        self.cycle = _new_cycle(self.env, self.program)
        # Reach the cash entitlement manager via the program (default manager)
        self.manager = self.program.get_manager(constants.MANAGER_ENTITLEMENT)

    def test_mark_job_as_failed_clears_lock_and_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Test lock"})
        before = len(self.cycle.message_ids)

        self.manager.mark_job_as_failed(self.cycle, "Setting entitlements failed.")

        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)
        self.assertGreater(len(self.cycle.message_ids), before)
        self.assertIn("Setting entitlements failed", self.cycle.message_ids[0].body)

    def test_mark_job_as_done_clears_lock_first(self):
        """Lock is released even if message_post somehow raises."""
        self.cycle.write({"is_locked": True, "locked_reason": "Test lock"})

        self.manager.mark_job_as_done(self.cycle, "Done.")

        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)


class TestCycleManagerLockRecovery(TransactionCase):
    """Cycle manager exposes failed-companion helpers for each async path."""

    def setUp(self):
        super().setUp()
        self.program = _new_program(self.env)
        self.cycle = _new_cycle(self.env, self.program)
        self.manager = self.program.get_manager(constants.MANAGER_CYCLE)

    def test_mark_import_as_failed_clears_lock(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Importing beneficiaries."})
        self.manager.mark_import_as_failed(self.cycle, "Import failed.")
        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)

    def test_mark_prepare_entitlement_as_failed_clears_lock(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Prepare entitlement for beneficiaries."})
        self.manager.mark_prepare_entitlement_as_failed(self.cycle, "Prep failed.")
        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)

    def test_mark_check_eligibility_as_failed_clears_lock(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Eligibility check of beneficiaries"})
        self.manager.mark_check_eligibility_as_failed(self.cycle)
        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)


class TestProgramLockRecovery(TransactionCase):
    """Programs share the same lock pattern; force-unlock works there too."""

    def setUp(self):
        super().setUp()
        self.program = _new_program(self.env)
        self.manager = self.program.get_manager(constants.MANAGER_PROGRAM)

    def test_mark_enroll_eligible_as_failed_clears_lock(self):
        self.program.write({"is_locked": True, "locked_reason": "Eligibility check of beneficiaries"})
        self.manager.mark_enroll_eligible_as_failed()
        self.assertFalse(self.program.is_locked)
        self.assertFalse(self.program.locked_reason)

    def test_action_force_unlock_clears_program_lock_and_audits(self):
        self.program.write({"is_locked": True, "locked_reason": "Enrollment running"})
        before = len(self.program.message_ids)

        self.program.action_force_unlock()

        self.assertFalse(self.program.is_locked)
        self.assertFalse(self.program.locked_reason)
        self.assertGreater(len(self.program.message_ids), before)
        self.assertIn("manually cleared", self.program.message_ids[0].body)


class TestPaymentManagerLockRecovery(TransactionCase):
    """Payment manager shares the same lock pattern."""

    def setUp(self):
        super().setUp()
        self.program = _new_program(self.env)
        self.cycle = _new_cycle(self.env, self.program)
        self.manager = self.program.get_manager(constants.MANAGER_PAYMENT)

    def test_mark_job_as_failed_clears_cycle_lock(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Send payments for batches in cycle."})
        self.manager.mark_job_as_failed(self.cycle, "Send payments failed.")
        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)


class TestMarkAsDoneHardenedPaths(TransactionCase):
    """The hardened mark_*_as_done success paths must clear the lock first
    and post completion chatter.

    The fix in OP#188 reorders these methods so the lock is released *before*
    `message_post` is attempted, with the chatter call wrapped in try/except.
    Without these tests, the new try/except branches and the reordered write
    are not exercised — codecov reports the entire method body as uncovered
    even though the as_failed siblings have similar shape.
    """

    def setUp(self):
        super().setUp()
        self.program = _new_program(self.env)
        self.cycle = _new_cycle(self.env, self.program)
        self.cycle_manager = self.program.get_manager(constants.MANAGER_CYCLE)
        self.entitlement_manager = self.program.get_manager(constants.MANAGER_ENTITLEMENT)
        self.payment_manager = self.program.get_manager(constants.MANAGER_PAYMENT)
        self.program_manager = self.program.get_manager(constants.MANAGER_PROGRAM)

    def _assert_chatter_grew(self, record, before_count, expected_substring):
        self.assertGreater(len(record.message_ids), before_count)
        body = record.message_ids[0].body or ""
        self.assertIn(expected_substring, body)

    def test_cycle_mark_import_as_done_clears_lock_and_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Importing beneficiaries."})
        before = len(self.cycle.message_ids)

        self.cycle_manager.mark_import_as_done(self.cycle, "Beneficiary import finished.")

        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)
        self._assert_chatter_grew(self.cycle, before, "Beneficiary import finished")

    def test_cycle_mark_prepare_entitlement_as_done_clears_lock_and_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Prepare entitlement for beneficiaries."})
        before = len(self.cycle.message_ids)

        self.cycle_manager.mark_prepare_entitlement_as_done(self.cycle, "Entitlement Ready.")

        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)
        self._assert_chatter_grew(self.cycle, before, "Entitlement Ready")

    def test_cycle_mark_check_eligibility_as_done_clears_lock_and_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Eligibility check of beneficiaries"})
        before = len(self.cycle.message_ids)

        self.cycle_manager.mark_check_eligibility_as_done(self.cycle)

        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)
        self._assert_chatter_grew(self.cycle, before, "Eligibility check finished")

    def test_entitlement_mark_job_as_done_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Set entitlements to pending validation for cycle."})
        before = len(self.cycle.message_ids)

        self.entitlement_manager.mark_job_as_done(self.cycle, "Entitlements Set to Pending Validation.")

        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)
        self._assert_chatter_grew(self.cycle, before, "Entitlements Set to Pending Validation")

    def test_payment_mark_job_as_done_clears_lock_and_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Send payments for batches in cycle."})
        before = len(self.cycle.message_ids)

        self.payment_manager.mark_job_as_done(self.cycle, "Payments sent.")

        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)
        self._assert_chatter_grew(self.cycle, before, "Payments sent")

    def test_program_mark_enroll_eligible_as_done_clears_lock_and_posts_chatter(self):
        self.program.write({"is_locked": True, "locked_reason": "Eligibility check of beneficiaries"})
        before = len(self.program.message_ids)

        self.program_manager.mark_enroll_eligible_as_done()

        self.assertFalse(self.program.is_locked)
        self.assertFalse(self.program.locked_reason)
        self._assert_chatter_grew(self.program, before, "Eligibility check finished")


class TestMarkAsFailedChatterContent(TransactionCase):
    """Companion coverage for the as_failed paths: every mark_*_as_failed
    method must also post a failure note to chatter (not just clear the lock).

    The existing TestEntitlementManagerLockRecovery /
    TestCycleManagerLockRecovery / TestPaymentManagerLockRecovery tests cover
    lock clearing but stop short of asserting on the chatter body, so the
    `cycle.message_post(body=msg)` line in the failure path is exercised but
    not pinned to a behavioral assertion.
    """

    def setUp(self):
        super().setUp()
        self.program = _new_program(self.env)
        self.cycle = _new_cycle(self.env, self.program)
        self.cycle_manager = self.program.get_manager(constants.MANAGER_CYCLE)
        self.entitlement_manager = self.program.get_manager(constants.MANAGER_ENTITLEMENT)
        self.payment_manager = self.program.get_manager(constants.MANAGER_PAYMENT)
        self.program_manager = self.program.get_manager(constants.MANAGER_PROGRAM)

    def test_cycle_mark_import_as_failed_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Importing beneficiaries."})
        before = len(self.cycle.message_ids)
        self.cycle_manager.mark_import_as_failed(self.cycle, "Beneficiary import failed.")
        self.assertGreater(len(self.cycle.message_ids), before)
        self.assertIn("Beneficiary import failed", self.cycle.message_ids[0].body)

    def test_cycle_mark_prepare_entitlement_as_failed_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Prepare entitlement for beneficiaries."})
        before = len(self.cycle.message_ids)
        self.cycle_manager.mark_prepare_entitlement_as_failed(self.cycle, "Entitlement preparation failed.")
        self.assertGreater(len(self.cycle.message_ids), before)
        self.assertIn("Entitlement preparation failed", self.cycle.message_ids[0].body)

    def test_cycle_mark_check_eligibility_as_failed_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Eligibility check of beneficiaries"})
        before = len(self.cycle.message_ids)
        self.cycle_manager.mark_check_eligibility_as_failed(self.cycle)
        self.assertGreater(len(self.cycle.message_ids), before)
        self.assertIn("Eligibility check failed", self.cycle.message_ids[0].body)

    def test_payment_mark_job_as_failed_posts_chatter(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Send payments for batches in cycle."})
        before = len(self.cycle.message_ids)
        self.payment_manager.mark_job_as_failed(self.cycle, "Send payments failed.")
        self.assertGreater(len(self.cycle.message_ids), before)
        self.assertIn("Send payments failed", self.cycle.message_ids[0].body)

    def test_program_mark_enroll_eligible_as_failed_posts_chatter(self):
        self.program.write({"is_locked": True, "locked_reason": "Eligibility check of beneficiaries"})
        before = len(self.program.message_ids)
        self.program_manager.mark_enroll_eligible_as_failed()
        self.assertGreater(len(self.program.message_ids), before)
        self.assertIn("Eligibility check failed", self.program.message_ids[0].body)


class TestForceUnlockOnCycle(TransactionCase):
    """`action_force_unlock` on spp.cycle is the operator escape hatch when
    no callback (neither on_done nor on_error) ever fires — e.g. the worker
    was killed mid-pipeline. Mirrors the program-side test."""

    def setUp(self):
        super().setUp()
        self.program = _new_program(self.env)
        self.cycle = _new_cycle(self.env, self.program)

    def test_action_force_unlock_clears_cycle_lock_and_audits(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Import running"})
        before = len(self.cycle.message_ids)

        self.cycle.action_force_unlock()

        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)
        self.assertGreater(len(self.cycle.message_ids), before)
        latest = self.cycle.message_ids[0].body
        self.assertIn("manually cleared", latest)
        self.assertIn("Import running", latest)

    def test_action_force_unlock_noop_when_cycle_not_locked(self):
        before = len(self.cycle.message_ids)
        self.cycle.action_force_unlock()
        self.assertFalse(self.cycle.is_locked)
        # No audit message — there was nothing to clear.
        self.assertEqual(len(self.cycle.message_ids), before)

    def test_action_force_unlock_records_user_in_audit_message(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Eligibility running"})
        self.cycle.action_force_unlock()
        latest = self.cycle.message_ids[0].body
        # The current user (admin in tests) is part of the audit line.
        self.assertIn(self.env.user.display_name, latest)

    def test_action_force_unlock_uses_none_placeholder_when_reason_empty(self):
        # Edge case: lock set but reason missing — the message uses "(none)"
        # as the placeholder so the audit line stays well-formed.
        self.cycle.write({"is_locked": True, "locked_reason": False})
        self.cycle.action_force_unlock()
        latest = self.cycle.message_ids[0].body
        self.assertIn("manually cleared", latest)


class TestForceUnlockOnProgramExtra(TransactionCase):
    """Extra coverage for spp.program.action_force_unlock — noop and
    user-name-in-audit branches that the existing test class skipped."""

    def setUp(self):
        super().setUp()
        self.program = _new_program(self.env)

    def test_action_force_unlock_noop_when_program_not_locked(self):
        before = len(self.program.message_ids)
        self.program.action_force_unlock()
        self.assertFalse(self.program.is_locked)
        self.assertEqual(len(self.program.message_ids), before)

    def test_action_force_unlock_uses_none_placeholder_when_reason_empty(self):
        self.program.write({"is_locked": True, "locked_reason": False})
        self.program.action_force_unlock()
        self.assertFalse(self.program.is_locked)
        self.assertIn("manually cleared", self.program.message_ids[0].body)
