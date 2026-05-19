"""DisabilityRegisterService unit tests.

Locks in:
  - New UIN -> partner + reg_id created on DR
  - Existing UIN, refresh=False -> 'skipped', partner untouched
  - Existing UIN, refresh=True  -> 'updated', partner identity rewritten
  - is_disabled=true + no prior assessment -> draft assessment created
  - is_disabled=true + prior assessment exists -> draft NOT created
  - is_disabled=false -> no assessment side effect
"""

from datetime import UTC, datetime

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci_server_disability.schemas import (
    RegisterIndividualItem,
    RegisterRequest,
)
from odoo.addons.spp_dci_server_disability.services.disability_register_service import (
    DisabilityRegisterService,
)


def _request(items, refresh_existing=False):
    return RegisterRequest(
        transaction_id="txn-1",
        register_request=items,
        refresh_existing=refresh_existing,
    )


def _item(uin, **kwargs):
    return RegisterIndividualItem(
        reference_id=f"ref-{uin}",
        uin=uin,
        name=kwargs.get("name", f"Demo {uin}"),
        given_name=kwargs.get("given_name", "Demo"),
        family_name=kwargs.get("family_name", "User"),
        is_disabled=kwargs.get("is_disabled", False),
    )


@tagged("post_install", "-at_install")
class TestDisabilityRegisterService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uin_type = cls.env.ref("spp_dci_server_disability.id_type_uin_dr")
        cls.service = DisabilityRegisterService(cls.env)

    def _make_partner_with_uin(self, uin):
        partner = self.env["res.partner"].create({"name": f"Existing {uin}", "is_registrant": True, "is_group": False})
        self.env["spp.registry.id"].create({"partner_id": partner.id, "id_type_id": self.uin_type.id, "value": uin})
        return partner

    # ------------------------------------------------------------------
    # Upsert semantics
    # ------------------------------------------------------------------

    def test_new_uin_creates_partner_and_reg_id(self):
        resp = self.service.execute_register(_request([_item("IND-NSR-REG1")]))
        self.assertEqual(len(resp.register_response), 1)
        item = resp.register_response[0]
        self.assertEqual(item.status, "succ")
        self.assertEqual(item.operation, "created")
        partner = self.env["res.partner"].browse(item.local_partner_id)
        self.assertTrue(partner.is_registrant)
        self.assertEqual(partner.given_name, "Demo")
        reg = self.env["spp.registry.id"].search(
            [("id_type_id", "=", self.uin_type.id), ("value", "=", "IND-NSR-REG1")]
        )
        self.assertEqual(reg.partner_id, partner)

    def test_existing_uin_without_refresh_is_skipped(self):
        existing = self._make_partner_with_uin("IND-NSR-REG2")
        resp = self.service.execute_register(_request([_item("IND-NSR-REG2", given_name="New")]))
        item = resp.register_response[0]
        self.assertEqual(item.operation, "skipped")
        self.assertEqual(item.local_partner_id, existing.id)
        # Partner identity untouched
        existing.invalidate_recordset()
        self.assertEqual(existing.name, "Existing IND-NSR-REG2")

    def test_existing_uin_with_refresh_overwrites_partner(self):
        existing = self._make_partner_with_uin("IND-NSR-REG3")
        resp = self.service.execute_register(
            _request(
                [_item("IND-NSR-REG3", given_name="Alex", family_name="Rivera", name="Alex Rivera")],
                refresh_existing=True,
            )
        )
        item = resp.register_response[0]
        self.assertEqual(item.operation, "updated")
        existing.invalidate_recordset()
        self.assertEqual(existing.given_name, "Alex")
        self.assertEqual(existing.family_name, "Rivera")

    # ------------------------------------------------------------------
    # Draft-assessment side effect for SR self-report
    # ------------------------------------------------------------------

    def test_is_disabled_true_with_no_prior_assessment_creates_draft(self):
        resp = self.service.execute_register(_request([_item("IND-NSR-REG4", is_disabled=True)]))
        item = resp.register_response[0]
        self.assertEqual(item.operation, "created")
        self.assertTrue(item.draft_assessment_created)

        partner = self.env["res.partner"].browse(item.local_partner_id)
        assessments = self.env["spp.disability.assessment"].search([("registrant_id", "=", partner.id)])
        self.assertEqual(len(assessments), 1)
        # Draft state, WG fields blank, has_disability still false until
        # an assessor populates the responses.
        self.assertEqual(assessments.approval_state, "draft")
        self.assertFalse(assessments.has_disability)
        # Chatter records the SR provenance — first non-tracking message.
        bodies = assessments.message_ids.mapped("body")
        self.assertTrue(
            any("Social Registry self-report" in (b or "") for b in bodies),
            f"Expected SR-provenance message; got: {bodies}",
        )

    def test_is_disabled_true_with_existing_assessment_does_not_duplicate(self):
        partner = self._make_partner_with_uin("IND-NSR-REG5")
        # Pre-existing assessment, any state — service should leave it alone.
        self.env["spp.disability.assessment"].create(
            {"registrant_id": partner.id, "assessment_date": datetime.now(UTC).date()}
        )
        resp = self.service.execute_register(_request([_item("IND-NSR-REG5", is_disabled=True)]))
        item = resp.register_response[0]
        self.assertEqual(item.operation, "skipped")
        # No second assessment created
        self.assertFalse(item.draft_assessment_created)
        assessments = self.env["spp.disability.assessment"].search([("registrant_id", "=", partner.id)])
        self.assertEqual(len(assessments), 1)

    def test_is_disabled_false_creates_no_assessment(self):
        resp = self.service.execute_register(_request([_item("IND-NSR-REG6", is_disabled=False)]))
        item = resp.register_response[0]
        self.assertEqual(item.operation, "created")
        self.assertFalse(item.draft_assessment_created)
        partner = self.env["res.partner"].browse(item.local_partner_id)
        self.assertFalse(self.env["spp.disability.assessment"].search_count([("registrant_id", "=", partner.id)]))

    def test_is_disabled_true_on_skipped_existing_partner_still_creates_draft(self):
        # When the partner is already on the DR but has no prior
        # assessment, an SR self-report should still surface them to
        # the assessor backlog — even though the upsert path is 'skipped'.
        partner = self._make_partner_with_uin("IND-NSR-REG7")
        resp = self.service.execute_register(_request([_item("IND-NSR-REG7", is_disabled=True)]))
        item = resp.register_response[0]
        self.assertEqual(item.operation, "skipped")
        self.assertTrue(item.draft_assessment_created)
        self.assertEqual(
            self.env["spp.disability.assessment"].search_count([("registrant_id", "=", partner.id)]),
            1,
        )
