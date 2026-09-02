# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""SLA-breach handling is deferred out of the stored ``sla_status`` compute.

The breach hook (auto-escalation + breach chatter note) runs at the
transaction's precommit stage, not from inside ``_compute_sla_status``: the
escalation engine writes, posts to chatter and uses savepoints, none of which
may run mid-computation.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSlaBreachDeferral(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Breach Complainant"})
        cls.past = cls.env["spp.grm.ticket.category"].create({"name": "Past SLA", "default_sla_hours": -1})
        Ticket = cls.env["spp.grm.ticket"]
        cls.tickets = Ticket.create(
            [
                {"name": "b1", "description": "b1", "partner_id": cls.partner.id},
                {"name": "b2", "description": "b2", "partner_id": cls.partner.id},
            ]
        )

    def _breach_notes(self):
        return self.env["mail.message"].search_count(
            [("model", "=", "spp.grm.ticket"), ("res_id", "in", self.tickets.ids), ("subject", "=", "SLA Breach Alert")]
        )

    def test_breach_note_posted_at_precommit_for_the_whole_batch(self):
        self.env.flush_all()
        self.assertEqual(self.tickets.mapped("sla_status"), ["on_track", "on_track"])
        before = self._breach_notes()

        self.tickets.write({"category_id": self.past.id})
        self.assertEqual(self.tickets.mapped("sla_status"), ["breached", "breached"])
        # The compute ran (field read) but only scheduled the hook.
        self.assertEqual(self._breach_notes(), before)

        # cr.flush() is what commit does: pending computes, then precommit hooks.
        self.env.cr.flush()
        self.assertEqual(self._breach_notes() - before, 2)

    def test_breach_hook_runs_once_per_ticket(self):
        """Several schedulings within one transaction collapse into one run."""
        self.env.flush_all()
        before = self._breach_notes()
        self.tickets[0].write({"category_id": self.past.id})
        self.tickets[1].write({"category_id": self.past.id})
        self.env.cr.flush()
        self.assertEqual(self._breach_notes() - before, 2)
        # Nothing left queued.
        self.assertNotIn("spp_grm.sla_breach_ids", self.env.cr.precommit.data)
