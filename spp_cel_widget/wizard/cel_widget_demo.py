"""CEL Widget Demo - Debug-only test page for the CEL expression widget."""

from odoo import api, fields, models


class CelWidgetDemo(models.TransientModel):
    """Transient model for testing the CEL expression widget."""

    _name = "spp.cel.widget.demo"
    _description = "CEL Widget Demo"

    name = fields.Char(default="CEL Widget Demo", readonly=True)

    # Test fields with different profiles
    expression_individuals = fields.Text(
        string="Individual Expression",
        help="Test CEL expression for individual registrants",
    )

    expression_groups = fields.Text(
        string="Group Expression",
        help="Test CEL expression for groups/households",
    )

    expression_entitlements = fields.Text(
        string="Entitlement Expression",
        help="Test CEL expression for entitlements",
    )

    # Profile selection for dynamic testing
    selected_profile = fields.Selection(
        selection="_get_profile_selection",
        string="Profile",
        default="registry_individuals",
    )

    dynamic_expression = fields.Text(
        string="Expression",
        help="Test expression with the selected profile",
    )

    # Read-only test
    readonly_expression = fields.Text(
        string="Read-only Expression",
        default="age_years(r.birthdate) >= 18 and r.gender == 'female'",
        readonly=True,
    )

    # Validation result display
    validation_result = fields.Html(
        string="Last Validation Result",
        readonly=True,
        sanitize=False,
    )

    @api.model
    def _get_profile_selection(self):
        """Get available CEL profiles for selection."""
        return [
            ("registry_individuals", "Registry - Individuals"),
            ("registry_groups", "Registry - Groups"),
            ("program_memberships", "Program Memberships"),
            ("entitlements", "Entitlements"),
            ("grm_tickets", "GRM Tickets"),
        ]

    def _reopen_self(self):
        """Return action to reopen this wizard (keeps modal open)."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": {"form_view_initial_mode": "edit"},
        }

    def action_validate_expression(self):
        """Manually trigger validation and show result."""
        self.ensure_one()
        provider = self.env["spp.cel.symbol.provider"]

        expression = self.dynamic_expression or ""
        profile = self.selected_profile or "registry_individuals"

        if not expression.strip():
            self.validation_result = '<div class="alert alert-warning mb-0">No expression to validate</div>'
            return self._reopen_self()

        result = provider.validate_expression(expression, profile)

        if result.get("valid"):
            count = result.get("matching_count")
            count_str = count if count is not None else "N/A"
            self.validation_result = (
                f'<div class="alert alert-success mb-0"><strong>Valid!</strong> Matching records: {count_str}</div>'
            )
        else:
            errors = result.get("errors", [])
            error_items = "".join(f"<li>{e.get('message', 'Unknown error')}</li>" for e in errors)
            self.validation_result = (
                '<div class="alert alert-danger mb-0">'
                f"<strong>Invalid</strong><ul class='mb-0 mt-1'>{error_items}</ul></div>"
            )
        return self._reopen_self()

    def action_load_symbols(self):
        """Load and display symbols for the selected profile."""
        self.ensure_one()
        provider = self.env["spp.cel.symbol.provider"]
        profile = self.selected_profile or "registry_individuals"

        symbols = provider.get_symbols_for_profile(profile)
        parts = [
            f"<h5>Symbols for <code>{profile}</code></h5>",
            "<p class='text-muted small mb-2'>Click any row to insert into the expression editor above.</p>",
        ]

        # Shared row style for clickable rows
        row_style = "cursor:pointer"

        # Model fields (via profile variables like r, m)
        variables = symbols.get("variables", [])
        if variables:
            parts.append(f"<h6>Model Fields ({len(variables)} variables)</h6>")
            for var in variables:
                var_fields = var.get("fields", [])
                model = var.get("model") or var.get("type", "?")
                parts.append(
                    f"<details open><summary><strong>{var['name']}</strong>"
                    f" <span class='text-muted'>({model}) &mdash;"
                    f" {len(var_fields)} fields</span></summary>"
                )
                if var_fields:
                    rows = "".join(
                        f"<tr style='{row_style}'"
                        f" data-cel-insert='{var['name']}.{f['name']}'>"
                        f"<td><code>{var['name']}.{f['name']}</code></td>"
                        f"<td><span class='badge bg-secondary'>"
                        f"{f['type']}</span></td>"
                        f"<td class='text-muted'>{f.get('doc', '')}</td></tr>"
                        for f in var_fields
                    )
                    parts.append(
                        "<table class='table table-sm table-hover mb-0'>"
                        "<thead><tr><th>Field</th><th>Type</th>"
                        "<th>Label</th></tr></thead>"
                        f"<tbody>{rows}</tbody></table>"
                    )
                parts.append("</details>")

        # CEL variables (from spp.cel.variable)
        cel_vars = symbols.get("cel_variables", [])
        if cel_vars:
            parts.append(f"<h6 class='mt-3'>CEL Variables ({len(cel_vars)})</h6>")
            rows = "".join(
                f"<tr style='{row_style}'"
                f" data-cel-insert='{v.get('cel_expression', v['name'])}'>"
                f"<td><strong>{v.get('label', v['name'])}</strong></td>"
                f"<td><span class='badge bg-secondary'>"
                f"{v.get('value_type', '?')}</span></td>"
                f"<td>{v.get('category', '')}</td>"
                f"<td><code>{v.get('cel_expression', '')}</code></td></tr>"
                for v in cel_vars
            )
            parts.append(
                "<table class='table table-sm table-hover mb-0'>"
                "<thead><tr><th>Name</th><th>Type</th>"
                "<th>Category</th><th>Expression</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )

        # Library expressions
        library = symbols.get("library", [])
        if library:
            parts.append(f"<h6 class='mt-3'>Library Expressions ({len(library)})</h6>")
            rows = "".join(
                f"<tr style='{row_style}'"
                f" data-cel-insert='{e.get('cel_expression', e['name'])}'>"
                f"<td><strong>{e['name']}</strong></td>"
                f"<td><span class='badge bg-info'>"
                f"{e.get('expression_type', '?')}</span></td>"
                f"<td><code>{e.get('cel_expression', '')}</code></td></tr>"
                for e in library
            )
            parts.append(
                "<table class='table table-sm table-hover mb-0'>"
                "<thead><tr><th>Name</th><th>Type</th>"
                "<th>Expression</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )

        # Functions
        functions = symbols.get("functions", [])
        if functions:
            parts.append(f"<h6 class='mt-3'>Functions ({len(functions)})</h6>")
            rows = "".join(
                f"<tr style='{row_style}'"
                f" data-cel-insert='{f['name']}()'>"
                f"<td><code>{f.get('signature', f['name'])}</code></td>"
                f"<td class='text-muted'>{f.get('doc', '')}</td></tr>"
                for f in functions
            )
            parts.append(
                "<table class='table table-sm table-hover mb-0'>"
                "<thead><tr><th>Signature</th>"
                "<th>Description</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )

        # Operators
        operators = symbols.get("operators", [])
        if operators:
            parts.append(f"<h6 class='mt-3'>Operators ({len(operators)})</h6>")
            rows = "".join(
                f"<tr style='{row_style}'"
                f" data-cel-insert=' {op['symbol']} '>"
                f"<td><code>{op['symbol']}</code></td>"
                f"<td>{op.get('doc', '')}</td>"
                f"<td><span class='badge bg-light text-dark'>"
                f"{op.get('type', '')}</span></td></tr>"
                for op in operators
            )
            parts.append(
                "<table class='table table-sm table-hover mb-0'>"
                "<thead><tr><th>Operator</th><th>Description</th>"
                "<th>Category</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>"
            )

        self.validation_result = "".join(parts)
        return self._reopen_self()

    def action_insert_example(self):
        """Insert an example expression."""
        self.ensure_one()
        examples = {
            "registry_individuals": "age_years(r.birthdate) >= 18 and r.gender == 'female'",
            "registry_groups": "members.count(m, age_years(m.birthdate) < 5) >= 2",
            "program_memberships": "r.state == 'enrolled'",
            "entitlements": "r.amount >= 1000",
            "grm_tickets": "r.state == 'open'",
        }
        self.dynamic_expression = examples.get(self.selected_profile, "r.active == true")
        return self._reopen_self()
