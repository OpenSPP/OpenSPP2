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
- `action_force_unlock` is a manager-only escape hatch when no callback
  fires at all (e.g. server killed mid-operation)
"""

import uuid

from odoo.tests import TransactionCase

from odoo.addons.spp_programs.models import constants


def _new_program(env):
    return env["spp.program"].create({"name": f"Async Lock Recovery {uuid.uuid4().hex[:8]}"})


def _new_cycle(env, program):
    return env["spp.cycle"].create(
        {
            "name": f"Async Lock Cycle {uuid.uuid4().hex[:8]}",
            "program_id": program.id,
            "sequence": 1,
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
