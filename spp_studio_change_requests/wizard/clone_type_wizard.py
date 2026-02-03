"""Clone CR Type Wizard for copying existing CR types."""

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class CloneCRTypeWizard(models.TransientModel):
    """Wizard for cloning an existing CR type."""

    _name = "spp.studio.clone.cr.type.wizard"
    _description = "Clone Change Request Type Wizard"

    # ══════════════════════════════════════════════════════════════════════════
    # SOURCE TYPE
    # ══════════════════════════════════════════════════════════════════════════

    source_type_id = fields.Many2one(
        "spp.change.request.type",
        string="Source Type",
        required=True,
        domain="[('is_studio_cloneable', '=', True)]",
        help="The CR type to clone. Only cloneable types are available.",
    )
    source_name = fields.Char(
        string="Source Name",
        related="source_type_id.name",
        readonly=True,
    )
    source_code = fields.Char(
        string="Source Code",
        related="source_type_id.code",
        readonly=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # NEW TYPE CONFIGURATION
    # ══════════════════════════════════════════════════════════════════════════

    new_name = fields.Char(
        string="New Type Name",
        required=True,
        help="Display name for the cloned type",
    )
    new_code = fields.Char(
        string="New Type Code",
        required=True,
        help="Unique technical code for the cloned type",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # CLONE OPTIONS
    # ══════════════════════════════════════════════════════════════════════════

    copy_field_mappings = fields.Boolean(
        string="Copy Field Mappings",
        default=True,
        help="Copy the field mapping configuration from the source type",
    )
    copy_approval_workflow = fields.Boolean(
        string="Copy Approval Workflow",
        default=True,
        help="Link the same approval workflow as the source type",
    )
    copy_document_requirements = fields.Boolean(
        string="Copy Document Requirements",
        default=False,
        help="Copy required document types from the source type",
    )

    # ══════════════════════════════════════════════════════════════════════════
    # COMPUTED / VALIDATION
    # ══════════════════════════════════════════════════════════════════════════

    code_is_unique = fields.Boolean(
        compute="_compute_code_is_unique",
    )
    source_is_cloneable = fields.Boolean(
        compute="_compute_source_is_cloneable",
    )

    @api.depends("new_code")
    def _compute_code_is_unique(self):
        """Check if the new code is unique."""
        for rec in self:
            if rec.new_code:
                existing = self.env["spp.change.request.type"].search([("code", "=", rec.new_code)], limit=1)
                rec.code_is_unique = not existing
            else:
                rec.code_is_unique = True

    @api.depends("source_type_id")
    def _compute_source_is_cloneable(self):
        """Check if source type is cloneable."""
        for rec in self:
            rec.source_is_cloneable = rec.source_type_id.is_studio_cloneable if rec.source_type_id else False

    # ══════════════════════════════════════════════════════════════════════════
    # ONCHANGE
    # ══════════════════════════════════════════════════════════════════════════

    @api.onchange("source_type_id")
    def _onchange_source_type_id(self):
        """Auto-suggest name and code based on source."""
        if self.source_type_id:
            # Suggest name with "(Copy)" suffix
            self.new_name = f"{self.source_type_id.name} (Copy)"
            # Suggest code with "_copy" suffix
            base_code = self.source_type_id.code
            counter = 1
            new_code = f"{base_code}_copy"
            # Ensure uniqueness
            while self.env["spp.change.request.type"].search([("code", "=", new_code)], limit=1):
                counter += 1
                new_code = f"{base_code}_copy_{counter}"
            self.new_code = new_code

    # ══════════════════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ══════════════════════════════════════════════════════════════════════════

    @api.constrains("source_type_id")
    def _check_source_cloneable(self):
        """Ensure source type is cloneable."""
        for rec in self:
            if rec.source_type_id and not rec.source_type_id.is_studio_cloneable:
                raise ValidationError(
                    _(
                        "Cannot clone type '%(name)s'. "
                        "This type is not cloneable because it requires custom Python logic."
                    )
                    % {"name": rec.source_type_id.name}
                )

    @api.constrains("new_code")
    def _check_code_unique(self):
        """Ensure new code is unique."""
        for rec in self:
            if rec.new_code:
                existing = self.env["spp.change.request.type"].search([("code", "=", rec.new_code)], limit=1)
                if existing:
                    raise ValidationError(
                        _("A type with code '%(code)s' already exists. Please choose a different code.")
                        % {"code": rec.new_code}
                    )

    # ══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def action_clone(self):
        """Clone the CR type and return action to view it."""
        self.ensure_one()

        if not self.source_type_id:
            raise UserError(_("Please select a source type to clone."))

        if not self.source_type_id.is_studio_cloneable:
            raise UserError(
                _(
                    "Cannot clone type '%(name)s'. "
                    "This type requires custom Python logic and cannot be cloned via Studio."
                )
                % {"name": self.source_type_id.name}
            )

        source = self.source_type_id

        # Create the new CR type
        new_type_vals = {
            "name": self.new_name,
            "code": self.new_code,
            "description": f"Cloned from: {source.name}. {source.description or ''}",
            "target_type": source.target_type,
            "detail_model": source.detail_model,
            "detail_form_view_id": source.detail_form_view_id.id if source.detail_form_view_id else False,
            "apply_strategy": source.apply_strategy,
            "apply_model": source.apply_model,
            "apply_method": source.apply_method,
            "auto_apply_on_approve": source.auto_apply_on_approve,
            "icon": source.icon,
            "color": source.color,
            "sequence": source.sequence + 1,
            # Editability - cloned types are editable
            "is_studio_editable": True,
            "is_studio_cloneable": True,
            "is_system_type": False,
            "cloned_from_id": source.id,
            "source_module": False,
        }

        # Copy approval workflow if requested
        if self.copy_approval_workflow and source.approval_definition_id:
            new_type_vals["approval_definition_id"] = source.approval_definition_id.id

        # Copy document requirements if requested
        if self.copy_document_requirements and source.required_document_type_ids:
            new_type_vals["required_document_type_ids"] = [Command.set(source.required_document_type_ids.ids)]
            new_type_vals["document_validation_mode"] = source.document_validation_mode

        new_type = self.env["spp.change.request.type"].create(new_type_vals)

        # Copy field mappings if requested
        if self.copy_field_mappings and source.apply_mapping_ids:
            for mapping in source.apply_mapping_ids:
                self.env["spp.change.request.type.mapping"].create(
                    {
                        "type_id": new_type.id,
                        "source_field": mapping.source_field,
                        "target_field": mapping.target_field,
                        "transform": mapping.transform,
                        "transform_expression": mapping.transform_expression,
                        "sequence": mapping.sequence,
                    }
                )

        # Return action to open the new type
        return {
            "type": "ir.actions.act_window",
            "name": _("Cloned CR Type"),
            "res_model": "spp.change.request.type",
            "res_id": new_type.id,
            "view_mode": "form",
            "target": "current",
        }
