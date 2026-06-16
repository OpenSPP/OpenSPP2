from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDisabilityAssessment(TransactionCase):
    """Test cases for disability assessment functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test users with appropriate groups
        cls.user_assessor = cls.env["res.users"].create(
            {
                "name": "Test Assessor",
                "login": "test_assessor",
                "email": "assessor@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("spp_disability_registry.group_disability_assessor").id),
                ],
            }
        )

        cls.user_validator = cls.env["res.users"].create(
            {
                "name": "Test Validator",
                "login": "test_validator",
                "email": "validator@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("spp_disability_registry.group_disability_validator").id),
                ],
            }
        )

        cls.user_manager = cls.env["res.users"].create(
            {
                "name": "Test Manager",
                "login": "test_disability_manager",
                "email": "disability_manager@test.com",
                "group_ids": [
                    Command.link(cls.env.ref("spp_disability_registry.group_disability_manager").id),
                ],
            }
        )

        # Create test registrant (adult - 35 years old)
        cls.adult_registrant = cls.env["res.partner"].create(
            {
                "name": "Test Adult Person",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=35),
            }
        )

        # Create test registrant (child - 10 years old)
        cls.child_registrant = cls.env["res.partner"].create(
            {
                "name": "Test Child Person",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=10),
            }
        )

        # Create test registrant (young child - 3 years old)
        cls.young_child_registrant = cls.env["res.partner"].create(
            {
                "name": "Test Young Child",
                "is_registrant": True,
                "is_group": False,
                "birthdate": date.today() - relativedelta(years=3),
            }
        )

        # Get severity vocabulary codes
        cls.severity_mild = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:02"),
                ("code", "=", "mild"),
            ],
            limit=1,
        )
        cls.severity_severe = cls.env["spp.vocabulary.code"].search(
            [
                ("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:02"),
                ("code", "=", "severe"),
            ],
            limit=1,
        )

    # === Assessment Type Tests ===

    def test_assessment_type_computed_for_adult(self):
        """Test that assessment type is WG-SS for adults (18+)."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
            }
        )
        self.assertEqual(assessment.assessment_type, "wg_ss")
        self.assertEqual(assessment.age_at_assessment, 35)

    def test_assessment_type_computed_for_child(self):
        """Test that assessment type is CFM 5-17 for children 5-17."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.child_registrant.id,
                "assessment_date": date.today(),
            }
        )
        self.assertEqual(assessment.assessment_type, "cfm_5_17")
        self.assertEqual(assessment.age_at_assessment, 10)

    def test_assessment_type_computed_for_young_child(self):
        """Test that assessment type is CFM 2-4 for children 2-4."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.young_child_registrant.id,
                "assessment_date": date.today(),
            }
        )
        self.assertEqual(assessment.assessment_type, "cfm_2_4")
        self.assertEqual(assessment.age_at_assessment, 3)

    # === WG Disability Indicator Tests ===

    def test_no_disability_with_no_difficulty(self):
        """Test that no difficulty responses do not indicate disability."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "wg_seeing": "none",
                "wg_hearing": "none",
                "wg_walking": "none",
                "wg_remembering": "none",
                "wg_selfcare": "none",
                "wg_communicating": "none",
            }
        )
        self.assertFalse(assessment.has_disability)
        self.assertEqual(assessment.wg_domain_count, 0)

    def test_no_disability_with_some_difficulty(self):
        """Test that 'some difficulty' does not indicate disability per WG standard."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "wg_seeing": "some",
                "wg_hearing": "some",
                "wg_walking": "none",
                "wg_remembering": "none",
                "wg_selfcare": "none",
                "wg_communicating": "none",
            }
        )
        self.assertFalse(assessment.has_disability)
        self.assertEqual(assessment.wg_domain_count, 0)

    def test_disability_with_a_lot_of_difficulty(self):
        """Test that 'a lot of difficulty' indicates disability."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "wg_seeing": "a_lot",
                "wg_hearing": "none",
                "wg_walking": "none",
                "wg_remembering": "none",
                "wg_selfcare": "none",
                "wg_communicating": "none",
            }
        )
        self.assertTrue(assessment.has_disability)
        self.assertEqual(assessment.wg_domain_count, 1)

    def test_disability_with_cannot_do(self):
        """Test that 'cannot do at all' indicates disability."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "wg_seeing": "none",
                "wg_hearing": "cannot",
                "wg_walking": "none",
                "wg_remembering": "none",
                "wg_selfcare": "none",
                "wg_communicating": "none",
            }
        )
        self.assertTrue(assessment.has_disability)
        self.assertEqual(assessment.wg_domain_count, 1)

    def test_multiple_domains_with_difficulty(self):
        """Test counting multiple domains with severe difficulty."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "wg_seeing": "a_lot",
                "wg_hearing": "cannot",
                "wg_walking": "a_lot",
                "wg_remembering": "some",
                "wg_selfcare": "none",
                "wg_communicating": "cannot",
            }
        )
        self.assertTrue(assessment.has_disability)
        self.assertEqual(assessment.wg_domain_count, 4)

    # === Review Schedule Tests ===

    def test_next_review_date_mie(self):
        """Test next review date for MIE category (12 months)."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "review_category": "mie",
            }
        )
        expected_date = date.today() + relativedelta(months=12)
        self.assertEqual(assessment.next_review_date, expected_date)

    def test_next_review_date_mip(self):
        """Test next review date for MIP category (36 months)."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "review_category": "mip",
            }
        )
        expected_date = date.today() + relativedelta(months=36)
        self.assertEqual(assessment.next_review_date, expected_date)

    def test_next_review_date_mine(self):
        """Test next review date for MINE category (72 months)."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "review_category": "mine",
            }
        )
        expected_date = date.today() + relativedelta(months=72)
        self.assertEqual(assessment.next_review_date, expected_date)

    def test_no_review_date_without_category(self):
        """Test no review date when category is not set."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
            }
        )
        self.assertFalse(assessment.next_review_date)

    # === Name Computation Tests ===

    def test_assessment_name_computed(self):
        """Test that assessment name is computed correctly."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
            }
        )
        expected_name = f"{self.adult_registrant.name} - {date.today()}"
        self.assertEqual(assessment.name, expected_name)

    # === Proxy Response Tests ===

    def test_proxy_flag_set_for_child(self):
        """Proxy response flag is set automatically for child (CFM) assessments."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.child_registrant.id,
                "assessment_date": date.today(),
            }
        )
        # is_proxy_response is computed from the (age-derived) assessment type.
        self.assertIn(assessment.assessment_type, ("cfm_2_4", "cfm_5_17"))
        self.assertTrue(assessment.is_proxy_response)

    def test_questionnaire_required_before_submit(self):
        """A blank questionnaire blocks submission; completing it lifts the gate."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
            }
        )
        # WG-SS with no answers cannot be submitted.
        self.assertFalse(assessment.questionnaire_complete)
        with self.assertRaises(UserError):
            assessment.action_submit_for_approval()
        # Answering all six WG-SS domains makes it complete (even "no difficulty").
        assessment.write(
            {
                "wg_seeing": "none",
                "wg_hearing": "none",
                "wg_walking": "none",
                "wg_remembering": "none",
                "wg_selfcare": "none",
                "wg_communicating": "none",
            }
        )
        self.assertTrue(assessment.questionnaire_complete)

    def test_approval_propagates_to_registrant(self):
        """Approving updates the registrant's disability status (#1022).

        The approval mixin writes approval_state via raw SQL, so the registrant's
        computed status must be re-synced via the _on_approve hook.
        """
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "wg_seeing": "cannot",
                "wg_hearing": "none",
                "wg_walking": "none",
                "wg_remembering": "none",
                "wg_selfcare": "none",
                "wg_communicating": "none",
            }
        )
        self.assertTrue(assessment.has_disability)
        self.assertFalse(self.adult_registrant.has_disability)
        # Simulate a submitted record and approve via the mixin's SQL path.
        assessment.write({"approval_state": "pending"})
        assessment._do_approve()
        self.assertEqual(assessment.approval_state, "approved")
        self.assertTrue(self.adult_registrant.has_disability)
        self.assertEqual(self.adult_registrant.current_disability_assessment_id, assessment)

    # === OP#1068: tab config, impairment gate, device requests ===
    def _full_wg(self):
        return {
            "wg_seeing": "none",
            "wg_hearing": "none",
            "wg_walking": "none",
            "wg_remembering": "none",
            "wg_selfcare": "none",
            "wg_communicating": "none",
        }

    def test_assessment_complete_requires_impairment_answer(self):
        """With the default config (impairment + WG required), a complete
        questionnaire alone isn't enough — the impairment question must be
        answered (OP#1068)."""
        vals = {"registrant_id": self.adult_registrant.id, "assessment_date": date.today()}
        vals.update(self._full_wg())
        a = self.env["spp.disability.assessment"].create(vals)
        # Review schedule is required by default (OP#1068); set it so this test
        # isolates the impairment-answer gate.
        a.review_category = "mie"
        self.assertTrue(a.questionnaire_complete)
        self.assertFalse(a.assessment_complete)  # impairment question unanswered
        # "No" → impairment tab complete → assessment complete (support never gates).
        a.has_impairments_to_record = "no"
        self.assertTrue(a.impairment_tab_complete)
        self.assertTrue(a.assessment_complete)
        # "Yes" with no rows → incomplete again.
        a.has_impairments_to_record = "yes"
        self.assertFalse(a.impairment_tab_complete)
        self.assertFalse(a.assessment_complete)

    def test_gate_is_config_driven(self):
        """When WG/CFM is configured as not required, a blank questionnaire no
        longer blocks completion (OP#1068)."""
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("spp_disability_registry.require_wg", "False")
        a = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "has_impairments_to_record": "no",
                # Review schedule is required by default (OP#1068); set it so the
                # WG config gate is the only variable under test.
                "review_category": "mie",
            }
        )
        a.invalidate_recordset()
        self.assertFalse(a.questionnaire_complete)
        self.assertFalse(a.cfg_require_wg)
        self.assertTrue(a.assessment_complete)

    def test_review_schedule_gates_submission(self):
        """Review schedule is required by default (OP#1068): a complete WG +
        impairment answer is not enough until a review category is set, and
        disabling the requirement removes the gate."""
        vals = {
            "registrant_id": self.adult_registrant.id,
            "assessment_date": date.today(),
            "has_impairments_to_record": "no",
        }
        vals.update(self._full_wg())
        a = self.env["spp.disability.assessment"].create(vals)
        # impairment + WG satisfied, but review category missing -> blocked
        self.assertFalse(a.assessment_complete)
        a.review_category = "mie"
        self.assertTrue(a.assessment_complete)
        # When review is not required, a missing category no longer blocks.
        a.review_category = False
        self.env["ir.config_parameter"].sudo().set_param("spp_disability_registry.require_review", "False")
        a.invalidate_recordset()
        self.assertFalse(a.cfg_require_review)
        self.assertTrue(a.assessment_complete)

    def test_proxy_details_required_when_proxy(self):
        """When a proxy responded and proxy details are required (default),
        the assessment cannot be completed until the respondent and the
        relationship are recorded (OP#1053)."""
        vals = {
            "registrant_id": self.adult_registrant.id,
            "assessment_date": date.today(),
            "has_impairments_to_record": "no",
            "review_category": "mie",
        }
        vals.update(self._full_wg())
        a = self.env["spp.disability.assessment"].create(vals)
        self.assertTrue(a.assessment_complete)  # baseline complete, no proxy in use
        # Mark as a proxy response -> proxy details now required to complete.
        a.is_proxy_response = True
        self.assertTrue(a.cfg_require_proxy_details)
        self.assertFalse(a.assessment_complete)
        a.proxy_respondent_id = self.child_registrant.id
        a.proxy_relationship = "parent"
        self.assertTrue(a.assessment_complete)

    def test_impairment_severity_display(self):
        """Each impairment line renders its type with its own severity on a
        separate line in the overview display (OP#1068)."""
        imp_types = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:01")], limit=2
        )
        severities = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:02")], limit=2
        )
        self.assertTrue(len(imp_types) >= 2 and len(severities) >= 2, "need 2 impairment types + 2 severities")
        a = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "has_impairments_to_record": "yes",
                "impairment_line_ids": [
                    (0, 0, {"impairment_type_id": imp_types[0].id, "severity_level_id": severities[0].id}),
                    (0, 0, {"impairment_type_id": imp_types[1].id, "severity_level_id": severities[1].id}),
                ],
            }
        )
        html = str(a.impairment_severity_display or "")
        for code in (imp_types[0], imp_types[1], severities[0], severities[1]):
            self.assertIn(code.display, html)
        # One <div> per impairment line -> two separate lines.
        self.assertEqual(html.count("<div>"), 2)

    def test_device_requests_materialize_on_approve(self):
        """Support-Needs device requests become spp.assistive.device (status
        'needed') on the registrant when the assessment is approved (OP#1068)."""
        device_type = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id.namespace_uri", "=", "urn:dci:cd:dr:04")], limit=1
        )
        if not device_type:
            self.skipTest("no assistive-device type vocabulary code present")
        a = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
                "device_request_ids": [(0, 0, {"device_type_id": device_type.id})],
            }
        )
        Device = self.env["spp.assistive.device"]
        self.assertFalse(Device.search_count([("registrant_id", "=", self.adult_registrant.id)]))
        a.write({"approval_state": "pending"})
        a._do_approve()
        dev = Device.search([("registrant_id", "=", self.adult_registrant.id), ("device_type_id", "=", device_type.id)])
        self.assertEqual(len(dev), 1)
        self.assertEqual(dev.status, "needed")

    # === Date Validation Tests ===

    def test_future_assessment_date_rejected(self):
        """Test that future assessment dates are rejected."""
        with self.assertRaises(ValidationError):
            self.env["spp.disability.assessment"].create(
                {
                    "registrant_id": self.adult_registrant.id,
                    "assessment_date": date.today() + timedelta(days=1),
                }
            )

    def test_assessment_date_before_birthdate_rejected(self):
        """Test that assessment date before birthdate raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.env["spp.disability.assessment"].create(
                {
                    "registrant_id": self.adult_registrant.id,
                    "assessment_date": self.adult_registrant.birthdate - timedelta(days=1),
                }
            )

    # === Disability Indicator with Empty Responses ===

    def test_disability_with_empty_responses(self):
        """Test disability indicator when no WG responses are set."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
            }
        )
        self.assertFalse(assessment.has_disability)
        self.assertEqual(assessment.wg_domain_count, 0)

    # === Access Rights Tests ===

    def test_assessor_can_create_assessment(self):
        """Test that assessor can create assessments."""
        assessment = (
            self.env["spp.disability.assessment"]
            .with_user(self.user_assessor)
            .with_context(tracking_disable=True)
            .create(
                {
                    "registrant_id": self.adult_registrant.id,
                    "assessment_date": date.today(),
                }
            )
        )
        self.assertTrue(assessment.id)

    def test_assessor_can_edit_assessment(self):
        """Test that assessor can edit assessments."""
        assessment = (
            self.env["spp.disability.assessment"]
            .with_user(self.user_assessor)
            .with_context(tracking_disable=True)
            .create(
                {
                    "registrant_id": self.adult_registrant.id,
                    "assessment_date": date.today(),
                }
            )
        )
        assessment.with_user(self.user_assessor).write({"wg_seeing": "some"})
        self.assertEqual(assessment.wg_seeing, "some")

    def test_manager_can_delete_assessment(self):
        """Test that manager can delete assessments."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
            }
        )
        assessment_id = assessment.id
        assessment.with_user(self.user_manager).unlink()
        deleted = self.env["spp.disability.assessment"].search([("id", "=", assessment_id)])
        self.assertFalse(deleted)

    # === View Registrant Action Test ===

    def test_action_view_registrant(self):
        """Test action to view registrant from assessment."""
        assessment = self.env["spp.disability.assessment"].create(
            {
                "registrant_id": self.adult_registrant.id,
                "assessment_date": date.today(),
            }
        )
        action = assessment.action_view_registrant()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "res.partner")
        self.assertEqual(action["res_id"], self.adult_registrant.id)
