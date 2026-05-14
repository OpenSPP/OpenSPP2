"""OpenG2PFRService FR-as-DR pretense tests.

Locks in:
  - Returns {"has_disability": True, ...} when OpenG2P returns any reg_record
  - Returns None when reg_records is empty or response has no search_response
  - Unwraps OpenG2P's data.reg_records[] response shape correctly
  - Skips partners without a usable identifier
"""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.spp_dci_openg2p.services.openg2p_fr_service import (
    OpenG2PFRService,
)


def make_fr_response(reg_records):
    """Shape that matches OpenG2P's actual response envelope."""
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
                        "reg_type": "ns:org:RegistryType:Social",
                        "reg_record_type": "spdci-extensions-dci:Farmer",
                        "reg_records": reg_records,
                    },
                }
            ],
        },
    }


def make_fr_not_found_response():
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
class TestOpenG2PFRService(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.data_source = cls.env["spp.dci.data.source"].create(
            {
                "name": "OpenG2P FR Test Source",
                "code": "openg2p_fr_test",
                "registry_type": "DR",
                "vendor": "openg2p",
                "base_url": "https://partner-registry.play.openg2p.org",
                "search_endpoint": "/dci/registry/sync/search",
                "auth_type": "none",
                "our_sender_id": "openspp.test",
                "receiver_id": "openg2p.test",
            }
        )

        # ID type vocabulary code for UIN
        vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not vocab:
            vocab = cls.env["spp.vocabulary"].create(
                {"name": "ID Type (FR test)", "namespace_uri": "urn:openspp:vocab:id-type"}
            )
        cls.id_type_uin = cls.env["spp.vocabulary.code"].create(
            {
                "vocabulary_id": vocab.id,
                "code": "UIN",
                "display": "UIN (FR test)",
                "target_type": "individual",
                "is_local": True,
            }
        )

        cls.partner_known = cls.env["res.partner"].create(
            {"name": "Known Farmer", "is_registrant": True, "is_group": False}
        )
        cls.env["spp.registry.id"].create(
            {
                "partner_id": cls.partner_known.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "FR-KNOWN-1",
            }
        )

        cls.partner_no_id = cls.env["res.partner"].create(
            {"name": "Partner Without ID", "is_registrant": True, "is_group": False}
        )

    def test_returns_has_disability_true_when_record_found(self):
        with patch.object(
            OpenG2PFRService.__mro__[0],
            "__init__",
            lambda self, env, data_source_code: None,
        ):
            service = OpenG2PFRService.__new__(OpenG2PFRService)
            service.env = self.env
            service.data_source_code = "openg2p_fr_test"
            service.data_source = self.data_source
            service.client = MagicMock()
            service.client.search.return_value = make_fr_response([{"farmer_id": "F-1", "name": "Known Farmer"}])

            result = service.get_disability_status(self.partner_known)

        self.assertIsNotNone(result)
        self.assertTrue(result["has_disability"])
        self.assertEqual(result["source_registry"], "OpenG2P (FR-as-DR demo)")
        self.assertEqual(result["raw_data"]["farmer_id"], "F-1")

    def test_returns_none_when_no_records(self):
        with patch.object(
            OpenG2PFRService.__mro__[0],
            "__init__",
            lambda self, env, data_source_code: None,
        ):
            service = OpenG2PFRService.__new__(OpenG2PFRService)
            service.env = self.env
            service.data_source_code = "openg2p_fr_test"
            service.data_source = self.data_source
            service.client = MagicMock()
            service.client.search.return_value = make_fr_not_found_response()

            result = service.get_disability_status(self.partner_known)

        self.assertIsNone(result)

    def test_returns_none_when_partner_has_no_identifier(self):
        with patch.object(
            OpenG2PFRService.__mro__[0],
            "__init__",
            lambda self, env, data_source_code: None,
        ):
            service = OpenG2PFRService.__new__(OpenG2PFRService)
            service.env = self.env
            service.data_source_code = "openg2p_fr_test"
            service.data_source = self.data_source
            service.client = MagicMock()

            result = service.get_disability_status(self.partner_no_id)

        self.assertIsNone(result)
        # Service must not have called the DCI client for a partner with
        # no identifier — saves an HTTP round-trip.
        service.client.search.assert_not_called()

    def test_extract_first_record_handles_empty_reg_records(self):
        response = make_fr_response([])
        self.assertIsNone(OpenG2PFRService._extract_first_record(response))

    def test_extract_first_record_handles_missing_data_key(self):
        response = {"message": {"search_response": [{"reference_id": "r1"}]}}
        self.assertIsNone(OpenG2PFRService._extract_first_record(response))

    def test_extract_first_record_returns_first_across_responses(self):
        response = make_fr_response([])
        # Add a second search_response entry that has records
        response["message"]["search_response"].append(
            {
                "reference_id": "r2",
                "data": {"reg_records": [{"farmer_id": "F-2"}]},
            }
        )
        record = OpenG2PFRService._extract_first_record(response)
        self.assertEqual(record["farmer_id"], "F-2")

    def test_is_pwd_convenience(self):
        with patch.object(
            OpenG2PFRService.__mro__[0],
            "__init__",
            lambda self, env, data_source_code: None,
        ):
            service = OpenG2PFRService.__new__(OpenG2PFRService)
            service.env = self.env
            service.data_source_code = "openg2p_fr_test"
            service.data_source = self.data_source
            service.client = MagicMock()
            service.client.search.return_value = make_fr_response([{"farmer_id": "F-1"}])

            self.assertTrue(service.is_pwd(self.partner_known))
