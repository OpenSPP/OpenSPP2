# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from lxml import etree

from odoo import fields
from odoo.tests import tagged

from .common import PrimeroTestCase

CONCERN_FIELDS = {
    "protection_concern_ids": "many2many",
    "protection_risk_level_id": "many2one",
    "protection_urgent": "boolean",
    "protection_concern_date": "date",
    "protection_notes": "text",
    "protection_consent_for_services": "boolean",
    "protection_disclosure_other_orgs": "boolean",
}
REFERRAL_FIELDS = {
    "primero_referral_state": "selection",
    "primero_referred_at": "datetime",
    "primero_run_ref": "char",
    "primero_referral_error": "char",
}


@tagged("post_install", "-at_install")
class TestFieldsAndViews(PrimeroTestCase):
    def test_fields_exist_with_expected_types(self):
        for name, ttype in {**CONCERN_FIELDS, **REFERRAL_FIELDS}.items():
            with self.subTest(field=name):
                self.assertIn(name, self.Partner._fields)
                self.assertEqual(self.Partner._fields[name].type, ttype)

    def test_vocabulary_fields_target_vocabulary_codes(self):
        self.assertEqual(self.Partner._fields["protection_concern_ids"].comodel_name, "spp.vocabulary.code")
        self.assertEqual(self.Partner._fields["protection_risk_level_id"].comodel_name, "spp.vocabulary.code")

    def test_referral_fields_are_not_copied(self):
        for name in REFERRAL_FIELDS:
            with self.subTest(field=name):
                self.assertFalse(self.Partner._fields[name].copy)

    def test_referral_state_defaults_to_none(self):
        self.assertEqual(self.child.primero_referral_state, "none")
        self.assertFalse(self.child.primero_referred_at)
        self.assertFalse(self.child.primero_run_ref)

    def test_concern_roundtrip(self):
        today = fields.Date.context_today(self.child)
        self.child.write(
            {
                "protection_concern_ids": [(6, 0, self._concern_code("street_child").ids)],
                "protection_risk_level_id": self._risk_code("high").id,
                "protection_urgent": True,
                "protection_concern_date": today,
                "protection_notes": "Seen sleeping at the market.",
                "protection_consent_for_services": True,
                "protection_disclosure_other_orgs": True,
            }
        )
        self.assertEqual(self.child.protection_concern_ids.mapped("code"), ["street_child"])
        self.assertEqual(self.child.protection_risk_level_id.code, "high")
        self.assertTrue(self.child.protection_urgent)
        self.assertEqual(self.child.protection_concern_date, today)

    def test_individual_form_has_button_and_tab(self):
        view = self.env.ref("spp_registry.view_individuals_form")
        arch = etree.fromstring(self.Partner.get_view(view.id, "form")["arch"])
        buttons = arch.xpath("//button[@name='action_refer_to_primero']")
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].get("type"), "object")
        pages = arch.xpath("//page[@name='protection']")
        self.assertEqual(len(pages), 1)
        for name in CONCERN_FIELDS:
            with self.subTest(field=name):
                self.assertTrue(pages[0].xpath(f".//field[@name='{name}']"), f"{name} missing from Protection tab")
        self.assertTrue(pages[0].xpath(".//field[@name='primero_referral_state']"))

    def test_refer_button_hidden_from_viewer(self):
        """The button is group-gated: a registry viewer's form does not render it (the tab still does)."""
        view = self.env.ref("spp_registry.view_individuals_form")
        arch = etree.fromstring(self.Partner.with_user(self.viewer).get_view(view.id, "form")["arch"])
        self.assertFalse(arch.xpath("//button[@name='action_refer_to_primero']"))
        self.assertTrue(arch.xpath("//page[@name='protection']"))

    def test_refer_button_rendered_for_officer(self):
        view = self.env.ref("spp_registry.view_individuals_form")
        arch = etree.fromstring(self.Partner.with_user(self.officer).get_view(view.id, "form")["arch"])
        self.assertEqual(len(arch.xpath("//button[@name='action_refer_to_primero']")), 1)
