# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestHxlImportMapping(TransactionCase):
    """Test HXL Import Mapping model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Mapping = cls.env["spp.hxl.import.mapping"]
        cls.Batch = cls.env["spp.hxl.import.batch"]
        cls.Profile = cls.env["spp.hxl.import.profile"]

        # Create test profile
        cls.profile = cls.Profile.create(
            {
                "name": "Mapping Test Profile",
                "code": "mapping_test_profile",
                "area_matching_strategy": "pcode",
                "area_column_tag": "#adm2+pcode",
            }
        )

        # Create test batch
        cls.batch = cls.Batch.create(
            {
                "name": "Test Import Batch",
                "profile_id": cls.profile.id,
            }
        )

    def test_create_mapping(self):
        """Test creating a basic column mapping."""
        mapping = self.Mapping.create(
            {
                "batch_id": self.batch.id,
                "source_column": "District",
                "detected_hxl_tag": "#adm2+name",
                "mapping_type": "area",
            }
        )

        self.assertEqual(mapping.source_column, "District")
        self.assertEqual(mapping.detected_hxl_tag, "#adm2+name")
        self.assertEqual(mapping.mapping_type, "area")

    def test_required_fields(self):
        """Test that required fields are enforced."""
        # batch_id is required
        with self.assertRaises(Exception):  # noqa: B017
            self.Mapping.create(
                {
                    "source_column": "Test",
                    "mapping_type": "skip",
                }
            )

    def test_default_values(self):
        """Test default values are set correctly."""
        mapping = self.Mapping.create(
            {
                "batch_id": self.batch.id,
                "source_column": "Test Column",
            }
        )

        self.assertEqual(mapping.sequence, 10)
        self.assertEqual(mapping.mapping_type, "skip")
        self.assertEqual(mapping.confidence, 0.0)

    def test_all_mapping_types(self):
        """Test all mapping type selections."""
        types = ["area", "aggregate", "filter", "disaggregate", "skip"]

        for map_type in types:
            mapping = self.Mapping.create(
                {
                    "batch_id": self.batch.id,
                    "source_column": f"Test {map_type}",
                    "mapping_type": map_type,
                }
            )
            self.assertEqual(mapping.mapping_type, map_type)

    def test_confidence_score_ranges(self):
        """Test confidence scores between 0.0 and 1.0."""
        # Test 0.0 confidence
        mapping_low = self.Mapping.create(
            {
                "batch_id": self.batch.id,
                "source_column": "Low Confidence",
                "mapping_type": "skip",
                "confidence": 0.0,
            }
        )
        self.assertEqual(mapping_low.confidence, 0.0)

        # Test 0.5 confidence
        mapping_mid = self.Mapping.create(
            {
                "batch_id": self.batch.id,
                "source_column": "Mid Confidence",
                "mapping_type": "aggregate",
                "confidence": 0.5,
            }
        )
        self.assertEqual(mapping_mid.confidence, 0.5)

        # Test 1.0 confidence
        mapping_high = self.Mapping.create(
            {
                "batch_id": self.batch.id,
                "source_column": "High Confidence",
                "mapping_type": "area",
                "confidence": 1.0,
            }
        )
        self.assertEqual(mapping_high.confidence, 1.0)

    def test_name_get_display(self):
        """Test name_get returns column info."""
        mapping = self.Mapping.create(
            {
                "batch_id": self.batch.id,
                "source_column": "Households",
                "detected_hxl_tag": "#affected+hh",
                "mapping_type": "aggregate",
            }
        )

        result = mapping.name_get()

        # Should return [(id, 'source_column [tag] -> type')]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], mapping.id)
        self.assertIn("Households", result[0][1])
        self.assertIn("#affected+hh", result[0][1])
        self.assertIn("aggregate", result[0][1])

    def test_name_get_without_tag(self):
        """Test name_get handles missing HXL tag."""
        mapping = self.Mapping.create(
            {
                "batch_id": self.batch.id,
                "source_column": "Unknown",
                "mapping_type": "skip",
            }
        )

        result = mapping.name_get()

        # Should still work
        self.assertEqual(len(result), 1)
        self.assertIn("Unknown", result[0][1])

    def test_cascade_deletion(self):
        """Test mapping is deleted when batch is deleted."""
        # Create a new batch for this test
        batch = self.Batch.create(
            {
                "name": "Cascade Test Batch",
                "profile_id": self.profile.id,
            }
        )

        mapping = self.Mapping.create(
            {
                "batch_id": batch.id,
                "source_column": "Cascade Test",
                "mapping_type": "skip",
            }
        )
        mapping_id = mapping.id

        # Delete batch
        batch.unlink()

        # Mapping should be deleted
        mapping_check = self.Mapping.browse(mapping_id)
        self.assertFalse(mapping_check.exists())

    def test_ordering(self):
        """Test mappings are ordered by batch_id and sequence."""
        mapping1 = self.Mapping.create(
            {
                "batch_id": self.batch.id,
                "source_column": "Column 1",
                "mapping_type": "skip",
                "sequence": 30,
            }
        )

        mapping2 = self.Mapping.create(
            {
                "batch_id": self.batch.id,
                "source_column": "Column 2",
                "mapping_type": "skip",
                "sequence": 10,
            }
        )

        mappings = self.Mapping.search([("batch_id", "=", self.batch.id)])

        # mapping2 (sequence 10) should come before mapping1 (sequence 30)
        self.assertEqual(mappings[0], mapping2)
        self.assertEqual(mappings[1], mapping1)

    def test_detected_hxl_tag_storage(self):
        """Test HXL tag can be stored and retrieved."""
        tags = [
            "#adm2+pcode",
            "#affected+hh+f",
            "#meta+count",
            "#loc+lat",
        ]

        for tag in tags:
            mapping = self.Mapping.create(
                {
                    "batch_id": self.batch.id,
                    "source_column": f"Test {tag}",
                    "detected_hxl_tag": tag,
                    "mapping_type": "aggregate",
                }
            )
            self.assertEqual(mapping.detected_hxl_tag, tag)
