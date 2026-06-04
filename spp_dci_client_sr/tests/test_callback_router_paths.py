# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Additional coverage for the SR callback router (routers/callback.py).

Targets branches not reached by test_callback.py:
- _find_partner_by_identifier: namespace-URI fallback and not-found paths
- _process_sr_search_result: empty id/value skip, exception swallowing
- receive_sr_search_response / receive_sr_subscribe_response: outer exception paths
- notification processors: partner-not-found early exit
"""

import asyncio
from unittest.mock import MagicMock, patch

from odoo.tests import tagged

from odoo.addons.spp_dci.schemas import DCIEnvelope

from fastapi import HTTPException

from .common import SRClientCommon

CALLBACK = "odoo.addons.spp_dci_client_sr.routers.callback"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _request():
    req = MagicMock()
    req.client.host = "203.0.113.10"
    return req


@tagged("post_install", "-at_install")
class TestFindPartnerByIdentifier(SRClientCommon):
    """Unit tests for _find_partner_by_identifier covering all three branches."""

    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_client_sr.routers import callback

        self.callback = callback

        self.id_code = self.env.ref("spp_vocabulary.code_id_type_national_id")
        self.partner = self.env["res.partner"].create(
            {"name": "NS URI Person", "is_registrant": True, "is_group": False}
        )

    def test_find_by_namespace_uri_fallback(self):
        """When exact code search misses and id_type is not a urn: prefix,
        the namespace_uri ilike fallback search finds the partner."""
        # Create a vocabulary whose namespace_uri does NOT start with "urn:" so
        # the fallback branch ("if not id_type.startswith('urn:')") is taken.
        vocab = self.env["spp.vocabulary"].create(
            {
                "name": "Test NS Fallback Vocab",
                "namespace_uri": "https://test.example.org/id-types",
                "domain": "core",
            }
        )
        code = self.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": vocab.id,
                "code": "test_ns_id",
                "display": "Test NS ID",
            }
        )
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.partner.id,
                "id_type_id": code.id,
                "value": "NS-URI-001",
            }
        )
        # Pass the vocabulary's non-urn namespace_uri as the id_type.
        # First search (by .code) finds nothing; fallback (by .namespace_uri ilike) succeeds.
        partner = self.callback._find_partner_by_identifier(self.env, "https://test.example.org/id-types", "NS-URI-001")
        self.assertEqual(partner, self.partner)

    def test_find_not_found_returns_falsy(self):
        """Unknown identifier returns a falsy result."""
        result = self.callback._find_partner_by_identifier(self.env, self.id_code.code, "NO-SUCH-VALUE")
        self.assertFalse(result)

    def test_find_urn_prefixed_type_skips_fallback(self):
        """When id_type starts with 'urn:' the namespace fallback is never attempted."""
        # Register the partner under the short code so the first search would
        # succeed if it tried the correct key — but the urn:-prefixed string
        # will not match the code, and the fallback is skipped for urn: values.
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.partner.id,
                "id_type_id": self.id_code.id,
                "value": "URN-VAL-001",
            }
        )
        result = self.callback._find_partner_by_identifier(self.env, "urn:example:type", "URN-VAL-001")
        # urn: prefix → only the exact-code branch runs → no match → None.
        self.assertFalse(result)


@tagged("post_install", "-at_install")
class TestProcessSRSearchResult(SRClientCommon):
    """Cover _process_sr_search_result internal branches."""

    def setUp(self):
        super().setUp()
        self.create_test_sr_sender()
        from odoo.addons.spp_dci_client_sr.routers import callback

        self.callback = callback
        self.id_code = self.env.ref("spp_vocabulary.code_id_type_national_id")
        self.partner = self.env["res.partner"].create(
            {"name": "Search Result Person", "is_registrant": True, "is_group": False}
        )
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.partner.id,
                "id_type_id": self.id_code.id,
                "value": "SRSR-NID-1",
            }
        )

    def test_identifier_with_empty_type_is_skipped(self):
        """An identifier with an empty identifier_type must be skipped (no crash)."""
        result = {
            "status": "succ",
            "data": {
                "reg_records": [
                    {
                        "id": "EXT-SKIP",
                        "name": "Skip Person",
                        "identifier": [{"identifier_type": "", "identifier_value": "SRSR-NID-1"}],
                    }
                ]
            },
        }
        # Should not raise and should not create any SR record.
        self.callback._process_sr_search_result(self.env, result, "test-registry")
        rec = self.env["spp.dci.sr.record"].search([("external_id", "=", "EXT-SKIP")])
        self.assertFalse(rec)

    def test_identifier_with_empty_value_is_skipped(self):
        """An identifier with an empty identifier_value must be skipped."""
        result = {
            "status": "succ",
            "data": {
                "reg_records": [
                    {
                        "id": "EXT-SKIP2",
                        "name": "Skip Person 2",
                        "identifier": [{"identifier_type": self.id_code.code, "identifier_value": ""}],
                    }
                ]
            },
        }
        self.callback._process_sr_search_result(self.env, result, "test-registry")
        rec = self.env["spp.dci.sr.record"].search([("external_id", "=", "EXT-SKIP2")])
        self.assertFalse(rec)

    def test_no_partner_found_logs_debug_and_continues(self):
        """When no partner matches the identifier, processing continues without error."""
        result = {
            "status": "succ",
            "data": {
                "reg_records": [
                    {
                        "id": "EXT-NOMATCH",
                        "identifier": [{"identifier_type": self.id_code.code, "identifier_value": "DOES-NOT-EXIST"}],
                    }
                ]
            },
        }
        # No exception expected; no SR record should be created.
        self.callback._process_sr_search_result(self.env, result, "test-registry")
        rec = self.env["spp.dci.sr.record"].search([("external_id", "=", "EXT-NOMATCH")])
        self.assertFalse(rec)

    def test_exception_inside_is_caught_and_logged(self):
        """Internal exceptions are swallowed with an error log, not propagated."""
        result = {
            "status": "succ",
            "data": {
                "reg_records": [
                    {
                        "id": "EXT-ERR",
                        "identifier": [{"identifier_type": self.id_code.code, "identifier_value": "SRSR-NID-1"}],
                    }
                ]
            },
        }
        with patch(f"{CALLBACK}._update_sr_record", side_effect=RuntimeError("db error")):
            # Must not propagate.
            self.callback._process_sr_search_result(self.env, result, "test-registry")


@tagged("post_install", "-at_install")
class TestCallbackRouterExceptionPaths(SRClientCommon):
    """Cover the outer try/except branches in the three route handlers."""

    def setUp(self):
        super().setUp()
        self.create_test_sr_sender()
        from odoo.addons.spp_dci_client_sr.routers import callback

        self.callback = callback
        self.id_code = self.env.ref("spp_vocabulary.code_id_type_national_id")
        self.partner = self.env["res.partner"].create(
            {"name": "Exception Path Person", "is_registrant": True, "is_group": False}
        )

    def _envelope(self, message):
        data = self.create_signed_envelope(action="notify", message=message)
        return DCIEnvelope(**data)

    # --- on-search outer exception ---

    def test_on_search_outer_exception_returns_500(self):
        """An unexpected error in receive_sr_search_response propagates as HTTP 500."""
        # A mock envelope whose .message.get() raises triggers the outer except.
        mock_message = MagicMock()
        mock_message.get = MagicMock(side_effect=RuntimeError("message parse error"))
        mock_envelope = MagicMock()
        mock_envelope.message = mock_message

        with self.assertRaises(HTTPException) as ctx:
            _run(
                self.callback.receive_sr_search_response(
                    _request(), mock_envelope, self.env, verified_sender_id=self.test_sender_id
                )
            )
        self.assertEqual(ctx.exception.status_code, 500)

    # --- on-subscribe outer exception ---

    def test_on_subscribe_outer_exception_returns_500(self):
        """An unexpected error in receive_sr_subscribe_response propagates as HTTP 500."""
        # Use a mock envelope whose .message.get() raises so the outer handler runs.
        mock_message = MagicMock()
        mock_message.get = MagicMock(side_effect=RuntimeError("sub boom"))
        mock_envelope = MagicMock()
        mock_envelope.message = mock_message

        with self.assertRaises(HTTPException) as ctx:
            _run(
                self.callback.receive_sr_subscribe_response(
                    _request(), mock_envelope, self.env, verified_sender_id=self.test_sender_id
                )
            )
        self.assertEqual(ctx.exception.status_code, 500)

    # --- on-notify: partner not found path ---

    def _notify(self, event_type, notify_data=None):
        message = {
            "event_type": event_type,
            "correlation_id": "notify-nopartner",
            "notify_data": notify_data or {},
        }
        envelope = self._envelope(message)
        return _run(
            self.callback.receive_sr_notification(
                _request(), envelope, self.env, verified_sender_id=self.test_sender_id
            )
        )

    def test_enrollment_notification_no_partner_acks(self):
        """ENROLLMENT notification where no partner matches the identifier still acks."""
        notify_data = {
            "identifier": [{"identifier_type": self.id_code.code, "identifier_value": "NONE-EXISTS"}],
            "id": "EXT-NPARTNER",
            "name": "Ghost Person",
        }
        result = self._notify("ENROLLMENT", notify_data)
        self.assertEqual(result["message"]["ack_status"], "rcvd")
        # No SR record should have been created.
        rec = self.env["spp.dci.sr.record"].search([("external_id", "=", "EXT-NPARTNER")])
        self.assertFalse(rec)

    def test_disenrollment_notification_no_partner_acks(self):
        """DISENROLLMENT where no partner matches still acks."""
        notify_data = {
            "identifier": [{"identifier_type": self.id_code.code, "identifier_value": "NONE-EXISTS-2"}],
        }
        result = self._notify("DISENROLLMENT", notify_data)
        self.assertEqual(result["message"]["ack_status"], "rcvd")

    def test_update_notification_no_partner_acks(self):
        """UPDATE notification where no partner matches still acks."""
        notify_data = {
            "identifier": [{"identifier_type": self.id_code.code, "identifier_value": "NONE-EXISTS-3"}],
        }
        result = self._notify("UPDATE", notify_data)
        self.assertEqual(result["message"]["ack_status"], "rcvd")
