# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#1102: the MIS demo generator seeds country-appropriate CR document types
into the `cr_document_type` vocabulary so a type can be selected when attaching
files to a change request."""

from odoo.tests import TransactionCase, tagged

NS = "urn:openspp:vocab:cr_document_type"


@tagged("post_install", "-at_install")
class TestCrDocumentTypeSeeding(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Gen = cls.env["spp.mis.demo.generator"]
        cls.Code = cls.env["spp.vocabulary.code"]

    def _seed_for(self, country_code):
        gen = self.Gen.create({"name": f"DocTypeSeed_{country_code}", "country_code": country_code})
        stats = {}
        gen._seed_cr_document_types(stats)
        return stats

    def test_seeds_at_least_five_per_country(self):
        for country in ("phl", "lka", "tgo"):
            expected = self.Gen.CR_DOCUMENT_TYPES[country]
            self.assertGreaterEqual(len(expected), 5, f"{country}: expected >=5 document types")
            stats = self._seed_for(country)
            self.assertEqual(stats["cr_document_types_seeded"], len(expected))
            for code, _display in expected:
                self.assertTrue(
                    self.Code.search([("namespace_uri", "=", NS), ("code", "=", code)], limit=1),
                    f"{country}: document type '{code}' was not seeded",
                )

    def test_seeding_is_idempotent(self):
        self._seed_for("phl")
        count_after_first = self.Code.search_count([("namespace_uri", "=", NS)])
        self._seed_for("phl")
        count_after_second = self.Code.search_count([("namespace_uri", "=", NS)])
        self.assertEqual(count_after_first, count_after_second, "re-seeding must not duplicate codes")
