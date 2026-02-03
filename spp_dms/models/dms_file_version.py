import base64
import hashlib
import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class SPPDMSFileVersion(models.Model):
    _name = "spp.dms.file.version"
    _description = "DMS File Version"
    _order = "version_number desc"

    file_id = fields.Many2one(
        comodel_name="spp.dms.file",
        string="File",
        required=True,
        ondelete="cascade",
        index=True,
    )
    version_number = fields.Integer(string="Version", required=True, readonly=True)
    content = fields.Binary(
        string="Content",
        attachment=True,
        required=True,
        readonly=True,
    )
    checksum = fields.Char(
        string="Checksum/SHA512",
        readonly=True,
        index=True,
    )
    size = fields.Float(string="Size (bytes)", readonly=True)
    mimetype = fields.Char(string="MIME Type", readonly=True)

    created_by_id = fields.Many2one(
        comodel_name="res.users",
        string="Created By",
        default=lambda self: self.env.uid,
        readonly=True,
        index=True,
    )
    created_date = fields.Datetime(
        string="Created On",
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    comment = fields.Text(
        string="Version Comment",
        help="Description of changes in this version",
    )
    is_current = fields.Boolean(
        string="Current Version",
        default=False,
        index=True,
        readonly=True,
    )

    _unique_version = models.Constraint(
        "UNIQUE(file_id, version_number)",
        "Version number must be unique per file",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to compute checksum and mimetype."""
        for vals in vals_list:
            if "content" in vals:
                binary = base64.b64decode(vals["content"] or "")
                vals["checksum"] = self._compute_checksum(binary)
                vals["size"] = len(binary) if binary else 0
                if "mimetype" not in vals:
                    vals["mimetype"] = guess_mimetype(binary)
        return super().create(vals_list)

    def _compute_checksum(self, binary):
        """Compute SHA512 checksum of binary content."""
        return hashlib.sha512(binary or b"").hexdigest()

    @api.constrains("is_current", "file_id")
    def _check_single_current_version(self):
        """Ensure only one version per file is marked as current."""
        for record in self:
            if record.is_current:
                current_versions = self.search(
                    [
                        ("file_id", "=", record.file_id.id),
                        ("is_current", "=", True),
                        ("id", "!=", record.id),
                    ]
                )
                if current_versions:
                    raise ValidationError(
                        _("Only one version can be marked as current for file '%s'.") % record.file_id.name
                    )

    @api.depends("version_number", "is_current")
    def _compute_display_name(self):
        """Compute display name showing version number."""
        for record in self:
            name = _("Version %d") % record.version_number
            if record.is_current:
                name += _(" (Current)")
            record.display_name = name
