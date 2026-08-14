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
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from .test_membership_constraints import MembershipCommon


@tagged("post_install", "-at_install")
class TestMembershipEndedStatusCron(MembershipCommon):
    """``_cron_recompute_ended_status`` — repair rows the clock has crossed."""

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

    def _read_stored_columns(self, rec):
        """Read ``status``/``is_ended`` straight from the SQL columns, the way
        the raw-SQL consumers of ``is_ended`` do — bypassing the ORM cache,
        which would recompute pending fields on read and mask a missing
        column write."""
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT status, is_ended FROM spp_group_membership WHERE id = %s",
            (rec.id,),
        )
        return self.env.cr.fetchone()

    def test_cron_ends_membership_the_clock_has_crossed(self):
        rec = self._make_membership(self.individual_a)
        now = fields.Datetime.now()
        self._age_row(rec, now - timedelta(days=730), now - timedelta(days=365))

        # Stale precondition: departed a year ago, still stored as active.
        self.assertEqual(self._read_stored_columns(rec), ("active", False))
        self.assertEqual(rec.status, "active")
        self.assertFalse(rec.is_ended)

        repaired = self.Membership._cron_recompute_ended_status()

        self.assertEqual(repaired, rec)
        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)
        # The SQL columns must be repaired too — four consumers read
        # is_ended in raw SQL and never see the ORM cache.
        self.assertEqual(self._read_stored_columns(rec), ("inactive", True))

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

        repaired = self.Membership._cron_recompute_ended_status()

        self.assertEqual(repaired, rec)
        self.assertEqual(rec.status, "active")
        self.assertFalse(rec.is_ended)
        self.assertEqual(self._read_stored_columns(rec), ("active", False))

    def test_cron_repairs_archived_rows(self):
        rec = self._make_membership(self.individual_a)
        now = fields.Datetime.now()
        self._age_row(rec, now - timedelta(days=730), now - timedelta(days=365), active=False)
        self.assertEqual(rec.status, "active")
        self.assertFalse(rec.is_ended)

        self.Membership._cron_recompute_ended_status()

        self.assertEqual(rec.status, "inactive")
        self.assertTrue(rec.is_ended)
        # The cron repairs the computes only; archiving stays as it was.
        self.assertFalse(rec.active)

    def test_cron_leaves_correct_rows_untouched(self):
        open_ended = self._make_membership(self.individual_a)
        past = fields.Datetime.now() - timedelta(days=365)
        already_ended = self._make_membership(
            self.individual_b,
            start_date=past - timedelta(days=1),
            ended_date=past,
        )

        repaired = self.Membership._cron_recompute_ended_status()

        # An over-matching domain would sweep these rows in; they must not
        # be selected at all, not merely end up with unchanged values.
        self.assertFalse(repaired)
        self.assertEqual(open_ended.status, "active")
        self.assertFalse(open_ended.is_ended)
        self.assertEqual(already_ended.status, "inactive")
        self.assertTrue(already_ended.is_ended)

    def test_cron_invalidates_group_metrics(self):
        rec = self._make_membership(self.individual_a)
        now = fields.Datetime.now()
        self._age_row(rec, now - timedelta(days=730), now - timedelta(days=365))

        # The recompute flushes through low-level SQL and bypasses write(),
        # so the cron must call the metric-invalidation funnel itself.
        with patch.object(
            type(self.env["res.partner"]),
            "invalidate_group_metrics",
            autospec=True,
        ) as funnel:
            self.Membership._cron_recompute_ended_status()

        funnel.assert_called_once()
        self.assertEqual(funnel.call_args.args[0], self.group)

    def test_cron_respects_batch_size(self):
        carol = self.Partner.create({"name": "Carol", "is_registrant": True, "is_group": False})
        now = fields.Datetime.now()
        rows = self.Membership.browse()
        for individual in (self.individual_a, self.individual_b, carol):
            rec = self._make_membership(individual)
            self._age_row(rec, now - timedelta(days=730), now - timedelta(days=365))
            rows |= rec

        first = self.Membership._cron_recompute_ended_status(batch_size=2)
        self.assertEqual(len(first), 2)

        second = self.Membership._cron_recompute_ended_status(batch_size=2)
        self.assertEqual(len(second), 1)
        self.assertEqual(first | second, rows)
        for rec in rows:
            self.assertEqual(rec.status, "inactive")
            self.assertTrue(rec.is_ended)

    def test_cron_record_registered(self):
        cron = self.env.ref("spp_registry.cron_recompute_membership_ended_status")
        self.assertEqual(cron.model_id.model, "spp.group.membership")
        self.assertTrue(cron.active)
        self.assertIn("_cron_recompute_ended_status", cron.code)
        self.assertEqual(cron.interval_number, 1)
        self.assertEqual(cron.interval_type, "hours")
