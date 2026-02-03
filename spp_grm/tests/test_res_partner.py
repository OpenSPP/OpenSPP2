from odoo.tests.common import TransactionCase


class ResPartnerTicketTests(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )
        cls.ticket = cls.env["spp.grm.ticket"].create(
            {
                "name": "Test Ticket",
                "description": "Test Description",
                "partner_id": cls.partner.id,
            }
        )

    def test_partner_ticket_relation(self):
        """Test partner has ticket in grm_ticket_ids."""
        self.assertIn(self.ticket, self.partner.grm_ticket_ids)

    def test_partner_ticket_count(self):
        """Test partner ticket count is computed correctly."""
        self.assertEqual(self.partner.grm_ticket_count, 1)

    def test_partner_active_ticket_count(self):
        """Test partner active ticket count is computed correctly."""
        self.assertEqual(self.partner.grm_ticket_active_count, 1)

    def test_partner_ticket_count_string(self):
        """Test partner ticket count string format."""
        self.assertEqual(self.partner.grm_ticket_count_string, "1 / 1")

    def test_partner_action_view_grm_tickets(self):
        """Test action to view partner's GRM tickets."""
        action = self.partner.action_view_grm_tickets()
        self.assertEqual(action["res_model"], "spp.grm.ticket")
        self.assertEqual(action["domain"], [("partner_id", "child_of", self.partner.id)])
