from odoo.tests import TransactionCase


class TestApplyStrategies(TransactionCase):
    """Tests for CR apply strategies."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cr_model = cls.env["spp.change.request"]
        cls.partner_model = cls.env["res.partner"]

        # Create test registrant
        cls.registrant = cls.partner_model.create(
            {
                "name": "Test Individual",
                "given_name": "Old",
                "family_name": "Name",
                "is_registrant": True,
                "is_group": False,
            }
        )

        # Get edit individual CR type by code
        cls.cr_type_edit_individual = cls.env["spp.change.request.type"].search(
            [("code", "=", "edit_individual")], limit=1
        )
        if not cls.cr_type_edit_individual:
            # Create a minimal test type with field mappings if not installed
            cls.cr_type_edit_individual = cls.env["spp.change.request.type"].create(
                {
                    "name": "Test Edit Individual",
                    "code": "test_edit_individual",
                    "target_type": "individual",
                    "detail_model": "spp.cr.detail.edit_individual",
                    "apply_strategy": "field_mapping",
                }
            )
            # Add required field mappings for the test
            mapping_model = cls.env["spp.change.request.type.mapping"]
            for field in ["given_name", "family_name", "phone", "email"]:
                mapping_model.create(
                    {
                        "type_id": cls.cr_type_edit_individual.id,
                        "source_field": field,
                        "target_field": field,
                        "transform": "direct",
                    }
                )

    def test_field_mapping_apply(self):
        """Test field mapping strategy applies changes correctly."""
        # Create CR
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit_individual.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Update detail record
        detail = cr.get_detail()
        detail.write(
            {
                "given_name": "New",
                "family_name": "Updated",
                "phone": "1234567890",
            }
        )

        # Approve and apply
        cr.approval_state = "approved"
        cr.action_apply()

        # Verify changes applied
        self.registrant.invalidate_recordset()
        self.assertEqual(self.registrant.given_name, "New")
        self.assertEqual(self.registrant.family_name, "Updated")
        self.assertEqual(self.registrant.phone, "1234567890")

    def test_field_mapping_preview(self):
        """Test field mapping preview shows correct changes."""
        # Create CR
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit_individual.id,
                "registrant_id": self.registrant.id,
            }
        )

        # Update detail record
        detail = cr.get_detail()
        detail.write({"given_name": "Preview"})

        # Get preview
        strategy = self.env["spp.cr.strategy.field_mapping"]
        preview = strategy.preview(cr)

        self.assertIn("given_name", preview)
        self.assertEqual(preview["given_name"]["new"], "Preview")

    def test_manual_strategy_noop(self):
        """Test manual strategy does nothing but returns True."""
        strategy = self.env["spp.cr.strategy.manual"]
        cr = self.cr_model.create(
            {
                "request_type_id": self.cr_type_edit_individual.id,
                "registrant_id": self.registrant.id,
            }
        )
        result = strategy.apply(cr)
        self.assertTrue(result)
