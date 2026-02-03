from odoo.tests.common import TransactionCase


class SPPGRMTicketStageTests(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.stage = cls.env["spp.grm.ticket.stage"].create(
            {
                "name": "Test Stage",
                "sequence": 1,
                "active": True,
            }
        )

    def test_stage_creation(self):
        """Test stage creation with basic attributes."""
        new_stage = self.env["spp.grm.ticket.stage"].create(
            {
                "name": "New Stage",
                "sequence": 2,
                "active": False,
            }
        )
        self.assertEqual(new_stage.name, "New Stage")

    def test_stage_sequence_order(self):
        """Test stage sequence is set correctly."""
        self.assertEqual(self.stage.sequence, 1)

    def test_stage_active_status(self):
        """Test stage active status default."""
        self.assertTrue(self.stage.active)

    def test_stage_unattended_status(self):
        """Test stage unattended status default."""
        self.assertFalse(self.stage.unattended)

    def test_stage_closed_status(self):
        """Test stage closed status default."""
        self.assertFalse(self.stage.is_closed)

    def test_stage_folded_status(self):
        """Test stage fold status default."""
        self.assertFalse(self.stage.fold)

    def test_stage_onchange_closed(self):
        """Test stage behavior when closed is changed."""
        self.stage.write({"is_closed": True})
        self.assertFalse(self.stage.fold)
