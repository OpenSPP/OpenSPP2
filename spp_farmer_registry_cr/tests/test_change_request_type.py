# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for change_request_type.py — activity operation toggles on CR type."""

from odoo.tests import TransactionCase, tagged

from .common import FarmerCRTestMixin


@tagged("post_install", "-at_install")
class TestChangeRequestType(TransactionCase, FarmerCRTestMixin):
    """Tests for spp.change.request.type activity operation fields."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.CRType = cls.env["spp.change.request.type"]

    def test_default_allow_activity_add(self):
        """Test that allow_activity_add defaults to True."""
        cr_type = self._create_cr_type(
            name="Test Activity Defaults Add",
            code="test_activity_defaults_add",
        )
        self.assertTrue(cr_type.allow_activity_add)

    def test_default_allow_activity_update(self):
        """Test that allow_activity_update defaults to True."""
        cr_type = self._create_cr_type(
            name="Test Activity Defaults Update",
            code="test_activity_defaults_update",
        )
        self.assertTrue(cr_type.allow_activity_update)

    def test_default_allow_activity_remove(self):
        """Test that allow_activity_remove defaults to True."""
        cr_type = self._create_cr_type(
            name="Test Activity Defaults Remove",
            code="test_activity_defaults_remove",
        )
        self.assertTrue(cr_type.allow_activity_remove)

    def test_write_allow_activity_add_false(self):
        """Test persisting allow_activity_add as False."""
        cr_type = self._create_cr_type(
            name="Test Write Add",
            code="test_write_add",
        )
        cr_type.write({"allow_activity_add": False})
        self.assertFalse(cr_type.allow_activity_add)

    def test_write_allow_activity_update_false(self):
        """Test persisting allow_activity_update as False."""
        cr_type = self._create_cr_type(
            name="Test Write Update",
            code="test_write_update",
        )
        cr_type.write({"allow_activity_update": False})
        self.assertFalse(cr_type.allow_activity_update)

    def test_write_allow_activity_remove_false(self):
        """Test persisting allow_activity_remove as False."""
        cr_type = self._create_cr_type(
            name="Test Write Remove",
            code="test_write_remove",
        )
        cr_type.write({"allow_activity_remove": False})
        self.assertFalse(cr_type.allow_activity_remove)

    def test_create_with_all_disabled(self):
        """Test creating CR type with all activity operations disabled."""
        cr_type = self._create_cr_type(
            name="Test All Disabled",
            code="test_all_disabled",
            allow_activity_add=False,
            allow_activity_update=False,
            allow_activity_remove=False,
        )
        self.assertFalse(cr_type.allow_activity_add)
        self.assertFalse(cr_type.allow_activity_update)
        self.assertFalse(cr_type.allow_activity_remove)

    def test_toggle_operations(self):
        """Test toggling operation flags back and forth."""
        cr_type = self._create_cr_type(
            name="Test Toggle",
            code="test_toggle",
        )
        # Disable all
        cr_type.write(
            {
                "allow_activity_add": False,
                "allow_activity_update": False,
                "allow_activity_remove": False,
            }
        )
        self.assertFalse(cr_type.allow_activity_add)
        self.assertFalse(cr_type.allow_activity_update)
        self.assertFalse(cr_type.allow_activity_remove)

        # Re-enable all
        cr_type.write(
            {
                "allow_activity_add": True,
                "allow_activity_update": True,
                "allow_activity_remove": True,
            }
        )
        self.assertTrue(cr_type.allow_activity_add)
        self.assertTrue(cr_type.allow_activity_update)
        self.assertTrue(cr_type.allow_activity_remove)
