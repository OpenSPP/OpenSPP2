# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsRequestFromTemplateWizard(DrimsTestCommon):
    """Test cases for DRIMS Request from Template Wizard functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.future_date = date.today() + timedelta(days=30)

        # Create additional products for template testing
        cls.product2 = cls.env["product.product"].create(
            {
                "name": "Test Relief Item 2",
                "type": "consu",
                "standard_price": 50.0,
            }
        )

    def _create_template(self, name, lines, priority=None, is_shared=True):
        """Helper to create a request template."""
        line_vals = []
        for product, quantity, notes in lines:
            line_vals.append(
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "quantity": quantity,
                        "uom_id": product.uom_id.id,
                        "notes": notes or "",
                    },
                )
            )

        template_vals = {
            "name": name,
            "is_shared": is_shared,
            "line_ids": line_vals,
        }
        if priority:
            template_vals["priority_id"] = priority.id

        return self.env["spp.drims.request.template"].create(template_vals)

    def test_template_selection_populates_lines(self):
        """Test select template, verify lines match template."""
        # Create template with multiple lines
        template = self._create_template(
            "Emergency Response Kit",
            [
                (self.product, 100.0, "Primary relief item"),
                (self.product2, 50.0, "Secondary item"),
            ],
            priority=self.priority_critical,
        )

        # Create wizard
        wizard = self.env["spp.drims.request.from.template.wizard"].create(
            {
                "template_id": template.id,
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        wizard._onchange_template_id()

        # Verify lines are populated from template
        self.assertEqual(len(wizard.line_ids), 2)

        # Verify first line
        line1 = wizard.line_ids.filtered(lambda line: line.product_id == self.product)
        self.assertEqual(len(line1), 1)
        self.assertEqual(line1.quantity, 100.0)
        self.assertEqual(line1.notes, "Primary relief item")

        # Verify second line
        line2 = wizard.line_ids.filtered(lambda line: line.product_id == self.product2)
        self.assertEqual(len(line2), 1)
        self.assertEqual(line2.quantity, 50.0)
        self.assertEqual(line2.notes, "Secondary item")

        # Verify priority is set from template
        self.assertEqual(wizard.priority_id, self.priority_critical)

    def test_empty_template_error(self):
        """Test template with no lines raises UserError."""
        # Create template with no lines
        template = self.env["spp.drims.request.template"].create(
            {
                "name": "Empty Template",
                "is_shared": True,
            }
        )

        wizard = self.env["spp.drims.request.from.template.wizard"].create(
            {
                "template_id": template.id,
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        wizard._onchange_template_id()

        # Try to create request - should fail
        with self.assertRaises(UserError) as context:
            wizard.action_create_request()
        self.assertIn("at least one item", str(context.exception))

    def test_zero_quantity_error(self):
        """Test all quantities set to 0 raises UserError."""
        template = self._create_template(
            "Test Template",
            [(self.product, 100.0, None)],
        )

        wizard = self.env["spp.drims.request.from.template.wizard"].create(
            {
                "template_id": template.id,
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        wizard._onchange_template_id()

        # Set all quantities to 0
        for line in wizard.line_ids:
            line.quantity = 0.0

        # Try to create request - should fail
        with self.assertRaises(UserError) as context:
            wizard.action_create_request()
        self.assertIn("zero quantity", str(context.exception))

    def test_request_creation(self):
        """Test complete wizard, verify request created correctly."""
        template = self._create_template(
            "Flood Response Kit",
            [
                (self.product, 100.0, "Water purification"),
                (self.product2, 75.0, "Shelter materials"),
            ],
            priority=self.priority_routine,
        )

        wizard = self.env["spp.drims.request.from.template.wizard"].create(
            {
                "template_id": template.id,
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
                "notes": "Urgent need for affected areas",
            }
        )
        wizard._onchange_template_id()

        # Modify one of the quantities
        line1 = wizard.line_ids.filtered(lambda line: line.product_id == self.product)
        line1.quantity = 120.0

        # Create request
        result = wizard.action_create_request()

        # Verify result
        self.assertEqual(result["res_model"], "spp.drims.request")
        request = self.env["spp.drims.request"].browse(result["res_id"])

        # Verify request fields
        self.assertEqual(request.incident_id, self.incident)
        self.assertEqual(request.destination_area_id, self.area)
        self.assertEqual(request.date_needed, self.future_date)
        self.assertEqual(request.priority_id, self.priority_routine)
        self.assertEqual(request.notes, "Urgent need for affected areas")

        # Verify request lines
        self.assertEqual(len(request.line_ids), 2)

        # Verify first line (modified quantity)
        req_line1 = request.line_ids.filtered(lambda line: line.product_id == self.product)
        self.assertEqual(len(req_line1), 1)
        self.assertEqual(req_line1.quantity_requested, 120.0)  # Modified value
        self.assertEqual(req_line1.notes, "Water purification")

        # Verify second line (original quantity)
        req_line2 = request.line_ids.filtered(lambda line: line.product_id == self.product2)
        self.assertEqual(len(req_line2), 1)
        self.assertEqual(req_line2.quantity_requested, 75.0)
        self.assertEqual(req_line2.notes, "Shelter materials")

    def test_partial_line_selection(self):
        """Test creating request with some lines set to 0 (excluded)."""
        template = self._create_template(
            "Mixed Kit",
            [
                (self.product, 100.0, None),
                (self.product2, 50.0, None),
            ],
        )

        wizard = self.env["spp.drims.request.from.template.wizard"].create(
            {
                "template_id": template.id,
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        wizard._onchange_template_id()

        # Set second line to 0 (exclude it)
        line2 = wizard.line_ids.filtered(lambda line: line.product_id == self.product2)
        line2.quantity = 0.0

        # Create request
        result = wizard.action_create_request()
        request = self.env["spp.drims.request"].browse(result["res_id"])

        # Verify only the first line was included
        self.assertEqual(len(request.line_ids), 1)
        self.assertEqual(request.line_ids[0].product_id, self.product)

    def test_template_change_updates_lines(self):
        """Test changing template updates the wizard lines."""
        template1 = self._create_template(
            "Template 1",
            [(self.product, 100.0, None)],
        )
        template2 = self._create_template(
            "Template 2",
            [(self.product2, 200.0, None)],
        )

        wizard = self.env["spp.drims.request.from.template.wizard"].create(
            {
                "template_id": template1.id,
                "incident_id": self.incident.id,
                "destination_area_id": self.area.id,
                "date_needed": self.future_date,
            }
        )
        wizard._onchange_template_id()

        # Verify initial lines
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids[0].product_id, self.product)

        # Change template
        wizard.template_id = template2
        wizard._onchange_template_id()

        # Verify lines updated
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids[0].product_id, self.product2)
        self.assertEqual(wizard.line_ids[0].quantity, 200.0)
