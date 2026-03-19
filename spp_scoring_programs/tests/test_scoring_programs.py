from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestScoringPrograms(TransactionCase):
    """Test cases for scoring-programs integration."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ScoringThreshold = cls.env["spp.scoring.threshold"]
        cls.ScoringEngine = cls.env["spp.scoring.engine"]
        cls.Partner = cls.env["res.partner"]

        # Check if spp_programs is installed
        cls.Program = cls.env.get("spp.program")

        # Create a scoring model
        cls.scoring_model = cls.ScoringModel.create(
            {
                "name": "Program Eligibility Model",
                "code": "PROGRAM_ELIG",
                "is_active": True,
            }
        )
        cls.ScoringIndicator.create(
            {
                "model_id": cls.scoring_model.id,
                "name": "Base Score",
                "code": "BASE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
                "min_score": 0,
                "max_score": 100,
            }
        )
        cls.ScoringThreshold.create(
            [
                {
                    "model_id": cls.scoring_model.id,
                    "name": "Eligible",
                    "min_score": 0,
                    "max_score": 50,
                    "classification_code": "ELIGIBLE",
                    "classification_label": "Eligible",
                },
                {
                    "model_id": cls.scoring_model.id,
                    "name": "Not Eligible",
                    "min_score": 50.01,
                    "max_score": 100,
                    "classification_code": "NOT_ELIGIBLE",
                    "classification_label": "Not Eligible",
                },
            ]
        )

    def test_scoring_model_program_relationship(self):
        """Test that scoring models can be linked to programs."""
        if not self.Program:
            self.skipTest("spp_programs module not installed")

        # Check that program_ids field exists
        self.assertTrue(hasattr(self.scoring_model, "program_ids"))
        self.assertEqual(self.scoring_model.program_count, 0)

    def test_program_scoring_configuration(self):
        """Test that programs can configure scoring settings."""
        if not self.Program:
            self.skipTest("spp_programs module not installed")

        # Check program has scoring fields
        program = self.Program.create(
            {
                "name": "Test Scoring Program",
            }
        )

        self.assertTrue(hasattr(program, "scoring_model_id"))
        self.assertTrue(hasattr(program, "is_use_scoring_eligibility"))
        self.assertTrue(hasattr(program, "eligibility_min_score"))
        self.assertTrue(hasattr(program, "eligibility_max_score"))
        self.assertTrue(hasattr(program, "eligibility_classifications"))

    def test_program_scoring_eligibility_check(self):
        """Test scoring-based eligibility checking."""
        if not self.Program:
            self.skipTest("spp_programs module not installed")

        program = self.Program.create(
            {
                "name": "Eligibility Test Program",
                "scoring_model_id": self.scoring_model.id,
                "is_use_scoring_eligibility": True,
                "eligibility_classifications": "ELIGIBLE",
            }
        )

        registrant = self.Partner.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
            }
        )

        # Check eligibility
        result = program.check_scoring_eligibility(registrant)

        self.assertIn("eligible", result)
        self.assertIn("score", result)
        self.assertIn("classification", result)

    def test_program_min_max_score_validation(self):
        """Test that min/max score validation works."""
        if not self.Program:
            self.skipTest("spp_programs module not installed")

        with self.assertRaises(ValidationError):
            self.Program.create(
                {
                    "name": "Invalid Score Range",
                    "scoring_model_id": self.scoring_model.id,
                    "is_use_scoring_eligibility": True,
                    "eligibility_min_score": 100,
                    "eligibility_max_score": 50,  # Invalid: min > max
                }
            )

    def test_pre_enrollment_hook_rejects_ineligible(self):
        """Test that pre-enrollment hook rejects ineligible registrants."""
        if not self.Program:
            self.skipTest("spp_programs module not installed")

        # Create program requiring ELIGIBLE classification
        program = self.Program.create(
            {
                "name": "Hook Test Program",
                "scoring_model_id": self.scoring_model.id,
                "is_use_scoring_eligibility": True,
                "eligibility_classifications": "NONEXISTENT_CLASS",  # Won't match
            }
        )

        registrant = self.Partner.create(
            {
                "name": "Test Registrant Hook",
                "is_registrant": True,
            }
        )

        # Pre-enrollment hook should raise ValidationError for ineligible
        with self.assertRaises(ValidationError) as cm:
            program._pre_enrollment_hook(registrant)

        self.assertIn("does not meet scoring eligibility", str(cm.exception))

    def test_pre_enrollment_hook_allows_eligible(self):
        """Test that pre-enrollment hook allows eligible registrants."""
        if not self.Program:
            self.skipTest("spp_programs module not installed")

        # Create program - scoring disabled, should pass
        program = self.Program.create(
            {
                "name": "No Scoring Program",
                "is_use_scoring_eligibility": False,
            }
        )

        registrant = self.Partner.create(
            {
                "name": "Test Registrant Eligible",
                "is_registrant": True,
            }
        )

        # Should not raise - no scoring eligibility check
        program._pre_enrollment_hook(registrant)

    def test_post_enrollment_hook_calculates_score(self):
        """Test that post-enrollment hook calculates score when configured."""
        if not self.Program:
            self.skipTest("spp_programs module not installed")

        Result = self.env["spp.scoring.result"]

        program = self.Program.create(
            {
                "name": "Auto Score Program",
                "scoring_model_id": self.scoring_model.id,
                "is_auto_score_on_enrollment": True,
            }
        )

        registrant = self.Partner.create(
            {
                "name": "Test Registrant AutoScore",
                "is_registrant": True,
            }
        )

        # Verify no score exists yet
        existing = Result.search(
            [
                ("registrant_id", "=", registrant.id),
                ("model_id", "=", self.scoring_model.id),
            ]
        )
        self.assertFalse(existing)

        # Call post-enrollment hook
        program._post_enrollment_hook(registrant)

        # Verify score was calculated
        new_score = Result.search(
            [
                ("registrant_id", "=", registrant.id),
                ("model_id", "=", self.scoring_model.id),
            ]
        )
        self.assertTrue(new_score)
        self.assertEqual(len(new_score), 1)

    def test_post_enrollment_hook_handles_errors_gracefully(self):
        """Test that post-enrollment hook doesn't fail on scoring errors."""
        if not self.Program:
            self.skipTest("spp_programs module not installed")

        # Create program with inactive scoring model (will cause error)
        inactive_model = self.ScoringModel.create(
            {
                "name": "Inactive Model",
                "code": "INACTIVE",
                "is_active": False,
            }
        )

        program = self.Program.create(
            {
                "name": "Error Handling Program",
                "scoring_model_id": inactive_model.id,
                "is_auto_score_on_enrollment": True,
            }
        )

        registrant = self.Partner.create(
            {
                "name": "Test Registrant Error",
                "is_registrant": True,
            }
        )

        # Should not raise - errors are caught and logged
        program._post_enrollment_hook(registrant)
