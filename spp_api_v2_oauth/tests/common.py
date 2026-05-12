# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Common test utilities for spp_api_v2_oauth tests."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from odoo.tests.common import TransactionCase

from ..constants import JWT_AUDIENCE, JWT_ISSUER

# HS256 test secret (same as spp_api_v2 tests)
HS256_TEST_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


class OAuthBridgeTestCase(TransactionCase):
    """Base class for OAuth bridge tests.

    Sets up RSA key pair and HS256 secret for testing both algorithms.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Generate RSA key pair for testing (2048-bit for speed)
        cls.rsa_private_key_obj = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        cls.rsa_private_key_pem = cls.rsa_private_key_obj.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        cls.rsa_public_key_pem = (
            cls.rsa_private_key_obj.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )

        # Store RSA keys in spp_oauth config parameters
        cls.env["ir.config_parameter"].sudo().set_param("spp_oauth.oauth_private_key", cls.rsa_private_key_pem)
        cls.env["ir.config_parameter"].sudo().set_param("spp_oauth.oauth_public_key", cls.rsa_public_key_pem)

        # Store HS256 secret for spp_api_v2
        cls.env["ir.config_parameter"].sudo().set_param("spp_api_v2.jwt_secret", HS256_TEST_SECRET)

        # Shared "internal" API client: no oauth_issuer_id, reachable via HS256
        # and internal RS256 tokens. External-issuer test classes create their
        # own issuer-linked clients via _make_api_client().
        cls.api_client = cls._make_api_client("OAuth Bridge Test Client")

        # Create test scopes
        cls.env["spp.api.client.scope"].create(
            {
                "client_id": cls.api_client.id,
                "resource": "individual",
                "action": "read",
            }
        )

    @classmethod
    def _make_api_client(cls, name, oauth_issuer_id=None):
        """Create an spp.api.client, optionally linked to a Trusted OAuth Issuer.

        :param name: Display name and partner name.
        :param oauth_issuer_id: integer id of an spp.oauth.issuer record, or None
            for an "internal" client (HS256 + internal RS256 only).
        """
        partner = cls.env["res.partner"].create({"name": f"{name} Org"})
        org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not org_type:
            org_type = cls.env.ref("spp_consent.org_type_government", raise_if_not_found=False)

        vals = {
            "name": name,
            "partner_id": partner.id,
            "is_require_consent": False,
            "legal_basis": "consent",
        }
        if org_type:
            vals["organization_type_id"] = org_type.id
        if oauth_issuer_id:
            vals["oauth_issuer_id"] = oauth_issuer_id

        return cls.env["spp.api.client"].create(vals)

    def _build_jwt_payload(self, overrides=None):
        """Build a standard JWT payload for testing."""
        now = datetime.now(tz=UTC)
        payload = {
            "iss": JWT_ISSUER,
            "sub": self.api_client.client_id,
            "aud": JWT_AUDIENCE,
            "exp": now + timedelta(hours=1),
            "iat": now,
            "client_id": self.api_client.client_id,
            "scopes": ["individual:read"],
        }
        if overrides:
            payload.update(overrides)
        return payload

    def generate_rs256_token(self, payload_overrides=None, private_key=None):
        """Generate an RS256-signed JWT token for testing."""
        payload = self._build_jwt_payload(payload_overrides)
        key = private_key or self.rsa_private_key_pem
        return jwt.encode(payload, key, algorithm="RS256")

    def generate_hs256_token(self, payload_overrides=None):
        """Generate an HS256-signed JWT token for testing."""
        payload = self._build_jwt_payload(payload_overrides)
        return jwt.encode(payload, HS256_TEST_SECRET, algorithm="HS256")

    @staticmethod
    def make_credentials(token):
        """Create a mock HTTPAuthorizationCredentials-like object."""
        return SimpleNamespace(credentials=token)
