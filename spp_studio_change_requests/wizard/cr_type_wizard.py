"""Change Request Type builder wizard for creating custom CR types."""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StudioCRTypeWizard(models.TransientModel):
    """Three-step wizard for creating change request types.

    Step 1: Basic Info - name, target type, description, approval settings
    Step 2: Field Selection - select fields from res.partner to include
    Step 3: Review - summary and create as draft
    """

    _name = "spp.studio.cr.type.wizard"
    _description = "CR Type Builder Wizard"

    # Wizard state
    step = fields.Selection(
        [
            ("basic", "Basic Info"),
            ("fields", "Select Fields"),
            ("review", "Review"),
        ],
        string="Step",
        default="basic",
        required=True,
    )

    # Step 1: Basic Info
    name = fields.Char(
        string="Change Request Name",
        required=True,
        help="E.g., 'Address Update Request', 'Phone Number Change'",
    )
    description = fields.Text(
        string="Description",
        help="What is this change request for?",
    )
    target_type = fields.Selection(
        [
            ("individual", "Individual Registry"),
            ("group", "Group/Household Registry"),
            ("both", "Both"),
        ],
        string="Can be used by",
        required=True,
        default="individual",
        help="Which registry types can submit this change request",
    )
    requires_approval = fields.Boolean(
        string="Requires Approval",
        default=True,
        help="Change requests must be approved before being applied",
    )
    approval_group_id = fields.Many2one(
        "res.groups",
        string="Who can approve",
        help="Select the group of users who are authorized to review and approve these change requests",
    )
    auto_apply = fields.Boolean(
        string="Auto-apply when approved",
        default=True,
        help=(
            "If checked, approved changes will automatically update the "
            "beneficiary record. If unchecked, someone must manually apply "
            "the changes after approval."
        ),
    )

    # Step 2: Field Selection
    available_field_ids = fields.Many2many(
        "ir.model.fields",
        "wizard_cr_available_fields_rel",
        "wizard_id",
        "field_id",
        string="Available Fields",
        compute="_compute_available_fields",
        help="Fields available for selection",
    )
    selected_field_ids = fields.Many2many(
        "ir.model.fields",
        "wizard_cr_selected_fields_rel",
        "wizard_id",
        "field_id",
        string="Selected Fields",
        help="Fields to include in this change request type",
    )

    # Step 3: Preview
    preview_technical_name = fields.Char(
        string="Technical Code",
        compute="_compute_preview",
        help="Auto-generated code used internally. You don't need to change this.",
    )
    preview_field_count = fields.Integer(
        string="Number of Fields",
        compute="_compute_preview",
        help="Total number of fields selected for this change request type",
    )

    @api.depends("target_type")
    def _compute_available_fields(self):
        """Get available fields from res.partner."""
        # Common fields that make sense for change requests
        # Exclude system fields and technical fields
        excluded_fields = [
            "id",
            "create_date",
            "create_uid",
            "write_date",
            "write_uid",
            "__last_update",
            "display_name",
            "active",
            "company_id",
            "message_ids",
            "message_follower_ids",
            "message_partner_ids",
            "activity_ids",
            "image_1920",
            "image_1024",
            "image_512",
            "image_256",
            "image_128",
        ]

        for wizard in self:
            domain = [
                ("model", "=", "res.partner"),
                ("store", "=", True),
                ("name", "not in", excluded_fields),
                (
                    "ttype",
                    "in",
                    [
                        "char",
                        "text",
                        "integer",
                        "float",
                        "monetary",
                        "date",
                        "datetime",
                        "boolean",
                        "selection",
                        "many2one",
                        "many2many",
                    ],
                ),
            ]
            wizard.available_field_ids = self.env["ir.model.fields"].search(domain)

    @api.depends("name", "selected_field_ids")
    def _compute_preview(self):
        """Compute preview values."""
        import re

        for wizard in self:
            if wizard.name:
                code = re.sub(r"[^a-z0-9]+", "_", wizard.name.lower())
                code = re.sub(r"_+", "_", code).strip("_")
                wizard.preview_technical_name = f"x_cr_{code}"
            else:
                wizard.preview_technical_name = ""
            wizard.preview_field_count = len(wizard.selected_field_ids)

    @api.constrains("requires_approval", "approval_group_id")
    def _check_approval_config(self):
        """Ensure approval group is set if approval is required."""
        for wizard in self:
            if wizard.step in ("review",) and wizard.requires_approval:
                if not wizard.approval_group_id:
                    raise ValidationError(_("Please select an approval group since approval is required."))

    def action_next(self):
        """Move to the next step."""
        self.ensure_one()

        if self.step == "basic":
            # Validate basic info
            if not self.name:
                raise ValidationError(_("Please enter a name for the change request."))
            if self.requires_approval and not self.approval_group_id:
                raise ValidationError(_("Please select who can approve these requests."))
            self.step = "fields"

        elif self.step == "fields":
            # Validate field selection
            if not self.selected_field_ids:
                raise ValidationError(_("Please select at least one field to include in this change request."))
            self.step = "review"

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_previous(self):
        """Move to the previous step."""
        self.ensure_one()

        if self.step == "fields":
            self.step = "basic"
        elif self.step == "review":
            self.step = "fields"

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_create_cr_type(self):
        """Create the studio CR type as a draft."""
        self.ensure_one()

        # Create the CR type
        cr_type_vals = {
            "name": self.name,
            "description": self.description,
            "target_type": self.target_type,
            "requires_approval": self.requires_approval,
            "approval_group_id": self.approval_group_id.id if self.approval_group_id else False,
            "auto_apply": self.auto_apply,
            "state": "draft",
        }
        cr_type = self.env["spp.studio.change.request.type"].create(cr_type_vals)

        # Create field mappings
        for sequence, field in enumerate(self.selected_field_ids, start=1):
            self.env["spp.studio.cr.field.mapping"].create(
                {
                    "cr_type_id": cr_type.id,
                    "field_id": field.id,
                    "label": field.field_description,
                    "sequence": sequence * 10,
                    "is_required": False,
                }
            )

        _logger.info(
            "Created Studio CR type '%s' with %d fields",
            cr_type.name,
            len(self.selected_field_ids),
        )

        # Return action to view the created CR type
        return {
            "type": "ir.actions.act_window",
            "name": _("Change Request Type Created"),
            "res_model": "spp.studio.change.request.type",
            "res_id": cr_type.id,
            "view_mode": "form",
            "target": "current",
        }
