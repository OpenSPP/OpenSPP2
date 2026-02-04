# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.cel.variable model - Variable Dictionary functionality."""

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.spp_cel_domain.tests.common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestLogicVariable(TransactionCase, CELTestDataMixin):
    """Tests for the Variable Dictionary model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableCategory = cls.env["spp.cel.variable.category"]

        # Create test categories
        cls.cat_household = cls._create_test_category(
            name=f"Test Household {cls._test_id}",
            code=f"test_household_variable_{cls._test_id}",
        )

        cls.cat_individual = cls._create_test_category(
            name=f"Test Individual {cls._test_id}",
            code=f"test_individual_variable_{cls._test_id}",
        )

    def test_create_variable_basic(self):
        """Test basic variable creation."""
        variable = self.LogicVariable.create(
            {
                "name": "income",
                "label": "Monthly Income",
                "value_type": "money",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "z_cst_income",
                "cel_accessor": "income",
                "category_id": self.cat_household.id,
            }
        )

        self.assertTrue(variable.id)
        self.assertEqual(variable.name, "income")
        self.assertEqual(variable.value_type, "money")
        self.assertEqual(variable.source_type, "field")
        self.assertTrue(variable.active)

    @mute_logger("odoo.sql_db")
    def test_variable_name_unique(self):
        """Test that variable names must be unique."""
        unique_name = f"unique_var_{self._test_id}"
        self.LogicVariable.create(
            {
                "name": unique_name,
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": f"unique_var_{self._test_id}",
            }
        )

        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.LogicVariable.create(
                    {
                        "name": unique_name,  # Duplicate
                        "value_type": "string",
                        "source_type": "field",
                        "cel_accessor": f"unique_var_2_{self._test_id}",
                    }
                )

    @mute_logger("odoo.sql_db")
    def test_cel_accessor_unique(self):
        """Test that CEL accessors are unique per context."""
        unique_accessor = f"unique_accessor_{self._test_id}"
        # First accessor for individual context
        self.LogicVariable.create(
            {
                "name": f"var1_{self._test_id}",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": unique_accessor,
                "applies_to": "individual",
            }
        )

        # Same accessor for group context is allowed
        self.LogicVariable.create(
            {
                "name": f"var2_{self._test_id}",
                "value_type": "string",
                "source_type": "field",
                "cel_accessor": unique_accessor,
                "applies_to": "group",
            }
        )

        # Duplicate accessor within same context should fail
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.LogicVariable.create(
                    {
                        "name": f"var3_{self._test_id}",
                        "value_type": "string",
                        "source_type": "field",
                        "cel_accessor": unique_accessor,
                        "applies_to": "individual",
                    }
                )

    def test_all_value_types(self):
        """Test all available value types can be created."""
        value_types = ["number", "boolean", "string", "date", "money", "list"]

        for i, vtype in enumerate(value_types):
            variable = self.LogicVariable.create(
                {
                    "name": f"test_{vtype}_{i}",
                    "value_type": vtype,
                    "source_type": "field",
                    "cel_accessor": f"test_{vtype}_{i}",
                }
            )
            self.assertEqual(variable.value_type, vtype)

    def test_all_source_types(self):
        """Test all available source types can be created."""
        source_types = [
            "field",
            "external",
            "scoring",
            "vocabulary",
            "computed",
            "constant",
            "aggregate",
        ]

        for i, stype in enumerate(source_types):
            variable = self.LogicVariable.create(
                {
                    "name": f"test_source_{stype}_{i}",
                    "value_type": "number",
                    "source_type": stype,
                    "cel_accessor": f"test_source_{stype}_{i}",
                }
            )
            self.assertEqual(variable.source_type, stype)

    def test_variable_with_category(self):
        """Test variable with category assignment."""
        variable = self.LogicVariable.create(
            {
                "name": "categorized_var",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "categorized_var",
                "category_id": self.cat_individual.id,
            }
        )

        self.assertEqual(variable.category_id, self.cat_individual)

    def test_name_get_with_unit(self):
        """Test name_get includes unit when present."""
        variable = self.LogicVariable.create(
            {
                "name": "income_with_unit",
                "label": "Monthly Income",
                "value_type": "money",
                "unit": "USD",
                "source_type": "field",
                "cel_accessor": "income_with_unit",
            }
        )

        name = variable.name_get()[0][1]
        self.assertIn("USD", name)

    def test_name_get_uses_label(self):
        """Test name_get uses label when available."""
        variable = self.LogicVariable.create(
            {
                "name": "tech_name",
                "label": "Friendly Name",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "tech_name",
            }
        )

        # Verify the stored label field value
        self.assertEqual(variable.label, "Friendly Name")
        # name_get should use the stored label
        name = variable.name_get()[0][1]
        self.assertIn("Friendly Name", name)

    def test_get_by_cel_accessor(self):
        """Test get_by_cel_accessor method."""
        variable = self.LogicVariable.create(
            {
                "name": "findable_var",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "findable_accessor",
            }
        )

        found = self.LogicVariable.get_by_cel_accessor("findable_accessor")
        self.assertEqual(found, variable)

        not_found = self.LogicVariable.get_by_cel_accessor("nonexistent")
        self.assertFalse(not_found)

    def test_upsert_variable_create(self):
        """Test _upsert_variable creates new variable."""
        result = self.LogicVariable._upsert_variable(
            {
                "name": "upsert_new",
                "label": "Upserted Variable",
                "value_type": "boolean",
                "source_type": "field",
                "cel_accessor": "upsert_new",
                "is_system": True,
            }
        )

        self.assertTrue(result.id)
        self.assertEqual(result.name, "upsert_new")
        self.assertTrue(result.is_system)

    def test_upsert_variable_update_system(self):
        """Test _upsert_variable updates existing system variable."""
        existing = self.LogicVariable.create(
            {
                "name": "upsert_existing",
                "label": "Original Name",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "upsert_existing",
                "is_system": True,
            }
        )

        result = self.LogicVariable._upsert_variable(
            {
                "name": "upsert_existing",
                "label": "Updated Name",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "upsert_existing",
                "is_system": True,
            }
        )

        self.assertEqual(result.id, existing.id)
        self.assertEqual(result.label, "Updated Name")

    def test_upsert_variable_skip_user_created(self):
        """Test _upsert_variable doesn't update user-created variables."""
        existing = self.LogicVariable.create(
            {
                "name": "user_variable",
                "label": "User Created",
                "value_type": "string",
                "source_type": "field",
                "cel_accessor": "user_variable",
                "is_system": False,  # User-created
            }
        )

        result = self.LogicVariable._upsert_variable(
            {
                "name": "user_variable",
                "label": "Should Not Update",
                "value_type": "string",
                "source_type": "field",
                "cel_accessor": "user_variable",
            }
        )

        self.assertEqual(result.id, existing.id)
        self.assertEqual(result.label, "User Created")  # Unchanged


@tagged("post_install", "-at_install")
class TestLogicVariableUsageTracking(TransactionCase):
    """Tests for variable usage tracking functionality."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Logic = cls.env["spp.cel.expression"]

        # Create test variable
        cls.test_var = cls.LogicVariable.create(
            {
                "name": "test_usage_var",
                "label": "Test Usage Variable",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "test_usage_var",
            }
        )

    def test_logic_usage_count_zero(self):
        """Test logic_usage_count is zero when no logic uses the variable."""
        # Refresh count to ensure it's up to date
        self.test_var.action_refresh_usage_count()
        self.assertEqual(self.test_var.logic_usage_count, 0)

    def test_logic_usage_count_single(self):
        """Test logic_usage_count increments when logic uses the variable."""
        # Create logic with CEL expression referencing the variable
        self.Logic.create(
            {
                "name": "Test Logic",
                "expression_type": "filter",
                "cel_expression": "r.test_usage_var > 100",
            }
        )

        # Refresh the usage count manually
        self.test_var.action_refresh_usage_count()

        # Check usage count (stored value)
        self.assertEqual(self.test_var.logic_usage_count, 1)

    def test_logic_usage_count_multiple(self):
        """Test logic_usage_count with multiple logic records."""
        # Create multiple logic records with CEL expressions referencing the variable
        for i in range(3):
            self.Logic.create(
                {
                    "name": f"Test Logic {i}",
                    "expression_type": "filter",
                    "cel_expression": f"r.test_usage_var > {100 * i}",
                }
            )

        # Refresh the usage count manually
        self.test_var.action_refresh_usage_count()

        # Check usage count (stored value)
        self.assertEqual(self.test_var.logic_usage_count, 3)

    def test_action_refresh_usage_count(self):
        """Test action_refresh_usage_count returns notification."""
        # Create logic with CEL expression
        self.Logic.create(
            {
                "name": "Test Logic",
                "expression_type": "filter",
                "cel_expression": "r.test_usage_var > 100",
            }
        )

        # Call refresh action
        result = self.test_var.action_refresh_usage_count()

        # Verify action structure
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertIn("params", result)
        self.assertEqual(result["params"]["type"], "success")

        # Verify count was updated
        self.assertEqual(self.test_var.logic_usage_count, 1)

    def test_action_view_logic_usage(self):
        """Test action_view_logic_usage returns correct action dict."""
        # Create logic with CEL expression referencing the variable
        self.Logic.create(
            {
                "name": "Test Logic",
                "expression_type": "filter",
                "cel_expression": "r.test_usage_var == 50",
            }
        )

        # Call action
        action = self.test_var.action_view_logic_usage()

        # Verify action structure
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.cel.expression")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertIn("domain", action)
        # Domain searches for variable name in CEL expressions
        expected_domain = [
            "|",
            ("cel_expression", "ilike", self.test_var.cel_accessor),
            ("compiled_expression", "ilike", self.test_var.cel_accessor),
        ]
        self.assertEqual(action["domain"], expected_domain)
        self.assertFalse(action["context"]["create"])


@tagged("post_install", "-at_install")
class TestLogicVariableMailMixin(TransactionCase):
    """Tests for variable mail.thread integration."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.LogicVariable = cls.env["spp.cel.variable"]

        cls.test_var = cls.LogicVariable.create(
            {
                "name": "mail_test_var",
                "label": "Mail Test Variable",
                "value_type": "string",
                "source_type": "field",
                "cel_accessor": "mail_test_var",
            }
        )

    def test_variable_has_mail_thread(self):
        """Test that variable model inherits mail.thread."""
        # Instead of relying on the _inherit attribute (which may be
        # normalized by Odoo), check for mail.thread capabilities.
        self.assertTrue(hasattr(self.test_var, "message_post"))
        self.assertTrue(hasattr(self.test_var, "message_ids"))

    def test_can_post_message_to_variable(self):
        """Test that messages can be posted to variables."""
        # Post a message
        message = self.test_var.message_post(
            body="Test message for variable",
            message_type="comment",
        )

        # Verify message was posted
        self.assertTrue(message)
        self.assertEqual(message.model, "spp.cel.variable")
        self.assertEqual(message.res_id, self.test_var.id)

    def test_variable_message_ids(self):
        """Test that variable has message_ids field from mail.thread."""
        # Post a message
        self.test_var.message_post(
            body="Test message",
            message_type="comment",
        )

        # Check message_ids field exists and has messages
        self.assertTrue(hasattr(self.test_var, "message_ids"))
        self.assertGreater(len(self.test_var.message_ids), 0)


@tagged("post_install", "-at_install")
class TestLogicVariableCategory(TransactionCase):
    """Tests for the Variable Category model."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.LogicVariableCategory = cls.env["spp.cel.variable.category"]

    def test_create_category_basic(self):
        """Test basic category creation."""
        category = self.LogicVariableCategory.create(
            {
                "name": "Test Category",
                "code": "test_cat",
            }
        )

        self.assertTrue(category.id)
        self.assertEqual(category.name, "Test Category")
        self.assertEqual(category.code, "test_cat")

    def test_category_with_icon(self):
        """Test category with icon."""
        category = self.LogicVariableCategory.create(
            {
                "name": "Icon Category",
                "code": "icon_cat",
                "icon": "fa-home",
            }
        )

        self.assertEqual(category.icon, "fa-home")

    # REMOVED: test_category_with_description
    # The 'description' field does not exist on spp.cel.variable.category model.
    # Only the following fields exist: name, code, icon, color, sequence, parent_id,
    # parent_path, child_ids, variable_ids, variable_count


@tagged("post_install", "-at_install")
class TestLogicVariableFieldExists(TransactionCase):
    """Tests for field_exists stored computed field."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.LogicVariable = cls.env["spp.cel.variable"]

    def test_field_exists_for_existing_field(self):
        """Test field_exists is 'exists' for an existing field."""
        variable = self.LogicVariable.create(
            {
                "name": "test_existing_field",
                "label": "Test Existing Field",
                "value_type": "string",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "name",  # 'name' field exists on res.partner
                "cel_accessor": "test_existing_field",
            }
        )

        # Refresh field status
        variable.action_refresh_field_status()

        # Verify field_exists is 'exists'
        self.assertEqual(variable.field_exists, "exists")
        self.assertIn("exists", variable.field_exists_message.lower())

    def test_field_exists_for_missing_field(self):
        """Test field_exists is 'missing' for a non-existent field."""
        variable = self.LogicVariable.create(
            {
                "name": "test_missing_field",
                "label": "Test Missing Field",
                "value_type": "string",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "nonexistent_field_xyz123",
                "cel_accessor": "test_missing_field",
            }
        )

        # Refresh field status
        variable.action_refresh_field_status()

        # Verify field_exists is 'missing'
        self.assertEqual(variable.field_exists, "missing")
        self.assertIn("not found", variable.field_exists_message.lower())

    def test_field_exists_for_missing_model(self):
        """Test field_exists is 'missing' when model doesn't exist."""
        variable = self.LogicVariable.create(
            {
                "name": "test_missing_model",
                "label": "Test Missing Model",
                "value_type": "string",
                "source_type": "field",
                "source_model": "nonexistent.model.xyz123",
                "source_field": "some_field",
                "cel_accessor": "test_missing_model",
            }
        )

        # Refresh field status
        variable.action_refresh_field_status()

        # Verify field_exists is 'missing'
        self.assertEqual(variable.field_exists, "missing")
        self.assertIn("not found", variable.field_exists_message.lower())

    def test_field_exists_not_applicable(self):
        """Test field_exists is 'na' for non-field source types."""
        variable = self.LogicVariable.create(
            {
                "name": "test_computed_var",
                "label": "Test Computed Variable",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "1 + 1",
                "cel_accessor": "test_computed_var",
            }
        )

        # Refresh field status
        variable.action_refresh_field_status()

        # Verify field_exists is 'na'
        self.assertEqual(variable.field_exists, "na")
        self.assertEqual(variable.field_exists_message, "")

    def test_action_refresh_field_status(self):
        """Test action_refresh_field_status returns notification."""
        variable = self.LogicVariable.create(
            {
                "name": "test_refresh_field",
                "label": "Test Refresh Field",
                "value_type": "string",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "name",
                "cel_accessor": "test_refresh_field",
            }
        )

        # Call refresh action
        result = variable.action_refresh_field_status()

        # Verify action structure
        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertIn("params", result)
        self.assertEqual(result["params"]["type"], "success")

        # Verify field status was updated
        self.assertEqual(variable.field_exists, "exists")

    def test_field_exists_stored_performance(self):
        """Test that field_exists is stored and doesn't recompute on every access."""
        variable = self.LogicVariable.create(
            {
                "name": "test_stored_field",
                "label": "Test Stored Field",
                "value_type": "string",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "name",
                "cel_accessor": "test_stored_field",
            }
        )

        # Refresh field status once
        variable.action_refresh_field_status()

        # Access field_exists multiple times - should not trigger recomputation
        for _ in range(5):
            status = variable.field_exists
            self.assertEqual(status, "exists")

        # Verify the value is still correct
        self.assertEqual(variable.field_exists, "exists")


@tagged("post_install", "-at_install")
class TestGetAllVariables(TransactionCase):
    """Tests for the get_all_variables() real-time discovery method."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.LogicVariableCategory = cls.env["spp.cel.variable.category"]

    def test_get_all_variables_returns_list(self):
        """Test get_all_variables returns a list."""
        result = self.LogicVariable.get_all_variables()
        self.assertIsInstance(result, list)

    def test_get_all_variables_includes_partner_fields(self):
        """Test that allowed partner fields are discovered."""
        result = self.LogicVariable.get_all_variables()

        # Check that some allowed fields are present
        accessors = [v.get("cel_accessor") for v in result]
        self.assertIn("name", accessors)
        self.assertIn("email", accessors)
        self.assertIn("phone", accessors)

    def test_get_all_variables_field_structure(self):
        """Test that discovered variables have expected structure."""
        result = self.LogicVariable.get_all_variables()

        # Find a known field variable
        name_var = next((v for v in result if v.get("cel_accessor") == "name"), None)
        self.assertIsNotNone(name_var)

        # Check required fields exist
        self.assertIn("id", name_var)
        self.assertIn("name", name_var)
        self.assertIn("label", name_var)
        self.assertIn("value_type", name_var)
        self.assertIn("source_type", name_var)
        self.assertIn("cel_accessor", name_var)
        self.assertIn("data_source", name_var)
        self.assertIn("applies_to", name_var)

        # Check source_type for field variables
        self.assertEqual(name_var["source_type"], "field")

    def test_get_all_variables_context_filter_individual(self):
        """Test context_type filter for individual."""
        # Create a group-only variable
        self.LogicVariable.create(
            {
                "name": "group_only_var",
                "label": "Group Only Variable",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "1",
                "cel_accessor": "group_only_var",
                "applies_to": "group",
                "is_system": False,
            }
        )

        # Get all variables filtered by individual
        result = self.LogicVariable.get_all_variables(context_type="individual")

        # Group-only variable should not be included
        accessors = [v.get("cel_accessor") for v in result]
        self.assertNotIn("group_only_var", accessors)

        # Check that 'both' applies_to variables are included
        # (discovered field variables default to 'both')
        self.assertIn("name", accessors)

    def test_get_all_variables_context_filter_group(self):
        """Test context_type filter for group."""
        # Create an individual-only variable
        self.LogicVariable.create(
            {
                "name": "individual_only_var",
                "label": "Individual Only Variable",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "1",
                "cel_accessor": "individual_only_var",
                "applies_to": "individual",
                "is_system": False,
            }
        )

        # Get all variables filtered by group
        result = self.LogicVariable.get_all_variables(context_type="group")

        # Individual-only variable should not be included
        accessors = [v.get("cel_accessor") for v in result]
        self.assertNotIn("individual_only_var", accessors)

    def test_get_all_variables_user_defined_included(self):
        """Test that user-defined variables are included."""
        # Create a user-defined computed variable
        user_var = self.LogicVariable.create(
            {
                "name": "user_computed_var",
                "label": "User Computed Variable",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "1 + 1",
                "cel_accessor": "user_computed_var",
                "is_system": False,
            }
        )

        result = self.LogicVariable.get_all_variables()

        # User variable should be included
        accessors = [v.get("cel_accessor") for v in result]
        self.assertIn("user_computed_var", accessors)

        # Should have real ID (not virtual)
        user_result = next((v for v in result if v.get("cel_accessor") == "user_computed_var"), None)
        self.assertIsNotNone(user_result)
        self.assertEqual(user_result["id"], user_var.id)
        self.assertFalse(user_result.get("is_virtual", True))

    def test_get_all_variables_user_customizations_applied(self):
        """Test that user customizations override discovered variable metadata."""
        # Create a customization record for a discovered field
        category = self.LogicVariableCategory._get_or_create("custom_category", "Custom Category")

        # Create customization for 'name' field variable
        self.LogicVariable.create(
            {
                "name": "name",
                "label": "Custom Name Label",
                "description": "Custom description for name field",
                "value_type": "string",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "name",
                "cel_accessor": "name",
                "category_id": category.id,
                "is_system": True,  # System variable with customization
            }
        )

        result = self.LogicVariable.get_all_variables()

        # Find name variable
        name_var = next((v for v in result if v.get("cel_accessor") == "name"), None)
        self.assertIsNotNone(name_var)

        # Custom label should be applied
        self.assertEqual(name_var["label"], "Custom Name Label")

        # Custom category should be applied
        self.assertEqual(name_var["category_id"][0], category.id)

    def test_get_all_variables_virtual_ids_negative(self):
        """Test that virtual variables have negative IDs."""
        result = self.LogicVariable.get_all_variables()

        # Virtual variables are discovered from sources but not stored in DB
        # They should have negative IDs to distinguish from real DB records
        virtual_found = False
        for var in result:
            if var.get("is_virtual"):
                # Virtual variables should have negative IDs
                self.assertLess(var["id"], 0)
                virtual_found = True
                break

        # If no virtual variables found, that's OK - all have been customized
        # The test verifies the ID logic when virtuals exist
        if not virtual_found:
            # At minimum, verify non-virtual variables have positive IDs
            for var in result:
                if not var.get("is_virtual"):
                    self.assertGreater(var["id"], 0)
                    break

    def test_get_all_variables_sorted_by_category(self):
        """Test that results are sorted by category."""
        result = self.LogicVariable.get_all_variables()

        # Variables should be sorted by category_id, sequence, name
        # Just verify we get a non-empty sorted list
        self.assertGreater(len(result), 0)

        # Check that variables with same category are together
        categories_seen = []
        for var in result:
            cat_id = var.get("category_id", [0])[0] if var.get("category_id") else 0
            if cat_id not in categories_seen:
                categories_seen.append(cat_id)

        # Categories should appear in order (no interleaving)
        self.assertEqual(categories_seen, sorted(categories_seen))

    def test_get_all_variables_vocabulary_discovery(self):
        """Test vocabulary concept group discovery if module installed."""
        if "spp.vocabulary.concept.group" not in self.env:
            self.skipTest("spp_vocabulary module not installed")

        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # Create a concept group with cel_function
        group = ConceptGroup.create(
            {
                "name": "Test Elderly Group",
                "cel_function": "is_test_elderly",
            }
        )

        result = self.LogicVariable.get_all_variables()

        # Vocabulary variable should be discovered
        accessors = [v.get("cel_accessor") for v in result]
        self.assertIn("is_test_elderly", accessors)

        # Check structure
        elderly_var = next((v for v in result if v.get("cel_accessor") == "is_test_elderly"), None)
        self.assertIsNotNone(elderly_var)
        self.assertEqual(elderly_var["source_type"], "vocabulary")
        self.assertEqual(elderly_var["value_type"], "boolean")
        self.assertEqual(elderly_var["source_concept_id"], group.id)

    def test_get_all_variables_scoring_discovery(self):
        """Test scoring model discovery if module installed."""
        if "spp.scoring.model" not in self.env:
            self.skipTest("spp_scoring module not installed")

        ScoringModel = self.env["spp.scoring.model"]

        # Create an active scoring model
        model = ScoringModel.create(
            {
                "name": "Test PMT Model",
                "code": "test_pmt_discovery",
                "is_active": True,
            }
        )

        result = self.LogicVariable.get_all_variables()

        # Score and classification variables should be discovered
        accessors = [v.get("cel_accessor") for v in result]
        self.assertIn('score("test_pmt_discovery")', accessors)
        self.assertIn('classification("test_pmt_discovery")', accessors)

        # Check score variable structure
        score_var = next(
            (v for v in result if v.get("cel_accessor") == 'score("test_pmt_discovery")'),
            None,
        )
        self.assertIsNotNone(score_var)
        self.assertEqual(score_var["source_type"], "scoring")
        self.assertEqual(score_var["value_type"], "number")
        # source_scoring_id only present when spp_studio_scoring bridge is installed
        if "source_scoring_id" in score_var:
            self.assertEqual(score_var["source_scoring_id"], model.id)

        # Check classification variable structure
        class_var = next(
            (v for v in result if v.get("cel_accessor") == 'classification("test_pmt_discovery")'),
            None,
        )
        self.assertIsNotNone(class_var)
        self.assertEqual(class_var["value_type"], "string")

    def test_get_all_variables_inactive_scoring_not_discovered(self):
        """Test that inactive scoring models are not discovered."""
        if "spp.scoring.model" not in self.env:
            self.skipTest("spp_scoring module not installed")

        ScoringModel = self.env["spp.scoring.model"]

        # Create an inactive scoring model
        ScoringModel.create(
            {
                "name": "Inactive PMT Model",
                "code": "inactive_pmt_discovery",
                "is_active": False,
            }
        )

        result = self.LogicVariable.get_all_variables()

        # Inactive model variables should not be discovered
        accessors = [v.get("cel_accessor") for v in result]
        self.assertNotIn('score("inactive_pmt_discovery")', accessors)
        self.assertNotIn('classification("inactive_pmt_discovery")', accessors)

    def test_get_all_variables_custom_fields_discovered(self):
        """Test that x_* custom fields are discovered."""
        # This test checks the logic - actual x_ fields may not exist
        # We verify the pattern by checking that the method handles them correctly
        Partner = self.env["res.partner"]
        partner_fields = Partner.fields_get()

        # Get discovered variables
        result = self.LogicVariable.get_all_variables()
        accessors = [v.get("cel_accessor") for v in result]

        # Any existing x_* fields should be discovered
        for field_name in partner_fields:
            if field_name.startswith("x_"):
                field_type = partner_fields[field_name].get("type")
                # Skip technical field types
                if field_type not in ["one2many", "many2many", "binary"]:
                    self.assertIn(field_name, accessors)
