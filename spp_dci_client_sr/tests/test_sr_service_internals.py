# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Coverage for SRService methods not exercised by test_sr_service:
check_connection failure, async search, search_household, check_eligibility,
get_program_enrollment, unsubscribe and the subscribe failure branches.

DCIClient calls are mocked at the method level; the mocks mirror the DCI
envelope shape (``{message: {...}}``) that the service unwraps.
"""

from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

SEARCH = "odoo.addons.spp_dci_client.services.client.DCIClient.search"
SEARCH_ASYNC = "odoo.addons.spp_dci_client.services.client.DCIClient.search_async"
SUBSCRIBE = "odoo.addons.spp_dci_client.services.client.DCIClient.subscribe"
UNSUBSCRIBE = "odoo.addons.spp_dci_client.services.client.DCIClient.unsubscribe"


def _person(enrolled_programs=None):
    return {
        "id": "EXT-1",
        "name": "SR Person",
        "enrolled_programs": enrolled_programs if enrolled_programs is not None else [],
    }


def _sync_envelope(reg_records, status="succ"):
    return {
        "message": {
            "search_response": [
                {"status": status, "data": {"reg_records": reg_records}},
            ]
        }
    }


@tagged("post_install", "-at_install")
class TestSRServiceInternals(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "SR Internals",
                "code": "sr_internals",
                "base_url": "https://sr.example.org",
                "our_sender_id": "openspp.test",
                "auth_type": "none",
                "registry_type": "sr",
                "state": "active",
            }
        )

    def _service(self):
        from odoo.addons.spp_dci_client_sr.services import SRService

        return SRService(self.env, self.data_source.code)

    # --- init / connection ---------------------------------------------------

    def test_init_missing_data_source_raises(self):
        from odoo.addons.spp_dci_client_sr.services import SRService

        with self.assertRaises(UserError):
            SRService(self.env, "does_not_exist")

    @patch(SEARCH)
    def test_check_connection_success(self, mock_search):
        mock_search.return_value = {"message": {"search_response": []}}
        self.assertTrue(self._service().check_connection())

    @patch(SEARCH)
    def test_check_connection_failure_propagates(self, mock_search):
        mock_search.side_effect = RuntimeError("down")
        with self.assertRaises(RuntimeError):
            self._service().check_connection()

    # --- search_person -------------------------------------------------------

    @patch(SEARCH_ASYNC)
    def test_search_person_async_returns_correlation(self, mock_async):
        mock_async.return_value = {"message": {"correlation_id": "corr-async"}}
        result = self._service().search_person("UIN", "U-1", async_mode=True)
        self.assertEqual(result, {"correlation_id": "corr-async"})

    @patch(SEARCH_ASYNC)
    def test_search_person_async_no_correlation_returns_none(self, mock_async):
        mock_async.return_value = {"message": {}}
        self.assertIsNone(self._service().search_person("UIN", "U-1", async_mode=True))

    @patch(SEARCH)
    def test_search_person_no_results_returns_none(self, mock_search):
        mock_search.return_value = {"message": {"search_response": []}}
        self.assertIsNone(self._service().search_person("UIN", "U-1"))

    @patch(SEARCH)
    def test_search_person_only_rejected_returns_none(self, mock_search):
        mock_search.return_value = _sync_envelope([_person()], status="rjct")
        self.assertIsNone(self._service().search_person("UIN", "U-1"))

    # --- search_household ----------------------------------------------------

    @patch(SEARCH)
    def test_search_household_sync_found(self, mock_search):
        mock_search.return_value = _sync_envelope([{"id": "HH-1", "household_size": 4}])
        result = self._service().search_household("HH-1")
        self.assertEqual(result["id"], "HH-1")

    @patch(SEARCH_ASYNC)
    def test_search_household_async(self, mock_async):
        mock_async.return_value = {"message": {"correlation_id": "hh-corr"}}
        self.assertEqual(self._service().search_household("HH-1", async_mode=True), {"correlation_id": "hh-corr"})

    @patch(SEARCH)
    def test_search_household_not_found(self, mock_search):
        mock_search.return_value = {"message": {"search_response": []}}
        self.assertIsNone(self._service().search_household("HH-1"))

    @patch(SEARCH)
    def test_search_household_error_raises_usererror(self, mock_search):
        mock_search.side_effect = RuntimeError("boom")
        with self.assertRaises(UserError):
            self._service().search_household("HH-1")

    # --- get_program_enrollment ----------------------------------------------

    @patch(SEARCH)
    def test_get_program_enrollment_returns_programs(self, mock_search):
        mock_search.return_value = _sync_envelope([_person(enrolled_programs=[{"id": "P1"}])])
        self.assertEqual(self._service().get_program_enrollment("UIN", "U-1"), [{"id": "P1"}])

    @patch(SEARCH)
    def test_get_program_enrollment_not_found_returns_empty(self, mock_search):
        mock_search.return_value = {"message": {"search_response": []}}
        self.assertEqual(self._service().get_program_enrollment("UIN", "U-1"), [])

    # --- check_eligibility ---------------------------------------------------

    @patch(SEARCH)
    def test_check_eligibility_not_found(self, mock_search):
        mock_search.return_value = {"message": {"search_response": []}}
        result = self._service().check_eligibility("UIN", "U-1")
        self.assertFalse(result["found"])
        self.assertFalse(result["eligible"])

    @patch(SEARCH)
    def test_check_eligibility_found_eligible(self, mock_search):
        mock_search.return_value = _sync_envelope([_person(enrolled_programs=[{"id": "P1"}])])
        result = self._service().check_eligibility("UIN", "U-1")
        self.assertTrue(result["found"])
        self.assertTrue(result["eligible"])
        self.assertEqual(result["enrolled_programs"], [{"id": "P1"}])

    @patch(SEARCH)
    def test_check_eligibility_already_enrolled_in_program(self, mock_search):
        mock_search.return_value = _sync_envelope([_person(enrolled_programs=[{"id": "P9"}])])
        result = self._service().check_eligibility("UIN", "U-1", program_id="P9")
        self.assertFalse(result["eligible"])
        self.assertIn("P9", result["reason"])

    @patch(SEARCH)
    def test_check_eligibility_error_returns_error_dict(self, mock_search):
        # search_person re-raises as UserError; check_eligibility catches and
        # returns a structured error dict rather than propagating.
        mock_search.side_effect = RuntimeError("boom")
        result = self._service().check_eligibility("UIN", "U-1")
        self.assertFalse(result["found"])
        self.assertIn("Error checking eligibility", result["reason"])

    # --- subscribe / unsubscribe ---------------------------------------------

    @patch(SUBSCRIBE)
    def test_subscribe_updates_failure_raises(self, mock_subscribe):
        mock_subscribe.side_effect = RuntimeError("net")
        with self.assertRaises(UserError):
            self._service().subscribe_updates(event_types=["ENROLLMENT"])

    @patch(SUBSCRIBE)
    def test_subscribe_updates_no_correlation_raises(self, mock_subscribe):
        mock_subscribe.return_value = {"message": {}}
        with self.assertRaises(UserError):
            self._service().subscribe_updates(event_types=["ENROLLMENT"])

    @patch(UNSUBSCRIBE)
    def test_unsubscribe_success(self, mock_unsub):
        mock_unsub.return_value = {"message": {"ack_status": "ACK"}}
        result = self._service().unsubscribe(["sub-1"])
        mock_unsub.assert_called_once_with(subscription_codes=["sub-1"])
        self.assertIsNotNone(result)

    def test_unsubscribe_requires_codes(self):
        with self.assertRaises(ValidationError):
            self._service().unsubscribe([])

    @patch(UNSUBSCRIBE)
    def test_unsubscribe_failure_raises_usererror(self, mock_unsub):
        mock_unsub.side_effect = RuntimeError("boom")
        with self.assertRaises(UserError):
            self._service().unsubscribe(["sub-1"])
