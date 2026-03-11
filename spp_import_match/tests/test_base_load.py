# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

from ..models.base import _import_match_local


@tagged("post_install", "-at_install")
class TestBaseLoad(TransactionCase):
    """Test the Base.load() override with import matching."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.res_partner_model = cls.env["ir.model"].search([("model", "=", "res.partner")])
        cls.name_field = cls.env["ir.model.fields"].search(
            [("name", "=", "name"), ("model_id", "=", cls.res_partner_model.id)]
        )
        cls.email_field = cls.env["ir.model.fields"].search(
            [("name", "=", "email"), ("model_id", "=", cls.res_partner_model.id)]
        )

    def _create_match_rule(self, field_ids_data, overwrite=True):
        """Helper to create a match rule with fields."""
        match = self.env["spp.import.match"].create(
            {
                "model_id": self.res_partner_model.id,
                "overwrite_match": overwrite,
            }
        )
        for data in field_ids_data:
            data["match_id"] = match.id
            self.env["spp.import.match.fields"].create(data)
        return match

    def test_load_no_usable_rules(self):
        """When no usable rules exist, load() passes through to super()."""
        result = self.env["res.partner"].load(
            ["name", "email"],
            [["NoRuleTest99xyz", "norule@test.com"]],
        )
        self.assertFalse(result["messages"])
        partner = self.env["res.partner"].search([("name", "=", "NoRuleTest99xyz")])
        self.assertEqual(len(partner), 1)

    def test_load_match_overwrite_true(self):
        """Match found + overwrite=True -> record updated."""
        partner = self.env["res.partner"].create({"name": "OverwriteTrue99xyz", "email": "old@test.com"})
        self._create_match_rule([{"field_id": self.name_field.id}], overwrite=True)
        result = self.env["res.partner"].load(
            ["name", "email"],
            [["OverwriteTrue99xyz", "new@test.com"]],
        )
        self.assertFalse(result["messages"])
        partner.invalidate_recordset()
        self.assertEqual(partner.email, "new@test.com")

    def test_load_match_overwrite_false(self):
        """Match found + overwrite=False -> record skipped."""
        partner = self.env["res.partner"].create({"name": "OverwriteFalse99xyz", "email": "original@test.com"})
        self._create_match_rule([{"field_id": self.name_field.id}], overwrite=False)
        self.env["res.partner"].load(
            ["name", "email"],
            [["OverwriteFalse99xyz", "changed@test.com"]],
        )
        partner.invalidate_recordset()
        self.assertEqual(partner.email, "original@test.com")

    def test_load_no_match_creates_record(self):
        """No match found -> new record created."""
        self._create_match_rule([{"field_id": self.name_field.id}])
        result = self.env["res.partner"].load(
            ["name", "email"],
            [["BrandNewPartner99xyz", "brandnew@test.com"]],
        )
        self.assertFalse(result["messages"])
        partner = self.env["res.partner"].search([("name", "=", "BrandNewPartner99xyz")])
        self.assertEqual(len(partner), 1)
        self.assertEqual(partner.email, "brandnew@test.com")

    def test_load_multiple_records_mixed(self):
        """Mix of matched and new records in one import."""
        self.env["res.partner"].create({"name": "ExistingMixed99xyz", "email": "existing@test.com"})
        self._create_match_rule([{"field_id": self.name_field.id}], overwrite=True)
        result = self.env["res.partner"].load(
            ["name", "email"],
            [
                ["ExistingMixed99xyz", "updated@test.com"],
                ["NewMixed99xyz", "newmixed@test.com"],
            ],
        )
        self.assertFalse(result["messages"])
        existing = self.env["res.partner"].search([("name", "=", "ExistingMixed99xyz")])
        self.assertEqual(len(existing), 1)
        existing.invalidate_recordset()
        self.assertEqual(existing.email, "updated@test.com")
        new_partner = self.env["res.partner"].search([("name", "=", "NewMixed99xyz")])
        self.assertEqual(len(new_partner), 1)

    def test_load_with_import_match_ids_context(self):
        """Context import_match_ids filters to specific rules."""
        self._create_match_rule([{"field_id": self.name_field.id}])
        match2 = self._create_match_rule([{"field_id": self.email_field.id}])
        partner = self.env["res.partner"].create({"name": "CtxFilter99xyz", "email": "ctxfilter@test.com"})
        # Only use match2 (email rule); import with matching email but different name
        result = (
            self.env["res.partner"]
            .with_context(import_match_ids=[match2.id])
            .load(
                ["name", "email"],
                [["CtxFilterRenamed99", "ctxfilter@test.com"]],
            )
        )
        self.assertFalse(result["messages"])
        partner.invalidate_recordset()
        self.assertEqual(partner.name, "CtxFilterRenamed99")

    def test_load_appends_id_field(self):
        """Auto-appends 'id' when not in fields list."""
        self._create_match_rule([{"field_id": self.name_field.id}])
        fields = ["name", "email"]
        self.env["res.partner"].load(
            fields,
            [["AppendIdTest99xyz", "appendid@test.com"]],
        )
        self.assertIn("id", fields)

    def test_load_match_counts_tracking(self):
        """_import_match_local.counts populated when import_match_ids in context."""
        self.env["res.partner"].create({"name": "CountsExisting99xyz", "email": "counts@test.com"})
        match = self._create_match_rule([{"field_id": self.name_field.id}], overwrite=True)
        _import_match_local.counts = None
        self.env["res.partner"].with_context(import_match_ids=[match.id]).load(
            ["name", "email"],
            [
                ["CountsExisting99xyz", "updated@test.com"],
                ["CountsNew99xyz", "new@test.com"],
            ],
        )
        counts = _import_match_local.counts
        self.assertIsNotNone(counts)
        self.assertEqual(counts["overwritten"], 1)
        self.assertEqual(counts["created"], 1)
        self.assertEqual(counts["skipped"], 0)
