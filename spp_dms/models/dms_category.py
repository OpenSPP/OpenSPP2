import logging

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPDMSCategory(models.Model):
    _name = "spp.dms.category"
    _description = "DMS Category"

    _order = "name asc"

    name = fields.Char(required=True, index="btree")
    file_ids = fields.One2many(
        comodel_name="spp.dms.file",
        inverse_name="category_id",
        string="Files",
        copy=False,
    )

    # File type restrictions
    allowed_extensions = fields.Char(
        help="Comma-separated list of allowed extensions (e.g., 'pdf,jpg,png'). Empty means all allowed."
    )
    blocked_extensions = fields.Char(
        default="exe,dll,bat,cmd,ps1,sh,msi,com,scr,vbs,js,jar,pif,application",
        help="Comma-separated blocked extensions (security). Applied before allowed list.",
    )
    allowed_mimetypes = fields.Char(
        help="Comma-separated MIME types with wildcard support (e.g., 'application/pdf,image/*')"
    )

    # Size limits
    max_file_size_mb = fields.Integer(
        default=50,
        help="Maximum file size in MB (0 = no limit)",
    )

    def validate_file(self, filename, mimetype, size_bytes):
        """Validate file against category rules.

        Args:
            filename (str): Name of the file
            mimetype (str): MIME type of the file
            size_bytes (float): Size in bytes

        Raises:
            ValidationError: If file violates category rules
        """
        self.ensure_one()

        # Extract extension from filename
        extension = ""
        if filename and "." in filename:
            extension = filename.rsplit(".", 1)[-1].lower()

        # Check blocked extensions first (security)
        if self.blocked_extensions:
            blocked = [ext.strip().lower() for ext in self.blocked_extensions.split(",") if ext.strip()]
            if extension and extension in blocked:
                raise ValidationError(
                    _(
                        "File extension '.%(ext)s' is blocked for security reasons in category '%(category)s'.",
                        ext=extension,
                        category=self.name,
                    )
                )

        # Check allowed extensions
        if self.allowed_extensions:
            allowed = [ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()]
            if extension and extension not in allowed:
                raise ValidationError(
                    _(
                        "File extension '.%(ext)s' is not allowed in category '%(category)s'. "
                        "Allowed extensions: %(allowed)s",
                        ext=extension,
                        category=self.name,
                        allowed=", ".join(allowed),
                    )
                )

        # Check MIME types (with wildcard support)
        if self.allowed_mimetypes and mimetype:
            allowed_mimes = [mime.strip() for mime in self.allowed_mimetypes.split(",") if mime.strip()]
            mime_match = False
            for allowed_mime in allowed_mimes:
                # Support wildcard patterns like "image/*"
                if allowed_mime.endswith("/*"):
                    prefix = allowed_mime[:-2]
                    if mimetype.startswith(prefix + "/"):
                        mime_match = True
                        break
                elif mimetype == allowed_mime:
                    mime_match = True
                    break

            if not mime_match:
                raise ValidationError(
                    _(
                        "File type '%(mimetype)s' is not allowed in category '%(category)s'. "
                        "Allowed types: %(allowed)s",
                        mimetype=mimetype,
                        category=self.name,
                        allowed=", ".join(allowed_mimes),
                    )
                )

        # Check file size
        if self.max_file_size_mb and self.max_file_size_mb > 0:
            max_bytes = self.max_file_size_mb * 1024 * 1024
            if size_bytes > max_bytes:
                raise ValidationError(
                    _(
                        "File size (%(size).2f MB) exceeds maximum allowed size of %(max)d MB "
                        "for category '%(category)s'.",
                        size=size_bytes / (1024 * 1024),
                        max=self.max_file_size_mb,
                        category=self.name,
                    )
                )
