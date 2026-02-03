import html
import logging

from odoo import Command, _, api, fields, models

_logger = logging.getLogger(__name__)


class CELBuilderWizard(models.TransientModel):
    """Wizard for building CEL expressions with a friendly UI."""

    _name = "spp.cel.builder.wizard"
    _description = "CEL Expression Builder"

    eligibility_manager_id = fields.Many2one(
        "spp.program.membership.manager.default",
        string="Eligibility Manager",
    )

    compliance_manager_id = fields.Many2one(
        "spp.compliance.manager.default",
        string="Compliance Manager",
    )

    target_type = fields.Selection(
        selection=[
            ("individual", "Individuals"),
            ("group", "Groups/Households"),
        ],
        string="Target Type",
        default="group",
        required=True,
    )

    cel_expression = fields.Text(
        string="CEL Expression",
        help="Enter your eligibility expression here",
    )

    # Preview results
    preview_count = fields.Integer(string="Matching Records", readonly=True)
    preview_explain = fields.Text(string="Expression Explanation", readonly=True)
    preview_error = fields.Text(string="Error", readonly=True)
    is_valid = fields.Boolean(string="Valid", readonly=True)

    # Help content - computed based on target type
    available_symbols = fields.Html(string="Available Symbols", compute="_compute_help_content")
    available_functions = fields.Html(string="Available Functions", compute="_compute_help_content")
    example_expressions = fields.Html(string="Examples", compute="_compute_help_content")

    # Sample records for preview
    sample_ids = fields.Many2many("res.partner", string="Sample Matches", readonly=True)

    @api.depends("target_type")
    def _compute_help_content(self):
        for rec in self:
            if rec.target_type == "group":
                rec.available_symbols = rec._get_group_symbols_html()
                rec.available_functions = rec._get_functions_html()
                rec.example_expressions = rec._get_group_examples_html()
            else:
                rec.available_symbols = rec._get_individual_symbols_html()
                rec.available_functions = rec._get_functions_html()
                rec.example_expressions = rec._get_individual_examples_html()

    def _get_group_symbols_html(self):
        """Get help content for group symbols, using QWeb template if available."""
        try:
            return self.env["ir.qweb"]._render("spp_programs.cel_help_symbols_groups")
        except Exception:
            # Fallback to inline HTML if template not found
            return """
            <div class="cel-help-section">
                <h5>Registrant Fields (r.)</h5>
                <ul>
                    <li><code>r.name</code> - Registrant name</li>
                    <li><code>r.disabled</code> - Is disabled</li>
                </ul>
                <h5>Metrics</h5>
                <ul>
                    <li><code>metric("household.size")</code> - Number of household members</li>
                    <li><code>metric("scoring.&lt;code&gt;")</code> - Scoring result (e.g., PMT score)</li>
                </ul>
                <h5>Household Members (members.)</h5>
                <ul>
                    <li><code>members.exists(m, condition)</code> - Check if any member matches</li>
                    <li><code>members.count(m, condition)</code> - Count members matching</li>
                </ul>
                <h5>Member Fields (m.)</h5>
                <ul>
                    <li><code>m.birthdate</code> - Birth date</li>
                    <li><code>m.gender</code> - Gender (male/female)</li>
                    <li><code>m.disabled</code> - Is disabled</li>
                    <li><code>head(m)</code> - Is head of household</li>
                </ul>
                <h5>Enrollments &amp; Entitlements</h5>
                <ul>
                    <li><code>enrollments.exists(e, condition)</code> - Has enrollment</li>
                    <li><code>entitlements.exists(e, condition)</code> - Has entitlement</li>
                </ul>
            </div>
            """

    def _get_individual_symbols_html(self):
        """Get help content for individual symbols, using QWeb template if available."""
        try:
            return self.env["ir.qweb"]._render("spp_programs.cel_help_symbols_individuals")
        except Exception:
            # Fallback to inline HTML if template not found
            return """
            <div class="cel-help-section">
                <h5>Registrant Fields (r.)</h5>
                <ul>
                    <li><code>r.name</code> - Registrant name</li>
                    <li><code>r.birthdate</code> - Birth date</li>
                    <li><code>r.gender</code> - Gender (male/female)</li>
                    <li><code>r.disabled</code> - Is disabled</li>
                    <li><code>r.phone</code> - Phone number</li>
                    <li><code>r.email</code> - Email address</li>
                </ul>
                <h5>Enrollments &amp; Entitlements</h5>
                <ul>
                    <li><code>enrollments.exists(e, condition)</code> - Has enrollment</li>
                    <li><code>entitlements.exists(e, condition)</code> - Has entitlement</li>
                </ul>
            </div>
            """

    def _get_functions_html(self):
        """Get help content for functions, using QWeb template if available."""
        try:
            return self.env["ir.qweb"]._render("spp_programs.cel_help_functions")
        except Exception:
            # Fallback to inline HTML if template not found
            return """
            <div class="cel-help-section">
                <h5>Date Functions</h5>
                <ul>
                    <li><code>age_years(date)</code> - Calculate age in years</li>
                    <li><code>today()</code> - Current date</li>
                    <li><code>days_ago(n)</code> - Date n days ago</li>
                    <li><code>months_ago(n)</code> - Date n months ago</li>
                    <li><code>years_ago(n)</code> - Date n years ago</li>
                </ul>
                <h5>Logical Operators</h5>
                <ul>
                    <li><code>and</code> - Both conditions must be true</li>
                    <li><code>or</code> - Either condition can be true</li>
                    <li><code>not</code> - Negate a condition</li>
                </ul>
                <h5>Comparison Operators</h5>
                <ul>
                    <li><code>==</code> - Equal to</li>
                    <li><code>!=</code> - Not equal to</li>
                    <li><code>&gt;</code>, <code>&gt;=</code> - Greater than (or equal)</li>
                    <li><code>&lt;</code>, <code>&lt;=</code> - Less than (or equal)</li>
                    <li><code>in</code> - Value in list</li>
                </ul>
                <h5>Metrics (if spp_indicators installed)</h5>
                <ul>
                    <li><code>metric("name")</code> - Get metric value</li>
                    <li><code>metric("household.size")</code> - Household size metric</li>
                </ul>
            </div>
            """

    def _get_group_examples_html(self, category="eligibility"):
        """Get examples HTML filtered by target type and category."""
        domain = [
            ("target_type", "in", ["group", "both"]),
            ("category", "=", category),
        ]
        examples = self.env["spp.cel.example"].search(domain)
        if not examples:
            return self._get_default_group_examples_html()

        result = '<div class="cel-examples">'
        for ex in examples:
            name = html.escape(ex.name or "")
            expression = html.escape(ex.expression or "")
            description = html.escape(ex.description or "")
            result += f"""
            <div class="cel-example-item mb-2">
                <strong>{name}</strong><br/>
                <code class="cel-clickable" data-expr="{expression}">{expression}</code>
                <p class="text-muted small mb-0">{description}</p>
            </div>
            """
        result += "</div>"
        return result

    def _get_default_group_examples_html(self):
        """Get default examples for groups, using QWeb template if available."""
        try:
            return self.env["ir.qweb"]._render("spp_programs.cel_default_examples_groups")
        except Exception:
            # Fallback to inline HTML if template not found
            return """
            <div class="cel-examples">
                <div class="cel-example-item mb-2">
                    <strong>Households with elderly head</strong><br/>
                    <code class="cel-clickable" data-expr='members.exists(m, head(m) and age_years(m.birthdate) >= 60)'>members.exists(m, head(m) and age_years(m.birthdate) >= 60)</code>
                </div>
                <div class="cel-example-item mb-2">
                    <strong>Households with children under 5</strong><br/>
                    <code class="cel-clickable" data-expr='members.exists(m, age_years(m.birthdate) < 5)'>members.exists(m, age_years(m.birthdate) < 5)</code>
                </div>
                <div class="cel-example-item mb-2">
                    <strong>Female-headed households</strong><br/>
                    <code class="cel-clickable" data-expr='members.exists(m, head(m) and m.gender == "female")'>members.exists(m, head(m) and m.gender == "female")</code>
                </div>
                <div class="cel-example-item mb-2">
                    <strong>Households with 2+ children</strong><br/>
                    <code class="cel-clickable" data-expr='members.count(m, age_years(m.birthdate) < 18) >= 2'>members.count(m, age_years(m.birthdate) < 18) >= 2</code>
                </div>
                <div class="cel-example-item mb-2">
                    <strong>Households with disabled member</strong><br/>
                    <code class="cel-clickable" data-expr='members.exists(m, m.disabled == true)'>members.exists(m, m.disabled == true)</code>
                </div>
            </div>
            """

    def _get_individual_examples_html(self, category="eligibility"):
        """Get examples HTML filtered by target type and category."""
        domain = [
            ("target_type", "in", ["individual", "both"]),
            ("category", "=", category),
        ]
        examples = self.env["spp.cel.example"].search(domain)
        if not examples:
            return self._get_default_individual_examples_html()

        result = '<div class="cel-examples">'
        for ex in examples:
            name = html.escape(ex.name or "")
            expression = html.escape(ex.expression or "")
            description = html.escape(ex.description or "")
            result += f"""
            <div class="cel-example-item mb-2">
                <strong>{name}</strong><br/>
                <code class="cel-clickable" data-expr="{expression}">{expression}</code>
                <p class="text-muted small mb-0">{description}</p>
            </div>
            """
        result += "</div>"
        return result

    def _get_default_individual_examples_html(self):
        """Get default examples for individuals, using QWeb template if available."""
        try:
            return self.env["ir.qweb"]._render("spp_programs.cel_default_examples_individuals")
        except Exception:
            # Fallback to inline HTML if template not found
            return """
            <div class="cel-examples">
                <div class="cel-example-item mb-2">
                    <strong>Adults (18 or older)</strong><br/>
                    <code class="cel-clickable" data-expr='age_years(r.birthdate) >= 18'>age_years(r.birthdate) >= 18</code>
                </div>
                <div class="cel-example-item mb-2">
                    <strong>Senior citizens</strong><br/>
                    <code class="cel-clickable" data-expr='age_years(r.birthdate) >= 60'>age_years(r.birthdate) >= 60</code>
                </div>
                <div class="cel-example-item mb-2">
                    <strong>Women of reproductive age</strong><br/>
                    <code class="cel-clickable" data-expr='r.gender == "female" and age_years(r.birthdate) >= 15 and age_years(r.birthdate) <= 49'>r.gender == "female" and age_years(r.birthdate) >= 15 and age_years(r.birthdate) <= 49</code>
                </div>
                <div class="cel-example-item mb-2">
                    <strong>Children under 5</strong><br/>
                    <code class="cel-clickable" data-expr='age_years(r.birthdate) < 5'>age_years(r.birthdate) < 5</code>
                </div>
            </div>
            """

    def action_validate(self):
        """Validate the CEL expression and show preview."""
        self.ensure_one()
        self._validate_expression()

        if self.preview_error:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Expression Error"),
                    "message": self.preview_error,
                    "type": "danger",
                    "sticky": True,
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Expression Valid"),
                "message": _("%d records match this expression.") % self.preview_count,
                "type": "success",
                "sticky": False,
            },
        }

    def _validate_expression(self):
        """Validate the expression and populate preview fields."""
        self.preview_count = 0
        self.preview_explain = ""
        self.preview_error = ""
        self.is_valid = False
        self.sample_ids = [Command.clear()]

        if not self.cel_expression:
            self.preview_error = _("Please enter an expression")
            return

        try:
            profile = "registry_groups" if self.target_type == "group" else "registry_individuals"
            base_domain = [["disabled", "=", False]]

            service = self.env["spp.cel.service"]
            result = service.compile_expression(self.cel_expression, profile=profile, base_domain=base_domain, limit=10)

            if result.get("valid"):
                self.preview_count = result.get("count", 0)
                self.preview_explain = result.get("explain", "")
                self.is_valid = True

                # Set sample records
                sample_ids = result.get("ids", [])[:10]
                if sample_ids:
                    self.sample_ids = [Command.set(sample_ids)]
            else:
                self.preview_error = result.get("error", _("Unknown error"))

        except Exception as e:
            self.preview_error = _("Error: %s") % str(e)

    @api.onchange("cel_expression")
    def _onchange_cel_expression(self):
        """Auto-validate on expression change."""
        if self.cel_expression:
            self._validate_expression()

    def action_apply(self):
        """Apply the expression to the eligibility or compliance manager and close wizard."""
        self.ensure_one()
        self._validate_expression()

        if not self.is_valid:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Cannot Apply"),
                    "message": self.preview_error or _("Expression is not valid"),
                    "type": "danger",
                    "sticky": True,
                },
            }

        # Update the appropriate manager
        if self.compliance_manager_id:
            # Update compliance manager
            self.compliance_manager_id.write(
                {
                    "compliance_cel_expression": self.cel_expression,
                    "compliance_cel_mode": "cel",
                }
            )
        elif self.eligibility_manager_id:
            # Update eligibility manager
            self.eligibility_manager_id.write(
                {
                    "cel_expression": self.cel_expression,
                    "eligibility_mode": "cel",
                }
            )
        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Cannot Apply"),
                    "message": _("No manager specified"),
                    "type": "danger",
                    "sticky": True,
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Expression Applied"),
                "message": _("CEL expression has been saved. %d records match.") % self.preview_count,
                "type": "success",
                "sticky": False,
            },
        }

    def action_preview_records(self):
        """Open a list view of matching records."""
        self.ensure_one()
        self._validate_expression()

        if not self.is_valid:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Cannot Preview"),
                    "message": self.preview_error or _("Expression is not valid"),
                    "type": "danger",
                    "sticky": True,
                },
            }

        try:
            profile = "registry_groups" if self.target_type == "group" else "registry_individuals"
            base_domain = [["disabled", "=", False]]

            service = self.env["spp.cel.service"]
            result = service.compile_expression(
                self.cel_expression,
                profile=profile,
                base_domain=base_domain,
                limit=0,
                materialize_sql=True,  # Required for window actions - domain must be serializable
            )

            if not result.get("valid"):
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Preview Error"),
                        "message": result.get("error", _("Unknown error")),
                        "type": "danger",
                        "sticky": True,
                    },
                }

            return {
                "type": "ir.actions.act_window",
                "name": _("Matching Records (%d)") % result.get("count", 0),
                "res_model": "res.partner",
                "view_mode": "list,form",
                "domain": result.get("domain", []),
                "target": "new",
                "context": {"create": False},
            }
        except Exception as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Preview Error"),
                    "message": str(e),
                    "type": "danger",
                    "sticky": True,
                },
            }


class CELExampleExpression(models.Model):
    """Store example CEL expressions for the builder wizard."""

    _name = "spp.cel.example"
    _description = "CEL Example Expression"
    _order = "sequence, name"

    name = fields.Char(string="Name", required=True)
    expression = fields.Text(string="Expression", required=True)
    description = fields.Text(string="Description")
    category = fields.Selection(
        selection=[
            ("eligibility", "Eligibility Criteria"),
            ("amount", "Entitlement Amount"),
            ("condition", "Entitlement Condition"),
            ("compliance", "Compliance Criteria"),
            ("inkind_qty", "In-Kind Quantity"),
        ],
        string="Category",
        default="eligibility",
        required=True,
        help="Type of CEL expression this example is for",
    )
    target_type = fields.Selection(
        selection=[
            ("individual", "Individuals"),
            ("group", "Groups/Households"),
            ("both", "Both"),
        ],
        string="Target Type",
        default="both",
        required=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    active = fields.Boolean(string="Active", default=True)

    @api.model
    def get_examples_html(self, category, target_type=None):
        """Generate HTML for examples of a given category.

        Args:
            category: The example category (eligibility, amount, condition, compliance, inkind_qty)
            target_type: Optional filter for target type (individual, group, both)

        Returns:
            str: HTML string with clickable examples
        """
        domain = [("category", "=", category), ("active", "=", True)]
        if target_type:
            if target_type == "both":
                pass  # Show all
            else:
                domain.append(("target_type", "in", [target_type, "both"]))

        examples = self.search(domain, order="sequence, name")
        if not examples:
            return '<p class="text-muted">No examples available for this category.</p>'

        result = '<div class="cel-examples">'
        for ex in examples:
            name = html.escape(ex.name or "")
            expression = html.escape(ex.expression or "")
            description = html.escape(ex.description or "")
            result += f"""
            <div class="cel-example-item mb-2 p-2 border-bottom">
                <strong>{name}</strong><br/>
                <code class="cel-clickable text-primary" style="cursor: pointer;"
                      data-expr="{expression}" title="Click to use this expression">
                    {expression}
                </code>
                <p class="text-muted small mb-0">{description}</p>
            </div>
            """
        result += "</div>"
        return result

    @api.model
    def get_examples_for_selection(self, category, target_type=None):
        """Get examples as a list of dicts for selection widgets.

        Args:
            category: The example category
            target_type: Optional filter for target type

        Returns:
            list: List of dicts with id, name, expression, description
        """
        domain = [("category", "=", category), ("active", "=", True)]
        if target_type and target_type != "both":
            domain.append(("target_type", "in", [target_type, "both"]))

        examples = self.search(domain, order="sequence, name")
        return [
            {
                "id": ex.id,
                "name": ex.name,
                "expression": ex.expression,
                "description": ex.description,
            }
            for ex in examples
        ]
