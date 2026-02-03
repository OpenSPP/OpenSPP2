# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.dci.data.source model"""

from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestDataSource(TransactionCase):
    """Test DCI Data Source model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]

    def test_create_data_source(self):
        """Test creating a data source with required fields"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )
        self.assertEqual(ds.state, "draft")
        self.assertEqual(ds.name, "Test CRVS")
        self.assertEqual(ds.code, "test_crvs")
        self.assertEqual(ds.base_url, "https://crvs.example.org/api")
        self.assertTrue(ds.active)

    def test_code_unique_constraint(self):
        """Test that duplicate codes are rejected"""
        # Create first data source
        self.DataSource.create(
            {
                "name": "Test CRVS 1",
                "code": "test_crvs",
                "base_url": "https://crvs1.example.org/api",
                "auth_type": "none",
            }
        )

        # Try to create duplicate code
        with self.assertRaises(Exception) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS 2",
                    "code": "test_crvs",
                    "base_url": "https://crvs2.example.org/api",
                    "auth_type": "none",
                }
            )

        # Check error message contains constraint name
        error_msg = str(cm.exception)
        self.assertIn("code", error_msg.lower())

    def test_code_format_validation_alphanumeric(self):
        """Test code must be lowercase alphanumeric and underscores"""
        # Valid codes should pass
        valid_codes = ["test", "test_123", "test_crvs_main", "a1b2c3"]
        for code in valid_codes:
            ds = self.DataSource.create(
                {
                    "name": f"Test {code}",
                    "code": code,
                    "base_url": "https://test.example.org/api",
                    "auth_type": "none",
                }
            )
            self.assertEqual(ds.code, code)

    def test_code_format_validation_uppercase(self):
        """Test code must be lowercase"""
        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS",
                    "code": "TEST_CRVS",
                    "base_url": "https://crvs.example.org/api",
                    "auth_type": "none",
                }
            )
        self.assertIn("lowercase", str(cm.exception))

    def test_code_format_validation_special_chars(self):
        """Test code cannot contain special characters"""
        invalid_codes = ["test-crvs", "test.crvs", "test crvs", "test@crvs"]
        for code in invalid_codes:
            with self.assertRaises(ValidationError) as cm:
                self.DataSource.create(
                    {
                        "name": f"Test {code}",
                        "code": code,
                        "base_url": "https://test.example.org/api",
                        "auth_type": "none",
                    }
                )
            error_msg = str(cm.exception)
            self.assertTrue(
                "lowercase" in error_msg.lower() or "alphanumeric" in error_msg.lower(),
                f"Expected validation error for code '{code}', got: {error_msg}",
            )

    def test_base_url_validation_protocol(self):
        """Test base URL must start with http:// or https://"""
        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS",
                    "code": "test_crvs",
                    "base_url": "crvs.example.org/api",
                    "auth_type": "none",
                }
            )
        self.assertIn("http", str(cm.exception).lower())

    def test_base_url_validation_trailing_slash(self):
        """Test base URL should not end with a slash"""
        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS",
                    "code": "test_crvs",
                    "base_url": "https://crvs.example.org/api/",
                    "auth_type": "none",
                }
            )
        self.assertIn("slash", str(cm.exception).lower())

    def test_oauth2_required_fields_token_url(self):
        """Test OAuth2 requires token URL"""
        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS",
                    "code": "test_crvs",
                    "base_url": "https://crvs.example.org/api",
                    "auth_type": "oauth2",
                    "oauth2_client_id": "client123",
                    "oauth2_client_secret": "secret456",
                }
            )
        self.assertIn("token url", str(cm.exception).lower())

    def test_oauth2_required_fields_client_id(self):
        """Test OAuth2 requires client ID"""
        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS",
                    "code": "test_crvs",
                    "base_url": "https://crvs.example.org/api",
                    "auth_type": "oauth2",
                    "oauth2_token_url": "https://auth.example.org/token",
                    "oauth2_client_secret": "secret456",
                }
            )
        self.assertIn("client id", str(cm.exception).lower())

    def test_oauth2_required_fields_client_secret(self):
        """Test OAuth2 requires client secret"""
        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS",
                    "code": "test_crvs",
                    "base_url": "https://crvs.example.org/api",
                    "auth_type": "oauth2",
                    "oauth2_token_url": "https://auth.example.org/token",
                    "oauth2_client_id": "client123",
                }
            )
        self.assertIn("client secret", str(cm.exception).lower())

    def test_oauth2_all_fields_provided(self):
        """Test OAuth2 succeeds when all fields are provided"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "oauth2",
                "oauth2_token_url": "https://auth.example.org/token",
                "oauth2_client_id": "client123",
                "oauth2_client_secret": "secret456",
                "our_sender_id": "openspp.example.org",
            }
        )
        self.assertEqual(ds.auth_type, "oauth2")

    def test_sender_id_required_for_auth(self):
        """Test sender ID is required when auth_type is not 'none'"""
        # Should fail for basic auth without sender_id
        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS",
                    "code": "test_crvs",
                    "base_url": "https://crvs.example.org/api",
                    "auth_type": "basic",
                }
            )
        self.assertIn("sender id", str(cm.exception).lower())

        # Should fail for oauth2 without sender_id
        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS",
                    "code": "test_crvs_2",
                    "base_url": "https://crvs.example.org/api",
                    "auth_type": "oauth2",
                    "oauth2_token_url": "https://auth.example.org/token",
                    "oauth2_client_id": "client123",
                    "oauth2_client_secret": "secret456",
                }
            )
        self.assertIn("sender id", str(cm.exception).lower())

    def test_sender_id_not_required_for_none_auth(self):
        """Test sender ID is not required when auth_type is 'none'"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )
        self.assertEqual(ds.auth_type, "none")
        self.assertFalse(ds.our_sender_id)

    def test_timeout_validation(self):
        """Test timeout must be positive"""
        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS",
                    "code": "test_crvs",
                    "base_url": "https://crvs.example.org/api",
                    "auth_type": "none",
                    "timeout": -10,
                }
            )
        self.assertIn("positive", str(cm.exception).lower())

        with self.assertRaises(ValidationError) as cm:
            self.DataSource.create(
                {
                    "name": "Test CRVS 2",
                    "code": "test_crvs_2",
                    "base_url": "https://crvs.example.org/api",
                    "auth_type": "none",
                    "timeout": 0,
                }
            )
        self.assertIn("positive", str(cm.exception).lower())

    def test_state_transitions_draft_to_active(self):
        """Test transitioning from draft to active state"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )
        self.assertEqual(ds.state, "draft")

        # Transition to active
        ds.write({"state": "active"})
        self.assertEqual(ds.state, "active")

    def test_state_transitions_to_error(self):
        """Test transitioning to error state"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )

        # Transition to error
        ds.write(
            {
                "state": "error",
                "last_error": "Connection failed",
            }
        )
        self.assertEqual(ds.state, "error")
        self.assertEqual(ds.last_error, "Connection failed")

    def test_get_by_code(self):
        """Test looking up data source by code"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )

        # Find by code
        found = self.DataSource.get_by_code("test_crvs")
        self.assertEqual(found, ds)

    def test_get_by_code_not_found(self):
        """Test get_by_code raises error when not found"""
        with self.assertRaises(UserError) as cm:
            self.DataSource.get_by_code("nonexistent")
        self.assertIn("not found", str(cm.exception).lower())

    def test_get_by_code_inactive(self):
        """Test get_by_code ignores inactive data sources"""
        self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "active": False,
            }
        )
        # Note: ds is intentionally not stored as we're testing that inactive sources are ignored

        with self.assertRaises(UserError) as cm:
            self.DataSource.get_by_code("test_crvs")
        self.assertIn("inactive", str(cm.exception).lower())

    def test_get_by_registry_type(self):
        """Test looking up data sources by registry type"""
        # Create CRVS data source
        ds_crvs = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "registry_type": "crvs",
            }
        )

        # Create IBR data source
        ds_ibr = self.DataSource.create(
            {
                "name": "Test IBR",
                "code": "test_ibr",
                "base_url": "https://ibr.example.org/api",
                "auth_type": "none",
                "registry_type": "ibr",
            }
        )

        # Find CRVS sources
        crvs_sources = self.DataSource.get_by_registry_type("crvs")
        self.assertIn(ds_crvs, crvs_sources)
        self.assertNotIn(ds_ibr, crvs_sources)

        # Find IBR sources
        ibr_sources = self.DataSource.get_by_registry_type("ibr")
        self.assertIn(ds_ibr, ibr_sources)
        self.assertNotIn(ds_crvs, ibr_sources)

    def test_get_by_registry_type_inactive(self):
        """Test get_by_registry_type ignores inactive data sources"""
        # Create active CRVS data source
        ds_active = self.DataSource.create(
            {
                "name": "Test CRVS Active",
                "code": "test_crvs_active",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "registry_type": "crvs",
            }
        )

        # Create inactive CRVS data source
        ds_inactive = self.DataSource.create(
            {
                "name": "Test CRVS Inactive",
                "code": "test_crvs_inactive",
                "base_url": "https://crvs2.example.org/api",
                "auth_type": "none",
                "registry_type": "crvs",
                "active": False,
            }
        )

        # Find CRVS sources
        crvs_sources = self.DataSource.get_by_registry_type("crvs")
        self.assertIn(ds_active, crvs_sources)
        self.assertNotIn(ds_inactive, crvs_sources)

    @patch("httpx.Client")
    def test_get_oauth2_token_success(self, mock_client_class):
        """Test OAuth2 token retrieval success"""
        # Create data source with OAuth2
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "oauth2",
                "oauth2_token_url": "https://auth.example.org/token",
                "oauth2_client_id": "client123",
                "oauth2_client_secret": "secret456",
                "our_sender_id": "openspp.example.org",
            }
        )

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_token_12345",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        # Get token
        token = ds.get_oauth2_token()

        self.assertEqual(token, "test_token_12345")
        self.assertTrue(ds._oauth2_access_token)
        self.assertTrue(ds._oauth2_token_expires_at)

    @patch("httpx.Client")
    def test_get_oauth2_token_cached(self, mock_client_class):
        """Test OAuth2 token caching"""
        from datetime import timedelta

        from odoo import fields

        # Create data source with OAuth2
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "oauth2",
                "oauth2_token_url": "https://auth.example.org/token",
                "oauth2_client_id": "client123",
                "oauth2_client_secret": "secret456",
                "our_sender_id": "openspp.example.org",
            }
        )

        # Set cached token that's still valid
        now = fields.Datetime.now()
        ds.write(
            {
                "_oauth2_access_token": "cached_token",
                "_oauth2_token_expires_at": now + timedelta(hours=1),
            }
        )

        # Get token - should use cache
        token = ds.get_oauth2_token()

        self.assertEqual(token, "cached_token")
        # HTTP client should not be called
        mock_client_class.assert_not_called()

    def test_get_oauth2_token_wrong_auth_type(self):
        """Test get_oauth2_token fails for non-OAuth2 auth"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )

        with self.assertRaises(UserError) as cm:
            ds.get_oauth2_token()
        self.assertIn("oauth2", str(cm.exception).lower())

    @patch("httpx.Client")
    def test_test_connection_success(self, mock_client_class):
        """Test successful connection test"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        # Test connection
        result = ds.test_connection()

        self.assertEqual(ds.state, "active")
        self.assertTrue(ds.last_test_date)
        self.assertFalse(ds.last_error)
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")

    @patch("httpx.Client")
    def test_test_connection_failure(self, mock_client_class):
        """Test failed connection test"""
        import httpx

        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )

        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request = MagicMock()

        def raise_status():
            raise httpx.HTTPStatusError("Server Error", request=mock_request, response=mock_response)

        mock_response.raise_for_status = raise_status

        mock_client = MagicMock()
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        # Test connection
        result = ds.test_connection()

        self.assertEqual(ds.state, "error")
        self.assertTrue(ds.last_error)
        self.assertEqual(result["params"]["type"], "danger")

    def test_get_headers_none_auth(self):
        """Test get_headers with no authentication"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )

        headers = ds.get_headers()

        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["Accept"], "application/json")
        self.assertNotIn("Authorization", headers)

    @patch("httpx.Client")
    def test_get_headers_oauth2(self, mock_client_class):
        """Test get_headers with OAuth2 authentication"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "oauth2",
                "oauth2_token_url": "https://auth.example.org/token",
                "oauth2_client_id": "client123",
                "oauth2_client_secret": "secret456",
                "our_sender_id": "openspp.example.org",
            }
        )

        # Mock OAuth2 token response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "test_token_12345",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client_class.return_value = mock_client

        headers = ds.get_headers()

        self.assertEqual(headers["Authorization"], "Bearer test_token_12345")

    def test_default_values(self):
        """Test default field values"""
        ds = self.DataSource.create(
            {
                "name": "Test CRVS",
                "code": "test_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
            }
        )

        self.assertEqual(ds.auth_type, "none")
        self.assertTrue(ds.verify_ssl)
        self.assertEqual(ds.timeout, 30)
        self.assertTrue(ds.active)
        self.assertEqual(ds.state, "draft")
        self.assertEqual(ds.search_endpoint, "/registry/sync/search")
        self.assertEqual(ds.subscribe_endpoint, "/registry/subscribe")
        self.assertEqual(ds.auth_endpoint, "/oauth2/client/token")
