from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestChangeRequestType(TransactionCase):
    """Tests for spp.change.request.type model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr_type_model = cls.env["spp.change.request.type"]

    def test_create_type_with_valid_detail_model(self):
        """Test creating a CR type with a valid detail model."""
        cr_type = self.cr_type_model.create(
            {
                "name": "Test Type",
                "code": "test_type",
                "detail_model": "spp.cr.detail.add_member",
            }
        )
        self.assertTrue(cr_type.id)
        self.assertEqual(cr_type.code, "test_type")

    def test_create_type_with_invalid_detail_model(self):
        """Test that creating a CR type with invalid detail model fails."""
        with self.assertRaises(ValidationError):
            self.cr_type_model.create(
                {
                    "name": "Test Type",
                    "code": "test_invalid",
                    "detail_model": "invalid.model.name",
                }
            )

    def test_code_uniqueness(self):
        """Test that CR type codes must be unique."""
        # Use a unique code to avoid conflicts with other tests
        import uuid

        unique_code = f"unique_code_{uuid.uuid4().hex[:8]}"

        # Delete any existing change request type with this code (shouldn't exist, but be safe)
        existing = self.cr_type_model.search([("code", "=", unique_code)])
        if existing:
            existing.unlink()

        self.cr_type_model.create(
            {
                "name": "Type 1",
                "code": unique_code,
                "detail_model": "spp.cr.detail.add_member",
            }
        )
        with self.assertRaises(ValidationError):
            self.cr_type_model.create(
                {
                    "name": "Type 2",
                    "code": unique_code,
                    "detail_model": "spp.cr.detail.add_member",
                }
            )

    def test_custom_strategy_requires_apply_model(self):
        """Test that custom apply strategy requires apply_model."""
        with self.assertRaises(ValidationError):
            self.cr_type_model.create(
                {
                    "name": "Custom Type",
                    "code": "custom_no_model",
                    "detail_model": "spp.cr.detail.add_member",
                    "apply_strategy": "custom",
                    "apply_model": False,
                }
            )

    def test_get_apply_strategy_field_mapping(self):
        """Test get_apply_strategy returns field mapping strategy."""
        cr_type = self.cr_type_model.create(
            {
                "name": "Field Mapping Type",
                "code": "field_mapping_test",
                "detail_model": "spp.cr.detail.add_member",
                "apply_strategy": "field_mapping",
            }
        )
        strategy = cr_type.get_apply_strategy()
        self.assertEqual(strategy._name, "spp.cr.strategy.field_mapping")

    def test_get_apply_strategy_manual(self):
        """Test get_apply_strategy returns manual strategy."""
        cr_type = self.cr_type_model.create(
            {
                "name": "Manual Type",
                "code": "manual_test",
                "detail_model": "spp.cr.detail.add_member",
                "apply_strategy": "manual",
            }
        )
        strategy = cr_type.get_apply_strategy()
        self.assertEqual(strategy._name, "spp.cr.strategy.manual")
