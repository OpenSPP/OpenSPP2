import json
import logging
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import audit_decorator
from ..tools.config import AuditConfig
from .spp_audit_backend import AuditBackendRegistry

_logger = logging.getLogger(__name__)


def _sanitize_value_for_storage(value):
    """Sanitize a value for safe storage and retrieval via ast.literal_eval.

    Handles Odoo Command objects, datetime objects, and other non-literal values.
    """
    if value is None:
        return None

    # Handle Odoo Command objects (they're tuples like (4, id, 0) or (6, 0, [ids]))
    # Command objects have a specific structure when converted
    if hasattr(value, "__class__") and value.__class__.__name__ == "Command":
        # Command objects are actually just integers representing the command type
        # but when used in vals, they come as tuples
        return repr(value)

    # Handle lists/tuples that may contain Command tuples
    if isinstance(value, (list, tuple)):
        # Check if it looks like a Command tuple: (int, int, value)
        if (
            isinstance(value, tuple)
            and len(value) == 3
            and isinstance(value[0], int)
            and value[0] in (0, 1, 2, 3, 4, 5, 6)
        ):
            # This is a Command tuple, convert the inner value too
            return (value[0], value[1], _sanitize_value_for_storage(value[2]))
        # Recursively sanitize list/tuple contents
        sanitized = [_sanitize_value_for_storage(item) for item in value]
        return type(value)(sanitized) if isinstance(value, tuple) else sanitized

    # Handle dictionaries recursively
    if isinstance(value, dict):
        return {k: _sanitize_value_for_storage(v) for k, v in value.items()}

    # Handle datetime objects
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()

    # Handle bytes
    if isinstance(value, bytes):
        return "<binary data>"

    # Handle basic types that are safe for literal_eval
    if isinstance(value, (str, int, float, bool, type(None))):
        return value

    # For anything else, convert to string representation
    # This is a fallback to prevent ast.literal_eval failures
    try:
        # Try to get a safe representation
        return str(value)
    except Exception:
        return "<unserializable>"


class SppAuditRule(models.Model):
    _name = "spp.audit.rule"
    _description = "SPP Audit Rule"
    _parent_name = "parent_id"
    _parent_store = True

    name = fields.Char(required=True)
    is_log_create = fields.Boolean("Log Creation", default=True)
    is_log_write = fields.Boolean("Log Update", default=True)
    is_log_unlink = fields.Boolean("Log Deletion", default=True)
    is_view_logs = fields.Boolean("View Logs Action Menu", default=True)

    # Lifecycle action logging (for explicit logging, not decorator-based)
    is_log_activate = fields.Boolean(
        "Log Activation",
        default=False,
        help="Log when records are activated (requires explicit call to log_lifecycle_action)",
    )
    is_log_deactivate = fields.Boolean(
        "Log Deactivation",
        default=False,
        help="Log when records are deactivated (requires explicit call to log_lifecycle_action)",
    )
    is_log_state_change = fields.Boolean(
        "Log State Changes",
        default=False,
        help="Log generic state changes like set_draft, approve, reject",
    )

    # File access logging
    is_log_download = fields.Boolean(
        "Log File Downloads",
        default=False,
        help="Log when files associated with this model are downloaded",
    )
    is_log_preview = fields.Boolean(
        "Log File Previews",
        default=False,
        help="Log when files associated with this model are previewed",
    )
    is_log_export = fields.Boolean(
        "Log Data Exports",
        default=False,
        help="Log when data from this model is exported",
    )

    # Mail thread integration (optional, default off)
    is_post_to_thread = fields.Boolean(
        "Post to Chatter",
        default=False,
        help="Post audit summary to record's chatter. Enable only for "
        "low-volume, human-reviewed records. Disabled by default.",
    )

    model_id = fields.Many2one(
        "ir.model",
        "Model",
        required=True,
        ondelete="cascade",
    )

    field_to_log_ids = fields.Many2many("ir.model.fields", string="Fields to log")
    field_to_log_ids_domain = fields.Char(
        compute="_compute_field_to_log_ids_domain",
        readonly=True,
    )

    action_id = fields.Many2one("ir.actions.act_window", "Add in the 'More' menu", readonly=True)

    # Fields from spp_audit_post
    parent_id = fields.Many2one(
        "spp.audit.rule",
        string="Parent Rule",
        domain=[("model_id.is_mail_thread", "=", True)],
    )
    child_ids = fields.One2many("spp.audit.rule", "parent_id", string="Related Rules", readonly=True)
    is_mail_thread = fields.Boolean(related="model_id.is_mail_thread")
    field_id = fields.Many2one(
        "ir.model.fields",
        ondelete="cascade",
        help="Field that connects this model to the model of the parent rule.",
    )
    field_id_domain = fields.Char(
        compute="_compute_field_id_domain",
        readonly=True,
    )
    parent_path = fields.Char(index=True)

    sql_constraints = [("name_uniq", "unique(name)", "Name must be unique")]

    _methods = ["create", "write", "unlink"]

    _ignored_fields = [
        "__last_update",
        "message_ids",
        "message_last_post",
        "write_date",
    ]

    @api.constrains("model_id")
    def _check_model(self):
        for rec in self:
            if self.env[self._name].search_count([("model_id", "=", rec.model_id.id), ("id", "!=", rec.id)]):
                raise ValidationError(_("A rule is already existed for the selected model."))

    @api.constrains("parent_id", "field_id")
    def _check_model_id_field_id(self):
        for rec in self:
            if rec.parent_id and not rec.field_id:
                raise ValidationError(_("Field is required if the rule is a child rule."))
            if rec.parent_id and rec.field_id.relation != rec.parent_id.model_id.model:
                error_msg = f"Field's relation should be {rec.parent_id.model_id.name}"
                raise ValidationError(_(error_msg))

    def _process_action_id(self):
        for rec in self:
            if rec.is_view_logs:
                if not rec.action_id:
                    # Check action menu if view audit logs for a model is already existing
                    ir_act_window_id = self.env["ir.actions.act_window"].search(
                        [
                            ("binding_model_id", "=", rec.model_id.id),
                            ("res_model", "=", "spp.audit.log"),
                            ("name", "=", "View logs"),
                        ],
                        limit=1,
                    )

                    if ir_act_window_id:
                        # If action menu is existing, save existing action menu to action_id
                        ir_act_window_id.update(
                            {
                                "binding_view_types": "form",
                            }
                        )
                        rec.action_id = ir_act_window_id
                    else:
                        # Create action menu
                        vals = {
                            "name": _("View logs"),
                            "res_model": "spp.audit.log",
                            "binding_model_id": rec.model_id.id,
                            "binding_view_types": "form",
                            "domain": "[('model_id','=', {}), ('res_id', '=', active_id), ('method', 'in', {})]".format(
                                rec.model_id.id,
                                [method.replace("_", "") for method in self._methods],
                            ),
                        }
                        rec.action_id = self.env["ir.actions.act_window"].create(vals)
            else:
                action_menu = rec.action_id
                if action_menu:
                    action_menu.unlink()
        return

    @api.model
    def get_audit_rules(self, method):
        """
        The function returns audit rules based on the specified method.

        :param method: The "method" parameter is a string that specifies the type of operation being
        performed. It can have one of the following values: "create", "write", or "unlink"
        :return: The method is returning a search result of "spp.audit.rule" records based on the
        specified domain.
        """
        domain = [("model_id.model", "=", self._name)]
        if method == "create":
            domain.append(("is_log_create", "=", True))
        elif method == "write":
            domain.append(("is_log_write", "=", True))
        elif method == "unlink":
            domain.append(("is_log_unlink", "=", True))

        return self.env["spp.audit.rule"].sudo().search(domain)

    @api.model
    def _register_hook(self, ids=None):
        """
        The function `_register_hook` adds a decorator to certain methods of models in order to enable
        auditing.

        :param ids: The `ids` parameter is a list of record IDs. It is used to specify a subset of
        records on which the hook should be registered. If `ids` is not provided or is an empty list,
        the hook will be registered on all records of the model
        :return: a boolean value indicating whether any updates were made.
        """
        # Run hook registration with sudo() as a system-level operation
        # restricted by spp_audit.group_audit_manager ACLs.
        self = (
            self.sudo()
        )  # nosemgrep: odoo-sudo-without-context - Audit hook wiring runs as a trusted admin-only operation.
        updated = False
        if ids:
            rules = self.browse(ids)
        else:
            rules = self.search([])
        for rule in rules:
            if rule.model_id.model not in self.env.registry.models:
                continue
            RecordModel = self.env[rule.model_id.model]

            # Add attribute get_audit_rules to models that are being created or updated in spp.audit.rule
            type(RecordModel).get_audit_rules = SppAuditRule.get_audit_rules

            for method in self._methods:
                func = getattr(RecordModel, method)
                while hasattr(func, "origin"):
                    if func.__name__.startswith("audit_"):
                        break
                    func = func.origin
                else:
                    # Monkey patch the methods to add a decorator
                    # Note: _patch_method was removed in Odoo 19, so we patch manually
                    original_method = getattr(type(RecordModel), method)
                    decorated_method = audit_decorator(method)
                    decorated_method.origin = original_method
                    setattr(type(RecordModel), method, decorated_method)
            updated = bool(ids)
        if updated:
            self.env.registry.clear_cache()
        return updated

    def _log_config_change(self, action, old_values=None, new_values=None):
        """Log audit configuration changes to all enabled backends.

        This method bypasses the normal audit flow to ensure configuration
        changes are ALWAYS logged to non-database backends (file, syslog, HTTP),
        even if database backend is disabled. This is a tamper-resistance measure.

        :param action: 'rule_created', 'rule_modified', 'rule_deleted'
        :param old_values: Dict of old field values (for modify/delete)
        :param new_values: Dict of new field values (for create/modify)
        """
        for rule in self:
            entry = {
                "type": "audit_config_change",
                "action": action,
                "rule_id": rule.id,
                "rule_name": rule.name,
                "model": rule.model_id.model if rule.model_id else None,
                "user_id": self.env.uid,
                "user_login": self.env.user.login,
                "old_values": old_values or {},
                "new_values": new_values or {},
            }

            # Always dispatch to file/syslog/http backends for config changes
            # This cannot be disabled via database settings
            AuditBackendRegistry.dispatch(entry, self.env)

            _logger.info(
                "Audit config change: %s - rule '%s' (model: %s) by user %s",
                action,
                rule.name,
                rule.model_id.model if rule.model_id else "N/A",
                self.env.user.login,
            )

    @api.model_create_multi
    def create(self, vals_list):
        rules = super().create(vals_list)
        for rule in rules:
            rule._process_action_id()
            if self._register_hook(rule.id):
                self.pool.signal_changes()

            # Self-protection: log rule creation directly to file backend
            rule._log_config_change(
                "rule_created",
                new_values={
                    "name": rule.name,
                    "model": rule.model_id.model if rule.model_id else None,
                    "is_log_create": rule.is_log_create,
                    "is_log_write": rule.is_log_write,
                    "is_log_unlink": rule.is_log_unlink,
                },
            )

        return rules

    def write(self, vals):
        # Capture old values before write for self-protection logging
        old_values_map = {}
        for rule in self:
            old_values_map[rule.id] = {
                "name": rule.name,
                "model": rule.model_id.model if rule.model_id else None,
                "is_log_create": rule.is_log_create,
                "is_log_write": rule.is_log_write,
                "is_log_unlink": rule.is_log_unlink,
            }

        res = super().write(vals)
        self._process_action_id()
        if self._register_hook(self.ids):
            self.pool.signal_changes()

        # Self-protection: log rule modification directly to file backend
        for rule in self:
            new_values = {
                "name": rule.name,
                "model": rule.model_id.model if rule.model_id else None,
                "is_log_create": rule.is_log_create,
                "is_log_write": rule.is_log_write,
                "is_log_unlink": rule.is_log_unlink,
            }
            # Only log if relevant values changed
            old = old_values_map.get(rule.id, {})
            if old != new_values:
                rule._log_config_change("rule_modified", old_values=old, new_values=new_values)

        return res

    def unlink(self):
        # Self-protection: log rule deletion directly to file backend BEFORE delete
        for rule in self:
            rule._log_config_change(
                "rule_deleted",
                old_values={
                    "name": rule.name,
                    "model": rule.model_id.model if rule.model_id else None,
                    "is_log_create": rule.is_log_create,
                    "is_log_write": rule.is_log_write,
                    "is_log_unlink": rule.is_log_unlink,
                },
            )

        for rec in self:
            audit_rule_count = len(self.env["spp.audit.rule"].search([("model_id", "=", rec.model_id.id)]))
            if audit_rule_count == 1 and rec.action_id:
                rec.action_id.unlink()
        return super().unlink()

    @classmethod
    def _format_data_to_log(cls, old_values, new_values, fields_to_log):
        """
        The function `_format_data_to_log` takes in old and new values, removes ignored fields, compares
        the values, and returns a dictionary of data with differences between old and new values.

        :param cls: The parameter `cls` refers to the class itself. It is used to access class
        attributes and methods within the method
        :param old_values: The parameter "old_values" is a list of dictionaries representing the old
        values of some data. Each dictionary represents a set of values for a specific data record
        :param new_values: The `new_values` parameter is a list of dictionaries or a single dictionary
        containing the new values for a particular resource. Each dictionary represents a resource and
        its corresponding field-value pairs
        :return: a dictionary containing the formatted data. The dictionary has resource IDs as keys,
        and the values are dictionaries with "old" and "new" keys. The "old" and "new" dictionaries
        contain the field-value pairs for the old and new values respectively.
        """
        data = {}
        for age in ("old", "new"):
            vals_list = old_values if age == "old" else new_values
            if isinstance(vals_list, dict):
                vals_list = [vals_list]
            for vals in vals_list or []:
                res_id = vals.pop("id")
                vals = dict(filter(lambda x: x[0] in fields_to_log, vals.items()))
                # Sanitize values to ensure they can be stored and retrieved safely
                vals = {k: _sanitize_value_for_storage(v) for k, v in vals.items()}
                if vals:
                    data.setdefault(res_id, {"old": {}, "new": {}})[age] = vals
        for res_id in list(data.keys()):
            all_fields = set(data[res_id]["old"].keys()) | set(data[res_id]["new"].keys())
            for field in all_fields:
                if data[res_id]["old"].get(field) == data[res_id]["new"].get(field):
                    del data[res_id]["old"][field]
                    del data[res_id]["new"][field]
            if data[res_id]["old"] == data[res_id]["new"]:
                del data[res_id]
        return data

    @api.depends("model_id")
    def _compute_field_to_log_ids_domain(self):
        for rec in self:
            domain = [("id", "=", 0)]
            if rec.model_id:
                domain = [
                    ("model_id", "=", rec.model_id.id),
                    ("name", "not in", self._ignored_fields),
                ]
            rec.field_to_log_ids_domain = json.dumps(domain)

    @api.depends("model_id", "parent_id")
    def _compute_field_id_domain(self):
        for rec in self:
            domain = [("id", "=", 0)]
            if rec.model_id and rec.parent_id:
                domain = [
                    ("model_id", "=", rec.model_id.id),
                    ("relation", "=", rec.parent_id.model_id.model),
                ]
            rec.field_id_domain = json.dumps(domain)

    @api.onchange("model_id")
    def _onchange_model_id(self):
        if self.model_id:
            self.update(
                {
                    "field_to_log_ids": None,
                    "field_id": None,
                }
            )

        return

    def get_most_parent(self, res_ids):
        """
        The function `get_most_parent` retrieves the model name and ids of the most parent rule based on
        a given set of resource ids.

        :param res_ids: The `res_ids` parameter is a list of record IDs
        :return: a tuple containing the model name and a list of record IDs.
        """
        if not self.parent_id:
            return None, []

        # Initialize variable to be used in while loop
        current_rule_id = self
        parent_rule_id = self.parent_id
        current_model_records = {"model": self.model_id.model, "ids": res_ids}

        # get the model name and ids of the most parent rule
        # loop will break if a rule doesn't have parent rule
        while parent_rule_id:
            current_records = self.env[current_model_records["model"]].browse(current_model_records["ids"])
            current_model_records["model"] = parent_rule_id.model_id.model
            new_ids = []
            for record in current_records:
                new_ids.extend(getattr(record, current_rule_id.field_id.name).ids)
            current_model_records["ids"] = new_ids

            current_rule_id = parent_rule_id
            parent_rule_id = parent_rule_id.parent_id

        return current_model_records["model"], [str(record_id) for record_id in current_model_records["ids"]]

    def get_audit_log_vals(self, res_id, method, data):
        self.ensure_one()

        parent_model, parent_res_ids = self.get_most_parent([res_id])

        return {
            "audit_rule_id": self.id,
            "user_id": self.env.uid,
            # Use sudo() here so audit logging remains reliable even if the caller
            # has limited read access on spp.audit.rule; access is controlled by
            # spp_audit.group_audit_manager and hook wiring uses sudo() already.
            "model_id": self.sudo().model_id.id,  # nosemgrep: odoo-sudo-without-context - System-level audit logging of model operations.
            "res_id": res_id,
            "method": method,
            "data": repr(data[res_id]),
            "parent_model_id": self.env["ir.model"].search([("model", "=", parent_model)], limit=1).id,
            "parent_res_ids_str": ",".join(parent_res_ids),
        }

    def log(self, method, old_values=None, new_values=None):
        """
        Log changes made to a model's records by dispatching to all enabled backends.

        :param method: The operation type: "create", "write", "unlink", or lifecycle action
        :param old_values: Dict of previous field values
        :param new_values: Dict of updated field values
        """
        if not (old_values or new_values):
            return

        fields_to_log = self.field_to_log_ids.mapped("name")
        data = self._format_data_to_log(old_values, new_values, fields_to_log)

        # Only proceed if there's actual data to log
        if not data:
            return

        # Use only the first rule to avoid duplicates if multiple rules match
        rec = self[:1]

        for res_id in data:
            # Build backend entry for non-DB backends
            backend_entry = {
                "rule_name": rec.name,
                "model": rec.model_id.model,
                "res_id": res_id,
                "method": method,
                "user_id": self.env.uid,
                "user_login": self.env.user.login,
                "data": data[res_id],
            }

            # Dispatch to file/syslog/http backends
            AuditBackendRegistry.dispatch(backend_entry, self.env)

            # Database backend: create spp.audit.log record (maintains UI compatibility)
            if AuditConfig.get_bool("backend_db", env=self.env):
                audit_log_vals = rec.get_audit_log_vals(res_id, method, data)
                # Pass is_post_to_thread to control mail.thread posting
                self.env["spp.audit.log"].sudo().with_context(audit_post_to_thread=rec.is_post_to_thread).create(
                    audit_log_vals
                )

    @api.model
    def log_lifecycle_action(self, model_name, record_id, action, old_values=None, new_values=None):
        """Log a lifecycle action for a record.

        This is called explicitly from models (not via decorator).
        Used for activate/deactivate/approve/reject/set_draft/download/preview/export actions.

        :param model_name: Technical model name (e.g., 'spp.studio.field')
        :param record_id: ID of the record being logged
        :param action: Action type - 'activate', 'deactivate', 'set_draft', 'approve', 'reject',
                       'download', 'preview', 'export'
        :param old_values: Dict of old field values (optional)
        :param new_values: Dict of new field values (optional)
        :return: True if logged successfully, False if no rule or action not enabled
        """
        rule = self.search([("model_id.model", "=", model_name)], limit=1)
        if not rule:
            return False

        # Check if this action type should be logged
        action_field_map = {
            "activate": "is_log_activate",
            "deactivate": "is_log_deactivate",
            "set_draft": "is_log_state_change",
            "approve": "is_log_state_change",
            "reject": "is_log_state_change",
            "download": "is_log_download",
            "preview": "is_log_preview",
            "export": "is_log_export",
        }

        field_name = action_field_map.get(action)
        if field_name and not getattr(rule, field_name, False):
            return False

        # Build data dict similar to the decorator-based logging
        data = {"old": old_values or {}, "new": new_values or {}}

        # Build backend entry for non-DB backends
        backend_entry = {
            "rule_name": rule.name,
            "model": model_name,
            "res_id": record_id,
            "method": action,
            "user_id": self.env.uid,
            "user_login": self.env.user.login,
            "data": data,
        }

        # Dispatch to file/syslog/http backends
        AuditBackendRegistry.dispatch(backend_entry, self.env)

        # Database backend: create spp.audit.log record
        if AuditConfig.get_bool("backend_db", env=self.env):
            parent_model, parent_res_ids = rule.get_most_parent([record_id])

            audit_log_vals = {
                "audit_rule_id": rule.id,
                "user_id": self.env.uid,
                "model_id": rule.model_id.id,
                "res_id": record_id,
                "method": action,
                "data": repr(data),
                "parent_model_id": self.env["ir.model"].search([("model", "=", parent_model)], limit=1).id,
                "parent_res_ids_str": ",".join(parent_res_ids) if parent_res_ids else "",
            }

            self.env["spp.audit.log"].sudo().with_context(audit_post_to_thread=rule.is_post_to_thread).create(
                audit_log_vals
            )

        return True

    @api.model
    def create_rules(
        self,
        rule_name: str,
        model: str,
        fields_to_log: list,
        view_logs=True,
        log_create=True,
        log_write=True,
        log_unlink=True,
        parent_rule_name="",
        connecting_field_name="",
        **kwargs,
    ):
        rule = self.env["spp.audit.rule"].search([("name", "=", rule_name)], limit=1)

        model_id = self.env["ir.model"].search([("model", "=", model)])
        if model_id:
            field_to_log_list = []
            for field_name in fields_to_log:
                field = self.env["ir.model.fields"].search(
                    [("model_id", "=", model_id.id), ("name", "=", field_name)], limit=1
                )
                if field:
                    field_to_log_list.append((4, field.id))

            vals = {
                "name": rule_name,
                "model_id": model_id.id,
                "field_to_log_ids": field_to_log_list,
                "is_view_logs": view_logs,
                "is_log_create": log_create,
                "is_log_write": log_write,
                "is_log_unlink": log_unlink,
            }

            if parent_rule_name and connecting_field_name:
                parent_rule = self.env["spp.audit.rule"].search([("name", "=", parent_rule_name)], limit=1)
                if parent_rule:
                    connecting_field = self.env["ir.model.fields"].search(
                        [
                            ("name", "=", connecting_field_name),
                            ("model_id", "=", model_id.id),
                            ("relation", "=", parent_rule.model_id.model),
                        ]
                    )
                    if connecting_field:
                        vals.update(
                            {
                                "parent_id": parent_rule.id,
                                "field_id": connecting_field.id,
                            }
                        )

            if rule:
                rule.write(vals)
            else:
                self.env["spp.audit.rule"].create(vals)

        return
