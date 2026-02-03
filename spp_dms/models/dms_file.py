import base64
import binascii
import hashlib
import json
import logging
from collections import defaultdict

import psycopg2
from PIL import Image

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools import human_size
from odoo.tools.mimetypes import guess_mimetype

from ..tools import file_tools

_logger = logging.getLogger(__name__)


class SPPDMSFile(models.Model):
    _name = "spp.dms.file"
    _inherit = [
        "spp.dms.mixins.thumbnail",
    ]
    _description = "DMS File"
    _order = "name asc"

    name = fields.Char(required=True, index="btree", string="Filename")
    directory_id = fields.Many2one(
        comodel_name="spp.dms.directory",
        string="Directory",
        ondelete="restrict",
        required=True,
        index="btree",
    )
    path_names = fields.Char(
        compute="_compute_path",
        compute_sudo=True,
        readonly=True,
        store=False,
    )
    path_json = fields.Text(
        compute="_compute_path",
        compute_sudo=True,
        readonly=True,
        store=False,
    )
    content = fields.Binary(
        compute="_compute_content",
        inverse="_inverse_content",
        attachment=False,
        prefetch=False,
        required=True,
        store=False,
    )
    extension = fields.Char(compute="_compute_extension", readonly=True, store=True)
    mimetype = fields.Char(compute="_compute_mimetype", string="Type", readonly=True, store=True)

    size = fields.Float(readonly=True)
    human_size = fields.Char(readonly=True, compute="_compute_human_size", store=True)
    checksum = fields.Char(string="Checksum/SHA512", readonly=True, index="btree")
    content_file = fields.Binary(attachment=True, prefetch=False)

    category_id = fields.Many2one(
        comodel_name="spp.dms.category",
        string="Category",
        ondelete="restrict",
        index="btree",
    )

    image_1920 = fields.Image(compute="_compute_image_1920", store=True, readonly=False)
    color = fields.Integer(default=0)

    # Versioning fields
    version_ids = fields.One2many(
        comodel_name="spp.dms.file.version",
        inverse_name="file_id",
        string="Versions",
        readonly=True,
    )
    current_version_number = fields.Integer(
        string="Current Version",
        compute="_compute_current_version_number",
        store=True,
        readonly=True,
    )
    is_versioned = fields.Boolean(
        string="Enable Versioning",
        default=False,
        help="Enable version history tracking for this file",
    )
    version_count = fields.Integer(
        string="Version Count",
        compute="_compute_version_count",
        store=False,
    )

    @api.depends("mimetype", "content")
    def _compute_image_1920(self):
        """Provide thumbnail automatically if possible."""
        for one in self.filtered("mimetype"):
            # Image.MIME provides a dict of mimetypes supported by Pillow,
            # SVG is not present in the dict but is also a supported image format
            # lacking a better solution, it's being added manually
            # Some component modifies the PIL dictionary by adding PDF as a valid
            # image type, so it must be explicitly excluded.
            if one.mimetype != "application/pdf" and one.mimetype in (
                *Image.MIME.values(),
                "image/svg+xml",
            ):
                one.image_1920 = one.content

    @api.depends("name", "directory_id", "directory_id.parent_path")
    def _compute_path(self):
        model = self.env["spp.dms.directory"]
        for record in self:
            if record.display_name:
                path_names = [record.display_name]
                path_json = [
                    {
                        "model": record._name,
                        "name": record.display_name,
                        "id": isinstance(record.id, int) and record.id or 0,
                    }
                ]
                current_dir = record.directory_id
                while current_dir:
                    path_names.insert(0, current_dir.name)
                    path_json.insert(
                        0,
                        {
                            "model": model._name,
                            "name": current_dir.name,
                            "id": current_dir._origin.id,
                        },
                    )
                    current_dir = current_dir.parent_id
                record.update(
                    {
                        "path_names": "/".join(path_names),
                        "path_json": json.dumps(path_json),
                    }
                )
            else:
                record.update(
                    {
                        "path_names": "/",
                        "path_json": None,
                    }
                )

    @api.depends("content_file")
    def _compute_content(self):
        bin_size = self.env.context.get("bin_size", False)
        for record in self:
            if record.content_file:
                context = {"human_size": True} if bin_size else {"base64": True}
                record.content = record.with_context(**context).content_file

    def _inverse_content(self):
        updates = defaultdict(set)
        for record in self:
            values = {"content_file": False}
            binary = base64.b64decode(record.content or "")
            values = record._update_content_vals(values, binary)
            updates[tools.frozendict(values)].add(record.id)
        # with self.env.norecompute():
        for vals, ids in updates.items():
            self.browse(ids).write(dict(vals))

    def _update_content_vals(self, vals, binary):
        new_vals = vals.copy()
        new_vals.update(
            {
                "checksum": self._get_checksum(binary),
                "size": binary and len(binary) or 0,
            }
        )
        new_vals["content_file"] = self.content
        return new_vals

    def _get_checksum(self, binary):
        return hashlib.sha512(binary or b"").hexdigest()

    @api.depends("name", "mimetype", "content")
    def _compute_extension(self):
        for record in self:
            record.extension = file_tools.guess_extension(record.name, record.mimetype, record.content)

    @api.depends("content")
    def _compute_mimetype(self):
        for record in self:
            try:
                binary = base64.b64decode(record.content or "")
            except (binascii.Error, ValueError) as e:
                _logger.warning(
                    "Failed to decode content for mimetype detection: record_id=%s, error=%s",
                    record.id,
                    str(e),
                )
                record.mimetype = "application/octet-stream"  # Fallback mimetype
            else:
                record.mimetype = guess_mimetype(binary)

    @api.depends("size")
    def _compute_human_size(self):
        for item in self:
            item.human_size = human_size(item.size)

    @api.constrains("content", "category_id", "name")
    def _check_category_file_validation(self):
        """Validate file against category rules if category is set."""
        for record in self:
            if record.category_id and record.content:
                try:
                    record.category_id.validate_file(
                        filename=record.name,
                        mimetype=record.mimetype,
                        size_bytes=record.size,
                    )
                except Exception as e:
                    _logger.warning(
                        "File validation failed for category: file_id=%s, category=%s, error=%s",
                        record.id,
                        record.category_id.name,
                        str(e),
                    )
                    raise

    @api.depends("version_ids", "version_ids.is_current", "version_ids.version_number")
    def _compute_current_version_number(self):
        """Compute the current version number from version history."""
        for record in self:
            current_version = record.version_ids.filtered("is_current")
            if current_version:
                record.current_version_number = current_version[0].version_number
            else:
                record.current_version_number = 0

    @api.depends("version_ids")
    def _compute_version_count(self):
        """Count total number of versions."""
        for record in self:
            record.version_count = len(record.version_ids)

    def _create_new_version(self, comment=None):
        """Create a new version snapshot of the current file content.

        Uses atomic version number calculation with retry on conflict to handle
        race conditions when multiple users modify the same file concurrently.

        Args:
            comment (str, optional): Description of changes in this version

        Returns:
            spp.dms.file.version: The newly created version record
        """
        self.ensure_one()

        if not self.is_versioned:
            raise UserError(_("Versioning is not enabled for file '%s'.") % self.name)

        # Mark all existing versions as not current
        self.version_ids.write({"is_current": False})

        # Retry loop for handling race conditions on version number
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Get next version number atomically using SQL to prevent race conditions
                self.env.cr.execute(
                    """
                    SELECT COALESCE(MAX(version_number), 0) + 1
                    FROM spp_dms_file_version
                    WHERE file_id = %s
                """,
                    (self.id,),
                )
                next_version = self.env.cr.fetchone()[0]

                # Create new version
                version_vals = {
                    "file_id": self.id,
                    "version_number": next_version,
                    "content": self.content,
                    "checksum": self.checksum,
                    "size": self.size,
                    "mimetype": self.mimetype,
                    "comment": comment or "",
                    "is_current": True,
                }

                version = self.env["spp.dms.file.version"].create(version_vals)
                _logger.info(
                    "Created version %d for file: file_id=%s, checksum=%s",
                    next_version,
                    self.id,
                    self.checksum[:16] if self.checksum else "None",
                )
                return version

            except psycopg2.errors.UniqueViolation:
                if attempt < max_retries - 1:
                    _logger.warning(
                        "Version number conflict for file_id=%s, retrying (attempt %d/%d)",
                        self.id,
                        attempt + 1,
                        max_retries,
                    )
                    # Clear the failed transaction savepoint
                    self.env.cr.rollback()
                    continue
                else:
                    _logger.error(
                        "Failed to create version after %d attempts for file_id=%s",
                        max_retries,
                        self.id,
                    )
                    raise UserError(
                        _("Could not create version due to concurrent modifications. Please try again.")
                    ) from None

    def action_restore_version(self, version_id):
        """Restore file content from a specific version.

        Args:
            version_id (int): ID of the version to restore

        Returns:
            bool: True if restoration was successful
        """
        self.ensure_one()

        version = self.env["spp.dms.file.version"].browse(version_id)
        if not version.exists():
            raise UserError(_("Version not found."))

        if version.file_id != self:
            raise UserError(_("Version does not belong to this file."))

        # Create a new version before restoring (to preserve current state)
        self._create_new_version(comment=_("Auto-saved before restoring version %d") % version.version_number)

        # Restore content from the selected version (skip auto-versioning)
        self.with_context(skip_auto_version=True).write({"content": version.content})

        # Create another version for the restored content
        restored_version = self._create_new_version(comment=_("Restored from version %d") % version.version_number)

        _logger.info(
            "Restored file from version: file_id=%s, restored_version=%d, new_version=%d",
            self.id,
            version.version_number,
            restored_version.version_number,
        )

        return True

    def action_enable_versioning(self):
        """Enable versioning for this file and create initial version."""
        for record in self:
            if record.is_versioned:
                raise UserError(_("Versioning is already enabled for file '%s'.") % record.name)

            record.write({"is_versioned": True})

            # Create initial version
            record._create_new_version(comment=_("Initial version"))

            _logger.info("Enabled versioning for file: file_id=%s", record.id)

        return True

    def action_disable_versioning(self):
        """Disable versioning for this file (versions are preserved)."""
        for record in self:
            if not record.is_versioned:
                raise UserError(_("Versioning is not enabled for file '%s'.") % record.name)

            record.write({"is_versioned": False})
            _logger.info("Disabled versioning for file: file_id=%s", record.id)

        return True

    def action_view_versions(self):
        """Open a view showing all versions of this file."""
        self.ensure_one()
        return {
            "name": _("Versions - %s") % self.name,
            "type": "ir.actions.act_window",
            "res_model": "spp.dms.file.version",
            "view_mode": "list,form",
            "domain": [("file_id", "=", self.id)],
            "context": {"default_file_id": self.id},
        }

    def write(self, vals):
        """Override write to auto-create version on content change if versioning enabled."""
        res = super().write(vals)

        # Auto-create version if content changed and versioning is enabled
        if "content" in vals:
            for record in self:
                if record.is_versioned and record.content:
                    # Check if this is not already part of a version operation
                    if not self.env.context.get("skip_auto_version"):
                        try:
                            record.with_context(skip_auto_version=True)._create_new_version(comment=_("Auto-saved"))
                        except Exception as e:
                            _logger.warning(
                                "Failed to auto-create version: file_id=%s, error=%s",
                                record.id,
                                str(e),
                            )

        return res
