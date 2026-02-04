from odoo.tests import TransactionCase


class TestDMSDirectoryCreation(TransactionCase):
    """Tests for automatic DMS directory creation for change requests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr_model = cls.env["spp.change.request"]
        cls.directory_model = cls.env["spp.dms.directory"]
        cls.partner_model = cls.env["res.partner"]

        # Create test registrant
        cls.registrant = cls.partner_model.create(
            {
                "name": "Test Registrant",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Get CR type by code (may be in different module)
        cls.cr_type = cls.env["spp.change.request.type"].search([("code", "=", "edit_individual")], limit=1)
        if not cls.cr_type:
            # Create a minimal test type if not installed
            cls.cr_type = cls.env["spp.change.request.type"].create(
                {
                    "name": "Test Edit Individual",
                    "code": "test_edit_individual",
                    "target_type": "individual",
                    "detail_model": "spp.cr.detail.edit_individual",
                    "apply_strategy": "field_mapping",
                }
            )

    def test_01_parent_directory_exists_from_data(self):
        """Test that parent 'Change Request' directory exists from XML data."""
        # Verify parent directory exists
        parent = self.env.ref(
            "spp_change_request_v2.dms_directory_change_request_root",
            raise_if_not_found=False,
        )
        self.assertTrue(parent, "Parent 'Change Request' directory should exist from data")
        self.assertEqual(
            parent.name,
            "Change Request",
            "Parent directory should be named 'Change Request'",
        )
        self.assertTrue(parent.is_root_directory, "Parent should be a root directory")

        # Create a change request
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Verify CR has a directory
        self.assertTrue(cr.dms_directory_id, "Change request should have a DMS directory")

    def test_02_subdirectory_created_for_cr(self):
        """Test that subdirectory is created for each change request."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Verify directory was created
        self.assertTrue(cr.dms_directory_id, "CR should have a DMS directory")

        # Verify directory name matches CR reference
        self.assertEqual(
            cr.dms_directory_id.name,
            cr.name,
            "Directory name should match CR reference",
        )

        # Verify directory has correct parent
        self.assertTrue(cr.dms_directory_id.parent_id, "Directory should have a parent")
        self.assertEqual(
            cr.dms_directory_id.parent_id.name,
            "Change Request",
            "Parent directory should be 'Change Request'",
        )

        # Verify directory is not a root directory
        self.assertFalse(
            cr.dms_directory_id.is_root_directory,
            "CR directory should not be a root directory",
        )

        # Verify back-reference
        self.assertEqual(
            cr.dms_directory_id.change_request_id,
            cr,
            "Directory should reference the change request",
        )

    def test_03_parent_directory_shared(self):
        """Test that parent directory is shared by multiple CRs."""
        parent_ref = self.env.ref("spp_change_request_v2.dms_directory_change_request_root")

        # Create first CR
        cr1 = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )
        parent1 = cr1.dms_directory_id.parent_id

        # Create second CR
        cr2 = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )
        parent2 = cr2.dms_directory_id.parent_id

        # Verify same parent is used
        self.assertEqual(
            parent1,
            parent2,
            "Both CRs should use the same parent directory",
        )

        # Verify it's the XML data parent
        self.assertEqual(
            parent1,
            parent_ref,
            "Parent should be the one defined in XML data",
        )

    def test_04_directory_archived_with_cr(self):
        """Test that directory is archived when CR is deleted."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )
        directory_id = cr.dms_directory_id.id

        # Delete the CR
        cr.unlink()

        # Verify directory was archived (not deleted, to preserve files)
        directory = self.directory_model.with_context(active_test=False).browse(directory_id)
        self.assertTrue(directory.exists(), "Directory should still exist after CR deletion")
        self.assertFalse(
            directory.active,
            "Directory should be archived (active=False) when CR is deleted",
        )

    def test_05_complete_name_computed(self):
        """Test that complete directory name includes parent path."""
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        expected_name = f"Change Request / {cr.name}"
        self.assertEqual(
            cr.dms_directory_id.complete_name,
            expected_name,
            "Complete directory name should include parent path",
        )

    def test_06_multiple_crs_have_unique_directories(self):
        """Test that each CR gets its own unique directory."""
        cr1 = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )
        cr2 = self.cr_model.create(
            {
                "request_type_id": self.cr_type.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Verify different directories
        self.assertNotEqual(
            cr1.dms_directory_id,
            cr2.dms_directory_id,
            "Each CR should have its own directory",
        )

        # Verify different names
        self.assertNotEqual(
            cr1.dms_directory_id.name,
            cr2.dms_directory_id.name,
            "Each CR directory should have a unique name",
        )
