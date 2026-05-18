"""SR-import wizard tests."""

from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


def _sr_response(reg_records):
    """Shape that matches OpenG2P SR's actual envelope."""
    return {
        "header": {"status": "succ"},
        "message": {
            "search_response": [
                {
                    "reference_id": "r1",
                    "status": "succ",
                    "data": {
                        "reg_type": "Individual",
                        "reg_record_type": "Individual",
                        "reg_records": reg_records,
                    },
                }
            ]
        },
    }


def _not_found_response():
    return {"header": {"status": "rjct"}, "message": {"search_response": []}}


def _payload(given, surname, sex="male", birth_date="1990-01-01"):
    return {
        "demographic_info": {
            "name": {"given_name": given, "surname": surname},
            "sex": sex,
            "birth_date": birth_date,
        }
    }


@tagged("post_install", "-at_install")
class TestSrImportWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.data_source = cls.env.ref("spp_dci_openg2p.openg2p_dr_source")
        cls.uin_type = cls.env.ref("spp_dci_openg2p.id_type_uin")

    def _wizard(self, **overrides):
        defaults = {
            "data_source_id": self.data_source.id,
            "discovery_mode": "range",
            "range_prefix": "IND-NSR-",
            "range_start": 1,
            "range_end": 3,
            "range_pad": 4,
        }
        defaults.update(overrides)
        return self.env["spp.dci.sr.import.wizard"].create(defaults)

    # ------------------------------------------------------------------
    # Identifier collection
    # ------------------------------------------------------------------

    def test_collect_identifiers_range_pads_correctly(self):
        wiz = self._wizard(range_start=1, range_end=5, range_pad=4)
        idents = wiz._collect_identifiers()
        self.assertEqual(
            idents,
            ["IND-NSR-0001", "IND-NSR-0002", "IND-NSR-0003", "IND-NSR-0004", "IND-NSR-0005"],
        )

    def test_collect_identifiers_list_strips_comments_and_dedupes(self):
        wiz = self._wizard(
            discovery_mode="list",
            identifier_list_raw="# header\nIND-NSR-0001\n\nIND-NSR-0002\nIND-NSR-0001\n",
        )
        self.assertEqual(wiz._collect_identifiers(), ["IND-NSR-0001", "IND-NSR-0002"])

    def test_collect_identifiers_rejects_empty_range(self):
        from odoo.exceptions import UserError

        wiz = self._wizard(range_start=10, range_end=5)
        with self.assertRaises(UserError):
            wiz._collect_identifiers()

    def test_collect_identifiers_rejects_empty_list(self):
        from odoo.exceptions import UserError

        wiz = self._wizard(discovery_mode="list", identifier_list_raw="   \n#only comments\n")
        with self.assertRaises(UserError):
            wiz._collect_identifiers()

    # ------------------------------------------------------------------
    # Preview step
    # ------------------------------------------------------------------

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_social_service.OpenG2PDCIClient")
    def test_preview_matched_not_found_and_existing_partner(self, mock_client_class):
        # 0001 matches, 0002 already on SP, 0003 not found
        existing_partner = self.env["res.partner"].create(
            {"name": "Existing", "is_registrant": True, "is_group": False}
        )
        self.env["spp.registry.id"].create(
            {
                "partner_id": existing_partner.id,
                "id_type_id": self.uin_type.id,
                "value": "IND-NSR-0002",
            }
        )

        def search(**kwargs):
            v = kwargs.get("query_value")
            if v == "IND-NSR-0001":
                return _sr_response([_payload("Alex", "Rivera")])
            if v == "IND-NSR-0002":
                return _sr_response([_payload("Priya", "Rivera", sex="female")])
            return _not_found_response()

        mock_client = MagicMock()
        mock_client.search.side_effect = search
        mock_client_class.return_value = mock_client

        wiz = self._wizard(range_start=1, range_end=3)
        wiz.action_preview()

        self.assertEqual(wiz.state, "preview")
        self.assertEqual(len(wiz.preview_line_ids), 3)

        by_uin = {line.uin: line for line in wiz.preview_line_ids}
        self.assertEqual(by_uin["IND-NSR-0001"].status, "matched")
        self.assertEqual(by_uin["IND-NSR-0001"].given_name, "Alex")
        self.assertEqual(by_uin["IND-NSR-0001"].surname, "Rivera")
        self.assertFalse(by_uin["IND-NSR-0001"].already_exists)
        self.assertTrue(by_uin["IND-NSR-0001"].selected)

        self.assertEqual(by_uin["IND-NSR-0002"].status, "matched")
        self.assertTrue(by_uin["IND-NSR-0002"].already_exists)
        self.assertEqual(by_uin["IND-NSR-0002"].existing_partner_id, existing_partner)
        self.assertFalse(by_uin["IND-NSR-0002"].selected)  # not pre-selected

        self.assertEqual(by_uin["IND-NSR-0003"].status, "not_found")
        self.assertFalse(by_uin["IND-NSR-0003"].selected)

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_social_service.OpenG2PDCIClient")
    def test_preview_captures_service_error_per_subject(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.search.side_effect = RuntimeError("HTTP 500 from OpenG2P")
        mock_client_class.return_value = mock_client

        wiz = self._wizard(range_start=1, range_end=2)
        wiz.action_preview()

        for line in wiz.preview_line_ids:
            self.assertEqual(line.status, "error")
            self.assertIn("HTTP 500", line.error_message)
            self.assertFalse(line.selected)

    # ------------------------------------------------------------------
    # Import step
    # ------------------------------------------------------------------

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_social_service.OpenG2PDCIClient")
    def test_import_creates_partners_and_reg_ids_for_selected_only(self, mock_client_class):
        def search(**kwargs):
            v = kwargs.get("query_value")
            payloads = {
                "IND-NSR-0001": _payload("Alex", "Rivera"),
                "IND-NSR-0002": _payload("Priya", "Rivera", sex="female"),
            }
            if v in payloads:
                return _sr_response([payloads[v]])
            return _not_found_response()

        mock_client = MagicMock()
        mock_client.search.side_effect = search
        mock_client_class.return_value = mock_client

        wiz = self._wizard(range_start=1, range_end=2)
        wiz.action_preview()

        # Deselect IND-NSR-0002 — only 0001 should import
        for line in wiz.preview_line_ids:
            if line.uin == "IND-NSR-0002":
                line.selected = False

        wiz.action_import()

        self.assertEqual(wiz.state, "done")
        regs = self.env["spp.registry.id"].search([("value", "=", "IND-NSR-0001")])
        self.assertEqual(len(regs), 1)
        partner = regs.partner_id
        # spp_registry auto-computes individual name as
        # "FAMILY_NAME, GIVEN_NAME" (uppercased) — assert the canonical
        # form, not the raw "Alex Rivera" we passed in.
        self.assertEqual(partner.name, "RIVERA, ALEX")
        self.assertEqual(partner.given_name, "Alex")
        self.assertEqual(partner.family_name, "Rivera")
        self.assertTrue(partner.is_registrant)
        self.assertFalse(partner.is_group)

        # 0002 was deselected — no partner created
        self.assertFalse(self.env["spp.registry.id"].search([("value", "=", "IND-NSR-0002")]))

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_social_service.OpenG2PDCIClient")
    def test_import_skips_already_existing_partners(self, mock_client_class):
        existing = self.env["res.partner"].create({"name": "Existing", "is_registrant": True, "is_group": False})
        self.env["spp.registry.id"].create(
            {
                "partner_id": existing.id,
                "id_type_id": self.uin_type.id,
                "value": "IND-NSR-0001",
            }
        )

        mock_client = MagicMock()
        mock_client.search.side_effect = lambda **k: _sr_response([_payload("Alex", "Rivera")])
        mock_client_class.return_value = mock_client

        wiz = self._wizard(range_start=1, range_end=1)
        wiz.action_preview()

        # Operator manually checks the box even though "already on SP"
        for line in wiz.preview_line_ids:
            line.selected = True

        wiz.action_import()

        # Still only one partner with this UIN — existing one untouched
        regs = self.env["spp.registry.id"].search([("value", "=", "IND-NSR-0001")])
        self.assertEqual(len(regs), 1)
        self.assertEqual(regs.partner_id, existing)
        self.assertEqual(existing.name, "Existing")  # not renamed

    @patch("odoo.addons.spp_dci_openg2p.services.openg2p_social_service.OpenG2PDCIClient")
    def test_import_auto_enrolls_into_program_when_set(self, mock_client_class):
        program = self.env["spp.program"].search([], limit=1)
        if not program:
            self.skipTest("no spp.program in this environment")

        mock_client = MagicMock()
        mock_client.search.side_effect = lambda **k: _sr_response([_payload("Alex", "Rivera")])
        mock_client_class.return_value = mock_client

        wiz = self._wizard(
            range_start=1,
            range_end=1,
            auto_enroll_program_id=program.id,
        )
        wiz.action_preview()
        wiz.action_import()

        regs = self.env["spp.registry.id"].search([("value", "=", "IND-NSR-0001")])
        mems = self.env["spp.program.membership"].search(
            [("partner_id", "=", regs.partner_id.id), ("program_id", "=", program.id)]
        )
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems.state, "draft")

    def test_back_to_configure_clears_preview(self):
        wiz = self._wizard()
        # Skip the live preview — fabricate one line manually
        self.env["spp.dci.sr.import.wizard.line"].create(
            {
                "wizard_id": wiz.id,
                "uin": "IND-NSR-0001",
                "status": "matched",
                "given_name": "Alex",
                "surname": "Rivera",
                "selected": True,
            }
        )
        wiz.state = "preview"

        wiz.action_back_to_configure()

        self.assertEqual(wiz.state, "configure")
        self.assertFalse(wiz.preview_line_ids)
