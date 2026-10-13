# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""The Refer to Primero button posts the child's identifier to the OpenFn webhook."""

import uuid
from unittest.mock import MagicMock, patch

import requests

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import WEBHOOK_API_KEY, WEBHOOK_URL, PrimeroTestCase

POST = "odoo.addons.spp_primero.models.res_partner.requests.post"
LOGGER = "odoo.addons.spp_primero.models.res_partner"


def _response(status_code=200, json_body=None, json_error=False, headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
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
                "protection_concern_ids": [Command.set(self._concern_code("street_child").ids)],
                "protection_risk_level_id": self._risk_code("high").id,
            }
        )
        self.as_officer = self.child.with_user(self.officer)

    def _referral_messages(self):
        return self.child.message_ids.filtered(lambda m: "Primero" in (m.body or ""))

    # --- preconditions -------------------------------------------------

    def test_refer_requires_concern(self):
        self.child.protection_concern_ids = [Command.clear()]
        with patch(POST) as post, self.assertRaises(UserError):
            self.as_officer.action_refer_to_primero()
        post.assert_not_called()

    def test_refer_requires_webhook_url(self):
        self._set_param("spp_primero.webhook_url", False)
        with patch(POST) as post, self.assertRaises(UserError):
            self.as_officer.action_refer_to_primero()
        post.assert_not_called()

    def test_refer_rejects_non_http_url(self):
        for url in ("ftp://lightning.example.test/i/abc", "http://", "lightning.example.test/i/abc"):
            with self.subTest(url=url):
                self._set_param("spp_primero.webhook_url", url)
                with patch(POST) as post, self.assertRaises(UserError):
                    self.as_officer.action_refer_to_primero()
                post.assert_not_called()

    def test_refer_rejects_plain_http_to_remote_host(self):
        """The key and the child's identifier travel in the request: https, except to this machine."""
        self._set_param("spp_primero.webhook_url", "http://lightning.example.test/i/abc")
        with patch(POST) as post, self.assertRaises(UserError):
            self.as_officer.action_refer_to_primero()
        post.assert_not_called()

    def test_refer_allows_plain_http_to_local_host(self):
        for url in ("http://localhost:4000/i/abc", "http://127.0.0.1:4000/i/abc", WEBHOOK_URL):
            with self.subTest(url=url):
                self._set_param("spp_primero.webhook_url", url)
                with patch(POST, return_value=_response(200, {"run_id": "run-local"})) as post:
                    self.as_officer.action_refer_to_primero()
                self.assertEqual(post.call_args.args[0], url)

    def test_refer_allows_plain_http_with_insecure_override(self):
        self._set_param("spp_primero.webhook_url", "http://lightning.example.test/i/abc")
        self._set_param("spp_primero.allow_insecure_webhook", "True")
        with patch(POST, return_value=_response(200, {"run_id": "run-insecure"})) as post:
            self.as_officer.action_refer_to_primero()
        post.assert_called_once()

    def test_refer_allows_https_anywhere(self):
        self._set_param("spp_primero.webhook_url", "https://lightning.example.test/i/abc")
        with patch(POST, return_value=_response(200, {"run_id": "run-https"})) as post:
            self.as_officer.action_refer_to_primero()
        post.assert_called_once()

    def test_refer_requires_identifier(self):
        self.child_reg_id.unlink()
        with patch(POST) as post, self.assertRaises(UserError):
            self.as_officer.action_refer_to_primero()
        post.assert_not_called()

    def test_refer_rejects_group(self):
        with patch(POST) as post, self.assertRaises(UserError):
            self.household.with_user(self.officer).action_refer_to_primero()
        post.assert_not_called()

    def test_refer_rejects_disabled_registrant(self):
        self.child.disabled = self.child.create_date
        with patch(POST) as post, self.assertRaises(UserError):
            self.as_officer.action_refer_to_primero()
        post.assert_not_called()

    def test_refer_viewer_denied(self):
        with patch(POST) as post, self.assertRaises(AccessError):
            self.child.with_user(self.viewer).action_refer_to_primero()
        post.assert_not_called()
        self.assertEqual(self.child.primero_referral_state, "not_referred")

    def test_refer_write_group_alone_denied(self):
        """Partner write rights are not enough: the officer group is the gate."""
        writer = self._make_user("primero_writer", ["spp_registry.group_registry_write"])
        with patch(POST) as post, self.assertRaises(AccessError):
            self.child.with_user(writer).action_refer_to_primero()
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
                raise AccessError(records.env._("write withheld"))

        with (
            patch.object(type(self.child), "check_access", autospec=True, side_effect=deny_write),
            patch(POST) as post,
            self.assertRaises(AccessError),
        ):
            self.child.with_user(officer_write_denied).action_refer_to_primero()
        post.assert_not_called()
        self.assertEqual(self.child.primero_referral_state, "not_referred")

    # --- success --------------------------------------------------------

    def test_refer_success_payload(self):
        with patch(POST, return_value=_response(200, {"work_order_id": "wo-1", "run_id": "run-1"})) as post:
            action = self.as_officer.action_refer_to_primero()

        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], WEBHOOK_URL)
        self.assertEqual(kwargs["timeout"], (3.05, 10))
        self.assertIs(kwargs["allow_redirects"], False)
        self.assertEqual(kwargs["headers"], {"x-api-key": WEBHOOK_API_KEY})
        payload = kwargs["json"]
        self.assertEqual(payload["event"], "protection_concern.referred")
        self.assertEqual(
            payload["identifier"],
            [{"system": self.child_reg_id.id_type_id.uri, "value": "BC-1234-5678901"}],
        )
        self.assertTrue(payload["referredAt"].endswith("Z"))
        uuid.UUID(payload["referralId"])  # a well-formed, per-call id for deduplication
        self.assertEqual(set(payload), {"event", "referralId", "identifier", "referredAt"})
        self.assertNotIn("Sofia", str(payload))

        self.assertEqual(self.child.primero_referral_state, "referred")
        self.assertEqual(self.child.primero_run_ref, "run-1")
        self.assertTrue(self.child.primero_referred_at)
        self.assertFalse(self.child.primero_referral_error)
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "success")
        self.assertIs(action["params"]["sticky"], False)
        self.assertTrue(self._referral_messages())

    def test_refer_each_call_has_a_new_referral_id(self):
        ids = set()
        for _ in range(2):
            with patch(POST, return_value=_response(200, {"run_id": "run-x"})) as post:
                self.as_officer.action_refer_to_primero()
            ids.add(post.call_args.kwargs["json"]["referralId"])
        self.assertEqual(len(ids), 2)

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

    def test_refer_success_takes_run_id_from_lightning_header(self):
        """Lightning's async reply: run id in x-meta-run-id, only the work order id in the body."""
        with patch(
            POST,
            return_value=_response(200, {"work_order_id": "wo-9"}, headers={"x-meta-run-id": "run-9"}),
        ):
            self.as_officer.action_refer_to_primero()
        self.assertEqual(self.child.primero_run_ref, "run-9")

    def test_refer_success_falls_back_to_work_order_id(self):
        with patch(POST, return_value=_response(200, {"work_order_id": "wo-10"})):
            self.as_officer.action_refer_to_primero()
        self.assertEqual(self.child.primero_run_ref, "wo-10")

    def test_refer_success_ignores_odd_run_ids(self):
        for body in ([], {"run_id": {"nested": 1}}, {"run_id": 42}, {"run_id": ""}):
            with self.subTest(body=body):
                with patch(POST, return_value=_response(200, body)):
                    self.as_officer.action_refer_to_primero()
                self.assertEqual(self.child.primero_referral_state, "referred")
                self.assertFalse(self.child.primero_run_ref)

    def test_refer_success_truncates_long_run_id(self):
        with patch(POST, return_value=_response(200, {"run_id": "r" * 500})):
            self.as_officer.action_refer_to_primero()
        self.assertEqual(len(self.child.primero_run_ref), 128)

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
        self.assertIs(action["params"]["sticky"], True)
        self.assertIn("API key", action["params"]["message"])
        joined = "\n".join(logs.output)
        self.assertIn(str(self.child.id), joined)
        for secret in ("Sofia", "BC-1234", "unauthorized"):
            self.assertNotIn(secret, joined)
        message = self._referral_messages()[:1]
        self.assertTrue(message)
        for secret in ("Sofia", "BC-1234", "unauthorized"):
            self.assertNotIn(secret, message.body)

    def test_refer_redirect_is_a_failure(self):
        """A 307/308 would replay the body and the key elsewhere; it is refused, not followed."""
        with patch(POST, return_value=_response(307)), self.assertLogs(LOGGER, level="WARNING"):
            action = self.as_officer.action_refer_to_primero()
        self.assertEqual(self.child.primero_referral_state, "failed")
        self.assertEqual(self.child.primero_referral_error, "HTTP 307")
        self.assertIn("redirect", action["params"]["message"])

    def test_refer_connection_error(self):
        with (
            patch(POST, side_effect=requests.ConnectionError("boom")),
            self.assertLogs(LOGGER, level="WARNING"),
        ):
            action = self.as_officer.action_refer_to_primero()
        self.assertEqual(self.child.primero_referral_state, "failed")
        self.assertEqual(self.child.primero_referral_error, "ConnectionError")
        self.assertIn("unreachable", action["params"]["message"])

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
