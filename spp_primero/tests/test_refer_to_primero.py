# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The Refer to Primero button posts the child's identifier to the OpenFn webhook."""

from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import WEBHOOK_API_KEY, WEBHOOK_URL, PrimeroTestCase

POST = "odoo.addons.spp_primero.models.res_partner.requests.post"
LOGGER = "odoo.addons.spp_primero.models.res_partner"


def _response(status_code=200, json_body=None, json_error=False):
    response = MagicMock()
    response.status_code = status_code
    if json_error:
        response.json.side_effect = ValueError("not json")
    else:
        response.json.return_value = json_body if json_body is not None else {}
    return response


@tagged("post_install", "-at_install")
class TestReferToPrimero(PrimeroTestCase):
    def setUp(self):
        super().setUp()
        self.child.write(
            {
                "protection_concern_ids": [(6, 0, self._concern_code("street_child").ids)],
                "protection_risk_level_id": self._risk_code("high").id,
            }
        )
        self.as_officer = self.child.with_user(self.officer)

    def _referral_messages(self):
        return self.child.message_ids.filtered(lambda m: "Primero" in (m.body or ""))

    # --- preconditions -------------------------------------------------

    def test_refer_requires_concern(self):
        self.child.protection_concern_ids = [(5, 0, 0)]
        with patch(POST) as post, self.assertRaises(UserError):
            self.as_officer.action_refer_to_primero()
        post.assert_not_called()

    def test_refer_requires_webhook_url(self):
        self._set_param("spp_primero.webhook_url", False)
        with patch(POST) as post, self.assertRaises(UserError):
            self.as_officer.action_refer_to_primero()
        post.assert_not_called()

    def test_refer_rejects_non_http_url(self):
        self._set_param("spp_primero.webhook_url", "ftp://lightning.example.test/i/abc")
        with patch(POST) as post, self.assertRaises(UserError):
            self.as_officer.action_refer_to_primero()
        post.assert_not_called()

    def test_refer_requires_identifier(self):
        self.child_reg_id.unlink()
        with patch(POST) as post, self.assertRaises(UserError):
            self.as_officer.action_refer_to_primero()
        post.assert_not_called()

    def test_refer_rejects_group(self):
        with patch(POST) as post, self.assertRaises(UserError):
            self.household.with_user(self.officer).action_refer_to_primero()
        post.assert_not_called()

    def test_refer_checks_write_access_before_posting(self):
        """A user who may not write the registrant must be refused before the webhook fires,
        otherwise OpenFn receives a referral that OpenSPP then rolls back."""
        officer_write_denied = self._make_user(
            "primero_officer_no_write",
            ["spp_registry.group_registry_officer"],
        )

        # Take write away through the access check, as a deployment setting such as
        # "Restrict Registry Edits to Admin Only" (spp_starter_sp_mis) would.
        def deny_write(records, operation):
            if operation == "write":
                raise AccessError("write withheld")

        with (
            patch.object(type(self.child), "check_access", autospec=True, side_effect=deny_write),
            patch(POST) as post,
            self.assertRaises(AccessError),
        ):
            self.child.with_user(officer_write_denied).action_refer_to_primero()
        post.assert_not_called()
        self.assertEqual(self.child.primero_referral_state, "none")

    def test_refer_viewer_denied(self):
        with patch(POST) as post, self.assertRaises(AccessError):
            self.child.with_user(self.viewer).action_refer_to_primero()
        post.assert_not_called()
        self.assertEqual(self.child.primero_referral_state, "none")

    # --- success --------------------------------------------------------

    def test_refer_success_payload(self):
        with patch(POST, return_value=_response(200, {"work_order_id": "wo-1", "run_id": "run-1"})) as post:
            action = self.as_officer.action_refer_to_primero()

        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], WEBHOOK_URL)
        self.assertEqual(kwargs["timeout"], 10)
        self.assertEqual(kwargs["headers"], {"x-api-key": WEBHOOK_API_KEY})
        payload = kwargs["json"]
        self.assertEqual(payload["event"], "protection_concern.referred")
        self.assertEqual(
            payload["identifier"],
            [{"system": self.child_reg_id.id_type_id.uri, "value": "BC-1234-5678901"}],
        )
        self.assertTrue(payload["referredAt"].endswith("Z"))
        self.assertEqual(set(payload), {"event", "identifier", "referredAt"})

        self.assertEqual(self.child.primero_referral_state, "referred")
        self.assertEqual(self.child.primero_run_ref, "run-1")
        self.assertTrue(self.child.primero_referred_at)
        self.assertFalse(self.child.primero_referral_error)
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "success")
        self.assertTrue(self._referral_messages())

    def test_refer_success_without_api_key(self):
        self._set_param("spp_primero.webhook_api_key", False)
        with patch(POST, return_value=_response(200, {"run_id": "run-2"})) as post:
            self.as_officer.action_refer_to_primero()
        self.assertEqual(post.call_args.kwargs["headers"], {})
        self.assertEqual(self.child.primero_referral_state, "referred")

    def test_refer_success_non_json_reply(self):
        with patch(POST, return_value=_response(202, json_error=True)):
            self.as_officer.action_refer_to_primero()
        self.assertEqual(self.child.primero_referral_state, "referred")
        self.assertFalse(self.child.primero_run_ref)

    def test_refer_as_manager(self):
        manager = self._make_user("primero_manager", ["spp_registry.group_registry_manager"])
        with patch(POST, return_value=_response(200, {"run_id": "run-3"})):
            self.child.with_user(manager).action_refer_to_primero()
        self.assertEqual(self.child.primero_referral_state, "referred")

    # --- failures -------------------------------------------------------

    def test_refer_http_error(self):
        with (
            patch(POST, return_value=_response(401, {"error": "unauthorized"})),
            self.assertLogs(LOGGER, level="WARNING") as logs,
        ):
            action = self.as_officer.action_refer_to_primero()

        self.assertEqual(self.child.primero_referral_state, "failed")
        self.assertEqual(self.child.primero_referral_error, "HTTP 401")
        self.assertFalse(self.child.primero_run_ref)
        self.assertEqual(action["params"]["type"], "danger")
        joined = "\n".join(logs.output)
        self.assertIn(str(self.child.id), joined)
        self.assertNotIn("Sofia", joined)
        self.assertNotIn("BC-1234", joined)
        self.assertNotIn("unauthorized", joined)

    def test_refer_connection_error(self):
        with (
            patch(POST, side_effect=requests.ConnectionError("boom")),
            self.assertLogs(LOGGER, level="WARNING"),
        ):
            self.as_officer.action_refer_to_primero()
        self.assertEqual(self.child.primero_referral_state, "failed")
        self.assertEqual(self.child.primero_referral_error, "ConnectionError")

    def test_refer_timeout(self):
        with patch(POST, side_effect=requests.Timeout("slow")), self.assertLogs(LOGGER, level="WARNING"):
            self.as_officer.action_refer_to_primero()
        self.assertEqual(self.child.primero_referral_state, "failed")
        self.assertEqual(self.child.primero_referral_error, "Timeout")

    def test_refer_again_after_failure(self):
        with patch(POST, return_value=_response(503)), self.assertLogs(LOGGER, level="WARNING"):
            self.as_officer.action_refer_to_primero()
        self.assertEqual(self.child.primero_referral_state, "failed")
        with patch(POST, return_value=_response(200, {"run_id": "run-4"})):
            self.as_officer.action_refer_to_primero()
        self.assertEqual(self.child.primero_referral_state, "referred")
        self.assertEqual(self.child.primero_run_ref, "run-4")
        self.assertFalse(self.child.primero_referral_error)
