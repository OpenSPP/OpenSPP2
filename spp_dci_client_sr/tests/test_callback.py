# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the SR callback router (on-search / on-subscribe / on-notify).

The handler bodies and their helper functions (_process_sr_search_result,
_find_partner_by_identifier, _update_sr_record, and the three notification
processors) are exercised by invoking the async handlers directly with a
signed envelope and a verified sender_id, bypassing the signature dependency.
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
    req.client.host = "203.0.113.9"
    return req


@tagged("post_install", "-at_install")
class TestSRCallback(SRClientCommon):
    def setUp(self):
        super().setUp()
        self.test_sender = self.create_test_sr_sender()
        from odoo.addons.spp_dci_client_sr.routers import callback

        self.callback = callback

        # Local partner reachable by national_id identifier.
        self.id_code = self.env.ref("spp_vocabulary.code_id_type_national_id")
        self.partner = self.env["res.partner"].create({"name": "SR Person", "is_registrant": True, "is_group": False})
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.partner.id,
                "id_type_id": self.id_code.id,
                "value": "SR-NID-1",
            }
        )

    def _envelope(self, message):
        data = self.create_signed_envelope(action="notify", message=message)
        return DCIEnvelope(**data)

    def _reg_record(self, name="SR Person"):
        return {
            "id": "EXT-SR-1",
            "name": name,
            "birth_date": "1990-05-15",
            "gender": "male",
            "identifier": [{"identifier_type": self.id_code.code, "identifier_value": "SR-NID-1"}],
        }

    # --- on-search -----------------------------------------------------------

    def test_on_search_response_syncs_record(self):
        message = {
            "transaction_id": "txn-1",
            "correlation_id": "corr-1",
            "search_response": [{"status": "succ", "data": {"reg_records": [self._reg_record()]}}],
        }
        result = _run(
            self.callback.receive_sr_search_response(
                _request(), self._envelope(message), self.env, verified_sender_id=self.test_sender_id
            )
        )
        self.assertEqual(result["message"]["ack_status"], "rcvd")
        self.assertEqual(result["message"]["correlation_id"], "corr-1")
        rec = self.env["spp.dci.sr.record"].search([("partner_id", "=", self.partner.id)], limit=1)
        self.assertTrue(rec)
        self.assertEqual(rec.sr_name, "SR Person")
        self.assertEqual(rec.state, "synced")

    def test_on_search_non_success_status_skipped(self):
        message = {
            "correlation_id": "corr-2",
            "search_response": [
                {"status": "rjct", "status_reason_message": "denied", "data": {"reg_records": [self._reg_record()]}}
            ],
        }
        result = _run(
            self.callback.receive_sr_search_response(
                _request(), self._envelope(message), self.env, verified_sender_id=self.test_sender_id
            )
        )
        self.assertEqual(result["message"]["ack_status"], "rcvd")
        rec = self.env["spp.dci.sr.record"].search([("partner_id", "=", self.partner.id)])
        self.assertFalse(rec)

    def test_on_search_empty_correlation_defaults(self):
        message = {"search_response": []}
        result = _run(
            self.callback.receive_sr_search_response(
                _request(), self._envelope(message), self.env, verified_sender_id=self.test_sender_id
            )
        )
        self.assertEqual(result["message"]["correlation_id"], "")

    # --- on-subscribe --------------------------------------------------------

    def test_on_subscribe_response_acks(self):
        message = {"correlation_id": "sub-corr"}
        result = _run(
            self.callback.receive_sr_subscribe_response(
                _request(), self._envelope(message), self.env, verified_sender_id=self.test_sender_id
            )
        )
        self.assertEqual(result["message"]["ack_status"], "rcvd")
        self.assertEqual(result["message"]["correlation_id"], "sub-corr")

    # --- on-notify -----------------------------------------------------------

    def _notify(self, event_type, notify_data=None):
        message = {
            "event_type": event_type,
            "correlation_id": "notify-corr",
            "notify_data": notify_data or {},
        }
        return _run(
            self.callback.receive_sr_notification(
                _request(), self._envelope(message), self.env, verified_sender_id=self.test_sender_id
            )
        )

    def _notify_data(self):
        return {
            "identifier": [{"identifier_type": self.id_code.code, "identifier_value": "SR-NID-1"}],
            "id": "EXT-NOTIFY",
            "name": "Notified Person",
        }

    def test_on_notify_enrollment_updates_record(self):
        result = self._notify("ENROLLMENT", self._notify_data())
        self.assertEqual(result["message"]["ack_status"], "rcvd")
        rec = self.env["spp.dci.sr.record"].search([("partner_id", "=", self.partner.id)], limit=1)
        self.assertEqual(rec.sr_name, "Notified Person")

    def test_on_notify_disenrollment(self):
        result = self._notify("DISENROLLMENT", self._notify_data())
        self.assertEqual(result["message"]["ack_status"], "rcvd")

    def test_on_notify_update(self):
        result = self._notify("UPDATE", self._notify_data())
        self.assertEqual(result["message"]["ack_status"], "rcvd")

    def test_on_notify_unknown_event_still_acks(self):
        result = self._notify("MYSTERY", self._notify_data())
        self.assertEqual(result["message"]["ack_status"], "rcvd")

    def test_on_notify_processing_error_returns_500(self):
        with patch(f"{CALLBACK}._process_enrollment_notification", side_effect=RuntimeError("boom")):
            with self.assertRaises(HTTPException) as ctx:
                self._notify("ENROLLMENT", self._notify_data())
        self.assertEqual(ctx.exception.status_code, 500)

    # --- helpers -------------------------------------------------------------

    def test_find_partner_by_identifier_found(self):
        partner = self.callback._find_partner_by_identifier(self.env, self.id_code.code, "SR-NID-1")
        self.assertEqual(partner, self.partner)

    def test_find_partner_by_identifier_not_found(self):
        partner = self.callback._find_partner_by_identifier(self.env, self.id_code.code, "MISSING")
        self.assertFalse(partner)

    def test_update_sr_record_creates_then_updates(self):
        self.callback._update_sr_record(self.env, self.partner, self._reg_record(name="First"), "srcreg")
        rec = self.env["spp.dci.sr.record"].search(
            [("partner_id", "=", self.partner.id), ("source_registry", "=", "srcreg")], limit=1
        )
        self.assertEqual(rec.sr_name, "First")
        # Second call with same partner+registry updates the existing record.
        self.callback._update_sr_record(self.env, self.partner, self._reg_record(name="Second"), "srcreg")
        rec.invalidate_recordset()
        self.assertEqual(rec.sr_name, "Second")
