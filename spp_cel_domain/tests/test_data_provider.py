# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.data.provider model (External Data Provider).

This module tests the external data provider configuration added as part of
the Unified Variable System implementation.
"""

import time

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

from .common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestDataProviderCRUD(TransactionCase, CELTestDataMixin):
    """Tests for basic CRUD operations on spp.data.provider."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataProvider = cls.env["spp.data.provider"]

    def test_create_provider_basic(self):
        """Test basic provider creation."""
        provider = self.DataProvider.create(
            {
                "name": "Test Provider",
                "code": f"test_provider_{self._test_id}",
            }
        )

        self.assertTrue(provider.id)
        self.assertEqual(provider.name, "Test Provider")
        self.assertTrue(provider.active)
        self.assertEqual(provider.auth_type, "none")
        self.assertEqual(provider.default_ttl_seconds, 86400)  # 24 hours

    def test_create_provider_with_auth(self):
        """Test provider creation with API key authentication."""
        provider = self.DataProvider.create(
            {
                "name": "API Provider",
                "code": f"api_provider_{self._test_id}",
                "base_url": "https://api.example.com/v1",
                "auth_type": "api_key",
            }
        )

        self.assertEqual(provider.auth_type, "api_key")
        self.assertEqual(provider.base_url, "https://api.example.com/v1")

    def test_create_provider_with_oauth(self):
        """Test provider creation with OAuth authentication."""
        provider = self.DataProvider.create(
            {
                "name": "OAuth Provider",
                "code": f"oauth_provider_{self._test_id}",
                "base_url": "https://api.secure.com/v2",
                "auth_type": "oauth2",
                "oauth_token_url": "https://auth.secure.com/token",
            }
        )

        self.assertEqual(provider.auth_type, "oauth2")
        self.assertEqual(provider.oauth_token_url, "https://auth.secure.com/token")

    def test_create_provider_custom_settings(self):
        """Test provider creation with custom behavior settings."""
        provider = self.DataProvider.create(
            {
                "name": "Custom Provider",
                "code": f"custom_provider_{self._test_id}",
                "default_ttl_seconds": 3600,  # 1 hour
                "max_batch_size": 500,
                "timeout_ms": 10000,
                "retry_max": 5,
                "recommended_concurrency": 10,
            }
        )

        self.assertEqual(provider.default_ttl_seconds, 3600)
        self.assertEqual(provider.max_batch_size, 500)
        self.assertEqual(provider.timeout_ms, 10000)
        self.assertEqual(provider.retry_max, 5)
        self.assertEqual(provider.recommended_concurrency, 10)

    def test_name_get(self):
        """Test display name includes code."""
        provider = self.DataProvider.create(
            {
                "name": "My Provider",
                "code": f"my_provider_{self._test_id}",
            }
        )

        display = provider.name_get()
        self.assertIn("My Provider", display[0][1])
        self.assertIn(f"my_provider_{self._test_id}", display[0][1])


@tagged("post_install", "-at_install")
class TestDataProviderConstraints(TransactionCase, CELTestDataMixin):
    """Tests for spp.data.provider constraints and validation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataProvider = cls.env["spp.data.provider"]

    def test_code_format_valid_lowercase(self):
        """Test valid lowercase code."""
        provider = self.DataProvider.create(
            {
                "name": "Test",
                "code": f"valid_code_{self._test_id}",
            }
        )
        self.assertTrue(provider.id)

    def test_code_format_invalid_uppercase(self):
        """Test uppercase code is rejected."""
        with self.assertRaises(ValidationError):
            self.DataProvider.create(
                {
                    "name": "Test",
                    "code": f"INVALID_CODE_{self._test_id}",
                }
            )

    def test_code_format_invalid_start_number(self):
        """Test code starting with number is rejected."""
        with self.assertRaises(ValidationError):
            self.DataProvider.create(
                {
                    "name": "Test",
                    "code": f"123_invalid_{self._test_id}",
                }
            )

    def test_code_format_invalid_special_chars(self):
        """Test code with special characters is rejected."""
        with self.assertRaises(ValidationError):
            self.DataProvider.create(
                {
                    "name": "Test",
                    "code": f"invalid-code-{self._test_id}",
                }
            )

    def test_ttl_positive(self):
        """Test TTL must be positive."""
        with self.assertRaises(ValidationError):
            self.DataProvider.create(
                {
                    "name": "Test",
                    "code": f"ttl_test_{self._test_id}",
                    "default_ttl_seconds": 0,
                }
            )

    def test_ttl_negative_rejected(self):
        """Test negative TTL is rejected."""
        with self.assertRaises(ValidationError):
            self.DataProvider.create(
                {
                    "name": "Test",
                    "code": f"ttl_neg_{self._test_id}",
                    "default_ttl_seconds": -1,
                }
            )

    def test_batch_size_positive(self):
        """Test batch size must be positive."""
        with self.assertRaises(ValidationError):
            self.DataProvider.create(
                {
                    "name": "Test",
                    "code": f"batch_test_{self._test_id}",
                    "max_batch_size": 0,
                }
            )

    def test_batch_size_max_limit(self):
        """Test batch size max limit."""
        with self.assertRaises(ValidationError):
            self.DataProvider.create(
                {
                    "name": "Test",
                    "code": f"batch_max_{self._test_id}",
                    "max_batch_size": 10001,
                }
            )

    @mute_logger("odoo.sql_db")
    def test_unique_code_per_company(self):
        """Test code must be unique per company."""
        code = f"unique_code_{self._test_id}"

        # Create first provider
        self.DataProvider.create(
            {
                "name": "First Provider",
                "code": code,
            }
        )

        # Attempt to create duplicate should fail
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.DataProvider.create(
                    {
                        "name": "Second Provider",
                        "code": code,
                    }
                )


@tagged("post_install", "-at_install")
class TestDataProviderMethods(TransactionCase, CELTestDataMixin):
    """Tests for spp.data.provider methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataProvider = cls.env["spp.data.provider"]

    def test_get_id_mapping_field_list_empty(self):
        """Test empty ID mapping returns empty list."""
        provider = self.DataProvider.create(
            {
                "name": "Test",
                "code": f"mapping_empty_{self._test_id}",
                "id_mapping_fields": "",
            }
        )

        result = provider.get_id_mapping_field_list()
        self.assertEqual(result, [])

    def test_get_id_mapping_field_list_single(self):
        """Test single ID mapping field."""
        provider = self.DataProvider.create(
            {
                "name": "Test",
                "code": f"mapping_single_{self._test_id}",
                "id_mapping_fields": "external_id",
            }
        )

        result = provider.get_id_mapping_field_list()
        self.assertEqual(result, ["external_id"])

    def test_get_id_mapping_field_list_multiple(self):
        """Test multiple ID mapping fields."""
        provider = self.DataProvider.create(
            {
                "name": "Test",
                "code": f"mapping_multi_{self._test_id}",
                "id_mapping_fields": "school_id, national_id, external_id",
            }
        )

        result = provider.get_id_mapping_field_list()
        self.assertEqual(result, ["school_id", "national_id", "external_id"])

    def test_get_id_mapping_field_list_strips_whitespace(self):
        """Test whitespace is stripped from mapping fields."""
        provider = self.DataProvider.create(
            {
                "name": "Test",
                "code": f"mapping_ws_{self._test_id}",
                "id_mapping_fields": "  field1  ,  field2  ,  field3  ",
            }
        )

        result = provider.get_id_mapping_field_list()
        self.assertEqual(result, ["field1", "field2", "field3"])

    def test_variable_count_zero(self):
        """Test variable count is zero for new provider."""
        provider = self.DataProvider.create(
            {
                "name": "Test",
                "code": f"count_zero_{self._test_id}",
            }
        )

        self.assertEqual(provider.variable_count, 0)

    def test_variable_count_with_variables(self):
        """Test variable count reflects linked variables."""
        provider = self.DataProvider.create(
            {
                "name": "Test",
                "code": f"count_vars_{self._test_id}",
            }
        )

        # Create test category
        category = self._create_test_category()

        # Create variables linked to provider
        Variable = self.env["spp.cel.variable"]
        for i in range(3):
            Variable.create(
                {
                    "name": f"var_{self._test_id}_{i}",
                    "cel_accessor": f"var_{self._test_id}_{i}",
                    "source_type": "external",
                    "value_type": "number",
                    "external_provider_id": provider.id,
                    "category_id": category.id,
                }
            )

        # Refresh provider to get updated count
        provider.invalidate_recordset()
        self.assertEqual(provider.variable_count, 3)

    def test_action_view_variables(self):
        """Test action_view_variables returns correct action."""
        provider = self.DataProvider.create(
            {
                "name": "Test",
                "code": f"action_vars_{self._test_id}",
            }
        )

        action = provider.action_view_variables()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.cel.variable")
        self.assertIn(("external_provider_id", "=", provider.id), action["domain"])

    def test_action_test_connection_no_url(self):
        """Test action_test_connection with no URL configured."""
        provider = self.DataProvider.create(
            {
                "name": "Test",
                "code": f"conn_no_url_{self._test_id}",
            }
        )

        result = provider.action_test_connection()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "warning")


@tagged("post_install", "-at_install")
class TestDataProviderKind(TransactionCase, CELTestDataMixin):
    """Tests for the provider_kind discriminator on spp.data.provider.

    `provider_kind` is the typed discriminator used by `_compute_variable_values`
    and `_exec_metric` to dispatch external-value resolution to provider-specific
    overrides. Base ships with `generic`; downstream modules (e.g. notary) extend
    the selection via `_selection_add`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.DataProvider = cls.env["spp.data.provider"]

    def test_provider_kind_defaults_to_generic(self):
        """New providers default to provider_kind='generic'."""
        provider = self.DataProvider.create(
            {
                "name": "Default Kind",
                "code": f"default_kind_{self._test_id}",
            }
        )
        self.assertEqual(provider.provider_kind, "generic")

    def test_provider_kind_selection_includes_generic(self):
        """The provider_kind selection includes at least 'generic'."""
        kinds = dict(self.DataProvider._fields["provider_kind"].selection)
        self.assertIn("generic", kinds)

    def test_provider_kind_explicit_assignment(self):
        """Assigning a known kind sticks."""
        provider = self.DataProvider.create(
            {
                "name": "Explicit Generic",
                "code": f"explicit_generic_{self._test_id}",
                "provider_kind": "generic",
            }
        )
        self.assertEqual(provider.provider_kind, "generic")

    @mute_logger("odoo.sql_db")
    def test_provider_kind_required(self):
        """provider_kind is required (cannot be set to false)."""
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.DataProvider.create(
                    {
                        "name": "No Kind",
                        "code": f"no_kind_{self._test_id}",
                        "provider_kind": False,
                    }
                )
