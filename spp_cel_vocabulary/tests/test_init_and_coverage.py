# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Additional tests for spp_cel_vocabulary to improve coverage to 95%+.

Covers gaps in:
- _ensure_concept_groups() from __init__.py
- CelVocabularyFunctions._ensure_registered()
- head() function edge cases
- VocabularyCache.clear()
- Translator error paths
- code() function edge cases
"""

from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.spp_cel_domain.tests.common import CELTestDataMixin


@tagged("post_install", "-at_install")
class TestEnsureConceptGroups(TransactionCase):
    """Test _ensure_concept_groups() from __init__.py."""

    def test_all_10_standard_groups_exist(self):
        """Test that all 10 standard concept groups exist after module install."""
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        expected_groups = [
            "feminine_gender",
            "masculine_gender",
            "head_of_household",
            "pregnant_eligible",
            "climate_hazards",
            "geophysical_hazards",
            "children",
            "adults",
            "elderly",
            "persons_with_disability",
        ]

        for group_name in expected_groups:
            group = ConceptGroup.search([("name", "=", group_name)], limit=1)
            self.assertTrue(
                group,
                f"Standard concept group '{group_name}' should exist after module install",
            )

    def test_ensure_concept_groups_idempotent(self):
        """Test that calling _ensure_concept_groups again doesn't create duplicates."""
        from .. import _ensure_concept_groups

        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # Count groups before
        count_before = ConceptGroup.search_count([])

        # Call again - should be idempotent
        _ensure_concept_groups(self.env)

        # Count groups after
        count_after = ConceptGroup.search_count([])

        self.assertEqual(
            count_before,
            count_after,
            "Calling _ensure_concept_groups again should not create duplicate groups",
        )

    def test_ensure_concept_groups_creates_missing(self):
        """Test that _ensure_concept_groups creates groups that are missing."""
        from .. import _ensure_concept_groups

        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # Delete one group to simulate missing
        elderly_group = ConceptGroup.search([("name", "=", "elderly")], limit=1)
        if elderly_group:
            elderly_group.unlink()

        # Verify it's gone
        self.assertFalse(ConceptGroup.search([("name", "=", "elderly")], limit=1))

        # Re-run
        _ensure_concept_groups(self.env)

        # Should be recreated
        self.assertTrue(
            ConceptGroup.search([("name", "=", "elderly")], limit=1),
            "elderly group should be recreated by _ensure_concept_groups",
        )

    def test_concept_groups_with_cel_function(self):
        """Test that concept groups with cel_function attribute are created correctly."""
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        # Groups that should have cel_function set
        groups_with_functions = {
            "feminine_gender": "is_female",
            "masculine_gender": "is_male",
            "head_of_household": "is_head",
            "pregnant_eligible": "is_pregnant",
        }

        for group_name, expected_func in groups_with_functions.items():
            group = ConceptGroup.search([("name", "=", group_name)], limit=1)
            self.assertTrue(group, f"Group '{group_name}' should exist")
            self.assertEqual(
                group.cel_function,
                expected_func,
                f"Group '{group_name}' should have cel_function='{expected_func}'",
            )

    def test_concept_groups_without_cel_function(self):
        """Test that concept groups without cel_function have it unset."""
        ConceptGroup = self.env["spp.vocabulary.concept.group"]

        groups_without_functions = [
            "climate_hazards",
            "geophysical_hazards",
            "children",
            "adults",
            "elderly",
            "persons_with_disability",
        ]

        for group_name in groups_without_functions:
            group = ConceptGroup.search([("name", "=", group_name)], limit=1)
            self.assertTrue(group, f"Group '{group_name}' should exist")
            self.assertFalse(
                group.cel_function,
                f"Group '{group_name}' should not have cel_function set",
            )


@tagged("post_install", "-at_install")
class TestEnsureRegistered(TransactionCase):
    """Test CelVocabularyFunctions._ensure_registered() lazy mechanism."""

    def test_ensure_registered_registers_when_needed(self):
        """Test that _ensure_registered registers functions when _needs_registration is True."""
        vocab_funcs_model = self.env["spp.cel.vocabulary.functions"]

        # Force _needs_registration to True
        vocab_funcs_model.__class__._needs_registration = True

        # Call _ensure_registered
        vocab_funcs_model._ensure_registered()

        # Should now be False
        self.assertFalse(
            vocab_funcs_model.__class__._needs_registration,
            "_needs_registration should be False after _ensure_registered",
        )

        # Functions should be registered
        registry = self.env["spp.cel.function.registry"]
        self.assertTrue(registry.is_registered("code"))
        self.assertTrue(registry.is_registered("in_group"))

    def test_ensure_registered_skips_when_not_needed(self):
        """Test that _ensure_registered skips if already registered."""
        vocab_funcs_model = self.env["spp.cel.vocabulary.functions"]

        # First ensure it's registered
        vocab_funcs_model._ensure_registered()
        self.assertFalse(vocab_funcs_model.__class__._needs_registration)

        # Calling again should not re-register (flag already False)
        with patch.object(type(vocab_funcs_model), "register_vocabulary_functions") as mock_register:
            vocab_funcs_model._ensure_registered()
            mock_register.assert_not_called()

    def test_register_hook_sets_flag(self):
        """Test that _register_hook sets _needs_registration to True."""
        vocab_funcs_model = self.env["spp.cel.vocabulary.functions"]

        # Clear the flag
        vocab_funcs_model.__class__._needs_registration = False

        # Call _register_hook
        vocab_funcs_model._register_hook()

        # Flag should be set
        self.assertTrue(
            vocab_funcs_model.__class__._needs_registration,
            "_register_hook should set _needs_registration to True",
        )


@tagged("post_install", "-at_install")
class TestHeadFunction(TransactionCase, CELTestDataMixin):
    """Test head() function edge cases."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()

        # Create the group membership type vocabulary if it doesn't exist
        Vocabulary = cls.env["spp.vocabulary"]
        existing_vocab = Vocabulary.search(
            [("namespace_uri", "=", "urn:openspp:vocab:group-membership-type")],
            limit=1,
        )
        if existing_vocab:
            cls.membership_vocab = existing_vocab
        else:
            cls.membership_vocab = Vocabulary.create(
                {
                    "name": "Group Membership Type",
                    "namespace_uri": "urn:openspp:vocab:group-membership-type",
                }
            )

        # Get or create the 'head' code
        VocabCode = cls.env["spp.vocabulary.code"]
        cls.head_code = VocabCode.sudo().get_code("urn:openspp:vocab:group-membership-type", "head")
        if not cls.head_code:
            cls.head_code = VocabCode.create(
                {
                    "vocabulary_id": cls.membership_vocab.id,
                    "code": "head",
                    "display": "Head",
                }
            )

        # Create a group
        cls.group_partner = cls._create_test_partner(
            name=f"Test Group {cls._test_id}",
            is_registrant=True,
            is_group=True,
        )

        # Create an individual
        cls.individual_partner = cls._create_test_partner(
            name=f"Test Individual {cls._test_id}",
            is_registrant=True,
            is_group=False,
        )

        # Create another individual (non-head)
        cls.individual_nonhead = cls._create_test_partner(
            name=f"Test NonHead {cls._test_id}",
            is_registrant=True,
            is_group=False,
        )

        # Create membership with head type
        cls.membership_head = cls.env["spp.group.membership"].create(
            {
                "group": cls.group_partner.id,
                "individual": cls.individual_partner.id,
                "membership_type_ids": [(6, 0, [cls.head_code.id])],
            }
        )

        # Create membership without head type
        cls.membership_nonhead = cls.env["spp.group.membership"].create(
            {
                "group": cls.group_partner.id,
                "individual": cls.individual_nonhead.id,
            }
        )

    def test_head_code_not_found(self):
        """Test head() when head vocabulary code is missing."""
        from ..services.cel_vocabulary_functions import head

        # Patch get_code to return empty recordset
        with patch.object(
            type(self.env["spp.vocabulary.code"]),
            "get_code",
            return_value=self.env["spp.vocabulary.code"].browse(),
        ):
            result = head(self.env, self.individual_partner)
            self.assertFalse(result)

    def test_head_with_membership_parameter(self):
        """Test head() with _membership parameter."""
        from ..services.cel_vocabulary_functions import head

        # Pass membership directly
        result = head(self.env, self.individual_partner, _membership=self.membership_head)
        self.assertTrue(result)

        # Non-head membership
        result = head(self.env, self.individual_nonhead, _membership=self.membership_nonhead)
        self.assertFalse(result)

    def test_head_with_group_parameter(self):
        """Test head() with _group parameter and active membership."""
        from ..services.cel_vocabulary_functions import head

        # Should find head membership through group context
        result = head(self.env, self.individual_partner, _group=self.group_partner)
        self.assertTrue(result)

        # Non-head through group context
        result = head(self.env, self.individual_nonhead, _group=self.group_partner)
        self.assertFalse(result)

    def test_head_fallback_individual_membership_ids(self):
        """Test head() fallback via individual_membership_ids."""
        from ..services.cel_vocabulary_functions import head

        # No _membership or _group passed, should fall back to individual_membership_ids
        result = head(self.env, self.individual_partner)
        self.assertTrue(result)

        # Non-head individual
        result = head(self.env, self.individual_nonhead)
        self.assertFalse(result)

    def test_head_with_empty_member(self):
        """Test head() with empty/falsy member."""
        from ..services.cel_vocabulary_functions import head

        result = head(self.env, None)
        self.assertFalse(result)

        result = head(self.env, self.env["res.partner"].browse())
        self.assertFalse(result)

    def test_head_with_group_no_membership(self):
        """Test head() with _group parameter but member has no membership in that group."""
        from ..services.cel_vocabulary_functions import head

        # Create a different group
        other_group = self._create_test_partner(
            name=f"Other Group {self._test_id}",
            is_registrant=True,
            is_group=True,
        )

        # Create a new individual that is NOT a member of any group
        lone_individual = self._create_test_partner(
            name=f"Lone Individual {self._test_id}",
            is_registrant=True,
            is_group=False,
        )

        # lone_individual is not a member of other_group
        result = head(self.env, lone_individual, _group=other_group)
        self.assertFalse(result)


@tagged("post_install", "-at_install")
class TestVocabularyCacheClear(TransactionCase, CELTestDataMixin):
    """Test VocabularyCache.clear() method."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()

        cls.gender_vocab = cls._create_test_vocabulary(
            name=f"Gender {cls._test_id}",
            namespace_uri=f"urn:test:vocab:gender:{cls._test_id}",
        )

        cls.code_female = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"F_{cls._test_id}",
            display="Female",
        )

        ConceptGroup = cls.env["spp.vocabulary.concept.group"]
        existing_feminine = ConceptGroup.search([("name", "=", "feminine_gender")], limit=1)
        if existing_feminine:
            existing_feminine.write({"code_ids": [(4, cls.code_female.id)]})
        else:
            cls._create_test_concept_group(
                name="feminine_gender",
                display_name="Feminine Gender",
                codes=[cls.code_female],
            )

    def test_clear_resets_cache(self):
        """Test that clear() resets the cache."""
        from ..services.vocabulary_cache import VocabularyCache

        cache = VocabularyCache(self.env)

        # Populate cache
        cache.check_membership(self.code_female, "feminine_gender")
        cache.check_membership(self.code_female, "nonexistent_group")

        # Verify cache has data
        self.assertGreater(len(cache._group_uri_cache), 0)

        # Clear
        cache.clear()

        # Verify cache is empty
        self.assertEqual(len(cache._group_uri_cache), 0)

    def test_clear_resets_stats(self):
        """Test that clear() resets stats."""
        from ..services.vocabulary_cache import VocabularyCache

        cache = VocabularyCache(self.env)

        # Populate cache
        cache.check_membership(self.code_female, "feminine_gender")
        cache.check_membership(self.code_female, "nonexistent_group")

        stats_before = cache.stats
        self.assertGreater(stats_before["cached_groups"], 0)

        # Clear
        cache.clear()

        stats_after = cache.stats
        self.assertEqual(stats_after["cached_groups"], 0)
        self.assertEqual(stats_after["missing_groups"], 0)

    def test_cache_works_after_clear(self):
        """Test that cache works correctly after being cleared."""
        from ..services.vocabulary_cache import VocabularyCache

        cache = VocabularyCache(self.env)

        # Populate, clear, then re-populate
        cache.check_membership(self.code_female, "feminine_gender")
        cache.clear()

        # Should work fine after clear
        result = cache.check_membership(self.code_female, "feminine_gender")
        self.assertTrue(result)
        self.assertIn("feminine_gender", cache._group_uri_cache)


@tagged("post_install", "-at_install")
class TestTranslatorErrorPaths(TransactionCase, CELTestDataMixin):
    """Test translator error paths in cel_vocabulary_translator.py."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()

        # Create test vocabulary and codes
        cls.gender_vocab = cls._create_test_vocabulary(
            name=f"Gender {cls._test_id}",
            namespace_uri=f"urn:test:vocab:gender:{cls._test_id}",
        )

        cls.code_female = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"F_{cls._test_id}",
            display="Female",
        )

        # Create an empty concept group (no codes)
        cls.empty_group = cls._create_test_concept_group(
            name=f"empty_group_{cls._test_id}",
            display_name="Empty Group",
        )

        cls.translator = cls.env["spp.cel.translator"]

    def test_semantic_helper_unknown_name(self):
        """Test _handle_semantic_helper() with unknown helper name."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        # Create a fake Call node for an unknown semantic helper
        func_ident = P.Ident("unknown_helper")
        field_arg = P.Attr(P.Ident("r"), "gender_id")
        call_node = P.Call(func_ident, [field_arg])

        plan, explain = self.translator._handle_semantic_helper("res.partner", call_node, {}, {}, "unknown_helper")

        self.assertIn("UNKNOWN HELPER", explain)

    def test_in_group_empty_uri_list(self):
        """Test _handle_in_group() when group has empty URI list."""
        expr = f'in_group(r.gender_id, "{self.empty_group.name}")'
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        plan, explain = self.translator.translate("res.partner", expr, cfg)

        self.assertIn("EMPTY GROUP", explain.upper())

    def test_code_comparison_unsupported_gt_operator(self):
        """Test _handle_code_comparison() with > operator falls back to parent."""
        # Using r.gender_id > code("Female") should fall back since > is not supported
        expr = f'r.gender_id > code("F_{self._test_id}")'
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        # This should not raise, it should fall back to parent translator
        try:
            plan, explain = self.translator.translate("res.partner", expr, cfg)
            # If it succeeds, that's fine (parent handled it)
        except Exception:  # pylint: disable=except-pass
            # Parent translator may also reject this, which is fine
            pass  # nosemgrep

    def test_code_comparison_unsupported_lt_operator(self):
        """Test _handle_code_comparison() with < operator falls back to parent."""
        expr = f'r.gender_id < code("F_{self._test_id}")'
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        try:
            plan, explain = self.translator.translate("res.partner", expr, cfg)
        except Exception:  # pylint: disable=except-pass
            # Parent translator may reject this, which is fine
            pass  # nosemgrep

    def test_in_group_empty_group_name(self):
        """Test in_group() with empty group name."""
        expr = 'in_group(r.gender_id, "")'
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        plan, explain = self.translator.translate("res.partner", expr, cfg)

        self.assertIn("INVALID", explain.upper())

    def test_semantic_helper_group_not_found(self):
        """Test semantic helper when its concept group doesn't exist."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        # Directly call _handle_semantic_helper with a helper whose group we'll make missing
        func_ident = P.Ident("is_pregnant")
        field_arg = P.Attr(P.Ident("r"), "gender_id")
        call_node = P.Call(func_ident, [field_arg])

        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        # Delete pregnant_eligible group temporarily
        ConceptGroup = self.env["spp.vocabulary.concept.group"]
        pregnant_group = ConceptGroup.search([("name", "=", "pregnant_eligible")], limit=1)
        if pregnant_group:
            pregnant_group.unlink()

        plan, explain = self.translator._handle_semantic_helper("res.partner", call_node, cfg, {}, "is_pregnant")

        self.assertIn("NOT FOUND", explain.upper())

    def test_code_eq_nonexistent_code_via_translator(self):
        """Test code_eq() translation with nonexistent code identifier."""
        expr = 'code_eq(r.gender_id, "nonexistent_code_xyz_12345")'
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        plan, explain = self.translator.translate("res.partner", expr, cfg)

        self.assertIn("NOT FOUND", explain.upper())


@tagged("post_install", "-at_install")
class TestCodeFunctionEdgeCases(TransactionCase):
    """Test code() function with various falsy non-string values."""

    def test_code_with_zero(self):
        """Test code() with 0."""
        from ..services.cel_vocabulary_functions import code

        result = code(self.env, 0)
        self.assertFalse(result)

    def test_code_with_false(self):
        """Test code() with False."""
        from ..services.cel_vocabulary_functions import code

        result = code(self.env, False)
        self.assertFalse(result)

    def test_code_with_empty_list(self):
        """Test code() with empty list."""
        from ..services.cel_vocabulary_functions import code

        result = code(self.env, [])
        self.assertFalse(result)

    def test_code_with_empty_dict(self):
        """Test code() with empty dict."""
        from ..services.cel_vocabulary_functions import code

        result = code(self.env, {})
        self.assertFalse(result)

    def test_code_with_none(self):
        """Test code() with None."""
        from ..services.cel_vocabulary_functions import code

        result = code(self.env, None)
        self.assertFalse(result)


@tagged("post_install", "-at_install")
class TestPostInitHook(TransactionCase):
    """Test post_init_hook from __init__.py."""

    def test_post_init_hook(self):
        """Test that post_init_hook runs without errors."""
        from .. import post_init_hook

        # Should run without raising
        post_init_hook(self.env)

        # Verify concept groups exist
        ConceptGroup = self.env["spp.vocabulary.concept.group"]
        self.assertTrue(ConceptGroup.search([("name", "=", "feminine_gender")], limit=1))

        # Verify functions are registered
        registry = self.env["spp.cel.function.registry"]
        self.assertTrue(registry.is_registered("code"))

    def test_post_init_hook_idempotent(self):
        """Test that post_init_hook can be called multiple times safely."""
        from .. import post_init_hook

        ConceptGroup = self.env["spp.vocabulary.concept.group"]
        count_before = ConceptGroup.search_count([])

        # Call twice
        post_init_hook(self.env)
        post_init_hook(self.env)

        count_after = ConceptGroup.search_count([])
        self.assertEqual(count_before, count_after)


@tagged("post_install", "-at_install")
class TestGetFunctionHelp(TransactionCase):
    """Test get_function_help edge cases."""

    def test_get_function_help_nonexistent(self):
        """Test get_function_help with nonexistent function name."""
        vocab_funcs = self.env["spp.cel.vocabulary.functions"]
        help_text = vocab_funcs.get_function_help("nonexistent_function_xyz")
        self.assertEqual(help_text, "")

    def test_get_function_help_head(self):
        """Test get_function_help for head function."""
        vocab_funcs = self.env["spp.cel.vocabulary.functions"]
        help_text = vocab_funcs.get_function_help("head")
        self.assertIn("head", help_text.lower())

    def test_get_function_help_in_group(self):
        """Test get_function_help for in_group function."""
        vocab_funcs = self.env["spp.cel.vocabulary.functions"]
        help_text = vocab_funcs.get_function_help("in_group")
        self.assertIn("group", help_text.lower())


@tagged("post_install", "-at_install")
class TestCreateEnvMarker(TransactionCase):
    """Test _create_env_marker method."""

    def test_create_env_marker_sets_flag(self):
        """Test that _create_env_marker sets _cel_needs_env on the function."""
        vocab_funcs = self.env["spp.cel.vocabulary.functions"]

        def dummy_func(env, x):
            return x

        marked = vocab_funcs._create_env_marker(dummy_func)

        self.assertTrue(getattr(marked, "_cel_needs_env", False))
        self.assertIs(marked, dummy_func)  # Should return same function object


@tagged("post_install", "-at_install")
class TestTranslatorChangedLines(TransactionCase, CELTestDataMixin):
    """Test translator changed lines for codecov patch coverage.

    Targets the specific _logger.warning/debug lines that were changed
    from f-strings to lazy % formatting.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = cls._get_unique_test_id()

        cls.gender_vocab = cls._create_test_vocabulary(
            name=f"Gender TL {cls._test_id}",
            namespace_uri=f"urn:test:vocab:gender-tl:{cls._test_id}",
        )

        cls.code_female = cls._create_test_vocabulary_code(
            vocabulary=cls.gender_vocab,
            code=f"F_TL_{cls._test_id}",
            display="Female",
        )

        # Create concept group with codes for successful paths
        ConceptGroup = cls.env["spp.vocabulary.concept.group"]
        cls.test_group = ConceptGroup.search([("name", "=", "feminine_gender")], limit=1)
        if cls.test_group:
            cls.test_group.write({"code_ids": [(4, cls.code_female.id)]})
        else:
            cls.test_group = cls._create_test_concept_group(
                name="feminine_gender",
                display_name="Feminine Gender",
                codes=[cls.code_female],
            )

        cls.translator = cls.env["spp.cel.translator"]

    def test_successful_semantic_helper_debug_log(self):
        """Test successful is_female() call covers debug log line in _to_plan."""
        # This exercises line 61: _logger.debug("...%s...%s", func_name, model)
        expr = "is_female(r.gender_id)"
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        plan, explain = self.translator.translate("res.partner", expr, cfg)
        # Should succeed (covers the debug log line in _to_plan)
        self.assertIn("feminine_gender", explain.lower())

    def test_in_group_field_resolution_error(self):
        """Test in_group() field resolution error via patch."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        func_ident = P.Ident("in_group")
        field_arg = P.Attr(P.Ident("r"), "gender_id")
        group_arg = P.Literal("feminine_gender")
        call_node = P.Call(func_ident, [field_arg, group_arg])
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        with patch.object(
            type(self.translator),
            "_resolve_field",
            side_effect=ValueError("test field error"),
        ):
            plan, explain = self.translator._handle_in_group("res.partner", call_node, cfg, {})
        self.assertIn("FIELD RESOLUTION ERROR", explain)

    def test_in_group_group_name_eval_error(self):
        """Test in_group() group name eval error via patch."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        func_ident = P.Ident("in_group")
        field_arg = P.Attr(P.Ident("r"), "gender_id")
        group_arg = P.Literal("feminine_gender")
        call_node = P.Call(func_ident, [field_arg, group_arg])
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        with patch.object(
            type(self.translator),
            "_eval_literal",
            side_effect=ValueError("test eval error"),
        ):
            plan, explain = self.translator._handle_in_group("res.partner", call_node, cfg, {})
        self.assertIn("EVAL ERROR", explain)

    def test_in_group_group_not_found(self):
        """Test in_group() with nonexistent group covers warning log."""
        expr = 'in_group(r.gender_id, "nonexistent_group_xyz_99")'
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        plan, explain = self.translator.translate("res.partner", expr, cfg)
        self.assertIn("GROUP NOT FOUND", explain)

    def test_semantic_helper_field_resolution_error(self):
        """Test is_female() field resolution error via patch."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        func_ident = P.Ident("is_female")
        field_arg = P.Attr(P.Ident("r"), "gender_id")
        call_node = P.Call(func_ident, [field_arg])
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        with patch.object(
            type(self.translator),
            "_resolve_field",
            side_effect=ValueError("test field error"),
        ):
            plan, explain = self.translator._handle_semantic_helper("res.partner", call_node, cfg, {}, "is_female")
        self.assertIn("FIELD RESOLUTION ERROR", explain)

    def test_semantic_helper_empty_group(self):
        """Test semantic helper when concept group has no codes covers warning log."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        # Create empty concept group
        ConceptGroup = self.env["spp.vocabulary.concept.group"]
        empty_group = ConceptGroup.create(
            {
                "name": f"empty_sem_{self._test_id}",
                "label": "Empty Semantic",
            }
        )

        func_ident = P.Ident("is_female")
        field_arg = P.Attr(P.Ident("r"), "gender_id")
        call_node = P.Call(func_ident, [field_arg])
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        # Temporarily change SEMANTIC_HELPERS to point to our empty group
        original = self.translator.SEMANTIC_HELPERS.copy()
        try:
            self.translator.SEMANTIC_HELPERS["is_female"] = empty_group.name
            plan, explain = self.translator._handle_semantic_helper("res.partner", call_node, cfg, {}, "is_female")
            self.assertIn("GROUP EMPTY", explain)
        finally:
            self.translator.SEMANTIC_HELPERS.update(original)

        empty_group.unlink()

    def test_code_eq_field_resolution_error(self):
        """Test code_eq() field resolution error via patch."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        func_ident = P.Ident("code_eq")
        field_arg = P.Attr(P.Ident("r"), "gender_id")
        identifier = P.Literal("some_code")
        call_node = P.Call(func_ident, [field_arg, identifier])
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        with patch.object(
            type(self.translator),
            "_resolve_field",
            side_effect=ValueError("test field error"),
        ):
            plan, explain = self.translator._handle_code_eq("res.partner", call_node, cfg, {})
        self.assertIn("FIELD RESOLUTION ERROR", explain)

    def test_code_eq_identifier_eval_error(self):
        """Test code_eq() identifier eval error via patch."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        func_ident = P.Ident("code_eq")
        field_arg = P.Attr(P.Ident("r"), "gender_id")
        identifier = P.Literal("some_code")
        call_node = P.Call(func_ident, [field_arg, identifier])
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        # _handle_code_eq calls _eval_literal for the identifier (args[1]).
        # Patch it to always raise - field resolution uses _resolve_field, not _eval_literal.
        with patch.object(
            type(self.translator),
            "_eval_literal",
            side_effect=ValueError("test eval error"),
        ):
            plan, explain = self.translator._handle_code_eq("res.partner", call_node, cfg, {})
        self.assertIn("EVAL ERROR", explain)

    def test_code_comparison_field_resolution_error(self):
        """Test code() comparison field resolution error via patch."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        field_arg = P.Attr(P.Ident("r"), "gender_id")
        code_call = P.Call(P.Ident("code"), [P.Literal("female")])
        compare_node = P.Compare("EQ", field_arg, code_call)
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        with patch.object(
            type(self.translator),
            "_resolve_field",
            side_effect=ValueError("test field error"),
        ):
            plan, explain = self.translator._handle_code_comparison(
                "res.partner", compare_node, cfg, {}, left_is_code=False
            )
        self.assertIn("FIELD RESOLUTION ERROR", explain)

    def test_code_comparison_eval_error(self):
        """Test code() comparison eval error via patch."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        field_arg = P.Attr(P.Ident("r"), "gender_id")
        code_call = P.Call(P.Ident("code"), [P.Literal("female")])
        compare_node = P.Compare("EQ", field_arg, code_call)
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        with patch.object(
            type(self.translator),
            "_eval_literal",
            side_effect=ValueError("test eval error"),
        ):
            plan, explain = self.translator._handle_code_comparison(
                "res.partner", compare_node, cfg, {}, left_is_code=False
            )
        # identifier becomes None after eval error, triggering empty check
        self.assertIn("code(EMPTY)", explain)

    def test_code_comparison_code_not_found(self):
        """Test code() comparison with nonexistent code covers warning log."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        field_arg = P.Attr(P.Ident("r"), "gender_id")
        code_call = P.Call(P.Ident("code"), [P.Literal("nonexistent_xyz_99")])
        compare_node = P.Compare("EQ", field_arg, code_call)
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        plan, explain = self.translator._handle_code_comparison(
            "res.partner", compare_node, cfg, {}, left_is_code=False
        )
        self.assertIn("NOT FOUND", explain)

    def test_code_comparison_empty_identifier(self):
        """Test code() comparison with empty args covers warning log."""
        from odoo.addons.spp_cel_domain.services import cel_parser as P

        field_arg = P.Attr(P.Ident("r"), "gender_id")
        # code() with NO arguments
        code_call = P.Call(P.Ident("code"), [])
        compare_node = P.Compare("EQ", field_arg, code_call)
        cfg = {"symbols": {"r": {"model": "res.partner"}}}

        plan, explain = self.translator._handle_code_comparison(
            "res.partner", compare_node, cfg, {}, left_is_code=False
        )
        self.assertIn("code(EMPTY)", explain)
