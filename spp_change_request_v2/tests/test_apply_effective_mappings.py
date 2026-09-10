# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Applying a change request that can write nothing must fail, not report success.

``_effective_mappings`` fails closed: for a dynamic-approval type it narrows to
the single routed field, and yields nothing if that field lost its mapping or
none was ever configured. The apply strategy returned ``True`` regardless, so
the request was stamped applied -- with ``applied_date``, an audit event and a
log line -- having written nothing. Operators saw a green, applied request whose
change had been silently dropped.

A genuine no-op is different and stays allowed: when the mappings exist and the
registrant already holds the proposed values there is nothing to write, and the
request is correctly recorded as applied.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CRTestCase


@tagged("post_install", "-at_install")
class TestApplyEffectiveMappings(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrant = cls.Partner.create(
            {
                "name": "Apply Scope Registrant",
                "given_name": "Orig",
                "family_name": "OrigFam",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _make_type(self, code, dynamic=True, with_mapping=True):
        vals = {
            "code": code,
            "name": code,
            "target_type": "individual",
            "detail_model": "spp.cr.detail.edit_individual",
            "apply_strategy": "field_mapping",
            "use_dynamic_approval": dynamic,
        }
        if with_mapping:
            vals["apply_mapping_ids"] = [
                (0, 0, {"source_field": "given_name", "target_field": "given_name"}),
            ]
        return self.CRType.create(vals)

    def _approved_cr(self, cr_type, detail_vals, selected="given_name"):
        cr = self.CR.create({"request_type_id": cr_type.id, "registrant_id": self.registrant.id})
        detail = cr.get_detail()
        vals = dict(detail_vals)
        if cr_type.use_dynamic_approval:
            vals["field_to_modify"] = selected
        detail.write(vals)
        cr.sudo().write({"approval_state": "approved"})
        return cr

    # ------------------------------------------------------------------
    # Must fail: nothing can be written
    # ------------------------------------------------------------------

    def test_routed_field_lost_its_mapping(self):
        cr_type = self._make_type("apply_scope_lost_mapping")
        cr = self._approved_cr(cr_type, {"given_name": "Changed"})
        cr_type.apply_mapping_ids.unlink()

        with self.assertRaisesRegex(UserError, "no longer has a mapping"):
            cr.sudo()._apply_change_request()

        self.assertFalse(cr.is_applied, "a request that wrote nothing must not be stamped applied")
        self.assertFalse(cr.applied_date)
        cr.invalidate_recordset(["apply_error"])
        self.assertTrue(cr.apply_error, "the failure must be recorded on the request")
        self.assertEqual(self.registrant.given_name, "Orig")

    def test_dynamic_type_with_no_selected_field(self):
        cr_type = self._make_type("apply_scope_unrouted")
        cr = self.CR.create({"request_type_id": cr_type.id, "registrant_id": self.registrant.id})
        cr.get_detail().write({"given_name": "Changed"})
        cr.sudo().write({"approval_state": "approved"})
        self.assertFalse(cr.selected_field_name, "probe assumes the request was never routed")

        with self.assertRaisesRegex(UserError, "no field mapping to apply"):
            cr.sudo()._apply_change_request()
        self.assertFalse(cr.is_applied)

    def test_type_with_no_mappings_configured(self):
        cr_type = self._make_type("apply_scope_no_mappings", dynamic=False, with_mapping=False)
        cr = self._approved_cr(cr_type, {"given_name": "Changed"})

        with self.assertRaisesRegex(UserError, "no field mapping to apply"):
            cr.sudo()._apply_change_request()
        self.assertFalse(cr.is_applied)

    # ------------------------------------------------------------------
    # Must still succeed
    # ------------------------------------------------------------------

    def test_normal_apply_still_works(self):
        cr_type = self._make_type("apply_scope_ok")
        cr = self._approved_cr(cr_type, {"given_name": "Changed"})
        cr.sudo()._apply_change_request()
        self.assertTrue(cr.is_applied)
        self.assertEqual(self.registrant.given_name, "Changed")

    def test_genuine_no_op_is_not_an_error(self):
        """Mappings exist, the registrant already holds the value: nothing to write."""
        cr_type = self._make_type("apply_scope_noop")
        cr = self._approved_cr(cr_type, {"given_name": self.registrant.given_name})
        cr.sudo()._apply_change_request()
        self.assertTrue(cr.is_applied, "a real no-op is legitimately applied")
        self.assertFalse(cr.apply_error)
