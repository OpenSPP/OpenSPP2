# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase


class DrimsTestCommon(TransactionCase):
    """Common test class for DRIMS tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Get vocabulary codes
        cls.vocab_code = cls.env["spp.vocabulary.code"]
        cls.priority_routine = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:priority-levels",
                ),
                ("code", "=", "routine"),
            ],
            limit=1,
        )
        cls.priority_critical = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:priority-levels",
                ),
                ("code", "=", "critical"),
            ],
            limit=1,
        )
        cls.state_draft = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:request-states",
                ),
                ("code", "=", "draft"),
            ],
            limit=1,
        )
        cls.state_donation_draft = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:donation-states",
                ),
                ("code", "=", "draft"),
            ],
            limit=1,
        )
        cls.state_announced = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:donation-states",
                ),
                ("code", "=", "announced"),
            ],
            limit=1,
        )
        cls.condition_new = cls.vocab_code.search(
            [
                (
                    "vocabulary_id.namespace_uri",
                    "=",
                    "urn:openspp:vocab:drims:item-conditions",
                ),
                ("code", "=", "new"),
            ],
            limit=1,
        )

        # Create test warehouse
        cls.warehouse = cls.env["stock.warehouse"].create(
            {
                "name": "Test DRIMS Warehouse",
                "code": "TDRIMS",
                "is_drims_warehouse": True,
            }
        )

        # Create hazard category for test incident
        cls.hazard_category = cls.env["spp.hazard.category"].create(
            {
                "name": "Flood",
                "code": "flood",
            }
        )

        # Create test incident
        cls.incident = cls.env["spp.hazard.incident"].create(
            {
                "name": "Test Flood 2024",
                "code": "FLOOD-2024-TEST",
                "category_id": cls.hazard_category.id,
                "start_date": "2024-01-01",
                "status": "active",
            }
        )

        # Create test area
        cls.area = cls.env["spp.area"].create(
            {
                "name": "Test District",
                "draft_name": "Test District",
            }
        )

        # Create test product (Odoo 19: type='consu' + is_storable=True for trackable goods)
        cls.product = cls.env["product.product"].create(
            {
                "name": "Test Relief Item",
                "type": "consu",
                "is_storable": True,  # Required for stock quant tracking
                "standard_price": 100.0,
            }
        )

    def _receive_donation(self, donation, received=None):
        """Advance a donation to the 'received' state via the OP#1076 flow.

        The lifecycle is draft -> announced -> received. Received quantities
        are entered manually post-OP#1076 (no auto-copy from pledged), so this
        helper fills any line that has no received quantity with its pledged
        quantity — preserving the pre-OP#1076 received==pledged expectation —
        then marks the donation received (which creates the receipt picking).
        """
        if donation.state == "draft":
            donation.action_mark_announced()
        for line in donation.line_ids:
            if line.quantity_received <= 0:
                line.quantity_received = received if received is not None else line.quantity_pledged
        donation.action_mark_received()
        return donation
