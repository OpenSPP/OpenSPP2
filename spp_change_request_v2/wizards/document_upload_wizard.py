import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRDocumentUploadWizard(models.TransientModel):
    """Wizard for uploading documents to change requests with category selection."""

    _name = "spp.cr.document.upload.wizard"
    _description = "Change Request Document Upload Wizard"

    change_request_id = fields.Many2one(
        "spp.change.request",
        string="Change Request",
        required=True,
        ondelete="cascade",
    )

    document_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Document Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:cr_document_type')]",
        required=True,
        help="Select the type of document you are uploading",
    )

    document_type_domain = fields.Char(
        compute="_compute_document_type_domain",
        store=False,
    )

    # Legacy field for backward compatibility
    category_id = fields.Many2one(
        "spp.dms.category",
        string="Document Type (Deprecated)",
        help="Deprecated: Use document_type_id instead",
    )

    filename = fields.Char(
        string="Filename",
        required=True,
    )

    content = fields.Binary(
        string="File",
        required=True,
        attachment=False,
    )

    directory_id = fields.Many2one(
        "spp.dms.directory",
        string="Storage Directory",
        related="change_request_id.dms_directory_id",
        readonly=True,
    )

    show_required_categories = fields.Boolean(
        compute="_compute_show_required_categories",
        store=False,
    )

    required_categories_text = fields.Html(
        compute="_compute_required_categories_text",
        store=False,
        sanitize=False,
    )

    missing_required_documents = fields.Many2many(
        "spp.vocabulary.code",
        compute="_compute_missing_required_documents",
        store=False,
    )

    # Legacy field for backward compatibility
    missing_required_categories = fields.Many2many(
        "spp.dms.category",
        compute="_compute_missing_required_categories",
        store=False,
    )

    @api.depends(
        "change_request_id",
        "change_request_id.request_type_id",
        "change_request_id.request_type_id.required_document_ids",
        "change_request_id.document_ids",
        "change_request_id.document_ids.document_type_id",
    )
    def _compute_missing_required_documents(self):
        """Compute which required documents are still missing (not uploaded)."""
        for wizard in self:
            if wizard.change_request_id and wizard.change_request_id.request_type_id:
                cr_type = wizard.change_request_id.request_type_id
                required_docs = cr_type.required_document_ids

                if required_docs:
                    # Get already uploaded document types
                    uploaded_docs = wizard.change_request_id.document_ids.mapped("document_type_id")
                    # Find missing ones
                    missing_docs = required_docs - uploaded_docs
                    wizard.missing_required_documents = missing_docs
                else:
                    wizard.missing_required_documents = self.env["spp.vocabulary.code"]
            else:
                wizard.missing_required_documents = self.env["spp.vocabulary.code"]

    @api.depends(
        "change_request_id",
        "change_request_id.request_type_id",
        "change_request_id.request_type_id.required_document_type_ids",
        "change_request_id.document_ids",
        "change_request_id.document_ids.category_id",
    )
    def _compute_missing_required_categories(self):
        """Legacy method for backward compatibility."""
        for wizard in self:
            if wizard.change_request_id and wizard.change_request_id.request_type_id:
                cr_type = wizard.change_request_id.request_type_id
                required_cats = cr_type.required_document_type_ids

                if required_cats:
                    # Get already uploaded categories
                    uploaded_cats = wizard.change_request_id.document_ids.mapped("category_id")
                    # Find missing ones
                    missing_cats = required_cats - uploaded_cats
                    wizard.missing_required_categories = missing_cats
                else:
                    wizard.missing_required_categories = self.env["spp.dms.category"]
            else:
                wizard.missing_required_categories = self.env["spp.dms.category"]

    @api.depends(
        "change_request_id",
        "change_request_id.request_type_id",
        "change_request_id.request_type_id.available_document_ids",
    )
    def _compute_document_type_domain(self):
        """Compute domain for document type selection.

        Only show document types that are available for this CR type.
        If no available documents are configured, show all document types.
        """
        for wizard in self:
            if (
                wizard.change_request_id
                and wizard.change_request_id.request_type_id
                and wizard.change_request_id.request_type_id.available_document_ids
            ):
                # Restrict to available document types
                available_ids = wizard.change_request_id.request_type_id.available_document_ids.ids
                wizard.document_type_domain = str([("id", "in", available_ids)])
            else:
                # No restriction - show all document types
                wizard.document_type_domain = str(
                    [
                        (
                            "vocabulary_id.namespace_uri",
                            "=",
                            "urn:openspp:vocab:cr_document_type",
                        )
                    ]
                )

    @api.depends(
        "change_request_id",
        "change_request_id.request_type_id",
        "change_request_id.request_type_id.required_document_type_ids",
        "missing_required_categories",
    )
    def _compute_category_domain(self):
        """Legacy method for backward compatibility."""
        for wizard in self:
            # Allow all categories - user may want to upload additional documents
            wizard.category_domain = "[]"

    @api.depends(
        "change_request_id",
        "change_request_id.request_type_id",
        "change_request_id.request_type_id.required_document_ids",
        "change_request_id.request_type_id.required_document_type_ids",
        "change_request_id.request_type_id.document_validation_mode",
        "missing_required_documents",
        "missing_required_categories",
    )
    def _compute_show_required_categories(self):
        """Check if there are required documents to show."""
        for wizard in self:
            # Use new fields if available, otherwise fall back to legacy
            has_required = bool(
                wizard.change_request_id
                and wizard.change_request_id.request_type_id
                and (
                    (
                        wizard.change_request_id.request_type_id.required_document_ids
                        and wizard.missing_required_documents
                    )
                    or (
                        wizard.change_request_id.request_type_id.required_document_type_ids
                        and wizard.missing_required_categories
                    )
                )
            )
            wizard.show_required_categories = has_required

    @api.depends(
        "change_request_id",
        "change_request_id.request_type_id",
        "change_request_id.request_type_id.required_document_ids",
        "change_request_id.request_type_id.required_document_type_ids",
        "change_request_id.request_type_id.document_validation_mode",
        "missing_required_documents",
        "missing_required_categories",
    )
    def _compute_required_categories_text(self):
        """Build HTML showing required document types from CR type configuration.

        Only shows missing required documents (not yet uploaded).
        Uses 'Required' terminology when validation mode is warning/required.
        """
        for wizard in self:
            if not wizard.change_request_id or not wizard.change_request_id.request_type_id:
                wizard.required_categories_text = ""
                continue

            cr_type = wizard.change_request_id.request_type_id
            validation_mode = cr_type.document_validation_mode

            # Use new vocabulary-based fields if available, otherwise fall back to legacy
            required_docs = cr_type.required_document_ids
            missing_docs = wizard.missing_required_documents

            if not required_docs:
                # Fall back to legacy fields
                required_docs = cr_type.required_document_type_ids
                missing_docs = wizard.missing_required_categories

            # Determine terminology based on validation mode
            is_required = validation_mode in ("warning", "required")
            term = "Required" if is_required else "Available"

            if required_docs and missing_docs:
                # Show only missing documents
                categories_html = "".join(f"<li><strong>{doc.display_name}</strong></li>" for doc in missing_docs)

                # Different styling for required vs available
                alert_class = "alert-warning" if is_required else "alert-info"
                icon_class = "fa-exclamation-circle" if is_required else "fa-info-circle"

                wizard.required_categories_text = (
                    f'<div class="alert {alert_class}" role="alert">'
                    f'<i class="fa {icon_class}"></i> '
                    f'<strong>{term} document types for "{cr_type.name}":</strong>'
                    f'<ul class="mb-0 mt-2">{categories_html}</ul>'
                    f"</div>"
                )
            elif required_docs and not missing_docs:
                # All required documents uploaded
                wizard.required_categories_text = (
                    '<div class="alert alert-success" role="alert">'
                    '<i class="fa fa-check-circle"></i> '
                    "<strong>All required documents have been uploaded.</strong>"
                    "</div>"
                )
            elif not required_docs:
                # No specific requirements
                wizard.required_categories_text = (
                    '<div class="alert alert-info" role="alert">'
                    '<i class="fa fa-info-circle"></i> '
                    "All document types are available for this change request type."
                    "</div>"
                )
            else:
                wizard.required_categories_text = ""

    def action_upload(self):
        """Upload the document to DMS and link to change request."""
        self.ensure_one()

        if not self.change_request_id.dms_directory_id:
            raise UserError(_("No storage directory found for this change request. Please contact an administrator."))

        # Create DMS file with document type
        vals = {
            "name": self.filename,
            "directory_id": self.directory_id.id,
            "content": self.content,
        }

        # Use vocabulary-based document_type_id (new way)
        if self.document_type_id:
            vals["document_type_id"] = self.document_type_id.id
        # Fall back to category_id for backward compatibility
        elif self.category_id:
            vals["category_id"] = self.category_id.id

        dms_file = self.env["spp.dms.file"].create(vals)

        # Link to change request
        self.change_request_id.write(
            {
                "document_ids": [(4, dms_file.id)],
            }
        )

        doc_type_name = (
            self.document_type_id.display_name
            if self.document_type_id
            else (self.category_id.name if self.category_id else "Unknown")
        )
        _logger.info(
            "Uploaded document '%s' (type: %s) to CR %s",
            self.filename,
            doc_type_name,
            self.change_request_id.name,
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Document Uploaded"),
                "message": _("Document '%s' has been uploaded successfully.") % self.filename,
                "type": "success",
                "sticky": False,
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }
