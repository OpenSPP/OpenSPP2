"""Tests for Studio deactivation wizard."""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestDeactivateWizard(TransactionCase):
    """Test cases for spp.studio.deactivate.wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Wizard = cls.env["spp.studio.deactivate.wizard"]
        # Create a test partner to use for testing
        cls.test_partner = cls.env["res.partner"].create({"name": "Test Partner"})

    def test_wizard_creation_with_context(self):
        """Test wizard can be created with context values."""
        wizard = self.Wizard.with_context(
            default_config_model="res.partner",
            default_config_id=self.test_partner.id,
            default_impact_message="Test impact message with 100 records",
        ).create({})

        self.assertEqual(wizard.config_model, "res.partner")
        self.assertEqual(wizard.config_id, self.test_partner.id)
        self.assertEqual(wizard.impact_message, "Test impact message with 100 records")

    def test_wizard_extracts_record_count(self):
        """Test wizard correctly extracts record count from impact message."""
        wizard = self.Wizard.with_context(
            default_config_model="res.partner",
            default_config_id=self.test_partner.id,
            default_impact_message="This field contains data in 1,247 records.",
        ).create({})

        # Should extract 1,247 as 1247
        self.assertEqual(wizard.record_count, 1247)

    def test_wizard_extracts_record_count_without_commas(self):
        """Test wizard extracts record count without commas."""
        wizard = self.Wizard.with_context(
            default_config_model="res.partner",
            default_config_id=self.test_partner.id,
            default_impact_message="This event type is used by 5 event records.",
        ).create({})

        self.assertEqual(wizard.record_count, 5)

    def test_wizard_extracts_zero_count_when_no_match(self):
        """Test wizard returns 0 when no count in message."""
        wizard = self.Wizard.with_context(
            default_config_model="res.partner",
            default_config_id=self.test_partner.id,
            default_impact_message="No impact detected.",
        ).create({})

        self.assertEqual(wizard.record_count, 0)

    def test_wizard_cancel_action(self):
        """Test cancel action closes wizard."""
        wizard = self.Wizard.with_context(
            default_config_model="res.partner",
            default_config_id=self.test_partner.id,
            default_impact_message="Test message",
        ).create({})

        result = wizard.action_cancel()
        self.assertEqual(result["type"], "ir.actions.act_window_close")

    def test_wizard_confirm_with_invalid_model_raises_error(self):
        """Test confirming with invalid model raises error."""
        wizard = self.Wizard.create(
            {
                "config_model": "invalid.model.name",
                "config_id": 999,
                "impact_message": "Test",
            }
        )

        with self.assertRaises(UserError):
            wizard.action_confirm_deactivate()

    def test_wizard_confirm_with_nonexistent_record_raises_error(self):
        """Test confirming with non-existent record raises error."""
        wizard = self.Wizard.create(
            {
                "config_model": "res.partner",
                "config_id": 999999,  # Non-existent ID
                "impact_message": "Test",
            }
        )

        with self.assertRaises(UserError):
            wizard.action_confirm_deactivate()

    def test_config_info_computed(self):
        """Test config_name and config_type are computed correctly."""
        wizard = self.Wizard.with_context(
            default_config_model="res.partner",
            default_config_id=self.test_partner.id,
            default_impact_message="Test with 50 records",
        ).create({})

        # config_name should be computed from the partner record
        self.assertEqual(wizard.config_name, "Test Partner")
        # config_type should be computed
        self.assertTrue(wizard.config_type)
        # record_count should be extracted from message
        self.assertEqual(wizard.record_count, 50)
