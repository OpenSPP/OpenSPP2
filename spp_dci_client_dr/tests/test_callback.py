# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DR callback endpoint processing."""

import json
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDRCallbackProcessing(TransactionCase):
    """Tests for _process_dr_search_result and _update_disability_status."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()

        cls.Partner = cls.env["res.partner"]
        cls.DisabilityStatus = cls.env["spp.dci.disability.status"]
        cls.VocabularyCode = cls.env["spp.vocabulary.code"]

        # Get or create ID type vocabulary
        id_type_vocab = cls.env["spp.vocabulary"].search([("namespace_uri", "=", "urn:openspp:vocab:id-type")], limit=1)
        if not id_type_vocab:
            id_type_vocab = cls.env["spp.vocabulary"].create(
                {
                    "name": "ID Type",
                    "namespace_uri": "urn:openspp:vocab:id-type",
                }
            )

        cls.id_type_uin = cls.VocabularyCode.create(
            {
                "vocabulary_id": id_type_vocab.id,
                "code": "UIN_DR_TEST",
                "display": "Universal Identification Number",
                "target_type": "individual",
                "is_local": True,
            }
        )

        cls.partner = cls.Partner.create(
            {
                "name": "CB Test Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.IdRecord = cls.env["spp.registry.id"]
        cls.IdRecord.create(
            {
                "partner_id": cls.partner.id,
                "id_type_id": cls.id_type_uin.id,
                "value": "UIN-CB-001",
            }
        )

    def _make_spec_result(self, disability_status="Approved", impairment_types=None):
        """Build a DCI v1.0.0 spec-shaped search result item."""
        if impairment_types is None:
            impairment_types = ["Vision"]
        return {
            "status": "succ",
            "data": {
                "version": "1.0.0",
                "reg_record_type": "PERSON",
                "reg_records": [
                    {
                        "personal_details": {"identifier": "UIN-CB-001"},
                        "identifier": [
                            {
                                "identifier_type": "UIN_DR_TEST",
                                "identifier_value": "UIN-CB-001",
                            }
                        ],
                        "disability_status": disability_status,
                        "disability_details": [{"impairment_type": t} for t in impairment_types],
                        "registration_date": "2024-01-01T00:00:00Z",
                    }
                ],
            },
        }

    def test_approved_status_creates_disability_record(self):
        """Spec-shape approved result creates spp.dci.disability.status with has_disability=True."""
        from odoo.addons.spp_dci_client_dr.routers.callback import _process_dr_search_result

        result = self._make_spec_result(disability_status="Approved", impairment_types=["Vision"])

        with patch(
            "odoo.addons.spp_dci_client_dr.routers.callback._find_partner_by_identifier",
            return_value=self.partner,
        ):
            _process_dr_search_result(self.env, result, "test-source-registry")

        status = self.DisabilityStatus.search([("partner_id", "=", self.partner.id)])
        self.assertEqual(len(status), 1)
        self.assertTrue(status.has_disability)
        self.assertEqual(status.state, "synced")

        types_list = json.loads(status.disability_types)
        self.assertIn("Vision", types_list)

    def test_rejected_status_creates_record_with_false(self):
        """Spec-shape rejected result creates spp.dci.disability.status with has_disability=False."""
        from odoo.addons.spp_dci_client_dr.routers.callback import _process_dr_search_result

        # Use a fresh partner so there is no pre-existing disability record
        rejected_partner = self.Partner.create(
            {
                "name": "CB Rejected Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

        result = self._make_spec_result(disability_status="Rejected", impairment_types=["Hearing"])

        with patch(
            "odoo.addons.spp_dci_client_dr.routers.callback._find_partner_by_identifier",
            return_value=rejected_partner,
        ):
            _process_dr_search_result(self.env, result, "test-source-registry")

        status = self.DisabilityStatus.search([("partner_id", "=", rejected_partner.id)])
        self.assertEqual(len(status), 1)
        self.assertFalse(status.has_disability)
        self.assertEqual(status.state, "synced")

    def test_non_success_status_is_skipped(self):
        """Search result with non-success status does not create a disability record."""
        from odoo.addons.spp_dci_client_dr.routers.callback import _process_dr_search_result

        skipped_partner = self.Partner.create(
            {
                "name": "CB Skipped Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

        result = {
            "status": "rjct",
            "data": {
                "version": "1.0.0",
                "reg_record_type": "PERSON",
                "reg_records": [
                    {
                        "identifier": [{"identifier_type": "UIN_DR_TEST", "identifier_value": "UIN-CB-SKIP"}],
                        "disability_status": "Approved",
                    }
                ],
            },
        }

        with patch(
            "odoo.addons.spp_dci_client_dr.routers.callback._find_partner_by_identifier",
            return_value=skipped_partner,
        ) as mock_find:
            _process_dr_search_result(self.env, result, "test-source-registry")

        # No record should be created
        status = self.DisabilityStatus.search([("partner_id", "=", skipped_partner.id)])
        self.assertEqual(len(status), 0)
        mock_find.assert_not_called()

    def test_malformed_envelope_warns_and_does_not_crash(self):
        """`data` of an unexpected type is rejected by unwrap_search_data with a WARN
        rather than crashing the callback or silently processing garbage."""
        from odoo.addons.spp_dci_client_dr.routers.callback import _process_dr_search_result

        result = {
            "status": "succ",
            "data": "not-an-envelope",
        }

        with (
            patch(
                "odoo.addons.spp_dci_client_dr.routers.callback._find_partner_by_identifier",
            ) as mock_find,
            self.assertLogs("odoo.addons.spp_dci_client_dr.services.dr_parsing", level="WARNING"),
        ):
            _process_dr_search_result(self.env, result, "test-source-registry")

        mock_find.assert_not_called()

    def test_update_overwrites_existing_record(self):
        """Calling _process_dr_search_result twice updates the existing record."""
        from odoo.addons.spp_dci_client_dr.routers.callback import _process_dr_search_result

        update_partner = self.Partner.create(
            {
                "name": "CB Update Person",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # First call: approved
        result_approved = self._make_spec_result(disability_status="Approved")
        with patch(
            "odoo.addons.spp_dci_client_dr.routers.callback._find_partner_by_identifier",
            return_value=update_partner,
        ):
            _process_dr_search_result(self.env, result_approved, "test-source-registry")

        status = self.DisabilityStatus.search([("partner_id", "=", update_partner.id)])
        self.assertEqual(len(status), 1)
        self.assertTrue(status.has_disability)

        # Second call: rejected
        result_rejected = self._make_spec_result(disability_status="Rejected")
        with patch(
            "odoo.addons.spp_dci_client_dr.routers.callback._find_partner_by_identifier",
            return_value=update_partner,
        ):
            _process_dr_search_result(self.env, result_rejected, "test-source-registry")

        # Should still be one record, now with has_disability=False
        status.invalidate_recordset()
        all_status = self.DisabilityStatus.search([("partner_id", "=", update_partner.id)])
        self.assertEqual(len(all_status), 1)
        self.assertFalse(all_status.has_disability)
