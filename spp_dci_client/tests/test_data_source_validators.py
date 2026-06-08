# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.dci.data.source @api.constrains validators."""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDataSourceValidators(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]

    def _valid_vals(self, **overrides):
        vals = {
            "name": "Valid DS",
            "code": "valid_ds",
            "base_url": "https://dci.example.org/api",
            "auth_type": "none",
            "our_sender_id": "openspp.test",
        }
        vals.update(overrides)
        return vals

    # --- code format ---------------------------------------------------------

    def test_code_rejects_uppercase(self):
        with self.assertRaises(ValidationError):
            self.DataSource.create(self._valid_vals(code="MixedCase"))

    def test_code_rejects_invalid_chars(self):
        with self.assertRaises(ValidationError):
            self.DataSource.create(self._valid_vals(code="bad-code!"))

    def test_code_accepts_lower_alnum_underscore(self):
        ds = self.DataSource.create(self._valid_vals(code="ok_code_123"))
        self.assertEqual(ds.code, "ok_code_123")

    # --- base_url format -----------------------------------------------------

    def test_base_url_requires_scheme(self):
        with self.assertRaises(ValidationError):
            self.DataSource.create(self._valid_vals(base_url="dci.example.org"))

    def test_base_url_rejects_trailing_slash(self):
        with self.assertRaises(ValidationError):
            self.DataSource.create(self._valid_vals(base_url="https://dci.example.org/"))

    def test_base_url_http_allowed(self):
        ds = self.DataSource.create(self._valid_vals(base_url="http://dci.example.org/api"))
        self.assertTrue(ds.base_url.startswith("http://"))

    # --- oauth2 fields -------------------------------------------------------

    def test_oauth2_requires_token_url(self):
        with self.assertRaises(ValidationError):
            self.DataSource.create(
                self._valid_vals(
                    auth_type="oauth2",
                    oauth2_client_id="cid",
                    oauth2_client_secret="secret",
                )
            )

    def test_oauth2_requires_client_id(self):
        with self.assertRaises(ValidationError):
            self.DataSource.create(
                self._valid_vals(
                    auth_type="oauth2",
                    oauth2_token_url="https://auth.example.org/token",
                    oauth2_client_secret="secret",
                )
            )

    def test_oauth2_requires_client_secret(self):
        with self.assertRaises(ValidationError):
            self.DataSource.create(
                self._valid_vals(
                    auth_type="oauth2",
                    oauth2_token_url="https://auth.example.org/token",
                    oauth2_client_id="cid",
                )
            )

    def test_oauth2_complete_config_ok(self):
        ds = self.DataSource.create(
            self._valid_vals(
                auth_type="oauth2",
                oauth2_token_url="https://auth.example.org/token",
                oauth2_client_id="cid",
                oauth2_client_secret="secret",
            )
        )
        self.assertEqual(ds.auth_type, "oauth2")

    # --- bearer token --------------------------------------------------------

    def test_bearer_requires_token(self):
        with self.assertRaises(ValidationError):
            self.DataSource.create(self._valid_vals(auth_type="bearer"))

    def test_bearer_with_token_ok(self):
        ds = self.DataSource.create(self._valid_vals(auth_type="bearer", bearer_token="tok"))
        self.assertEqual(ds.bearer_token, "tok")

    # --- timeout -------------------------------------------------------------

    def test_timeout_rejects_zero_and_negative(self):
        for bad in (0, -5):
            with self.assertRaises(ValidationError):
                self.DataSource.create(self._valid_vals(code=f"ds_to_{abs(bad)}", timeout=bad))

    def test_timeout_positive_ok(self):
        ds = self.DataSource.create(self._valid_vals(timeout=30))
        self.assertEqual(ds.timeout, 30)

    # --- sender id -----------------------------------------------------------

    def test_sender_id_required_for_authenticated(self):
        with self.assertRaises(ValidationError):
            self.DataSource.create(
                self._valid_vals(
                    auth_type="bearer",
                    bearer_token="tok",
                    our_sender_id=False,
                )
            )

    def test_sender_id_not_required_for_none_auth(self):
        ds = self.DataSource.create(self._valid_vals(auth_type="none", our_sender_id=False))
        self.assertEqual(ds.auth_type, "none")
