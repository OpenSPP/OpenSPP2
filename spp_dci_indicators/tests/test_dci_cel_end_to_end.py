# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""End-to-end proof: a DCI external variable, once fetched and cached, is
usable in a real CEL expression.

Chain exercised:
  seeded variable (crvs.dci.is_alive, external, DCI-backed provider)
   -> precompute_variable -> fetcher -> CRVS check_death (mocked)
   -> cached in spp.data.value (keyed by cel_accessor)
   -> compile_expression("crvs.dci.is_alive == true") filters partners.

This nails both the name-vs-accessor cache keying and the value encoding the
comparison SQL expects.
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci.schemas.constants import RegistryType

CHECK_DEATH = "odoo.addons.spp_dci_client_crvs.services.crvs_service.CRVSService.check_death"


@tagged("post_install", "-at_install")
class TestDCICelEndToEnd(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CacheMgr = cls.env["spp.data.cache.manager"]
        cls.CelService = cls.env["spp.cel.service"]

        cls.dci_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "OpenCRVS Farajaland",
                "code": "opencrvs_e2e_t",
                "base_url": "https://crvs.example.org/api",
                "registry_type": RegistryType.CRVS.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "state": "active",
            }
        )
        cls.provider = cls.env["spp.data.provider"].create(
            {"name": "OpenCRVS", "code": "opencrvs_e2e_prov", "dci_data_source_id": cls.dci_source.id}
        )

        # Use the real seeded variable and point it at our test provider.
        cls.var = cls.env.ref("spp_dci_indicators.var_dci_crvs_is_alive")
        cls.var.external_provider_id = cls.provider

        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")
        cls.alive = cls._make_registrant("Alive Person", "NID-ALIVE")
        cls.dead = cls._make_registrant("Dead Person", "NID-DEAD")

    @classmethod
    def _make_registrant(cls, name, id_value):
        partner = cls.env["res.partner"].create({"name": name, "is_registrant": True, "is_group": False})
        cls.env["spp.registry.id"].create({"partner_id": partner.id, "id_type_id": cls.id_code.id, "value": id_value})
        return partner

    def test_variable_accessor_is_new_format(self):
        """Guard: the seeded variable uses the <registry>.dci.<metric> accessor."""
        self.assertEqual(self.var.cel_accessor, "crvs.dci.is_alive")

    def test_fetch_caches_under_accessor_key(self):
        """precompute must write spp.data.value keyed by cel_accessor (not name)."""
        with patch(CHECK_DEATH, return_value=False):
            self.CacheMgr.precompute_variable("dci.crvs.is_alive", [self.alive.id])

        cached = self.env["spp.data.value"].search(
            [("variable_name", "=", "crvs.dci.is_alive"), ("subject_id", "=", self.alive.id)]
        )
        self.assertTrue(cached, "value should be cached under the cel_accessor key")
        # Booleans are stored as 1/0 so the metric comparison SQL can cast them.
        self.assertEqual(cached.value_json, {"value": 1})
        # Nothing cached under the variable name.
        self.assertFalse(self.env["spp.data.value"].search([("variable_name", "=", "dci.crvs.is_alive")]))

    def test_cel_expression_filters_on_cached_dci_value(self):
        """The acceptance gate: a CEL expression using the DCI accessor selects
        the right partners off the cached values."""
        with patch(CHECK_DEATH, return_value=False):
            self.CacheMgr.precompute_variable("dci.crvs.is_alive", [self.alive.id])
        with patch(CHECK_DEATH, return_value=True):
            self.CacheMgr.precompute_variable("dci.crvs.is_alive", [self.dead.id])

        result = self.CelService.compile_expression(
            "crvs.dci.is_alive == true",
            profile="registry_individuals",
            base_domain=[("id", "in", [self.alive.id, self.dead.id])],
            limit=0,
            materialize_sql=True,
        )
        self.assertTrue(result.get("valid"), result.get("error"))

        matched = self.env["res.partner"].search(result["domain"])
        self.assertIn(self.alive, matched, "alive person should match crvs.dci.is_alive == true")
        self.assertNotIn(self.dead, matched, "dead person should not match")
