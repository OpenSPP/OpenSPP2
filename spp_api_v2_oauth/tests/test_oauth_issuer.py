# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the spp.oauth.issuer model.

The model represents an external RS256 token issuer (e.g., a Keycloak realm)
that the bridge will accept tokens from. Constraints exist so that bad
configuration is rejected at write time rather than at token-verification time.
"""

import psycopg2
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


def _fresh_public_key_pem():
    """Generate a throwaway RSA public key in PEM form for use as a fixture."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )


@tagged("post_install", "-at_install")
class TestOAuthIssuerModel(TransactionCase):
    """Constraint tests for spp.oauth.issuer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.IssuerModel = cls.env["spp.oauth.issuer"]
        cls.sample_pem = _fresh_public_key_pem()

    def _make_jwks_vals(self, **overrides):
        vals = {
            "name": "Test Keycloak",
            "issuer": "https://keycloak.example.com/realms/test",
            "audience": "openspp",
            "key_source": "jwks_uri",
            "jwks_uri": "https://keycloak.example.com/realms/test/protocol/openid-connect/certs",
        }
        vals.update(overrides)
        return vals

    def _make_pem_vals(self, **overrides):
        vals = {
            "name": "Test Static-PEM Issuer",
            "issuer": "https://idp.example.com",
            "audience": "openspp",
            "key_source": "public_key",
            "public_key": self.sample_pem,
        }
        vals.update(overrides)
        return vals

    # ------------------------------------------------------------------ valid
    def test_create_jwks_issuer(self):
        """A well-formed JWKS issuer record is accepted."""
        rec = self.IssuerModel.create(self._make_jwks_vals())
        self.assertTrue(rec.id)
        self.assertEqual(rec.client_claim, "client_id")
        self.assertEqual(rec.algorithms, "RS256")
        self.assertTrue(rec.active)

    def test_create_pem_issuer(self):
        """A well-formed static-PEM issuer record is accepted."""
        rec = self.IssuerModel.create(self._make_pem_vals())
        self.assertTrue(rec.id)
        self.assertEqual(rec.key_source, "public_key")

    # ------------------------------------------------------------------ required fields
    def test_name_required(self):
        with self.assertRaises(psycopg2.IntegrityError), mute_logger("odoo.sql_db"):
            self.IssuerModel.create(self._make_jwks_vals(name=False))

    def test_issuer_required(self):
        with self.assertRaises(psycopg2.IntegrityError), mute_logger("odoo.sql_db"):
            self.IssuerModel.create(self._make_jwks_vals(issuer=False))

    def test_audience_required(self):
        with self.assertRaises(psycopg2.IntegrityError), mute_logger("odoo.sql_db"):
            self.IssuerModel.create(self._make_jwks_vals(audience=False))

    def test_unique_issuer(self):
        """The issuer claim value must be unique across records."""
        self.IssuerModel.create(self._make_jwks_vals(issuer="https://idp.example.com/dup"))
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_pem_vals(name="Another", issuer="https://idp.example.com/dup"))

    # ------------------------------------------------------------------ key_source consistency
    def test_jwks_uri_required_when_jwks_source(self):
        """key_source=jwks_uri without a jwks_uri value is rejected."""
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_jwks_vals(jwks_uri=False))

    def test_public_key_required_when_pem_source(self):
        """key_source=public_key without a public_key value is rejected."""
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_pem_vals(public_key=False))

    # ------------------------------------------------------------------ URL scheme
    def test_jwks_uri_https_accepted(self):
        rec = self.IssuerModel.create(
            self._make_jwks_vals(jwks_uri="https://example.com/jwks.json", issuer="iss-https")
        )
        self.assertTrue(rec.id)

    def test_jwks_uri_plain_http_rejected(self):
        """Plain http:// (non-loopback) is rejected to prevent MitM key swap."""
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_jwks_vals(jwks_uri="http://example.com/jwks.json", issuer="iss-http"))

    def test_jwks_uri_localhost_http_accepted(self):
        """http://localhost is allowed for local-dev IdPs (Keycloak on a dev host)."""
        rec = self.IssuerModel.create(self._make_jwks_vals(jwks_uri="http://localhost:8080/certs", issuer="iss-local"))
        self.assertTrue(rec.id)

    def test_jwks_uri_loopback_http_accepted(self):
        rec = self.IssuerModel.create(
            self._make_jwks_vals(jwks_uri="http://127.0.0.1:8080/certs", issuer="iss-loopback")
        )
        self.assertTrue(rec.id)

    def test_jwks_uri_malformed_rejected(self):
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_jwks_vals(jwks_uri="not-a-url", issuer="iss-malformed"))

    # ------------------------------------------------------------------ PEM validation
    def test_invalid_pem_rejected(self):
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(
                self._make_pem_vals(public_key="-----BEGIN PUBLIC KEY-----\nnot a real key\n-----END PUBLIC KEY-----")
            )

    def test_private_key_pem_rejected(self):
        """A PRIVATE-key PEM in the public_key field must be rejected."""
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_pem_vals(public_key=priv_pem, issuer="iss-priv"))

    # ------------------------------------------------------------------ algorithms
    def test_algorithms_default_is_rs256(self):
        rec = self.IssuerModel.create(self._make_jwks_vals(issuer="iss-alg-default"))
        self.assertEqual(rec.algorithms, "RS256")

    def test_algorithms_whitelist_accepted(self):
        rec = self.IssuerModel.create(self._make_jwks_vals(algorithms="RS256,RS384", issuer="iss-alg-ok"))
        self.assertEqual(rec.algorithms, "RS256,RS384")

    def test_algorithms_unknown_rejected(self):
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_jwks_vals(algorithms="HS256", issuer="iss-alg-bad-1"))

    def test_algorithms_none_alg_rejected(self):
        """`none` must never be allowed — JWT-none-alg is a classic attack."""
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_jwks_vals(algorithms="none", issuer="iss-alg-bad-2"))

    def test_algorithms_empty_rejected(self):
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_jwks_vals(algorithms="", issuer="iss-alg-empty"))

    # ------------------------------------------------------------------ client_claim
    def test_client_claim_default(self):
        rec = self.IssuerModel.create(self._make_jwks_vals(issuer="iss-claim-default"))
        self.assertEqual(rec.client_claim, "client_id")

    def test_client_claim_custom_accepted(self):
        rec = self.IssuerModel.create(self._make_jwks_vals(client_claim="azp", issuer="iss-claim-azp"))
        self.assertEqual(rec.client_claim, "azp")

    def test_client_claim_empty_rejected(self):
        with self.assertRaises(ValidationError):
            self.IssuerModel.create(self._make_jwks_vals(client_claim="", issuer="iss-claim-empty"))

    # ------------------------------------------------------------------ defaults / misc
    def test_active_defaults_true(self):
        rec = self.IssuerModel.create(self._make_jwks_vals(issuer="iss-active"))
        self.assertTrue(rec.active)

    def test_jwks_cache_ttl_default(self):
        rec = self.IssuerModel.create(self._make_jwks_vals(issuer="iss-ttl"))
        self.assertEqual(rec.jwks_cache_ttl_seconds, 3600)

    def test_http_timeout_default(self):
        rec = self.IssuerModel.create(self._make_jwks_vals(issuer="iss-timeout"))
        self.assertEqual(rec.http_timeout_seconds, 5)
