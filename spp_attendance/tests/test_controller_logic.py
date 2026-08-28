# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

"""Controller logic tests (Layer A of the hybrid strategy).

Controller methods are called directly with a mocked ``request`` so the
env stays writable and every validation/error branch — including the
write endpoints — is exercised. End-to-end HTTP fidelity is covered by
the HttpCase smoke layer in test_http_smoke.py.
"""

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from .common import ControllerTestMixin


@tagged("post_install", "-at_install")
class TestControllerLogic(ControllerTestMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_oauth_keys()
        cls._setup_attendance_fixtures()
        cls._setup_controller()

    # ------------------------------------------------------------------
    # /auth/token
    # ------------------------------------------------------------------
    def test_token_mint_success(self):
        body = {
            "client_id": self.credential.client_id,
            "client_secret": self.credential.client_secret,
        }
        with self.mock_request(body=body):
            response = self.controller.auth_get_access_token()
        self.assertEqual(response.status_code, 200)
        data = self.response_json(response)
        self.assertEqual(data["token_type"], "Bearer")
        self.assertTrue(data["access_token"])

    def test_token_mint_wrong_secret(self):
        body = {"client_id": self.credential.client_id, "client_secret": "nope"}
        with self.mock_request(body=body):
            response = self.controller.auth_get_access_token()
        self.assertEqual(response.status_code, 401)

    def test_token_mint_missing_fields(self):
        with self.mock_request(body={"client_id": "only-id"}):
            response = self.controller.auth_get_access_token()
        self.assertEqual(response.status_code, 400)

    def test_token_mint_malformed_body(self):
        with self.mock_request(body="{not json"):
            response = self.controller.auth_get_access_token()
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------
    # auth gate
    # ------------------------------------------------------------------
    def test_protected_routes_reject_bad_bearer(self):
        cases = [
            lambda: self.controller.create_attendance_list(),
            lambda: self.controller.update_attendance_list(),
            lambda: self.controller.delete_attendance_list(ids="1"),
            lambda: self.controller.attendance_list_person("PID-0001"),
            lambda: self.controller.attendance_list(),
            lambda: self.controller.get_attendance_types(),
            lambda: self.controller.get_attendance_locations(),
            lambda: self.controller.get_subscriber_list_information(),
            lambda: self.controller.get_subscriber_information("PID-0001"),
        ]
        for call in cases:
            with self.mock_request(body={}, token="garbage-token"):
                response = call()
            self.assertEqual(response.status_code, 401)

    # ------------------------------------------------------------------
    # POST /attendances
    # ------------------------------------------------------------------
    def _attendance_body(self, **overrides):
        body = {
            "submitted_by": "tester",
            "submitted_datetime": "2026-08-18 08:00:00",
            "records": [
                {
                    "person_id": "PID-0001",
                    "time_card": [
                        {
                            "date_time": "2026-08-01 08:00:00",
                            "attendance_type": str(self.attendance_type.id),
                            "attendance_location": str(self.attendance_location.id),
                        }
                    ],
                }
            ],
        }
        body.update(overrides)
        return body

    def test_create_attendance_success(self):
        with self.mock_request(body=self._attendance_body(), token="__valid__"):
            response = self.controller.create_attendance_list()
        self.assertEqual(response.status_code, 200)
        data = self.response_json(response)
        self.assertEqual(data["person_ids"], ["PID-0001"])
        record = self.env["spp.attendance.list"].search([("subscriber_id", "=", self.subscriber.id)])
        self.assertEqual(len(record), 1)
        self.assertEqual(str(record.attendance_date), "2026-08-01")
        self.assertEqual(record.attendance_category, "present")

    def test_create_attendance_missing_top_level_fields(self):
        with self.mock_request(body={"records": []}, token="__valid__"):
            response = self.controller.create_attendance_list()
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required fields", self.response_json(response)["error"]["message"])

    def test_create_attendance_unknown_person(self):
        body = self._attendance_body()
        body["records"][0]["person_id"] = "PID-UNKNOWN"
        with self.mock_request(body=body, token="__valid__"):
            response = self.controller.create_attendance_list()
        self.assertEqual(response.status_code, 400)
        self.assertIn("person_id does not exist", self.response_json(response)["error"]["message"])

    def test_create_attendance_invalid_category(self):
        body = self._attendance_body()
        body["records"][0]["time_card"][0]["attendance_category"] = "late"
        with self.mock_request(body=body, token="__valid__"):
            response = self.controller.create_attendance_list()
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid category", self.response_json(response)["error"]["message"])

    def test_create_attendance_invalid_type(self):
        body = self._attendance_body()
        body["records"][0]["time_card"][0]["attendance_type"] = "999999"
        with self.mock_request(body=body, token="__valid__"):
            response = self.controller.create_attendance_list()
        self.assertEqual(response.status_code, 400)

    def test_create_attendance_duplicate_and_ignore_unique(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("spp_attendance.date_unique", "True")
        icp.set_param("spp_attendance.time_unique", "True")

        with self.mock_request(body=self._attendance_body(), token="__valid__"):
            self.controller.create_attendance_list()

        # same payload again → uniqueness violation
        with self.mock_request(body=self._attendance_body(), token="__valid__"):
            response = self.controller.create_attendance_list()
        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", self.response_json(response)["error"]["message"])

        # ignore_unique skips duplicates instead of failing
        with self.mock_request(body=self._attendance_body(), token="__valid__"):
            response = self.controller.create_attendance_list(ignore_unique="true")
        self.assertEqual(response.status_code, 200)
        count = self.env["spp.attendance.list"].search_count([("subscriber_id", "=", self.subscriber.id)])
        self.assertEqual(count, 1, "duplicate must be skipped, not created")

    # ------------------------------------------------------------------
    # PUT /attendances
    # ------------------------------------------------------------------
    def _existing_attendance(self):
        return self.env["spp.attendance.list"].create(
            {
                "subscriber_id": self.subscriber.id,
                "attendance_date": "2026-08-02",
                "attendance_time": "09:00:00",
                "submitted_by": "seed",
            }
        )

    def test_update_attendance_success(self):
        record = self._existing_attendance()
        body = {
            "submitted_by": "editor",
            "submitted_datetime": "2026-08-18 09:00:00",
            "records": [
                {
                    "id": record.id,
                    "time_card": {
                        "date_time": "2026-08-03 10:30:00",
                        "attendance_category": "absent",
                        "attendance_description": "updated",
                    },
                }
            ],
        }
        with self.mock_request(body=body, token="__valid__"):
            response = self.controller.update_attendance_list()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(record.attendance_date), "2026-08-03")
        self.assertEqual(record.attendance_time, "10:30:00")
        self.assertEqual(record.attendance_category, "absent")
        self.assertEqual(record.submitted_by, "editor")

    def test_update_attendance_bad_id(self):
        body = {
            "submitted_by": "editor",
            "submitted_datetime": "2026-08-18 09:00:00",
            "records": [{"id": "abc", "time_card": {}}],
        }
        with self.mock_request(body=body, token="__valid__"):
            response = self.controller.update_attendance_list()
        self.assertEqual(response.status_code, 400)

        body["records"] = [{"id": 999999, "time_card": {}}]
        with self.mock_request(body=body, token="__valid__"):
            response = self.controller.update_attendance_list()
        self.assertEqual(response.status_code, 400)

    def test_update_attendance_time_card_must_be_object(self):
        record = self._existing_attendance()
        body = {
            "submitted_by": "editor",
            "submitted_datetime": "2026-08-18 09:00:00",
            "records": [{"id": record.id, "time_card": ["not-a-dict"]}],
        }
        with self.mock_request(body=body, token="__valid__"):
            response = self.controller.update_attendance_list()
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------
    # DELETE /attendances
    # ------------------------------------------------------------------
    def test_delete_attendance(self):
        record = self._existing_attendance()
        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.delete_attendance_list(ids=str(record.id))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(record.exists())

    def test_delete_attendance_bad_ids(self):
        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.delete_attendance_list(ids="1,abc")
        self.assertEqual(response.status_code, 400)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.delete_attendance_list(ids="999999")
        self.assertEqual(response.status_code, 400)

    # ------------------------------------------------------------------
    # GET /attendance/<person_identifier> and /attendances
    # ------------------------------------------------------------------
    def test_person_attendance_list_and_pagination(self):
        self._existing_attendance()
        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.attendance_list_person("PID-0001", page=1, limit=10)
        self.assertEqual(response.status_code, 200)
        data = self.response_json(response)
        self.assertEqual(data["pagination"]["total_records"], 1)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.attendance_list_person("PID-NOPE")
        self.assertEqual(response.status_code, 400)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.attendance_list_person("PID-0001", page="x", limit=10)
        self.assertEqual(response.status_code, 400)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.attendance_list_person("PID-0001", page=0, limit=10)
        self.assertEqual(response.status_code, 400)

    def test_person_attendance_date_filters(self):
        self._existing_attendance()
        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.attendance_list_person("PID-0001", from_date="2026-08-01", to_date="2026-08-31")
        self.assertEqual(response.status_code, 200)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.attendance_list_person("PID-0001", from_date="31-08-2026", to_date="x")
        self.assertEqual(response.status_code, 400)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.attendance_list_person("PID-0001", from_date="2026-08-31", to_date="2026-08-01")
        self.assertEqual(response.status_code, 400)

    def test_attendance_list_cursor_pagination(self):
        other = self.env["spp.attendance.subscriber"].create(
            {"person_identifier": "PID-0002", "family_name": "Reyes", "given_name": "Maria"}
        )
        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.attendance_list(limit=1, last_id=0)
        self.assertEqual(response.status_code, 200)
        data = self.response_json(response)
        self.assertEqual(len(data["records"]), 1)
        self.assertEqual(data["pagination"]["total_records"], 2)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.attendance_list(last_id="abc")
        self.assertEqual(response.status_code, 400)

        # filter by person_ids in body
        with self.mock_request(body={"person_ids": ["PID-0002"]}, token="__valid__"):
            response = self.controller.attendance_list()
        data = self.response_json(response)
        self.assertEqual(data["pagination"]["total_records"], 1)
        self.assertEqual(data["records"][0]["person_id"], other.person_identifier)

    # ------------------------------------------------------------------
    # GET types / locations / subscribers
    # ------------------------------------------------------------------
    def test_types_and_locations(self):
        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.get_attendance_types()
        data = self.response_json(response)
        self.assertIn(self.attendance_type.name, [r["name"] for r in data["records"]])

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.get_attendance_locations()
        data = self.response_json(response)
        self.assertIn(self.attendance_location.name, [r["name"] for r in data["records"]])

    def test_subscriber_endpoints(self):
        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.get_subscriber_list_information()
        data = self.response_json(response)
        self.assertGreaterEqual(data["pagination"]["total_records"], 1)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.get_subscriber_information("PID-0001")
        self.assertEqual(response.status_code, 200)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.get_subscriber_information("PID-NOPE")
        self.assertEqual(response.status_code, 400)

        with self.mock_request(body={}, token="__valid__"):
            response = self.controller.get_subscriber_list_information(last_id="abc")
        self.assertEqual(response.status_code, 400)
