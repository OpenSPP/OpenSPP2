# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The protection concern is exposed on GET /Individual/{id}?_extensions=protection-concern."""

from odoo import fields
from odoo.tests import tagged

from odoo.addons.spp_api_v2.services.extension_service import ExtensionService
from odoo.addons.spp_api_v2.services.individual_service import IndividualService

from .common import PROTECTION_CONCERN_NS, PROTECTION_RISK_NS, PrimeroTestCase

EXTENSION_URL = "urn:openspp:extension:protection-concern"
EXTENSION_KEY = "protection-concern"
EXPOSED_FIELDS = {
    "protection_concern_ids",
    "protection_risk_level_id",
    "protection_urgent",
    "protection_concern_date",
    "protection_notes",
    "protection_consent_for_services",
    "protection_disclosure_other_orgs",
    "primero_referral_state",
    "primero_referred_at",
}


@tagged("post_install", "-at_install")
class TestApiExtension(PrimeroTestCase):
    def setUp(self):
        super().setUp()
        self.today = fields.Date.context_today(self.child)
        self.child.write(
            {
                "protection_concern_ids": [
                    (6, 0, (self._concern_code("street_child") | self._concern_code("disabled")).ids)
                ],
                "protection_risk_level_id": self._risk_code("high").id,
                "protection_urgent": True,
                "protection_concern_date": self.today,
                "protection_notes": "Seen sleeping at the market.",
                "protection_consent_for_services": True,
                "protection_disclosure_other_orgs": False,
            }
        )

    def test_extension_record_seeded(self):
        extension = self.env["spp.api.extension"].search([("url", "=", EXTENSION_URL)])
        self.assertEqual(len(extension), 1)
        self.assertTrue(extension.active)
        self.assertEqual(extension.applies_to, "individual")
        self.assertEqual(extension.module_id.name, "spp_primero")
        self.assertEqual(set(extension.field_ids.mapped("name")), EXPOSED_FIELDS)
        self.assertTrue(all(f.model == "res.partner" for f in extension.field_ids))

    def test_extension_output(self):
        data = ExtensionService(self.env).get_extension_data(self.child, [EXTENSION_KEY])
        self.assertIn(EXTENSION_KEY, data)
        block = data[EXTENSION_KEY]
        self.assertEqual(block["url"], EXTENSION_URL)

        concerns = block["protectionConcernIds"]
        self.assertEqual({c["coding"][0]["code"] for c in concerns}, {"street_child", "disabled"})
        self.assertTrue(all(c["coding"][0]["system"] == PROTECTION_CONCERN_NS for c in concerns))

        risk = block["protectionRiskLevel"]
        self.assertEqual(risk["coding"][0]["code"], "high")
        self.assertEqual(risk["coding"][0]["system"], PROTECTION_RISK_NS)

        self.assertIs(block["protectionUrgent"], True)
        self.assertEqual(block["protectionConcernDate"], self.today.isoformat())
        self.assertEqual(block["protectionNotes"], "Seen sleeping at the market.")
        self.assertIs(block["protectionConsentForServices"], True)
        self.assertIs(block["protectionDisclosureOtherOrgs"], False)
        self.assertEqual(block["primeroReferralState"], "none")
        self.assertNotIn("primeroRunRef", block)
        self.assertNotIn("primeroReferralError", block)

    def test_extension_omits_unset_values(self):
        self.child.write({"protection_risk_level_id": False, "protection_notes": False})
        block = ExtensionService(self.env).get_extension_data(self.child, [EXTENSION_KEY])[EXTENSION_KEY]
        self.assertNotIn("protectionRiskLevel", block)
        self.assertNotIn("protectionNotes", block)

    def test_extension_via_individual_service(self):
        individual = IndividualService(self.env).to_api_schema(self.child, extensions=[EXTENSION_KEY])
        self.assertIn(EXTENSION_KEY, individual["extension"])
        self.assertEqual(individual["extension"][EXTENSION_KEY]["protectionRiskLevel"]["coding"][0]["code"], "high")
        self.assertEqual(individual["identifier"][0]["value"], "BC-1234-5678901")

    def test_extension_included_in_wildcard(self):
        data = ExtensionService(self.env).get_extension_data(self.child, ["*"])
        self.assertIn(EXTENSION_KEY, data)
