# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the DCI bearer-token middleware.

The bearer-token dependency previously accepted *any* non-empty token when
``dci.api_tokens`` was unset. These tests pin the new fail-closed default
(``dci.api_tokens_required`` defaults to ``'true'``) and the explicit
opt-out path, plus regression tests for the existing behaviours so they
do not silently regress.
"""

import asyncio
import os
from datetime import datetime, timedelta

from odoo.tests import tagged

from fastapi import HTTPException

from .common import DCIServerCommon

# 48-char high-entropy secret so spp_api_v2's _validate_jwt_secret_strength
# (>=32 chars, entropy >= 3.0) accepts it.
_TEST_JWT_SECRET = "Zx9Kq2Lm7Pw4Rt6Yv1Nb8Hc3Jd5Fg0SaUeWiOqTzXyMnBvCr"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@tagged("post_install", "-at_install")
class TestBearerTokenAuth(DCIServerCommon):
    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.middleware import signature as sig_module

        self.sig_module = sig_module
        self.verify_bearer_token = sig_module.verify_bearer_token

        # Reset the "warning already logged" guards between tests so each
        # case exercises a fresh logger path.
        sig_module._bearer_bypass_warning_logged = False
        sig_module._empty_tokens_warning_logged = False

        self.ICP = self.env["ir.config_parameter"].sudo()

    def _call(self, authorization=None):
        return _run(self.verify_bearer_token(self.env, authorization))

    # --- Fail-closed default --------------------------------------------------

    def test_empty_api_tokens_rejects_by_default(self):
        """With dci.api_tokens unset and no explicit opt-out, the bearer
        dependency must reject all tokens. This was the security hole the
        previous implementation left wide open."""
        self.ICP.set_param("dci.api_tokens", "")
        self.ICP.set_param("dci.api_tokens_required", "")  # default == required

        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer anything-goes")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_empty_api_tokens_required_explicit_true_rejects(self):
        self.ICP.set_param("dci.api_tokens", "")
        self.ICP.set_param("dci.api_tokens_required", "true")

        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer anything-goes")
        self.assertEqual(ctx.exception.status_code, 401)

    # --- Explicit opt-out -----------------------------------------------------

    def test_explicit_opt_out_accepts_any_token(self):
        """Setting dci.api_tokens_required=false preserves the legacy
        accept-any-non-empty-token behaviour for development."""
        self.ICP.set_param("dci.api_tokens", "")
        self.ICP.set_param("dci.api_tokens_required", "false")

        token = self._call("Bearer dev-token-123")
        self.assertEqual(token, "dev-token-123")

    # --- Configured token list (regression) -----------------------------------

    def test_configured_tokens_accept_match(self):
        self.ICP.set_param("dci.api_tokens", "alpha,beta")

        self.assertEqual(self._call("Bearer alpha"), "alpha")
        self.assertEqual(self._call("Bearer beta"), "beta")

    def test_configured_tokens_reject_non_match(self):
        self.ICP.set_param("dci.api_tokens", "alpha,beta")

        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer gamma")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_token_comparison_is_constant_time(self):
        """The compare loop must call hmac.compare_digest once per
        configured candidate (no short-circuit on match). A short-circuit
        would leak the accepted token via response-time side channels."""
        import hmac as hmac_module
        from unittest.mock import patch

        self.ICP.set_param("dci.api_tokens", "alpha,beta,gamma")

        with patch(
            "odoo.addons.spp_dci_server.middleware.signature.hmac.compare_digest",
            wraps=hmac_module.compare_digest,
        ) as compare:
            self.assertEqual(self._call("Bearer alpha"), "alpha")
        self.assertEqual(
            compare.call_count,
            3,
            "constant-time loop must compare against every configured token",
        )

    # --- Bypass flag (regression) ---------------------------------------------

    def test_bypass_bearer_auth_returns_dev_bypass(self):
        """When the operator explicitly disables bearer auth, the helper
        returns the well-known 'development-bypass' sentinel."""
        self.ICP.set_param("dci.bypass_bearer_auth", "true")
        try:
            token = self._call(None)
            self.assertEqual(token, "development-bypass")
        finally:
            self.ICP.set_param("dci.bypass_bearer_auth", "false")

    # --- Header parsing (regression) ------------------------------------------

    def test_missing_authorization_header_rejects(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call(None)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_non_bearer_prefix_rejects(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call("Basic dXNlcjpwYXNz")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_empty_bearer_token_rejects(self):
        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer ")
        self.assertEqual(ctx.exception.status_code, 401)

    # --- Non-ASCII / malformed credentials (regression) -----------------------

    def test_non_ascii_bearer_token_rejected_with_401(self):
        """A Bearer token carrying non-ASCII characters must be rejected as a
        401, not crash the dependency. HTTP headers are latin-1-decoded, so a
        non-ASCII header byte reaches this code as a non-ASCII str; passing it
        to hmac.compare_digest raises TypeError, which - being neither an
        HTTPException nor caught here - escaped as a generic 500 (with a stack
        trace in the log) on every bearer-authenticated DCI endpoint."""
        self.ICP.set_param("dci.api_tokens", "alpha,beta")

        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer café-ÿ")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_non_ascii_bearer_token_rejected_even_with_empty_list(self):
        """The non-ASCII guard is a single choke point: it rejects before the
        opt-out 'accept any non-empty token' path too, so a non-ASCII token is
        never returned as a valid credential regardless of configuration."""
        self.ICP.set_param("dci.api_tokens", "")
        self.ICP.set_param("dci.api_tokens_required", "false")

        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer café-ÿ")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_control_char_token_treated_as_normal_invalid(self):
        """Control characters are ASCII, so a control-char token passes the
        non-ASCII guard and reaches hmac.compare_digest, which handles it
        without raising. It is simply an ordinary non-match -> 401. This pins
        that the guard deliberately rejects only non-ASCII input, not every
        odd byte, and that control chars do not crash the compare."""
        self.ICP.set_param("dci.api_tokens", "alpha")

        with self.assertRaises(HTTPException) as ctx:
            self._call("Bearer \x00\x01")
        self.assertEqual(ctx.exception.status_code, 401)


@tagged("post_install", "-at_install")
class TestSecurityDefaults(DCIServerCommon):
    """Pin the fail-closed defaults for every dev-mode bypass flag.

    These flags read ``ir.config_parameter`` with ``"false"`` as the
    fallback. If someone later flips that fallback to ``"true"``, the
    middleware would silently start accepting unsigned / unauthenticated
    traffic without anyone noticing - so the defaults are tested
    explicitly here.
    """

    SECURITY_FLAGS = [
        "dci.allow_unsigned_requests",
        "dci.bypass_bearer_auth",
        "dci.allow_http_callbacks",
        "dci.allow_internal_callback_ips",
        "dci.api_tokens_required",  # new flag introduced with the fix
    ]

    def setUp(self):
        super().setUp()
        self.ICP = self.env["ir.config_parameter"].sudo()

    def test_security_flags_default_to_fail_closed(self):
        """Each security flag, when unset, must resolve to its safe value.

        For the bypass flags ('allow_unsigned_requests',
        'bypass_bearer_auth', 'allow_http_callbacks',
        'allow_internal_callback_ips') the safe default is 'false'.
        For 'api_tokens_required' the safe default is 'true' (required).
        """
        expected = {
            "dci.allow_unsigned_requests": "false",
            "dci.bypass_bearer_auth": "false",
            "dci.allow_http_callbacks": "false",
            "dci.allow_internal_callback_ips": "false",
            "dci.api_tokens_required": "true",
        }
        for key, safe_value in expected.items():
            # Clear so we read the in-code default.
            self.ICP.set_param(key, "")
            from odoo.addons.spp_dci_server.middleware.signature import (
                _read_security_flag,
            )

            self.assertEqual(
                _read_security_flag(self.env, key),
                safe_value,
                f"{key} must default to {safe_value!r} (fail-closed)",
            )


@tagged("post_install", "-at_install")
class TestOAuth2BearerToken(DCIServerCommon):
    """The bearer dependency also accepts OAuth2 access tokens (spp_api_v2
    JWTs) so DCI callers can authenticate with client-credentials, not only
    static tokens."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.middleware import signature as sig_module

        self.verify_bearer_token = sig_module.verify_bearer_token
        sig_module._bearer_bypass_warning_logged = False
        sig_module._empty_tokens_warning_logged = False
        self.ICP = self.env["ir.config_parameter"].sudo()
        # Sign with the secret the verifier will use (env var wins over param).
        self.secret = os.environ.get("OPENSPP_JWT_SECRET") or _TEST_JWT_SECRET
        if not os.environ.get("OPENSPP_JWT_SECRET"):
            self.ICP.set_param("spp_api_v2.jwt_secret", self.secret)
        self.client = self.env["spp.api.client"].create(
            {
                "name": "DCI OAuth Test Client",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type_government.id,
            }
        )

    def _call(self, authorization=None):
        return _run(self.verify_bearer_token(self.env, authorization))

    def _mint_jwt(self, client_id=None, expires_in_hours=1, secret=None):
        import jwt

        now = datetime.utcnow()
        payload = {
            "iss": "openspp-api-v2",
            "aud": "openspp",
            "sub": client_id or self.client.client_id,
            "client_id": client_id or self.client.client_id,
            "iat": now,
            "exp": now + timedelta(hours=expires_in_hours),
            "scopes": [],
        }
        return jwt.encode(payload, secret or self.secret, algorithm="HS256")

    def test_valid_oauth2_jwt_accepted(self):
        """A valid OAuth2 JWT is accepted even with no static tokens and
        dci.api_tokens_required=true."""
        self.ICP.set_param("dci.api_tokens", "")
        self.ICP.set_param("dci.api_tokens_required", "true")
        token = self._mint_jwt()
        self.assertEqual(self._call(f"Bearer {token}"), token)

    def test_oauth2_jwt_accepted_alongside_nonmatching_static(self):
        """A valid OAuth2 JWT is accepted even when a (non-matching) static
        token list is configured."""
        self.ICP.set_param("dci.api_tokens", "some-other-static-token")
        token = self._mint_jwt()
        self.assertEqual(self._call(f"Bearer {token}"), token)

    def test_static_token_still_accepted(self):
        """Regression: configured static tokens keep working."""
        self.ICP.set_param("dci.api_tokens", "static-abc")
        self.assertEqual(self._call("Bearer static-abc"), "static-abc")

    def test_expired_oauth2_jwt_rejected(self):
        self.ICP.set_param("dci.api_tokens", "")
        token = self._mint_jwt(expires_in_hours=-1)
        with self.assertRaises(HTTPException) as ctx:
            self._call(f"Bearer {token}")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_invalid_signature_jwt_rejected(self):
        self.ICP.set_param("dci.api_tokens", "")
        token = self._mint_jwt(secret="wrong-but-long-enough-secret-aB3dE6fH9jK2mN5pQ8rT1v")
        with self.assertRaises(HTTPException) as ctx:
            self._call(f"Bearer {token}")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_oauth2_jwt_for_inactive_client_rejected(self):
        self.ICP.set_param("dci.api_tokens", "")
        self.client.active = False
        token = self._mint_jwt()
        with self.assertRaises(HTTPException) as ctx:
            self._call(f"Bearer {token}")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_oauth2_jwt_unknown_client_rejected(self):
        self.ICP.set_param("dci.api_tokens", "")
        token = self._mint_jwt(client_id="no-such-client-id")
        with self.assertRaises(HTTPException) as ctx:
            self._call(f"Bearer {token}")
        self.assertEqual(ctx.exception.status_code, 401)
