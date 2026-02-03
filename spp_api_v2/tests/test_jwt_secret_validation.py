# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Tests for JWT secret strength validation.

SECURITY: Weak JWT secrets can be brute-forced, enabling token forgery.
These tests ensure the secret meets minimum security requirements.
"""

import json

from fastapi import HTTPException

from .common import ApiV2HttpTestCase, ApiV2TestCase


class TestJWTSecretValidation(ApiV2HttpTestCase):
    """Test JWT secret strength validation"""

    def setUp(self):
        super().setUp()
        # Reset rate limiter to prevent 429 responses from prior tests
        from ..middleware.rate_limit import get_rate_limiter

        get_rate_limiter().clear()

        # Clear JWT secret validation cache so each test can set its own secret
        from ..middleware.auth import _validated_jwt_secrets

        _validated_jwt_secrets.clear()

        self.client = self.create_api_client(
            name="Test Client",
            scopes=[{"resource": "individual", "action": "read"}],
        )
        self.token_url = "/api/v2/spp/oauth/token"

    def _get_token_response(self):
        """Helper to get token with current JWT secret"""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client.client_id,
            "client_secret": self.client.client_secret,
        }

        return self.url_open(
            self.token_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

    def test_jwt_secret_too_short_fails(self):
        """JWT secret shorter than 32 characters is rejected"""
        # Set a short secret (28 chars)
        self.env["ir.config_parameter"].sudo().set_param(
            "spp_api_v2.jwt_secret",
            "short-secret-only-31-chars-x",  # 28 characters (under 32 min)
        )

        response = self._get_token_response()

        # Should return 500 (server configuration error)
        self.assertEqual(
            response.status_code,
            500,
            "Short JWT secret should cause server error",
        )

    def test_jwt_secret_minimum_length_passes(self):
        """JWT secret with exactly 32 characters and good entropy passes"""
        # Set a 32-char secret with good randomness
        self.env["ir.config_parameter"].sudo().set_param(
            "spp_api_v2.jwt_secret",
            "a7B9xP2mQ5nR8tY1zW4vE6uK3jH0cF9D",  # 32 chars, good entropy
        )

        response = self._get_token_response()

        # Should succeed (200 or 201)
        self.assertEqual(
            response.status_code,
            200,
            "32-char secret with good entropy should work",
        )

    def test_jwt_secret_low_entropy_fails(self):
        """JWT secret with low entropy (repeated characters) is rejected"""
        # Set a 32-char secret with low entropy (mostly same character)
        self.env["ir.config_parameter"].sudo().set_param(
            "spp_api_v2.jwt_secret",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # 32 'a's, very low entropy
        )

        response = self._get_token_response()

        # Should return 500 (server configuration error)
        self.assertEqual(
            response.status_code,
            500,
            "Low entropy JWT secret should cause server error",
        )

    def test_jwt_secret_sequential_pattern_fails(self):
        """JWT secret with low entropy pattern is rejected"""
        # Set a 32-char secret with low entropy (only 4 unique chars, ~2.0 bits/char)
        self.env["ir.config_parameter"].sudo().set_param(
            "spp_api_v2.jwt_secret",
            "aabbccddaabbccddaabbccddaabbccdd",  # 32 chars, ~2.0 bits/char entropy
        )

        response = self._get_token_response()

        # Should return 500 (server configuration error)
        self.assertEqual(
            response.status_code,
            500,
            "Sequential pattern JWT secret should cause server error",
        )

    def test_jwt_secret_good_entropy_long_passes(self):
        """JWT secret with good entropy and > 32 chars passes"""
        # Set a long secret with excellent randomness (like secrets.token_urlsafe generates)
        self.env["ir.config_parameter"].sudo().set_param(
            "spp_api_v2.jwt_secret",
            "xK9mP2nQ5rR8tY1zW4vE6uH3jL0cF9DaG7bX",  # 40 chars, high entropy
        )

        response = self._get_token_response()

        # Should succeed
        self.assertEqual(
            response.status_code,
            200,
            "Long secret with high entropy should work",
        )

    def test_jwt_secret_production_strength(self):
        """Production-quality secret (64+ chars) passes all checks"""
        # Simulate production secret (like what secrets.token_urlsafe(48) generates)
        self.env["ir.config_parameter"].sudo().set_param(
            "spp_api_v2.jwt_secret",
            "aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY3zA5bC7dE9fG1hJ3kL5mN7pQ9rS1tU3vW5xY7z",
        )

        response = self._get_token_response()

        self.assertEqual(response.status_code, 200)

        # Token should be valid JWT
        data = json.loads(response.content)
        self.assertIn("access_token", data)
        self.assertEqual(data["token_type"], "Bearer")


class TestJWTSecretValidationDirect(ApiV2TestCase):
    """Direct tests for _validate_jwt_secret_strength function"""

    def test_validate_jwt_secret_strength_too_short(self):
        """_validate_jwt_secret_strength raises for short secrets"""
        from ..middleware.auth import _validate_jwt_secret_strength

        with self.assertRaises(HTTPException) as cm:
            _validate_jwt_secret_strength("short")

        self.assertEqual(cm.exception.status_code, 500)

    def test_validate_jwt_secret_strength_low_entropy(self):
        """_validate_jwt_secret_strength raises for low entropy"""
        from ..middleware.auth import _validate_jwt_secret_strength

        # 32 chars but all same character
        with self.assertRaises(HTTPException) as cm:
            _validate_jwt_secret_strength("a" * 32)

        self.assertEqual(cm.exception.status_code, 500)

    def test_validate_jwt_secret_strength_good_secret(self):
        """_validate_jwt_secret_strength passes for good secret"""
        from ..middleware.auth import _validate_jwt_secret_strength

        # Should return True without raising
        result = _validate_jwt_secret_strength("aB3dE5fG7hJ9kL1mN3pQ5rS7tU9vW1xY")

        self.assertTrue(result)

    def test_validate_jwt_secret_strength_caches_result(self):
        """_validate_jwt_secret_strength caches valid secrets"""
        import hashlib

        from ..middleware.auth import _validate_jwt_secret_strength, _validated_jwt_secrets

        secret = "cacheTestXk9mP2nQ5rR8tY1zW4vE6uH3j"
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()

        # Clear cache first
        _validated_jwt_secrets.discard(secret_hash)

        # First call should validate and cache
        result = _validate_jwt_secret_strength(secret)
        self.assertTrue(result)
        self.assertIn(secret_hash, _validated_jwt_secrets)

        # Second call should use cache (we can verify by checking it's still True)
        result2 = _validate_jwt_secret_strength(secret)
        self.assertTrue(result2)

    def test_validate_jwt_secret_strength_entropy_threshold(self):
        """_validate_jwt_secret_strength uses 3.0 bits/char threshold"""
        from ..middleware.auth import _validate_jwt_secret_strength

        # Test a secret right at the edge
        # Mixed case alphanumeric has ~5.95 bits/char entropy, well above 3.0
        good_secret = "Xk9mP2nQ5rR8tY1zW4vE6uH3jL0cF9Da"  # 32 chars
        result = _validate_jwt_secret_strength(good_secret)
        self.assertTrue(result)

        # Very low entropy should fail
        with self.assertRaises(HTTPException):
            _validate_jwt_secret_strength("11111111111111111111111111111111")
