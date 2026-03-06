# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

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
