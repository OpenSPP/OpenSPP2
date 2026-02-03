import uuid

from odoo import Command
from odoo.tests import TransactionCase


class Common(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.areas = cls.env["spp.area"].create(
            [
                {"draft_name": "Area 1 [TEST]"},
                {"draft_name": "Area 2 [TEST]"},
                {"draft_name": "Area 3 [TEST]"},
            ]
        )
        # Create tag using vocabulary code
        vocab = cls.env.ref("spp_registry.vocab_registrant_tags")
        cls._tag = cls.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": vocab.id,
                "code": "tag_1_test",
                "display": "Tag 1 [TEST]",
            }
        )
        # Create a test product for in-kind entitlements
        cls._product = cls.env["product.product"].create(
            {
                "name": "Test Product [TEST]",
                "type": "consu",
            }
        )

    @classmethod
    def program_create_wizard(cls, vals):
        base_vals = {
            "name": f"Program {uuid.uuid4().hex[:8]} [TEST]",
            "rrule_type": "monthly",
            "eligibility_domain": "[]",
            "cycle_duration": 1,
            "currency_id": cls.env.company.currency_id.id,
            "admin_area_ids": [Command.set(cls.areas.ids)],
            "entitlement_type": "cash",
            "entitlement_cash_item_ids": [Command.create({"amount": 100.0})],
        }
        base_vals.update(vals)
        return cls.env["spp.program.create.wizard"].create(base_vals)
