# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for SR Service.

DCIClient.search and search_async return the *full DCI envelope* parsed
from the upstream registry - i.e. ``{signature?, header?, message: {...}}``.
SRService unwraps ``message.search_response[*]`` for sync results and
``message.correlation_id`` for async ones. Mocks here mirror that shape.
"""

import uuid
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


def _sync_search_envelope(reg_records, status="succ", reg_type="SOCIAL_REGISTRY"):
    """Build the envelope DCIClient.search returns for a successful sync search."""
    return {
        "header": {"action": "search", "sender_id": "test.sr"},
        "message": {
            "transaction_id": "txn-test",
            "search_response": [
                {
                    "reference_id": "ref-test",
                    "timestamp": "2026-01-01T00:00:00",
                    "status": status,
                    "data": {
                        "reg_type": reg_type,
                        "reg_record_type": "PERSON",
                        "reg_records": reg_records,
                    },
                }
            ],
        },
    }


def _async_search_envelope(correlation_id):
    """Build the envelope DCIClient.search_async returns."""
    return {
        "header": {"action": "search", "sender_id": "test.sr"},
        "message": {"correlation_id": correlation_id},
    }


def _subscribe_envelope(correlation_id):
    """Build the envelope DCIClient.subscribe returns."""
    return {
        "header": {"action": "subscribe", "sender_id": "test.sr"},
        "message": {"correlation_id": correlation_id},
    }


@tagged("post_install", "-at_install")
class TestSRService(TransactionCase):
    """Test cases for SR Service."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.DataSource = cls.env["spp.dci.data.source"]
        cls.Partner = cls.env["res.partner"]

        # Create test data source
        cls.test_data_source = cls.DataSource.create(
            {
                "name": "Test SR Data Source",
                "code": "test_sr",
                "base_url": "https://sr.example.org",
                "our_sender_id": "openspp.test",
                "auth_type": "none",  # Use no auth for testing
                "registry_type": "sr",
                "state": "active",
            }
        )

        # Create test partner
        cls.test_partner = cls.Partner.create(
            {
                "name": "Test Person for SR",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def _get_sr_service(self):
        """Create SR service instance."""
        from odoo.addons.spp_dci_client_sr.services import SRService

        return SRService(self.env, "test_sr")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_search_person_sync(self, mock_search):
        """Sync search unwraps message.search_response[0].data.reg_records[0]."""
        mock_search.return_value = _sync_search_envelope(
            reg_records=[
                {
                    "id": "PERSON_001",
                    "name": "John Doe",
                    "birth_date": "1990-01-15",
                    "gender": "male",
                }
            ]
        )

        service = self._get_sr_service()
        result = service.search_person("UIN", "123456789", async_mode=False)

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "PERSON_001")
        self.assertEqual(result["name"], "John Doe")
        mock_search.assert_called_once()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search_async")
    def test_search_person_async(self, mock_search_async):
        """Async search returns {'correlation_id': ...} from the envelope."""
        correlation = str(uuid.uuid4())
        mock_search_async.return_value = _async_search_envelope(correlation)

        service = self._get_sr_service()
        result = service.search_person("UIN", "123456789", async_mode=True)

        self.assertIsNotNone(result)
        self.assertEqual(result["correlation_id"], correlation)
        mock_search_async.assert_called_once()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_search_household(self, mock_search):
        """Household sync search unwraps the same envelope shape."""
        mock_search.return_value = _sync_search_envelope(
            reg_records=[
                {"id": "MEMBER_001", "name": "Member 1", "household_id": "HH_001"},
                {"id": "MEMBER_002", "name": "Member 2", "household_id": "HH_001"},
            ]
        )

        service = self._get_sr_service()
        result = service.search_household("HH_001")

        self.assertIsNotNone(result)
        self.assertEqual(result["household_id"], "HH_001")
        mock_search.assert_called_once()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_get_program_enrollment(self, mock_search):
        """get_program_enrollment routes through search_person + reads .enrolled_programs."""
        mock_search.return_value = _sync_search_envelope(
            reg_records=[
                {
                    "id": "PERSON_001",
                    "enrolled_programs": ["Cash Transfer", "Food Assistance"],
                }
            ]
        )

        service = self._get_sr_service()
        result = service.get_program_enrollment("UIN", "123456789")

        self.assertEqual(result, ["Cash Transfer", "Food Assistance"])
        mock_search.assert_called_once()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.subscribe")
    def test_subscribe_updates(self, mock_subscribe):
        """Subscribe reads message.correlation_id and returns a list of IDs."""
        mock_subscribe.return_value = _subscribe_envelope("SUB-001")

        service = self._get_sr_service()
        result = service.subscribe_updates(event_types=["ENROLLMENT"])

        self.assertEqual(result, ["SUB-001"])
        mock_subscribe.assert_called_once()

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_sync_person_to_local_new_record(self, mock_search):
        """sync_person_to_local creates a new spp.dci.sr.record when none exists."""
        mock_search.return_value = _sync_search_envelope(
            reg_records=[
                {
                    "id": "EXT_001",
                    "name": "Synced Person",
                    "birth_date": "1985-03-20",
                    "gender": "female",
                    "enrolled_programs": ["Program A"],
                    "household_id": "HH_100",
                    "household_size": 4,
                    "is_head_of_household": True,
                }
            ]
        )

        service = self._get_sr_service()
        result = service.sync_person_to_local(
            "UIN",
            "SYNC_001",
            partner_id=self.test_partner.id,
        )

        self.assertTrue(result)
        sr_record = self.env["spp.dci.sr.record"].search(
            [("partner_id", "=", self.test_partner.id)],
            limit=1,
        )
        self.assertTrue(sr_record)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_sync_person_to_local_update_record(self, mock_search):
        """sync_person_to_local updates an existing record matched by
        (partner_id, source_registry). source_registry stores the data
        source's our_sender_id, not its code."""
        self.env["spp.dci.sr.record"].create(
            {
                "partner_id": self.test_partner.id,
                "external_id": "EXT_002",
                "source_registry": self.test_data_source.our_sender_id,
                "sr_name": "Old Name",
                "state": "synced",
            }
        )

        mock_search.return_value = _sync_search_envelope(
            reg_records=[
                {
                    "id": "EXT_002",
                    "name": "Updated Name",
                    "enrolled_programs": ["Program B"],
                }
            ]
        )

        service = self._get_sr_service()
        result = service.sync_person_to_local(
            "UIN",
            "SYNC_002",
            partner_id=self.test_partner.id,
        )

        self.assertTrue(result)
        sr_record = self.env["spp.dci.sr.record"].search(
            [
                ("partner_id", "=", self.test_partner.id),
                ("source_registry", "=", self.test_data_source.our_sender_id),
            ]
        )
        self.assertEqual(sr_record.sr_name, "Updated Name")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_sync_person_to_local_looks_up_partner_by_identifier(self, mock_search):
        """Without an explicit partner_id, sync_person_to_local must look up
        the local partner via spp.registry.id. Earlier code queried a
        non-existent 'spp.id' model and silently fell through to the
        UserError 'Could not find local partner' even when the identifier
        existed.
        """
        # Match the National ID vocabulary code shipped with spp_vocabulary
        # so id_type_id.code resolves the way the production query expects.
        national_id_code = self.env.ref("spp_vocabulary.code_id_type_national_id")
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.test_partner.id,
                "id_type_id": national_id_code.id,
                "value": "LOOKUP-001",
            }
        )

        mock_search.return_value = _sync_search_envelope(
            reg_records=[
                {
                    "id": "EXT_LOOKUP",
                    "name": "Lookup Person",
                }
            ]
        )

        service = self._get_sr_service()
        # No partner_id - service must resolve it from the identifier.
        result = service.sync_person_to_local(national_id_code.code, "LOOKUP-001")
        self.assertTrue(result)
        self.assertEqual(result.partner_id, self.test_partner)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_sync_person_to_local_looks_up_partner_by_namespace_uri(self, mock_search):
        """A namespace-URI identifier type must resolve the local partner via
        id_type_id.namespace_uri (the callback router's fallback); an exact
        code search cannot match the URN form."""
        national_id_code = self.env.ref("spp_vocabulary.code_id_type_national_id")
        self.assertTrue(
            national_id_code.namespace_uri,
            "seeded id-type code must carry a vocabulary namespace URI",
        )
        self.env["spp.registry.id"].create(
            {
                "partner_id": self.test_partner.id,
                "id_type_id": national_id_code.id,
                "value": "LOOKUP-URN-001",
            }
        )

        mock_search.return_value = _sync_search_envelope(
            reg_records=[
                {
                    "id": "EXT_LOOKUP_URN",
                    "name": "Lookup Person URN",
                }
            ]
        )

        service = self._get_sr_service()
        result = service.sync_person_to_local(national_id_code.namespace_uri, "LOOKUP-URN-001")
        self.assertTrue(result)
        self.assertEqual(result.partner_id, self.test_partner)

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_search_person_uses_data_source_registry_type(self, mock_search):
        """The service must not override the registry type - the client
        derives it from the data source (namespaced per SPDCI). A hardcoded
        ad-hoc value made every search get rejected by compliant servers."""
        mock_search.return_value = _sync_search_envelope(reg_records=[])
        service = self._get_sr_service()
        service.search_person("UIN", "RT-001")
        kwargs = mock_search.call_args.kwargs
        self.assertIsNone(
            kwargs.get("registry_type"),
            f"search_person must not override registry_type, got {kwargs.get('registry_type')!r}",
        )

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_search_household_uses_data_source_registry_type(self, mock_search):
        """Same contract for household search."""
        mock_search.return_value = _sync_search_envelope(reg_records=[])
        service = self._get_sr_service()
        service.search_household("HH-RT-002")
        kwargs = mock_search.call_args.kwargs
        self.assertIsNone(
            kwargs.get("registry_type"),
            f"search_household must not override registry_type, got {kwargs.get('registry_type')!r}",
        )

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_sync_person_not_found_raises(self, mock_search):
        """When the registry returns no records, sync raises UserError per docstring."""
        mock_search.return_value = _sync_search_envelope(reg_records=[])

        service = self._get_sr_service()
        with self.assertRaises(UserError):
            service.sync_person_to_local(
                "UIN",
                "NOT_FOUND",
                partner_id=self.test_partner.id,
            )

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_search_person_propagates_api_errors(self, mock_search):
        """API failures wrap into UserError so callers see them; they are not
        silently swallowed (the docstring says ``Raises: UserError``)."""
        mock_search.side_effect = Exception("API Error")

        service = self._get_sr_service()
        with self.assertRaises(UserError):
            service.search_person("UIN", "123456789")

    @patch("odoo.addons.spp_dci_client.services.client.DCIClient.search")
    def test_check_connection(self, mock_search):
        """Test check_connection method."""
        mock_search.return_value = {"message": {"status": "ok"}}

        service = self._get_sr_service()
        result = service.check_connection()

        self.assertTrue(result)
        mock_search.assert_called_once()

    def test_service_initialization(self):
        """Test service initialization with data source."""
        service = self._get_sr_service()

        self.assertEqual(service.data_source.code, "test_sr")
        self.assertEqual(service.env, self.env)
        self.assertIsNotNone(service.client)
