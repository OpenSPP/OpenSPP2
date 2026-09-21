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

from datetime import timedelta

from odoo import fields
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
        """Give a test-created type the mappings its shipped counterpart has.

        When the shipped type is present (a full stack), the constants must
        match it exactly, so a drift in ``spp_cr_types_base`` shows up here
        instead of silently narrowing what these tests clear and assert.
        """
        if cr_type.apply_mapping_ids:
            shipped = {(m.source_field, m.target_field) for m in cr_type.apply_mapping_ids}
            if shipped != set(pairs):
                raise AssertionError(f"{cr_type.code}: shipped mappings drifted from the test constants")
            return
        cls.env["spp.change.request.type.mapping"].create(
            [{"type_id": cr_type.id, "source_field": source, "target_field": target} for source, target in pairs]
        )

    def _plant_future_birthdate(self, registrant):
        """Store a future date of birth the way a legacy record holds one:
        the registry constraint refuses it on write, so go under the ORM."""
        future = fields.Date.context_today(registrant) + timedelta(days=30)
        self.env.cr.execute("UPDATE res_partner SET birthdate = %s WHERE id = %s", (future, registrant.id))
        registrant.invalidate_recordset(["birthdate"])
        return future

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
        with self.assertRaisesRegex(UserError, "already been submitted for approval"):
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
        gender = self.env["spp.vocabulary.code"].search([("namespace_uri", "ilike", "gender")], limit=1)
        if gender:
            # A Many2one value: create() takes an id where write() also took a recordset.
            self.test_individual.write({"gender_id": gender.id})
        cr = self._submitted_cr_without_detail()
        detail = cr._ensure_detail()
        expected = {
            source: getattr(self.test_individual, target)
            for source, target in EDIT_INDIVIDUAL_MAPPINGS
            if getattr(self.test_individual, target)
        }
        self.assertGreaterEqual(len(expected), 4, "fixture must hold enough values for this to assert anything")
        if gender:
            self.assertEqual(detail.gender_id, gender)
        for field_name, value in expected.items():
            self.assertEqual(detail[field_name], value, field_name)

    def test_approving_a_repaired_request_changes_nothing(self):
        """End to end: apply the repaired request and the registrant is untouched."""
        before = {target: getattr(self.test_individual, target) for _source, target in EDIT_INDIVIDUAL_MAPPINGS}
        cr = self._submitted_cr_without_detail()
        cr._ensure_detail()
        cr.sudo().write({"approval_state": "approved"})

        cr.sudo().request_type_id.get_apply_strategy().apply(cr.sudo())

        after = {target: getattr(self.test_individual, target) for _source, target in EDIT_INDIVIDUAL_MAPPINGS}
        self.assertEqual(after, before)

    def test_repair_refused_when_it_would_propose_a_change(self):
        """A value the prefill declines to offer would be applied as "clear this
        field" — the field-mapping strategy writes empties on purpose. A legacy
        registrant holding a future date of birth is the shipped case: the
        prefill drops it, so the rebuilt row would clear the DOB on approval.
        The repair refuses instead, and the request keeps no detail row."""
        future = self._plant_future_birthdate(self.test_individual)
        cr = self._submitted_cr_without_detail()
        with self.assertRaisesRegex(UserError, "cannot be reconstructed without proposing a change"):
            cr._ensure_detail()
        self.assertEqual(self.test_individual.birthdate, future, "the registrant is untouched")

    def test_repair_in_draft_still_drops_a_future_birthdate(self):
        """Before submission the row is editable, so the birthdate is simply left
        empty for the user to correct — the 19.0.3.1.16 behaviour."""
        self._plant_future_birthdate(self.test_individual)
        cr = self.CR.create({"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id})
        detail = cr.get_detail()
        self.assertFalse(detail.birthdate)
        self.assertEqual(detail.given_name, self.test_individual.given_name)

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
