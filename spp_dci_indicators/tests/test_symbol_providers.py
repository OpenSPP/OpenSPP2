# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI Symbol Providers."""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDCISymbolProviders(TransactionCase):
    """Tests for DCI CEL symbol providers."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_dr_symbol_provider_initialization(self):
        """Test DRSymbolProvider can be initialized."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import DRSymbolProvider

        provider = DRSymbolProvider(self.env, self.partner)

        self.assertIsNotNone(provider)
        self.assertEqual(provider.partner, self.partner)
        self.assertFalse(provider._loaded)

    def test_dr_symbol_provider_lazy_loading(self):
        """Test DRSymbolProvider uses lazy loading."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import DRSymbolProvider

        provider = DRSymbolProvider(self.env, self.partner)

        # Not loaded initially
        self.assertFalse(provider._loaded)

        # Access property triggers loading
        _ = provider.has_disability

        # Now loaded
        self.assertTrue(provider._loaded)

    def test_dr_symbol_provider_default_values(self):
        """Test DRSymbolProvider returns defaults when no data."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import DRSymbolProvider

        provider = DRSymbolProvider(self.env, self.partner)

        self.assertFalse(provider.has_disability)
        self.assertEqual(provider.types, [])
        self.assertFalse(provider.assessed)
        self.assertEqual(provider.severity("Vision"), 1)
        self.assertFalse(provider.has_type("Vision"))

    def test_dr_symbol_provider_with_none_partner(self):
        """Test DRSymbolProvider handles None partner."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import DRSymbolProvider

        provider = DRSymbolProvider(self.env, None)

        self.assertFalse(provider.has_disability)
        self.assertEqual(provider.types, [])

    def test_crvs_symbol_provider_initialization(self):
        """Test CRVSSymbolProvider can be initialized."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import CRVSSymbolProvider

        provider = CRVSSymbolProvider(self.env, self.partner)

        self.assertIsNotNone(provider)
        self.assertEqual(provider.partner, self.partner)
        self.assertFalse(provider._loaded)

    def test_crvs_symbol_provider_default_values(self):
        """Test CRVSSymbolProvider returns defaults when no data."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import CRVSSymbolProvider

        provider = CRVSSymbolProvider(self.env, self.partner)

        self.assertTrue(provider.is_alive)  # Default is alive
        self.assertFalse(provider.birth_verified)
        self.assertFalse(provider.is_married)
        self.assertFalse(provider.has_event("birth"))

    def test_crvs_symbol_provider_with_none_partner(self):
        """Test CRVSSymbolProvider handles None partner."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import CRVSSymbolProvider

        provider = CRVSSymbolProvider(self.env, None)

        self.assertTrue(provider.is_alive)
        self.assertFalse(provider.birth_verified)

    def test_ibr_symbol_provider_initialization(self):
        """Test IBRSymbolProvider can be initialized."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import IBRSymbolProvider

        provider = IBRSymbolProvider(self.env, self.partner)

        self.assertIsNotNone(provider)
        self.assertEqual(provider.partner, self.partner)
        self.assertFalse(provider._loaded)

    def test_ibr_symbol_provider_default_values(self):
        """Test IBRSymbolProvider returns defaults when no data."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import IBRSymbolProvider

        provider = IBRSymbolProvider(self.env, self.partner)

        self.assertFalse(provider.has_duplicate)
        self.assertIsNone(provider.last_check_date)
        self.assertEqual(provider.matched_programs, [])
        self.assertFalse(provider.is_enrolled("Test Program"))

    def test_ibr_symbol_provider_with_none_partner(self):
        """Test IBRSymbolProvider handles None partner."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import IBRSymbolProvider

        provider = IBRSymbolProvider(self.env, None)

        self.assertFalse(provider.has_duplicate)
        self.assertEqual(provider.matched_programs, [])

    def test_dr_query_live_no_data_source(self):
        """Test DRSymbolProvider.query_live when no data source configured."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import DRSymbolProvider

        provider = DRSymbolProvider(self.env, self.partner)

        # Should return False when no DR data source
        result = provider.query_live()

        self.assertFalse(result)

    def test_crvs_query_live_no_data_source(self):
        """Test CRVSSymbolProvider.query_live when no data source configured."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import CRVSSymbolProvider

        provider = CRVSSymbolProvider(self.env, self.partner)

        # Should return None when no CRVS data source
        result = provider.query_live()

        self.assertIsNone(result)

    def test_ibr_query_live_no_data_source(self):
        """Test IBRSymbolProvider.query_live when no data source configured."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import IBRSymbolProvider

        provider = IBRSymbolProvider(self.env, self.partner)

        # Should return None when no IBR data source
        result = provider.query_live()

        self.assertIsNone(result)

    def test_get_data_source_by_type(self):
        """Test _get_data_source_by_type helper function."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import (
            _get_data_source_by_type,
        )

        # Create an active data source
        data_source = self.env["spp.dci.data.source"].create(
            {
                "name": "Test DR",
                "code": "test_dr",
                "base_url": "https://dr.example.org/api",
                "auth_type": "none",
                "our_sender_id": "openspp.example.org",
                "registry_type": "dr",
                "state": "active",
            }
        )

        # Should find it
        result = _get_data_source_by_type(self.env, "dr")
        self.assertEqual(result.id, data_source.id)

        # Should not find non-existent type
        result = _get_data_source_by_type(self.env, "nonexistent")
        self.assertFalse(result)


@tagged("post_install", "-at_install")
class TestDCICELIntegration(TransactionCase):
    """Tests for DCI CEL integration service."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test CEL Partner",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_get_dci_symbols(self):
        """Test CEL integration service returns symbol providers."""
        service = self.env["spp.dci.cel.integration"]
        symbols = service.get_dci_symbols(self.partner)

        self.assertIn("dr", symbols)
        self.assertIn("crvs", symbols)
        self.assertIn("ibr", symbols)

    def test_get_dci_symbols_types(self):
        """Test CEL integration service returns correct provider types."""
        from odoo.addons.spp_dci_indicators.symbols.dci_symbols import (
            CRVSSymbolProvider,
            DRSymbolProvider,
            IBRSymbolProvider,
        )

        service = self.env["spp.dci.cel.integration"]
        symbols = service.get_dci_symbols(self.partner)

        self.assertIsInstance(symbols["dr"], DRSymbolProvider)
        self.assertIsInstance(symbols["crvs"], CRVSSymbolProvider)
        self.assertIsInstance(symbols["ibr"], IBRSymbolProvider)

    def test_register_dci_symbols(self):
        """Test DCI symbols registration."""
        service = self.env["spp.dci.cel.integration"]
        result = service.register_dci_symbols()

        self.assertTrue(result)

    def test_get_symbol_documentation(self):
        """Test symbol documentation is returned."""
        service = self.env["spp.dci.cel.integration"]
        docs = service.get_symbol_documentation()

        self.assertIn("dr", docs)
        self.assertIn("crvs", docs)
        self.assertIn("ibr", docs)

        # Check DR documentation
        dr_docs = docs["dr"]
        self.assertIn("properties", dr_docs)
        self.assertIn("methods", dr_docs)
        self.assertIn("has_disability", dr_docs["properties"])
        self.assertIn("severity", dr_docs["methods"])

        # Check CRVS documentation
        crvs_docs = docs["crvs"]
        self.assertIn("is_alive", crvs_docs["properties"])
        self.assertIn("has_event", crvs_docs["methods"])

        # Check IBR documentation
        ibr_docs = docs["ibr"]
        self.assertIn("has_duplicate", ibr_docs["properties"])
        self.assertIn("is_enrolled", ibr_docs["methods"])
