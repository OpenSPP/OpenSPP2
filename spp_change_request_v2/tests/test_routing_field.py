# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""A selectable routing key may be served by more than one mapping.

For a dynamic-approval type, apply is narrowed to the field the request was
routed and approved on. That narrowing matched ``source_field`` against
``selected_field_name``, which assumed the selectable values returned by
``_get_field_to_modify_selection()`` are always physical source fields.

They need not be. A name may be offered as a single choice but stored as
separate components, so one selectable value legitimately maps to several
mappings. Matching on ``source_field`` alone matched nothing, and the request
applied nothing at all -- silently, until applying with nothing to write began
raising.

``routing_field`` lets a mapping declare the selectable value it serves. It
defaults to ``source_field``, so existing configurations are unchanged.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CRTestCase


@tagged("post_install", "-at_install")
class TestRoutingField(CRTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.registrant = cls.Partner.create(
            {
                "name": "Routing Registrant",
                "given_name": "Ann",
                "family_name": "Original",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _type(self, code, mappings):
        return self.CRType.create(
            {
                "code": code,
                "name": code,
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "use_dynamic_approval": True,
                "apply_mapping_ids": [(0, 0, m) for m in mappings],
            }
        )

    def _cr(self, cr_type, detail_vals, selected):
        cr = self.CR.create({"request_type_id": cr_type.id, "registrant_id": self.registrant.id})
        cr.get_detail().write(dict(detail_vals, field_to_modify=selected))
        # The routing selector drives apply; set it directly for fields that are
        # not in this detail model's own selection list.
        cr.selected_field_name = selected
        return cr

    # ------------------------------------------------------------------
    # One routing key, several mappings
    # ------------------------------------------------------------------

    def test_one_routing_key_can_drive_several_mappings(self):
        cr_type = self._type(
            "routing_multi",
            [
                {"source_field": "given_name", "target_field": "given_name", "routing_field": "full_name"},
                {"source_field": "family_name", "target_field": "family_name", "routing_field": "full_name"},
            ],
        )
        cr = self._cr(cr_type, {"given_name": "Beth", "family_name": "Changed"}, "full_name")

        applied = sorted(m.source_field for m in self.env["spp.cr.strategy.field_mapping"]._effective_mappings(cr))
        self.assertEqual(applied, ["family_name", "given_name"])

        self.env["spp.cr.strategy.field_mapping"].apply(cr)
        self.assertEqual(self.registrant.given_name, "Beth")
        self.assertEqual(self.registrant.family_name, "Changed")

    def test_a_different_routing_key_still_applies_nothing(self):
        """Narrowing must still hold: only what was routed may be applied."""
        cr_type = self._type(
            "routing_scope",
            [
                {"source_field": "given_name", "target_field": "given_name", "routing_field": "full_name"},
                {"source_field": "phone", "target_field": "phone"},
            ],
        )
        cr = self._cr(cr_type, {"given_name": "Beth", "phone": "12345"}, "full_name")

        applied = sorted(m.source_field for m in self.env["spp.cr.strategy.field_mapping"]._effective_mappings(cr))
        self.assertEqual(applied, ["given_name"], "a mapping for another routing key must not be applied")

        self.env["spp.cr.strategy.field_mapping"].apply(cr)
        self.assertEqual(self.registrant.given_name, "Beth")
        self.assertNotEqual(self.registrant.phone, "12345", "an unrouted mapping was applied")

    # ------------------------------------------------------------------
    # Existing configurations are unchanged
    # ------------------------------------------------------------------

    def test_source_field_is_the_default_routing_key(self):
        cr_type = self._type(
            "routing_default",
            [{"source_field": "given_name", "target_field": "given_name"}],
        )
        cr = self._cr(cr_type, {"given_name": "Beth"}, "given_name")
        applied = [m.source_field for m in self.env["spp.cr.strategy.field_mapping"]._effective_mappings(cr)]
        self.assertEqual(applied, ["given_name"])

    def test_routing_field_shadows_source_field_for_matching(self):
        """With routing_field set, the source field no longer matches."""
        cr_type = self._type(
            "routing_shadow",
            [{"source_field": "given_name", "target_field": "given_name", "routing_field": "full_name"}],
        )
        cr = self._cr(cr_type, {"given_name": "Beth"}, "given_name")
        with self.assertRaisesRegex(UserError, "no longer has a mapping"):
            cr.sudo().write({"approval_state": "approved"})
            cr.sudo()._apply_change_request()

    def test_non_dynamic_types_are_unaffected(self):
        cr_type = self.CRType.create(
            {
                "code": "routing_static",
                "name": "routing_static",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "use_dynamic_approval": False,
                "apply_mapping_ids": [
                    (0, 0, {"source_field": "given_name", "target_field": "given_name", "routing_field": "x"}),
                    (0, 0, {"source_field": "family_name", "target_field": "family_name"}),
                ],
            }
        )
        cr = self.CR.create({"request_type_id": cr_type.id, "registrant_id": self.registrant.id})
        applied = sorted(m.source_field for m in self.env["spp.cr.strategy.field_mapping"]._effective_mappings(cr))
        self.assertEqual(applied, ["family_name", "given_name"], "routing keys must not narrow a non-dynamic type")
