# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DR (Disability Registry) DCI fetch handlers.

DR handlers are partner-based: DRService.get_disability_status(partner) resolves
the identifier internally and returns a dict of disability data, from which the
flat metrics are derived. The service is mocked here.
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci.schemas.constants import RegistryType

GET_STATUS = "odoo.addons.spp_dci_client_dr.services.dr_service.DRService.get_disability_status"


@tagged("post_install", "-at_install")
class TestDCICelDRHandlers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]
        cls.dr_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "National DR",
                "code": "national_dr_t",
                "base_url": "https://dr.example.org/api",
                "registry_type": RegistryType.DISABILITY_REGISTRY.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "state": "active",
            }
        )
        cls.provider = cls.env["spp.data.provider"].create(
            {"name": "DR", "code": "national_dr_prov", "dci_data_source_id": cls.dr_source.id}
        )
        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")
        cls.partner = cls.env["res.partner"].create(
            {"name": "DR Person", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {"partner_id": cls.partner.id, "id_type_id": cls.id_code.id, "value": "NID-DR-1"}
        )

    def _var(self, accessor):
        return self.env["spp.cel.variable"].create(
            {
                "name": f"zz_{accessor}",
                "label": accessor,
                "cel_accessor": accessor,
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": self.provider.id,
                "cache_strategy": "ttl",
            }
        )

    def test_dr_has_disability_true(self):
        var = self._var("dr.dci.has_disability")
        with patch(GET_STATUS, return_value={"has_disability": True, "functional_scores": {}}):
            result = self.Fetcher.fetch_values(var, [self.partner.id])
        self.assertEqual(result, {self.partner.id: True})

    def test_dr_has_disability_false_when_no_record(self):
        var = self._var("dr.dci.has_disability")
        with patch(GET_STATUS, return_value=None):
            result = self.Fetcher.fetch_values(var, [self.partner.id])
        self.assertEqual(result, {self.partner.id: False})

    def test_dr_assessed(self):
        var = self._var("dr.dci.assessed")
        with patch(GET_STATUS, return_value={"assessment_date": "2024-11-15"}):
            self.assertEqual(self.Fetcher.fetch_values(var, [self.partner.id]), {self.partner.id: True})

    def test_dr_vision_severe_true_at_threshold(self):
        var = self._var("dr.dci.vision_severe")
        with patch(GET_STATUS, return_value={"functional_scores": {"Vision": 3}}):
            self.assertEqual(self.Fetcher.fetch_values(var, [self.partner.id]), {self.partner.id: True})

    def test_dr_vision_severe_false_below_threshold(self):
        var = self._var("dr.dci.vision_severe")
        with patch(GET_STATUS, return_value={"functional_scores": {"Vision": 2}}):
            self.assertEqual(self.Fetcher.fetch_values(var, [self.partner.id]), {self.partner.id: False})

    def test_dr_mobility_severe(self):
        var = self._var("dr.dci.mobility_severe")
        with patch(GET_STATUS, return_value={"functional_scores": {"Mobility": 4}}):
            self.assertEqual(self.Fetcher.fetch_values(var, [self.partner.id]), {self.partner.id: True})
