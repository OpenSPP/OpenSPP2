# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the SR (Social Registry) DCI fetch handlers.

All six r.dci.sr.* metrics derive from a single person record returned by
SRService.search_person (identifiers -> registration, enrolled_programs,
household_info). The service is mocked here.

Semantics: every metric returns a value for every queried person - the CEL
SQL fast path requires a complete cache (a row per candidate). A person not
found in the SR yields the semantic defaults: not registered, 0 programs,
household size 0, not a head, not a large household.
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci.schemas.constants import RegistryType

SEARCH_PERSON = "odoo.addons.spp_dci_client_sr.services.sr_service.SRService.search_person"


@tagged("post_install", "-at_install")
class TestDCICelSRHandlers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Fetcher = cls.env["spp.dci.cel.fetcher"]
        cls.sr_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "National SR",
                "code": "national_sr_t",
                "base_url": "https://sr.example.org/api",
                "registry_type": RegistryType.SOCIAL_REGISTRY.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "state": "active",
            }
        )
        cls.provider = cls.env["spp.data.provider"].create(
            {"name": "SR", "code": "national_sr_prov", "dci_data_source_id": cls.sr_source.id}
        )
        cls.id_code = cls.env.ref("spp_vocabulary.code_id_type_national_id")
        cls.partner = cls.env["res.partner"].create({"name": "SR Person", "is_registrant": True, "is_group": False})
        cls.env["spp.registry.id"].create(
            {"partner_id": cls.partner.id, "id_type_id": cls.id_code.id, "value": "NID-SR-1"}
        )

    def _var(self, accessor, value_type="boolean"):
        # One variable per accessor: spp.cel.variable enforces UNIQUE
        # (cel_accessor, applies_to), so repeat fetches reuse the record.
        if not hasattr(self, "_vars"):
            self._vars = {}
        if accessor not in self._vars:
            self._vars[accessor] = self.env["spp.cel.variable"].create(
                {
                    "name": f"zz_{accessor}",
                    "label": accessor,
                    "cel_accessor": accessor,
                    "source_type": "external",
                    "value_type": value_type,
                    "external_provider_id": self.provider.id,
                    "cache_strategy": "ttl",
                }
            )
        return self._vars[accessor]

    def _fetch(self, accessor, person, value_type="boolean"):
        var = self._var(accessor, value_type=value_type)
        with patch(SEARCH_PERSON, return_value=person):
            return self.Fetcher.fetch_values(var, [self.partner.id])

    # -- is_registered ---------------------------------------------------------

    def test_sr_is_registered_true(self):
        result = self._fetch("r.dci.sr.is_registered", {"id": "EXT-1", "name": "SR Person"})
        self.assertEqual(result, {self.partner.id: True})

    def test_sr_is_registered_false_when_not_found(self):
        result = self._fetch("r.dci.sr.is_registered", None)
        self.assertEqual(result, {self.partner.id: False})

    # -- programmes ------------------------------------------------------------

    def test_sr_program_count(self):
        person = {"enrolled_programs": [{"programme_name": "A"}, {"programme_name": "B"}]}
        result = self._fetch("r.dci.sr.program_count", person, value_type="number")
        self.assertEqual(result, {self.partner.id: 2})

    def test_sr_program_count_zero_without_enrollments(self):
        result = self._fetch("r.dci.sr.program_count", {"id": "EXT-1"}, value_type="number")
        self.assertEqual(result, {self.partner.id: 0})

    def test_sr_program_count_zero_when_not_found(self):
        """Not found in SR -> 0 programs (a value, so the cache stays complete)."""
        result = self._fetch("r.dci.sr.program_count", None, value_type="number")
        self.assertEqual(result, {self.partner.id: 0})

    def test_sr_has_programs(self):
        person = {"enrolled_programs": [{"programme_name": "A"}]}
        self.assertEqual(self._fetch("r.dci.sr.has_programs", person), {self.partner.id: True})
        self.assertEqual(self._fetch("r.dci.sr.has_programs", {"id": "X"}), {self.partner.id: False})

    # -- household -------------------------------------------------------------

    def test_sr_household_size(self):
        person = {"household_info": {"household_size": 4, "is_household_head": False}}
        result = self._fetch("r.dci.sr.household_size", person, value_type="number")
        self.assertEqual(result, {self.partner.id: 4})

    def test_sr_household_size_zero_without_household(self):
        """Registered but household-less -> size 0 (complete cache)."""
        result = self._fetch("r.dci.sr.household_size", {"id": "EXT-1"}, value_type="number")
        self.assertEqual(result, {self.partner.id: 0})

    def test_sr_is_head_of_household(self):
        person = {"household_info": {"household_size": 3, "is_household_head": True}}
        self.assertEqual(self._fetch("r.dci.sr.is_head_of_household", person), {self.partner.id: True})

    def test_sr_is_head_false_without_household(self):
        result = self._fetch("r.dci.sr.is_head_of_household", {"id": "EXT-1"})
        self.assertEqual(result, {self.partner.id: False})

    def test_sr_large_household_above_threshold(self):
        person = {"household_info": {"household_size": 6}}
        self.assertEqual(self._fetch("r.dci.sr.large_household", person), {self.partner.id: True})

    def test_sr_large_household_at_threshold_is_false(self):
        # The seeded variable documents "more than 5 members"
        person = {"household_info": {"household_size": 5}}
        self.assertEqual(self._fetch("r.dci.sr.large_household", person), {self.partner.id: False})

    def test_sr_large_household_false_without_household(self):
        result = self._fetch("r.dci.sr.large_household", {"id": "EXT-1"})
        self.assertEqual(result, {self.partner.id: False})
