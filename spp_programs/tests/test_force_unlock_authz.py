# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Server-side authorization for the Force Unlock escape hatch.

The Force Unlock buttons on the cycle/program forms are gated to
``base.group_system`` in XML, but that only hides the button — Odoo lets
any user reach ``action_force_unlock`` through RPC/``call_kw``. Because
program officers, managers and cycle approvers hold write access on
``spp.program`` / ``spp.cycle``, without a server-side check they could
clear an active operation lock while async entitlement / payment /
eligibility jobs are still running. These tests pin that only system
administrators (and trusted ``sudo()`` flows) may force-unlock.
"""

import uuid

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase


def _new_program(env):
    return (
        env["spp.program"]
        .with_context(create_default_managers=True)
        .create({"name": f"Force Unlock Authz {uuid.uuid4().hex[:8]}"})
    )


def _new_cycle(env, program):
    today = fields.Date.today()
    return env["spp.cycle"].create(
        {
            "name": f"Force Unlock Authz Cycle {uuid.uuid4().hex[:8]}",
            "program_id": program.id,
            "sequence": 1,
            "start_date": today,
            "end_date": fields.Date.add(today, days=30),
        }
    )


class TestForceUnlockAuthorization(TransactionCase):
    def setUp(self):
        super().setUp()
        self.program = _new_program(self.env)
        self.cycle = _new_cycle(self.env, self.program)

        def _user(login, group_xmlids):
            groups = [self.env.ref("base.group_user")]
            groups += [self.env.ref(x) for x in group_xmlids]
            return self.env["res.users"].create(
                {
                    "name": login,
                    "login": login,
                    "group_ids": [(6, 0, [g.id for g in groups])],
                }
            )

        self.officer = _user("fu_officer", ["spp_programs.group_programs_officer"])
        self.manager = _user("fu_manager", ["spp_programs.group_programs_manager"])
        self.approver = _user("fu_approver", ["spp_programs.group_programs_cycle_approver"])
        self.system = _user("fu_system", ["base.group_system"])

    # --- cycle ---------------------------------------------------------

    def _lock_cycle(self):
        self.cycle.write({"is_locked": True, "locked_reason": "Import running"})

    def test_cycle_force_unlock_denied_for_officer(self):
        self._lock_cycle()
        with self.assertRaises(AccessError):
            self.cycle.with_user(self.officer).action_force_unlock()
        self.assertTrue(self.cycle.is_locked, "lock must remain set after a denied call")

    def test_cycle_force_unlock_denied_for_manager(self):
        self._lock_cycle()
        with self.assertRaises(AccessError):
            self.cycle.with_user(self.manager).action_force_unlock()
        self.assertTrue(self.cycle.is_locked)

    def test_cycle_force_unlock_denied_for_cycle_approver(self):
        self._lock_cycle()
        with self.assertRaises(AccessError):
            self.cycle.with_user(self.approver).action_force_unlock()
        self.assertTrue(self.cycle.is_locked)

    def test_cycle_force_unlock_allowed_for_system_admin(self):
        self._lock_cycle()
        before = len(self.cycle.message_ids)
        self.cycle.with_user(self.system).action_force_unlock()
        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)
        self.assertGreater(len(self.cycle.message_ids), before)

    def test_cycle_force_unlock_allowed_via_sudo(self):
        """Trusted server-side sudo() flows are not blocked by the guard."""
        self._lock_cycle()
        self.cycle.with_user(self.officer).sudo().action_force_unlock()
        self.assertFalse(self.cycle.is_locked)

    # --- program -------------------------------------------------------

    def test_program_force_unlock_denied_for_manager(self):
        self.program.write({"is_locked": True, "locked_reason": "Enrollment running"})
        with self.assertRaises(AccessError):
            self.program.with_user(self.manager).action_force_unlock()
        self.assertTrue(self.program.is_locked)

    def test_program_force_unlock_allowed_for_system_admin(self):
        self.program.write({"is_locked": True, "locked_reason": "Enrollment running"})
        self.program.with_user(self.system).action_force_unlock()
        self.assertFalse(self.program.is_locked)
        self.assertFalse(self.program.locked_reason)

    # --- direct field write (the sink behind action_force_unlock) ------

    def test_cycle_direct_write_is_locked_denied_for_officer(self):
        """Clearing the lock via a direct RPC write must be blocked too, not
        just the action_force_unlock button — officers hold write on the model."""
        self._lock_cycle()
        with self.assertRaises(AccessError):
            self.cycle.with_user(self.officer).write({"is_locked": False, "locked_reason": False})
        self.assertTrue(self.cycle.is_locked)

    def test_cycle_direct_write_is_locked_denied_for_manager(self):
        self._lock_cycle()
        with self.assertRaises(AccessError):
            self.cycle.with_user(self.manager).write({"is_locked": False})
        self.assertTrue(self.cycle.is_locked)

    def test_cycle_direct_write_setting_lock_denied_for_manager(self):
        """Setting the lock out of band is blocked as well (availability)."""
        with self.assertRaises(AccessError):
            self.cycle.with_user(self.manager).write({"is_locked": True, "locked_reason": "x"})
        self.assertFalse(self.cycle.is_locked)

    def test_program_direct_write_is_locked_denied_for_manager(self):
        self.program.write({"is_locked": True, "locked_reason": "Enrollment running"})
        with self.assertRaises(AccessError):
            self.program.with_user(self.manager).write({"is_locked": False})
        self.assertTrue(self.program.is_locked)

    def test_cycle_direct_write_is_locked_allowed_for_system_admin(self):
        self._lock_cycle()
        self.cycle.with_user(self.system).write({"is_locked": False, "locked_reason": False})
        self.assertFalse(self.cycle.is_locked)

    def test_manager_editing_other_fields_still_works(self):
        """The guard only covers the lock fields — normal edits by a manager
        (who holds write) must not be affected."""
        self._lock_cycle()
        # A non-lock field write by the manager succeeds even while locked.
        self.cycle.with_user(self.manager).write({"name": "Renamed [CYCLE TEST]"})
        self.assertEqual(self.cycle.name, "Renamed [CYCLE TEST]")

    # --- pipeline helpers still work for the non-admin operating user --

    def test_release_operation_lock_works_for_non_admin(self):
        """The async pipeline releases its own lock via the sudo() helper even
        though the job runs as the initiating (non-admin) user."""
        self._lock_cycle()
        self.cycle.with_user(self.officer)._release_operation_lock()
        self.assertFalse(self.cycle.is_locked)
        self.assertFalse(self.cycle.locked_reason)

    def test_acquire_operation_lock_works_for_non_admin(self):
        self.cycle.with_user(self.officer)._acquire_operation_lock("Import running")
        self.assertTrue(self.cycle.is_locked)
        self.assertEqual(self.cycle.locked_reason, "Import running")
