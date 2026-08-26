# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The post-submit freeze must not reject a payload that changes nothing.

Both freeze guards -- the one on ``spp.change.request`` for its routing fields
and the one on every ``spp.cr.detail.*`` model for its proposed-change fields --
compare an incoming write payload against the stored value. Odoo stores an unset
Char as ``False``, but a JSON-RPC client or integration re-saving a record sends
``""``. Normalising only ``None`` left ``""`` looking like a real change, so an
idempotent re-save was rejected with the lockout error as though it had altered
the approved content.

Both guards share one normalisation helper, so this cannot be fixed on one side
and missed on the other.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..models.frozen_value import normalize_frozen_value
from .common import CRTestCase, get_or_create_cr_type


@tagged("post_install", "-at_install")
class TestFrozenValueNormalisation(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.edit_type = get_or_create_cr_type(cls.env, "edit_individual")

    # ------------------------------------------------------------------
    # The helper itself
    # ------------------------------------------------------------------

    def test_unset_representations_all_normalise_together(self):
        for value in (None, False, ""):
            self.assertIs(
                normalize_frozen_value(value),
                False,
                f"{value!r} must normalise to the stored representation of unset",
            )

    def test_recordset_normalises_to_its_id(self):
        self.assertEqual(normalize_frozen_value(self.test_individual), self.test_individual.id)

    def test_real_values_are_preserved(self):
        self.assertEqual(normalize_frozen_value("Jane"), "Jane")
        self.assertEqual(normalize_frozen_value(7), 7)
        self.assertIs(normalize_frozen_value(True), True)

    def test_zero_is_not_treated_as_unset(self):
        """``0`` is a real value; only None/False/'' mean unset."""
        self.assertEqual(normalize_frozen_value(0), 0)

    # ------------------------------------------------------------------
    # The CR-level guard
    # ------------------------------------------------------------------

    def test_empty_string_for_an_unset_frozen_field_is_accepted(self):
        cr = self.CR.create(
            {"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id}
        )
        cr.sudo().write({"approval_state": "pending"})
        self.assertFalse(cr.selected_field_old_value, "test assumes the field is unset")
        # An integration re-saving the record sends "" for the empty Char.
        cr.write({"selected_field_old_value": ""})
        self.assertFalse(cr.selected_field_old_value)

    def test_a_real_change_to_a_frozen_field_is_still_rejected(self):
        cr = self.CR.create(
            {"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id}
        )
        cr.sudo().write({"approval_state": "pending"})
        with self.assertRaises(UserError):
            cr.write({"selected_field_old_value": "something else"})

    def test_clearing_a_populated_frozen_field_is_still_rejected(self):
        """'' must read as unset, not as a licence to clear a set value."""
        cr = self.CR.create(
            {"request_type_id": self.edit_type.id, "registrant_id": self.test_individual.id}
        )
        cr.write({"selected_field_old_value": "Original"})
        cr.sudo().write({"approval_state": "pending"})
        with self.assertRaises(UserError):
            cr.write({"selected_field_old_value": ""})
