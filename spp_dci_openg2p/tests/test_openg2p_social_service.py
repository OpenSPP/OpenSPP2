"""OpenG2PSocialService unit tests.

Locks in:
  - get_partner_record returns the raw reg_record dict when OpenG2P matches
  - Returns None on REG-ERR-001 / empty search_response
  - Returns None when the partner has no resolvable identifier (no HTTP call)
  - Response unwrap walks message.search_response[i].data.reg_records[0]
  - Search request is issued with the partner identifier value as the
    expression query's search_text
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci.schemas import QueryType
from odoo.addons.spp_dci_openg2p.services.openg2p_social_service import (
    OpenG2PSocialService,
)


def make_sr_response(reg_records):
    """Shape that matches OpenG2P's actual response envelope (Social Registry)."""
    return {
        "signature": "",
        "header": {
            "version": "1.0.0",
            "message_id": "m1",
            "message_ts": "2026-05-14T00:00:00Z",
            "action": "search",
            "status": "succ",
            "sender_id": "openg2p.test",
            "receiver_id": "openspp.test",
        },
        "message": {
            "transaction_id": "t1",
            "correlation_id": "c1",
            "search_response": [
                {
                    "reference_id": "r1",
                    "timestamp": "2026-05-14T00:00:00Z",
                    "status": "succ",
                    "data": {
                        "version": "1.0.0",
                        "reg_type": "Individual",
                        "reg_record_type": "Individual",
                        "reg_records": reg_records,
                    },
                }
            ],
        },
    }


def make_sr_not_found_response():
    """Shape returned by OpenG2P for REG-ERR-001 / unknown identifier."""
    return {
        "signature": "",
        "header": {
            "version": "1.0.0",
            "message_id": "m1",
            "message_ts": "2026-05-14T00:00:00Z",
            "action": "search",
            "status": "rjct",
            "status_reason_code": "REG-ERR-001",
            "status_reason_message": "REGISTER_NOT_FOUND",
            "sender_id": "openg2p.test",
            "receiver_id": "openspp.test",
        },
        "message": {
            "transaction_id": "t1",
            "correlation_id": "c1",
            "search_response": [],
        },
    }


@tagged("post_install", "-at_install")
class TestOpenG2PSocialService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "OpenG2P SR Test Source",
                "code": "openg2p_sr_test",
                "registry_type": "SR",
                "vendor": "openg2p",
                "base_url": "https://partner-registry.play.openg2p.org",
                "search_endpoint": "/dci/registry/sync/search",
                "auth_type": "none",
                "our_sender_id": "openspp.test",
                "receiver_id": "openg2p.test",
            }
        )

        cls.id_type_uin = cls.env.ref("spp_dci_openg2p.id_type_uin")

        cls.partner_known = cls.env["res.partner"].create(
            {"name": "Known Registrant", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_known.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "IND-NSR-0001",
            }
        )

        cls.partner_no_id = cls.env["res.partner"].create(
            {"name": "Partner Without ID", "is_registrant": True, "is_group": False}
        )

    @staticmethod
    def _make_service_with_mock_client(env, data_source, mock_client):
        """Construct an OpenG2PSocialService with a mocked OpenG2PDCIClient
        injected, bypassing __init__ which would touch the DCI client
        constructor and the data source loader."""
        with patch.object(
            OpenG2PSocialService.__mro__[0],
            "__init__",
            lambda self, env, data_source_code: None,
        ):
            service = OpenG2PSocialService.__new__(OpenG2PSocialService)
            service.env = env
            service.data_source_code = data_source.code
            service.data_source = data_source
            service.client = mock_client
        return service

    def test_returns_record_when_openg2p_matches(self):
        """get_partner_record returns the raw reg_record dict (no synthesis)."""
        mock_client = MagicMock()
        mock_client.search.return_value = make_sr_response(
            [{"is_poor": True, "has_dependent_under_school_age": False, "name": "Known"}]
        )
        service = self._make_service_with_mock_client(self.env, self.data_source, mock_client)

        result = service.get_partner_record(self.partner_known)

        self.assertIsNotNone(result)
        self.assertEqual(result["is_poor"], True)
        self.assertEqual(result["has_dependent_under_school_age"], False)
        self.assertEqual(result["name"], "Known")

    def test_issues_expression_query_with_partner_identifier_as_search_text(self):
        """Search must use QueryType.EXPRESSION with the partner's UIN value
        as the query_value (search_text). Verifies the SR semantics: partner
        identifier flows through unchanged, no vendor-specific synthesis."""
        mock_client = MagicMock()
        mock_client.search.return_value = make_sr_response([{"is_poor": True}])
        service = self._make_service_with_mock_client(self.env, self.data_source, mock_client)

        service.get_partner_record(self.partner_known)

        mock_client.search.assert_called_once()
        kwargs = mock_client.search.call_args.kwargs
        self.assertEqual(kwargs["query_type"], QueryType.EXPRESSION)
        self.assertEqual(kwargs["query_value"], "IND-NSR-0001")

    def test_returns_none_when_no_records(self):
        mock_client = MagicMock()
        mock_client.search.return_value = make_sr_not_found_response()
        service = self._make_service_with_mock_client(self.env, self.data_source, mock_client)

        result = service.get_partner_record(self.partner_known)

        self.assertIsNone(result)

    def test_returns_none_when_partner_has_no_identifier(self):
        """Service must not call OpenG2P at all when the partner has no
        identifier to send as search_text — saves an HTTP round-trip."""
        mock_client = MagicMock()
        service = self._make_service_with_mock_client(self.env, self.data_source, mock_client)

        result = service.get_partner_record(self.partner_no_id)

        self.assertIsNone(result)
        mock_client.search.assert_not_called()

    def test_extract_first_record_handles_empty_reg_records(self):
        response = make_sr_response([])
        self.assertIsNone(OpenG2PSocialService._extract_first_record(response))

    def test_extract_first_record_handles_missing_data_key(self):
        response = {"message": {"search_response": [{"reference_id": "r1"}]}}
        self.assertIsNone(OpenG2PSocialService._extract_first_record(response))

    def test_extract_first_record_returns_first_across_responses(self):
        response = make_sr_response([])
        response["message"]["search_response"].append(
            {
                "reference_id": "r2",
                "data": {"reg_records": [{"is_poor": True}]},
            }
        )
        record = OpenG2PSocialService._extract_first_record(response)
        self.assertEqual(record["is_poor"], True)

    def test_extract_first_record_handles_non_dict_response(self):
        """Defensive: non-dict input must return None, not raise."""
        self.assertIsNone(OpenG2PSocialService._extract_first_record(None))
        self.assertIsNone(OpenG2PSocialService._extract_first_record("not a dict"))

    def test_extract_first_record_skips_non_dict_record_entries(self):
        response = make_sr_response([])
        response["message"]["search_response"][0]["data"]["reg_records"] = [
            "junk",
            {"is_poor": False},
        ]
        record = OpenG2PSocialService._extract_first_record(response)
        self.assertEqual(record, {"is_poor": False})
