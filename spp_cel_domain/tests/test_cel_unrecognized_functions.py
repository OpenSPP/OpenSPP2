# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for unrecognized function handling in CEL translator.

These tests verify that unrecognized functions raise clear errors instead of
silently returning TRUE (which matches everything). This behavior was introduced
to prevent subtle bugs where vocabulary functions or other extensions are not
properly loaded.

Key scenarios tested:
- Unrecognized standalone functions raise NotImplementedError
- Unrecognized functions inside exists() predicates raise NotImplementedError
- Known functions are still handled correctly
- Error messages are clear and actionable
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestUnrecognizedFunctionFailure(TransactionCase):
    """Test that unrecognized functions fail instead of returning TRUE."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.translator = cls.env["spp.cel.translator"]
        cls.service = cls.env["spp.cel.service"]

        # Create a test household
        cls.household = cls.env["res.partner"].create(
            {
                "name": "Test Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Create a member
        cls.member = cls.env["res.partner"].create(
            {
                "name": "Test Member",
                "is_registrant": True,
                "is_group": False,
            }
        )

        cls.env["spp.group.membership"].create(
            {
                "group": cls.household.id,
                "individual": cls.member.id,
            }
        )

    def test_unrecognized_function_raises_error(self):
        """Test that unrecognized standalone function raises NotImplementedError."""
        expr = "totally_fake_function(r.name)"
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        with self.assertRaises(NotImplementedError) as context:
            self.translator.translate("res.partner", expr, cfg)

        self.assertIn("totally_fake_function", str(context.exception))
        self.assertIn("Unrecognized function", str(context.exception))

    def test_unrecognized_function_inside_exists_raises_error(self):
        """Test that unrecognized function inside exists() raises error.

        This is the key test case - previously this would silently return TRUE,
        causing all records to match regardless of the intended filter.
        """
        expr = "members.exists(m, fake_filter(m.name))"
        cfg = {
            "symbols": {
                "r": {"model": "res.partner"},
                "members": {
                    "relation": "rel",
                    "through": "spp.group.membership",
                    "parent": "group",
                    "link_to": "individual",
                    "child_model": "res.partner",
                    "default_domain": [("is_ended", "=", False)],
                },
            }
        }

        with self.assertRaises(NotImplementedError) as context:
            self.translator.translate("res.partner", expr, cfg)

        self.assertIn("fake_filter", str(context.exception))

    def test_unrecognized_function_in_and_condition_raises_error(self):
        """Test unrecognized function in AND condition inside exists()."""
        expr = "members.exists(m, true && unknown_func(m))"
        cfg = {
            "symbols": {
                "r": {"model": "res.partner"},
                "members": {
                    "relation": "rel",
                    "through": "spp.group.membership",
                    "parent": "group",
                    "link_to": "individual",
                    "child_model": "res.partner",
                    "default_domain": [("is_ended", "=", False)],
                },
            }
        }

        with self.assertRaises(NotImplementedError) as context:
            self.translator.translate("res.partner", expr, cfg)

        self.assertIn("unknown_func", str(context.exception))

    def test_recognized_function_age_years_still_works(self):
        """Test that recognized functions like age_years still work."""
        expr = "age_years(r.birthdate) >= 18"
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        # Should not raise an error
        plan, explain = self.translator.translate("res.partner", expr, cfg)

        self.assertIsNotNone(plan)
        self.assertIn("birthdate", explain)

    def test_recognized_function_head_still_works(self):
        """Test that the head() function still works in exists()."""
        expr = "members.exists(m, head(m))"
        cfg = {
            "symbols": {
                "r": {"model": "res.partner"},
                "members": {
                    "relation": "rel",
                    "through": "spp.group.membership",
                    "parent": "group",
                    "link_to": "individual",
                    "child_model": "res.partner",
                    "default_domain": [("is_ended", "=", False)],
                },
            },
            "roles": {"head": ["Head", "Household Head", "HoH"]},
        }

        # Should not raise an error
        plan, explain = self.translator.translate("res.partner", expr, cfg)

        self.assertIsNotNone(plan)
        self.assertIn("EXISTS", explain)

    def test_cel_service_reports_unrecognized_function_error(self):
        """Test that CEL service returns clear error for unrecognized functions."""
        result = self.service.compile_expression(
            "unknown_function(r.name)",
            profile="registry_groups",
        )

        self.assertFalse(result.get("valid"))
        self.assertIn("unknown_function", result.get("error", ""))

    def test_error_message_is_actionable(self):
        """Test that error message suggests possible causes."""
        expr = "some_vocab_function(r.field)"
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        with self.assertRaises(NotImplementedError) as context:
            self.translator.translate("res.partner", expr, cfg)

        error_msg = str(context.exception)
        # Error should suggest possible causes
        self.assertIn("module", error_msg.lower())


@tagged("post_install", "-at_install")
class TestFallbackBehaviorRemoved(TransactionCase):
    """Test that the old TRUE fallback behavior is removed.

    These tests document the previous buggy behavior and verify it's fixed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.translator = cls.env["spp.cel.translator"]

    def test_no_silent_true_for_unknown_function(self):
        """Verify unknown function doesn't silently return TRUE domain.

        Previously, unrecognized functions would return [("id", "!=", 0)] which
        matches all records. This was a bug because it caused incorrect results
        when vocabulary functions like is_female() weren't loaded.
        """
        expr = "might_be_vocab_function(r.gender_id)"
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        # Should raise error, not return TRUE
        with self.assertRaises(NotImplementedError):
            self.translator.translate("res.partner", expr, cfg)

    def test_attribute_used_as_predicate_still_works(self):
        """Test that boolean fields used as predicates still work.

        The fallback TRUE behavior should still work for non-function nodes
        like boolean fields used as predicates (e.g., m._link.is_ended).
        """
        # This tests that we didn't break legitimate uses of the fallback
        expr = "r.is_group"
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        # Should work - is_group is a boolean field
        plan, explain = self.translator.translate("res.partner", expr, cfg)

        self.assertIsNotNone(plan)
        # Should have translated to is_group = True
        self.assertIn("is_group", explain)
