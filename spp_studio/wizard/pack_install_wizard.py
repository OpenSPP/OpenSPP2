"""Pack Installation Wizard for Logic Studio."""

import json
import logging

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PackInstallWizard(models.TransientModel):
    """Wizard to install a Logic Pack."""

    _name = "spp.studio.pack.install.wizard"
    _description = "Logic Pack Installation Wizard"

    pack_id = fields.Many2one(
        "spp.studio.pack",
        string="Logic Pack",
        required=True,
        domain=[("state", "=", "available")],
    )

    # Pack info (computed from pack_id)
    pack_name = fields.Char(related="pack_id.name", readonly=True)
    pack_description = fields.Text(related="pack_id.description", readonly=True)

    # Installation options
    install_as_draft = fields.Boolean(
        string="Install as Draft",
        default=True,
        help="Install logic items as Draft for review before publishing",
    )
    install_personas = fields.Boolean(
        string="Install Test Personas",
        default=True,
        help="Include test personas from the pack",
    )

    # Items to install
    item_ids = fields.Many2many(
        "spp.studio.pack.item",
        string="Items to Install",
        compute="_compute_items",
        readonly=False,
        store=True,
    )

    # Variable check results
    missing_variables = fields.Text(
        string="Missing Variables",
        compute="_compute_missing_variables",
    )
    has_missing_variables = fields.Boolean(compute="_compute_missing_variables")

    # Preview fields
    preview_ids = fields.One2many(
        "spp.studio.pack.install.preview",
        "wizard_id",
        string="Preview",
    )
    show_preview = fields.Boolean(
        string="Show Preview",
        default=False,
    )
    program_id = fields.Many2one(
        "spp.program",
        string="Program",
        help="Optional: Program for constant value lookups",
    )

    # Vocabulary summary
    vocabulary_summary = fields.Text(
        string="Vocabulary Changes",
        compute="_compute_vocabulary_summary",
    )
    has_vocabulary_items = fields.Boolean(compute="_compute_vocabulary_summary")

    # Results
    result_message = fields.Text(string="Result", readonly=True)
    installed_logic_ids = fields.Many2many(
        "spp.cel.expression",
        string="Installed Logic",
        readonly=True,
    )

    @api.depends("pack_id")
    def _compute_items(self):
        """Load items from selected pack."""
        for wizard in self:
            if wizard.pack_id:
                wizard.item_ids = wizard.pack_id.item_ids
            else:
                wizard.item_ids = False

    @api.depends("pack_id", "item_ids")
    def _compute_missing_variables(self):
        """Check which required variables are missing."""
        Variable = self.env["spp.cel.variable"]

        for wizard in self:
            if not wizard.pack_id:
                wizard.missing_variables = ""
                wizard.has_missing_variables = False
                continue

            # Get required variables from pack
            required = wizard.pack_id.required_variable_ids

            # Find which are missing
            missing = []
            for var in required:
                existing = Variable.search([("name", "=", var.name), ("active", "=", True)], limit=1)
                if not existing:
                    missing.append(var.label or var.name)

            if missing:
                wizard.missing_variables = _("Missing variables:\n• ") + "\n• ".join(missing)
                wizard.has_missing_variables = True
            else:
                wizard.missing_variables = _("All required variables are available.")
                wizard.has_missing_variables = False

    @api.depends("pack_id")
    def _compute_vocabulary_summary(self):
        """Build a human-readable summary of vocabulary changes the pack will make."""
        for wizard in self:
            if not wizard.pack_id or not wizard.pack_id.vocabulary_ids:
                wizard.vocabulary_summary = ""
                wizard.has_vocabulary_items = False
                continue

            wizard.has_vocabulary_items = True
            lines = []
            for vocab_item in wizard.pack_id.vocabulary_ids:
                code_count = len(vocab_item.code_ids)
                if vocab_item.vocabulary_id:
                    lines.append(
                        _("Add %d code(s) to '%s'") % (code_count, vocab_item.vocabulary_id.name)
                    )
                else:
                    lines.append(
                        _("Create vocabulary '%s' with %d code(s)")
                        % (vocab_item.new_vocabulary_name, code_count)
                    )

            for concept in wizard.pack_id.concept_ids:
                ref_count = len(concept.code_ref_ids)
                lines.append(
                    _("Create concept group '%s' (%s) with %d code reference(s)")
                    % (concept.name, concept.cel_function or "no CEL function", ref_count)
                )

            wizard.vocabulary_summary = "\n".join(lines)

    def _install_vocabularies(self):
        """Phase 1: Provision vocabularies and codes.

        For add-codes mode, adds codes to existing vocabularies.
        For create-new mode, creates the vocabulary then adds codes.
        Uses sudo() for cross-module vocabulary operations.
        """
        VocabCode = self.env["spp.vocabulary.code"].sudo()
        Vocabulary = self.env["spp.vocabulary"].sudo()

        installed_vocab_count = 0
        installed_code_count = 0

        for vocab_item in self.pack_id.vocabulary_ids:
            if vocab_item.vocabulary_id:
                # Add-codes mode
                namespace_uri = vocab_item.vocabulary_id.namespace_uri
            else:
                # Create-new mode: find or create the vocabulary
                namespace_uri = vocab_item.new_vocabulary_namespace
                existing_vocab = Vocabulary.search(
                    [("namespace_uri", "=", namespace_uri)], limit=1
                )
                if existing_vocab:
                    vocab_item.installed_vocabulary_id = existing_vocab.id
                else:
                    new_vocab = Vocabulary.create(
                        {
                            "name": vocab_item.new_vocabulary_name,
                            "namespace_uri": namespace_uri,
                            "domain": vocab_item.new_vocabulary_domain or "core",
                            "is_hierarchical": vocab_item.new_vocabulary_hierarchical,
                        }
                    )
                    vocab_item.installed_vocabulary_id = new_vocab.id
                    installed_vocab_count += 1

            # Install each code
            for code_item in vocab_item.code_ids:
                if code_item.is_local:
                    code_rec = VocabCode.get_or_create_local(
                        namespace_uri, code_item.code, display=code_item.display
                    )
                else:
                    code_rec = VocabCode.get_or_create(
                        namespace_uri, code_item.code, display=code_item.display
                    )

                # Set extra fields only on freshly created codes
                # (codes returned by get_or_create that already existed keep their values)
                if not code_item.installed_code_id:
                    extra_vals = {}
                    if code_item.definition and not code_rec.definition:
                        extra_vals["definition"] = code_item.definition
                    if code_item.sequence and code_rec.sequence == 10:
                        extra_vals["sequence"] = code_item.sequence
                    if code_item.target_type and not code_rec.target_type:
                        extra_vals["target_type"] = code_item.target_type
                    if extra_vals:
                        code_rec.sudo().write(extra_vals)

                code_item.installed_code_id = code_rec.id
                installed_code_count += 1

        return installed_vocab_count, installed_code_count

    def _install_concept_groups(self):
        """Phase 2: Provision concept groups.

        Resolves code URI references to actual code records.
        If a concept group with the same name exists, merges codes into it.
        """
        VocabCode = self.env["spp.vocabulary.code"].sudo()
        ConceptGroup = self.env["spp.vocabulary.concept.group"].sudo()

        installed_count = 0

        for concept in self.pack_id.concept_ids:
            # Resolve all code URIs
            resolved_codes = self.env["spp.vocabulary.code"]
            missing_uris = []

            for code_ref in concept.code_ref_ids:
                code_rec = VocabCode.search([("uri", "=", code_ref.uri)], limit=1)
                if not code_rec:
                    missing_uris.append(code_ref.uri)
                else:
                    resolved_codes |= code_rec

            if missing_uris:
                raise UserError(
                    _("Cannot install concept group '%s': unresolvable code URIs:\n%s")
                    % (concept.name, "\n".join("- " + uri for uri in missing_uris))
                )

            # Check if concept group already exists
            existing_group = ConceptGroup.search([("name", "=", concept.name)], limit=1)
            if existing_group:
                # Merge codes (additive)
                existing_codes = existing_group.code_ids
                new_codes = resolved_codes - existing_codes
                if new_codes:
                    existing_group.write({"code_ids": [(4, c.id) for c in new_codes]})
                concept.installed_group_id = existing_group.id
            else:
                # Create new concept group
                group_vals = {
                    "name": concept.name,
                    "label": concept.label,
                    "cel_function": concept.cel_function,
                    "target_field": concept.target_field,
                    "description": concept.description,
                    "code_ids": [(6, 0, resolved_codes.ids)],
                }
                new_group = ConceptGroup.create(group_vals)
                concept.installed_group_id = new_group.id

            installed_count += 1

        return installed_count

    def action_preview(self):
        """Generate preview showing original expressions and runtime resolution preview.

        With deferred resolution, the original expression is stored and variables
        are resolved at evaluation time. This preview shows:
        - Original expression (what will be stored)
        - Runtime preview (what it would resolve to with current variable definitions)
        - Missing variables (variables that need to be defined before logic can run)
        """
        self.ensure_one()

        if not self.pack_id:
            raise UserError(_("Please select a Logic Pack."))

        # Clear existing previews
        self.preview_ids.unlink()

        resolver = self.env["spp.cel.variable.resolver"]

        previews = []
        for item in self.item_ids:
            result = resolver.expand_pack_item(item, program_id=self.program_id.id if self.program_id else None)

            previews.append(
                Command.create(
                    {
                        "wizard_id": self.id,
                        "item_id": item.id,
                        "item_name": item.name,
                        "expression_type": item.expression_type,
                        "original_expression": result["original_expression"],
                        "expanded_expression": result["expanded_expression"],
                        "missing_variables": ", ".join(result["missing_variables"])
                        if result["missing_variables"]
                        else "",
                        "warnings": "\n".join(result["warnings"]) if result["warnings"] else "",
                    }
                )
            )

        self.write(
            {
                "preview_ids": previews,
                "show_preview": True,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_install(self):
        """Install the selected pack items with original expressions (deferred resolution).

        Variable references are kept in the expression and resolved at evaluation time.
        This allows changes to variable definitions to automatically propagate to all
        logic that uses them.
        """
        self.ensure_one()

        if not self.pack_id:
            raise UserError(_("Please select a Logic Pack to install."))

        if not self.item_ids and not self.pack_id.vocabulary_ids and not self.pack_id.concept_ids:
            raise UserError(_("No items selected for installation."))

        # Phase 1: Provision vocabularies and codes
        installed_vocab_count, installed_code_count = self._install_vocabularies()

        # Phase 2: Provision concept groups
        installed_concept_count = self._install_concept_groups()

        Logic = self.env["spp.cel.expression"]

        installed_logic = self.env["spp.cel.expression"]
        installed_personas = self.env["spp.studio.test.persona"]

        # Phase 3: Install each item with ORIGINAL expression (deferred resolution)
        for item in self.item_ids:
            try:
                logic_data = json.loads(item.logic_data)

                # Use the ORIGINAL expression with variable references
                # Variables will be resolved at evaluation time, not installation time
                cel_expression = logic_data.get("cel_expression", "")

                # Determine initial state
                state = "draft" if self.install_as_draft else "published"

                # Create logic record with original expression (variables intact)
                logic_vals = {
                    "name": item.name,
                    "description": item.description or logic_data.get("description"),
                    "expression_type": item.expression_type,
                    # Preserve intended context from pack item
                    "context_type": item.context_type or "individual",
                    "cel_expression": cel_expression,  # Keep original with variable refs
                    "output_type": logic_data.get("output_type", "boolean"),
                    "state": state,
                }

                logic = Logic.create(logic_vals)
                installed_logic |= logic

                # Update pack item reference
                item.installed_logic_id = logic.id

                _logger.info("Installed logic ID %s from pack ID %s", item.id, self.pack_id.id)

            except json.JSONDecodeError as e:
                _logger.error("Invalid JSON in pack item ID %s: %s", item.id, e)
                raise UserError(_("Invalid data in pack item ID %s: %s") % (item.name, e)) from e
            except Exception as e:
                _logger.error("Error installing pack item ID %s: %s", item.id, e)
                raise UserError(_("Error installing '%s': %s") % (item.name, e)) from e

        # Install personas if requested
        if self.install_personas and self.pack_id.persona_ids:
            for persona in self.pack_id.persona_ids:
                new_persona = persona.copy({"is_global": True})
                installed_personas |= new_persona

        # Mark pack as installed
        self.pack_id.write(
            {
                "state": "installed",
                "installed_date": fields.Datetime.now(),
            }
        )

        # Build result message
        message = _("Pack '%s' installed successfully!\n\n") % self.pack_id.name
        if installed_vocab_count:
            message += _("Vocabularies created: %d\n") % installed_vocab_count
        if installed_code_count:
            message += _("Vocabulary codes provisioned: %d\n") % installed_code_count
        if installed_concept_count:
            message += _("Concept groups provisioned: %d\n") % installed_concept_count
        message += _("Logic items installed: %d\n") % len(installed_logic)
        if installed_personas:
            message += _("Test personas installed: %d\n") % len(installed_personas)

        if self.install_as_draft:
            message += _("\nAll items installed as Draft. Review and test before publishing.")

        self.result_message = message
        self.installed_logic_ids = installed_logic

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_view_installed(self):
        """Open list view of installed logic."""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Installed Logic"),
            "res_model": "spp.cel.expression",
            "view_mode": "list,form",
            "domain": [("id", "in", self.installed_logic_ids.ids)],
            "target": "current",
        }


class PackInstallPreview(models.TransientModel):
    """Preview line for pack installation."""

    _name = "spp.studio.pack.install.preview"
    _description = "Pack Install Preview Line"

    wizard_id = fields.Many2one(
        "spp.studio.pack.install.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )
    item_id = fields.Many2one(
        "spp.studio.pack.item",
        string="Pack Item",
        readonly=True,
    )
    item_name = fields.Char(string="Item Name", readonly=True)
    description = fields.Text(string="Description", readonly=True)
    expression_type = fields.Selection(
        selection=[
            ("filter", "Filter"),
            ("formula", "Formula"),
            ("scoring", "Scoring"),
            ("validation", "Validation"),
            ("other", "Other"),
        ],
        string="Type",
        readonly=True,
    )
    original_expression = fields.Text(
        string="Original Expression",
        readonly=True,
    )
    expanded_expression = fields.Text(
        string="Expanded Expression",
        help="You can modify this expression before installation",
    )
    missing_variables = fields.Char(
        string="Missing Variables",
        readonly=True,
    )
    warnings = fields.Text(
        string="Warnings",
        readonly=True,
    )
    has_issues = fields.Boolean(
        compute="_compute_has_issues",
        string="Has Issues",
    )

    @api.depends("missing_variables", "warnings")
    def _compute_has_issues(self):
        for rec in self:
            rec.has_issues = bool(rec.missing_variables or rec.warnings)
