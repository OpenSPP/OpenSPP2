"""Studio Change Request Type model for tracking CR types created via Studio."""

import logging
import re

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class StudioChangeRequestType(models.Model):
    """Custom change request type definition created via Studio.

    This model tracks CR types created through the Studio interface and
    manages their lifecycle (draft/active/inactive).
    """

    _name = "spp.studio.change.request.type"
    _description = "Studio Change Request Type"
    _inherit = ["spp.studio.mixin", "mail.thread", "mail.activity.mixin"]
    _order = "target_type, name"
    _rec_name = "name"

    # Basic identification
    name = fields.Char(
        string="CR Type Name",
        required=True,
        translate=True,
        help="Display name shown to users (e.g., 'Address Update Request')",
    )
    technical_name = fields.Char(
        string="Technical Name",
        readonly=True,
        copy=False,
        help="Auto-generated code (x_cr_*)",
    )
    description = fields.Text(
        string="Description",
        translate=True,
        help="Description of what this change request type is for",
    )

    # Target configuration
    target_type = fields.Selection(
        [
            ("individual", "Individual"),
            ("group", "Group/Household"),
            ("both", "Both"),
        ],
        string="Target Registry",
        required=True,
        default="individual",
        help="Which registry types can use this change request",
    )

    # Field mappings
    field_mapping_ids = fields.One2many(
        "spp.studio.cr.field.mapping",
        "cr_type_id",
        string="Field Mappings",
        help="Fields that can be changed via this request type",
    )

    # Approval configuration
    requires_approval = fields.Boolean(
        string="Requires Approval",
        default=True,
        help="Change requests must be approved before applying",
    )
    approval_group_id = fields.Many2one(
        "res.groups",
        string="Approval Group",
        help="Group of users who can approve these requests",
    )
    auto_apply = fields.Boolean(
        string="Auto-Apply on Approval",
        default=True,
        help="Automatically apply changes when approved",
    )

    # Link to actual CR type
    spp_change_request_type_id = fields.Many2one(
        "spp.change.request.type",
        string="Change Request Type",
        readonly=True,
        copy=False,
        ondelete="set null",
        help="Link to the actual CR type created when this is activated",
    )
    detail_model_id = fields.Many2one(
        "ir.model",
        string="Detail Model",
        readonly=True,
        copy=False,
        ondelete="set null",
        help="Generated detail model for this CR type",
    )

    # Computed
    field_count = fields.Integer(
        string="Field Count",
        compute="_compute_field_count",
    )

    @api.depends("field_mapping_ids")
    def _compute_field_count(self):
        for record in self:
            record.field_count = len(record.field_mapping_ids)

    @api.constrains("field_mapping_ids")
    def _check_field_mappings(self):
        for record in self:
            if record.state != "draft" and not record.field_mapping_ids:
                raise ValidationError(_("At least one field mapping is required before activation."))

    @api.model_create_multi
    def create(self, vals_list):
        """Generate technical name on create."""
        for vals in vals_list:
            if not vals.get("technical_name") and vals.get("name"):
                vals["technical_name"] = self._generate_technical_name(vals["name"])
        return super().create(vals_list)

    def write(self, vals):
        """Track changes and prevent editing active CR types.

        For active types, only field mappings can be edited (if the type is
        studio-editable). Core fields like name, target_type, requires_approval
        remain locked.
        """
        for record in self:
            if record.state == "active" and not self.env.context.get("force_write"):
                # Fields that can be changed even when active (for editable types)
                editable_fields = {"field_mapping_ids"}
                # Fields that can always change (state management)
                allowed_fields = {"state", "deactivated_by_id", "deactivated_date"}

                changed_keys = set(vals.keys())
                protected_fields = changed_keys - allowed_fields - editable_fields

                if protected_fields:
                    raise UserError(
                        _(
                            "Cannot modify core settings of active change request type '%(name)s'. "
                            "Deactivate it first to change name, target type, or approval settings.",
                            name=record.name,
                        )
                    )

        result = super().write(vals)

        # If field mappings changed on active type, sync the detail model
        if "field_mapping_ids" in vals:
            for record in self:
                if record.state == "active" and record.detail_model_id:
                    record._sync_detail_model_fields()

        return result

    @api.model
    def _generate_technical_name(self, name):
        """Generate a technical code from the name."""
        # Convert to lowercase, replace spaces/special chars with underscore
        code = re.sub(r"[^a-z0-9]+", "_", name.lower())
        code = re.sub(r"_+", "_", code).strip("_")
        # Ensure uniqueness against both core and studio models
        base_code = f"x_cr_{code}"
        final_code = base_code
        counter = 1
        while self.env["spp.change.request.type"].search([("code", "=", final_code)], limit=1) or self.search(
            [("technical_name", "=", final_code)], limit=1
        ):
            final_code = f"{base_code}_{counter}"
            counter += 1
        return final_code

    def _pre_activate(self):
        """Create the actual change request type when activating."""
        self.ensure_one()

        if not self.field_mapping_ids:
            raise ValidationError(_("Cannot activate change request type without field mappings."))

        if self.spp_change_request_type_id:
            # Already created, just reactivate
            self.spp_change_request_type_id.write({"active": True})
            return

        # Create detail model (must start with x_ for manual models)
        detail_model_name = f"x_spp_cr_detail_{self.technical_name}"
        detail_model = self._create_detail_model_without_view(detail_model_name)

        # Create CR type
        cr_type_vals = self._prepare_cr_type_vals(detail_model_name)
        cr_type = self.env["spp.change.request.type"].sudo().create(cr_type_vals)

        # Create field mappings
        for mapping in self.field_mapping_ids:
            mapping._create_spp_mapping(cr_type)

        # Populate required_field_ids for fields marked as required
        self._populate_required_fields(cr_type, detail_model)

        # Link back to this record
        self.with_context(force_write=True).write(
            {
                "spp_change_request_type_id": cr_type.id,
                "detail_model_id": detail_model.id,
            }
        )

        # Create form view for the detail model and link it to the CR type
        form_view = self._create_detail_form_view(detail_model)
        if form_view:
            self._set_detail_form_view(form_view)

        _logger.info(
            "Studio CR type '%s' activated: created %s",
            self.name,
            detail_model_name,
        )

    def _create_detail_model_without_view(self, model_name):
        """Create the detail model for this CR type without creating its view.

        The view is created separately after the CR type is linked.
        """
        # Check if model already exists
        existing = self.env["ir.model"].search([("model", "=", model_name)], limit=1)
        if existing:
            return existing

        # Create new model (manual model, starts with x_)
        model_vals = {
            "name": self.name,
            "model": model_name,
            "state": "manual",
            "transient": False,
        }
        model = self.env["ir.model"].sudo().create(model_vals)

        # Add the required change_request_id field (like spp.cr.detail.base)
        self.env["ir.model.fields"].sudo().create(
            {
                "name": "x_change_request_id",
                "field_description": "Change Request",
                "model_id": model.id,
                "ttype": "many2one",
                "relation": "spp.change.request",
                "required": True,
                "on_delete": "cascade",
                "index": True,
                "state": "manual",
            }
        )

        # Add registrant_id field
        self.env["ir.model.fields"].sudo().create(
            {
                "name": "x_registrant_id",
                "field_description": "Registrant",
                "model_id": model.id,
                "ttype": "many2one",
                "relation": "res.partner",
                "state": "manual",
            }
        )

        # Create fields for each mapping
        for mapping in self.field_mapping_ids:
            field_vals = mapping._prepare_detail_field_vals(model)
            self.env["ir.model.fields"].sudo().create(field_vals)

        # Create access rights for the new model
        self._create_model_access_rights(model)

        return model

    def _populate_required_fields(self, cr_type, detail_model):
        """Populate required_field_ids on the CR type for fields marked as required.

        This method finds all field mappings with is_required=True and adds their
        corresponding ir.model.fields records to the CR type's required_field_ids.

        Args:
            cr_type: spp.change.request.type record
            detail_model: ir.model record for the detail model
        """
        self.ensure_one()

        # Find field mappings marked as required
        required_mappings = self.field_mapping_ids.filtered(lambda m: m.is_required)
        if not required_mappings:
            return

        # Build list of field names (with x_ prefix)
        required_field_names = [
            f"x_{mapping.field_name}" if not mapping.field_name.startswith("x_") else mapping.field_name
            for mapping in required_mappings
        ]

        # Find the ir.model.fields records for these fields
        field_records = (
            self.env["ir.model.fields"]
            .sudo()
            .search(
                [
                    ("model_id", "=", detail_model.id),
                    ("name", "in", required_field_names),
                ]
            )
        )

        if field_records:
            # Add to required_field_ids on the CR type
            cr_type.sudo().write({"required_field_ids": [Command.set(field_records.ids)]})
            _logger.info(
                "Set %d required fields for CR type '%s': %s",
                len(field_records),
                self.name,
                ", ".join(field_records.mapped("name")),
            )

    def _create_model_access_rights(self, model):
        """Create access rights for the dynamically created detail model.

        Sets up access for the change request security groups:
        - Manager: Full CRUD access (including create for manual scenarios)
        - Validator: Read and write access (no create - records created by system)
        - User: Read and write access (no create - records created by system)

        Note: Detail records are created automatically via _ensure_detail() using
        sudo, so regular users don't need create permission. This also prevents
        the "New" button from appearing in the form view.
        """
        access_model = self.env["ir.model.access"].sudo()

        # Define access rights for each group
        access_rules = [
            {
                "name": f"access_{model.model.replace('.', '_')}_manager",
                "model_id": model.id,
                "group_id": self.env.ref("spp_change_request_v2.group_cr_manager").id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
                "perm_unlink": True,
            },
            {
                "name": f"access_{model.model.replace('.', '_')}_validator",
                "model_id": model.id,
                "group_id": self.env.ref("spp_change_request_v2.group_cr_validator").id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": False,  # No create - records created by system
                "perm_unlink": False,
            },
            {
                "name": f"access_{model.model.replace('.', '_')}_user",
                "model_id": model.id,
                "group_id": self.env.ref("spp_change_request_v2.group_cr_user").id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": False,  # No create - records created by system
                "perm_unlink": False,
            },
        ]

        for access_vals in access_rules:
            # Check if access rule already exists
            existing = access_model.search(
                [
                    ("model_id", "=", access_vals["model_id"]),
                    ("group_id", "=", access_vals["group_id"]),
                ],
                limit=1,
            )
            if not existing:
                access_model.create(access_vals)
                _logger.info(
                    "Created access rule '%s' for model '%s'",
                    access_vals["name"],
                    model.model,
                )

    def _create_detail_form_view(self, model):
        """Create a form view for the dynamically created detail model.

        This form view:
        - Hides system fields (x_change_request_id, x_registrant_id, x_name)
        - Only shows fields defined in field_mapping_ids
        - Prevents creation of new records (create="false")

        Args:
            model: ir.model record for the detail model

        Returns:
            ir.ui.view record for the created form view
        """
        self.ensure_one()

        # Build the form view XML architecture
        arch = self._build_detail_form_arch()

        view_vals = {
            "name": f"{model.model}.form.studio",
            "model": model.model,
            "type": "form",
            "arch": arch,
            "priority": 16,  # Higher priority than default views
        }

        view = self.env["ir.ui.view"].sudo().create(view_vals)
        _logger.info(
            "Created form view '%s' for Studio CR detail model '%s'",
            view.name,
            model.model,
        )

        # Also create a window action to ensure proper control panel behavior
        self._create_detail_window_action(model, view)

        return view

    def _create_detail_window_action(self, model, form_view):
        """Create a window action for the detail model that disables create/delete.

        This ensures that when navigating to the detail model via URL or breadcrumb,
        the action settings (no create, no delete) are respected.

        Args:
            model: ir.model record for the detail model
            form_view: ir.ui.view record for the form view
        """
        self.ensure_one()

        # Check if action already exists
        existing_action = self.env["ir.actions.act_window"].search(
            [("res_model", "=", model.model), ("name", "=like", f"%{self.name}%")],
            limit=1,
        )
        if existing_action:
            # Update existing action
            existing_action.sudo().write(
                {
                    "view_id": form_view.id,
                    "context": "{'create': False, 'delete': False}",
                }
            )
            return existing_action

        action_vals = {
            "name": f"{self.name} Details",
            "res_model": model.model,
            "view_mode": "form",
            "view_id": form_view.id,
            "target": "current",
            "context": "{'create': False, 'delete': False}",
        }

        action = self.env["ir.actions.act_window"].sudo().create(action_vals)
        _logger.info(
            "Created window action '%s' for Studio CR detail model '%s'",
            action.name,
            model.model,
        )

    def _build_detail_form_arch(self):
        """Build the XML architecture for the detail form view.

        Returns:
            str: XML string for the form view architecture
        """
        self.ensure_one()

        # Start building the form
        form_parts = [
            '<?xml version="1.0"?>',
            '<form create="false" delete="false" duplicate="false">',
            "    <sheet>",
            '        <div class="oe_title">',
            f"            <h1>{self.name}</h1>",
            "        </div>",
            "",
            "        <!-- System fields (hidden) -->",
            '        <field name="x_change_request_id" invisible="1"/>',
            '        <field name="x_registrant_id" invisible="1"/>',
            "",
            "        <!-- Mapped fields -->",
            '        <group string="Change Details">',
        ]

        # Add fields from field mappings in sequence order
        sorted_mappings = self.field_mapping_ids.sorted(key=lambda m: m.sequence)
        for mapping in sorted_mappings:
            field_name = f"x_{mapping.field_name}"
            attrs = []
            if mapping.is_required:
                attrs.append('required="1"')
            if mapping.is_readonly:
                attrs.append('readonly="1"')
            attrs_str = " ".join(attrs)
            if attrs_str:
                attrs_str = " " + attrs_str
            form_parts.append(f'            <field name="{field_name}"{attrs_str}/>')

        # Close the form
        form_parts.extend(
            [
                "        </group>",
                "    </sheet>",
                "</form>",
            ]
        )

        return "\n".join(form_parts)

    def _set_detail_form_view(self, form_view):
        """Set the detail form view on the spp.change.request.type record.

        Args:
            form_view: ir.ui.view record
        """
        self.ensure_one()
        if self.spp_change_request_type_id:
            self.spp_change_request_type_id.sudo().write({"detail_form_view_id": form_view.id})

    def _sync_detail_model_fields(self):
        """Sync the detail model fields with current field mappings.

        This is called when field mappings are modified on an active type.
        It adds new fields and updates existing ones. Field removal is not
        supported (fields are kept but may become unused).
        """
        self.ensure_one()
        if not self.detail_model_id:
            return

        model = self.detail_model_id

        # Get existing fields on the detail model (excluding system fields)
        existing_fields = {
            f.name: f
            for f in self.env["ir.model.fields"].search(
                [
                    ("model_id", "=", model.id),
                    ("state", "=", "manual"),
                    ("name", "not in", ["x_change_request_id", "x_registrant_id"]),
                ]
            )
        }

        # Track which fields we've processed
        processed_fields = set()

        for mapping in self.field_mapping_ids:
            field_name = f"x_{mapping.field_name}"
            processed_fields.add(field_name)

            if field_name in existing_fields:
                # Update existing field properties (label, help, but NOT required)
                # Note: We never set required=True at database level to avoid NOT NULL constraints
                existing_field = existing_fields[field_name]
                update_vals = {}
                if existing_field.field_description != (mapping.label or mapping.field_name):
                    update_vals["field_description"] = mapping.label or mapping.field_name
                if existing_field.help != (mapping.help_text or ""):
                    update_vals["help"] = mapping.help_text or ""
                # Ensure required is always False at database level
                if existing_field.required:
                    update_vals["required"] = False
                if update_vals:
                    existing_field.sudo().write(update_vals)
            else:
                # Create new field
                field_vals = mapping._prepare_detail_field_vals(model)
                self.env["ir.model.fields"].sudo().create(field_vals)
                _logger.info(
                    "Added field '%s' to detail model '%s' for CR type '%s'",
                    field_name,
                    model.model,
                    self.name,
                )

        # Also sync the spp.change.request.type.mapping records
        if self.spp_change_request_type_id:
            self._sync_spp_mappings()

        # Sync required_field_ids based on current field mappings
        if self.spp_change_request_type_id:
            self._populate_required_fields(self.spp_change_request_type_id, model)

        # Sync the form view to reflect field changes
        self._sync_detail_form_view()

        _logger.info(
            "Synced field mappings for Studio CR type '%s' (model: %s)",
            self.name,
            model.model,
        )

    def _sync_spp_mappings(self):
        """Sync field mappings to the spp.change.request.type.mapping records."""
        self.ensure_one()
        if not self.spp_change_request_type_id:
            return

        cr_type = self.spp_change_request_type_id
        existing_mappings = {m.source_field: m for m in cr_type.apply_mapping_ids}

        for mapping in self.field_mapping_ids:
            source_field = f"x_{mapping.field_name}"
            target_field = mapping.field_name

            if source_field in existing_mappings:
                # Update existing mapping
                existing_mapping = existing_mappings[source_field]
                existing_mapping.write(
                    {
                        "target_field": target_field,
                        "sequence": mapping.sequence,
                    }
                )
            else:
                # Create new mapping
                mapping._create_spp_mapping(cr_type)

    def _sync_detail_form_view(self):
        """Sync the form view for the detail model with current field mappings.

        This updates the existing form view or creates one if it doesn't exist.
        """
        self.ensure_one()
        if not self.detail_model_id or not self.spp_change_request_type_id:
            return

        # Find existing form view
        existing_view = self.env["ir.ui.view"].search(
            [
                ("model", "=", self.detail_model_id.model),
                ("type", "=", "form"),
                ("name", "=like", "%.form.studio"),
            ],
            limit=1,
        )

        # Build new architecture
        new_arch = self._build_detail_form_arch()

        if existing_view:
            # Update existing view
            existing_view.sudo().write({"arch": new_arch})
            _logger.info(
                "Updated form view '%s' for Studio CR detail model '%s'",
                existing_view.name,
                self.detail_model_id.model,
            )
            # Ensure it's linked to the CR type
            if self.spp_change_request_type_id.detail_form_view_id != existing_view:
                self._set_detail_form_view(existing_view)
        else:
            # Create new view
            form_view = self._create_detail_form_view(self.detail_model_id)
            if form_view:
                self._set_detail_form_view(form_view)

    def _prepare_cr_type_vals(self, detail_model_name):
        """Prepare values for creating spp.change.request.type record."""
        vals = {
            "name": self.name,
            "code": self.technical_name,
            "description": self.description or "",
            "target_type": self.target_type,
            "detail_model": detail_model_name,
            "apply_strategy": "field_mapping",
            "auto_apply_on_approve": self.auto_apply,
            "active": True,
        }

        # Set up approval if configured
        if self.requires_approval and self.approval_group_id:
            # For now, we don't create approval definitions automatically
            # Users should configure them separately if needed
            pass

        return vals

    def _post_deactivate(self):
        """Deactivate the CR type when deactivating."""
        if self.spp_change_request_type_id:
            self.spp_change_request_type_id.write({"active": False})

    def _get_deactivation_impact(self):
        """Check if there are any pending/active change requests."""
        if not self.spp_change_request_type_id:
            return None

        count = self.env["spp.change.request"].search_count(
            [
                ("request_type_id", "=", self.spp_change_request_type_id.id),
                ("approval_state", "in", ["draft", "pending", "approved"]),
            ]
        )

        if count > 0:
            return _(
                "This change request type has %(count)d active or pending requests. "
                "Deactivating will prevent new requests but existing ones will remain.",
                count=count,
            )
        return None

    @api.model
    def _get_studio_config_type(self):
        return _("Change Request Type")

    def action_regenerate_form_view(self):
        """Regenerate the form view and update access rights for this CR type.

        This is useful for CR types that were activated before form view
        generation was implemented, or if the form view needs to be refreshed.
        Also updates access rights to prevent users from creating records directly.
        """
        self.ensure_one()
        if self.state != "active":
            raise UserError(_("Can only regenerate form view for active CR types."))

        if not self.detail_model_id:
            raise UserError(_("No detail model found for this CR type."))

        # Update access rights to disable create for users
        self._update_access_rights_no_create()

        # Sync the form view
        self._sync_detail_form_view()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Form view regenerated and access rights updated successfully."),
                "type": "success",
                "sticky": False,
            },
        }

    def _update_access_rights_no_create(self):
        """Update existing access rights to disable create permission.

        This is called when regenerating the form view to ensure users
        cannot create detail records directly.
        """
        self.ensure_one()
        if not self.detail_model_id:
            return

        access_model = self.env["ir.model.access"].sudo()

        # Find and update validator access
        validator_access = access_model.search(
            [
                ("model_id", "=", self.detail_model_id.id),
                ("group_id", "=", self.env.ref("spp_change_request_v2.group_cr_validator").id),
            ],
            limit=1,
        )
        if validator_access and validator_access.perm_create:
            validator_access.write({"perm_create": False})
            _logger.info(
                "Updated access rights for model '%s' (validator): perm_create=False",
                self.detail_model_id.model,
            )

        # Find and update user access
        user_access = access_model.search(
            [
                ("model_id", "=", self.detail_model_id.id),
                ("group_id", "=", self.env.ref("spp_change_request_v2.group_cr_user").id),
            ],
            limit=1,
        )
        if user_access and user_access.perm_create:
            user_access.write({"perm_create": False})
            _logger.info(
                "Updated access rights for model '%s' (user): perm_create=False",
                self.detail_model_id.model,
            )

    def action_view_change_requests(self):
        """View all change requests of this type."""
        self.ensure_one()
        if not self.spp_change_request_type_id:
            raise UserError(_("This change request type is not yet activated."))

        return self.spp_change_request_type_id.action_view_change_requests()
