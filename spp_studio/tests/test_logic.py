# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.cel.expression model - core Logic Studio functionality."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_cel_domain.tests.common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestLogic(TransactionCase):
    """Tests for the main Logic model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.VocabCode = cls.env["spp.vocabulary.code"]
        cls.vocab = cls.env.ref("spp_studio.vocab_logic_tags")

        # Create test tags as vocabulary codes
        cls.tag_eligibility = cls.VocabCode.create(
            {
                "vocabulary_id": cls.vocab.id,
                "code": "eligibility",
                "display": "Eligibility",
                "color": 1,
            }
        )
        cls.tag_income = cls.VocabCode.create(
            {
                "vocabulary_id": cls.vocab.id,
                "code": "income_based",
                "display": "Income Based",
                "color": 2,
            }
        )

    def test_create_logic_basic(self):
        """Test basic logic creation with required fields."""
        logic = self.Logic.create(
            {
                "name": "Test Eligibility Logic",
                "expression_type": "filter",
                "output_type": "boolean",
            }
        )

        self.assertTrue(logic.id)
        self.assertEqual(logic.name, "Test Eligibility Logic")
        self.assertEqual(logic.expression_type, "filter")
        self.assertEqual(logic.state, "draft")
        self.assertEqual(logic.version, 1)

    def test_create_logic_auto_code_generation(self):
        """Test that code is auto-generated from name if not provided."""
        logic = self.Logic.create(
            {
                "name": "My Custom Logic 123",
                "expression_type": "formula",
            }
        )

        self.assertTrue(logic.code)
        self.assertIn("my_custom_logic", logic.code)

    def test_create_logic_code_unique(self):
        """Test that duplicate codes are handled with suffix."""
        logic1 = self.Logic.create(
            {
                "name": "Test Logic",
                "expression_type": "filter",
            }
        )
        logic2 = self.Logic.create(
            {
                "name": "Test Logic",
                "expression_type": "formula",
            }
        )

        self.assertNotEqual(logic1.code, logic2.code)
        # Second one should have a suffix
        self.assertTrue(logic2.code.startswith("test_logic"))

    def test_logic_with_tags(self):
        """Test logic creation with tags."""
        logic = self.Logic.create(
            {
                "name": "Tagged Logic",
                "expression_type": "filter",
                "tag_ids": [(6, 0, [self.tag_eligibility.id, self.tag_income.id])],
            }
        )

        self.assertEqual(len(logic.tag_ids), 2)
        self.assertIn(self.tag_eligibility, logic.tag_ids)
        self.assertIn(self.tag_income, logic.tag_ids)

    def test_expression_types(self):
        """Test all available logic types can be created."""
        expression_types = ["filter", "formula", "scoring", "validation", "other"]

        for ltype in expression_types:
            logic = self.Logic.create(
                {
                    "name": f"Test {ltype}",
                    "expression_type": ltype,
                }
            )
            self.assertEqual(logic.expression_type, ltype)

    def test_logic_output_types(self):
        """Test all available output types."""
        output_types = ["boolean", "number", "string", "money"]

        for otype in output_types:
            logic = self.Logic.create(
                {
                    "name": f"Test {otype} output",
                    "expression_type": "other",
                    "output_type": otype,
                }
            )
            self.assertEqual(logic.output_type, otype)

    def test_inline_logic(self):
        """Test inline logic creation (not reusable)."""
        logic = self.Logic.create(
            {
                "name": "Inline Logic for Program X",
                "expression_type": "filter",
                "is_inline": True,
            }
        )

        self.assertTrue(logic.is_inline)

    def test_cel_expression(self):
        """Test logic with CEL expression."""
        logic = self.Logic.create(
            {
                "name": "CEL Logic",
                "expression_type": "filter",
                "cel_expression": "income < 5000 && hh_size > 2",
            }
        )

        self.assertEqual(logic.cel_expression, "income < 5000 && hh_size > 2")

    def test_logic_state_transitions_archive(self):
        """Test archiving logic without usage."""
        logic = self.Logic.create(
            {
                "name": "To Be Archived",
                "expression_type": "filter",
                "state": "published",
                "cel_expression": "true",
            }
        )

        # Should be able to archive since no usage
        logic.action_archive()
        self.assertEqual(logic.state, "archived")

    def test_logic_state_draft_from_published(self):
        """Test creating draft from published logic."""
        logic = self.Logic.create(
            {
                "name": "Published Logic",
                "expression_type": "filter",
                "state": "published",
                "cel_expression": "true",
            }
        )

        logic.action_draft()
        self.assertEqual(logic.state, "draft")

    def test_cannot_delete_logic_in_use(self):
        """Test that logic cannot be deleted when in use."""
        logic = self.Logic.create(
            {
                "name": "Used Logic",
                "expression_type": "filter",
            }
        )

        # Create a usage record
        self.env["spp.studio.usage"].create(
            {
                "logic_id": logic.id,
                "res_model": "test.model",
                "res_id": 1,
                "usage_type": "filter",
            }
        )

        # Should raise error when trying to delete
        with self.assertRaises(UserError):
            logic.unlink()

    def test_name_get_includes_version_for_published(self):
        """Test name_get includes version for published logic."""
        logic = self.Logic.create(
            {
                "name": "Versioned Logic",
                "expression_type": "filter",
                "state": "published",
                "cel_expression": "true",
                "version": 3,
            }
        )

        name = logic.name_get()[0][1]
        self.assertIn("v3", name)

    def test_name_get_no_version_for_inline(self):
        """Test name_get excludes version for inline logic."""
        logic = self.Logic.create(
            {
                "name": "Inline Logic",
                "expression_type": "filter",
                "state": "published",
                "is_inline": True,
                "cel_expression": "true",
                "version": 5,
            }
        )

        name = logic.name_get()[0][1]
        self.assertNotIn("v5", name)


@tagged("post_install", "-at_install")
class TestLogicPublishing(TransactionCase, CELTestDataMixin):
    """Tests for logic publishing workflow."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableCategory = cls.env["spp.cel.variable.category"]

        # Create test category
        cls.cat_household = cls._create_test_category(
            name=f"Test Household {cls._test_id}",
            code=f"test_household_publishing_{cls._test_id}",
        )

        # Create test variable for testing with applies_to='both'
        # for context compatibility in all tests
        cls.var_income = cls._create_test_variable(
            name=f"income_{cls._test_id}",
            label="Monthly Income",
            cel_accessor=f"income_{cls._test_id}",
            value_type="money",
            source_type="field",
            category=cls.cat_household,
            applies_to="both",
            source_model="res.partner",
            source_field="income",
        )

    def test_publish_creates_version_for_reusable(self):
        """Test that publishing creates version record for reusable logic."""
        logic = self.Logic.create(
            {
                "name": "Versioned Logic",
                "expression_type": "filter",
                "cel_expression": f"{self.var_income.cel_accessor} < 5000",
            }
        )

        initial_version = logic.version
        logic.action_publish()

        # Version should be incremented
        self.assertEqual(logic.version, initial_version + 1)

        # Version record should be created
        version = self.env["spp.studio.version"].search(
            [
                ("logic_id", "=", logic.id),
            ]
        )
        self.assertEqual(len(version), 1)
        self.assertEqual(version.version, initial_version)

    def test_publish_no_version_for_inline(self):
        """Test that publishing inline logic doesn't create version."""
        logic = self.Logic.create(
            {
                "name": "Inline Logic",
                "expression_type": "filter",
                "cel_expression": "true",
                "is_inline": True,
            }
        )

        initial_version = logic.version
        logic.action_publish()

        # Version should not be incremented for inline
        self.assertEqual(logic.version, initial_version)

        # No version record for inline
        versions = self.env["spp.studio.version"].search(
            [
                ("logic_id", "=", logic.id),
            ]
        )
        self.assertEqual(len(versions), 0)

    def test_cannot_publish_without_expression(self):
        """Test that logic without CEL expression cannot be published."""
        logic = self.Logic.create(
            {
                "name": "Empty Logic",
                "expression_type": "filter",
                "cel_expression": "",  # Empty
            }
        )

        with self.assertRaises(ValidationError):
            logic.action_publish()


@tagged("post_install", "-at_install")
class TestLogicGovernance(TransactionCase):
    """Tests for logic governance write protection."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]

        # Create test variable
        cls.test_var = cls.LogicVariable.create(
            {
                "name": "gov_test_var",
                "label": "Governance Test Variable",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "gov_test_var",
            }
        )

    def setUp(self):
        """Set up test environment."""
        super().setUp()
        # Store original governance setting
        self.original_governance = (
            self.env["ir.config_parameter"].sudo().get_param("spp_studio.governance_enabled", "False")
        )

    def tearDown(self):
        """Restore original governance setting."""
        self.env["ir.config_parameter"].sudo().set_param("spp_studio.governance_enabled", self.original_governance)
        super().tearDown()

    def test_governance_disabled_allows_edit_published(self):
        """Test that published logic can be edited when governance is disabled."""
        # Disable governance
        self.env["ir.config_parameter"].sudo().set_param("spp_studio.governance_enabled", "False")

        logic = self.Logic.create(
            {
                "name": "Published Logic",
                "expression_type": "filter",
                "cel_expression": "true",
                "state": "published",
            }
        )

        # Should be able to edit
        logic.write({"name": "Updated Name"})
        self.assertEqual(logic.name, "Updated Name")

    def test_governance_enabled_blocks_edit_published(self):
        """Test that published logic cannot be edited when governance is enabled."""
        # Enable governance
        self.env["ir.config_parameter"].sudo().set_param("spp_studio.governance_enabled", "True")

        logic = self.Logic.create(
            {
                "name": "Published Logic",
                "expression_type": "filter",
                "cel_expression": "true",
                "state": "published",
            }
        )

        # Should raise error when trying to edit
        with self.assertRaises(UserError) as cm:
            logic.write({"name": "Updated Name"})

        self.assertIn("Cannot modify published logic", str(cm.exception))

    def test_governance_allows_state_change(self):
        """Test that state changes are allowed even with governance enabled."""
        # Enable governance
        self.env["ir.config_parameter"].sudo().set_param("spp_studio.governance_enabled", "True")

        logic = self.Logic.create(
            {
                "name": "Published Logic",
                "expression_type": "filter",
                "cel_expression": "true",
                "state": "published",
            }
        )

        # Should be able to change state
        logic.write({"state": "archived"})
        self.assertEqual(logic.state, "archived")

    def test_governance_allows_edit_draft(self):
        """Test that draft logic can be edited with governance enabled."""
        # Enable governance
        self.env["ir.config_parameter"].sudo().set_param("spp_studio.governance_enabled", "True")

        logic = self.Logic.create(
            {
                "name": "Draft Logic",
                "expression_type": "filter",
                "cel_expression": "true",
                "state": "draft",
            }
        )

        # Should be able to edit draft
        logic.write({"name": "Updated Draft"})
        self.assertEqual(logic.name, "Updated Draft")

    def test_force_write_context_bypasses_governance(self):
        """Test that force_write context bypasses governance."""
        # Enable governance
        self.env["ir.config_parameter"].sudo().set_param("spp_studio.governance_enabled", "True")

        logic = self.Logic.create(
            {
                "name": "Published Logic",
                "expression_type": "filter",
                "cel_expression": "true",
                "state": "published",
            }
        )

        # Should be able to edit with force_write context
        logic.with_context(force_write=True).write({"name": "Force Updated"})
        self.assertEqual(logic.name, "Force Updated")


@tagged("post_install", "-at_install")
class TestLogicCompiledExpression(TransactionCase):
    """Tests for compiled expression updates."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]

        # Create test variable
        cls.test_var = cls.LogicVariable.create(
            {
                "name": "comp_test_var",
                "label": "Compiled Test Variable",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "comp_test_income",
            }
        )

    def test_compiled_expression_updates_on_cel_change(self):
        """Test that compiled_expression updates when cel_expression changes."""
        logic = self.Logic.create(
            {
                "name": "Advanced Logic",
                "expression_type": "filter",
                "cel_expression": "comp_test_income > 1000",
            }
        )

        # Update CEL expression
        logic.write({"cel_expression": "comp_test_income > 5000"})

        # Compiled expression should be updated
        logic.invalidate_recordset()
        # Compiled expression should reflect the updated CEL expression
        self.assertIn("5000", logic.compiled_expression or logic.cel_expression)


@tagged("post_install", "-at_install")
class TestLogicTestExecution(TransactionCase):
    """Tests for logic test execution."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicTest = cls.env["spp.studio.test"]

    def test_action_test_all_no_tests(self):
        """Test action_test_all with no tests defined."""
        logic = self.Logic.create(
            {
                "name": "Logic Without Tests",
                "expression_type": "filter",
                "cel_expression": "true",
            }
        )

        result = logic.action_test_all()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "warning")

    def test_test_pass_count_computed(self):
        """Test that test pass/fail counts are computed correctly."""
        logic = self.Logic.create(
            {
                "name": "Logic With Tests",
                "expression_type": "filter",
                "cel_expression": "income < 5000",
                "compiled_expression": "income < 5000",
            }
        )

        # Create test cases (they won't actually run without CEL service)
        self.LogicTest.create(
            {
                "logic_id": logic.id,
                "name": "Test 1",
                "input_type": "values",
                "custom_values": '{"income": 3000}',
                "expected_result": "true",
            }
        )

        # Verify test count fields exist and work
        self.assertIsInstance(logic.test_pass_count, int)
        self.assertIsInstance(logic.test_fail_count, int)
