# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for multi-company record rule enforcement.

Tests verify that ir.rule records in security/rules.xml correctly
isolate data between companies for:
- spp.data.provider (allows company_id=False for global providers)
- spp.data.value (strict company isolation)
- spp.data.credential (allows company_id=False for global credentials)
"""

import time

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestMultiCompanySetup(TransactionCase, CELTestDataMixin):
    """Base setup for multi-company tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._class_test_id = int(time.time() * 1000)

        # Create companies for multi-company tests (shared across test methods)
        cls.company_a = cls.env["res.company"].create({"name": f"Company A {cls._class_test_id}"})
        cls.company_b = cls.env["res.company"].create({"name": f"Company B {cls._class_test_id}"})

    def setUp(self):
        """Create fresh test users for each test method.

        Moving user creation to setUp ensures proper ACL cache state in full CI,
        where setUpClass-created users may have stale cache entries.
        """
        super().setUp()
        self._test_id = int(time.time() * 1000000)

        # Get required groups
        group_user = self.env.ref("base.group_user")
        group_read = self.env.ref("spp_cel_domain.group_cel_domain_read")
        group_viewer = self.env.ref("spp_cel_domain.group_cel_domain_viewer")
        group_manager = self.env.ref("spp_cel_domain.group_cel_domain_manager")
        group_admin = self.env.ref("spp_cel_domain.group_cel_domain_admin")

        # Create users with CEL domain manager role in different companies
        # Note: role_line_ids=[] bypasses default roles from base_user_role module
        self.user_company_a = self.env["res.users"].create(
            {
                "name": f"User A {self._test_id}",
                "login": f"user_a_{self._test_id}",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, [self.company_a.id])],
                "group_ids": [(6, 0, [group_user.id, group_read.id, group_viewer.id, group_manager.id])],
                "role_line_ids": [],
            }
        )

        self.user_company_b = self.env["res.users"].create(
            {
                "name": f"User B {self._test_id}",
                "login": f"user_b_{self._test_id}",
                "company_id": self.company_b.id,
                "company_ids": [(6, 0, [self.company_b.id])],
                "group_ids": [(6, 0, [group_user.id, group_read.id, group_viewer.id, group_manager.id])],
                "role_line_ids": [],
            }
        )

        # Create multi-company user with admin role
        self.user_multi_company = self.env["res.users"].create(
            {
                "name": f"Multi-Company Admin {self._test_id}",
                "login": f"multi_admin_{self._test_id}",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, [self.company_a.id, self.company_b.id])],
                "group_ids": [(6, 0, [group_user.id, group_read.id, group_viewer.id, group_manager.id, group_admin.id])],
                "role_line_ids": [],
            }
        )

        # Invalidate cache to ensure ACL changes are recognized
        self.env.invalidate_all()


@tagged("post_install", "-at_install")
class TestDataProviderMultiCompany(TestMultiCompanySetup):
    """Tests for multi-company isolation of spp.data.provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataProvider = cls.env["spp.data.provider"]

        # Create providers in different companies (shared across test methods)
        cls.provider_company_a = cls.DataProvider.create(
            {
                "name": f"Provider A {cls._class_test_id}",
                "code": f"prov_a_{cls._class_test_id}",
                "company_id": cls.company_a.id,
            }
        )

        cls.provider_company_b = cls.DataProvider.create(
            {
                "name": f"Provider B {cls._class_test_id}",
                "code": f"prov_b_{cls._class_test_id}",
                "company_id": cls.company_b.id,
            }
        )

        # Create global provider (no company)
        cls.provider_global = cls.DataProvider.create(
            {
                "name": f"Global Provider {cls._class_test_id}",
                "code": f"prov_global_{cls._class_test_id}",
                "company_id": False,
            }
        )

    def test_01_user_sees_own_company_provider(self):
        """Test user can see providers from their company."""
        providers = self.DataProvider.with_user(self.user_company_a).search([("id", "=", self.provider_company_a.id)])
        self.assertEqual(len(providers), 1)
        self.assertIn(self.provider_company_a, providers)

    def test_02_user_cannot_see_other_company_provider(self):
        """Test user cannot see providers from other companies."""
        providers = self.DataProvider.with_user(self.user_company_a).search([("id", "=", self.provider_company_b.id)])
        self.assertEqual(len(providers), 0)
        self.assertNotIn(self.provider_company_b, providers)

    def test_03_user_sees_global_provider(self):
        """Test user can see global providers (company_id=False)."""
        providers = self.DataProvider.with_user(self.user_company_a).search([("id", "=", self.provider_global.id)])
        self.assertEqual(len(providers), 1)
        self.assertIn(self.provider_global, providers)

    def test_04_company_b_user_isolation(self):
        """Test company B user sees company B and global, not company A."""
        # Should see company B provider
        providers_b = self.DataProvider.with_user(self.user_company_b).search([("id", "=", self.provider_company_b.id)])
        self.assertEqual(len(providers_b), 1)

        # Should see global provider
        providers_global = self.DataProvider.with_user(self.user_company_b).search(
            [("id", "=", self.provider_global.id)]
        )
        self.assertEqual(len(providers_global), 1)

        # Should NOT see company A provider
        providers_a = self.DataProvider.with_user(self.user_company_b).search([("id", "=", self.provider_company_a.id)])
        self.assertEqual(len(providers_a), 0)

    def test_05_multi_company_user_sees_all(self):
        """Test multi-company user sees providers from all their companies."""
        # Filter to our test providers only
        test_provider_ids = [
            self.provider_company_a.id,
            self.provider_company_b.id,
            self.provider_global.id,
        ]
        providers = self.DataProvider.with_user(self.user_multi_company).search([("id", "in", test_provider_ids)])
        self.assertEqual(len(providers), 3)
        self.assertIn(self.provider_company_a, providers)
        self.assertIn(self.provider_company_b, providers)
        self.assertIn(self.provider_global, providers)


@tagged("post_install", "-at_install")
class TestDataValueMultiCompany(TestMultiCompanySetup):
    """Tests for multi-company isolation of spp.data.value (strict)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataValue = cls.env["spp.data.value"]

        # Create a test partner for subject reference
        cls.test_partner = cls._create_test_partner()

        # Create data values in different companies
        cls.value_company_a = cls.DataValue.create(
            {
                "variable_name": f"test_var_a_{cls._class_test_id}",
                "subject_model": "res.partner",
                "subject_id": cls.test_partner.id,
                "value_json": {"value": 100},
                "value_type": "number",
                "company_id": cls.company_a.id,
            }
        )

        cls.value_company_b = cls.DataValue.create(
            {
                "variable_name": f"test_var_b_{cls._class_test_id}",
                "subject_model": "res.partner",
                "subject_id": cls.test_partner.id,
                "value_json": {"value": 200},
                "value_type": "number",
                "company_id": cls.company_b.id,
            }
        )

    def test_01_user_sees_own_company_values(self):
        """Test user can see data values from their company."""
        values = self.DataValue.with_user(self.user_company_a).search([("id", "=", self.value_company_a.id)])
        self.assertEqual(len(values), 1)
        self.assertIn(self.value_company_a, values)

    def test_02_user_cannot_see_other_company_values(self):
        """Test user cannot see data values from other companies."""
        values = self.DataValue.with_user(self.user_company_a).search([("id", "=", self.value_company_b.id)])
        self.assertEqual(len(values), 0)

    def test_03_company_b_user_isolation(self):
        """Test company B user sees only company B values."""
        # Should see company B value
        values_b = self.DataValue.with_user(self.user_company_b).search([("id", "=", self.value_company_b.id)])
        self.assertEqual(len(values_b), 1)

        # Should NOT see company A value
        values_a = self.DataValue.with_user(self.user_company_b).search([("id", "=", self.value_company_a.id)])
        self.assertEqual(len(values_a), 0)

    def test_04_multi_company_user_sees_all(self):
        """Test multi-company user sees values from all their companies."""
        test_value_ids = [
            self.value_company_a.id,
            self.value_company_b.id,
        ]
        values = self.DataValue.with_user(self.user_multi_company).search([("id", "in", test_value_ids)])
        self.assertEqual(len(values), 2)
        self.assertIn(self.value_company_a, values)
        self.assertIn(self.value_company_b, values)

    def test_05_strict_isolation_no_global_values(self):
        """Test that data values require company_id (no global fallback)."""
        # Data values should always have a company_id
        # The record rule is strict: [('company_id', 'in', company_ids)]
        # This test verifies records default to user's company
        new_value = self.DataValue.with_user(self.user_company_a).create(
            {
                "variable_name": f"test_strict_{self._test_id}",
                "subject_model": "res.partner",
                "subject_id": self.test_partner.id,
                "value_json": {"value": 999},
                "value_type": "number",
            }
        )
        # Should have company_id set to user's company by default
        self.assertEqual(new_value.company_id, self.company_a)


@tagged("post_install", "-at_install")
class TestDataCredentialMultiCompany(TestMultiCompanySetup):
    """Tests for multi-company isolation of spp.data.credential."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataCredential = cls.env["spp.data.credential"]
        cls.DataProvider = cls.env["spp.data.provider"]

        # Create providers for credentials (shared across test methods)
        cls.provider_a = cls.DataProvider.create(
            {
                "name": f"Credential Provider A {cls._class_test_id}",
                "code": f"cred_prov_a_{cls._class_test_id}",
                "company_id": cls.company_a.id,
            }
        )

        cls.provider_b = cls.DataProvider.create(
            {
                "name": f"Credential Provider B {cls._class_test_id}",
                "code": f"cred_prov_b_{cls._class_test_id}",
                "company_id": cls.company_b.id,
            }
        )

        cls.provider_global = cls.DataProvider.create(
            {
                "name": f"Global Credential Provider {cls._class_test_id}",
                "code": f"cred_prov_global_{cls._class_test_id}",
                "company_id": False,
            }
        )

        # Create credentials in different companies
        cls.credential_company_a = cls.DataCredential.create(
            {
                "name": f"Credential A {cls._class_test_id}",
                "provider_id": cls.provider_a.id,
                "credential_type": "api_key",
                "api_key": "test_key_a",
                "company_id": cls.company_a.id,
            }
        )

        cls.credential_company_b = cls.DataCredential.create(
            {
                "name": f"Credential B {cls._class_test_id}",
                "provider_id": cls.provider_b.id,
                "credential_type": "api_key",
                "api_key": "test_key_b",
                "company_id": cls.company_b.id,
            }
        )

        # Create global credential (no company)
        cls.credential_global = cls.DataCredential.create(
            {
                "name": f"Global Credential {cls._class_test_id}",
                "provider_id": cls.provider_global.id,
                "credential_type": "api_key",
                "api_key": "test_key_global",
                "company_id": False,
            }
        )

    def setUp(self):
        """Create fresh admin users for credentials tests."""
        super().setUp()

        # Get required groups
        group_user = self.env.ref("base.group_user")
        group_admin = self.env.ref("spp_cel_domain.group_cel_domain_admin")

        # Create admin users for credentials (credentials require admin group)
        # Note: role_line_ids=[] bypasses default roles from base_user_role module
        self.admin_company_a = self.env["res.users"].create(
            {
                "name": f"Admin A {self._test_id}",
                "login": f"admin_a_{self._test_id}",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, [self.company_a.id])],
                "group_ids": [(6, 0, [group_user.id, group_admin.id])],
                "role_line_ids": [],
            }
        )

        self.admin_company_b = self.env["res.users"].create(
            {
                "name": f"Admin B {self._test_id}",
                "login": f"admin_b_{self._test_id}",
                "company_id": self.company_b.id,
                "company_ids": [(6, 0, [self.company_b.id])],
                "group_ids": [(6, 0, [group_user.id, group_admin.id])],
                "role_line_ids": [],
            }
        )

        # Invalidate cache to ensure ACL changes are recognized
        self.env.invalidate_all()

    def test_01_user_sees_own_company_credentials(self):
        """Test admin user can see credentials from their company."""
        credentials = self.DataCredential.with_user(self.admin_company_a).search(
            [("id", "=", self.credential_company_a.id)]
        )
        self.assertEqual(len(credentials), 1)
        self.assertIn(self.credential_company_a, credentials)

    def test_02_user_cannot_see_other_company_credentials(self):
        """Test admin user cannot see credentials from other companies."""
        credentials = self.DataCredential.with_user(self.admin_company_a).search(
            [("id", "=", self.credential_company_b.id)]
        )
        self.assertEqual(len(credentials), 0)

    def test_03_user_sees_global_credentials(self):
        """Test admin user can see global credentials (company_id=False)."""
        credentials = self.DataCredential.with_user(self.admin_company_a).search(
            [("id", "=", self.credential_global.id)]
        )
        self.assertEqual(len(credentials), 1)
        self.assertIn(self.credential_global, credentials)

    def test_04_company_b_user_isolation(self):
        """Test company B admin sees company B and global, not company A."""
        # Should see company B credential
        creds_b = self.DataCredential.with_user(self.admin_company_b).search(
            [("id", "=", self.credential_company_b.id)]
        )
        self.assertEqual(len(creds_b), 1)

        # Should see global credential
        creds_global = self.DataCredential.with_user(self.admin_company_b).search(
            [("id", "=", self.credential_global.id)]
        )
        self.assertEqual(len(creds_global), 1)

        # Should NOT see company A credential
        creds_a = self.DataCredential.with_user(self.admin_company_b).search(
            [("id", "=", self.credential_company_a.id)]
        )
        self.assertEqual(len(creds_a), 0)

    def test_05_multi_company_user_sees_all(self):
        """Test multi-company user sees credentials from all their companies."""
        test_cred_ids = [
            self.credential_company_a.id,
            self.credential_company_b.id,
            self.credential_global.id,
        ]
        credentials = self.DataCredential.with_user(self.user_multi_company).search([("id", "in", test_cred_ids)])
        self.assertEqual(len(credentials), 3)
        self.assertIn(self.credential_company_a, credentials)
        self.assertIn(self.credential_company_b, credentials)
        self.assertIn(self.credential_global, credentials)

    def test_06_admin_group_required_for_credentials(self):
        """Test that only admin users can access credentials (via ACL)."""
        from odoo.exceptions import AccessError

        # Create a user with only manager role (not admin)
        manager_user = self.env["res.users"].create(
            {
                "name": f"Manager Only {self._test_id}",
                "login": f"manager_only_{self._test_id}",
                "company_id": self.company_a.id,
                "company_ids": [(6, 0, [self.company_a.id])],
                "group_ids": [
                    (4, self.env.ref("spp_cel_domain.group_cel_domain_manager").id),
                ],
            }
        )

        # Admin user should have access
        admin_creds = self.DataCredential.with_user(self.user_multi_company).search(  # Has admin role
            [("company_id", "=", self.company_a.id)]
        )
        # Admin should see the credential
        self.assertGreaterEqual(len(admin_creds), 1)

        # Manager user should NOT have access (negative case)
        with self.assertRaises(AccessError):
            self.DataCredential.with_user(manager_user).search([("id", "=", self.credential_company_a.id)])
