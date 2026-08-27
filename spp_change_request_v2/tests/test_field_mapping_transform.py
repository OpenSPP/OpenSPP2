# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Field-mapping transform expressions: evaluated, sandboxed, and fail-closed.

Covers that a configured transform is actually applied (it was once passed a
``nocopy`` kwarg ``safe_eval`` does not accept, so every expression raised and
the raw value was written), that no ORM handle -- ``env``, ``sudo()`` or the
cursor -- is reachable from an expression, that an unevaluable expression fails
closed instead of writing the requester-controlled raw value, that the failure
log does not leak the field value, and that the expression is admin-only.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestFieldMappingTransform(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Transform Registrant",
                "given_name": "john",
                "family_name": "Fam",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _type_with_transform(self, code, expression):
        return self.env["spp.change.request.type"].create(
            {
                "code": code,
                "name": code,
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "apply_mapping_ids": [
                    (
                        0,
                        0,
                        {
                            "source_field": "given_name",
                            "target_field": "given_name",
                            "transform": "expression",
                            "transform_expression": expression,
                        },
                    )
                ],
            }
        )

    def _apply(self, cr_type, detail_vals):
        cr = self.env["spp.change.request"].create({"request_type_id": cr_type.id, "registrant_id": self.registrant.id})
        cr.get_detail().write(detail_vals)
        self.env["spp.cr.strategy.field_mapping"].apply(cr)
        return cr

    def test_transform_expression_is_applied(self):
        cr_type = self._type_with_transform("tf_upper", "value.upper()")
        self._apply(cr_type, {"given_name": "jane"})
        self.assertEqual(
            self.registrant.given_name,
            "JANE",
            "the configured transform must be applied, not silently ignored",
        )

    def test_transform_can_reference_the_registrant(self):
        cr_type = self._type_with_transform("tf_ref", "value + '-' + registrant.family_name")
        self._apply(cr_type, {"given_name": "jane"})
        self.assertEqual(self.registrant.given_name, "jane-Fam")

    def test_transform_result_is_what_gets_compared(self):
        """A transform landing on the stored value means there is nothing to write."""
        cr_type = self._type_with_transform("tf_noop", "'john'")
        self._apply(cr_type, {"given_name": "jane"})
        self.assertEqual(self.registrant.given_name, "john")

    def test_a_broken_expression_fails_closed(self):
        """A transform that cannot be evaluated blocks the apply -- it must not
        fall back to writing the raw value. ``value`` is requester-controlled, so
        a fallback would let a requester force the untransformed value onto the
        registrant by feeding input the transform cannot handle."""
        cr_type = self._type_with_transform("tf_broken", "value.no_such_method()")
        with self.assertLogs("odoo.addons.spp_change_request_v2.strategies.field_mapping", level="ERROR") as logs:
            with self.assertRaises(UserError):
                self._apply(cr_type, {"given_name": "jane"})
        self.assertEqual(
            self.registrant.given_name,
            "john",
            "a failing expression must not write anything to the registrant",
        )
        self.assertTrue(
            any("transform expression failed" in line for line in logs.output),
            "the failure must be logged loudly enough to be diagnosable",
        )

    def test_the_failure_log_does_not_leak_the_field_value(self):
        """The ERROR log carries the error *type* and the expression, never the
        wrapped error text -- which embeds the (PII) field value."""
        cr_type = self._type_with_transform("tf_pii", "int(value)")
        with self.assertLogs("odoo.addons.spp_change_request_v2.strategies.field_mapping", level="ERROR") as logs:
            with self.assertRaises(UserError):
                self._apply(cr_type, {"given_name": "Juan Dela Cruz"})
        error_lines = [line for line in logs.output if line.startswith("ERROR:")]
        self.assertTrue(error_lines)
        for line in error_lines:
            self.assertNotIn("Juan Dela Cruz", line)

    def test_the_orm_is_not_reachable_from_an_expression(self):
        """``env`` alone is not the boundary: a live recordset in the context
        carries ``env``, ``sudo()`` and ``_cr`` with it, and ``safe_eval``
        permits arbitrary non-dunder attribute access. The record snapshots
        close every one of these; each fails closed rather than escaping."""
        for index, expression in enumerate(
            (
                "env['res.users'].search([])",
                "registrant.env['res.users'].search([])",
                "registrant.sudo().family_name",
                "registrant._cr",
                "detail.env.cr",
            )
        ):
            with self.subTest(expression=expression):
                cr_type = self._type_with_transform(f"tf_escape_{index}", expression)
                with self.assertLogs("odoo.addons.spp_change_request_v2.strategies.field_mapping", level="ERROR"):
                    with self.assertRaises(UserError):
                        self._apply(cr_type, {"given_name": "jane"})
                self.assertEqual(self.registrant.given_name, "john")

    def test_direct_mappings_are_unaffected(self):
        cr_type = self.env["spp.change.request.type"].create(
            {
                "code": "tf_direct",
                "name": "tf_direct",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "apply_mapping_ids": [(0, 0, {"source_field": "given_name", "target_field": "given_name"})],
            }
        )
        self._apply(cr_type, {"given_name": "jane"})
        self.assertEqual(self.registrant.given_name, "jane")

    def test_unrelated_apply_still_raises_without_a_detail(self):
        """Guard against the fallback masking a genuinely missing detail."""
        cr_type = self._type_with_transform("tf_nodetail", "value.upper()")
        cr = self.env["spp.change.request"].create({"request_type_id": cr_type.id, "registrant_id": self.registrant.id})
        cr.write({"detail_res_id": False})
        with self.assertRaises(UserError):
            self.env["spp.cr.strategy.field_mapping"].apply(cr)

    def test_cr_manager_cannot_write_transform_expression(self):
        """``transform_expression`` is admin-only (``base.group_system``). A
        Change Request Manager -- who is not a system administrator -- must not
        be able to author the server-side expression, so the "administrators
        only" warning is ORM-enforced rather than merely advisory."""
        manager = self.env["res.users"].create(
            {
                "name": "CR Manager",
                "login": "cr_manager_tf",
                "group_ids": [(4, self.env.ref("spp_change_request_v2.group_cr_manager").id)],
            }
        )
        self.assertFalse(manager._has_group("base.group_system"))
        cr_type = self._type_with_transform("tf_acl", "value.upper()")
        mapping = cr_type.apply_mapping_ids
        with self.assertRaises(AccessError):
            mapping.with_user(manager).write({"transform_expression": "value.lower()"})
