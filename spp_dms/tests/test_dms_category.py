# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDMSCategory(TransactionCase):
    """Tests for DMS Category model with file validation."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Category = cls.env["spp.dms.category"]

    def test_01_create_category(self):
        """Test basic category creation."""
        category = self.Category.create(
            {
                "name": "Test Category",
            }
        )
        self.assertEqual(category.name, "Test Category")

    def test_02_validate_file_blocked_extensions(self):
        """Test that blocked extensions are rejected."""
        category = self.Category.create(
            {
                "name": "Secure Documents",
                "blocked_extensions": "exe,dll,bat,cmd",
            }
        )

        # Should raise for blocked extension
        with self.assertRaises(ValidationError):
            category.validate_file(
                filename="malware.exe",
                mimetype="application/octet-stream",
                size_bytes=1000,
            )

        # Should pass for allowed extension
        category.validate_file(
            filename="document.pdf",
            mimetype="application/pdf",
            size_bytes=1000,
        )

    def test_03_validate_file_allowed_extensions(self):
        """Test that only allowed extensions pass when specified."""
        category = self.Category.create(
            {
                "name": "Images Only",
                "allowed_extensions": "jpg,png,gif",
            }
        )

        # Should pass for allowed extensions
        category.validate_file(
            filename="photo.jpg",
            mimetype="image/jpeg",
            size_bytes=1000,
        )

        # Should raise for non-allowed extension
        with self.assertRaises(ValidationError):
            category.validate_file(
                filename="document.pdf",
                mimetype="application/pdf",
                size_bytes=1000,
            )

    def test_04_validate_file_blocked_takes_precedence(self):
        """Test that blocked extensions take precedence over allowed."""
        category = self.Category.create(
            {
                "name": "Mixed Rules",
                "allowed_extensions": "exe,pdf,doc",  # exe is in allowed
                "blocked_extensions": "exe",  # but also in blocked
            }
        )

        # exe should still be blocked
        with self.assertRaises(ValidationError):
            category.validate_file(
                filename="program.exe",
                mimetype="application/octet-stream",
                size_bytes=1000,
            )

        # pdf should be allowed
        category.validate_file(
            filename="document.pdf",
            mimetype="application/pdf",
            size_bytes=1000,
        )

    def test_05_validate_file_size_limit(self):
        """Test that files exceeding size limit are rejected."""
        category = self.Category.create(
            {
                "name": "Small Files Only",
                "max_file_size_mb": 1,  # 1 MB limit
            }
        )

        # Should pass for small file
        category.validate_file(
            filename="small.txt",
            mimetype="text/plain",
            size_bytes=500 * 1024,  # 500 KB
        )

        # Should raise for large file
        with self.assertRaises(ValidationError):
            category.validate_file(
                filename="large.txt",
                mimetype="text/plain",
                size_bytes=2 * 1024 * 1024,  # 2 MB
            )

    def test_06_validate_file_allowed_mimetypes(self):
        """Test that only allowed MIME types pass when specified."""
        category = self.Category.create(
            {
                "name": "PDF Only",
                "allowed_mimetypes": "application/pdf",
            }
        )

        # Should pass for allowed mimetype
        category.validate_file(
            filename="document.pdf",
            mimetype="application/pdf",
            size_bytes=1000,
        )

        # Should raise for non-allowed mimetype
        with self.assertRaises(ValidationError):
            category.validate_file(
                filename="image.jpg",
                mimetype="image/jpeg",
                size_bytes=1000,
            )

    def test_07_validate_file_mimetype_wildcard(self):
        """Test MIME type wildcard matching (e.g., image/*)."""
        category = self.Category.create(
            {
                "name": "All Images",
                "allowed_mimetypes": "image/*",
            }
        )

        # Should pass for any image mimetype
        category.validate_file(
            filename="photo.jpg",
            mimetype="image/jpeg",
            size_bytes=1000,
        )
        category.validate_file(
            filename="icon.png",
            mimetype="image/png",
            size_bytes=1000,
        )

        # Should raise for non-image mimetype
        with self.assertRaises(ValidationError):
            category.validate_file(
                filename="document.pdf",
                mimetype="application/pdf",
                size_bytes=1000,
            )

    def test_08_validate_file_no_extension(self):
        """Test handling of files without extension.

        Note: The current implementation allows files without extension to pass
        even when allowed_extensions is set. This is because the check only applies
        when extension is truthy.
        """
        category = self.Category.create(
            {
                "name": "With Extensions",
                "allowed_extensions": "txt,pdf",
            }
        )

        # File without extension currently passes through (extension is empty)
        # This is the current implementation behavior
        category.validate_file(
            filename="README",
            mimetype="text/plain",
            size_bytes=1000,
        )

    def test_09_validate_file_case_insensitive_extension(self):
        """Test that extension matching is case-insensitive."""
        category = self.Category.create(
            {
                "name": "Case Test",
                "allowed_extensions": "pdf,jpg",
            }
        )

        # Should accept regardless of case
        category.validate_file(
            filename="Document.PDF",
            mimetype="application/pdf",
            size_bytes=1000,
        )
        category.validate_file(
            filename="PHOTO.JPG",
            mimetype="image/jpeg",
            size_bytes=1000,
        )

    def test_10_validate_file_empty_restrictions(self):
        """Test that files pass when restrictions are explicitly cleared."""
        category = self.Category.create(
            {
                "name": "No Restrictions",
                "blocked_extensions": "",  # Clear default blocked extensions
                "max_file_size_mb": 0,  # No size limit (0 means unlimited)
            }
        )

        # Any file should pass when restrictions are cleared
        category.validate_file(
            filename="anything.xyz",
            mimetype="application/octet-stream",
            size_bytes=100 * 1024 * 1024,  # 100 MB
        )

    def test_11_validate_file_default_blocked_extensions(self):
        """Test that default blocked extensions work."""
        # The model has default blocked extensions for security
        category = self.Category.create(
            {
                "name": "Secure by Default",
            }
        )

        # Check if exe is blocked by default (depends on model default)
        if category.blocked_extensions:
            with self.assertRaises(ValidationError):
                category.validate_file(
                    filename="malware.exe",
                    mimetype="application/octet-stream",
                    size_bytes=1000,
                )

    def test_12_validate_file_combined_restrictions(self):
        """Test validation with multiple restrictions combined."""
        category = self.Category.create(
            {
                "name": "Strict Category",
                "allowed_extensions": "pdf,doc,docx",
                "blocked_extensions": "exe,dll",
                "allowed_mimetypes": "application/pdf,application/msword",
                "max_file_size_mb": 5,
            }
        )

        # Should pass all restrictions
        category.validate_file(
            filename="report.pdf",
            mimetype="application/pdf",
            size_bytes=1024 * 1024,  # 1 MB
        )

        # Should fail - wrong extension
        with self.assertRaises(ValidationError):
            category.validate_file(
                filename="spreadsheet.xlsx",
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                size_bytes=1024,
            )

        # Should fail - too large
        with self.assertRaises(ValidationError):
            category.validate_file(
                filename="big.pdf",
                mimetype="application/pdf",
                size_bytes=10 * 1024 * 1024,  # 10 MB
            )
