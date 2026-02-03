from odoo import Command, api, fields, models


class CelRuleWizard(models.TransientModel):
    _name = "spp.cel.rule.wizard"
    _description = "CEL Rule Preview"

    profile = fields.Selection(
        selection=[
            ("registry_individuals", "Registry / Individuals"),
            ("registry_groups", "Registry / Groups"),
            ("program_memberships", "Program Memberships"),
            ("entitlements", "Entitlements"),
        ],
        default="registry_groups",
        required=True,
    )
    model_id = fields.Many2one("ir.model", string="Target Model", required=True)
    cel_expression = fields.Text(string="CEL Expression", required=True)

    result_domain_text = fields.Text(string="Generated Domain", readonly=True)
    explain_text = fields.Html(string="Explanation", readonly=True, sanitize=False)
    metrics_explain_text = fields.Text(readonly=True)
    metric_line_ids = fields.One2many("spp.cel.rule.wizard.metric", "wizard_id", string="Metrics", readonly=True)
    preview_count = fields.Integer(readonly=True)
    # For now, surface sample records for the common Individuals use case
    # (res.partner). This can be extended to other models later.
    sample_ids = fields.Many2many("res.partner", string="Sample IDs", readonly=True)

    @api.onchange("profile")
    def _onchange_profile(self):
        if self.profile:
            model = self.env["spp.cel.registry"].profile_root_model(self.profile)
            if model:
                self.model_id = self.env["ir.model"].search([("model", "=", model)], limit=1)

    def action_validate_preview(self):
        self.ensure_one()
        registry = self.env["spp.cel.registry"]
        # Clear previous results
        self.result_domain_text = ""
        self.explain_text = ""
        self.preview_count = 0
        self.sample_ids = [Command.clear()]

        # Build context config by profile
        cfg = registry.load_profile(self.profile)
        executor = self.env["spp.cel.executor"].with_context(cel_profile=self.profile, cel_cfg=cfg)

        try:
            # Translate + execute
            result = executor.compile_and_preview(self.model_id.model, self.cel_expression, limit=50)
            self.result_domain_text = self._format_domain_text(result.get("domain") or [])
            raw_explain = result.get("explain") or ""
            # Strip metrics appendage from explain (shown separately)
            marker = " | Metrics: "
            clean_explain = raw_explain.split(marker, 1)[0] if marker in raw_explain else raw_explain
            metrics_addendum = raw_explain.split(marker, 1)[1] if marker in raw_explain else ""
            # Build user-friendly explanation
            path = result.get("path", "domain")
            warnings = result.get("warnings") or []
            self.explain_text = self._build_explain_html(
                self.cel_expression, clean_explain, path, warnings,
            )
            # Append simple warnings if present in struct
            warnings_lines = []
            for mi in (result.get("explain_struct") or {}).get("metrics", []) or []:
                w = mi.get("warnings") or []
                if w:
                    warnings_lines.append(f"{mi.get('metric')}@{mi.get('period_key')}: {', '.join(w)}")
            if warnings_lines:
                metrics_addendum = (
                    metrics_addendum + ("; " if metrics_addendum else "") + "Warnings: " + "; ".join(warnings_lines)
                )
            self.metrics_explain_text = metrics_addendum
            self.preview_count = result.get("count")
            # Populate structured metrics lines
            lines = []
            for mi in (result.get("explain_struct") or {}).get("metrics", []) or []:
                lines.append(
                    Command.create(
                        {
                            "metric": mi.get("metric"),
                            "period_key": mi.get("period_key"),
                            "requested": mi.get("requested", 0),
                            "cache_hits": mi.get("cache_hits", 0),
                            "misses": mi.get("misses", 0),
                            "fresh_fetches": mi.get("fresh_fetches", 0),
                            "coverage": mi.get("coverage", 0.0),
                        }
                    )
                )
            if lines:
                self.metric_line_ids = [Command.clear()] + lines
            else:
                self.metric_line_ids = [Command.clear()]
            # Populate sample_ids for Individuals profile (res.partner)
            if self.model_id.model == "res.partner":
                self.sample_ids = [Command.set(result.get("ids", []))]
            else:
                self.sample_ids = [Command.clear()]
            return self._reopen_self()

        except SyntaxError as e:
            error_msg = str(e)
            pos = getattr(e, "offset", None)
            friendly_msg = "Syntax Error"
            if pos:
                friendly_msg += f" at position {pos}"
            friendly_msg += f": {error_msg}"
            self.explain_text = self._error_html(
                friendly_msg,
                "Please check your expression for typos or missing parentheses.",
            )
            return self._reopen_self()

        except KeyError as e:
            symbol = str(e).strip("'\"")
            available = list(cfg.get("symbols", {}).keys())
            suggestion = self._suggest_symbol(symbol, available)
            msg = f"Unknown symbol '{symbol}'."
            if suggestion:
                msg += f" Did you mean <code>{suggestion}</code>?"
            hint = f"Available symbols for this profile: {', '.join(available)}" if available else ""
            self.explain_text = self._error_html(msg, hint)
            return self._reopen_self()

        except NotImplementedError as e:
            self.explain_text = self._error_html(f"Not Supported: {e}")
            return self._reopen_self()

        except AttributeError as e:
            self.explain_text = self._error_html(
                f"Invalid field access: {e}",
                "This usually means you're trying to access a field that doesn't exist. "
                "Check field names and make sure you're using the correct profile.",
            )
            return self._reopen_self()

        except Exception as e:
            self.explain_text = self._error_html(str(e))
            return self._reopen_self()

    def _suggest_symbol(self, wrong_symbol, available_symbols):
        """Simple string similarity for suggestions using difflib."""
        if not available_symbols:
            return None
        import difflib

        matches = difflib.get_close_matches(wrong_symbol, available_symbols, n=1, cutoff=0.6)
        return matches[0] if matches else None

    @staticmethod
    def _error_html(message, hint=""):
        """Build an HTML error message for display."""
        html = f'<div class="alert alert-danger mb-0"><strong>{message}</strong>'
        if hint:
            html += f"<br/><span class='text-muted'>{hint}</span>"
        html += "</div>"
        return html

    @staticmethod
    def _build_explain_html(expression, translated, path, warnings):
        """Build a user-friendly HTML explanation of the preview results."""
        from markupsafe import Markup

        parts = []
        # Expression echo
        parts.append(
            f'<div class="mb-2"><strong>Expression:</strong> '
            f"<code>{Markup.escape(expression)}</code></div>"
        )
        # Translation
        if translated:
            parts.append(
                f'<div class="mb-2"><strong>Translates to:</strong> '
                f"<code>{Markup.escape(translated)}</code></div>"
            )
        # Execution path
        path_labels = {
            "domain": "Direct domain filter (fastest)",
            "sql": "SQL fast path (scalable)",
            "python": "Python evaluation (may be slow for large datasets)",
        }
        path_label = path_labels.get(path, path)
        parts.append(
            f'<div class="mb-2 text-muted"><strong>Execution path:</strong> {path_label}</div>'
        )
        # Warnings
        for w in warnings:
            parts.append(
                f'<div class="text-warning"><i class="fa fa-exclamation-triangle"/> {Markup.escape(w)}</div>'
            )
        return "".join(parts)

    @staticmethod
    def _format_domain_text(domain):
        """Format an Odoo domain list into a human-readable string."""
        if not domain:
            return ""
        operator_map = {
            "=": "=",
            "!=": "!=",
            ">": ">",
            ">=": ">=",
            "<": "<",
            "<=": "<=",
            "in": "in",
            "not in": "not in",
            "like": "contains",
            "ilike": "contains",
            "=like": "matches",
            "=ilike": "matches",
        }
        parts = []
        for item in domain:
            if item == "&":
                continue  # implicit AND between conditions
            if item == "|":
                parts.append("OR")
                continue
            if item == "!":
                parts.append("NOT")
                continue
            if isinstance(item, (list, tuple)) and len(item) == 3:
                field, op, value = item
                op_text = operator_map.get(op, op)
                if value is True:
                    parts.append(f"{field} is True")
                elif value is False:
                    parts.append(f"{field} is False")
                else:
                    parts.append(f"{field} {op_text} {value}")
            else:
                parts.append(str(item))
        return "\n".join(parts)

    def _reopen_self(self):
        """Reopen the wizard to display updated results."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }


class CelRuleWizardMetric(models.TransientModel):
    _name = "spp.cel.rule.wizard.metric"
    _description = "CEL Preview Metric Explain Line"

    wizard_id = fields.Many2one("spp.cel.rule.wizard", required=True, ondelete="cascade")
    metric = fields.Char(required=True)
    period_key = fields.Char()
    requested = fields.Integer()
    cache_hits = fields.Integer()
    misses = fields.Integer()
    fresh_fetches = fields.Integer()
    coverage = fields.Float()
