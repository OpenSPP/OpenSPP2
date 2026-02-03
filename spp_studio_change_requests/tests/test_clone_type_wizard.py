"""Tests for Clone CR Type Wizard functionality."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCloneCRTypeWizard(TransactionCase):
    """Test Clone CR Type Wizard functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.CRType = cls.env["spp.change.request.type"]
        cls.CloneWizard = cls.env["spp.studio.clone.cr.type.wizard"]

        # Create a cloneable CR type for testing
        cls.cloneable_type = cls.CRType.create(
            {
                "name": "Cloneable Test Type",
                "code": "cloneable_test",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
                "apply_strategy": "field_mapping",
                "is_studio_editable": True,
                "is_studio_cloneable": True,
                "is_system_type": False,
            }
        )

        # Create a non-cloneable CR type for testing
        cls.non_cloneable_type = cls.CRType.create(
            {
                "name": "Non-Cloneable Test Type",
                "code": "non_cloneable_test",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.add_member",
                "apply_strategy": "custom",
                "apply_model": "spp.cr.strategy.manual",
                "is_studio_editable": False,
                "is_studio_cloneable": False,
                "is_system_type": True,
                "locked_reason": "Requires custom Python logic",
            }
        )

    def test_01_clone_basic(self):
        """Test basic cloning of a CR type."""
        wizard = self.CloneWizard.create(
            {
                "source_type_id": self.cloneable_type.id,
                "new_name": "Cloned Type",
                "new_code": "cloned_type_001",
            }
        )

        result = wizard.action_clone()

        # Verify action result
        self.assertEqual(result["type"], "ir.actions.act_window")
        self.assertEqual(result["res_model"], "spp.change.request.type")
        self.assertTrue(result.get("res_id"))

        # Verify cloned type
        cloned = self.CRType.browse(result["res_id"])
        self.assertEqual(cloned.name, "Cloned Type")
        self.assertEqual(cloned.code, "cloned_type_001")
        self.assertEqual(cloned.target_type, self.cloneable_type.target_type)
        self.assertEqual(cloned.apply_strategy, self.cloneable_type.apply_strategy)
        self.assertTrue(cloned.is_studio_editable)
        self.assertTrue(cloned.is_studio_cloneable)
        self.assertFalse(cloned.is_system_type)
        self.assertEqual(cloned.cloned_from_id.id, self.cloneable_type.id)

    def test_02_clone_non_cloneable_fails(self):
        """Test that cloning a non-cloneable type fails."""
        with self.assertRaises(ValidationError):
            self.CloneWizard.create(
                {
                    "source_type_id": self.non_cloneable_type.id,
                    "new_name": "Should Fail",
                    "new_code": "should_fail_001",
                }
            )

    def test_03_clone_duplicate_code_fails(self):
        """Test that cloning with an existing code fails."""
        with self.assertRaises(ValidationError):
            self.CloneWizard.create(
                {
                    "source_type_id": self.cloneable_type.id,
                    "new_name": "New Name",
                    "new_code": "cloneable_test",  # Same as source
                }
            )

    def test_04_onchange_suggests_name_and_code(self):
        """Test onchange auto-suggests name and code."""
        wizard = self.CloneWizard.create(
            {
                "source_type_id": self.cloneable_type.id,
                "new_name": "Placeholder",
                "new_code": "placeholder",
            }
        )

        # Trigger onchange
        wizard._onchange_source_type_id()

        self.assertEqual(wizard.new_name, "Cloneable Test Type (Copy)")
        self.assertEqual(wizard.new_code, "cloneable_test_copy")

    def test_05_onchange_increments_code_for_uniqueness(self):
        """Test onchange increments code suffix if not unique."""
        # Create first clone
        self.CRType.create(
            {
                "name": "First Clone",
                "code": "cloneable_test_copy",
                "target_type": "individual",
                "detail_model": "spp.cr.detail.edit_individual",
            }
        )

        wizard = self.CloneWizard.create(
            {
                "source_type_id": self.cloneable_type.id,
                "new_name": "Placeholder",
                "new_code": "placeholder",
            }
        )

        # Trigger onchange
        wizard._onchange_source_type_id()

        # Should increment to _copy_2
        self.assertEqual(wizard.new_code, "cloneable_test_copy_2")

    def test_06_clone_copies_field_mappings(self):
        """Test that clone copies field mappings when option is enabled."""
        # Create field mappings on source type
        MappingModel = self.env["spp.change.request.type.mapping"]
        MappingModel.create(
            {
                "type_id": self.cloneable_type.id,
                "source_field": "phone",
                "target_field": "phone",
                "sequence": 10,
            }
        )
        MappingModel.create(
            {
                "type_id": self.cloneable_type.id,
                "source_field": "email",
                "target_field": "email",
                "sequence": 20,
            }
        )

        wizard = self.CloneWizard.create(
            {
                "source_type_id": self.cloneable_type.id,
                "new_name": "With Mappings",
                "new_code": "with_mappings_001",
                "copy_field_mappings": True,
            }
        )

        result = wizard.action_clone()
        cloned = self.CRType.browse(result["res_id"])

        self.assertEqual(len(cloned.apply_mapping_ids), 2)
        mapping_fields = cloned.apply_mapping_ids.mapped("source_field")
        self.assertIn("phone", mapping_fields)
        self.assertIn("email", mapping_fields)

    def test_07_clone_skips_field_mappings_when_disabled(self):
        """Test that clone skips field mappings when option is disabled."""
        wizard = self.CloneWizard.create(
            {
                "source_type_id": self.cloneable_type.id,
                "new_name": "Without Mappings",
                "new_code": "without_mappings_001",
                "copy_field_mappings": False,
            }
        )

        result = wizard.action_clone()
        cloned = self.CRType.browse(result["res_id"])

        self.assertEqual(len(cloned.apply_mapping_ids), 0)

    def test_08_code_is_unique_computed(self):
        """Test code_is_unique computed field."""
        wizard = self.CloneWizard.new(
            {
                "source_type_id": self.cloneable_type.id,
                "new_name": "Test",
                "new_code": "unique_code_xxx",
            }
        )
        wizard._compute_code_is_unique()
        self.assertTrue(wizard.code_is_unique)

        # Set to existing code
        wizard.new_code = "cloneable_test"
        wizard._compute_code_is_unique()
        self.assertFalse(wizard.code_is_unique)

    def test_09_source_is_cloneable_computed(self):
        """Test source_is_cloneable computed field."""
        wizard = self.CloneWizard.new(
            {
                "source_type_id": self.cloneable_type.id,
                "new_name": "Test",
                "new_code": "test_computed",
            }
        )
        wizard._compute_source_is_cloneable()
        self.assertTrue(wizard.source_is_cloneable)

        wizard.source_type_id = self.non_cloneable_type
        wizard._compute_source_is_cloneable()
        self.assertFalse(wizard.source_is_cloneable)

    def test_10_clone_without_source_fails(self):
        """Test that cloning without a source type fails."""
        # Use .new() to create unsaved record since source_type_id is required
        wizard = self.CloneWizard.new(
            {
                "new_name": "No Source",
                "new_code": "no_source_001",
            }
        )

        with self.assertRaises(UserError):
            wizard.action_clone()

    def test_11_cloned_type_description_includes_source(self):
        """Test that cloned type description mentions the source."""
        wizard = self.CloneWizard.create(
            {
                "source_type_id": self.cloneable_type.id,
                "new_name": "Check Description",
                "new_code": "check_desc_001",
            }
        )

        result = wizard.action_clone()
        cloned = self.CRType.browse(result["res_id"])

        self.assertIn("Cloned from:", cloned.description)
        self.assertIn(self.cloneable_type.name, cloned.description)
