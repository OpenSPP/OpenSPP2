import logging

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class RestoreVersionWizard(models.TransientModel):
    _name = "spp.dms.restore.version.wizard"
    _description = "Restore File Version Wizard"

    file_id = fields.Many2one(
        comodel_name="spp.dms.file",
        string="File",
        required=True,
        readonly=True,
    )
    version_id = fields.Many2one(
        comodel_name="spp.dms.file.version",
        string="Version to Restore",
        required=True,
        domain="[('file_id', '=', file_id)]",
    )
    version_number = fields.Integer(
        related="version_id.version_number",
        string="Version Number",
        readonly=True,
    )
    created_date = fields.Datetime(
        related="version_id.created_date",
        string="Created On",
        readonly=True,
    )
    created_by_id = fields.Many2one(
        related="version_id.created_by_id",
        string="Created By",
        readonly=True,
    )
    comment = fields.Text(
        related="version_id.comment",
        string="Version Comment",
        readonly=True,
    )

    def action_restore(self):
        """Execute the version restore operation."""
        self.ensure_one()

        if not self.version_id:
            raise UserError(_("Please select a version to restore."))

        if not self.file_id:
            raise UserError(_("File not found."))

        # Call the restore method on the file
        self.file_id.action_restore_version(self.version_id.id)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Version %d has been restored successfully.") % self.version_number,
                "type": "success",
                "sticky": False,
            },
        }
