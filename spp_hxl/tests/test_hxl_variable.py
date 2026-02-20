import logging

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestHxlVariable(TransactionCase):
    """Test cases for CEL Variable HXL extension"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.CELVariable = cls.env["spp.cel.variable"]

    def test_hxl_tag_computation_basic(self):
        """Test basic HXL tag computation from hashtag and attributes"""
        variable = self.CELVariable.create(
            {
                "name": "test_hxl_basic",
                "cel_accessor": "test_hxl_basic",
                "source_type": "constant",
                "hxl_hashtag": "#affected",
                "hxl_attributes": "+f+children",
            }
        )
        self.assertEqual(variable.hxl_tag, "#affected+f+children")

    def test_hxl_tag_computation_hashtag_only(self):
        """Test HXL tag computation with only hashtag"""
        variable = self.CELVariable.create(
            {
                "name": "test_hxl_hashtag",
                "cel_accessor": "test_hxl_hashtag",
                "source_type": "constant",
                "hxl_hashtag": "#population",
            }
        )
        self.assertEqual(variable.hxl_tag, "#population")

    def test_hxl_tag_computation_no_hashtag(self):
        """Test HXL tag computation when no hashtag is set"""
        variable = self.CELVariable.create(
            {
                "name": "test_hxl_no_tag",
                "cel_accessor": "test_hxl_no_tag",
                "source_type": "constant",
            }
        )
        self.assertFalse(variable.hxl_tag)

    def test_hxl_tag_computation_auto_prefix(self):
        """Test HXL tag computation automatically adds # if missing"""
        variable = self.CELVariable.create(
            {
                "name": "test_hxl_auto_prefix",
                "cel_accessor": "test_hxl_auto_prefix",
                "source_type": "constant",
                "hxl_hashtag": "affected",  # Missing #
                "hxl_attributes": "+m",
            }
        )
        self.assertEqual(variable.hxl_tag, "#affected+m")

    def test_hxl_import_action_default(self):
        """Test default HXL import action"""
        variable = self.CELVariable.create(
            {
                "name": "test_hxl_import",
                "cel_accessor": "test_hxl_import",
                "source_type": "constant",
                "hxl_hashtag": "#indicator",
            }
        )
        self.assertEqual(variable.hxl_import_action, "variable")

    def test_hxl_export_include_default(self):
        """Test default HXL export include"""
        variable = self.CELVariable.create(
            {
                "name": "test_hxl_export",
                "cel_accessor": "test_hxl_export",
                "source_type": "constant",
                "hxl_hashtag": "#value",
            }
        )
        self.assertTrue(variable.hxl_export_include)

    def test_hxl_import_action_options(self):
        """Test different HXL import action options"""
        for action in ["field", "event", "variable", "skip"]:
            variable = self.CELVariable.create(
                {
                    "name": f"test_hxl_action_{action}",
                    "cel_accessor": f"test_hxl_action_{action}",
                    "source_type": "constant",
                    "hxl_import_action": action,
                }
            )
            self.assertEqual(variable.hxl_import_action, action)

    def test_hxl_export_include_flag(self):
        """Test HXL export include flag"""
        variable1 = self.CELVariable.create(
            {
                "name": "test_hxl_export_yes",
                "cel_accessor": "test_hxl_export_yes",
                "source_type": "constant",
                "hxl_export_include": True,
            }
        )
        variable2 = self.CELVariable.create(
            {
                "name": "test_hxl_export_no",
                "cel_accessor": "test_hxl_export_no",
                "source_type": "constant",
                "hxl_export_include": False,
            }
        )
        self.assertTrue(variable1.hxl_export_include)
        self.assertFalse(variable2.hxl_export_include)

    def test_hxl_tag_update(self):
        """Test HXL tag updates when hashtag or attributes change"""
        variable = self.CELVariable.create(
            {
                "name": "test_hxl_update",
                "cel_accessor": "test_hxl_update",
                "source_type": "constant",
                "hxl_hashtag": "#affected",
            }
        )
        self.assertEqual(variable.hxl_tag, "#affected")

        # Update attributes
        variable.write({"hxl_attributes": "+f"})
        self.assertEqual(variable.hxl_tag, "#affected+f")

        # Update hashtag
        variable.write({"hxl_hashtag": "#inneed"})
        self.assertEqual(variable.hxl_tag, "#inneed+f")

        # Clear hashtag
        variable.write({"hxl_hashtag": False})
        self.assertFalse(variable.hxl_tag)

    def test_search_by_hxl_tag(self):
        """Test searching variables by HXL tag"""
        self.CELVariable.create(
            {
                "name": "test_hxl_search1",
                "cel_accessor": "test_hxl_search1",
                "source_type": "constant",
                "hxl_hashtag": "#affected",
                "hxl_attributes": "+f",
            }
        )
        self.CELVariable.create(
            {
                "name": "test_hxl_search2",
                "cel_accessor": "test_hxl_search2",
                "source_type": "constant",
                "hxl_hashtag": "#affected",
                "hxl_attributes": "+m",
            }
        )
        self.CELVariable.create(
            {
                "name": "test_hxl_search3",
                "cel_accessor": "test_hxl_search3",
                "source_type": "constant",
                "hxl_hashtag": "#population",
            }
        )

        # Search for variables with #affected hashtag
        affected_vars = self.CELVariable.search([("hxl_hashtag", "ilike", "affected")])
        self.assertTrue(len(affected_vars) >= 2)

    def test_filter_export_variables(self):
        """Test filtering variables for export"""
        self.CELVariable.create(
            {
                "name": "test_hxl_filter1",
                "cel_accessor": "test_hxl_filter1",
                "source_type": "constant",
                "hxl_export_include": True,
            }
        )
        self.CELVariable.create(
            {
                "name": "test_hxl_filter2",
                "cel_accessor": "test_hxl_filter2",
                "source_type": "constant",
                "hxl_export_include": True,
            }
        )
        self.CELVariable.create(
            {
                "name": "test_hxl_filter3",
                "cel_accessor": "test_hxl_filter3",
                "source_type": "constant",
                "hxl_export_include": False,
            }
        )

        export_vars = self.CELVariable.search([("hxl_export_include", "=", True)])
        self.assertTrue(len(export_vars) >= 2)
