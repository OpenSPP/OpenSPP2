# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCI indicator data loading.

This module tests that the DCI variables and category are properly loaded
from XML data when the module is installed.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestDCIIndicatorData(TransactionCase):
    """Tests for DCI indicator data loading."""

    def test_dci_category_exists(self):
        """Test that DCI variable category was created."""
        Category = self.env["spp.cel.variable.category"]
        category = Category.search([("code", "=", "dci")])

        self.assertTrue(category, "DCI category should exist")
        self.assertEqual(category.name, "DCI Integration")
        self.assertEqual(category.icon, "fa-exchange")

    def test_dr_variables_exist(self):
        """Test Disability Registry (DR) variables were created."""
        Variable = self.env["spp.cel.variable"]

        # Check has_disability variable
        var = Variable.search([("name", "=", "dci.dr.has_disability")])
        self.assertTrue(var, "dci.dr.has_disability should exist")
        self.assertEqual(var.value_type, "boolean")
        self.assertEqual(var.source_type, "external")
        self.assertEqual(var.cel_accessor, "dr.dci.has_disability")
        self.assertEqual(var.applies_to, "individual")
        self.assertTrue(var.is_system)

        # Check severity variables exist
        for name in ["dci.dr.vision_severe", "dci.dr.hearing_severe", "dci.dr.mobility_severe"]:
            var = Variable.search([("name", "=", name)])
            self.assertTrue(var, f"{name} should exist")
            self.assertEqual(var.value_type, "boolean")

        # Check assessed variable
        var = Variable.search([("name", "=", "dci.dr.assessed")])
        self.assertTrue(var, "dci.dr.assessed should exist")

    def test_crvs_variables_exist(self):
        """Test Civil Registration (CRVS) variables were created."""
        Variable = self.env["spp.cel.variable"]

        # Check CRVS variables
        for name in ["dci.crvs.is_alive", "dci.crvs.birth_verified", "dci.crvs.is_married"]:
            var = Variable.search([("name", "=", name)])
            self.assertTrue(var, f"{name} should exist")
            self.assertEqual(var.value_type, "boolean")
            self.assertEqual(var.source_type, "external")
            self.assertEqual(var.applies_to, "individual")

    def test_ibr_variables_exist(self):
        """Test Integrated Beneficiary Registry (IBR) variables were created."""
        Variable = self.env["spp.cel.variable"]

        # Check IBR variables
        for name in ["dci.ibr.has_duplicate", "dci.ibr.no_duplicate", "dci.ibr.checked"]:
            var = Variable.search([("name", "=", name)])
            self.assertTrue(var, f"{name} should exist")
            self.assertEqual(var.value_type, "boolean")
            self.assertEqual(var.source_type, "external")

    def test_all_dci_variables_count(self):
        """Test total number of DCI variables."""
        Variable = self.env["spp.cel.variable"]
        Category = self.env["spp.cel.variable.category"]

        category = Category.search([("code", "=", "dci")])
        variables = Variable.search([("category_id", "=", category.id)])

        # Should have: 5 DR + 3 CRVS + 3 IBR + 6 SR = 17 variables
        self.assertEqual(len(variables), 17, "Should have 17 DCI variables")

    def test_dci_variables_have_labels(self):
        """Test that DCI variables have user-friendly labels."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.search([("name", "=", "dci.dr.has_disability")])
        self.assertTrue(var.label, "Variable should have a label")
        self.assertIn("Disability", var.label)

    def test_dci_variables_have_descriptions(self):
        """Test that DCI variables have descriptions."""
        Variable = self.env["spp.cel.variable"]

        var = Variable.search([("name", "=", "dci.crvs.is_alive")])
        self.assertTrue(var.description, "Variable should have a description")
        self.assertIn("alive", var.description.lower())

    def test_dci_variables_cache_settings(self):
        """Test that DCI variables have proper cache settings."""
        Variable = self.env["spp.cel.variable"]

        # DR variables should have 24-hour TTL
        var = Variable.search([("name", "=", "dci.dr.has_disability")])
        self.assertEqual(var.cache_strategy, "ttl")
        self.assertEqual(var.cache_ttl_seconds, 86400)  # 24 hours

        # IBR variables should have 1-hour TTL
        var = Variable.search([("name", "=", "dci.ibr.has_duplicate")])
        self.assertEqual(var.cache_strategy, "ttl")
        self.assertEqual(var.cache_ttl_seconds, 3600)  # 1 hour

    def test_dci_variables_linked_to_category(self):
        """Test that all DCI variables are properly linked to DCI category."""
        Variable = self.env["spp.cel.variable"]

        dci_vars = Variable.search([("name", "=like", "dci.%")])
        for var in dci_vars:
            self.assertTrue(var.category_id, f"{var.name} should have a category")
            self.assertEqual(var.category_id.code, "dci", f"{var.name} should be in DCI category")
