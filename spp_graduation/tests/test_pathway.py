# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestGraduationPathway(TransactionCase):
    """Test graduation pathway management."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Pathway = cls.env["spp.graduation.pathway"]
        cls.Criteria = cls.env["spp.graduation.criteria"]

    def test_pathway_creation(self):
        """Test graduation pathway can be created."""
        pathway = self.Pathway.create(
            {
                "name": "Standard Graduation",
                "code": "STD",
            }
        )
        self.assertTrue(pathway.active)
        self.assertEqual(pathway.criteria_count, 0)

    def test_pathway_with_monitoring(self):
        """Test pathway with post-graduation monitoring."""
        pathway = self.Pathway.create(
            {
                "name": "Extended Monitoring",
                "code": "EXT",
                "post_graduation_monitoring_months": 6,
            }
        )
        self.assertEqual(pathway.post_graduation_monitoring_months, 6)

    def test_pathway_with_criteria(self):
        """Test pathway with graduation criteria."""
        pathway = self.Pathway.create(
            {
                "name": "Full Graduation",
                "code": "FULL",
            }
        )

        self.Criteria.create(
            {
                "pathway_id": pathway.id,
                "name": "Economic Stability",
                "weight": 30,
                "is_required": True,
            }
        )
        self.Criteria.create(
            {
                "pathway_id": pathway.id,
                "name": "Social Integration",
                "weight": 20,
                "is_required": False,
            }
        )

        pathway.invalidate_recordset(["criteria_count"])
        self.assertEqual(pathway.criteria_count, 2)

    def test_criteria_weight_total(self):
        """Test criteria weights can sum to different totals."""
        pathway = self.Pathway.create(
            {
                "name": "Weighted Pathway",
                "code": "WGT",
            }
        )

        self.Criteria.create(
            {
                "pathway_id": pathway.id,
                "name": "Criterion A",
                "weight": 50,
            }
        )
        self.Criteria.create(
            {
                "pathway_id": pathway.id,
                "name": "Criterion B",
                "weight": 50,
            }
        )

        total = sum(c.weight for c in pathway.criteria_ids)
        self.assertEqual(total, 100)

    def test_criteria_weight_must_be_positive(self):
        """Test criteria weight constraint rejects zero and negative values."""
        pathway = self.Pathway.create(
            {
                "name": "Test Pathway",
                "code": "TST",
            }
        )

        with self.assertRaises(ValidationError):
            self.Criteria.create(
                {
                    "pathway_id": pathway.id,
                    "name": "Zero Weight",
                    "weight": 0,
                }
            )

        with self.assertRaises(ValidationError):
            self.Criteria.create(
                {
                    "pathway_id": pathway.id,
                    "name": "Negative Weight",
                    "weight": -5,
                }
            )

    def test_pathway_boolean_field_defaults(self):
        """Test renamed boolean fields have correct defaults."""
        pathway = self.Pathway.create(
            {
                "name": "Default Pathway",
            }
        )
        self.assertTrue(pathway.is_positive_exit)
        self.assertTrue(pathway.is_assessment_required)
        self.assertTrue(pathway.is_approval_required)

    def test_criteria_assessment_method_values(self):
        """Test all assessment method selection values are accepted."""
        pathway = self.Pathway.create({"name": "Method Test Pathway"})
        methods = ["self_report", "verification", "computed", "observation"]
        for method in methods:
            criteria = self.Criteria.create(
                {
                    "pathway_id": pathway.id,
                    "name": f"Criterion {method}",
                    "weight": 1.0,
                    "assessment_method": method,
                }
            )
            self.assertEqual(criteria.assessment_method, method)

    def test_criteria_assessment_method_default(self):
        """Test assessment method defaults to verification."""
        pathway = self.Pathway.create({"name": "Default Method Pathway"})
        criteria = self.Criteria.create(
            {
                "pathway_id": pathway.id,
                "name": "Default Method",
                "weight": 1.0,
            }
        )
        self.assertEqual(criteria.assessment_method, "verification")

    def test_criteria_active_field(self):
        """Test criteria active field defaults to True and can be archived."""
        pathway = self.Pathway.create({"name": "Active Test Pathway"})
        criteria = self.Criteria.create(
            {
                "pathway_id": pathway.id,
                "name": "Active Criterion",
                "weight": 1.0,
            }
        )
        self.assertTrue(criteria.active)
        criteria.active = False
        self.assertFalse(criteria.active)

    def test_pathway_description(self):
        """Test pathway description field is stored correctly."""
        pathway = self.Pathway.create(
            {
                "name": "Described Pathway",
                "description": "A pathway for testing description storage.",
            }
        )
        self.assertEqual(pathway.description, "A pathway for testing description storage.")

    def test_criteria_code_and_description(self):
        """Test criteria code and description fields are stored correctly."""
        pathway = self.Pathway.create({"name": "Code Test Pathway"})
        criteria = self.Criteria.create(
            {
                "pathway_id": pathway.id,
                "name": "Coded Criterion",
                "code": "ECON_01",
                "weight": 1.0,
                "description": "Measures economic stability.",
            }
        )
        self.assertEqual(criteria.code, "ECON_01")
        self.assertEqual(criteria.description, "Measures economic stability.")
