# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Parameterized DCI methods end-to-end: severity('type') and has_event('event').

The resolver rewrites the method call to a params-carrying metric(); the fetcher
materializes one params-keyed cache row per argument; the CEL comparison then
filters on the right argument's value.
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci.schemas.constants import RegistryType

GET_STATUS = "odoo.addons.spp_dci_client_dr.services.dr_service.DRService.get_disability_status"
CHECK_DEATH = "odoo.addons.spp_dci_client_crvs.services.crvs_service.CRVSService.check_death"
VERIFY_BIRTH = "odoo.addons.spp_dci_client_crvs.services.crvs_service.CRVSService.verify_birth"


@tagged("post_install", "-at_install")
class TestDCICelMethods(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]
        cls.Resolver = cls.env["spp.cel.variable.resolver"]
        cls.svc = cls.env["spp.cel.service"]
        cls.DV = cls.env["spp.data.value"]

        def _provider(name, code, registry_type):
            ds = cls.env["spp.dci.data.source"].create(
                {
                    "name": name,
                    "code": code,
                    "base_url": "https://reg.example.org/api",
                    "registry_type": registry_type,
                    "our_sender_id": "openspp.test",
                    "auth_type": "none",
                    "state": "active",
                }
            )
            return cls.env["spp.data.provider"].create(
                {"name": name, "code": code + "_prov", "dci_data_source_id": ds.id}
            )

        cls.dr_provider = _provider("DR", "methods_dr", RegistryType.DISABILITY_REGISTRY.value)
        cls.crvs_provider = _provider("CRVS", "methods_crvs", RegistryType.CRVS.value)

        cls.sev_var = cls.env.ref("spp_dci_indicators.var_dci_dr_severity")
        cls.sev_var.external_provider_id = cls.dr_provider
        cls.event_var = cls.env.ref("spp_dci_indicators.var_dci_crvs_has_event")
        cls.event_var.external_provider_id = cls.crvs_provider

        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")
        cls.partner = cls.env["res.partner"].create({"name": "Method Person", "is_registrant": True, "is_group": False})
        cls.env["spp.registry.id"].create(
            {"partner_id": cls.partner.id, "id_type_id": cls.id_code.id, "value": "NID-M-1"}
        )

    # ── resolver rewrite ─────────────────────────────────────────────────────

    def test_resolver_rewrites_severity_call(self):
        out = self.Resolver.expand_expression("dr.dci.severity('Vision') >= 3", context_type="individual")
        self.assertIn("metric('dr.dci.severity', me, arg='Vision')", out["expression"])

    def test_resolver_rewrites_has_event_call(self):
        out = self.Resolver.expand_expression("crvs.dci.has_event('death') == true", context_type="individual")
        self.assertIn("metric('crvs.dci.has_event', me, arg='death')", out["expression"])

    # ── materialization ──────────────────────────────────────────────────────

    def test_materialize_severity_one_row_per_type(self):
        with patch(GET_STATUS, return_value={"functional_scores": {"Vision": 4, "Hearing": 1}}):
            n = self.Fetcher.sync_for_partners([self.partner.id], variables=self.sev_var)
        self.assertEqual(n, 3)  # Vision, Hearing, Mobility
        rows = self.DV.search([("variable_name", "=", "dr.dci.severity"), ("subject_id", "=", self.partner.id)])
        self.assertEqual(len(rows), 3)

    def test_materialize_has_event_one_row_per_event(self):
        with patch(VERIFY_BIRTH, return_value={"x": 1}), patch(CHECK_DEATH, return_value=False):
            n = self.Fetcher.sync_for_partners([self.partner.id], variables=self.event_var)
        self.assertEqual(n, 2)  # birth, death

    # ── end-to-end CEL filtering ─────────────────────────────────────────────

    def _match(self, expr):
        r = self.svc.compile_expression(
            expr,
            profile="registry_individuals",
            base_domain=[("id", "in", [self.partner.id])],
            limit=0,
            materialize_sql=True,
        )
        self.assertTrue(r.get("valid"), r.get("error"))
        return self.env["res.partner"].search(r["domain"])

    def test_e2e_severity_discriminates_by_arg(self):
        with patch(GET_STATUS, return_value={"functional_scores": {"Vision": 4, "Hearing": 1}}):
            self.Fetcher.sync_for_partners([self.partner.id], variables=self.sev_var)
        self.assertIn(self.partner, self._match("dr.dci.severity('Vision') >= 3"))
        self.assertNotIn(self.partner, self._match("dr.dci.severity('Hearing') >= 3"))

    def test_e2e_has_event_death(self):
        with patch(VERIFY_BIRTH, return_value=None), patch(CHECK_DEATH, return_value=True):
            self.Fetcher.sync_for_partners([self.partner.id], variables=self.event_var)
        self.assertIn(self.partner, self._match("crvs.dci.has_event('death') == true"))
        self.assertNotIn(self.partner, self._match("crvs.dci.has_event('birth') == true"))
