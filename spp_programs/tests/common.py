import uuid

from odoo import fields
from odoo.tests import TransactionCase


class Common(TransactionCase):
    def setUp(self):
        super().setUp()

        self.program = self.env["spp.program"].create({"name": f"Test Program {uuid.uuid4().hex[:8]}"})

        self.registrant = self.env["res.partner"].create(
            {
                "name": "test registrant",
                "is_registrant": True,
            }
        )

        self.cycle = self.env["spp.cycle"].create(
            {
                "name": "Test Cycle",
                "program_id": self.program.id,
                "start_date": fields.Date.today(),
                "end_date": fields.Date.today(),
            }
        )

        self.entitlement = self.env["spp.entitlement.inkind"].create(
            {
                "partner_id": self.registrant.id,
                "cycle_id": self.cycle.id,
            }
        )
