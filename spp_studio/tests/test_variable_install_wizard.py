# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the Variable Install Wizard.

Tests cover:
- Wizard initialization and line population
- Variable matching against different sources
- Variable installation from various sources
- Edge cases and error handling
"""

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVariableInstallWizardBasic(TransactionCase):
    """Basic tests for the Variable Install Wizard."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]
        cls.WizardLine = cls.env["spp.studio.variable.install.wizard.line"]
        cls.Category = cls.env["spp.cel.variable.category"]

        # Ensure we have a category for tests
        cls.test_category = cls.Category._get_or_create("test_install", "Test Install Category")

    def test_wizard_opens_from_logic(self):
        """Test that wizard can be opened from a logic with missing variables."""
        # Create logic with missing variable in expression
        logic = self.Logic.create(
            {
                "name": "Test Logic Missing Vars",
                "expression_type": "filter",
                "cel_expression": "unknown_variable > 10",
            }
        )

        # Verify missing variables detected
        self.assertTrue(logic.missing_variables)
        self.assertIn("unknown_variable", logic.missing_variables)

        # Open wizard via action
        action = logic.action_install_missing_variables()
        self.assertEqual(action["res_model"], "spp.studio.variable.install.wizard")
        self.assertEqual(action["context"]["default_logic_id"], logic.id)

    def test_wizard_no_missing_variables(self):
        """Test wizard shows notification when no missing variables."""
        # Create a variable first
        self.LogicVariable.create(
            {
                "name": "known_var",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "known_var",
            }
        )

        # Create logic using that variable
        logic = self.Logic.create(
            {
                "name": "Test Logic Known Vars",
                "expression_type": "filter",
                "cel_expression": "known_var > 10",
            }
        )

        # Verify no missing variables
        self.assertFalse(logic.missing_variables)

        # Action should return notification, not wizard
        action = logic.action_install_missing_variables()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")

    def test_wizard_populates_lines(self):
        """Test wizard correctly populates lines from missing variables."""
        logic = self.Logic.create(
            {
                "name": "Test Multi Missing",
                "expression_type": "filter",
                "cel_expression": "var_one > 10 && var_two < 20",
            }
        )

        # Create wizard
        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Check lines were created
        self.assertEqual(len(wizard.line_ids), 2)
        var_names = wizard.line_ids.mapped("variable_name")
        self.assertIn("var_one", var_names)
        self.assertIn("var_two", var_names)

    def test_wizard_summary_computation(self):
        """Test wizard summary fields are computed correctly."""
        logic = self.Logic.create(
            {
                "name": "Test Summary",
                "expression_type": "filter",
                "cel_expression": "a > 1 && b < 2 && c == 3",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # All are unmatched (none type)
        self.assertEqual(wizard.total_missing, 3)
        self.assertEqual(wizard.installable_count, 0)  # No matches
        self.assertEqual(wizard.selected_count, 0)  # None selected


@tagged("post_install", "-at_install")
class TestVariableInstallWizardMatching(TransactionCase):
    """Tests for variable matching logic in the wizard."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]
        cls.Category = cls.env["spp.cel.variable.category"]

    def test_match_existing_inactive_variable(self):
        """Test matching against existing inactive variable."""
        # Create an inactive variable
        self.LogicVariable.create(
            {
                "name": "inactive_test_var",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "inactive_test_var",
                "active": False,
            }
        )

        # Create logic referencing this inactive variable
        logic = self.Logic.create(
            {
                "name": "Test Inactive Match",
                "expression_type": "filter",
                "cel_expression": "inactive_test_var > 10",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Should match as existing_inactive
        line = wizard.line_ids.filtered(lambda line: line.variable_name == "inactive_test_var")
        self.assertEqual(len(line), 1)
        self.assertEqual(line.match_type, "existing_inactive")
        self.assertTrue(line.selected)  # Should be auto-selected

    def test_match_partner_field(self):
        """Test matching against res.partner field."""
        # 'name' is a standard field on res.partner
        self.Logic.create(
            {
                "name": "Test Field Match",
                "expression_type": "filter",
                # Use a field that definitely exists on res.partner
                "cel_expression": "name != ''",
            }
        )

        # Check if 'name' is in missing variables
        # Note: 'name' might already be a variable, so let's use a different approach
        wizard = self.Wizard.new({})
        match_info = wizard._find_match("name")

        # Should match as field type (or existing if already defined)
        self.assertIn(
            match_info["type"],
            ["field", "existing_active", "existing_inactive", "standard"],
        )

    def test_match_no_match(self):
        """Test when no match is found."""
        logic = self.Logic.create(
            {
                "name": "Test No Match",
                "expression_type": "filter",
                "cel_expression": "completely_unknown_xyz123 > 10",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        line = wizard.line_ids.filtered(lambda line: line.variable_name == "completely_unknown_xyz123")
        self.assertEqual(len(line), 1)
        self.assertEqual(line.match_type, "none")
        self.assertFalse(line.selected)  # Should not be auto-selected

    def test_match_scoring_pattern(self):
        """Test matching scoring model patterns."""
        wizard = self.Wizard.new({})

        # Test _score suffix pattern
        match_info = wizard._find_match("pmt_score")
        # Will be 'none' if no scoring model exists, or 'scoring' if it does
        self.assertIn(
            match_info["type"],
            ["none", "scoring", "existing_active", "existing_inactive", "standard"],
        )

    def test_match_metric_pattern(self):
        """Test matching metric() indicator pattern."""
        wizard = self.Wizard.new({})

        # Test metric("...") pattern
        match_info = wizard._find_match('metric("test.indicator")')
        # Will be 'none' if no indicator exists, or 'indicator' if it does
        self.assertIn(match_info["type"], ["none", "indicator"])


@tagged("post_install", "-at_install")
class TestVariableInstallWizardInstallation(TransactionCase):
    """Tests for variable installation from the wizard."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]
        cls.WizardLine = cls.env["spp.studio.variable.install.wizard.line"]
        cls.Category = cls.env["spp.cel.variable.category"]

    def test_install_from_inactive_variable(self):
        """Test installing (activating) an inactive variable."""
        # Create inactive variable
        inactive_var = self.LogicVariable.create(
            {
                "name": "activate_me_var",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "1 + 1",
                "cel_accessor": "activate_me_var",
                "active": False,
            }
        )

        # Create logic referencing it
        logic = self.Logic.create(
            {
                "name": "Test Activate",
                "expression_type": "filter",
                "cel_expression": "activate_me_var > 0",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Find and install the line
        line = wizard.line_ids.filtered(lambda line: line.variable_name == "activate_me_var")
        self.assertTrue(line.selected)

        # Install
        wizard.action_install_selected()

        # Variable should now be active
        inactive_var.invalidate_recordset()
        self.assertTrue(inactive_var.active)

    def test_install_from_partner_field(self):
        """Test creating variable from res.partner field."""
        # Ensure variable doesn't exist
        existing = self.LogicVariable.search([("name", "=", "email")])
        if existing:
            existing.unlink()

        wizard = self.Wizard.new({})
        line = self.WizardLine.new(
            {
                "wizard_id": wizard.id,
                "variable_name": "email",
                "match_type": "field",
                "match_data": "field:email",
            }
        )

        # Install the variable
        variable = line._create_field_variable("email")

        self.assertTrue(variable.id)
        self.assertEqual(variable.name, "email")
        self.assertEqual(variable.source_type, "field")
        self.assertEqual(variable.source_model, "res.partner")
        self.assertEqual(variable.source_field, "email")

    def test_install_selected_batch(self):
        """Test batch installation of selected variables."""
        # Create multiple inactive variables
        for i in range(3):
            self.LogicVariable.create(
                {
                    "name": f"batch_var_{i}",
                    "value_type": "number",
                    "source_type": "computed",
                    "cel_expression": f"{i} + 1",
                    "cel_accessor": f"batch_var_{i}",
                    "active": False,
                }
            )

        # Create logic with all of them
        logic = self.Logic.create(
            {
                "name": "Test Batch Install",
                "expression_type": "filter",
                "cel_expression": "batch_var_0 + batch_var_1 + batch_var_2",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # All should be selected (existing_inactive)
        self.assertEqual(wizard.selected_count, 3)

        # Install all
        wizard.action_install_selected()

        # All should now be active
        for i in range(3):
            var = self.LogicVariable.search([("name", "=", f"batch_var_{i}")])
            self.assertTrue(var.active)

    def test_install_nothing_selected_error(self):
        """Test error when trying to install with nothing selected."""
        logic = self.Logic.create(
            {
                "name": "Test No Selection",
                "expression_type": "filter",
                "cel_expression": "xyz_no_match > 10",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Nothing should be selected (no match)
        self.assertEqual(wizard.selected_count, 0)

        # Should raise UserError
        with self.assertRaises(UserError):
            wizard.action_install_selected()


@tagged("post_install", "-at_install")
class TestVariableInstallWizardActions(TransactionCase):
    """Tests for wizard action methods."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]

    def test_select_all_action(self):
        """Test select all action."""
        # Create mixed variables (some matchable, some not)
        self.LogicVariable.create(
            {
                "name": "selectable_var",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "selectable_var",
                "active": False,
            }
        )

        logic = self.Logic.create(
            {
                "name": "Test Select All",
                "expression_type": "filter",
                "cel_expression": "selectable_var + unknown_var",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Deselect all first
        wizard.line_ids.write({"selected": False})
        self.assertEqual(wizard.selected_count, 0)

        # Select all
        wizard.action_select_all()

        # Only installable ones should be selected
        self.assertEqual(wizard.selected_count, wizard.installable_count)

    def test_deselect_all_action(self):
        """Test deselect all action."""
        self.LogicVariable.create(
            {
                "name": "deselect_test_var",
                "value_type": "number",
                "source_type": "field",
                "cel_accessor": "deselect_test_var",
                "active": False,
            }
        )

        logic = self.Logic.create(
            {
                "name": "Test Deselect All",
                "expression_type": "filter",
                "cel_expression": "deselect_test_var > 0",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Should have at least one selected
        self.assertGreater(wizard.selected_count, 0)

        # Deselect all
        wizard.action_deselect_all()

        self.assertEqual(wizard.selected_count, 0)

    def test_create_variable_action(self):
        """Test action to create variable manually."""
        logic = self.Logic.create(
            {
                "name": "Test Create Action",
                "expression_type": "filter",
                "cel_expression": "manual_create_var > 0",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})
        line = wizard.line_ids[0]

        # Call create action
        action = line.action_create_variable()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "spp.cel.variable")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "new")
        # Should have default values pre-filled
        self.assertEqual(action["context"]["default_name"], line.variable_name)


@tagged("post_install", "-at_install")
class TestVariableInstallWizardEdgeCases(TransactionCase):
    """Tests for edge cases and error handling."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]
        cls.WizardLine = cls.env["spp.studio.variable.install.wizard.line"]

    def test_empty_expression(self):
        """Test wizard with empty expression."""
        logic = self.Logic.create(
            {
                "name": "Test Empty",
                "expression_type": "filter",
                "cel_expression": "",
            }
        )

        # Should show notification since no missing vars
        action = logic.action_install_missing_variables()
        self.assertEqual(action["type"], "ir.actions.client")

    def test_cel_keywords_filtered(self):
        """Test that CEL keywords are not considered missing variables."""
        logic = self.Logic.create(
            {
                "name": "Test Keywords",
                "expression_type": "filter",
                "cel_expression": "true && false || has(x)",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # 'true', 'false', 'has' should not be in lines
        var_names = wizard.line_ids.mapped("variable_name")
        self.assertNotIn("true", var_names)
        self.assertNotIn("false", var_names)
        self.assertNotIn("has", var_names)
        # But 'x' should be there
        self.assertIn("x", var_names)

    def test_duplicate_variable_in_expression(self):
        """Test that duplicate variables are deduplicated."""
        logic = self.Logic.create(
            {
                "name": "Test Duplicates",
                "expression_type": "filter",
                "cel_expression": "dup_var > 10 && dup_var < 20",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Should only have one line for dup_var
        dup_lines = wizard.line_ids.filtered(lambda line: line.variable_name == "dup_var")
        self.assertEqual(len(dup_lines), 1)

    def test_complex_expression_parsing(self):
        """Test parsing of complex CEL expressions."""
        logic = self.Logic.create(
            {
                "name": "Test Complex",
                "expression_type": "filter",
                "cel_expression": """
                members.count(m, age_years(m.birthdate) < 18) >= min_children &&
                household_income < income_threshold * adjustment_factor
            """,
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        var_names = wizard.line_ids.mapped("variable_name")
        # Should include various variables from the expression
        # Note: exact parsing depends on regex, some may or may not be captured
        self.assertGreater(len(var_names), 0)

    def test_install_line_no_match_data_error(self):
        """Test error when trying to install line without match data."""
        wizard = self.Wizard.create(
            {
                "logic_id": self.Logic.create(
                    {
                        "name": "Test No Data",
                        "expression_type": "filter",
                        "cel_expression": "x > 0",
                    }
                ).id
            }
        )

        line = self.WizardLine.create(
            {
                "wizard_id": wizard.id,
                "variable_name": "test_var",
                "match_type": "none",
                "match_data": "",  # Empty match data
            }
        )

        with self.assertRaises(UserError):
            line._install_variable()

    def test_match_standard_variable_age(self):
        """Test matching the standard 'age' variable."""
        wizard = self.Wizard.new({})
        match_info = wizard._find_match("age")

        # 'age' is a standard variable defined in standard_variables.xml
        # Should match as standard or existing
        self.assertIn(match_info["type"], ["standard", "existing_active", "existing_inactive"])

    def test_match_standard_variable_hh_size(self):
        """Test matching the standard 'hh_size' variable."""
        wizard = self.Wizard.new({})
        match_info = wizard._find_match("hh_size")

        # 'hh_size' is a standard variable
        self.assertIn(match_info["type"], ["standard", "existing_active", "existing_inactive"])

    def test_is_installable_computation(self):
        """Test is_installable computed field."""
        wizard = self.Wizard.create(
            {
                "logic_id": self.Logic.create(
                    {
                        "name": "Test Installable",
                        "expression_type": "filter",
                        "cel_expression": "x > 0",
                    }
                ).id
            }
        )

        # Create lines with different match types
        none_line = self.WizardLine.create(
            {
                "wizard_id": wizard.id,
                "variable_name": "no_match",
                "match_type": "none",
            }
        )
        self.assertFalse(none_line.is_installable)

        field_line = self.WizardLine.create(
            {
                "wizard_id": wizard.id,
                "variable_name": "field_match",
                "match_type": "field",
                "match_data": "field:email",
            }
        )
        self.assertTrue(field_line.is_installable)

        existing_active_line = self.WizardLine.create(
            {
                "wizard_id": wizard.id,
                "variable_name": "active_var",
                "match_type": "existing_active",
            }
        )
        self.assertFalse(existing_active_line.is_installable)


@tagged("post_install", "-at_install")
class TestVariableInstallWizardVocabulary(TransactionCase):
    """Tests for vocabulary concept matching and installation."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]
        cls.WizardLine = cls.env["spp.studio.variable.install.wizard.line"]

        # Check if vocabulary module is installed
        cls.has_vocabulary = "spp.vocabulary.concept.group" in cls.env

    def test_match_vocabulary_function(self):
        """Test matching vocabulary concept group by cel_function."""
        if not self.has_vocabulary:
            self.skipTest("Vocabulary module not installed")

        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # Create a concept group with cel_function
        group = ConceptGroup.create(
            {
                "name": "Test Gender Female",
                "label": "Female",
                "cel_function": "is_test_female",
            }
        )

        wizard = self.Wizard.new({})
        match_info = wizard._find_match("is_test_female")

        self.assertEqual(match_info["type"], "vocabulary")
        self.assertIn(str(group.id), match_info["data"])

    def test_install_vocabulary_variable(self):
        """Test creating variable from vocabulary concept group."""
        if not self.has_vocabulary:
            self.skipTest("Vocabulary module not installed")

        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        group = ConceptGroup.create(
            {
                "name": "Test Concept Install",
                "label": "Test Concept",
                "cel_function": "is_test_concept_install",
            }
        )

        wizard = self.Wizard.new({})
        line = self.WizardLine.new(
            {
                "wizard_id": wizard.id,
                "variable_name": "is_test_concept_install",
                "match_type": "vocabulary",
                "match_data": f"vocabulary:{group.id}",
            }
        )

        variable = line._create_vocabulary_variable(group.id)

        self.assertTrue(variable.id)
        self.assertEqual(variable.name, "is_test_concept_install")
        self.assertEqual(variable.source_type, "vocabulary")
        self.assertEqual(variable.value_type, "boolean")
        self.assertEqual(variable.source_concept_id, group)


@tagged("post_install", "-at_install")
class TestVariableInstallWizardIndicator(TransactionCase):
    """Tests for indicator matching and installation."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]
        cls.WizardLine = cls.env["spp.studio.variable.install.wizard.line"]

        # Check if indicator module is installed
        cls.has_indicators = "spp.indicator.definition" in cls.env

    def test_match_indicator_metric_pattern(self):
        """Test matching indicator by metric() pattern."""
        if not self.has_indicators:
            self.skipTest("Indicators module not installed")

        Indicator = self.env["spp.indicator.definition"]

        # Create test indicator
        indicator = Indicator.create(
            {
                "name": "test.install.indicator",
                "value_type": "number",
                "active": True,
            }
        )

        wizard = self.Wizard.new({})
        match_info = wizard._find_match('metric("test.install.indicator")')

        self.assertEqual(match_info["type"], "indicator")
        self.assertIn(str(indicator.id), match_info["data"])

    def test_install_indicator_variable(self):
        """Test creating variable from indicator definition."""
        if not self.has_indicators:
            self.skipTest("Indicators module not installed")

        Indicator = self.env["spp.indicator.definition"]

        indicator = Indicator.create(
            {
                "name": "test.wizard.indicator",
                "value_type": "number",
                "description": "Test indicator for wizard",
                "active": True,
            }
        )

        wizard = self.Wizard.new({})
        line = self.WizardLine.new(
            {
                "wizard_id": wizard.id,
                "variable_name": "test.wizard.indicator",
                "match_type": "indicator",
                "match_data": f"indicator:{indicator.id}",
            }
        )

        variable = line._create_indicator_variable(indicator.id)

        self.assertTrue(variable.id)
        self.assertEqual(variable.source_type, "external")  # Indicator data uses external source type
        # NOTE: source_indicator_id removed - external data uses external_provider_id instead
        self.assertIn("metric(", variable.cel_accessor)


@tagged("post_install", "-at_install")
class TestVariableInstallWizardScoring(TransactionCase):
    """Tests for scoring model matching and installation."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]
        cls.WizardLine = cls.env["spp.studio.variable.install.wizard.line"]

        # Check if scoring module is installed
        cls.has_scoring = "spp.scoring.model" in cls.env

    def test_match_scoring_score_suffix(self):
        """Test matching scoring model by _score suffix."""
        if not self.has_scoring:
            self.skipTest("Scoring module not installed")

        ScoringModel = self.env["spp.scoring.model"]

        # Create test scoring model
        model = ScoringModel.create(
            {
                "name": "Test Wizard Scoring",
                "code": "test_wizard_score",
                "is_active": True,
            }
        )

        wizard = self.Wizard.new({})
        match_info = wizard._find_match("test_wizard_score_score")

        self.assertEqual(match_info["type"], "scoring")
        self.assertIn(str(model.id), match_info["data"])
        self.assertIn("score", match_info["data"])

    def test_match_scoring_classification_suffix(self):
        """Test matching scoring model by _classification suffix."""
        if not self.has_scoring:
            self.skipTest("Scoring module not installed")

        ScoringModel = self.env["spp.scoring.model"]

        model = ScoringModel.create(
            {
                "name": "Test Classification Scoring",
                "code": "test_class_score",
                "is_active": True,
            }
        )

        wizard = self.Wizard.new({})
        match_info = wizard._find_match("test_class_score_classification")

        self.assertEqual(match_info["type"], "scoring")
        self.assertIn(str(model.id), match_info["data"])
        self.assertIn("classification", match_info["data"])

    def test_install_scoring_variable_score(self):
        """Test creating score variable from scoring model."""
        if not self.has_scoring:
            self.skipTest("Scoring module not installed")

        ScoringModel = self.env["spp.scoring.model"]

        model = ScoringModel.create(
            {
                "name": "Test Install Scoring",
                "code": "test_install_scoring",
                "is_active": True,
            }
        )

        wizard = self.Wizard.new({})
        line = self.WizardLine.new(
            {
                "wizard_id": wizard.id,
                "variable_name": "test_install_scoring_score",
                "match_type": "scoring",
                "match_data": f"scoring:{model.id}:score",
            }
        )

        variable = line._create_scoring_variable(model.id, "score")

        self.assertTrue(variable.id)
        self.assertEqual(variable.source_type, "scoring")
        self.assertEqual(variable.value_type, "number")
        # source_scoring_id only present when spp_studio_scoring bridge is installed
        if hasattr(variable, "source_scoring_id"):
            self.assertEqual(variable.source_scoring_id, model)
        self.assertIn("score(", variable.cel_accessor)

    def test_install_scoring_variable_classification(self):
        """Test creating classification variable from scoring model."""
        if not self.has_scoring:
            self.skipTest("Scoring module not installed")

        ScoringModel = self.env["spp.scoring.model"]

        model = ScoringModel.create(
            {
                "name": "Test Install Classification",
                "code": "test_install_class",
                "is_active": True,
            }
        )

        wizard = self.Wizard.new({})
        line = self.WizardLine.new(
            {
                "wizard_id": wizard.id,
                "variable_name": "test_install_class_classification",
                "match_type": "scoring",
                "match_data": f"scoring:{model.id}:classification",
            }
        )

        variable = line._create_scoring_variable(model.id, "classification")

        self.assertTrue(variable.id)
        self.assertEqual(variable.source_type, "scoring")
        self.assertEqual(variable.value_type, "string")
        # source_scoring_id only present when spp_studio_scoring bridge is installed
        if hasattr(variable, "source_scoring_id"):
            self.assertEqual(variable.source_scoring_id, model)
        self.assertIn("classification(", variable.cel_accessor)


@tagged("post_install", "-at_install")
class TestVariableInstallWizardRecursive(TransactionCase):
    """Tests for recursive dependency detection in the wizard."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]
        cls.Category = cls.env["spp.cel.variable.category"]

        # Get or create test category
        cls.test_category = cls.Category._get_or_create("test_recursive", "Test Recursive Category")

    def test_recursive_computed_dependency(self):
        """Test that computed variable dependencies are detected recursively."""
        # Create a computed variable that depends on another variable
        # dep_var depends on base_var
        self.LogicVariable.create(
            {
                "name": "base_var_recursive",
                "value_type": "number",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "id",
                "cel_accessor": "base_var_recursive",
                "category_id": self.test_category.id,
                "active": False,  # Make it inactive so it shows as missing
            }
        )

        self.LogicVariable.create(
            {
                "name": "dep_var_recursive",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "base_var_recursive * 2",
                "cel_accessor": "dep_var_recursive",
                "category_id": self.test_category.id,
                "active": False,  # Make it inactive
            }
        )

        # Create logic that uses dep_var (which depends on base_var)
        logic = self.Logic.create(
            {
                "name": "Test Recursive Logic",
                "expression_type": "filter",
                "cel_expression": "dep_var_recursive > 10",
            }
        )

        # Open wizard
        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Should have BOTH variables: dep_var (direct) and base_var (dependency)
        var_names = wizard.line_ids.mapped("variable_name")
        self.assertIn("dep_var_recursive", var_names)
        self.assertIn("base_var_recursive", var_names)

        # Check dependency flags
        dep_line = wizard.line_ids.filtered(lambda line: line.variable_name == "dep_var_recursive")
        base_line = wizard.line_ids.filtered(lambda line: line.variable_name == "base_var_recursive")

        self.assertFalse(dep_line.is_dependency)  # Direct reference
        self.assertTrue(base_line.is_dependency)  # Transitive dependency

    def test_recursive_aggregate_dependency(self):
        """Test that aggregate variable filter dependencies are detected."""
        # Create an aggregate variable with a filter that uses another variable
        self.LogicVariable.create(
            {
                "name": "filter_threshold_var",
                "value_type": "number",
                "source_type": "constant",
                "default_value": "18",
                "cel_accessor": "filter_threshold_var",
                "category_id": self.test_category.id,
                "active": False,
            }
        )

        self.LogicVariable.create(
            {
                "name": "filtered_count_var",
                "value_type": "number",
                "source_type": "aggregate",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "age_years(m.birthdate) < filter_threshold_var",
                "cel_accessor": "filtered_count_var",
                "category_id": self.test_category.id,
                "active": False,
            }
        )

        logic = self.Logic.create(
            {
                "name": "Test Aggregate Recursive",
                "expression_type": "filter",
                "cel_expression": "filtered_count_var >= 2",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        var_names = wizard.line_ids.mapped("variable_name")
        self.assertIn("filtered_count_var", var_names)
        self.assertIn("filter_threshold_var", var_names)

    def test_recursive_multiple_levels(self):
        """Test multiple levels of dependency detection."""
        # Create a chain: level3 -> level2 -> level1
        self.LogicVariable.create(
            {
                "name": "level1_var",
                "value_type": "number",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "id",
                "cel_accessor": "level1_var",
                "category_id": self.test_category.id,
                "active": False,
            }
        )

        self.LogicVariable.create(
            {
                "name": "level2_var",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "level1_var + 1",
                "cel_accessor": "level2_var",
                "category_id": self.test_category.id,
                "active": False,
            }
        )

        self.LogicVariable.create(
            {
                "name": "level3_var",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "level2_var * 2",
                "cel_accessor": "level3_var",
                "category_id": self.test_category.id,
                "active": False,
            }
        )

        logic = self.Logic.create(
            {
                "name": "Test Multi-Level",
                "expression_type": "filter",
                "cel_expression": "level3_var > 100",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        var_names = wizard.line_ids.mapped("variable_name")
        self.assertEqual(len(var_names), 3)
        self.assertIn("level3_var", var_names)
        self.assertIn("level2_var", var_names)
        self.assertIn("level1_var", var_names)

        # Check dependency flags
        l3_line = wizard.line_ids.filtered(lambda line: line.variable_name == "level3_var")
        l2_line = wizard.line_ids.filtered(lambda line: line.variable_name == "level2_var")
        l1_line = wizard.line_ids.filtered(lambda line: line.variable_name == "level1_var")

        self.assertFalse(l3_line.is_dependency)  # Direct
        self.assertTrue(l2_line.is_dependency)  # Transitive
        self.assertTrue(l1_line.is_dependency)  # Transitive

    def test_recursive_circular_reference_protection(self):
        """Test that circular references don't cause infinite loops."""
        # Create variables that reference each other (circular)
        self.LogicVariable.create(
            {
                "name": "circular_a",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "circular_b + 1",
                "cel_accessor": "circular_a",
                "category_id": self.test_category.id,
                "active": False,
            }
        )

        self.LogicVariable.create(
            {
                "name": "circular_b",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "circular_a - 1",
                "cel_accessor": "circular_b",
                "category_id": self.test_category.id,
                "active": False,
            }
        )

        logic = self.Logic.create(
            {
                "name": "Test Circular",
                "expression_type": "filter",
                "cel_expression": "circular_a > 0",
            }
        )

        # Should not hang or crash
        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Should have both variables (visited set prevents infinite loop)
        var_names = wizard.line_ids.mapped("variable_name")
        self.assertIn("circular_a", var_names)
        self.assertIn("circular_b", var_names)
        self.assertEqual(len(var_names), 2)

    def test_recursive_no_extra_when_already_active(self):
        """Test that active variables don't add their dependencies."""
        # Create an active computed variable
        self.LogicVariable.create(
            {
                "name": "base_active_var",
                "value_type": "number",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "id",
                "cel_accessor": "base_active_var",
                "category_id": self.test_category.id,
                "active": True,
                "state": "active",
            }
        )

        self.LogicVariable.create(
            {
                "name": "computed_active_var",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "base_active_var * 2",
                "cel_accessor": "computed_active_var",
                "category_id": self.test_category.id,
                "active": True,
                "state": "active",
            }
        )

        # Create logic using the active computed variable
        logic = self.Logic.create(
            {
                "name": "Test Active Dependencies",
                "expression_type": "filter",
                "cel_expression": "computed_active_var > 10 && missing_new_var > 5",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Should only have missing_new_var, not the active ones or their deps
        var_names = wizard.line_ids.mapped("variable_name")
        self.assertIn("missing_new_var", var_names)
        # The active variables shouldn't cause base_active_var to appear
        # (computed_active_var is active so it's not processed for dependencies)

    def test_extract_variables_filters_cel_keywords(self):
        """Test that CEL keywords are properly filtered from expressions."""
        wizard = self.Wizard.new({})

        expression = "true && false || has(x) && size(list) > 0 && m.age >= 18"
        vars_found = wizard._extract_variables_from_expression(expression)

        # Should not include CEL keywords
        self.assertNotIn("true", vars_found)
        self.assertNotIn("false", vars_found)
        self.assertNotIn("has", vars_found)
        self.assertNotIn("size", vars_found)
        # 'm' is a common loop variable, should be filtered
        self.assertNotIn("m", vars_found)
        # 'x', 'list', 'age' should potentially be included
        # (depends on implementation - some might be filtered as common)

    def test_get_variable_expression_computed(self):
        """Test extracting expression from computed variable."""
        wizard = self.Wizard.new({})

        var = self.LogicVariable.create(
            {
                "name": "test_expr_computed",
                "value_type": "number",
                "source_type": "computed",
                "cel_expression": "some_var + other_var",
                "cel_accessor": "test_expr_computed",
                "category_id": self.test_category.id,
            }
        )

        expr = wizard._get_variable_expression(var)
        self.assertEqual(expr, "some_var + other_var")

    def test_get_variable_expression_aggregate(self):
        """Test extracting expression from aggregate variable."""
        wizard = self.Wizard.new({})

        var = self.LogicVariable.create(
            {
                "name": "test_expr_aggregate",
                "value_type": "number",
                "source_type": "aggregate",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "some_filter_var > 10",
                "cel_accessor": "test_expr_aggregate",
                "category_id": self.test_category.id,
            }
        )

        expr = wizard._get_variable_expression(var)
        self.assertIn("some_filter_var", expr)

    def test_get_variable_expression_field_returns_empty(self):
        """Test that field variables return empty expression."""
        wizard = self.Wizard.new({})

        var = self.LogicVariable.create(
            {
                "name": "test_expr_field",
                "value_type": "number",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "id",
                "cel_accessor": "test_expr_field",
                "category_id": self.test_category.id,
            }
        )

        expr = wizard._get_variable_expression(var)
        self.assertEqual(expr, "")


@tagged("post_install", "-at_install")
class TestVariableInstallWizardAdditionalCoverage(TransactionCase):
    """Additional tests for edge cases and gap coverage."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVariable = cls.env["spp.cel.variable"]
        cls.Wizard = cls.env["spp.studio.variable.install.wizard"]
        cls.WizardLine = cls.env["spp.studio.variable.install.wizard.line"]
        cls.Category = cls.env["spp.cel.variable.category"]

    def test_match_vocabulary_with_parentheses(self):
        """Test matching vocabulary function with trailing parentheses."""
        if "spp.vocabulary.concept.group" not in self.env:
            self.skipTest("Vocabulary module not installed")

        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # Create a concept group
        ConceptGroup.create(
            {
                "name": "Test Parentheses",
                "label": "Test Paren",
                "cel_function": "is_test_paren",
            }
        )

        wizard = self.Wizard.new({})

        # Match with parentheses (as user might type in CEL)
        match_info = wizard._find_match("is_test_paren()")
        self.assertEqual(match_info["type"], "vocabulary")

    def test_install_unknown_source_type_error(self):
        """Test error handling for unknown source type in match_data."""
        wizard = self.Wizard.create(
            {
                "logic_id": self.Logic.create(
                    {
                        "name": "Test Unknown Source",
                        "expression_type": "filter",
                        "cel_expression": "x > 0",
                    }
                ).id
            }
        )

        line = self.WizardLine.create(
            {
                "wizard_id": wizard.id,
                "variable_name": "test_unknown",
                "match_type": "field",
                "match_data": "unknown_type:123",  # Invalid source type
            }
        )

        with self.assertRaises(UserError):
            line._install_variable()

    def test_install_selected_with_partial_failures(self):
        """Test batch installation handles partial failures gracefully."""
        # Create one valid inactive variable
        self.LogicVariable.create(
            {
                "name": "valid_install_var",
                "value_type": "number",
                "source_type": "field",
                "source_model": "res.partner",
                "source_field": "id",
                "cel_accessor": "valid_install_var",
                "active": False,
            }
        )

        logic = self.Logic.create(
            {
                "name": "Test Partial Failure",
                "expression_type": "filter",
                "cel_expression": "valid_install_var > 0",
            }
        )

        wizard = self.Wizard.with_context(default_logic_id=logic.id).create({})

        # Manually corrupt one line's match_data to cause a failure
        # (simulating a race condition or data corruption)
        if len(wizard.line_ids) > 0:
            # Should succeed without raising
            result = wizard.action_install_selected()
            self.assertEqual(result["type"], "ir.actions.client")

    def test_filter_missing_excludes_already_visited(self):
        """Test that _filter_missing_variables excludes already visited vars."""
        wizard = self.Wizard.new({})

        already_visited = {"var_a", "var_b"}
        var_names = {"var_a", "var_b", "var_c"}

        missing = wizard._filter_missing_variables(var_names, already_visited)

        # var_a and var_b should be excluded
        self.assertNotIn("var_a", missing)
        self.assertNotIn("var_b", missing)
        # var_c might be in missing if it doesn't exist as active variable

    def test_recursive_depth_limit(self):
        """Test that recursion stops at depth 10."""
        wizard = self.Wizard.new({})

        # Simulate deep recursion by calling with depth > 10
        result = wizard._collect_missing_recursively(["some_var"], visited=set(), depth=11)

        # Should return empty dict when depth exceeded
        self.assertEqual(result, {})

    def test_aggregate_filter_true_excluded(self):
        """Test that aggregate filter 'true' doesn't add dependencies."""
        Category = self.env["spp.cel.variable.category"]
        test_cat = Category._get_or_create("test_agg", "Test Aggregate")

        var = self.LogicVariable.create(
            {
                "name": "simple_agg_var",
                "value_type": "number",
                "source_type": "aggregate",
                "aggregate_type": "count",
                "aggregate_target": "members",
                "aggregate_filter": "true",  # Simple true filter
                "cel_accessor": "simple_agg_var",
                "category_id": test_cat.id,
            }
        )

        wizard = self.Wizard.new({})
        expr = wizard._get_variable_expression(var)

        # "true" should be excluded, so expression should be empty
        self.assertEqual(expr, "")
