# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Field-mapping transform expressions must actually be evaluated.

``_eval_expression`` passed ``nocopy=True`` to ``safe_eval``, which takes no
such argument in Odoo 19. Every expression therefore raised ``TypeError``, the
blanket fallback swallowed it, and the *untransformed* value was written to the
registrant -- so a configured transform was silently ignored and only a warning
in the log said so.
"""

from odoo.exceptions import UserError
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

    def test_a_broken_expression_falls_back_to_the_raw_value(self):
        cr_type = self._type_with_transform("tf_broken", "value.no_such_method()")
        with self.assertLogs("odoo.addons.spp_change_request_v2.strategies.field_mapping", level="ERROR") as logs:
            self._apply(cr_type, {"given_name": "jane"})
        self.assertEqual(
            self.registrant.given_name,
            "jane",
            "a failing expression falls back to the untransformed value",
        )
        self.assertTrue(
            any("transform expression failed" in line for line in logs.output),
            "the failure must be logged loudly enough to be diagnosable",
        )

    def test_env_is_not_reachable_from_an_expression(self):
        """The context deliberately omits env; keep it that way."""
        cr_type = self._type_with_transform("tf_env", "env['res.users'].search([])")
        with self.assertLogs("odoo.addons.spp_change_request_v2.strategies.field_mapping", level="ERROR"):
            self._apply(cr_type, {"given_name": "jane"})
        self.assertEqual(self.registrant.given_name, "jane")

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
