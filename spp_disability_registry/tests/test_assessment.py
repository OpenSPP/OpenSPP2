from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from odoo import Command
from odoo.exceptions import ValidationError
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
