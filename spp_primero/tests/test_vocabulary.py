# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests import tagged

from .common import PROTECTION_CONCERN_NS, PROTECTION_RISK_NS, PrimeroTestCase

# Primero's stock ``lookup-protection-concerns`` ids, in Primero's order.
PRIMERO_PROTECTION_CONCERNS = [
    "sexually_exploited",
    "gbv_survivor",
    "trafficked_smuggled",
    "statelessness",
    "arrested_detained",
    "migrant",
    "disabled",
    "serious_health_issue",
    "refugee",
    "caafag",
    "street_child",
    "child_mother",
    "physically_or_mentally_abused",
    "living_with_vulnerable_person",
    "worst_forms_of_child_labor",
    "child_headed_household",
    "mentally_distressed",
    "other",
]


@tagged("post_install", "-at_install")
class TestVocabulary(PrimeroTestCase):
    def _vocabulary(self, namespace_uri):
        return self.env["spp.vocabulary"].search([("namespace_uri", "=", namespace_uri)])

    def test_concern_vocabulary_seeded(self):
        vocab = self._vocabulary(PROTECTION_CONCERN_NS)
        self.assertEqual(len(vocab), 1)
        self.assertTrue(vocab.is_system)
        codes = self.Code.search([("vocabulary_id", "=", vocab.id)], order="sequence, id")
        self.assertEqual(codes.mapped("code"), PRIMERO_PROTECTION_CONCERNS)
        self.assertTrue(all(codes.mapped("display")))

    def test_concern_code_uri(self):
        street_child = self._concern_code("street_child")
        self.assertEqual(street_child.uri, f"{PROTECTION_CONCERN_NS}#street_child")

    def test_risk_level_vocabulary_seeded(self):
        vocab = self._vocabulary(PROTECTION_RISK_NS)
        self.assertEqual(len(vocab), 1)
        codes = self.Code.search([("vocabulary_id", "=", vocab.id)], order="sequence, id")
        self.assertEqual(codes.mapped("code"), ["high", "medium", "low"])
