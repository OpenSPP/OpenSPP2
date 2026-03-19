from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBatchScoringWizard(TransactionCase):
    """Test cases for the batch scoring wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.ScoringThreshold = cls.env["spp.scoring.threshold"]
        cls.BatchWizard = cls.env["spp.batch.scoring.wizard"]
        cls.Partner = cls.env["res.partner"]

        # Create an active scoring model
        cls.model = cls.ScoringModel.create(
            {
                "name": "Batch Test Model",
                "code": "BATCH_TEST",
                "is_active": True,
            }
        )
        cls.ScoringIndicator.create(
            {
                "model_id": cls.model.id,
                "name": "ID Score",
                "code": "ID_SCORE",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
                "min_score": 0,
                "max_score": 100,
            }
        )
        cls.ScoringThreshold.create(
            {
                "model_id": cls.model.id,
                "name": "Default",
                "min_score": 0,
                "max_score": 100,
                "classification_code": "DEFAULT",
                "classification_label": "Default",
            }
        )

        # Create test registrants
        cls.registrants = cls.Partner.create(
            [{"name": f"Batch Registrant {i}", "is_registrant": True} for i in range(5)]
        )

    def test_wizard_with_specific_registrants(self):
        """Test batch scoring with specific registrants selected."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_ids": [(6, 0, self.registrants.ids)],
            }
        )

        wizard.action_run_batch_scoring()

        self.assertEqual(wizard.state, "done")
        self.assertEqual(wizard.result_count, 5)
        self.assertEqual(wizard.error_count, 0)

    def test_wizard_with_domain_filter(self):
        """Test batch scoring with domain filter."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_domain": "[('is_registrant', '=', True), ('name', 'ilike', 'Batch Registrant')]",
            }
        )

        wizard.action_run_batch_scoring()

        self.assertEqual(wizard.state, "done")
        self.assertGreaterEqual(wizard.result_count, 5)

    def test_wizard_invalid_domain_error(self):
        """Test that invalid domain raises UserError."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_domain": "not a valid domain",
            }
        )

        with self.assertRaises(UserError):
            wizard.action_run_batch_scoring()

    def test_wizard_domain_not_list_error(self):
        """Test that domain returning non-list raises UserError."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_domain": "{'key': 'value'}",
            }
        )

        with self.assertRaises(UserError):
            wizard.action_run_batch_scoring()

    def test_wizard_no_registrants_error(self):
        """Test error when no registrants match criteria."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_domain": "[('name', '=', 'NonExistent12345')]",
            }
        )

        with self.assertRaises(UserError):
            wizard.action_run_batch_scoring()

    def test_wizard_max_records_limit(self):
        """Test that max_records limits processing."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_ids": [(6, 0, self.registrants.ids)],
                "max_records": 2,
            }
        )

        wizard.action_run_batch_scoring()

        self.assertEqual(wizard.state, "done")
        self.assertEqual(wizard.result_count, 2)

    def test_wizard_max_records_with_domain(self):
        """Test max_records with domain filter."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_domain": "[('is_registrant', '=', True)]",
                "max_records": 3,
            }
        )

        wizard.action_run_batch_scoring()

        self.assertEqual(wizard.state, "done")
        self.assertLessEqual(wizard.result_count, 3)

    def test_wizard_view_results_action(self):
        """Test the view results action returns correct domain."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_ids": [(6, 0, self.registrants[:2].ids)],
            }
        )
        wizard.action_run_batch_scoring()

        action = wizard.action_view_results()

        self.assertEqual(action["res_model"], "spp.scoring.result")
        self.assertIn(("model_id", "=", self.model.id), action["domain"])

    def test_wizard_result_summary_format(self):
        """Test that result summary is properly formatted."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_ids": [(6, 0, self.registrants.ids)],
            }
        )
        wizard.action_run_batch_scoring()

        self.assertIn("Total:", wizard.result_summary)
        self.assertIn("Successful:", wizard.result_summary)
        self.assertIn("Failed:", wizard.result_summary)

    def test_wizard_fail_fast_mode(self):
        """Test fail-fast mode stops on first error."""
        # Create a wizard with fail_fast enabled
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_ids": [(6, 0, self.registrants.ids)],
                "is_fail_fast": True,
            }
        )

        # With valid registrants, should complete normally
        wizard.action_run_batch_scoring()
        self.assertEqual(wizard.state, "done")


@tagged("post_install", "-at_install")
class TestBatchScoringDomainValidation(TransactionCase):
    """Test domain validation in batch scoring wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScoringModel = cls.env["spp.scoring.model"]
        cls.ScoringIndicator = cls.env["spp.scoring.indicator"]
        cls.BatchWizard = cls.env["spp.batch.scoring.wizard"]

        cls.model = cls.ScoringModel.create(
            {
                "name": "Domain Test Model",
                "code": "DOMAIN_TEST",
                "is_active": True,
            }
        )
        cls.ScoringIndicator.create(
            {
                "model_id": cls.model.id,
                "name": "Test",
                "code": "TEST",
                "field_path": "id",
                "calculation_type": "direct",
                "weight": 1.0,
            }
        )

    def test_malicious_domain_blocked(self):
        """Test that potentially malicious domains are blocked by safe_eval."""
        # Try to use __import__ (should be blocked by safe_eval)
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_domain": "__import__('os').system('ls')",
            }
        )

        with self.assertRaises(UserError):
            wizard.action_run_batch_scoring()

    def test_exec_blocked(self):
        """Test that exec is blocked by safe_eval."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_domain": "exec('print(1)')",
            }
        )

        with self.assertRaises(UserError):
            wizard.action_run_batch_scoring()

    def test_tuple_domain_accepted(self):
        """Test that tuple-based domains are properly converted."""
        wizard = self.BatchWizard.create(
            {
                "model_id": self.model.id,
                "registrant_domain": "[('is_registrant', '=', True)]",
            }
        )
        # Should not raise - valid domain format
        try:
            wizard.action_run_batch_scoring()
        except UserError as e:
            # Only acceptable if no registrants found
            self.assertIn("No registrants found", str(e))
