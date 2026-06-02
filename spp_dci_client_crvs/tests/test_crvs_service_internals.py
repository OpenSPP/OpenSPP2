# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Coverage for CRVSService internals: process_notification, error paths,
response-shape branches and _extract_birth_data variants.

These complement test_crvs_service.py (happy-path subscribe/verify/check)
by exercising the validation, invalid-response and exception branches plus
the notification-to-event pipeline.
"""

from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.spp_dci.schemas.constants import RegistryType

from .common import CRVSClientCommon

# verify_birth/check_death now use the OpenCRVS-specific search format.
SEARCH = "odoo.addons.spp_dci_client.services.client.DCIClient.search_by_id_opencrvs"


@tagged("post_install", "-at_install")
class TestCRVSServiceInternals(CRVSClientCommon):
    def setUp(self):
        super().setUp()
        self.data_source = self.env["spp.dci.data.source"].create(
            {
                "name": "Internals CRVS",
                "code": "internals_crvs",
                "base_url": "https://crvs.example.org/api",
                "auth_type": "none",
                "our_sender_id": "openspp.example.org",
                "our_callback_uri": "https://openspp.example.org/callback",
                "registry_type": RegistryType.CRVS.value,
            }
        )

    def _get_service(self):
        from odoo.addons.spp_dci_client_crvs.services import CRVSService

        return CRVSService(self.env, self.data_source.code)

    # --- argument validation -------------------------------------------------

    def test_verify_birth_requires_identifier(self):
        service = self._get_service()
        with self.assertRaises(ValidationError):
            service.verify_birth("", "")

    def test_check_death_requires_identifier(self):
        service = self._get_service()
        with self.assertRaises(ValidationError):
            service.check_death("UIN", "")

    # --- verify_birth response-shape branches --------------------------------

    @patch(SEARCH)
    def test_verify_birth_invalid_response_returns_none(self, mock_search):
        mock_search.return_value = {"no_message": True}
        self.assertIsNone(self._get_service().verify_birth("BRN", "B-1"))

    @patch(SEARCH)
    def test_verify_birth_empty_data_returns_none(self, mock_search):
        mock_search.return_value = {"message": {"search_response": [{"data": []}]}}
        self.assertIsNone(self._get_service().verify_birth("BRN", "B-1"))

    @patch(SEARCH)
    def test_verify_birth_data_as_dict(self, mock_search):
        # data may arrive as a bare dict rather than a list
        mock_search.return_value = {
            "message": {"search_response": [{"data": {"name": "Jane Doe", "birth_date": "2001-02-03"}}]}
        }
        result = self._get_service().verify_birth("BRN", "B-1")
        self.assertEqual(result["person_name"], "Jane Doe")
        self.assertEqual(result["birth_date"], "2001-02-03")

    @patch(SEARCH)
    def test_verify_birth_propagates_as_usererror(self, mock_search):
        mock_search.side_effect = RuntimeError("boom")
        with self.assertRaises(UserError):
            self._get_service().verify_birth("BRN", "B-1")

    # --- check_death branches ------------------------------------------------

    @patch(SEARCH)
    def test_check_death_invalid_response_false(self, mock_search):
        mock_search.return_value = {"nope": 1}
        self.assertFalse(self._get_service().check_death("UIN", "U-1"))

    @patch(SEARCH)
    def test_check_death_empty_data_false(self, mock_search):
        mock_search.return_value = {"message": {"search_response": [{"data": []}]}}
        self.assertFalse(self._get_service().check_death("UIN", "U-1"))

    @patch(SEARCH)
    def test_check_death_propagates_as_usererror(self, mock_search):
        mock_search.side_effect = RuntimeError("boom")
        with self.assertRaises(UserError):
            self._get_service().check_death("UIN", "U-1")

    # --- process_notification ------------------------------------------------

    def test_process_notification_requires_data(self):
        with self.assertRaises(ValidationError):
            self._get_service().process_notification({})

    def test_process_notification_creates_event_from_envelope(self):
        service = self._get_service()
        event_id = service.process_notification(
            {
                "header": {"sender_id": "crvs.example.org"},
                "message": {
                    "event_type": "DEATH",
                    "event_date": "2024-01-02",
                    "identifiers": [{"type": "national_id", "value": "PN-1"}],
                },
            }
        )
        event = self.env["spp.dci.crvs.event"].browse(event_id)
        self.assertEqual(event.event_type, "death")
        self.assertEqual(event.identifier_type, "national_id")
        self.assertEqual(event.identifier_value, "PN-1")

    def test_process_notification_bare_message(self):
        # notification without an envelope wrapper - message at top level
        service = self._get_service()
        event_id = service.process_notification(
            {
                "event_type": "BIRTH",
                "event_date": "2024-03-04",
                "identifiers": [{"type": "national_id", "value": "PN-2"}],
            }
        )
        event = self.env["spp.dci.crvs.event"].browse(event_id)
        self.assertEqual(event.event_type, "birth")
        self.assertEqual(event.identifier_value, "PN-2")

    def test_process_notification_wraps_errors(self):
        # An invalid event_type makes crvs.event.create raise; the service
        # must re-raise as ValidationError.
        service = self._get_service()
        with self.assertRaises(ValidationError):
            service.process_notification(
                {"message": {"event_type": "not-a-real-type", "identifiers": []}}
            )

    # --- _extract_birth_data variants ----------------------------------------

    def test_extract_birth_data_brn_and_birthdate_alt(self):
        service = self._get_service()
        data = service._extract_birth_data(
            {
                "identifiers": [{"type": "UIN", "value": "u"}, {"type": "BRN", "value": "BRN-9"}],
                "birthdate": "1999-09-09",
            }
        )
        self.assertEqual(data["identifier_type"], "BRN")
        self.assertEqual(data["identifier_value"], "BRN-9")
        self.assertEqual(data["birth_date"], "1999-09-09")

    def test_extract_birth_data_given_family_and_parents(self):
        service = self._get_service()
        data = service._extract_birth_data(
            {
                "given_name": "John",
                "family_name": "Doe",
                "mother_name": "Jane",
                "father_name": "James",
                "place_of_birth": "General Hospital",
            }
        )
        self.assertEqual(data["person_name"], "John Doe")
        self.assertEqual(data["mother_name"], "Jane")
        self.assertEqual(data["father_name"], "James")
        self.assertEqual(data["place_of_birth"], "General Hospital")
