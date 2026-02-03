"""Tests for spp.artifact.usage model."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestArtifactUsage(TransactionCase):
    """Test cases for ArtifactUsage model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ArtifactUsage = cls.env["spp.artifact.usage"]
        # Create test partners to use as artifacts and consumers
        cls.artifact_partner = cls.env["res.partner"].create({"name": "Artifact Partner"})
        cls.consumer_partner = cls.env["res.partner"].create({"name": "Consumer Partner"})

    def test_create_usage(self):
        """Test creating a usage record."""
        usage = self.ArtifactUsage.create(
            {
                "artifact_model": "res.partner",
                "artifact_res_id": self.artifact_partner.id,
                "consumer_model": "res.partner",
                "consumer_res_id": self.consumer_partner.id,
                "usage_type": "eligibility",
            }
        )
        self.assertEqual(usage.artifact_name, "Artifact Partner")
        self.assertEqual(usage.consumer_name, "Consumer Partner")
        self.assertEqual(usage.usage_type, "eligibility")

    def test_register_usage(self):
        """Test registering a usage relationship."""
        usage = self.ArtifactUsage.register_usage(
            artifact_model="res.partner",
            artifact_res_id=self.artifact_partner.id,
            consumer_model="res.partner",
            consumer_res_id=self.consumer_partner.id,
            usage_type="entitlement",
        )
        self.assertTrue(usage.id)
        self.assertEqual(usage.usage_type, "entitlement")

    def test_register_usage_idempotent(self):
        """Test that registering same usage twice returns existing record."""
        usage1 = self.ArtifactUsage.register_usage(
            artifact_model="res.partner",
            artifact_res_id=self.artifact_partner.id,
            consumer_model="res.partner",
            consumer_res_id=self.consumer_partner.id,
            usage_type="scoring",
        )
        usage2 = self.ArtifactUsage.register_usage(
            artifact_model="res.partner",
            artifact_res_id=self.artifact_partner.id,
            consumer_model="res.partner",
            consumer_res_id=self.consumer_partner.id,
            usage_type="scoring",
        )
        self.assertEqual(usage1, usage2)

    def test_unregister_usage(self):
        """Test unregistering a usage relationship."""
        self.ArtifactUsage.register_usage(
            artifact_model="res.partner",
            artifact_res_id=self.artifact_partner.id,
            consumer_model="res.partner",
            consumer_res_id=self.consumer_partner.id,
            usage_type="validation",
        )
        count = self.ArtifactUsage.unregister_usage(
            artifact_model="res.partner",
            artifact_res_id=self.artifact_partner.id,
            consumer_model="res.partner",
            consumer_res_id=self.consumer_partner.id,
            usage_type="validation",
        )
        self.assertEqual(count, 1)

        # Verify it's gone
        remaining = self.ArtifactUsage.search(
            [
                ("artifact_model", "=", "res.partner"),
                ("artifact_res_id", "=", self.artifact_partner.id),
                ("consumer_model", "=", "res.partner"),
                ("consumer_res_id", "=", self.consumer_partner.id),
            ]
        )
        self.assertFalse(remaining)

    def test_unregister_usage_all_types(self):
        """Test unregistering all usage types when type not specified."""
        self.ArtifactUsage.register_usage(
            artifact_model="res.partner",
            artifact_res_id=self.artifact_partner.id,
            consumer_model="res.partner",
            consumer_res_id=self.consumer_partner.id,
            usage_type="eligibility",
        )
        self.ArtifactUsage.register_usage(
            artifact_model="res.partner",
            artifact_res_id=self.artifact_partner.id,
            consumer_model="res.partner",
            consumer_res_id=self.consumer_partner.id,
            usage_type="entitlement",
        )
        count = self.ArtifactUsage.unregister_usage(
            artifact_model="res.partner",
            artifact_res_id=self.artifact_partner.id,
            consumer_model="res.partner",
            consumer_res_id=self.consumer_partner.id,
        )
        self.assertEqual(count, 2)

    def test_unique_usage_constraint(self):
        """Test that duplicate usages are rejected by SQL constraint."""
        self.ArtifactUsage.create(
            {
                "artifact_model": "res.partner",
                "artifact_res_id": self.artifact_partner.id,
                "consumer_model": "res.partner",
                "consumer_res_id": self.consumer_partner.id,
                "usage_type": "compliance",
            }
        )
        # Using create directly should fail due to SQL constraint
        from psycopg2 import IntegrityError

        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.ArtifactUsage.create(
                {
                    "artifact_model": "res.partner",
                    "artifact_res_id": self.artifact_partner.id,
                    "consumer_model": "res.partner",
                    "consumer_res_id": self.consumer_partner.id,
                    "usage_type": "compliance",
                }
            )

    def test_compute_names_deleted_records(self):
        """Test name computation when referenced records are deleted."""
        usage = self.ArtifactUsage.create(
            {
                "artifact_model": "res.partner",
                "artifact_res_id": self.artifact_partner.id,
                "consumer_model": "res.partner",
                "consumer_res_id": self.consumer_partner.id,
                "usage_type": "other",
            }
        )
        self.assertEqual(usage.artifact_name, "Artifact Partner")
        # Point to non-existent record
        usage.write({"artifact_res_id": 999999999})
        usage.invalidate_recordset()
        self.assertEqual(usage.artifact_name, "Deleted")

    def test_view_actions(self):
        """Test view artifact and consumer actions."""
        usage = self.ArtifactUsage.create(
            {
                "artifact_model": "res.partner",
                "artifact_res_id": self.artifact_partner.id,
                "consumer_model": "res.partner",
                "consumer_res_id": self.consumer_partner.id,
                "usage_type": "other",
            }
        )
        artifact_action = usage.action_view_artifact()
        self.assertEqual(artifact_action["res_model"], "res.partner")
        self.assertEqual(artifact_action["res_id"], self.artifact_partner.id)

        consumer_action = usage.action_view_consumer()
        self.assertEqual(consumer_action["res_model"], "res.partner")
        self.assertEqual(consumer_action["res_id"], self.consumer_partner.id)
