# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo.tests.common import TransactionCase


class TestStoryAreaMapIntegrity(TransactionCase):
    """Every STORY_AREA_MAP external ID must resolve once its country's areas load.

    The map is consumed with ``raise_if_not_found=False``, so a renamed area
    external ID silently drops story area assignments instead of failing (this
    regressed once, when the PHL areas moved to curated PSGC p-codes). This
    guard turns any future rename into a loud test failure.
    """

    _LOCALE_COUNTRY = {"fil_PH": "phl", "fr_TG": "tgo", "si_LK": "lka"}

    def test_all_story_area_xmlids_resolve(self):
        generator_model = self.env["spp.mis.demo.generator"]
        loader = self.env["spp.demo.area.loader"]
        for country in sorted(set(self._LOCALE_COUNTRY.values())):
            loader.load_country_areas(country, load_shapes=False)

        missing = []
        unknown_locales = []
        for story_id, locales in generator_model.STORY_AREA_MAP.items():
            for locale, xmlid in locales.items():
                if locale not in self._LOCALE_COUNTRY:
                    unknown_locales.append((story_id, locale))
                    continue
                if not self.env.ref(xmlid, raise_if_not_found=False):
                    missing.append((story_id, locale, xmlid))

        self.assertFalse(
            unknown_locales,
            f"STORY_AREA_MAP locales without a country mapping in this test: {unknown_locales}",
        )
        self.assertFalse(
            missing,
            "STORY_AREA_MAP references unresolvable area external IDs "
            f"(story registrants would silently lose their area): {missing}",
        )
