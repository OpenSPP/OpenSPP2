from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDisabilityConfigAndModels(TransactionCase):
    """Covers configuration settings, registrant eligibility/rollups, assistive
    devices, impairment lines and assessment device requests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.code = cls.env["spp.vocabulary.code"]
        cls.registrant = cls.env["res.partner"].create(
            {
                "name": "Coverage Adult",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=30),
            }
        )

    def _code(self, namespace):
        return self.code.search([("vocabulary_id.namespace_uri", "=", namespace)], limit=1)

    # === res.config.settings ===
    def test_config_settings_roundtrip(self):
        Settings = self.env["res.config.settings"]
        settings = Settings.create(
            {
                "disability_allow_proxy_wg_ss": False,
                "disability_display_impairment": False,
                "disability_require_support": False,
                "disability_allow_self_report_cfm": True,
                "disability_self_report_min_age": "10",
            }
        )
        settings.set_values()

        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("spp_disability_registry.allow_proxy_wg_ss"), "False")
        self.assertEqual(icp.get_param("spp_disability_registry.display_impairment"), "False")
        self.assertEqual(icp.get_param("spp_disability_registry.self_report_min_age"), "10")

        vals = settings.get_values()
        self.assertFalse(vals["disability_allow_proxy_wg_ss"])
        self.assertFalse(vals["disability_display_impairment"])
        self.assertTrue(vals["disability_require_wg"])  # untouched default stays True
        self.assertEqual(vals["disability_self_report_min_age"], "10")

    def test_config_self_report_min_age_out_of_range(self):
        Settings = self.env["res.config.settings"]
        settings = Settings.create(
            {
                "disability_allow_self_report_cfm": True,
                "disability_self_report_min_age": "3",
            }
        )
        with self.assertRaises(ValidationError):
            settings.set_values()

    # === Registrant eligibility + actions ===
    def test_can_create_assessment_by_age(self):
        # Adult with a birthdate can create.
        self.assertTrue(self.registrant.can_create_disability_assessment)

        # No birthdate -> blocked, with a reason.
        no_bd = self.env["res.partner"].create({"name": "No Birthdate", "is_registrant": True, "is_group": False})
        self.assertFalse(no_bd.can_create_disability_assessment)
        self.assertTrue(no_bd.disability_no_create_reason)

        # Under 2 -> blocked.
        baby = self.env["res.partner"].create(
            {
                "name": "Under Two",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=1),
            }
        )
        self.assertFalse(baby.can_create_disability_assessment)

    def test_registrant_action_helpers(self):
        self.assertEqual(self.registrant.action_view_disability_assessments()["res_model"], "spp.disability.assessment")
        self.assertEqual(self.registrant.action_view_assistive_devices()["res_model"], "spp.assistive.device")
        self.assertEqual(
            self.registrant.action_create_disability_assessment()["res_model"], "spp.disability.assessment"
        )

    # === Assistive device ===
    def test_assistive_device_name_onchange_and_rollup(self):
        device_type = self._code("urn:dci:cd:dr:04")
        if not device_type:
            self.skipTest("no device-type vocabulary codes present")
        device = self.env["spp.assistive.device"].create(
            {
                "registrant_id": self.registrant.id,
                "device_type_id": device_type.id,
                "status": "provided",
                "provision_date": date.today(),
            }
        )
        self.assertIn(self.registrant.name, device.name)
        self.assertIn(device_type.display, device.name)

        # Changing away from "provided" clears the provision date.
        device.status = "needed"
        device._onchange_status()
        self.assertFalse(device.provision_date)

        action = device.action_view_registrant()
        self.assertEqual(action["res_id"], self.registrant.id)

        self.registrant.invalidate_recordset()
        self.assertEqual(self.registrant.assistive_device_count, 1)
        self.assertTrue(self.registrant.has_unmet_device_need)

    # === Impairment line + assessment device request ===
    def test_impairment_and_device_request_on_assessment(self):
        assessment = self.env["spp.disability.assessment"].create(
            {"registrant_id": self.registrant.id, "assessment_date": date.today()}
        )
        imp_type = self._code("urn:dci:cd:dr:01")
        severity = self._code("urn:dci:cd:dr:02")
        device_type = self._code("urn:dci:cd:dr:04")
        if not (imp_type and severity and device_type):
            self.skipTest("disability vocabulary codes not present")

        impairment = self.env["spp.disability.impairment"].create(
            {
                "assessment_id": assessment.id,
                "impairment_type_id": imp_type.id,
                "severity_level_id": severity.id,
            }
        )
        self.assertEqual(impairment.severity_sequence, severity.sequence)

        request = self.env["spp.disability.assessment.device.request"].create(
            {"assessment_id": assessment.id, "device_type_id": device_type.id}
        )
        self.assertEqual(request.status, "needed")
