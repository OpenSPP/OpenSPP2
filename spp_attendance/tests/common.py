# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Shared fixtures for spp_attendance tests.

Provides an RSA keypair for the spp_oauth signing helpers, standard
attendance fixtures, and a mock for ``odoo.http.request`` so controller
logic can be exercised in a plain (writable) TransactionCase — the
HttpCase layer covers read-only end-to-end smoke separately.
"""

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from odoo.addons.spp_attendance.controllers.controllers import SppAttendanceController


def generate_rsa_keypair():
    """Return (private_pem, public_pem) strings for test signing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


class AttendanceFixtureMixin:
    """setUpClass fixtures shared by the test cases."""

    @classmethod
    def _setup_oauth_keys(cls):
        private_pem, public_pem = generate_rsa_keypair()
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param("spp_oauth.oauth_priv_key", private_pem)
        icp.set_param("spp_oauth.oauth_pub_key", public_pem)

    @classmethod
    def _setup_attendance_fixtures(cls):
        cls.credential = cls.env["spp.attendance.api.client.credential"].create({"name": "Test Client"})
        cls.attendance_type = cls.env["spp.attendance.type"].create({"name": "Training"})
        cls.attendance_location = cls.env["spp.attendance.location"].create({"name": "Community Hall"})
        cls.subscriber = cls.env["spp.attendance.subscriber"].create(
            {
                "person_identifier": "PID-0001",
                "family_name": "Dela Cruz",
                "given_name": "Juan",
            }
        )

    @classmethod
    def _make_bearer_token(cls):
        return cls.env["spp.attendance.api.client.credential"].generate_access_token()


class ControllerTestMixin(AttendanceFixtureMixin):
    """Call controller methods directly with a mocked odoo.http.request."""

    @classmethod
    def _setup_controller(cls):
        cls.controller = SppAttendanceController()

    @contextmanager
    def mock_request(self, body=None, headers=None, token=None):
        """Patch the controller module's ``request`` global.

        Args:
            body: dict serialized to the raw request body (or a raw string)
            headers: extra HTTP headers
            token: bearer token; use "__valid__" for a freshly signed one
        """
        all_headers = dict(headers or {})
        if token == "__valid__":
            token = self._make_bearer_token()
        if token:
            all_headers["Authorization"] = f"Bearer {token}"

        if body is None:
            raw = b"{}"
        elif isinstance(body, (bytes, str)):
            raw = body if isinstance(body, bytes) else body.encode()
        else:
            raw = json.dumps(body).encode()

        fake_request = SimpleNamespace(
            env=self.env,
            httprequest=SimpleNamespace(data=raw, headers=all_headers),
        )
        with patch(
            "odoo.addons.spp_attendance.controllers.controllers.request",
            fake_request,
        ):
            yield fake_request

    @staticmethod
    def response_json(response):
        """Decode a werkzeug Response produced by the controller."""
        return json.loads(response.get_data(as_text=True) or "null")
