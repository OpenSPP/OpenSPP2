# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AgrovocImportWizard(models.TransientModel):
    """Wizard for importing AGROVOC vocabulary data.

    Provides a user-friendly interface for:
    1. Uploading AGROVOC RDF files
    2. Selecting target vocabulary
    3. Filtering by language
    4. Previewing before import
    """

    _name = "spp.agrovoc.import.wizard"
    _description = "AGROVOC Import Wizard"

    # Step 1: File upload
    file_data = fields.Binary(
        string="AGROVOC File",
        required=True,
        help="Upload AGROVOC N-Triples file (.nt or .nt.zip)",
    )
    file_name = fields.Char(
        string="File Name",
        help="Name of the uploaded file",
    )

    # Step 2: Configuration
    vocabulary_type = fields.Selection(
        selection=[
            ("crops", "Crops (FAO ICC)"),
            ("livestock", "Livestock"),
            ("aquaculture", "Aquaculture (FAO ASFIS)"),
        ],
        string="Vocabulary Type",
        required=True,
        default="crops",
        help="Select which vocabulary to import into",
    )
    vocabulary_id = fields.Many2one(
        comodel_name="spp.vocabulary",
        string="Target Vocabulary",
        compute="_compute_vocabulary_id",
        store=True,
        readonly=False,
        help="Vocabulary to import codes into",
    )
    language = fields.Char(
        string="Language",
        default="en",
        required=True,
        help="Language code for labels (e.g., 'en', 'es', 'fr', 'ar')",
    )

    # Step 3: Preview
    preview_data = fields.Text(
        string="Preview",
        readonly=True,
        help="Preview of codes to be imported",
    )
    preview_count = fields.Integer(
        string="Concepts Found",
        readonly=True,
        help="Number of concepts found in file",
    )

    @api.depends("vocabulary_type")
    def _compute_vocabulary_id(self):
        """Set vocabulary based on selected type."""
        for wizard in self:
            if wizard.vocabulary_type == "crops":
                vocab = self.env.ref("spp_farmer_registry_vocabularies.vocab_crops", raise_if_not_found=False)
            elif wizard.vocabulary_type == "livestock":
                vocab = self.env.ref("spp_farmer_registry_vocabularies.vocab_livestock", raise_if_not_found=False)
            elif wizard.vocabulary_type == "aquaculture":
                vocab = self.env.ref("spp_farmer_registry_vocabularies.vocab_aquaculture", raise_if_not_found=False)
            else:
                vocab = False

            wizard.vocabulary_id = vocab

    def action_preview(self):
        """Generate preview of concepts to import.

        Returns:
            dict: Action to refresh wizard view
        """
        self.ensure_one()

        if not self.file_data:
            raise UserError(_("Please upload a file first"))

        # Create temporary import job for preview
        import_job = self.env["spp.agrovoc.import"].create(
            {
                "name": _("Preview: %s") % self.vocabulary_id.name,
                "vocabulary_id": self.vocabulary_id.id,
                "primary_language": self.language,
                "file_data": self.file_data,
                "file_name": self.file_name,
            }
        )

        try:
            # Extract and parse
            content = import_job._extract_file_content()
            graph = import_job._parse_rdf_graph(content)
            concepts = import_job._extract_concepts(graph)

            # Generate preview text
            preview_lines = [_("Found %d concepts") % len(concepts), ""]
            preview_lines.append(_("First 20 concepts:"))
            for concept in concepts[:20]:
                preview_lines.append(f"  - {concept['code']}: {concept['display']}")

            if len(concepts) > 20:
                preview_lines.append(f"  ... and {len(concepts) - 20} more")

            self.write(
                {
                    "preview_data": "\n".join(preview_lines),
                    "preview_count": len(concepts),
                }
            )

            # Delete temporary job
            import_job.unlink()

        except Exception as e:
            # Delete temporary job on error
            import_job.unlink()
            raise UserError(_("Preview failed: %s") % str(e)) from e

        return {
            "type": "ir.actions.act_window",
            "res_model": "spp.agrovoc.import.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_import(self):
        """Create import job and start processing.

        Returns:
            dict: Action to view import job
        """
        self.ensure_one()

        if not self.file_data:
            raise UserError(_("Please upload a file first"))

        if not self.vocabulary_id:
            raise UserError(_("Please select a target vocabulary"))

        # Create import job
        import_job = self.env["spp.agrovoc.import"].create(
            {
                "name": _("Import: %s") % self.vocabulary_id.name,
                "vocabulary_id": self.vocabulary_id.id,
                "primary_language": self.language,
                "file_data": self.file_data,
                "file_name": self.file_name,
            }
        )

        # Start processing
        import_job.action_process()

        # Return action to view import job
        return {
            "type": "ir.actions.act_window",
            "name": _("AGROVOC Import Job"),
            "res_model": "spp.agrovoc.import",
            "res_id": import_job.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_cancel(self):
        """Cancel wizard.

        Returns:
            dict: Action to close wizard
        """
        return {"type": "ir.actions.act_window_close"}
