# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""A submitted change request with no detail row must still be repairable.

``detail_res_id`` is frozen once a request leaves draft, so a substituted detail
cannot be attached after approval. The guard compared old against new without
distinguishing *binding* from *re-pointing*, so the legitimate False -> id
transition was refused too. ``_ensure_detail()`` performs exactly that
transition, and the guard has no sudo exemption, so a submitted request that
never got a detail row -- a type whose ``detail_model`` was configured after the
request was created, a row lost to a cascade, a request created through the API
without one -- could not be opened from any context.

Binding is now allowed, but only to a row that already points back at this
request, so it cannot be used to attach someone else's detail.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CRTestCase, get_or_create_cr_type


@tagged("post_install", "-at_install")
class TestFrozenDetailBinding(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.edit_type = get_or_create_cr_type(cls.env, "edit_individual")

    def _submitted_cr_without_detail(self):
        cr = self.CR.create({"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id})
        cr.get_detail()  # materialise, then unbind while still in draft
        cr.write({"detail_res_id": False})
        cr.sudo().write({"approval_state": "pending"})
        return cr

    # ------------------------------------------------------------------
    # The repair path must work
    # ------------------------------------------------------------------

    def test_ensure_detail_can_bind_after_submit(self):
        cr = self._submitted_cr_without_detail()
        detail = cr._ensure_detail()
        self.assertTrue(detail, "_ensure_detail must be able to repair a submitted CR")
        self.assertTrue(cr.detail_res_id)
        self.assertEqual(detail.change_request_id, cr)

    def test_get_detail_works_after_repair(self):
        cr = self._submitted_cr_without_detail()
        cr._ensure_detail()
        self.assertTrue(cr.get_detail())

    # ------------------------------------------------------------------
    # Substitution must still be refused
    # ------------------------------------------------------------------

    def test_cannot_bind_a_detail_belonging_to_another_request(self):
        other = self.CR.create({"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id})
        foreign_detail = other.get_detail()

        cr = self._submitted_cr_without_detail()
        with self.assertRaises(UserError):
            cr.write({"detail_res_id": foreign_detail.id})

    def test_cannot_repoint_an_already_bound_detail(self):
        other = self.CR.create({"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id})
        foreign_detail = other.get_detail()

        cr = self.CR.create({"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id})
        cr.get_detail()
        cr.sudo().write({"approval_state": "pending"})
        with self.assertRaises(UserError):
            cr.write({"detail_res_id": foreign_detail.id})

    def test_cannot_clear_an_already_bound_detail(self):
        cr = self.CR.create({"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id})
        cr.get_detail()
        cr.sudo().write({"approval_state": "pending"})
        with self.assertRaises(UserError):
            cr.write({"detail_res_id": False})

    def test_other_frozen_fields_are_unaffected(self):
        cr = self._submitted_cr_without_detail()
        with self.assertRaises(UserError):
            cr.write({"selected_field_name": "given_name"})
