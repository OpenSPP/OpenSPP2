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

# The field mappings spp_cr_types_base ships for the two field_mapping types.
# The module's own test database has no spp_cr_types_base, so without these the
# test types carry no mappings, the detail-level freeze protects nothing but
# ``field_to_modify``, and the repair path passes here while failing on every
# real deployment.
EDIT_INDIVIDUAL_MAPPINGS = [
    ("given_name", "given_name"),
    ("family_name", "family_name"),
    ("birthdate", "birthdate"),
    ("gender_id", "gender_id"),
    ("phone", "phone"),
    ("email", "email"),
    ("address_line1", "street"),
    ("address_line2", "street2"),
    ("city", "city"),
    ("postal_code", "zip"),
]
EDIT_GROUP_MAPPINGS = [
    ("group_name", "name"),
    ("phone", "phone"),
    ("email", "email"),
    ("address_line1", "street"),
    ("address_line2", "street2"),
    ("city", "city"),
    ("postal_code", "zip"),
]


@tagged("post_install", "-at_install")
class TestFrozenDetailBinding(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.edit_type = get_or_create_cr_type(cls.env, "edit_individual")
        cls.edit_group_type = get_or_create_cr_type(cls.env, "edit_group")
        cls._ensure_mappings(cls.edit_type, EDIT_INDIVIDUAL_MAPPINGS)
        cls._ensure_mappings(cls.edit_group_type, EDIT_GROUP_MAPPINGS)

    @classmethod
    def _ensure_mappings(cls, cr_type, pairs):
        """Give a test-created type the mappings its shipped counterpart has."""
        if cr_type.apply_mapping_ids:
            return
        cls.env["spp.change.request.type.mapping"].create(
            [{"type_id": cr_type.id, "source_field": source, "target_field": target} for source, target in pairs]
        )

    def _submitted_cr_without_detail(self, cr_type=None, registrant=None):
        cr_type = cr_type or self.edit_type
        registrant = registrant or self.test_individual
        cr = self.CR.create({"request_type_id": cr_type.id, "registrant_id": registrant.id})
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
        # The repaired detail proposes what the registrant already holds, so an
        # approval applies nothing rather than clearing every mapped field.
        self.assertEqual(detail.given_name, self.test_individual.given_name)
        self.assertEqual(detail.family_name, self.test_individual.family_name)

    def test_get_detail_works_after_repair(self):
        cr = self._submitted_cr_without_detail()
        cr._ensure_detail()
        self.assertTrue(cr.get_detail())

    def test_edit_group_can_be_repaired_after_submit(self):
        """Edit Group has fully overlapping prefill and apply mappings too."""
        cr = self._submitted_cr_without_detail(self.edit_group_type, self.test_group)
        detail = cr._ensure_detail()
        self.assertTrue(detail)
        self.assertEqual(detail.group_name, self.test_group.name)

    # ------------------------------------------------------------------
    # The freeze stays absolute: the repair prefills inside create(), never by write()
    # ------------------------------------------------------------------

    def _submitted_cr_with_empty_detail(self):
        """A submitted request whose detail proposes clearing every mapped field.

        This is also the shape a repaired row would have if it were created
        empty, which is why the repair must prefill at creation: no write to a
        mapped field is accepted past submission, whatever value it carries.
        """
        cr = self.CR.create({"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id})
        detail = cr.get_detail()
        detail.write({source: False for source, _target in EDIT_INDIVIDUAL_MAPPINGS})
        cr.sudo().write({"approval_state": "pending"})
        return cr, detail

    def test_prefill_write_is_refused_after_submit(self):
        """Even the registrant's own values cannot be written onto an empty
        submitted detail: that would turn an approved "clear these fields" into
        a no-op. The repair path does not need this write (see create-time prefill)."""
        _cr, detail = self._submitted_cr_with_empty_detail()
        with self.assertRaises(UserError):
            detail.prefill_from_registrant()
        self.assertFalse(detail.given_name)

    def test_other_value_on_empty_detail_is_refused_after_submit(self):
        _cr, detail = self._submitted_cr_with_empty_detail()
        with self.assertRaises(UserError):
            detail.write({"given_name": "Someone Else"})

    def test_registrants_own_value_on_detail_with_content_is_refused(self):
        """A single cleared field cannot be restored to the registrant's value either."""
        cr = self.CR.create({"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id})
        detail = cr.get_detail()
        detail.write({"family_name": False})  # in draft: propose clearing the family name
        cr.sudo().write({"approval_state": "pending"})
        with self.assertRaises(UserError):
            detail.write({"family_name": self.test_individual.family_name})

    def test_repaired_detail_is_prefilled_without_a_write(self):
        """The repair creates the detail already populated, so a later approval
        applies nothing rather than clearing every mapped field."""
        cr = self._submitted_cr_without_detail()
        detail = cr._ensure_detail()
        expected = {
            source: getattr(self.test_individual, target)
            for source, target in EDIT_INDIVIDUAL_MAPPINGS
            if getattr(self.test_individual, target)
        }
        for field_name, value in expected.items():
            self.assertEqual(detail[field_name], value, field_name)

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
