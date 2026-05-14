"""OpenSPPDRService unit tests."""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci_openspp_dr.services.openspp_dr_service import (
    OpenSPPDRService,
)

from .common import get_or_create_uin_code


def make_dr_response(reg_records):
    return {
        "signature": "",
        "header": {
            "version": "1.0.0",
            "message_id": "m1",
            "message_ts": "2026-05-14T00:00:00Z",
            "action": "search",
            "status": "succ",
            "sender_id": "openspp-dr.test",
            "receiver_id": "openspp-sp.test",
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
                        "reg_type": "DR",
                        "reg_record_type": "PWD_PERSON",
                        "reg_records": reg_records,
                    },
                }
            ],
        },
    }


def make_dr_not_found_response():
    return {
        "header": {"status": "rjct", "status_reason_code": "REG-ERR-001"},
        "message": {"search_response": []},
    }


@tagged("post_install", "-at_install")
class TestOpenSPPDRService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "OpenSPP-DR Test Source",
                "code": "openspp_dr_test",
                "registry_type": "DR",
                "vendor": "openspp",
                "base_url": "http://openspp-dr.test:8069",
                "search_endpoint": "/dci_api/v1/disability/registry/sync/search",
                "auth_type": "none",
                "our_sender_id": "openspp-sp.test",
                "receiver_id": "openspp-dr.test",
            }
        )

        cls.id_type_uin = get_or_create_uin_code(cls.env)
        cls.partner_known = cls.env["res.partner"].create(
            {"name": "Known DR Registrant", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_known.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-DR-1",
            }
        )
        cls.partner_no_id = cls.env["res.partner"].create(
            {"name": "Partner Without ID", "is_registrant": True, "is_group": False}
        )

    @staticmethod
    def _make_service(env, data_source, mock_client):
        with patch.object(
            OpenSPPDRService.__mro__[0],
            "__init__",
            lambda self, env, data_source_code: None,
        ):
            service = OpenSPPDRService.__new__(OpenSPPDRService)
            service.env = env
            service.data_source_code = data_source.code
            service.data_source = data_source
            service.client = mock_client
        return service

    def test_returns_reg_record_when_dr_matches(self):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_response(
            [{"has_disability": True, "disability_certified": True, "partner_uid": 42}]
        )
        service = self._make_service(self.env, self.data_source, mock_client)

        result = service.get_partner_record(self.partner_known)

        self.assertIsNotNone(result)
        self.assertEqual(result["has_disability"], True)
        self.assertEqual(result["disability_certified"], True)

    def test_returns_none_when_dr_says_not_found(self):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_not_found_response()
        service = self._make_service(self.env, self.data_source, mock_client)

        result = service.get_partner_record(self.partner_known)

        self.assertIsNone(result)

    def test_returns_none_when_partner_has_no_identifier(self):
        """Service must not call the DR at all if the partner has no
        identifier — saves an HTTP round-trip."""
        mock_client = MagicMock()
        service = self._make_service(self.env, self.data_source, mock_client)

        result = service.get_partner_record(self.partner_no_id)

        self.assertIsNone(result)
        mock_client.search_by_id.assert_not_called()

    def test_uses_uin_as_identifier_type_first(self):
        mock_client = MagicMock()
        mock_client.search_by_id.return_value = make_dr_response(
            [{"has_disability": False}]
        )
        service = self._make_service(self.env, self.data_source, mock_client)

        service.get_partner_record(self.partner_known)

        mock_client.search_by_id.assert_called_once()
        kwargs = mock_client.search_by_id.call_args.kwargs
        self.assertEqual(kwargs["identifier_type"], "UIN")
        self.assertEqual(kwargs["identifier_value"], "UIN-DR-1")

    def test_extract_first_record_handles_empty_reg_records(self):
        response = make_dr_response([])
        self.assertIsNone(OpenSPPDRService._extract_first_record(response))

    def test_extract_first_record_handles_non_dict_response(self):
        self.assertIsNone(OpenSPPDRService._extract_first_record(None))
        self.assertIsNone(OpenSPPDRService._extract_first_record("junk"))

    def test_extract_first_record_skips_non_dict_record_entries(self):
        response = make_dr_response([])
        response["message"]["search_response"][0]["data"]["reg_records"] = [
            "junk",
            {"has_disability": True},
        ]
        record = OpenSPPDRService._extract_first_record(response)
        self.assertEqual(record, {"has_disability": True})
