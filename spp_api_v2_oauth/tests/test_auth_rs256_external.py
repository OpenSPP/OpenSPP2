# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for RS256 token verification against external trusted issuers.

These exercise the iss-based dispatcher in auth_rs256.py: tokens whose `iss`
matches a registered `spp.oauth.issuer` record are verified using that
record's key source (static PEM or JWKS), and the configured `client_claim`
is used to resolve the calling `spp.api.client`.
"""

from datetime import UTC, datetime, timedelta
from unittest import mock

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from odoo.tests import tagged

from fastapi import HTTPException

from .common import OAuthBridgeTestCase

EXT_ISSUER_URL = "https://idp.example.com/realms/ext"
EXT_AUDIENCE = "openspp-ext"


def _generate_rsa_keypair():
    """Return (private_pem, public_pem, private_key_obj)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem, key


@tagged("post_install", "-at_install")
class TestExternalRS256StaticPEM(OAuthBridgeTestCase):
    """Bridge accepts tokens signed by an external issuer (static-PEM key source)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ext_private_pem, cls.ext_public_pem, cls.ext_private_key_obj = _generate_rsa_keypair()
        cls.issuer_rec = cls.env["spp.oauth.issuer"].create(
            {
                "name": "Test External IdP (PEM)",
                "issuer": EXT_ISSUER_URL,
                "audience": EXT_AUDIENCE,
                "key_source": "public_key",
                "public_key": cls.ext_public_pem,
            }
        )

    def _make_external_token(self, payload_overrides=None, private_pem=None):
        now = datetime.now(tz=UTC)
        payload = {
            "iss": EXT_ISSUER_URL,
            "aud": EXT_AUDIENCE,
            "exp": now + timedelta(hours=1),
            "iat": now,
            "sub": "external-subject-uuid",
            "client_id": self.api_client.client_id,
        }
        if payload_overrides:
            payload.update(payload_overrides)
        key = private_pem or self.ext_private_pem
        return jwt.encode(payload, key, algorithm="RS256")

    # -------------------------------------------------------------- happy path
    def test_external_pem_token_accepted(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self._make_external_token()
        creds = self.make_credentials(token)

        client = get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(client.client_id, self.api_client.client_id)

    def test_external_pem_token_tampered_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self._make_external_token()
        # Flip a character in the signature segment
        parts = token.split(".")
        sig = parts[2]
        parts[2] = ("A" if sig[0] != "A" else "B") + sig[1:]
        tampered = ".".join(parts)
        creds = self.make_credentials(tampered)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_external_pem_token_wrong_key_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        other_private_pem, _, _ = _generate_rsa_keypair()
        token = self._make_external_token(private_pem=other_private_pem)
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------- dispatch
    def test_unknown_issuer_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self._make_external_token(payload_overrides={"iss": "https://no-such-issuer.example.com"})
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("issuer", ctx.exception.detail.lower())

    def test_missing_iss_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        now = datetime.now(tz=UTC)
        payload = {
            "aud": EXT_AUDIENCE,
            "exp": now + timedelta(hours=1),
            "iat": now,
            "client_id": self.api_client.client_id,
        }
        token = jwt.encode(payload, self.ext_private_pem, algorithm="RS256")
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_inactive_issuer_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        self.issuer_rec.active = False
        self.addCleanup(setattr, self.issuer_rec, "active", True)

        token = self._make_external_token()
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------- claim checks
    def test_external_token_wrong_audience_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self._make_external_token(payload_overrides={"aud": "some-other-aud"})
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_external_token_expired_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        past = datetime.now(tz=UTC) - timedelta(hours=1)
        token = self._make_external_token(payload_overrides={"exp": past, "iat": past - timedelta(hours=1)})
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------- client_claim mapping
    def test_client_claim_default_uses_client_id(self):
        """With default client_claim='client_id', the bridge reads `client_id`."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self._make_external_token()
        creds = self.make_credentials(token)

        client = get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(client.client_id, self.api_client.client_id)

    def test_client_claim_custom_used_for_lookup(self):
        """If client_claim is set to 'azp', the bridge reads `azp` for lookup."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        self.issuer_rec.client_claim = "azp"
        self.addCleanup(setattr, self.issuer_rec, "client_claim", "client_id")

        # Put the api_client value in `azp` and something else in `client_id`
        token = self._make_external_token(
            payload_overrides={
                "azp": self.api_client.client_id,
                "client_id": "not-the-right-value",
            }
        )
        creds = self.make_credentials(token)

        client = get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(client.client_id, self.api_client.client_id)

    def test_client_claim_missing_value_rejected(self):
        """If the configured claim is absent from the token payload, reject."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        self.issuer_rec.client_claim = "azp"
        self.addCleanup(setattr, self.issuer_rec, "client_claim", "client_id")

        token = self._make_external_token()  # no `azp` claim
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    # -------------------------------------------------------------- isolation
    def test_internal_path_still_uses_spp_oauth_key(self):
        """Adding an external issuer must not break the internal RS256 path."""
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self.generate_rs256_token()  # uses internal JWT_ISSUER
        creds = self.make_credentials(token)

        client = get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(client.client_id, self.api_client.client_id)


@tagged("post_install", "-at_install")
class TestExternalRS256JWKS(OAuthBridgeTestCase):
    """Bridge accepts tokens signed by an external issuer (JWKS key source).

    PyJWKClient.get_signing_key_from_jwt is patched so tests never make real
    HTTP calls.
    """

    JWKS_URI = "https://idp.example.com/realms/ext/protocol/openid-connect/certs"
    KID = "test-kid-1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ext_private_pem, cls.ext_public_pem, cls.ext_private_key_obj = _generate_rsa_keypair()
        cls.issuer_rec = cls.env["spp.oauth.issuer"].create(
            {
                "name": "Test External IdP (JWKS)",
                "issuer": EXT_ISSUER_URL + "/jwks",
                "audience": EXT_AUDIENCE,
                "key_source": "jwks_uri",
                "jwks_uri": cls.JWKS_URI,
            }
        )

    def setUp(self):
        super().setUp()
        from ..tools import jwks_cache

        jwks_cache.clear()

        signing_key = mock.MagicMock()
        signing_key.key = self.ext_public_key_obj_for_pyjwt()

        patcher = mock.patch(
            "jwt.PyJWKClient.get_signing_key_from_jwt",
            return_value=signing_key,
        )
        self.mock_get_signing_key = patcher.start()
        self.addCleanup(patcher.stop)

    def ext_public_key_obj_for_pyjwt(self):
        """PyJWT accepts a cryptography public-key object as the `key` argument."""
        return self.ext_private_key_obj.public_key()

    def _make_external_token(self, payload_overrides=None, private_pem=None, headers=None):
        now = datetime.now(tz=UTC)
        payload = {
            "iss": self.issuer_rec.issuer,
            "aud": EXT_AUDIENCE,
            "exp": now + timedelta(hours=1),
            "iat": now,
            "sub": "external-subject-uuid",
            "client_id": self.api_client.client_id,
        }
        if payload_overrides:
            payload.update(payload_overrides)
        key = private_pem or self.ext_private_pem
        token_headers = {"kid": self.KID}
        if headers:
            token_headers.update(headers)
        return jwt.encode(payload, key, algorithm="RS256", headers=token_headers)

    def test_jwks_token_accepted(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self._make_external_token()
        creds = self.make_credentials(token)

        client = get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(client.client_id, self.api_client.client_id)
        self.mock_get_signing_key.assert_called_once()

    def test_jwks_token_expired_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        past = datetime.now(tz=UTC) - timedelta(hours=1)
        token = self._make_external_token(payload_overrides={"exp": past, "iat": past - timedelta(hours=1)})
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_jwks_token_wrong_audience_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        token = self._make_external_token(payload_overrides={"aud": "wrong-aud"})
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_jwks_token_signed_with_other_key_rejected(self):
        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        other_private_pem, _, _ = _generate_rsa_keypair()
        token = self._make_external_token(private_pem=other_private_pem)
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_jwks_fetch_failure_rejected(self):
        from jwt.exceptions import PyJWKClientError

        from ..middleware.auth_rs256 import get_authenticated_client_rs256

        self.mock_get_signing_key.side_effect = PyJWKClientError("network down")

        token = self._make_external_token()
        creds = self.make_credentials(token)

        with self.assertRaises(HTTPException) as ctx:
            get_authenticated_client_rs256(creds, self.env)
        self.assertEqual(ctx.exception.status_code, 401)
