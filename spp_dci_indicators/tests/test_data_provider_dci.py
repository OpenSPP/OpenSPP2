# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI Integration bridge on spp.data.provider.

A data provider can be linked to a spp.dci.data.source, making it
"DCI-backed": at runtime its values are fetched via the DCI protocol using
the linked Data Source rather than the provider's own connection settings.
This module adds the link + the is_dci_backed flag (Part 1: config layer).
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_dci.schemas.constants import RegistryType


@tagged("post_install", "-at_install")
class TestDataProviderDCI(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Provider = cls.env["spp.data.provider"]
        cls.dci_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "OpenCRVS Farajaland",
                "code": "opencrvs_farajaland_t",
                "base_url": "https://crvs.example.org/api",
                "registry_type": RegistryType.CRVS.value,
                "our_sender_id": "openspp.test",
                "auth_type": "none",
            }
        )

    def test_dci_data_source_field_exists(self):
        """The provider gains a Many2one to spp.dci.data.source."""
        field = self.Provider._fields.get("dci_data_source_id")
        self.assertIsNotNone(field, "dci_data_source_id field should exist on spp.data.provider")
        self.assertEqual(field.comodel_name, "spp.dci.data.source")

    def test_is_dci_backed_reflects_link(self):
        """is_dci_backed is False until a DCI source is linked, then True."""
        provider = self.Provider.create({"name": "OpenCRVS", "code": "opencrvs_t"})
        self.assertFalse(provider.is_dci_backed)

        provider.dci_data_source_id = self.dci_source
        self.assertTrue(provider.is_dci_backed)

        provider.dci_data_source_id = False
        self.assertFalse(provider.is_dci_backed)

    def test_link_set_at_create(self):
        provider = self.Provider.create(
            {
                "name": "OpenCRVS",
                "code": "opencrvs_create_t",
                "dci_data_source_id": self.dci_source.id,
            }
        )
        self.assertTrue(provider.is_dci_backed)
        self.assertEqual(provider.dci_data_source_id, self.dci_source)
