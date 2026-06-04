# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Additional coverage for services/sr_service.py.

Targets the small number of branches not yet reached:
- SRService.__init__: wrong registry_type logs a warning (does not raise)
- search_household async with no correlation_id returns None
- subscribe_updates with multiple event types where one succeeds and one fails
"""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

SEARCH_ASYNC = "odoo.addons.spp_dci_client.services.client.DCIClient.search_async"
SUBSCRIBE = "odoo.addons.spp_dci_client.services.client.DCIClient.subscribe"


@tagged("post_install", "-at_install")
class TestSRServiceCoverage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sr_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "SR Coverage DS",
                "code": "sr_cov_ds",
                "base_url": "https://sr.example.org",
                "our_sender_id": "openspp.cov",
                "auth_type": "none",
                "registry_type": "sr",
                "state": "active",
            }
        )
        # A data source whose registry_type is NOT 'sr', to trigger the warning.
        cls.non_sr_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "Non-SR DS",
                "code": "non_sr_ds",
                "base_url": "https://other.example.org",
                "our_sender_id": "openspp.non.sr",
                "auth_type": "none",
                "registry_type": "crvs",
                "state": "active",
            }
        )

    def _service(self, code=None):
        from odoo.addons.spp_dci_client_sr.services import SRService

        return SRService(self.env, code or self.sr_source.code)

    # --- __init__: non-sr registry_type logs a warning ---

    def test_init_non_sr_registry_type_warns_but_succeeds(self):
        """Initialising SRService with a non-SR data source logs a warning but
        does not raise — the service is still usable (caller's responsibility)."""
        from odoo.addons.spp_dci_client_sr.services import SRService

        with patch("odoo.addons.spp_dci_client_sr.services.sr_service._logger") as mock_log:
            service = SRService(self.env, self.non_sr_source.code)
            mock_log.warning.assert_called_once()
            warning_msg = mock_log.warning.call_args[0][0]
            self.assertIn("expected 'sr'", warning_msg)

        self.assertEqual(service.data_source.code, self.non_sr_source.code)

    # --- search_household async with no correlation_id ---

    @patch(SEARCH_ASYNC)
    def test_search_household_async_no_correlation_returns_none(self, mock_async):
        """search_household in async mode returns None when the envelope carries
        no correlation_id (empty message dict)."""
        mock_async.return_value = {"message": {}}
        result = self._service().search_household("HH-NOCORR", async_mode=True)
        self.assertIsNone(result)

    # --- subscribe_updates: failure mid-loop raises UserError ---

    @patch(SUBSCRIBE)
    def test_subscribe_updates_failure_on_second_event_raises(self, mock_subscribe):
        """When subscribe fails on the second event type, UserError is raised.
        The first successful subscription is irrelevant — the error propagates."""
        # First call succeeds, second call raises.
        mock_subscribe.side_effect = [
            {"message": {"correlation_id": "first-sub"}},
            RuntimeError("network timeout"),
        ]
        with self.assertRaises(UserError) as ctx:
            self._service().subscribe_updates(event_types=["ENROLLMENT", "DISENROLLMENT"])
        self.assertIn("subscribe", ctx.exception.args[0].lower())

    # --- subscribe_updates: all events return no correlation_id ---

    @patch(SUBSCRIBE)
    def test_subscribe_updates_no_correlation_raises_usererror(self, mock_subscribe):
        """When subscribe succeeds but returns no correlation_id for any event,
        UserError is raised because subscription_ids remains empty."""
        mock_subscribe.return_value = {"message": {}}
        with self.assertRaises(UserError) as ctx:
            self._service().subscribe_updates(event_types=["ENROLLMENT"])
        self.assertIn("No subscriptions", ctx.exception.args[0])

    # --- check_eligibility: string program id (not dict) ---

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_check_eligibility_string_program_already_enrolled(self, mock_search):
        """When enrolled_programs contains plain strings (not dicts), the
        string comparison branch in check_eligibility is exercised."""
        mock_search.return_value = {
            "message": {
                "search_response": [
                    {
                        "status": "succ",
                        "data": {
                            "reg_records": [
                                {
                                    "id": "EXT-STR",
                                    "enrolled_programs": ["PROG-STR-1", "PROG-STR-2"],
                                }
                            ]
                        },
                    }
                ]
            }
        }
        result = self._service().check_eligibility("UIN", "U-STR", program_id="PROG-STR-1")
        self.assertFalse(result["eligible"])
        self.assertIn("PROG-STR-1", result["reason"])
