# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import base64
import logging
import zipfile
from io import BytesIO

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import rdflib
except ImportError:
    rdflib = None

_logger = logging.getLogger(__name__)

# Well-known AGROVOC root concepts for filtering
AGROVOC_ROOT_CONCEPTS = {
    "crops": "c_1972",  # crops
    "cereals": "c_1495",  # cereals
    "vegetables": "c_8174",  # vegetables
    "fruits": "c_3131",  # fruits
    "livestock": "c_4397",  # livestock
    "cattle": "c_1391",  # cattle
    "poultry": "c_6145",  # poultry
    "fish": "c_15903",  # fish
    "aquaculture": "c_550",  # aquaculture
    "irrigation": "c_3954",  # irrigation
    "fertilizers": "c_2867",  # fertilizers
    "pesticides": "c_13397",  # pesticides
}


class AgrovocImport(models.Model):
    """AGROVOC RDF Import Job.

    Handles batch import of AGROVOC vocabulary data from RDF N-Triples format.
    Uses job_worker for scalable processing of large datasets.

    Features:
    - Filtered imports by concept hierarchy (e.g., only cereals)
    - Multilingual label extraction
    - Parent-child relationship preservation
    """

    _name = "spp.agrovoc.import"
    _description = "AGROVOC Import Job"
    _order = "create_date desc"

    name = fields.Char(
        required=True,
        default=lambda self: _("AGROVOC Import %s") % fields.Datetime.now(),
        help="Name of this import job",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        help="Current state of the import job",
    )
    vocabulary_id = fields.Many2one(
        comodel_name="spp.vocabulary",
        string="Target Vocabulary",
        required=True,
        help="Vocabulary to import codes into",
    )

    # Language settings
    primary_language = fields.Char(
        string="Primary Language",
        default="en",
        required=True,
        help="Primary language for display names (e.g., 'en', 'es', 'fr')",
    )
    additional_languages = fields.Char(
        string="Additional Languages",
        default="es,fr,ar,zh,pt,ru",
        help="Comma-separated list of additional languages to extract for translations",
    )

    # Filtering options
    filter_mode = fields.Selection(
        selection=[
            ("all", "All Concepts"),
            ("root", "Under Root Concept"),
            ("list", "Specific Concept List"),
        ],
        string="Filter Mode",
        default="all",
        required=True,
        help="How to filter which concepts to import",
    )
    root_concept_type = fields.Selection(
        selection=[
            ("crops", "Crops (c_1972)"),
            ("cereals", "Cereals (c_1495)"),
            ("vegetables", "Vegetables (c_8174)"),
            ("fruits", "Fruits (c_3131)"),
            ("livestock", "Livestock (c_4397)"),
            ("cattle", "Cattle (c_1391)"),
            ("poultry", "Poultry (c_6145)"),
            ("fish", "Fish (c_15903)"),
            ("aquaculture", "Aquaculture (c_550)"),
            ("irrigation", "Irrigation (c_3954)"),
            ("custom", "Custom Root URI"),
        ],
        string="Root Concept",
        help="Import only concepts that are narrower than this root concept",
    )
    custom_root_uri = fields.Char(
        string="Custom Root URI",
        help="Custom AGROVOC URI to use as root (e.g., http://aims.fao.org/aos/agrovoc/c_1972)",
    )
    concept_list = fields.Text(
        string="Concept List",
        help="Newline-separated list of AGROVOC concept codes to import (e.g., c_8373, c_6599)",
    )

    # Hierarchy options
    include_hierarchy = fields.Boolean(
        string="Include Hierarchy",
        default=True,
        help="Extract parent-child relationships from AGROVOC broader/narrower relations",
    )
    max_depth = fields.Integer(
        string="Maximum Depth",
        default=3,
        help="Maximum depth of hierarchy to import (0 = unlimited)",
    )

    # File input
    file_data = fields.Binary(
        string="RDF File (.nt or .nt.zip)",
        attachment=True,
        help="AGROVOC N-Triples RDF file (can be zipped)",
    )
    file_name = fields.Char(
        string="File Name",
        help="Name of the uploaded file",
    )

    # Statistics
    total_count = fields.Integer(
        string="Total Concepts",
        readonly=True,
        help="Total number of concepts found matching filter",
    )
    imported_count = fields.Integer(
        string="Imported",
        readonly=True,
        help="Number of codes successfully imported",
    )
    skipped_count = fields.Integer(
        string="Skipped",
        readonly=True,
        help="Number of codes skipped (already exist)",
    )
    error_count = fields.Integer(
        string="Errors",
        readonly=True,
        help="Number of codes that failed to import",
    )

    error_log = fields.Text(
        string="Error Log",
        readonly=True,
        help="Log of errors encountered during import",
    )

    @api.model
    def _check_rdflib(self):
        """Check if rdflib is available."""
        if rdflib is None:
            raise UserError(
                _(
                    "The Python package 'rdflib' is required for AGROVOC import. "
                    "Please install it using: pip install rdflib"
                )
            )

    def _extract_file_content(self):
        """Extract content from uploaded file (handle zip if needed)."""
        self.ensure_one()
        if not self.file_data:
            raise UserError(_("No file uploaded"))

        content = BytesIO(base64.b64decode(self.file_data))

        # Check if it's a zip file
        if self.file_name and self.file_name.endswith(".zip"):
            try:
                with zipfile.ZipFile(content) as zf:
                    # Find first .nt file in zip
                    nt_files = [f for f in zf.namelist() if f.endswith(".nt")]
                    if not nt_files:
                        raise UserError(_("No .nt file found in zip archive"))
                    with zf.open(nt_files[0]) as f:
                        return f.read()
            except zipfile.BadZipFile as e:
                raise UserError(_("Invalid zip file: %s") % str(e)) from e
        else:
            return content.read()

    def _parse_rdf_graph(self, content):
        """Parse RDF N-Triples content into graph."""
        self._check_rdflib()
        graph = rdflib.Graph()
        try:
            graph.parse(data=content, format="nt")
            return graph
        except (rdflib.exceptions.ParserError, ValueError, SyntaxError) as e:
            raise UserError(_("Failed to parse RDF file: %s") % str(e)) from e

    def _get_root_uri(self):
        """Get the root URI for filtering based on settings."""
        if self.filter_mode != "root":
            return None

        if self.root_concept_type == "custom":
            if not self.custom_root_uri:
                raise UserError(_("Custom root URI is required when using custom root"))
            return self.custom_root_uri

        if self.root_concept_type and self.root_concept_type in AGROVOC_ROOT_CONCEPTS:
            code = AGROVOC_ROOT_CONCEPTS[self.root_concept_type]
            return f"http://aims.fao.org/aos/agrovoc/{code}"

        return None

    def _get_concept_list(self):
        """Get list of specific concepts to import."""
        if self.filter_mode != "list" or not self.concept_list:
            return None

        codes = []
        for line in self.concept_list.strip().split("\n"):
            code = line.strip()
            if code:
                # Handle both raw codes and full URIs
                if code.startswith("http"):
                    codes.append(code)
                else:
                    codes.append(f"http://aims.fao.org/aos/agrovoc/{code}")
        return codes

    def _get_descendants(self, graph, root_uri, max_depth=0):
        """Get all descendant concepts of a root using SKOS narrower relations.

        Args:
            graph: RDF graph
            root_uri: URI of root concept
            max_depth: Maximum depth (0 = unlimited)

        Returns:
            set: Set of URIs that are descendants of root
        """
        skos = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
        root_ref = rdflib.URIRef(root_uri)

        descendants = {root_uri}
        current_level = {root_ref}
        depth = 0

        while current_level and (max_depth == 0 or depth < max_depth):
            next_level = set()
            for concept in current_level:
                # Get narrower concepts
                for narrower in graph.objects(concept, skos.narrower):
                    uri_str = str(narrower)
                    if uri_str not in descendants:
                        descendants.add(uri_str)
                        next_level.add(narrower)
                # Also check broader (inverse relationship)
                for broader_of in graph.subjects(skos.broader, concept):
                    uri_str = str(broader_of)
                    if uri_str not in descendants:
                        descendants.add(uri_str)
                        next_level.add(broader_of)

            current_level = next_level
            depth += 1

        return descendants

    def _extract_concepts(self, graph):
        """Extract AGROVOC concepts from RDF graph with filtering and translations."""
        self.ensure_one()

        # AGROVOC namespaces
        skos = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")
        agrovoc = rdflib.Namespace("http://aims.fao.org/aos/agrovoc/")

        # Get additional languages
        additional_langs = []
        if self.additional_languages:
            additional_langs = [lang.strip() for lang in self.additional_languages.split(",") if lang.strip()]

        # Determine which concepts to include
        allowed_uris = None
        if self.filter_mode == "root":
            root_uri = self._get_root_uri()
            if root_uri:
                _logger.info("Building descendant tree from root: %s", root_uri)
                allowed_uris = self._get_descendants(graph, root_uri, self.max_depth)
                _logger.info("Found %d descendants", len(allowed_uris))
        elif self.filter_mode == "list":
            allowed_uris = set(self._get_concept_list() or [])

        # Build parent mapping for hierarchy
        parent_map = {}
        if self.include_hierarchy:
            for subject in graph.subjects(rdflib.RDF.type, skos.Concept):
                for broader in graph.objects(subject, skos.broader):
                    parent_map[str(subject)] = str(broader)

        concepts = []

        # Find all AGROVOC concepts
        for subject in graph.subjects(rdflib.RDF.type, skos.Concept):
            uri_str = str(subject)

            # Only process AGROVOC URIs
            if not uri_str.startswith(str(agrovoc)):
                continue

            # Apply filtering
            if allowed_uris is not None and uri_str not in allowed_uris:
                continue

            # Extract code from URI
            code = uri_str.split("/")[-1]

            # Get all labels
            labels = {}
            for label in graph.objects(subject, skos.prefLabel):
                if hasattr(label, "language"):
                    labels[label.language] = str(label)

            # Get primary language label
            display = labels.get(self.primary_language)
            if not display:
                continue

            # Get translations
            translations = {}
            for lang in additional_langs:
                if lang in labels and lang != self.primary_language:
                    translations[lang] = labels[lang]

            # Get parent code if hierarchy enabled
            parent_code = None
            if self.include_hierarchy and uri_str in parent_map:
                parent_uri = parent_map[uri_str]
                if allowed_uris is None or parent_uri in allowed_uris:
                    parent_code = parent_uri.split("/")[-1]

            # Get definition (scopeNote)
            definition = None
            for note in graph.objects(subject, skos.scopeNote):
                if hasattr(note, "language") and note.language == self.primary_language:
                    definition = str(note)
                    break

            concepts.append(
                {
                    "code": code,
                    "display": display,
                    "uri": uri_str,
                    "parent_code": parent_code,
                    "definition": definition,
                    "translations": translations,
                }
            )

        return concepts

    def action_process(self):
        """Start processing the import."""
        self.ensure_one()
        self._check_rdflib()

        if not self.file_data:
            raise UserError(_("Please upload a file first"))

        if not self.vocabulary_id:
            raise UserError(_("Please select a target vocabulary"))

        self.write({"state": "processing"})

        # Use job_worker for batch processing
        self.with_delay()._process_import()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import Started"),
                "message": _("AGROVOC import job has been queued for processing"),
                "type": "info",
                "sticky": False,
            },
        }

    def _process_import(self):
        """Process the import (runs in job_worker)."""
        self.ensure_one()
        _logger.info("Starting AGROVOC import for vocabulary: %s", self.vocabulary_id.name)

        errors = []
        imported = 0
        skipped = 0
        failed = 0

        try:
            # Extract and parse file
            content = self._extract_file_content()
            graph = self._parse_rdf_graph(content)

            # Extract concepts
            concepts = self._extract_concepts(graph)
            total = len(concepts)

            self.write({"total_count": total})
            _logger.info("Found %d concepts to import", total)

            # First pass: create all codes without parents
            code_map = {}  # code -> record id
            batch_size = 100
            for i in range(0, total, batch_size):
                batch = concepts[i : i + batch_size]

                for concept in batch:
                    try:
                        # Check if code already exists
                        existing = self.env["spp.vocabulary.code"].search(
                            [
                                ("vocabulary_id", "=", self.vocabulary_id.id),
                                ("code", "=", concept["code"]),
                            ],
                            limit=1,
                        )

                        if existing:
                            code_map[concept["code"]] = existing.id
                            skipped += 1
                            continue

                        # Create new code (without parent initially)
                        vals = {
                            "vocabulary_id": self.vocabulary_id.id,
                            "code": concept["code"],
                            "display": concept["display"],
                            "reference_uri": concept["uri"],
                            "is_local": True,
                        }
                        if concept.get("definition"):
                            vals["definition"] = concept["definition"]

                        new_code = self.env["spp.vocabulary.code"].create(vals)
                        code_map[concept["code"]] = new_code.id
                        imported += 1

                    except (ValueError, TypeError) as e:
                        failed += 1
                        error_msg = f"Failed to import {concept['code']}: {str(e)}"
                        errors.append(error_msg)
                        _logger.warning(error_msg)

            # Second pass: update parent relationships
            if self.include_hierarchy:
                _logger.info("Updating parent relationships...")
                for concept in concepts:
                    if concept.get("parent_code") and concept["code"] in code_map:
                        parent_id = code_map.get(concept["parent_code"])
                        if parent_id:
                            try:
                                self.env["spp.vocabulary.code"].browse(code_map[concept["code"]]).write(
                                    {"parent_id": parent_id}
                                )
                            except (ValueError, TypeError) as e:
                                _logger.warning(
                                    "Failed to set parent for %s: %s",
                                    concept["code"],
                                    str(e),
                                )

            # Update statistics
            self.write(
                {
                    "state": "done",
                    "imported_count": imported,
                    "skipped_count": skipped,
                    "error_count": failed,
                    "error_log": "\n".join(errors) if errors else False,
                }
            )

            _logger.info(
                "AGROVOC import completed: %d imported, %d skipped, %d failed",
                imported,
                skipped,
                failed,
            )

        except (UserError, ValueError, TypeError, OSError) as e:
            error_msg = f"Import failed: {str(e)}"
            _logger.error(error_msg, exc_info=True)
            self.write(
                {
                    "state": "failed",
                    "error_log": error_msg,
                }
            )
            raise

    def action_preview(self):
        """Preview what would be imported without actually importing."""
        self.ensure_one()
        self._check_rdflib()

        if not self.file_data:
            raise UserError(_("Please upload a file first"))

        content = self._extract_file_content()
        graph = self._parse_rdf_graph(content)
        concepts = self._extract_concepts(graph)

        # Show preview
        preview_lines = [_("Preview of concepts to import:"), "=" * 50]
        for concept in concepts[:50]:  # Show first 50
            line = f"{concept['code']}: {concept['display']}"
            if concept.get("parent_code"):
                line += f" (parent: {concept['parent_code']})"
            preview_lines.append(line)

        if len(concepts) > 50:
            preview_lines.append(f"... and {len(concepts) - 50} more")

        preview_lines.append("=" * 50)
        preview_lines.append(_("Total: %d concepts") % len(concepts))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Import Preview"),
                "message": "\n".join(preview_lines),
                "type": "info",
                "sticky": True,
            },
        }
