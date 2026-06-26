# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI CEL value fetcher and the cache-manager routing override.

The fetcher resolves a partner's identifier and calls the CRVS service against
the provider's linked DCI Data Source; the cache manager override routes
DCI-backed external variables to it. The CRVS service's network methods are
mocked - we exercise the fetch/routing/identifier logic, not real HTTP.
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci.schemas.constants import RegistryType

CHECK_DEATH = "odoo.addons.spp_dci_client_crvs.services.crvs_service.CRVSService.check_death"
VERIFY_BIRTH = "odoo.addons.spp_dci_client_crvs.services.crvs_service.CRVSService.verify_birth"


@tagged("post_install", "-at_install")
class TestDCICelFetcher(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]
        cls.CacheMgr = cls.env["spp.data.cache.manager"]

        cls.dci_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "OpenCRVS Farajaland",
                "code": "opencrvs_fetch_t",
                "base_url": "https://crvs.example.org/api",
                "registry_type": RegistryType.CRVS.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "state": "active",
            }
        )
        cls.provider = cls.env["spp.data.provider"].create(
            {
                "name": "OpenCRVS",
                "code": "opencrvs_fetch_prov",
                "dci_data_source_id": cls.dci_source.id,
            }
        )
        cls.var_is_alive = cls.env["spp.cel.variable"].create(
            {
                "name": "zz_test.crvs.is_alive",
                "label": "DCI: Is Alive",
                "cel_accessor": "r.dci.crvs.is_alive",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": cls.provider.id,
                "cache_strategy": "ttl",
            }
        )

        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")
        cls.partner = cls.env["res.partner"].create({"name": "CRVS Person", "is_registrant": True, "is_group": False})
        cls.env["spp.registry.id"].create(
            {"partner_id": cls.partner.id, "id_type_id": cls.id_code.id, "value": "NID-FETCH-1"}
        )

    # ── fetch_values ─────────────────────────────────────────────────────────

    def test_fetch_is_alive_true_when_not_dead(self):
        with patch(CHECK_DEATH, return_value=False) as m:
            result = self.Fetcher.fetch_values(self.var_is_alive, [self.partner.id])
        m.assert_called_once()
        self.assertEqual(result, {self.partner.id: True})

    def test_fetch_is_alive_false_when_dead(self):
        with patch(CHECK_DEATH, return_value=True):
            result = self.Fetcher.fetch_values(self.var_is_alive, [self.partner.id])
        self.assertEqual(result, {self.partner.id: False})

    def test_fetch_birth_verified(self):
        var = self.env["spp.cel.variable"].create(
            {
                "name": "zz_test.crvs.birth_verified",
                "label": "DCI: Birth Verified",
                "cel_accessor": "r.dci.crvs.birth_verified",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": self.provider.id,
                "cache_strategy": "ttl",
            }
        )
        with patch(VERIFY_BIRTH, return_value={"identifier_value": "X"}):
            result = self.Fetcher.fetch_values(var, [self.partner.id])
        self.assertEqual(result, {self.partner.id: True})

    def test_fetch_skips_partner_without_identifier(self):
        other = self.env["res.partner"].create({"name": "No ID", "is_registrant": True})
        with patch(CHECK_DEATH, return_value=False):
            result = self.Fetcher.fetch_values(self.var_is_alive, [other.id])
        self.assertEqual(result, {})

    def test_fetch_unknown_accessor_returns_empty(self):
        var = self.env["spp.cel.variable"].create(
            {
                "name": "zz_test.crvs.unknown",
                "label": "Unknown",
                "cel_accessor": "r.dci.crvs.not_a_metric",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": self.provider.id,
                "cache_strategy": "ttl",
            }
        )
        self.assertEqual(self.Fetcher.fetch_values(var, [self.partner.id]), {})

    def test_fetch_single_subject_failure_does_not_abort_batch(self):
        p2 = self.env["res.partner"].create({"name": "CRVS Person 2", "is_registrant": True})
        self.env["spp.registry.id"].create({"partner_id": p2.id, "id_type_id": self.id_code.id, "value": "NID-FETCH-2"})
        # First call raises, second succeeds.
        with patch(CHECK_DEATH, side_effect=[RuntimeError("boom"), False]):
            result = self.Fetcher.fetch_values(self.var_is_alive, [self.partner.id, p2.id])
        # Only the successful subject is in the result.
        self.assertEqual(result, {p2.id: True})

    # ── identifier resolution ────────────────────────────────────────────────

    def test_get_partner_identifier_returns_registry_id(self):
        ident = self.Fetcher._get_partner_identifier(self.partner)
        self.assertEqual(ident, (self.id_code.code, "NID-FETCH-1"))

    def test_get_partner_identifier_none_without_id(self):
        other = self.env["res.partner"].create({"name": "No ID 2", "is_registrant": True})
        self.assertIsNone(self.Fetcher._get_partner_identifier(other))

    # ── cache-manager routing override ───────────────────────────────────────

    def test_cache_manager_routes_dci_backed_to_fetcher(self):
        with patch(CHECK_DEATH, return_value=False):
            result = self.CacheMgr._compute_variable_values(self.var_is_alive, [self.partner.id], "current", False)
        self.assertEqual(result, {self.partner.id: True})

    # ── sync trigger ─────────────────────────────────────────────────────────

    def test_sync_for_partners_caches_values(self):
        with patch(CHECK_DEATH, return_value=False):
            count = self.Fetcher.sync_for_partners([self.partner.id], variables=self.var_is_alive)
        self.assertGreaterEqual(count, 1)
        cached = self.env["spp.data.value"].search(
            [("variable_name", "=", "r.dci.crvs.is_alive"), ("subject_id", "=", self.partner.id)]
        )
        self.assertTrue(cached)
        self.assertEqual(cached.value_json, {"value": 1})

    def test_sync_for_partners_empty_is_noop(self):
        self.assertEqual(self.Fetcher.sync_for_partners([]), 0)

    def test_dci_backed_variables_excludes_plain_providers(self):
        plain = self.env["spp.data.provider"].create({"name": "Plain", "code": "plain_excl_t"})
        self.env["spp.cel.variable"].create(
            {
                "name": "zz_plain_excl",
                "label": "Plain",
                "cel_accessor": "plain.excl",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": plain.id,
                "cache_strategy": "ttl",
            }
        )
        backed = self.Fetcher._dci_backed_variables()
        self.assertIn(self.var_is_alive, backed)
        self.assertFalse(backed.filtered(lambda v: v.cel_accessor == "plain.excl"))

    def test_cache_manager_non_dci_external_falls_back_to_super(self):
        """An external variable whose provider is NOT DCI-backed must not be
        routed to the DCI fetcher (base behaviour: returns {})."""
        plain_provider = self.env["spp.data.provider"].create({"name": "Plain", "code": "plain_prov_t"})
        var = self.env["spp.cel.variable"].create(
            {
                "name": "plain.external",
                "label": "Plain External",
                "cel_accessor": "plain.external",
                "source_type": "external",
                "value_type": "boolean",
                "external_provider_id": plain_provider.id,
                "cache_strategy": "ttl",
            }
        )
        result = self.CacheMgr._compute_variable_values(var, [self.partner.id], "current", False)
        self.assertEqual(result, {})
