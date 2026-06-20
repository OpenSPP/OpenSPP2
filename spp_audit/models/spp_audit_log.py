import ast
import logging

from dateutil import tz
from markupsafe import escape as html_escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _safe_parse_audit_data(data_str):
    """Safely parse audit log data string.

    Falls back to empty dict if parsing fails to prevent crashes.
    """
    if not data_str:
        return {"old": {}, "new": {}}
    try:
        return ast.literal_eval(data_str)
    except (ValueError, SyntaxError) as e:
        _logger.warning("Could not parse audit data: %s. Data: %s...", e, data_str[:100])
        return {"old": {}, "new": {}}


class SppAuditLog(models.Model):
    _name = "spp.audit.log"
    _description = "SPP Audit Log"
    _order = "create_date desc, id desc"

    audit_rule_id = fields.Many2one("spp.audit.rule", required=True)
    name = fields.Char("Resource Name", size=256, compute="_compute_name")
    create_date = fields.Datetime("Date", readonly=True)
    user_id = fields.Many2one("res.users", "User", required=True, readonly=True)
    model_id = fields.Many2one("ir.model", "Model", required=True, readonly=True, ondelete="cascade")
    model = fields.Char(related="model_id.model", string="Model Name")
    res_id = fields.Integer("Resource Id", readonly=True)
    method = fields.Char(size=64, readonly=True)
    data = fields.Text(readonly=True)
    data_html = fields.Html("HTML Data", readonly=True, compute="_compute_data_html")

    # Fields from spp_audit_post
    parent_data_html = fields.Html("Parent HTML Data", readonly=True, compute="_compute_parent_data_html")
    parent_model_id = fields.Many2one("ir.model", "Parent Model", readonly=True, ondelete="cascade")
    parent_res_ids_str = fields.Text(readonly=True)
    log_to = fields.Text(compute="_compute_log_to")

    ALLOW_DELETE = False

    @api.model_create_multi
    def create(self, vals_list):
        logs = super().create(vals_list)

        # Check if mail.thread posting is enabled via context
        # Default is False (off) - must be explicitly enabled per rule
        post_to_thread = self.env.context.get("audit_post_to_thread", False)

        if post_to_thread:
            for res in logs:
                records = []
                msg = ""
                if res.parent_model_id and res.parent_model_id.is_mail_thread:
                    if res.parent_res_ids_str:
                        res_ids = list(map(int, res.parent_res_ids_str.split(",")))
                        records = self.env[res.parent_model_id.model].browse(res_ids)
                    msg = res.parent_data_html
                elif res.model_id and res.model_id.is_mail_thread:
                    records = self.env[res.model_id.model].browse(res.res_id)
                    msg = res.data_html

                for record in records:
                    record.message_post(body=msg)

        return logs

    def _compute_name(self):
        for rec in self:
            if rec.model_id and rec.res_id:
                # Audit metadata (the record's name) must render even when the
                # audited record is outside the viewer's row-level (e.g.
                # area-scoped) access; otherwise an out-of-scope record raises
                # AccessError and breaks the whole audit-log view. Scope is
                # limited to display_name; who may open the Audit Log is governed
                # by this model's own ACL.
                # nosemgrep: odoo-sudo-without-context -- audit metadata, see above
                record = rec.env[rec.model_id.model].sudo().browse(rec.res_id).exists()
                if record:
                    rec.name = record.display_name
                else:
                    data = _safe_parse_audit_data(rec.data)
                    rec_name = rec.env[rec.model_id.model]._rec_name
                    if rec_name in data["new"]:
                        rec.name = data["new"][rec_name]
                    elif rec_name in data["old"]:
                        rec.name = data["old"][rec_name]
                    else:
                        rec.name = f"id={rec.res_id}"
            else:
                rec.name = ""

    def _format_value(self, field, value):
        """
        The function `_format_value` formats a given value based on the field type in a specific
        context.

        :param field: The `field` parameter represents the field object that contains information about
        the field being formatted, such as its type, selection options, and related model
        :param value: The `value` parameter is the value of the field that needs to be formatted. It can
        be of any data type depending on the field type
        :return: the formatted value based on the field type and value provided.
        """
        self.ensure_one()
        if not value and field.type not in ("boolean", "integer", "float"):
            return ""
        if field.type == "selection":
            selection = field.selection
            if callable(selection):
                selection = selection(self.env[self.model_id.model])
            return dict(selection).get(value, value)
        if field.type == "many2one" and value:
            return self.env[field.comodel_name].browse(value).exists().display_name or value
        if field.type == "reference" and value:
            res_model, res_id = value.split(",")
            return self.env[res_model].browse(int(res_id)).exists().display_name or value
        if field.type in ("one2many", "many2many") and value:
            return ", ".join(
                [self.env[field.comodel_name].browse(rec_id).exists().display_name or str(rec_id) for rec_id in value]
            )
        if field.type == "binary" and value:
            return "&lt;binary data&gt;"
        if field.type == "datetime":
            # Handle both datetime objects and ISO format strings (from sanitization)
            if isinstance(value, str):
                return value  # Already formatted as string
            from_tz = tz.tzutc()
            to_tz = tz.gettz(self.env.user.tz)
            datetime_wo_tz = value
            datetime_with_tz = datetime_wo_tz.replace(tzinfo=from_tz)
            return fields.Datetime.to_string(datetime_with_tz.astimezone(to_tz))
        return value

    def _get_content(self):
        """
        The function `_get_content` retrieves the content of a record, including the old and new values
        of its fields, and returns it as a list of tuples.
        :return: a list of tuples containing the label, old value, and new value for each field that has
        changed in the record.
        """

        self.ensure_one()
        content = []
        data = _safe_parse_audit_data(self.data)
        RecordModel = self.env[self.model_id.model]
        for fname in set(data["new"].keys()) | set(data["old"].keys()):
            field = RecordModel._fields.get(fname)
            if field and (not field.groups or self.env.user.has_group(field.groups)):
                old_value = self._format_value(field, data["old"].get(fname, ""))
                new_value = self._format_value(field, data["new"].get(fname, ""))
                if old_value != new_value:
                    label = field.get_description(self.env)["string"]
                    content.append((label, old_value, new_value))
        return content

    def _compute_data_html(self):
        for rec in self:
            thead = ""
            for head in (_("Field"), _("Old value"), _("New value")):
                thead += f"<th>{head}</th>"
            thead = f"<thead><tr>{thead}</tr></thead>"
            tbody = ""
            for line in rec._get_content():
                row = ""
                for item in line:
                    row += f"<td>{html_escape(str(item))}</td>"
                tbody += f"<tr>{row}</tr>"
            tbody = f"<tbody>{tbody}</tbody>"
            rec.data_html = f'<table class="o_list_view table table-condensed table-striped">{thead}{tbody}</table>'

    def _parent_get_content(self):
        """
        The function `_parent_get_content` retrieves the content of a record and compares the old and
        new values of its fields, returning a list of tuples containing the record name, field label,
        old value, and new value for each field that has changed.
        :return: a list of tuples containing information about the changes made to a record. Each tuple
        in the list represents a change and contains the following elements:
        """
        self.ensure_one()
        content = []
        data = _safe_parse_audit_data(self.data)
        RecordModel = self.env[self.model_id.model]
        record = RecordModel.browse(self.res_id)
        if record and hasattr(record, "name"):
            record_name = record.name
        else:
            record_name = self.model_id.name
        for fname in set(data["new"].keys()) | set(data["old"].keys()):
            field = RecordModel._fields.get(fname)
            if field and (not field.groups or self.env.user.has_group(field.groups)):
                old_value = self._format_value(field, data["old"].get(fname, ""))
                new_value = self._format_value(field, data["new"].get(fname, ""))
                if old_value != new_value:
                    label = field.get_description(self.env)["string"]
                    content.append((record_name, label, old_value, new_value))
        return content

    def _compute_parent_data_html(self):
        for rec in self:
            thead = ""
            for head in (_("Model"), _("Field"), _("Old value"), _("New value")):
                thead += f"<th>{head}</th>"
            thead = f"<thead><tr>{thead}</tr></thead>"
            tbody = ""
            for line in rec._parent_get_content():
                row = ""
                for item in line:
                    row += f"<td>{html_escape(str(item))}</td>"
                tbody += f"<tr>{row}</tr>"
            tbody = f"<tbody>{tbody}</tbody>"
            rec.parent_data_html = (
                f'<table class="o_list_view table table-condensed table-striped">{thead}{tbody}</table>'
            )

    @api.depends("parent_model_id")
    def _compute_log_to(self):
        for rec in self:
            if rec.parent_model_id:
                rec.log_to = f"{rec.parent_model_id.model}({rec.parent_res_ids_str})"
            else:
                rec.log_to = f"{rec.model_id.model}({rec.res_id})"

    def unlink(self):
        if not self.ALLOW_DELETE:
            raise UserError(_("You cannot remove audit logs!"))

        return super().unlink()
