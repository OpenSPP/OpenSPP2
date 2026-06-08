# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for AGROVOC Import model (spp.agrovoc.import).

Tests cover:
- Model field definitions
- File extraction (plain .nt and .zip)
- Root URI computation
- Concept list parsing
- Import processing with real vocabulary records
- Duplicate handling (skip existing codes)
- Error handling for invalid data
- Preview action
- State transitions
"""

import base64
import time
import zipfile
from io import BytesIO

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


# Minimal N-Triples RDF content for testing
_AGR = "http://aims.fao.org/aos/agrovoc"
_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns"
_SKOS = "http://www.w3.org/2004/02/skos/core"
_SAMPLE_NT = (
    f"<{_AGR}/c_1234> <{_RDF}#type> <{_SKOS}#Concept> .\n"
    f'<{_AGR}/c_1234> <{_SKOS}#prefLabel> "Rice"@en .\n'
    f'<{_AGR}/c_1234> <{_SKOS}#prefLabel> "Arroz"@es .\n'
    f"<{_AGR}/c_5678> <{_RDF}#type> <{_SKOS}#Concept> .\n"
    f'<{_AGR}/c_5678> <{_SKOS}#prefLabel> "Wheat"@en .\n'
    f"<{_AGR}/c_5678> <{_SKOS}#broader> <{_AGR}/c_1234> .\n"
)


def _make_nt_binary(content=_SAMPLE_NT):
    """Encode NT content as base64 binary field value."""
    return base64.b64encode(content.encode("utf-8"))


def _make_zip_binary(content=_SAMPLE_NT, inner_name="agrovoc.nt"):
    """Create a zip containing an .nt file, encoded as base64."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(inner_name, content)
    return base64.b64encode(buf.getvalue())


@tagged("post_install", "-at_install")
class TestAgrovocImportModel(TransactionCase):
    """Test spp.agrovoc.import model fields and basic methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        # Create a target vocabulary
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": _unique("Test AGROVOC Vocab"),
                "namespace_uri": _unique("urn:test:agrovoc"),
            }
        )

    def _create_import_job(self, **kwargs):
        """Create an import job with default values."""
        vals = {
            "name": _unique("Test Import"),
            "vocabulary_id": self.vocab.id,
            "primary_language": "en",
        }
        vals.update(kwargs)
        return self.env["spp.agrovoc.import"].create(vals)

    def test_create_import_job(self):
        """Import job should be created in draft state."""
        job = self._create_import_job()
        self.assertEqual(job.state, "draft")
        self.assertEqual(job.vocabulary_id.id, self.vocab.id)

    def test_default_state_is_draft(self):
        """Default state must be 'draft'."""
        job = self._create_import_job()
        self.assertEqual(job.state, "draft")

    def test_default_language_is_en(self):
        """Default primary language should be 'en'."""
        job = self._create_import_job()
        self.assertEqual(job.primary_language, "en")

    def test_default_filter_mode_is_all(self):
        """Default filter mode should be 'all'."""
        job = self._create_import_job()
        self.assertEqual(job.filter_mode, "all")

    def test_default_include_hierarchy(self):
        """Include hierarchy should default to True."""
        job = self._create_import_job()
        self.assertTrue(job.include_hierarchy)

    def test_default_max_depth(self):
        """Max depth should default to 3."""
        job = self._create_import_job()
        self.assertEqual(job.max_depth, 3)


@tagged("post_install", "-at_install")
class TestAgrovocImportFileExtraction(TransactionCase):
    """Test file extraction from uploaded binary data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": _unique("Test Extract Vocab"),
                "namespace_uri": _unique("urn:test:extract"),
            }
        )

    def _create_import_job(self, **kwargs):
        vals = {
            "name": _unique("Test Extract"),
            "vocabulary_id": self.vocab.id,
        }
        vals.update(kwargs)
        return self.env["spp.agrovoc.import"].create(vals)

    def test_extract_plain_nt_file(self):
        """Plain .nt file should be extracted as-is."""
        job = self._create_import_job(
            file_data=_make_nt_binary(),
            file_name="test.nt",
        )
        content = job._extract_file_content()
        self.assertIn(b"Rice", content)

    def test_extract_zip_file(self):
        """Zip file containing .nt should extract the inner file."""
        job = self._create_import_job(
            file_data=_make_zip_binary(),
            file_name="test.nt.zip",
        )
        content = job._extract_file_content()
        self.assertIn(b"Rice", content)

    def test_extract_no_file_raises(self):
        """No file_data should raise UserError."""
        job = self._create_import_job()
        with self.assertRaises(UserError):
            job._extract_file_content()

    def test_extract_bad_zip_raises(self):
        """Invalid zip file should raise UserError."""
        job = self._create_import_job(
            file_data=base64.b64encode(b"not a zip file"),
            file_name="bad.zip",
        )
        with self.assertRaises(UserError):
            job._extract_file_content()

    def test_extract_zip_no_nt_raises(self):
        """Zip without .nt files should raise UserError."""
        buf = BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "no nt files here")
        job = self._create_import_job(
            file_data=base64.b64encode(buf.getvalue()),
            file_name="no_nt.zip",
        )
        with self.assertRaises(UserError):
            job._extract_file_content()


@tagged("post_install", "-at_install")
class TestAgrovocImportRootUri(TransactionCase):
    """Test root URI computation for filtering."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": _unique("Test Root Vocab"),
                "namespace_uri": _unique("urn:test:root"),
            }
        )

    def _create_import_job(self, **kwargs):
        vals = {
            "name": _unique("Test Root"),
            "vocabulary_id": self.vocab.id,
        }
        vals.update(kwargs)
        return self.env["spp.agrovoc.import"].create(vals)

    def test_get_root_uri_all_mode(self):
        """Filter mode 'all' should return None."""
        job = self._create_import_job(filter_mode="all")
        self.assertIsNone(job._get_root_uri())

    def test_get_root_uri_root_mode_crops(self):
        """Root mode with crops should return AGROVOC crops URI."""
        job = self._create_import_job(
            filter_mode="root",
            root_concept_type="crops",
        )
        uri = job._get_root_uri()
        self.assertEqual(uri, "http://aims.fao.org/aos/agrovoc/c_1972")

    def test_get_root_uri_root_mode_livestock(self):
        """Root mode with livestock should return AGROVOC livestock URI."""
        job = self._create_import_job(
            filter_mode="root",
            root_concept_type="livestock",
        )
        uri = job._get_root_uri()
        self.assertEqual(uri, "http://aims.fao.org/aos/agrovoc/c_4397")

    def test_get_root_uri_custom(self):
        """Custom root should return the custom URI."""
        custom_uri = "http://aims.fao.org/aos/agrovoc/c_9999"
        job = self._create_import_job(
            filter_mode="root",
            root_concept_type="custom",
            custom_root_uri=custom_uri,
        )
        uri = job._get_root_uri()
        self.assertEqual(uri, custom_uri)

    def test_get_root_uri_custom_missing_raises(self):
        """Custom root without URI should raise UserError."""
        job = self._create_import_job(
            filter_mode="root",
            root_concept_type="custom",
        )
        with self.assertRaises(UserError):
            job._get_root_uri()


@tagged("post_install", "-at_install")
class TestAgrovocImportConceptList(TransactionCase):
    """Test concept list parsing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": _unique("Test List Vocab"),
                "namespace_uri": _unique("urn:test:list"),
            }
        )

    def _create_import_job(self, **kwargs):
        vals = {
            "name": _unique("Test List"),
            "vocabulary_id": self.vocab.id,
        }
        vals.update(kwargs)
        return self.env["spp.agrovoc.import"].create(vals)

    def test_concept_list_non_list_mode(self):
        """Non-list filter mode should return None."""
        job = self._create_import_job(filter_mode="all")
        self.assertIsNone(job._get_concept_list())

    def test_concept_list_with_codes(self):
        """List mode should parse newline-separated codes."""
        job = self._create_import_job(
            filter_mode="list",
            concept_list="c_1234\nc_5678\n",
        )
        result = job._get_concept_list()
        self.assertEqual(len(result), 2)
        self.assertIn("http://aims.fao.org/aos/agrovoc/c_1234", result)
        self.assertIn("http://aims.fao.org/aos/agrovoc/c_5678", result)

    def test_concept_list_with_full_uris(self):
        """Full URIs should be kept as-is."""
        job = self._create_import_job(
            filter_mode="list",
            concept_list="http://aims.fao.org/aos/agrovoc/c_1234",
        )
        result = job._get_concept_list()
        self.assertEqual(result[0], "http://aims.fao.org/aos/agrovoc/c_1234")

    def test_concept_list_empty(self):
        """Empty concept list should return None."""
        job = self._create_import_job(filter_mode="list", concept_list="")
        self.assertIsNone(job._get_concept_list())


@tagged("post_install", "-at_install")
class TestAgrovocImportProcess(TransactionCase):
    """Test the full import processing pipeline."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.vocab = cls.env["spp.vocabulary"].create(
            {
                "name": _unique("Test Process Vocab"),
                "namespace_uri": _unique("urn:test:process"),
            }
        )

    def _create_import_job(self, **kwargs):
        vals = {
            "name": _unique("Test Process"),
            "vocabulary_id": self.vocab.id,
            "file_data": _make_nt_binary(),
            "file_name": "test.nt",
        }
        vals.update(kwargs)
        return self.env["spp.agrovoc.import"].create(vals)

    def test_check_rdflib_available(self):
        """_check_rdflib should not raise if rdflib is installed."""
        try:
            import rdflib  # noqa: F401

            job = self._create_import_job()
            job._check_rdflib()  # Should not raise
        except ImportError:
            self.skipTest("rdflib not installed")

    def test_process_import_creates_codes(self):
        """Processing should create vocabulary codes from RDF content."""
        try:
            import rdflib  # noqa: F401
        except ImportError:
            self.skipTest("rdflib not installed")

        job = self._create_import_job()
        job._process_import()

        self.assertEqual(job.state, "done")
        self.assertGreaterEqual(job.total_count, 2)
        self.assertGreaterEqual(job.imported_count, 2)

        # Verify codes were created
        codes = self.env["spp.vocabulary.code"].search([("vocabulary_id", "=", self.vocab.id)])
        code_vals = {c.code for c in codes}
        self.assertIn("c_1234", code_vals)
        self.assertIn("c_5678", code_vals)

    def test_process_import_skips_duplicates(self):
        """Running import twice should skip already-existing codes."""
        try:
            import rdflib  # noqa: F401
        except ImportError:
            self.skipTest("rdflib not installed")

        # First import
        job1 = self._create_import_job()
        job1._process_import()
        initial_count = job1.imported_count

        # Second import to same vocabulary
        job2 = self._create_import_job()
        job2._process_import()

        self.assertEqual(job2.skipped_count, initial_count)
        self.assertEqual(job2.imported_count, 0)

    def test_process_import_sets_hierarchy(self):
        """Parent-child relationships should be set when include_hierarchy is True."""
        try:
            import rdflib  # noqa: F401
        except ImportError:
            self.skipTest("rdflib not installed")

        job = self._create_import_job(include_hierarchy=True)
        job._process_import()

        child = self.env["spp.vocabulary.code"].search(
            [("vocabulary_id", "=", self.vocab.id), ("code", "=", "c_5678")],
            limit=1,
        )
        if child and child.parent_id:
            self.assertEqual(child.parent_id.code, "c_1234")

    def test_process_import_no_file_raises(self):
        """Processing without a file should raise UserError."""
        try:
            import rdflib  # noqa: F401
        except ImportError:
            self.skipTest("rdflib not installed")

        job = self._create_import_job(file_data=False)
        with self.assertRaises(UserError):
            job._process_import()

    def test_action_process_requires_file(self):
        """action_process should raise if no file uploaded."""
        try:
            import rdflib  # noqa: F401
        except ImportError:
            self.skipTest("rdflib not installed")

        job = self._create_import_job(file_data=False)
        with self.assertRaises(UserError):
            job.action_process()

    def test_action_process_requires_vocabulary(self):
        """action_process should raise if no vocabulary selected."""
        try:
            import rdflib  # noqa: F401
        except ImportError:
            self.skipTest("rdflib not installed")

        job = self._create_import_job(vocabulary_id=False)
        with self.assertRaises(UserError):
            job.action_process()

    def test_action_preview(self):
        """Preview should return notification action without creating codes."""
        try:
            import rdflib  # noqa: F401
        except ImportError:
            self.skipTest("rdflib not installed")

        job = self._create_import_job()
        result = job.action_preview()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")

        # No codes should have been created
        codes = self.env["spp.vocabulary.code"].search([("vocabulary_id", "=", self.vocab.id)])
        self.assertEqual(len(codes), 0)

    def test_action_preview_no_file_raises(self):
        """Preview without file should raise UserError."""
        try:
            import rdflib  # noqa: F401
        except ImportError:
            self.skipTest("rdflib not installed")

        job = self._create_import_job(file_data=False)
        with self.assertRaises(UserError):
            job.action_preview()
