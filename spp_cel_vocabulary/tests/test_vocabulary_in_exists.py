# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for vocabulary functions inside exists() predicates.

These tests verify that vocabulary functions like is_female(), is_male(),
in_group() work correctly when used inside members.exists() predicates.

This was a bug where vocabulary functions inside exists() would return TRUE
instead of proper domain filters, causing incorrect eligibility results.

Key scenarios tested:
- is_female(m.gender_id) inside members.exists()
- is_male(m.gender_id) inside members.exists()
- Combined predicates like head(m) && is_female(m.gender_id)
- The full is_female_headed pattern
"""

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_cel_domain.tests.common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestVocabularyInExists(TransactionCase, CELTestDataMixin):
    """Test vocabulary functions inside exists() predicates."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.translator = cls.env["spp.cel.translator"]
        cls.service = cls.env["spp.cel.service"]

        # Create test vocabulary
        cls.gender_vocab = cls._create_test_vocabulary(
            name=f"Gender Test {cls._test_id}",
            namespace_uri=f"urn:test:vocab:gender:exists:{cls._test_id}",
        )

        # Create gender codes
        cls.code_male = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"M_{cls._test_id}",
            display="Male",
        )

        cls.code_female = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"F_{cls._test_id}",
            display="Female",
        )

        # Create or get concept groups with standard names (no test_id suffix)
        # These names must match SEMANTIC_HELPERS in CelVocabularyTranslator
        cls.group_feminine = cls.env["spp.vocabulary.concept.group"].search(
            [
                ("name", "=", "feminine_gender"),
            ],
            limit=1,
        )
        if not cls.group_feminine:
            cls.group_feminine = cls.env["spp.vocabulary.concept.group"].create(
                {
                    "name": "feminine_gender",
                    "display_name": "Feminine Gender",
                    "cel_function": "is_female",
                }
            )
        # Add our test code to the group
        cls.group_feminine.write(
            {
                "code_ids": [(4, cls.code_female.id)],
            }
        )

        cls.group_masculine = cls.env["spp.vocabulary.concept.group"].search(
            [
                ("name", "=", "masculine_gender"),
            ],
            limit=1,
        )
        if not cls.group_masculine:
            cls.group_masculine = cls.env["spp.vocabulary.concept.group"].create(
                {
                    "name": "masculine_gender",
                    "display_name": "Masculine Gender",
                    "cel_function": "is_male",
                }
            )
        # Add our test code to the group
        cls.group_masculine.write(
            {
                "code_ids": [(4, cls.code_male.id)],
            }
        )

        # Create household with head membership type
        rel_vocab = cls._create_test_vocabulary(
            name=f"Relationship {cls._test_id}",
            namespace_uri=f"urn:test:vocab:relationship:{cls._test_id}",
        )
        cls.head_type = cls._create_test_vocabulary_code(
            vocabulary=rel_vocab,
            code=f"HEAD_{cls._test_id}",
            display="Head",
        )

        # Standard config for exists
        cls.exists_cfg = {
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

        # Register vocabulary functions
        cls.env["spp.cel.vocabulary.functions"].register_vocabulary_functions()

    def test_is_female_inside_exists_translates_correctly(self):
        """Test that is_female(m.gender_id) inside exists() creates proper domain.

        This was the bug - is_female would return TRUE instead of a domain
        checking gender_id.uri or gender_id.reference_uri.
        """
        from odoo.addons.spp_cel_domain.models.cel_queryplan import ExistsThrough, LeafDomain

        expr = "members.exists(m, is_female(m.gender_id))"

        plan, explain = self.translator.translate("res.partner", expr, self.exists_cfg)

        # Verify we have an ExistsThrough plan
        self.assertIsInstance(plan, ExistsThrough, "Should create ExistsThrough plan")

        # Check that child plan is a proper gender domain, not TRUE fallback
        child_plan = plan.child_plan
        self.assertIsInstance(child_plan, LeafDomain, "Child plan should be LeafDomain")

        # Verify domain is NOT the TRUE fallback
        self.assertNotEqual(
            child_plan.domain, [("id", "!=", 0)], "Should create actual gender domain, not TRUE fallback"
        )

        # Verify domain checks gender_id.uri or gender_id.reference_uri
        domain_str = str(child_plan.domain)
        self.assertTrue(
            "gender_id.uri" in domain_str or "gender_id.reference_uri" in domain_str,
            f"Domain should check gender_id.uri or gender_id.reference_uri, got: {child_plan.domain}",
        )

        # Verify explain mentions the semantic helper or group
        self.assertTrue(
            "feminine_gender" in explain.lower() or "is_female" in explain.lower(),
            f"Explain should mention feminine_gender or is_female, got: {explain}",
        )

    def test_is_male_inside_exists_translates_correctly(self):
        """Test that is_male(m.gender_id) inside exists() creates proper domain."""
        from odoo.addons.spp_cel_domain.models.cel_queryplan import ExistsThrough, LeafDomain

        expr = "members.exists(m, is_male(m.gender_id))"

        plan, explain = self.translator.translate("res.partner", expr, self.exists_cfg)

        # Verify we have an ExistsThrough plan
        self.assertIsInstance(plan, ExistsThrough, "Should create ExistsThrough plan")

        # Check that child plan is a proper gender domain, not TRUE fallback
        child_plan = plan.child_plan
        self.assertIsInstance(child_plan, LeafDomain, "Child plan should be LeafDomain")

        # Verify domain is NOT the TRUE fallback
        self.assertNotEqual(
            child_plan.domain, [("id", "!=", 0)], "Should create actual gender domain, not TRUE fallback"
        )

        # Verify domain checks gender_id fields
        domain_str = str(child_plan.domain)
        self.assertTrue("gender_id" in domain_str, f"Domain should check gender_id, got: {child_plan.domain}")

    def test_combined_head_and_is_female(self):
        """Test head(m) && is_female(m.gender_id) pattern.

        This is the pattern used in is_female_headed variable.
        """
        expr = "members.exists(m, head(m) && is_female(m.gender_id))"

        plan, explain = self.translator.translate("res.partner", expr, self.exists_cfg)

        # Both parts should be in the explain
        self.assertIn("membership", explain.lower())  # from head()
        # Should have something about gender/feminine
        self.assertTrue(
            "gender" in explain.lower() or "feminine" in explain.lower() or "is_female" in explain.lower(),
            f"Expected gender-related explain in: {explain}",
        )

        # Should NOT have (TRUE) as the gender part
        # The old bug would produce: "... AND (TRUE)"
        self.assertNotIn("AND (TRUE)", explain.upper())

    def test_in_group_inside_exists(self):
        """Test in_group() function inside exists()."""
        expr = 'members.exists(m, in_group(m.gender_id, "feminine_gender"))'

        plan, explain = self.translator.translate("res.partner", expr, self.exists_cfg)

        self.assertIn("feminine_gender", explain.lower())
        self.assertNotIn("AND (TRUE)", explain.upper())

    def test_semantic_helper_creates_domain_not_true(self):
        """Verify semantic helpers create actual domains, not TRUE fallback.

        This test ensures the fix for the bug where vocabulary functions
        inside exists() were returning TRUE ([("id", "!=", 0)]) instead of
        proper domain filters checking vocabulary code URIs.
        """
        from odoo.addons.spp_cel_domain.models.cel_queryplan import ExistsThrough, LeafDomain

        expr = "members.exists(m, is_female(m.gender_id))"

        plan, explain = self.translator.translate("res.partner", expr, self.exists_cfg)

        # The plan should be ExistsThrough with a child_plan that has a domain
        # checking gender_id.uri or gender_id.reference_uri
        self.assertIsNotNone(plan)
        self.assertIsInstance(plan, ExistsThrough, "Should create ExistsThrough plan")

        # Check child plan structure
        child_plan = getattr(plan, "child_plan", None)
        self.assertIsNotNone(child_plan, "ExistsThrough should have child_plan")
        self.assertIsInstance(child_plan, LeafDomain, "Child plan should be LeafDomain")

        # The critical check: domain should NOT be the TRUE fallback
        domain = getattr(child_plan, "domain", [])
        self.assertNotEqual(
            domain, [("id", "!=", 0)], "is_female should create actual domain checking gender_id.uri, not TRUE fallback"
        )

        # Verify the domain actually checks gender_id fields
        domain_str = str(domain)
        self.assertTrue(
            "gender_id.uri" in domain_str or "gender_id.reference_uri" in domain_str,
            f"Domain should check gender_id URI fields, got: {domain}",
        )

        # Verify it's checking membership in a code list (should have "in" operator)
        self.assertIn("in", domain_str, f"Domain should use 'in' operator to check code membership, got: {domain}")

    def test_function_registry_skips_variable_references(self):
        """Regression test: function registry should skip functions with variable refs.

        This ensures that vocabulary functions used inside exists() predicates
        with variable references (like m.gender_id) are handled by the vocabulary
        translator's domain generation, not by the function registry's literal evaluation.

        The bug was that the function registry would try to evaluate m.gender_id as
        a literal, pass an AST node to the function, and return TRUE as a fallback.
        """
        from odoo.addons.spp_cel_domain.models.cel_queryplan import ExistsThrough, LeafDomain

        # Test multiple vocabulary functions to ensure the fix works for all
        test_cases = [
            ("members.exists(m, is_female(m.gender_id))", "gender_id"),
            ("members.exists(m, is_male(m.gender_id))", "gender_id"),
            ('members.exists(m, in_group(m.gender_id, "feminine_gender"))', "gender_id"),
        ]

        for expr, expected_field in test_cases:
            with self.subTest(expr=expr):
                plan, explain = self.translator.translate("res.partner", expr, self.exists_cfg)

                # Verify proper plan structure
                self.assertIsInstance(plan, ExistsThrough, f"Expression: {expr}")
                child_plan = plan.child_plan
                self.assertIsInstance(child_plan, LeafDomain, f"Expression: {expr}")

                # Critical: domain should NOT be TRUE fallback
                self.assertNotEqual(
                    child_plan.domain, [("id", "!=", 0)], f"Expression '{expr}' should not use TRUE fallback"
                )

                # Domain should reference the expected field
                domain_str = str(child_plan.domain)
                self.assertIn(
                    expected_field, domain_str, f"Expression '{expr}' domain should reference {expected_field}"
                )


@tagged("post_install", "-at_install")
class TestIsFemaleHeadedIntegration(TransactionCase, CELTestDataMixin):
    """End-to-end integration test for is_female_headed pattern.

    This tests the complete flow from CEL expression to actual record matching.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()
        cls.service = cls.env["spp.cel.service"]

        # Create vocabulary
        cls.gender_vocab = cls._create_test_vocabulary(
            name=f"Gender Integrated {cls._test_id}",
            namespace_uri=f"urn:test:vocab:gender:integrated:{cls._test_id}",
        )

        cls.code_male = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"M_{cls._test_id}",
            display="Male",
        )

        cls.code_female = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"F_{cls._test_id}",
            display="Female",
        )

        # Create or get concept groups with standard names (no test_id suffix)
        # These names must match SEMANTIC_HELPERS in CelVocabularyTranslator
        cls.group_feminine = cls.env["spp.vocabulary.concept.group"].search(
            [
                ("name", "=", "feminine_gender"),
            ],
            limit=1,
        )
        if not cls.group_feminine:
            cls.group_feminine = cls.env["spp.vocabulary.concept.group"].create(
                {
                    "name": "feminine_gender",
                    "display_name": "Feminine Gender",
                    "cel_function": "is_female",
                }
            )
        # Add our test code to the group
        cls.group_feminine.write(
            {
                "code_ids": [(4, cls.code_female.id)],
            }
        )

        cls.group_masculine = cls.env["spp.vocabulary.concept.group"].search(
            [
                ("name", "=", "masculine_gender"),
            ],
            limit=1,
        )
        if not cls.group_masculine:
            cls.group_masculine = cls.env["spp.vocabulary.concept.group"].create(
                {
                    "name": "masculine_gender",
                    "display_name": "Masculine Gender",
                    "cel_function": "is_male",
                }
            )
        # Add our test code to the group
        cls.group_masculine.write(
            {
                "code_ids": [(4, cls.code_male.id)],
            }
        )

        # Create head membership type
        rel_vocab = cls._create_test_vocabulary(
            name=f"Relationship Type {cls._test_id}",
            namespace_uri=f"urn:test:vocab:relationship:{cls._test_id}",
        )

        cls.head_type = cls._create_test_vocabulary_code(
            vocabulary=rel_vocab,
            code=f"HEAD_{cls._test_id}",
            display="Head",
        )

        # Create test households
        # Household 1: Female head (should match is_female_headed)
        cls.hh_female_head = cls.env["res.partner"].create(
            {
                "name": "Female-Headed Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cls.female_head = cls.env["res.partner"].create(
            {
                "name": "Jane Doe (Female Head)",
                "is_registrant": True,
                "is_group": False,
                "gender_id": cls.code_female.id,
            }
        )

        cls.env["spp.group.membership"].create(
            {
                "group": cls.hh_female_head.id,
                "individual": cls.female_head.id,
                "membership_type_ids": [(6, 0, [cls.head_type.id])],
            }
        )

        # Household 2: Male head (should NOT match is_female_headed)
        cls.hh_male_head = cls.env["res.partner"].create(
            {
                "name": "Male-Headed Household",
                "is_registrant": True,
                "is_group": True,
            }
        )

        cls.male_head = cls.env["res.partner"].create(
            {
                "name": "John Doe (Male Head)",
                "is_registrant": True,
                "is_group": False,
                "gender_id": cls.code_male.id,
            }
        )

        cls.env["spp.group.membership"].create(
            {
                "group": cls.hh_male_head.id,
                "individual": cls.male_head.id,
                "membership_type_ids": [(6, 0, [cls.head_type.id])],
            }
        )

        # Register vocabulary functions
        cls.env["spp.cel.vocabulary.functions"].register_vocabulary_functions()

    def test_is_female_headed_expression_compiles(self):
        """Test that the is_female_headed expression compiles successfully."""
        result = self.service.compile_expression(
            "members.exists(m, head(m) && is_female(m.gender_id))",
            profile="registry_groups",
            limit=100,
        )

        self.assertTrue(result.get("valid"), f"Expression should be valid, got error: {result.get('error')}")
        self.assertIn("EXISTS", result.get("explain", "").upper())

    def test_is_female_headed_matches_female_headed_household(self):
        """Test that female-headed household is matched correctly."""
        result = self.service.compile_expression(
            "members.exists(m, head(m) && is_female(m.gender_id))",
            profile="registry_groups",
            base_domain=[("id", "in", [self.hh_female_head.id, self.hh_male_head.id])],
            limit=100,
        )

        self.assertTrue(result.get("valid"), f"Error: {result.get('error')}")

        # Female-headed household should be in results
        ids = result.get("ids", [])
        self.assertIn(self.hh_female_head.id, ids, f"Female-headed household should match. Got IDs: {ids}")

    def test_is_female_headed_excludes_male_headed_household(self):
        """Test that male-headed household is NOT matched."""
        result = self.service.compile_expression(
            "members.exists(m, head(m) && is_female(m.gender_id))",
            profile="registry_groups",
            base_domain=[("id", "in", [self.hh_female_head.id, self.hh_male_head.id])],
            limit=100,
        )

        self.assertTrue(result.get("valid"), f"Error: {result.get('error')}")

        # Male-headed household should NOT be in results
        ids = result.get("ids", [])
        self.assertNotIn(self.hh_male_head.id, ids, f"Male-headed household should NOT match. Got IDs: {ids}")

    def test_correct_count_for_female_headed(self):
        """Test that count is correct for female-headed filter."""
        result = self.service.compile_expression(
            "members.exists(m, head(m) && is_female(m.gender_id))",
            profile="registry_groups",
            base_domain=[("id", "in", [self.hh_female_head.id, self.hh_male_head.id])],
            limit=100,
        )

        self.assertTrue(result.get("valid"), f"Error: {result.get('error')}")

        # Should match exactly 1 household (the female-headed one)
        self.assertEqual(
            result.get("count"), 1, f"Should match exactly 1 female-headed household, got {result.get('count')}"
        )


@tagged("post_install", "-at_install")
class TestVocabularyTranslatorInheritance(TransactionCase):
    """Test that vocabulary translator is properly inherited.

    These tests verify that the Odoo model inheritance is working correctly
    and the vocabulary translator's _to_plan is being called.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.translator = cls.env["spp.cel.translator"]

        # Ensure concept groups exist
        cls.env["spp.vocabulary.concept.group"].search(
            [
                ("name", "=", "feminine_gender"),
            ]
        ) or cls.env["spp.vocabulary.concept.group"].create(
            {
                "name": "feminine_gender",
                "display_name": "Feminine Gender",
            }
        )

    def test_translator_has_vocabulary_methods(self):
        """Test that translator has vocabulary-specific methods."""
        # These methods come from CelVocabularyTranslator
        self.assertTrue(
            hasattr(self.translator, "_handle_semantic_helper"),
            "Translator should have _handle_semantic_helper from vocabulary extension",
        )
        self.assertTrue(
            hasattr(self.translator, "_handle_in_group"),
            "Translator should have _handle_in_group from vocabulary extension",
        )

    def test_semantic_helpers_constant_is_available(self):
        """Test that SEMANTIC_HELPERS mapping is available."""
        self.assertTrue(
            hasattr(self.translator, "SEMANTIC_HELPERS"), "Translator should have SEMANTIC_HELPERS constant"
        )

        helpers = getattr(self.translator, "SEMANTIC_HELPERS", {})
        self.assertIn("is_female", helpers)
        self.assertIn("is_male", helpers)
        self.assertEqual(helpers["is_female"], "feminine_gender")
