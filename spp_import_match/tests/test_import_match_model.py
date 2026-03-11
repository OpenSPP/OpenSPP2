# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestImportMatchModel(TransactionCase):
    """Test spp.import.match and spp.import.match.fields models."""

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

    def _create_match_rule(self, field_ids_data=None):
        """Helper to create a match rule with fields."""
        match = self.env["spp.import.match"].create(
            {
                "model_id": self.res_partner_model.id,
                "overwrite_match": True,
            }
        )
        if field_ids_data:
            for data in field_ids_data:
                data["match_id"] = match.id
                self.env["spp.import.match.fields"].create(data)
        return match

    def test_onchange_model_id_clears_fields(self):
        """Test that changing model_id clears field_ids."""
        match = self._create_match_rule([{"field_id": self.name_field.id}])
        self.assertEqual(len(match.field_ids), 1)
        match._onchange_model_id()
        self.assertFalse(match.field_ids)

    def test_usable_rules_returns_matching(self):
        """Test _usable_rules returns rules when fields match."""
        match = self._create_match_rule([{"field_id": self.name_field.id}])
        result_ids, field_to_match = self.env["spp.import.match"]._usable_rules("res.partner", ["name", "email"])
        self.assertIn(match.id, result_ids)
        self.assertTrue(len(field_to_match) > 0)

    def test_usable_rules_no_match(self):
        """Test _usable_rules returns empty when no fields match."""
        self._create_match_rule([{"field_id": self.name_field.id}])
        result_ids, _ = self.env["spp.import.match"]._usable_rules("res.partner", ["phone"])
        self.assertEqual(result_ids, [])

    def test_usable_rules_with_option_config_ids(self):
        """Test _usable_rules filters by option_config_ids."""
        match1 = self._create_match_rule([{"field_id": self.name_field.id}])
        match2 = self._create_match_rule([{"field_id": self.email_field.id}])
        # Only match1 should be returned
        result_ids, _ = self.env["spp.import.match"]._usable_rules(
            "res.partner", ["name", "email"], option_config_ids=[match1.id]
        )
        self.assertIn(match1.id, result_ids)
        self.assertNotIn(match2.id, result_ids)

    def test_match_find_single_match(self):
        """Test _match_find returns single match."""
        partner = self.env["res.partner"].create({"name": "UniqueMatchTest12345"})
        match = self._create_match_rule([{"field_id": self.name_field.id}])
        result = match._match_find(
            self.env["res.partner"],
            {"name": "UniqueMatchTest12345"},
            {"name": "UniqueMatchTest12345", "id": None},
        )
        self.assertEqual(result, partner)

    def test_match_find_no_match(self):
        """Test _match_find returns empty model when no match found."""
        match = self._create_match_rule([{"field_id": self.name_field.id}])
        result = match._match_find(
            self.env["res.partner"],
            {"name": "NonExistentPartner99999"},
            {"name": "NonExistentPartner99999", "id": None},
        )
        # Should return the model (empty recordset)
        self.assertFalse(result.id)

    def test_match_find_multiple_matches_raises(self):
        """Test _match_find raises ValidationError on multiple matches."""
        self.env["res.partner"].create({"name": "DuplicateMatchTest"})
        self.env["res.partner"].create({"name": "DuplicateMatchTest"})
        match = self._create_match_rule([{"field_id": self.name_field.id}])
        with self.assertRaises(ValidationError):
            match._match_find(
                self.env["res.partner"],
                {"name": "DuplicateMatchTest"},
                {"name": "DuplicateMatchTest", "id": None},
            )

    def test_match_find_conditional_skip(self):
        """Test _match_find skips rule when conditional value doesn't match."""
        self.env["res.partner"].create({"name": "ConditionalTest"})
        match = self._create_match_rule(
            [
                {
                    "field_id": self.name_field.id,
                    "is_conditional": True,
                    "imported_value": "WrongValue",
                }
            ]
        )
        result = match._match_find(
            self.env["res.partner"],
            {"name": "ConditionalTest"},
            {"name": "ConditionalTest", "id": None},
        )
        # Should not find match because conditional value doesn't match
        self.assertFalse(result.id)

    def test_match_find_conditional_match(self):
        """Test _match_find uses rule when conditional value matches."""
        partner = self.env["res.partner"].create({"name": "ConditionalMatchTest"})
        match = self._create_match_rule(
            [
                {
                    "field_id": self.name_field.id,
                    "is_conditional": True,
                    "imported_value": "ConditionalMatchTest",
                }
            ]
        )
        result = match._match_find(
            self.env["res.partner"],
            {"name": "ConditionalMatchTest"},
            {"name": "ConditionalMatchTest", "id": None},
        )
        self.assertEqual(result, partner)

    def test_field_compute_name(self):
        """Test _compute_name for match fields."""
        match = self._create_match_rule([{"field_id": self.name_field.id}])
        self.assertEqual(match.field_ids[0].name, "name")

    def test_field_compute_name_with_sub_field(self):
        """Test _compute_name includes sub_field when present."""
        # Find a relational field on res.partner for sub_field testing
        child_ids_field = self.env["ir.model.fields"].search(
            [
                ("name", "=", "child_ids"),
                ("model_id", "=", self.res_partner_model.id),
            ],
            limit=1,
        )
        if child_ids_field:
            match = self._create_match_rule(
                [
                    {
                        "field_id": child_ids_field.id,
                        "sub_field_id": self.name_field.id,
                    }
                ]
            )
            self.assertEqual(match.field_ids[0].name, "child_ids/name")

    def test_onchange_field_id_skips_relational(self):
        """_onchange_field_id skips duplicate check for relational fields."""
        parent_id_field = self.env["ir.model.fields"].search(
            [("name", "=", "parent_id"), ("model_id", "=", self.res_partner_model.id)],
            limit=1,
        )
        match = self._create_match_rule(
            [
                {"field_id": parent_id_field.id},
                {"field_id": parent_id_field.id},
            ]
        )
        # Should NOT raise ValidationError because parent_id is many2one
        for field_rec in match.field_ids:
            field_rec._onchange_field_id()
        self.assertEqual(len(match.field_ids), 2)

    def test_match_find_sub_field(self):
        """_match_find handles sub_field matching for relational fields."""
        child = self.env["res.partner"].create({"name": "SubFieldChild_Uniq99xyz"})
        parent = self.env["res.partner"].create(
            {
                "name": "SubFieldParent_Uniq99xyz",
                "child_ids": [(4, child.id)],
            }
        )
        child_ids_field = self.env["ir.model.fields"].search(
            [
                ("name", "=", "child_ids"),
                ("model_id", "=", self.res_partner_model.id),
            ],
            limit=1,
        )
        match = self._create_match_rule(
            [
                {
                    "field_id": child_ids_field.id,
                    "sub_field_id": self.name_field.id,
                }
            ]
        )
        result = match._match_find(
            self.env["res.partner"],
            {"child_ids": [(0, 0, {"name": "SubFieldChild_Uniq99xyz"})]},
            {"child_ids/name": "SubFieldChild_Uniq99xyz", "id": None},
        )
        self.assertEqual(result, parent)

    def test_match_find_multiple_combinations(self):
        """_match_find iterates rules; first matching single result wins."""
        partner = self.env["res.partner"].create({"name": "MultiCombo99xyz", "email": "multicombo@test.com"})
        # First rule by email (lower sequence -> tried first)
        match1 = self._create_match_rule([{"field_id": self.email_field.id}])
        match1.sequence = 1
        # Second rule by name
        match2 = self._create_match_rule([{"field_id": self.name_field.id}])
        match2.sequence = 2
        # Email won't match, but name will
        result = self.env["spp.import.match"]._match_find(
            self.env["res.partner"],
            {"name": "MultiCombo99xyz", "email": "nomatch@test.com"},
            {"name": "MultiCombo99xyz", "email": "nomatch@test.com", "id": None},
        )
        self.assertEqual(result, partner)
