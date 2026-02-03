# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.tests import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsTemplate(DrimsTestCommon):
    """Tests for DRIMS Request Template model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.future_date = date.today() + timedelta(days=30)

    def test_create_template(self):
        """Test basic template creation."""
        template = self.env["spp.drims.request.template"].create(
            {
                "name": "Emergency Food Kit",
                "description": "Standard emergency food package",
            }
        )
        self.assertEqual(template.name, "Emergency Food Kit")
        self.assertEqual(template.user_id, self.env.user)
        self.assertFalse(template.is_shared)

    def test_template_with_lines(self):
        """Test template with line items."""
        template = self.env["spp.drims.request.template"].create(
            {
                "name": "Medical Supply Kit",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 100,
                            "uom_id": self.product.uom_id.id,
                            "notes": "Critical supply",
                        },
                    )
                ],
            }
        )
        self.assertEqual(len(template.line_ids), 1)
        self.assertEqual(template.line_ids[0].quantity, 100)
        self.assertEqual(template.line_ids[0].notes, "Critical supply")

    def test_create_request_from_template(self):
        """Test creating a request from a template with context values."""
        template = self.env["spp.drims.request.template"].create(
            {
                "name": "Test Template",
                "priority_id": self.priority_routine.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 50,
                            "uom_id": self.product.uom_id.id,
                        },
                    ),
                ],
            }
        )
        # Create request from template with all required values
        action = template.action_create_request(
            incident_id=self.incident.id,
            destination_area_id=self.area.id,
            date_needed=self.future_date,
        )
        self.assertEqual(action["res_model"], "spp.drims.request")
        request_id = action["res_id"]
        request = self.env["spp.drims.request"].browse(request_id)
        self.assertTrue(request.exists())
        self.assertEqual(request.priority_id, self.priority_routine)
        self.assertEqual(request.incident_id, self.incident)
        self.assertEqual(request.destination_area_id, self.area)
        self.assertEqual(len(request.line_ids), 1)
        self.assertEqual(request.line_ids[0].quantity_requested, 50)

    def test_create_request_from_template_no_context(self):
        """Test that template returns form action when no context values."""
        template = self.env["spp.drims.request.template"].create(
            {
                "name": "Test Template",
                "priority_id": self.priority_routine.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 25,
                            "uom_id": self.product.uom_id.id,
                        },
                    ),
                ],
            }
        )
        # Without required values, should return form action
        action = template.action_create_request()
        self.assertEqual(action["res_model"], "spp.drims.request")
        self.assertEqual(action["view_mode"], "form")
        self.assertNotIn("res_id", action)  # No record created
        # Context should have defaults
        self.assertEqual(action["context"]["default_priority_id"], self.priority_routine.id)
        self.assertEqual(len(action["context"]["default_line_ids"]), 1)

    def test_shared_template(self):
        """Test shared template visibility."""
        template = self.env["spp.drims.request.template"].create(
            {
                "name": "Shared Template",
                "is_shared": True,
            }
        )
        self.assertTrue(template.is_shared)

    def test_template_line_product_onchange(self):
        """Test UoM auto-set on product change."""
        template = self.env["spp.drims.request.template"].create(
            {
                "name": "Test Template",
            }
        )
        line = self.env["spp.drims.request.template.line"].new(
            {
                "template_id": template.id,
                "product_id": self.product.id,
                "quantity": 10,
            }
        )
        line._onchange_product_id()
        self.assertEqual(line.uom_id, self.product.uom_id)

    def test_template_multiple_lines(self):
        """Test template with multiple product lines."""
        product2 = self.env["product.product"].create(
            {
                "name": "Second Relief Item",
                "type": "consu",
            }
        )
        template = self.env["spp.drims.request.template"].create(
            {
                "name": "Multi-Item Kit",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 100,
                            "uom_id": self.product.uom_id.id,
                            "sequence": 10,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": product2.id,
                            "quantity": 50,
                            "uom_id": product2.uom_id.id,
                            "sequence": 20,
                        },
                    ),
                ],
            }
        )
        self.assertEqual(len(template.line_ids), 2)
        # Test ordering
        lines = template.line_ids.sorted("sequence")
        self.assertEqual(lines[0].product_id, self.product)
        self.assertEqual(lines[1].product_id, product2)
