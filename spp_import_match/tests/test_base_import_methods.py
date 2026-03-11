# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.queue_job.exception import FailedJobError

from ..models.base_import import ImportValidationError

OPTIONS = {
    "import_skip_records": [],
    "import_set_empty_fields": [],
    "fallback_values": {},
    "name_create_enabled_fields": {},
    "encoding": "utf-8",
    "separator": ",",
    "quoting": '"',
    "date_format": "",
    "datetime_format": "",
    "float_thousand_separator": ",",
    "float_decimal_separator": ".",
    "advanced": True,
    "has_headers": True,
    "keep_matches": False,
    "limit": 2000,
    "sheets": [],
    "sheet": "",
    "skip": 0,
    "tracking_disable": True,
}


@tagged("post_install", "-at_install")
class TestBaseImportMethods(TransactionCase):
    """Test SPPBaseImport helper methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.csv_options = {
            "separator": ",",
            "quoting": '"',
            "encoding": "utf-8",
        }
        cls.import_record = cls.env["base_import.import"].create(
            {
                "res_model": "res.partner",
                "file_name": "test.csv",
            }
        )

    def test_csv_attachment_roundtrip(self):
        """_create_csv_attachment + _read_csv_attachment round-trip."""
        fields_in = ["name", "email"]
        data_in = [["Alice", "alice@test.com"], ["Bob", "bob@test.com"]]
        attachment = self.import_record._create_csv_attachment(fields_in, data_in, self.csv_options, "roundtrip.csv")
        self.assertTrue(attachment.id)
        self.assertEqual(attachment.name, "roundtrip.csv")
        fields_out, data_out = self.import_record._read_csv_attachment(attachment, self.csv_options)
        self.assertEqual(fields_out, fields_in)
        self.assertEqual(len(data_out), 2)
        self.assertEqual(data_out[0], ["Alice", "alice@test.com"])
        self.assertEqual(data_out[1], ["Bob", "bob@test.com"])

    def test_csv_attachment_custom_options(self):
        """_create/_read_csv_attachment with custom separator/quoting/encoding."""
        custom_options = {
            "separator": ";",
            "quoting": "'",
            "encoding": "latin-1",
        }
        fields_in = ["name", "email"]
        data_in = [["TestAccent", "accent@test.com"]]
        attachment = self.import_record._create_csv_attachment(fields_in, data_in, custom_options, "custom.csv")
        fields_out, data_out = self.import_record._read_csv_attachment(attachment, custom_options)
        self.assertEqual(fields_out, fields_in)
        self.assertEqual(data_out[0][0], "TestAccent")

    def test_extract_chunks_basic(self):
        """_extract_chunks splits data into chunks >= chunk_size."""
        model_obj = self.env["res.partner"]
        fields = ["name", "email"]
        data = [[f"P{i}", f"p{i}@test.com"] for i in range(7)]
        chunks = list(self.env["base_import.import"]._extract_chunks(model_obj, fields, data, 3))
        self.assertTrue(len(chunks) > 1)
        # All rows should be covered
        all_rows = set()
        for start, end in chunks:
            for r in range(start, end + 1):
                all_rows.add(r)
        self.assertEqual(all_rows, set(range(7)))

    def test_extract_chunks_small_data(self):
        """_extract_chunks with data smaller than chunk_size yields one chunk."""
        model_obj = self.env["res.partner"]
        fields = ["name", "email"]
        data = [["A", "a@test.com"], ["B", "b@test.com"]]
        chunks = list(self.env["base_import.import"]._extract_chunks(model_obj, fields, data, 100))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], (0, 1))

    def test_import_one_chunk_success(self):
        """_import_one_chunk loads data successfully."""
        attachment = self.import_record._create_csv_attachment(
            ["name"], [["ChunkSuccess99xyz"]], self.csv_options, "chunk.csv"
        )
        result = self.import_record._import_one_chunk("res.partner", attachment, self.csv_options, {})
        errors = [m for m in result["messages"] if m.get("type") == "error"]
        self.assertFalse(errors)
        partner = self.env["res.partner"].search([("name", "=", "ChunkSuccess99xyz")])
        self.assertEqual(len(partner), 1)

    def test_import_one_chunk_error(self):
        """_import_one_chunk raises FailedJobError on load errors."""
        attachment = self.import_record._create_csv_attachment(["name"], [["ErrTest"]], self.csv_options, "err.csv")
        error_result = {
            "messages": [{"type": "error", "message": "Test error"}],
            "ids": [],
        }
        with patch.object(type(self.env["res.partner"]), "load", return_value=error_result):
            with self.assertRaises(FailedJobError):
                self.import_record._import_one_chunk("res.partner", attachment, self.csv_options, {})

    def test_import_validation_error_attributes(self):
        """ImportValidationError stores field, type, and message attrs."""
        err = ImportValidationError("Bad value", field="name", error_type="warning", field_type="char")
        self.assertEqual(str(err), "Bad value")
        self.assertEqual(err.message, "Bad value")
        self.assertEqual(err.type, "warning")
        self.assertEqual(err.field_path, ["name"])
        self.assertEqual(err.field_type, "char")
        self.assertFalse(err.record)
        self.assertTrue(err.not_matching_error)
        # Test defaults
        err2 = ImportValidationError("Default error")
        self.assertEqual(err2.type, "error")
        self.assertFalse(err2.field_path)
        self.assertIsNone(err2.field_type)

    def test_execute_import_with_match_ids_passes_context(self):
        """execute_import passes import_match_ids and overwrite_match to context."""
        res_partner_model = self.env["ir.model"].search([("model", "=", "res.partner")])
        name_field = self.env["ir.model.fields"].search(
            [("name", "=", "name"), ("model_id", "=", res_partner_model.id)]
        )
        self.env["res.partner"].create({"name": "ExecMatchTest99xyz", "email": "exec@test.com"})
        match = self.env["spp.import.match"].create({"model_id": res_partner_model.id, "overwrite_match": True})
        self.env["spp.import.match.fields"].create({"field_id": name_field.id, "match_id": match.id})
        import_rec = self.env["base_import.import"].create(
            {
                "res_model": "res.partner",
                "file": b"name,email\nExecMatchTest99xyz,updated@test.com",
                "file_name": "test_exec.csv",
                "file_type": "csv",
            }
        )
        options = dict(OPTIONS)
        options["import_match_ids"] = [match.id]
        options["overwrite_match"] = True
        result = import_rec.execute_import(["name", "email"], [], options, dryrun=True)
        self.assertIn("import_match_counts", result)
        self.assertEqual(result["import_match_counts"]["overwritten"], 1)
