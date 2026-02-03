# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Variable Install Wizard for Logic Studio.

This wizard helps users install missing variables referenced in logic expressions.
It automatically matches variable names against available sources and allows
batch installation of matching variables.
"""

import logging
import re

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.spp_cel_domain.services.cel_parser import Lexer

_logger = logging.getLogger(__name__)


class VariableInstallWizard(models.TransientModel):
    """Wizard to install missing variables for a logic definition.

    This wizard:
    1. Parses the logic's missing variables
    2. Attempts to match each against available sources
    3. Allows batch installation of matching variables
    4. Provides creation action for unmatched variables
    """

    _name = "spp.studio.variable.install.wizard"
    _description = "Install Missing Variables Wizard"

    logic_id = fields.Many2one(
        comodel_name="spp.cel.expression",
        string="Logic",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    logic_name = fields.Char(
        related="logic_id.name",
        string="Logic Name",
    )
    line_ids = fields.One2many(
        comodel_name="spp.studio.variable.install.wizard.line",
        inverse_name="wizard_id",
        string="Missing Variables",
    )

    # Summary fields
    total_missing = fields.Integer(
        string="Total Missing",
        compute="_compute_summary",
    )
    installable_count = fields.Integer(
        string="Installable",
        compute="_compute_summary",
    )
    selected_count = fields.Integer(
        string="Selected",
        compute="_compute_summary",
    )

    @api.depends("line_ids", "line_ids.match_type", "line_ids.selected")
    def _compute_summary(self):
        """Compute summary statistics."""
        for wizard in self:
            wizard.total_missing = len(wizard.line_ids)
            wizard.installable_count = len(wizard.line_ids.filtered(lambda line: line.match_type != "none"))
            wizard.selected_count = len(wizard.line_ids.filtered(lambda line: line.selected))

    @api.model
    def default_get(self, fields_list):
        """Populate lines from logic's missing variables.

        This method recursively discovers all missing variables, including
        transitive dependencies from computed/aggregate variables.
        """
        res = super().default_get(fields_list)

        logic_id = self.env.context.get("default_logic_id")
        if not logic_id:
            return res

        logic = self.env["spp.cel.expression"].browse(logic_id)
        if not logic.exists():
            return res

        # Parse missing variables
        missing_vars = logic.missing_variables or ""
        if not missing_vars:
            return res

        initial_var_names = [v.strip() for v in missing_vars.split(",") if v.strip()]

        # Recursively collect all missing variables including dependencies
        all_missing = self._collect_missing_recursively(initial_var_names)

        # Build lines with match information
        # Pass the logic's context_type to filter matches appropriately
        context_type = logic.context_type or "both"
        lines = []
        for var_name, is_dependency in all_missing.items():
            match_info = self._find_match(var_name, context_type)
            lines.append(
                Command.create(
                    {
                        "variable_name": var_name,
                        "match_type": match_info["type"],
                        "match_source": match_info["source"],
                        "match_details": match_info["details"],
                        "selected": match_info["type"] != "none",
                        "match_data": match_info.get("data", ""),
                        "is_dependency": is_dependency,
                    }
                )
            )

        res["line_ids"] = lines
        return res

    def _collect_missing_recursively(self, var_names, visited=None, depth=0):
        """Recursively collect all missing variables including dependencies.

        When a matched variable is computed/aggregate, its expression may
        reference other variables that are also missing. This method
        discovers the full dependency tree.

        Args:
            var_names: List of variable names to check
            visited: Set of already visited variable names (prevents cycles)
            depth: Current recursion depth (max 10 to prevent infinite loops)

        Returns:
            dict: {var_name: is_dependency} where is_dependency is True for
                  transitive dependencies (not directly in the logic expression)
        """
        if visited is None:
            visited = set()

        if depth > 10:
            _logger.warning("Max recursion depth reached in variable dependency detection")
            return {}

        Variable = self.env["spp.cel.variable"]
        result = {}

        for var_name in var_names:
            if var_name in visited:
                continue
            visited.add(var_name)

            # Add this variable (is_dependency=False for initial vars, True for nested)
            is_dependency = depth > 0
            result[var_name] = is_dependency

            # Check if this variable matches an existing variable with an expression
            existing = Variable.with_context(active_test=False).search(
                [
                    "|",
                    ("name", "=", var_name),
                    ("cel_accessor", "=", var_name),
                ],
                limit=1,
            )

            if existing:
                # Get the variable's CEL expression (if computed/aggregate)
                nested_expr = self._get_variable_expression(existing)
                if nested_expr:
                    # Extract potential variables from the expression
                    nested_vars = self._extract_variables_from_expression(nested_expr)
                    # Filter to only include missing ones
                    missing_nested = self._filter_missing_variables(nested_vars, visited)
                    if missing_nested:
                        # Recursively collect dependencies
                        nested_result = self._collect_missing_recursively(missing_nested, visited, depth + 1)
                        result.update(nested_result)

        return result

    def _get_variable_expression(self, variable):
        """Get the CEL expression from a variable if it has one.

        Args:
            variable: spp.cel.variable record

        Returns:
            str: CEL expression or empty string
        """
        if variable.source_type == "computed":
            return variable.cel_expression or ""
        elif variable.source_type == "aggregate":
            # Aggregate variables have filter and field expressions
            expressions = []
            if variable.aggregate_filter and variable.aggregate_filter != "true":
                expressions.append(variable.aggregate_filter)
            if variable.aggregate_field:
                expressions.append(variable.aggregate_field)
            return " ".join(expressions)
        return ""

    def _extract_variables_from_expression(self, expression):
        """Extract potential variable names from a CEL expression.

        Uses the CEL lexer to properly tokenize the expression, which correctly
        handles string literals, numbers, and other tokens. Only IDENT tokens
        are returned as potential variable names.

        Args:
            expression: CEL expression string

        Returns:
            set: Potential variable names
        """
        if not expression:
            return set()

        # Use the variable resolver service to get reserved words dynamically
        resolver = self.env["spp.cel.variable.resolver"]
        reserved_words = resolver._get_reserved_words()

        try:
            lexer = Lexer(expression)
            tokens = lexer.tokens()
            # Extract only IDENT tokens - these are the potential variable names
            # STRING, NUMBER, BOOL tokens are literals, not variables
            potential_vars = {tok.value for tok in tokens if tok.kind == "IDENT"}
            return potential_vars - reserved_words
        except SyntaxError:
            # Fall back to regex if lexer fails on malformed expressions
            _logger.debug("Lexer failed on expression, falling back to regex: %s", expression)
            var_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b"
            potential_vars = set(re.findall(var_pattern, expression))
            return potential_vars - reserved_words

    def _filter_missing_variables(self, var_names, already_visited):
        """Filter variable names to only those that are missing.

        Args:
            var_names: Set of variable names to check
            already_visited: Set of variables already being processed

        Returns:
            list: Variable names that are missing from the dictionary
        """
        Variable = self.env["spp.cel.variable"]
        missing = []

        for var_name in var_names:
            if var_name in already_visited:
                continue

            # Check if variable exists and is active
            existing = Variable.search(
                [
                    "|",
                    ("name", "=", var_name),
                    ("cel_accessor", "=", var_name),
                    ("active", "=", True),
                    ("state", "=", "active"),
                ],
                limit=1,
            )

            if not existing:
                missing.append(var_name)

        return missing

    def _is_context_compatible(self, var_context, logic_context):
        """Check if a variable's context is compatible with the logic's context.

        Args:
            var_context: The variable's applies_to value ('individual', 'group', 'both')
            logic_context: The logic's context_type ('individual', 'group', 'both')

        Returns:
            bool: True if compatible, False otherwise
        """
        # If either is 'both', they're compatible
        if var_context == "both" or logic_context == "both":
            return True
        # Otherwise must match exactly
        return var_context == logic_context

    def _find_match(self, var_name, context_type="both"):
        """Find a matching source for a variable name.

        Checks sources in order of priority:
        1. Existing inactive/draft variables (with compatible context)
        2. Standard variables (XML data)
        3. res.partner fields
        4. Vocabulary concept groups
        5. Indicator definitions
        6. Scoring models

        Args:
            var_name: The variable name to match
            context_type: The logic's context ('individual', 'group', or 'both')

        Returns:
            dict: Match info with keys: type, source, details, data
        """
        # 1. Check for existing variable (might be inactive or draft)
        Variable = self.env["spp.cel.variable"]
        existing = Variable.with_context(active_test=False).search(
            [
                "|",
                ("name", "=", var_name),
                ("cel_accessor", "=", var_name),
            ],
            limit=1,
        )

        if existing:
            # Check context compatibility
            is_compatible = self._is_context_compatible(existing.applies_to, context_type)

            if existing.active and existing.state == "active":
                if is_compatible:
                    # Already active and compatible - shouldn't be in missing list
                    return {
                        "type": "existing_active",
                        "source": f"Variable: {existing.label or existing.name}",
                        "details": "Already exists and is active",
                        "data": f"existing:{existing.id}",
                    }
                else:
                    # Active but wrong context
                    return {
                        "type": "wrong_context",
                        "source": f"Variable: {existing.label or existing.name}",
                        "details": f"Exists but for {existing.applies_to} context (need {context_type})",
                        "data": "",
                    }
            else:
                if is_compatible:
                    return {
                        "type": "existing_inactive",
                        "source": f"Variable: {existing.label or existing.name}",
                        "details": f"Exists but {'inactive' if not existing.active else 'in draft state'}",
                        "data": f"existing:{existing.id}",
                    }
                else:
                    # Inactive and wrong context
                    return {
                        "type": "wrong_context",
                        "source": f"Variable: {existing.label or existing.name}",
                        "details": f"Exists but for {existing.applies_to} context (need {context_type})",
                        "data": "",
                    }

        # 2. Check standard variables by XML ID pattern
        standard_match = self._match_standard_variable(var_name)
        if standard_match:
            return standard_match

        # 3. Check res.partner fields
        field_match = self._match_partner_field(var_name)
        if field_match:
            return field_match

        # 4. Check vocabulary concept groups
        vocab_match = self._match_vocabulary(var_name)
        if vocab_match:
            return vocab_match

        # 5. Check indicator definitions
        indicator_match = self._match_indicator(var_name)
        if indicator_match:
            return indicator_match

        # 6. Check scoring models
        scoring_match = self._match_scoring(var_name)
        if scoring_match:
            return scoring_match

        # No match found
        return {
            "type": "none",
            "source": "",
            "details": "No automatic match found. Create manually.",
            "data": "",
        }

    def _match_standard_variable(self, var_name):
        """Check if variable matches a standard variable XML ID.

        Standard variables are defined in data/standard_variables.xml
        and may not yet be loaded if module was recently updated.
        """
        # Common standard variable names and their XML IDs
        standard_vars = {
            "age": "var_age",
            "hh_size": "var_hh_size",
            "child_count": "var_child_count",
            "elderly_count": "var_elderly_count",
            "working_age_count": "var_working_age_count",
            "dependency_ratio": "var_dependency_ratio",
            "income": "var_income_individual",
            "hh_income": "var_income_group",
            "total_income": "var_hh_total_income",
            "avg_income": "var_hh_avg_income",
            "benefit_amount": "var_benefit_amount",
        }

        if var_name in standard_vars:
            xml_id = f"spp_studio.{standard_vars[var_name]}"
            # Check if XML ID exists
            try:
                record = self.env.ref(xml_id, raise_if_not_found=False)
                if record:
                    return {
                        "type": "standard",
                        "source": f"Standard: {record.label or record.name}",
                        "details": f"Pre-defined variable (XML ID: {xml_id})",
                        "data": f"standard:{record.id}",
                    }
            except Exception:
                pass

        return None

    def _match_partner_field(self, var_name):
        """Check if variable matches a res.partner field."""
        try:
            Partner = self.env["res.partner"]
            partner_fields = Partner.fields_get()

            # Direct field name match
            if var_name in partner_fields:
                field_info = partner_fields[var_name]
                # Skip technical field types
                if field_info.get("type") in ["one2many", "many2many", "binary"]:
                    return None

                return {
                    "type": "field",
                    "source": f"Field: res.partner.{var_name}",
                    "details": f"{field_info.get('string', var_name)} ({field_info.get('type', 'unknown')})",
                    "data": f"field:{var_name}",
                }

            # Also check for x_cst_ prefixed custom fields without prefix
            custom_field_name = f"x_cst_{var_name}"
            if custom_field_name in partner_fields:
                field_info = partner_fields[custom_field_name]
                return {
                    "type": "field",
                    "source": f"Field: res.partner.{custom_field_name}",
                    "details": f"Custom field: {field_info.get('string', var_name)}",
                    "data": f"field:{custom_field_name}",
                }

        except Exception:
            _logger.exception("Error checking partner fields")

        return None

    def _match_vocabulary(self, var_name):
        """Check if variable matches a vocabulary concept group."""
        if "spp.vocabulary.concept.group" not in self.env:
            return None

        try:
            ConceptGroup = self.env["spp.vocabulary.concept.group"]

            # Try exact match on cel_function
            group = ConceptGroup.search(
                [
                    ("cel_function", "=", var_name),
                ],
                limit=1,
            )

            if group:
                return {
                    "type": "vocabulary",
                    "source": f"Vocabulary: {group.label or group.name}",
                    "details": f"Concept group with CEL function: {group.cel_function}",
                    "data": f"vocabulary:{group.id}",
                }

            # Try without parentheses if var_name has them
            clean_name = var_name.rstrip("()")
            if clean_name != var_name:
                group = ConceptGroup.search(
                    [
                        ("cel_function", "=", clean_name),
                    ],
                    limit=1,
                )
                if group:
                    return {
                        "type": "vocabulary",
                        "source": f"Vocabulary: {group.label or group.name}",
                        "details": f"Concept group: {group.cel_function}",
                        "data": f"vocabulary:{group.id}",
                    }

        except Exception:
            _logger.exception("Error checking vocabulary")

        return None

    def _match_indicator(self, var_name):
        """Check if variable matches an indicator definition."""
        if "spp.indicator.definition" not in self.env:
            return None

        try:
            Indicator = self.env["spp.indicator.definition"]

            # Extract indicator name from metric("name") pattern
            metric_match = re.match(r'metric\(["\']([^"\']+)["\']\)', var_name)
            if metric_match:
                indicator_name = metric_match.group(1)
            else:
                indicator_name = var_name

            # Search for indicator
            indicator = Indicator.search(
                [
                    ("name", "=", indicator_name),
                    ("active", "=", True),
                ],
                limit=1,
            )

            if indicator:
                return {
                    "type": "indicator",
                    "source": f"Indicator: {indicator.name}",
                    "details": indicator.description or "Indicator definition",
                    "data": f"indicator:{indicator.id}",
                }

        except Exception:
            _logger.exception("Error checking indicators")

        return None

    def _match_scoring(self, var_name):
        """Check if variable matches a scoring model."""
        if "spp.scoring.model" not in self.env:
            return None

        try:
            ScoringModel = self.env["spp.scoring.model"]

            # Extract code from score("code") or classification("code") patterns
            score_match = re.match(r'score\(["\']([^"\']+)["\']\)', var_name)
            class_match = re.match(r'classification\(["\']([^"\']+)["\']\)', var_name)

            if score_match:
                code = score_match.group(1)
                var_type = "score"
            elif class_match:
                code = class_match.group(1)
                var_type = "classification"
            else:
                # Check if name ends with _score or _classification
                if var_name.endswith("_score"):
                    code = var_name[:-6]  # Remove "_score"
                    var_type = "score"
                elif var_name.endswith("_classification"):
                    code = var_name[:-15]  # Remove "_classification"
                    var_type = "classification"
                else:
                    code = var_name
                    var_type = "score"

            # Search for scoring model
            model = ScoringModel.search(
                [
                    ("code", "=", code),
                    ("is_active", "=", True),
                ],
                limit=1,
            )

            if model:
                return {
                    "type": "scoring",
                    "source": f"Scoring: {model.name}",
                    "details": f"Create {var_type} variable from scoring model",
                    "data": f"scoring:{model.id}:{var_type}",
                }

        except Exception:
            _logger.exception("Error checking scoring models")

        return None

    def action_install_selected(self):
        """Install all selected variables."""
        self.ensure_one()

        selected_lines = self.line_ids.filtered(lambda line: line.selected and line.match_type != "none")

        if not selected_lines:
            raise UserError(_("No installable variables selected."))

        # Sort lines: dependencies first, then direct variables
        # This ensures that if Variable A depends on Variable B,
        # Variable B gets installed first
        sorted_lines = selected_lines.sorted(key=lambda line: (not line.is_dependency, line.id))

        installed_count = 0
        errors = []

        for line in sorted_lines:
            try:
                line._install_variable()
                installed_count += 1
            except Exception as e:
                errors.append(f"{line.variable_name}: {str(e)}")
                _logger.exception("Failed to install variable %s", line.variable_name)

        # Build result message
        if errors:
            message = _(
                "Installed %(count)d variable(s). %(error_count)d error(s):\n%(errors)s",
                count=installed_count,
                error_count=len(errors),
                errors="\n".join(errors),
            )
            msg_type = "warning"
        else:
            message = _("Successfully installed %d variable(s).") % installed_count
            msg_type = "success"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Variables Installed"),
                "message": message,
                "type": msg_type,
                "sticky": bool(errors),
            },
        }

    def action_select_all(self):
        """Select all installable lines."""
        self.ensure_one()
        self.line_ids.filtered(lambda line: line.match_type != "none").write({"selected": True})
        return self._reopen_wizard()

    def action_deselect_all(self):
        """Deselect all lines."""
        self.ensure_one()
        self.line_ids.write({"selected": False})
        return self._reopen_wizard()

    def _reopen_wizard(self):
        """Reopen the wizard to show updated state."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class VariableInstallWizardLine(models.TransientModel):
    """Line item for variable installation wizard."""

    _name = "spp.studio.variable.install.wizard.line"
    _description = "Variable Install Wizard Line"

    wizard_id = fields.Many2one(
        comodel_name="spp.studio.variable.install.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    variable_name = fields.Char(
        string="Variable Name",
        required=True,
        readonly=True,
    )
    match_type = fields.Selection(
        selection=[
            ("existing_active", "Already Active"),
            ("existing_inactive", "Existing (Inactive)"),
            ("wrong_context", "Wrong Context"),
            ("standard", "Standard Variable"),
            ("field", "Model Field"),
            ("vocabulary", "Vocabulary Concept"),
            ("indicator", "Indicator"),
            ("scoring", "Scoring Model"),
            ("none", "No Match"),
        ],
        string="Match Type",
        readonly=True,
    )
    match_source = fields.Char(
        string="Source",
        readonly=True,
    )
    match_details = fields.Char(
        string="Details",
        readonly=True,
    )
    match_data = fields.Char(
        string="Match Data",
        readonly=True,
        help="Internal data for installation",
    )
    selected = fields.Boolean(
        string="Install",
        default=False,
    )
    is_installable = fields.Boolean(
        string="Installable",
        compute="_compute_is_installable",
    )
    is_dependency = fields.Boolean(
        string="Dependency",
        default=False,
        readonly=True,
        help="True if this is a transitive dependency (required by another variable)",
    )

    @api.depends("match_type")
    def _compute_is_installable(self):
        """Check if line can be installed."""
        for line in self:
            # Cannot install if: no match, already active, or wrong context
            line.is_installable = line.match_type not in ("none", "existing_active", "wrong_context")

    def _install_variable(self):
        """Install this variable based on match type.

        Creates or activates the variable in spp.cel.variable.
        """
        self.ensure_one()

        if not self.match_data:
            raise UserError(_("No match data available for %s") % self.variable_name)

        parts = self.match_data.split(":")
        source_type = parts[0]

        Variable = self.env["spp.cel.variable"]

        try:
            if source_type == "existing":
                # Activate existing variable
                var_id = int(parts[1])
                variable = Variable.with_context(active_test=False).browse(var_id)
                if not variable.exists():
                    raise UserError(_("Variable %s not found (may have been deleted)") % self.variable_name)
                if not variable.active:
                    variable.active = True
                if hasattr(variable, "state") and variable.state == "draft":
                    variable.action_activate()
                _logger.info("Activated existing variable: %s", variable.name)
                return variable

            elif source_type == "standard":
                # Standard variable already exists, just activate if needed
                var_id = int(parts[1])
                variable = Variable.browse(var_id)
                if not variable.exists():
                    raise UserError(_("Standard variable %s not found") % self.variable_name)
                if not variable.active:
                    variable.active = True
                if hasattr(variable, "state") and variable.state == "draft":
                    variable.action_activate()
                _logger.info("Activated standard variable: %s", variable.name)
                return variable

            elif source_type == "field":
                # Create variable from res.partner field
                field_name = parts[1]
                return self._create_field_variable(field_name)

            elif source_type == "vocabulary":
                # Create variable from vocabulary concept group
                group_id = int(parts[1])
                return self._create_vocabulary_variable(group_id)

            elif source_type == "indicator":
                # Create variable from indicator
                indicator_id = int(parts[1])
                return self._create_indicator_variable(indicator_id)

            elif source_type == "scoring":
                # Create variable from scoring model
                model_id = int(parts[1])
                var_type = parts[2] if len(parts) > 2 else "score"
                return self._create_scoring_variable(model_id, var_type)

        except (ValueError, IndexError) as e:
            raise UserError(
                _("Invalid match data for %(var)s: %(error)s") % {"var": self.variable_name, "error": str(e)}
            ) from e

        raise UserError(_("Unknown source type: %s") % source_type)

    def _create_field_variable(self, field_name):
        """Create a variable from a res.partner field."""
        Partner = self.env["res.partner"]
        Variable = self.env["spp.cel.variable"]

        partner_fields = Partner.fields_get([field_name])
        if field_name not in partner_fields:
            raise UserError(_("Field %s not found on res.partner") % field_name)

        field_info = partner_fields[field_name]

        # Map Odoo field type to variable value type
        type_mapping = {
            "integer": "number",
            "float": "number",
            "monetary": "money",
            "boolean": "boolean",
            "char": "string",
            "text": "string",
            "html": "string",
            "date": "date",
            "datetime": "date",
            "selection": "string",
            "many2one": "string",
        }
        value_type = type_mapping.get(field_info.get("type"), "string")

        # Get or create demographics category
        Category = self.env["spp.cel.variable.category"]
        category = Category._get_or_create("demographics", "Demographics", icon="fa-user")

        vals = {
            "name": field_name,
            "label": field_info.get("string") or field_name.replace("_", " ").title(),
            "description": field_info.get("help") or f"Field: {field_name} from res.partner",
            "category_id": category.id,
            "value_type": value_type,
            "source_type": "field",
            "source_model": "res.partner",
            "source_field": field_name,
            "cel_accessor": field_name,
            "is_system": True,
            "data_source": "local",
        }

        variable = Variable.create(vals)
        _logger.info("Created field variable: %s", variable.name)
        return variable

    def _create_vocabulary_variable(self, group_id):
        """Create a variable from a vocabulary concept group."""
        ConceptGroup = self.env["spp.vocabulary.concept.group"]
        Variable = self.env["spp.cel.variable"]

        group = ConceptGroup.browse(group_id)
        if not group.exists():
            raise UserError(_("Concept group not found"))

        # Get or create characteristics category
        Category = self.env["spp.cel.variable.category"]
        category = Category._get_or_create("characteristics", "Characteristics", icon="fa-tags")

        vals = {
            "name": group.cel_function,
            "label": group.label or group.name,
            "description": group.description or f"True if registrant belongs to: {group.name}",
            "category_id": category.id,
            "value_type": "boolean",
            "source_type": "vocabulary",
            "source_concept_id": group.id,
            "cel_accessor": group.cel_function,
            "is_system": True,
            "data_source": "local",
        }

        variable = Variable.create(vals)
        _logger.info("Created vocabulary variable: %s", variable.name)
        return variable

    def _create_indicator_variable(self, indicator_id):
        """Create a variable from an indicator definition."""
        Indicator = self.env["spp.indicator.definition"]
        Variable = self.env["spp.cel.variable"]

        indicator = Indicator.browse(indicator_id)
        if not indicator.exists():
            raise UserError(_("Indicator not found"))

        # Get or create indicators category
        Category = self.env["spp.cel.variable.category"]
        category = Category._get_or_create("indicators", "Indicators", icon="fa-chart-line")

        # Map indicator value type
        type_mapping = {
            "number": "number",
            "string": "string",
            "json": "list",
        }
        value_type = type_mapping.get(indicator.value_type, "string")

        vals = {
            "name": indicator.name,
            "label": indicator.name.replace(".", " ").title(),
            "description": indicator.description or f"Indicator: {indicator.name}",
            "category_id": category.id,
            "value_type": value_type,
            "source_type": "external",  # External source for indicator data
            "cel_accessor": f'metric("{indicator.name}")',
            "is_system": True,
            "data_source": "external",
        }

        variable = Variable.create(vals)
        _logger.info("Created indicator variable: %s", variable.name)
        return variable

    def _create_scoring_variable(self, model_id, var_type="score"):
        """Create a variable from a scoring model."""
        ScoringModel = self.env["spp.scoring.model"]
        Variable = self.env["spp.cel.variable"]

        model = ScoringModel.browse(model_id)
        if not model.exists():
            raise UserError(_("Scoring model not found"))

        # Get or create scoring category
        Category = self.env["spp.cel.variable.category"]
        category = Category._get_or_create("scoring", "Scoring", icon="fa-calculator")

        if var_type == "score":
            vals = {
                "name": f"{model.code}_score",
                "label": f"{model.name} - Score",
                "description": f"Numeric score from {model.name}",
                "category_id": category.id,
                "value_type": "number",
                "source_type": "scoring",
                "cel_accessor": f'score("{model.code}")',
                "is_system": True,
                "data_source": "computed",
            }
        else:  # classification
            vals = {
                "name": f"{model.code}_classification",
                "label": f"{model.name} - Classification",
                "description": f"Classification label from {model.name}",
                "category_id": category.id,
                "value_type": "string",
                "source_type": "scoring",
                "cel_accessor": f'classification("{model.code}")',
                "is_system": True,
                "data_source": "computed",
            }

        # Add source_scoring_id only if field exists (from spp_studio_scoring bridge)
        if "source_scoring_id" in Variable._fields:
            vals["source_scoring_id"] = model.id

        variable = Variable.create(vals)
        _logger.info("Created scoring variable: %s", variable.name)
        return variable

    def action_create_variable(self):
        """Open variable creation form for manual creation."""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Create Variable: %s") % self.variable_name,
            "res_model": "spp.cel.variable",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_name": self.variable_name,
                "default_cel_accessor": self.variable_name,
                "default_label": self.variable_name.replace("_", " ").title(),
            },
        }
