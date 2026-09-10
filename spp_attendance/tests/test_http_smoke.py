# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""End-to-end HTTP smoke tests (Layer B of the hybrid strategy).

HTTP-served requests run read-only against the test transaction (repo
precedent: spp_dci_client_compliance), so this layer covers only the
read paths, token minting, and auth rejection — the write endpoints are
fully covered by test_controller_logic.py.
"""

import json

from odoo.tests import HttpCase, tagged

from .common import AttendanceFixtureMixin


@tagged("post_install", "-at_install")
class TestAttendanceHttpSmoke(AttendanceFixtureMixin, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_oauth_keys()
        cls._setup_attendance_fixtures()
        cls.client_secret_plain = cls.credential.client_secret
        cls.bearer = cls._make_bearer_token()

    def _post_json(self, path, payload, headers=None):
        return self.url_open(
            path,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json", **(headers or {})},
        )

    def test_token_mint_roundtrip(self):
        response = self._post_json(
            "/auth/token",
            {"client_id": self.credential.client_id, "client_secret": self.client_secret_plain},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["token_type"], "Bearer")
        self.assertTrue(data["access_token"])

    def test_token_mint_rejects_wrong_secret(self):
        response = self._post_json(
            "/auth/token",
            {"client_id": self.credential.client_id, "client_secret": "wrong"},
        )
        self.assertEqual(response.status_code, 401)

    def test_protected_route_rejects_garbage_bearer(self):
        response = self.url_open(
            "/attendance/types",
            headers={"Authorization": "Bearer garbage"},
        )
        self.assertEqual(response.status_code, 401)

    def test_read_endpoints_roundtrip(self):
        headers = {"Authorization": f"Bearer {self.bearer}"}

        response = self.url_open("/attendance/types", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.attendance_type.name, [r["name"] for r in response.json()["records"]])

        response = self.url_open("/attendance/locations", headers=headers)
        self.assertEqual(response.status_code, 200)

        response = self.url_open("/subscribers", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["pagination"]["total_records"], 1)

        response = self.url_open("/subscriber/PID-0001", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["person_id"], "PID-0001")

        response = self.url_open("/attendance/PID-0001", headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["person_id"], "PID-0001")
