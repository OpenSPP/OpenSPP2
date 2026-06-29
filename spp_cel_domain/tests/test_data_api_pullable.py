# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.cel.variable.is_data_api_pullable (base rule).

Only ordinary external-provider variables may be exposed through the generic
external Data API; computed/scoring/aggregate variables must not be.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDataApiPullable(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["spp.data.provider"].create({"name": "Edu", "code": "edu_pullable_t"})

    def _var(self, accessor, source_type, provider=True):
        return self.env["spp.cel.variable"].create(
            {
                "name": f"v_{accessor}",
                "cel_accessor": accessor,
                "source_type": source_type,
                "external_provider_id": self.provider.id if provider else False,
                "value_type": "number",
            }
        )

    def test_external_with_provider_is_pullable(self):
        self.assertTrue(self._var("pa_ext", "external").is_data_api_pullable())

    def test_external_without_provider_is_not_pullable(self):
        self.assertFalse(self._var("pa_ext_np", "external", provider=False).is_data_api_pullable())

    def test_computed_is_not_pullable(self):
        self.assertFalse(self._var("pa_computed", "computed", provider=False).is_data_api_pullable())

    def test_scoring_is_not_pullable(self):
        # Scoring values (e.g. PMT) land in the same cache but must not be pulled.
        self.assertFalse(self._var("pa_scoring", "scoring", provider=False).is_data_api_pullable())
