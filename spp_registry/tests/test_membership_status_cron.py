# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Cron repair of the stored ``status``/``is_ended`` computes (issue #417).

Both fields depend only on ``ended_date`` and compare it against *now*, so a
recompute fires on a write to ``ended_date`` but never when the clock crosses
it: a future-dated departure stays ``active``/``is_ended = False`` forever.
The stale state cannot be produced through the ORM (writing ``ended_date``
recomputes at write time), so these tests age rows behind the ORM's back with
raw SQL — exactly how production rows drift.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .test_membership_constraints import MembershipCommon


@tagged("post_install", "-at_install")
class TestMembershipEndedStatusCron(MembershipCommon):
    """``cron_recompute_ended_status`` — repair rows the clock has crossed."""

    def _make_membership(self, individual, **vals):
        vals.update({"group": self.group.id, "individual": individual.id})
        return self.Membership.create(vals)

    def _age_row(self, rec, start_date, ended_date, active=True):
        """Rewrite the date window (and ``active``) behind the ORM's back so
        the stored computes keep their now-wrong values."""
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE spp_group_membership SET start_date = %s, ended_date = %s, active = %s WHERE id = %s",
            (start_date, ended_date, active, rec.id),
        )
        rec.invalidate_recordset()

    def test_cron_ends_membership_the_clock_has_crossed(self):
        rec = self._make_membership(self.individual_a)
        now = fields.Datetime.now()
        self._age_row(rec, now - timedelta(days=730), now - timedelta(days=365))

        # Stale precondition: departed a year ago, still stored as active.
        self.assertEqual(rec.status, "active")
        self.assertFalse(rec.is_ended)

        self.Membership.cron_recompute_ended_status()

        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)

    def test_cron_reactivates_membership_whose_end_moved_to_future(self):
        past = fields.Datetime.now() - timedelta(days=365)
        rec = self._make_membership(
            self.individual_a,
            start_date=past - timedelta(days=1),
            ended_date=past,
        )
        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)

        # The end date is pushed to the future behind the ORM's back; the
        # stored "inactive" is now wrong in the other direction.
        future = fields.Datetime.now() + timedelta(days=365)
        self._age_row(rec, past - timedelta(days=1), future)
        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)

        self.Membership.cron_recompute_ended_status()

        self.assertEqual(rec.status, "active")
        self.assertFalse(rec.is_ended)

    def test_cron_repairs_archived_rows(self):
        rec = self._make_membership(self.individual_a)
        now = fields.Datetime.now()
        self._age_row(rec, now - timedelta(days=730), now - timedelta(days=365), active=False)
        self.assertEqual(rec.status, "active")
        self.assertFalse(rec.is_ended)

        self.Membership.cron_recompute_ended_status()

        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)

    def test_cron_leaves_correct_rows_untouched(self):
        open_ended = self._make_membership(self.individual_a)
        past = fields.Datetime.now() - timedelta(days=365)
        already_ended = self._make_membership(
            self.individual_b,
            start_date=past - timedelta(days=1),
            ended_date=past,
        )

        self.Membership.cron_recompute_ended_status()

        self.assertEqual(open_ended.status, "active")
        self.assertFalse(open_ended.is_ended)
        self.assertEqual(already_ended.status, "inactive")
        self.assertTrue(already_ended.is_ended)

    def test_cron_record_registered(self):
        cron = self.env.ref("spp_registry.cron_recompute_membership_ended_status")
        self.assertEqual(cron.model_id.model, "spp.group.membership")
        self.assertTrue(cron.active)
        self.assertIn("cron_recompute_ended_status", cron.code)
