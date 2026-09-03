# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import base64
import json

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_demo_child_benefit.models.demo_setup import expected_qualified_count

# 1x1 transparent PNG
PNG_1PX = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="

PACK = {
    "programme_name": "Localized Benefit Programme",
    "currency": "BTN",
    "company": {"name": "Localized Agency", "country": "BT", "logo": PNG_1PX},
    "banks": {"National Commercial Bank": "First Localized Bank"},
    "areas": {"CR": "Localized Region"},
    "mothers": ["Localized Mother A"],
    "family_name_template": "{mother_first} Family",
}


@tagged("post_install", "-at_install")
class TestDemoSettings(TransactionCase):
    """Settings-based demo management: superuser-only, idempotent, localizable."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.settings = cls.env["res.config.settings"].create({})

    def test_create_is_idempotent(self):
        # post_init already built the environment; the button must not duplicate it.
        result = self.settings.action_create_demo_environment()
        self.assertEqual(result["params"]["type"], "warning")
        self.assertEqual(self.env["spp.program"].search_count([("name", "=", "Child Benefit Programme")]), 1)

    def test_demo_actions_superuser_only(self):
        officer = self.env["res.users"].search([("login", "=", "officer")], limit=1)
        self.assertTrue(officer)
        with self.assertRaises(AccessError):
            self.settings.with_user(officer).action_create_demo_environment()
        with self.assertRaises(AccessError):
            self.settings.with_user(officer).action_apply_demo_localization()

    def test_settings_status_reflects_environment(self):
        self.assertTrue(self.settings.demo_environment_ready)
        self.assertEqual(self.settings.demo_beneficiary_count, expected_qualified_count())

    def test_localization_pack_applies_and_persists(self):
        raw = json.dumps(PACK)
        self.settings.demo_localization_file = base64.b64encode(raw.encode())
        self.settings.action_apply_demo_localization()

        Partner = self.env["res.partner"]
        self.assertTrue(self.env["spp.program"].search([("name", "=", "Localized Benefit Programme")]))
        self.assertTrue(self.env["res.bank"].search([("name", "=", "First Localized Bank")]))
        self.assertEqual(self.env["spp.area"].search([("code", "=", "CR")]).draft_name, "Localized Region")
        localized_mother = Partner.search([("name", "=", "Localized Mother A")])
        self.assertTrue(localized_mother)
        self.assertEqual(localized_mother.given_name, "Localized")
        self.assertEqual(localized_mother.family_name, "Mother A")
        self.assertTrue(Partner.search([("name", "=", "Localized Family")]))
        # Company identity and currency follow the pack; every currency the
        # demo shows (company, programme, journal, fund, cycle) agrees.
        company = self.env.company
        btn = self.env["res.currency"].search([("name", "=", "BTN")])
        self.assertTrue(btn.active)
        self.assertEqual(company.name, "Localized Agency")
        self.assertEqual(company.country_id.code, "BT")
        self.assertEqual(company.currency_id, btn)
        self.assertEqual(company.logo.decode(), PNG_1PX)
        program = self.env["spp.program"].search([("name", "=", "Localized Benefit Programme")])
        self.assertEqual(program.currency_id, btn)
        self.assertEqual(program.journal_id.currency_id, btn)
        self.assertEqual(program.cycle_ids[:1].currency_id, btn)
        self.assertEqual(self.env["spp.program.fund"].search([("program_id", "=", program.id)])[:1].currency_id, btn)

        # Pack persists beyond the transient settings record...
        fresh = self.env["res.config.settings"].create({})
        stored = fresh._stored_localization()
        self.assertEqual(json.loads(stored)["programme_name"], "Localized Benefit Programme")
        # ...and re-applying is harmless (idempotent renames find nothing).
        fresh.action_apply_demo_localization()
        self.assertEqual(self.env["spp.program"].search_count([("name", "=", "Localized Benefit Programme")]), 1)

    def test_invalid_logo_rejected(self):
        bad = dict(PACK, company={"name": "X", "logo": "not base64!!"})
        self.settings.demo_localization_file = base64.b64encode(json.dumps(bad).encode())
        with self.assertRaises(UserError):
            self.settings.action_apply_demo_localization()

    def test_apply_without_pack_raises(self):
        # Ensure no stored pack from other tests leaks in (fresh attachment scan).
        attachment = self.settings._localization_attachment()
        if attachment:
            attachment.unlink()
        with self.assertRaises(UserError):
            self.settings.action_apply_demo_localization()

    def test_invalid_pack_rejected(self):
        self.settings.demo_localization_file = base64.b64encode(b"not json at all {")
        with self.assertRaises(UserError):
            self.settings.action_apply_demo_localization()
        self.settings.demo_localization_file = base64.b64encode(b'["a","list"]')
        with self.assertRaises(UserError):
            self.settings.action_apply_demo_localization()
