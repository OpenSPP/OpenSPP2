# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestBaseWrite(TransactionCase):
    """Test the Base.write() override that removes falsy o2m/m2m fields."""

    def test_write_removes_falsy_one2many(self):
        """Test that write removes falsy one2many values from vals."""
        partner = self.env["res.partner"].create({"name": "WriteTest"})
        # Writing False to a one2many field should not cause errors
        # The override should strip it from vals
        partner.write({"name": "WriteTest Updated", "child_ids": False})
        self.assertEqual(partner.name, "WriteTest Updated")

    def test_write_removes_falsy_many2many(self):
        """Test that write removes falsy many2many values from vals."""
        partner = self.env["res.partner"].create({"name": "WriteTestM2M"})
        # Writing False to category_id (many2many) should be stripped
        partner.write({"name": "WriteTestM2M Updated", "category_id": False})
        self.assertEqual(partner.name, "WriteTestM2M Updated")

    def test_write_keeps_truthy_values(self):
        """Test that write keeps non-falsy field values unchanged."""
        partner = self.env["res.partner"].create({"name": "WriteKeep"})
        partner.write({"name": "WriteKeep Updated", "email": "test@test.com"})
        self.assertEqual(partner.name, "WriteKeep Updated")
        self.assertEqual(partner.email, "test@test.com")

    def test_write_keeps_falsy_non_relational(self):
        """Test that write keeps falsy values for non-relational fields."""
        partner = self.env["res.partner"].create({"name": "WriteFalsyChar", "email": "before@test.com"})
        partner.write({"email": False})
        self.assertFalse(partner.email)
