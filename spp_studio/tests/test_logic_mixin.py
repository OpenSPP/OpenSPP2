# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for spp.studio - Logic, Usage, Tag, and Version models."""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLogicUsage(TransactionCase):
    """Tests for logic usage tracking."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicUsage = cls.env["spp.studio.usage"]

        cls.logic = cls.Logic.create(
            {
                "name": "Trackable Logic",
                "expression_type": "filter",
                "cel_expression": "true",
                "state": "published",
            }
        )

    def test_create_usage_record(self):
        """Test creating usage record."""
        usage = self.LogicUsage.create(
            {
                "logic_id": self.logic.id,
                "res_model": "test.model",
                "res_id": 123,
                "usage_type": "filter",
            }
        )

        self.assertTrue(usage.id)
        self.assertEqual(usage.logic_id, self.logic)
        self.assertEqual(usage.res_model, "test.model")
        self.assertEqual(usage.res_id, 123)

    def test_usage_count_computed(self):
        """Test usage_count is computed correctly."""
        # Initially no usage
        self.assertEqual(self.logic.usage_count, 0)

        # Create usage records
        self.LogicUsage.create(
            {
                "logic_id": self.logic.id,
                "res_model": "test.model1",
                "res_id": 1,
                "usage_type": "filter",
            }
        )
        self.LogicUsage.create(
            {
                "logic_id": self.logic.id,
                "res_model": "test.model2",
                "res_id": 2,
                "usage_type": "filter",
            }
        )

        # Refresh record
        self.logic.invalidate_recordset()
        self.assertEqual(self.logic.usage_count, 2)

    def test_display_name_computed(self):
        """Test display_name is computed from model and record info."""
        usage = self.LogicUsage.create(
            {
                "logic_id": self.logic.id,
                "res_model": "res.partner",
                "res_id": 1,
                "usage_type": "filter",
            }
        )

        # Should have some display name
        self.assertTrue(usage.display_name)


@tagged("post_install", "-at_install")
class TestLogicTag(TransactionCase):
    """Tests for logic tags using vocabulary codes."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.VocabCode = cls.env["spp.vocabulary.code"]
        cls.vocab = cls.env.ref("spp_studio.vocab_logic_tags")

    def test_create_tag(self):
        """Test creating a logic tag as vocabulary code."""
        tag = self.VocabCode.create(
            {
                "vocabulary_id": self.vocab.id,
                "code": "test_tag",
                "display": "Test Tag",
                "color": 5,
            }
        )

        self.assertTrue(tag.id)
        self.assertEqual(tag.display, "Test Tag")
        self.assertEqual(tag.color, 5)

    def test_tag_colors(self):
        """Test various tag colors."""
        for color in range(0, 12):
            tag = self.VocabCode.create(
                {
                    "vocabulary_id": self.vocab.id,
                    "code": f"color_{color}",
                    "display": f"Color {color}",
                    "color": color,
                }
            )
            self.assertEqual(tag.color, color)


@tagged("post_install", "-at_install")
class TestLogicVersion(TransactionCase):
    """Tests for logic versioning."""

    @classmethod
    def setUpClass(cls):
        """Set up test data."""
        super().setUpClass()
        cls.Logic = cls.env["spp.cel.expression"]
        cls.LogicVersion = cls.env["spp.studio.version"]

    def test_create_version_record(self):
        """Test creating version record directly."""
        logic = self.Logic.create(
            {
                "name": "Versioned Logic",
                "expression_type": "filter",
                "cel_expression": "income < 5000",
            }
        )

        version = self.LogicVersion.create(
            {
                "logic_id": logic.id,
                "version": 1,
                "cel_expression": "income < 5000",
                "state": "published",
            }
        )

        self.assertTrue(version.id)
        self.assertEqual(version.version, 1)
        self.assertEqual(version.logic_id, logic)

    def test_version_created_on_publish(self):
        """Test that version is created when logic is published."""
        logic = self.Logic.create(
            {
                "name": "To Be Published",
                "expression_type": "filter",
                "cel_expression": "true",
            }
        )

        initial_version = logic.version

        # Publish
        logic.action_publish()

        # Check version record was created
        versions = self.LogicVersion.search([("logic_id", "=", logic.id)])
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].version, initial_version)

        # Logic version should be incremented
        self.assertEqual(logic.version, initial_version + 1)
