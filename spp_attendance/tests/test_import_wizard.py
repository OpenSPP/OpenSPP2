# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

DCI_STYLE_RESPONSE = {
    "message": {
        "search_response": [
            {
                "data": {
                    "reg_records": [
                        {
                            "identifier": [{"identifier": "PID-W1"}],
                            "family_name": "Garcia",
                            "given_name": "Luis",
                            "email": "luis@example.org",
                            "phone": "0917000001",
                            "gender": "male",
                        },
                        {
                            "identifier": [{"identifier": "PID-W2"}],
                            "family_name": "Lim",
                            "given_name": "Rosa",
                            "email": "",
                            "phone": "",
                            "gender": "",
                        },
                    ]
                }
            }
        ]
    },
    "pagination": {"page": 1, "limit": 30},
}


@tagged("post_install", "-at_install")
class TestImportWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param("spp_attendance.server_url", "http://registry.test")
        icp.set_param("spp_attendance.attendance_auth_endpoint", "/oauth2/client/token")
        icp.set_param("spp_attendance.attendance_import_endpoint", "/registry/sync/search")
        icp.set_param("spp_attendance.access_token_mapping", "access_token")
        icp.set_param("spp_attendance.personal_information_mapping", "message.search_response.0.data.reg_records")
        icp.set_param("spp_attendance.person_identifier_mapping", "identifier.0.identifier")
        icp.set_param("spp_attendance.family_name_mapping", "family_name")
        icp.set_param("spp_attendance.given_name_mapping", "given_name")
        icp.set_param("spp_attendance.email_mapping", "email")
        icp.set_param("spp_attendance.phone_mapping", "phone")
        icp.set_param("spp_attendance.gender_mapping", "gender")

    def _wizard(self):
        return self.env["spp.import.attendance.wizard"].create({})

    def _mock_response(self, ok=True, payload=None, text=""):
        response = MagicMock()
        response.ok = ok
        response.reason = "Testing"
        response.text = text
        response.json.return_value = payload
        return response

    def test_import_creates_and_updates_subscribers(self):
        wizard = self._wizard()
        auth = self._mock_response(payload={"access_token": "tok"})
        search = self._mock_response(payload=DCI_STYLE_RESPONSE)
        with patch(
            "odoo.addons.spp_attendance.wizard.import_attendance.requests.post",
            side_effect=[auth, search],
        ):
            wizard.action_import_attendance()

        Subscriber = self.env["spp.attendance.subscriber"]
        first = Subscriber.search([("person_identifier", "=", "PID-W1")])
        self.assertEqual(first.family_name, "Garcia")
        self.assertEqual(first.email, "luis@example.org")
        self.assertEqual(first.gender_char, "Male", "gender should be title-cased from source data")

        second = Subscriber.search([("person_identifier", "=", "PID-W2")])
        self.assertTrue(second)
        self.assertFalse(second.gender_char, "absent gender must stay empty, never fabricated")

        # Re-import updates in place instead of duplicating
        modified = json.loads(json.dumps(DCI_STYLE_RESPONSE))
        modified["message"]["search_response"][0]["data"]["reg_records"][0]["family_name"] = "Garcia-Cruz"
        auth2 = self._mock_response(payload={"access_token": "tok"})
        search2 = self._mock_response(payload=modified)
        with patch(
            "odoo.addons.spp_attendance.wizard.import_attendance.requests.post",
            side_effect=[auth2, search2],
        ):
            wizard.action_import_attendance()
        self.assertEqual(Subscriber.search_count([("person_identifier", "=", "PID-W1")]), 1)
        self.assertEqual(first.family_name, "Garcia-Cruz")

    def test_auth_failure_raises(self):
        wizard = self._wizard()
        with patch(
            "odoo.addons.spp_attendance.wizard.import_attendance.requests.post",
            return_value=self._mock_response(ok=False),
        ):
            with self.assertRaises(UserError):
                wizard.action_import_attendance()

    def test_import_failure_raises(self):
        wizard = self._wizard()
        auth = self._mock_response(payload={"access_token": "tok"})
        bad_search = self._mock_response(ok=False)
        with patch(
            "odoo.addons.spp_attendance.wizard.import_attendance.requests.post",
            side_effect=[auth, bad_search],
        ):
            with self.assertRaises(UserError):
                wizard.action_import_attendance()

    def test_bad_header_json_raises(self):
        wizard = self._wizard()
        wizard.auth_header = "{not json"
        with self.assertRaises(UserError):
            wizard.action_import_attendance()

    def test_mapping_must_point_to_list(self):
        wizard = self._wizard()
        self.env["ir.config_parameter"].sudo().set_param("spp_attendance.personal_information_mapping", "message")
        with self.assertRaises(UserError):
            wizard._import_attendance(DCI_STYLE_RESPONSE)

    def test_element_mapper_errors(self):
        wizard = self._wizard()
        self.assertIsNone(wizard.element_mapper({"a": 1}, []))
        with self.assertRaises(UserError):
            wizard.element_mapper({"a": 1}, ["missing"])
        with self.assertRaises(UserError):
            wizard.element_mapper({"a": {"b": 1}}, ["a", "0"])
        with self.assertRaises(UserError):
            wizard.element_mapper({"a": []}, ["a", "5"])

    def test_missing_config_raises_friendly_error(self):
        """A missing mapping parameter must produce the intended UserError,
        not crash with a KeyError while composing the message.

        check_required_fields looks the parameter name up in
        ir.config_parameter._fields, where it never exists.
        """
        wizard = self._wizard()
        self.env["ir.config_parameter"].sudo().set_param("spp_attendance.family_name_mapping", False)
        with self.assertRaises(UserError):
            wizard._import_attendance(DCI_STYLE_RESPONSE)

    def test_basic_auth_token_not_double_prefixed(self):
        """A token already carrying a scheme must be passed through as-is.

        The prefix guard's operator precedence re-prefixes 'Basic ...'
        tokens, producing 'Basic Basic xyz'.
        """
        wizard = self._wizard()
        wizard.auth_type = "Basic"
        auth = self._mock_response(payload={"access_token": "Basic xyz"})
        search = self._mock_response(payload=DCI_STYLE_RESPONSE)
        with patch(
            "odoo.addons.spp_attendance.wizard.import_attendance.requests.post",
            side_effect=[auth, search],
        ) as mocked_post:
            wizard.action_import_attendance()

        import_headers = mocked_post.call_args_list[1].kwargs["headers"]
        self.assertEqual(import_headers["Authorization"], "Basic xyz")
