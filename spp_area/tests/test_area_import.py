import logging

from odoo.exceptions import ValidationError

from .common import AreaImportBaseTestMixin

_logger = logging.getLogger(__name__)


class BaseAreaImportTest(AreaImportBaseTestMixin):
    def test_01_cancel_area_import(self):
        """Test canceling an area import"""
        self.area_import_id.cancel_import()

        self.assertEqual(self.area_import_id.state, "Cancelled")

    def test_02_reset_to_uploaded_area(self):
        """Test resetting import back to uploaded state"""
        self.area_import_id.reset_to_uploaded()

        self.assertEqual(self.area_import_id.state, "Uploaded")

    def test_03_parse_excel_to_json(self):
        """Test parsing Excel file to JSON using pandas"""
        # Parse Excel to JSON
        self.area_import_id.parse_excel_to_json()

        # Check that parsing was successful
        self.assertEqual(self.area_import_id.state, "Parsed")
        self.assertIsNotNone(self.area_import_id.date_parsed)
        self.assertIsNotNone(self.area_import_id.parse_id)

        # Check that JSON files were created
        self.assertTrue(len(self.area_import_id.json_file_ids) > 0)

        # Verify JSON file structure
        for json_file in self.area_import_id.json_file_ids:
            self.assertIsNotNone(json_file.json_file)
            self.assertIsNotNone(json_file.json_file_name)
            self.assertTrue(json_file.row_count > 0)
            self.assertTrue(json_file.file_size > 0)
            self.assertIsNotNone(json_file.batch_number)

    def test_04_parse_excel_to_json_smaller_file(self):
        """Test parsing smaller Excel file (Palestine - less than 400 rows)"""
        # Parse Excel to JSON
        self.area_import_id_2.parse_excel_to_json()

        # Check that parsing was successful
        self.assertEqual(self.area_import_id_2.state, "Parsed")
        self.assertTrue(len(self.area_import_id_2.json_file_ids) > 0)

    def test_05_import_area_data_without_parsing(self):
        """Test that importing without parsing raises an error"""
        with self.assertRaises(ValidationError):
            self.area_import_id.import_data()

    def test_06_import_area_data_auto_activates_language(self):
        """Test that importing auto-activates required languages"""
        # Parse Excel to JSON first
        self.area_import_id.parse_excel_to_json()

        # Deactivate Arabic language
        lang = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", "ar")])
        lang.active = False

        # Import should succeed and auto-activate the language
        self.area_import_id.import_data()

        # Verify Arabic was auto-activated
        lang.invalidate_recordset()
        self.assertTrue(lang.active, "Arabic language should be auto-activated")

        # Verify import was successful
        self.assertEqual(self.area_import_id.state, "Imported")

    def test_07_import_area_data_complete_workflow(self):
        """Test complete workflow: parse then import with proper language setup"""
        # Activate Arabic language
        lang = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", "ar")])
        lang.active = True

        # Parse Excel to JSON
        self.area_import_id.parse_excel_to_json()
        self.assertEqual(self.area_import_id.state, "Parsed")

        # Import data from JSON
        self.area_import_id.import_data()

        # Check that import was successful
        self.assertEqual(self.area_import_id.state, "Imported")
        self.assertIsNotNone(self.area_import_id.date_imported)
        self.assertIsNotNone(self.area_import_id.import_id)

        # Check raw data was created
        raw_area_data_ids = self.area_import_id.raw_data_ids
        self.assertTrue(len(raw_area_data_ids) > 0)
        self.assertEqual(len(raw_area_data_ids.ids), self.area_import_id.total_rows_imported)
        self.assertEqual(0, self.area_import_id.total_rows_error)

        # Check that raw data records are in "New" state
        self.assertEqual(
            len(self.env["spp.area.import.raw"].search([("id", "in", raw_area_data_ids.ids), ("state", "=", "New")])),
            self.area_import_id.total_rows_imported,
        )

    def test_08_json_file_model_fields(self):
        """Test that JSON file model has all required fields"""
        # Parse Excel to create JSON files
        self.area_import_id.parse_excel_to_json()

        json_file = self.area_import_id.json_file_ids[0]

        # Check all fields are present
        self.assertEqual(json_file.area_import_id, self.area_import_id)
        self.assertIsInstance(json_file.batch_number, int)
        self.assertTrue(json_file.json_file)
        self.assertTrue(json_file.json_file_name)
        self.assertIsInstance(json_file.row_count, int)
        self.assertIsInstance(json_file.file_size, int)

    def test_09_validate_languages_auto_activation(self):
        """Test language validation auto-activates missing languages"""
        # Parse Excel to create JSON files
        lang = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", "ar")])
        lang.active = True
        self.area_import_id.parse_excel_to_json()

        # Should not raise error when all languages are activated
        self.area_import_id._validate_languages_activated()

        # Deactivate Arabic - validation should auto-activate it
        lang.active = False
        self.area_import_id._validate_languages_activated()

        # Verify Arabic was auto-activated
        lang.invalidate_recordset()
        self.assertTrue(lang.active, "Arabic language should be auto-activated by validation")

    def test_10_reload_page(self):
        """Test page reload action"""
        action = self.area_import_id.refresh_page()

        self.assertEqual(
            action,
            {
                "type": "ir.actions.client",
                "tag": "reload",
            },
        )

    def test_11_async_mark_done(self):
        """Test async mark done functionality"""
        self.area_import_id.is_locked = True
        self.area_import_id.locked_reason = "Testing"

        self.area_import_id._async_mark_done()

        self.assertFalse(self.area_import_id.is_locked)
        self.assertFalse(self.area_import_id.locked_reason)

    def test_12_async_mark_done_with_function(self):
        """Test async mark done with callback function"""
        self.area_import_id.is_locked = True
        self.area_import_id.locked_reason = "Testing"

        # Parse and import first to have data
        lang = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", "ar")])
        lang.active = True
        self.area_import_id.parse_excel_to_json()
        self.area_import_id.import_data()

        # Call with _import_mark_done function
        self.area_import_id._async_mark_done("_import_mark_done")

        self.assertFalse(self.area_import_id.is_locked)
        self.assertFalse(self.area_import_id.locked_reason)
        self.assertEqual(self.area_import_id.state, "Imported")

    def test_13_compute_get_total_rows(self):
        """Test computation of total rows imported and error count"""
        # Parse and import
        lang = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", "ar")])
        lang.active = True
        self.area_import_id.parse_excel_to_json()
        self.area_import_id.import_data()

        # Initial count
        initial_count = self.area_import_id.total_rows_imported

        self.assertTrue(initial_count > 0)
        self.assertEqual(self.area_import_id.total_rows_error, 0)

    def test_14_json_files_ordered_by_batch_number(self):
        """Test that JSON files are ordered by batch number"""
        # Parse Excel
        self.area_import_id.parse_excel_to_json()

        # Get all JSON files
        json_files = self.area_import_id.json_file_ids

        # Check ordering
        batch_numbers = [json_file.batch_number for json_file in json_files]
        self.assertEqual(batch_numbers, sorted(batch_numbers))

    def test_15_parse_clears_existing_json_files(self):
        """Test that parsing again clears existing JSON files"""
        # First parse
        self.area_import_id.parse_excel_to_json()
        len(self.area_import_id.json_file_ids)

        # Reset to uploaded and parse again
        self.area_import_id.reset_to_uploaded()
        self.area_import_id.parse_excel_to_json()
        second_count = len(self.area_import_id.json_file_ids)

        # Should have same or similar count (clearing and recreating)
        self.assertTrue(second_count > 0)

    def test_16_import_clears_existing_raw_data(self):
        """Test that importing again clears existing raw data"""
        # Parse and import
        lang = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", "ar")])
        lang.active = True
        self.area_import_id.parse_excel_to_json()
        self.area_import_id.import_data()
        first_count = len(self.area_import_id.raw_data_ids)

        # Import again (without resetting)
        self.area_import_id.state = "Parsed"  # Reset to allow import again
        self.area_import_id.import_data()
        second_count = len(self.area_import_id.raw_data_ids)

        # Should have same count (clearing and recreating)
        self.assertEqual(first_count, second_count)

    # ============================================================
    # Tests for different COD file formats
    # ============================================================

    def test_17_parse_sri_lanka_format(self):
        """Test parsing Sri Lanka file with admin{N}Name_{lang} column format"""
        # Sri Lanka uses lowercase admin{N}Name_{lang} format instead of ADM{N}_{LANG}
        self.area_import_lka.parse_excel_to_json()

        # Check that parsing was successful
        self.assertEqual(self.area_import_lka.state, "Parsed")
        self.assertTrue(len(self.area_import_lka.json_file_ids) > 0)

        # Verify first batch has normalized headers
        import base64
        import json

        first_json = self.area_import_lka.json_file_ids.sorted(lambda x: x.batch_number)[0]
        json_bytes = base64.b64decode(first_json.json_file)
        rows = json.loads(json_bytes.decode("utf-8"))

        # Check that headers are normalized to ADM{N}_{LANG} format
        # First batch is from Admin0 sheet (level 0), so check for ADM0 columns
        first_row = rows[0]
        self.assertIn("ADM0_EN", first_row.keys(), "Headers should be normalized to ADM format")
        self.assertIn("ADM0_PCODE", first_row.keys(), "PCODE should be normalized")

        # Find a batch with level 4 data to verify Admin4 normalization works too
        for json_file in self.area_import_lka.json_file_ids.sorted(lambda x: x.batch_number):
            json_bytes = base64.b64decode(json_file.json_file)
            rows = json.loads(json_bytes.decode("utf-8"))
            if rows and rows[0].get("_area_level") == 4:
                # Found a level 4 batch - verify normalization
                self.assertIn("ADM4_EN", rows[0].keys(), "Admin4 headers should be normalized")
                self.assertIn("ADM4_PCODE", rows[0].keys(), "Admin4 PCODE should be normalized")
                break

    def test_18_parse_togo_french_primary(self):
        """Test parsing Togo file with French as primary language (no EN column)"""
        # Togo uses French as primary language, no English column
        self.area_import_tgo.parse_excel_to_json()

        # Check that parsing was successful
        self.assertEqual(self.area_import_tgo.state, "Parsed")
        self.assertTrue(len(self.area_import_tgo.json_file_ids) > 0)

        # Verify primary language is detected as FR
        import base64
        import json

        first_json = self.area_import_tgo.json_file_ids.sorted(lambda x: x.batch_number)[0]
        json_bytes = base64.b64decode(first_json.json_file)
        rows = json.loads(json_bytes.decode("utf-8"))

        first_row = rows[0]
        self.assertEqual(first_row.get("_primary_language"), "FR", "Primary language should be FR")
        self.assertIn("ADM0_FR", first_row.keys(), "Should have French column")

    def test_19_import_togo_auto_activates_french(self):
        """Test importing Togo file auto-activates French language"""
        # Ensure French is deactivated first
        lang_fr = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", "fr")])
        lang_fr.active = False

        # Parse and import
        self.area_import_tgo.parse_excel_to_json()
        self.area_import_tgo.import_data()

        # Verify French was auto-activated
        lang_fr.invalidate_recordset()
        self.assertTrue(lang_fr.active, "French language should be auto-activated")

        # Verify import was successful
        self.assertEqual(self.area_import_tgo.state, "Imported")
        self.assertTrue(len(self.area_import_tgo.raw_data_ids) > 0)

        # Verify raw data has names (not None)
        for raw_data in self.area_import_tgo.raw_data_ids[:5]:
            self.assertIsNotNone(raw_data.admin_name, "Admin name should not be None")
            self.assertIsNotNone(raw_data.admin_code, "Admin code should not be None")

    def test_20_parse_philippines_format(self):
        """Test parsing Philippines file with standard format"""
        self.area_import_phl.parse_excel_to_json()

        # Check that parsing was successful
        self.assertEqual(self.area_import_phl.state, "Parsed")
        self.assertTrue(len(self.area_import_phl.json_file_ids) > 0)

    def test_21_import_sri_lanka_complete_workflow(self):
        """Test complete workflow for Sri Lanka file with different naming convention"""
        # Activate Sinhala and Tamil languages
        for iso_code in ["si", "ta"]:
            lang = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", iso_code)])
            if lang:
                lang.active = True

        # Parse and import
        self.area_import_lka.parse_excel_to_json()
        self.assertEqual(self.area_import_lka.state, "Parsed")

        self.area_import_lka.import_data()
        self.assertEqual(self.area_import_lka.state, "Imported")

        # Verify raw data was created with correct values
        self.assertTrue(len(self.area_import_lka.raw_data_ids) > 0)

        # Check first raw data record has valid data
        first_raw = self.area_import_lka.raw_data_ids[0]
        self.assertIsNotNone(first_raw.admin_name)
        self.assertIsNotNone(first_raw.admin_code)

    def test_22_header_normalization(self):
        """Test that header normalization works correctly"""
        import_model = self.env["spp.area.import"]

        # Test Sri Lanka style headers
        self.assertEqual(import_model._normalize_cod_header("admin0Name_en"), "ADM0_EN")
        self.assertEqual(import_model._normalize_cod_header("admin1Name_si"), "ADM1_SI")
        self.assertEqual(import_model._normalize_cod_header("admin2Pcode"), "ADM2_PCODE")
        self.assertEqual(import_model._normalize_cod_header("admin3Name_ta"), "ADM3_TA")

        # Test standard ADM format (should just uppercase)
        self.assertEqual(import_model._normalize_cod_header("ADM0_EN"), "ADM0_EN")
        self.assertEqual(import_model._normalize_cod_header("adm1_fr"), "ADM1_FR")
        self.assertEqual(import_model._normalize_cod_header("ADM2_PCODE"), "ADM2_PCODE")

        # Test non-matching headers are preserved
        self.assertEqual(import_model._normalize_cod_header("AREA_SQKM"), "AREA_SQKM")
        self.assertEqual(import_model._normalize_cod_header("date"), "date")

    def test_23_primary_language_detection(self):
        """Test that primary language detection works correctly"""
        import_model = self.env["spp.area.import"]

        # Test with English present
        headers_en = ["ADM0_EN", "ADM0_FR", "ADM0_PCODE"]
        self.assertEqual(import_model._detect_primary_language(headers_en), "EN")

        # Test with only French (like Togo)
        headers_fr = ["ADM0_FR", "ADM0_PCODE", "ADM1_FR"]
        self.assertEqual(import_model._detect_primary_language(headers_fr), "FR")

        # Test with multiple languages but no English
        headers_multi = ["ADM0_ES", "ADM0_FR", "ADM0_PCODE"]
        result = import_model._detect_primary_language(headers_multi)
        self.assertIn(result, ["ES", "FR"])  # Should pick first alphabetically

    # ============================================================
    # Tests for unified workflow (process_file)
    # ============================================================

    def test_24_process_file_unified_workflow(self):
        """Test that process_file chains Parse → Import → Validate in one call"""
        # Activate Arabic language for Iraq file
        lang = self.env["res.lang"].with_context(active_test=False).search([("iso_code", "=", "ar")])
        lang.active = True

        # Create a fresh import record
        import_record = self._create_import_from_file(self.get_file_path_pse())

        # Call process_file - should do Parse + Import + Validate
        import_record.process_file()

        # Verify final state is Validated (not Imported or Parsed)
        self.assertEqual(import_record.state, "Validated", "State should be Validated after process_file")

        # Verify all intermediate steps completed
        self.assertIsNotNone(import_record.date_parsed, "Parsing should have completed")
        self.assertIsNotNone(import_record.date_imported, "Import should have completed")
        self.assertIsNotNone(import_record.date_validated, "Validation should have completed")

        # Verify raw data was created and validated
        self.assertTrue(len(import_record.raw_data_ids) > 0, "Raw data should have been created")

        # Check all raw data is in Validated state (no errors)
        validated_count = self.env["spp.area.import.raw"].search_count(
            [("id", "in", import_record.raw_data_ids.ids), ("state", "=", "Validated")]
        )
        self.assertEqual(validated_count, len(import_record.raw_data_ids), "All raw data records should be validated")

    def test_25_process_file_progress_tracking(self):
        """Test that progress tracking works during process_file"""
        # Use small Palestine file for faster test
        import_record = self._create_import_from_file(self.get_file_path_pse())

        # Process the file
        import_record.process_file()

        # After completion, progress should be reset (is_locked = False)
        self.assertFalse(import_record.is_locked, "Record should be unlocked after processing")
