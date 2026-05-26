# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase


class TestDemoPrograms(TransactionCase):
    """Test demo programs definitions.

    The demo programs use activated registry variables for CEL expressions:
    - Universal Child Grant: child_count variable
    - Conditional Child Grant: members.exists() for first 1,000 days
    - Elderly Social Pension: age + retirement_age variables
    - Emergency Relief Fund: dependency_ratio, is_female_headed, elderly_count
    - Cash Transfer Program: hh_total_income, poverty_line, hh_size
    - Food Assistance: Simple inline CEL (r.active)
    """

    def test_get_all_demo_programs(self):
        """Test that all 6 demo programs are returned."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        programs = demo_programs.get_all_demo_programs()
        self.assertIsInstance(programs, list)
        self.assertEqual(len(programs), 6, "Expected exactly 6 demo programs")

        # Check expected programs exist (V3 names)
        program_names = [p["name"] for p in programs]
        self.assertIn("Universal Child Grant", program_names)
        self.assertIn("Conditional Child Grant", program_names)
        self.assertIn("Elderly Social Pension", program_names)
        self.assertIn("Emergency Relief Fund", program_names)
        self.assertIn("Cash Transfer Program", program_names)
        self.assertIn("Food Assistance", program_names)

    def test_get_demo_program_by_id(self):
        """Test getting a program by ID."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        program = demo_programs.get_demo_program_by_id("universal_child_grant")
        self.assertIsNotNone(program)
        self.assertEqual(program["name"], "Universal Child Grant")

        # Test non-existent program
        program = demo_programs.get_demo_program_by_id("nonexistent")
        self.assertIsNone(program)

    def test_get_demo_program_by_name(self):
        """Test getting a program by name."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        program = demo_programs.get_demo_program_by_name("Cash Transfer Program")
        self.assertIsNotNone(program)
        self.assertEqual(program["id"], "cash_transfer_program")

    def test_get_programs_for_story(self):
        """Test getting programs for a specific story."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        # Carlos/Elena Morales should be in Universal Child Grant
        programs = demo_programs.get_programs_for_story("carlos_elena_morales")
        self.assertGreater(len(programs), 0)
        program_names = [p["name"] for p in programs]
        self.assertIn("Universal Child Grant", program_names)

        # Rosa Garcia should be in multiple programs (Elderly Pension + Food)
        programs = demo_programs.get_programs_for_story("rosa_garcia")
        self.assertGreaterEqual(len(programs), 2)

    def test_get_story_enrollments(self):
        """Test getting enrollment details for a story."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        # Carlos/Elena Morales enrollment details
        enrollments = demo_programs.get_story_enrollments("carlos_elena_morales")
        self.assertIsInstance(enrollments, list)
        self.assertGreater(len(enrollments), 0)

        enrollment = enrollments[0]
        self.assertEqual(enrollment["program"], "Universal Child Grant")
        self.assertIn("enrolled_days_back", enrollment)
        self.assertIn("payments", enrollment)

        # Test non-existent story
        enrollments = demo_programs.get_story_enrollments("nonexistent")
        self.assertEqual(enrollments, [])

    def test_program_definitions_have_required_fields(self):
        """Test that all programs have required fields."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        required_fields = ["id", "name", "target_type"]

        for program in demo_programs.get_all_demo_programs():
            for field in required_fields:
                self.assertIn(
                    field,
                    program,
                    f"Program '{program.get('name', 'unknown')}' missing required field '{field}'",
                )

    def test_story_program_alignment(self):
        """Test that stories reference existing programs."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        all_program_names = [p["name"] for p in demo_programs.get_all_demo_programs()]

        for story_id, enrollments in demo_programs.STORY_ENROLLMENTS.items():
            for enrollment in enrollments:
                program_name = enrollment.get("program")
                self.assertIn(
                    program_name,
                    all_program_names,
                    f"Story '{story_id}' references unknown program '{program_name}'",
                )

    # ═══════════════════════════════════════════════════════════════════════
    # CEL EXPRESSION VALIDATION TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_all_programs_have_cel_expressions(self):
        """Test that all demo programs have CEL expressions for eligibility."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        for program in demo_programs.get_all_demo_programs():
            self.assertIn(
                "cel_expression",
                program,
                f"Program '{program['name']}' missing CEL expression",
            )
            self.assertIsInstance(
                program["cel_expression"],
                str,
                f"Program '{program['name']}' CEL expression must be string",
            )
            self.assertGreater(
                len(program["cel_expression"]),
                0,
                f"Program '{program['name']}' has empty CEL expression",
            )

    def test_cel_expression_syntax_basic(self):
        """Test CEL expressions have valid basic syntax (balanced parens, quotes)."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        for program in demo_programs.get_all_demo_programs():
            expr = program.get("cel_expression", "")
            program_name = program["name"]

            # Check balanced parentheses
            paren_count = expr.count("(") - expr.count(")")
            self.assertEqual(
                paren_count,
                0,
                f"Program '{program_name}' has unbalanced parentheses in CEL: {expr}",
            )

            # Check balanced single quotes
            quote_count = expr.count("'")
            self.assertEqual(
                quote_count % 2,
                0,
                f"Program '{program_name}' has unbalanced quotes in CEL: {expr}",
            )

    def test_cel_expressions_use_documented_features(self):
        """Test CEL expressions use the documented feature set.

        The demo programs demonstrate these CEL patterns using activated variables:
        - Field access: r.field_name (e.g., r.is_group, r.active)
        - Variables: child_count, age, hh_size, hh_total_income
        - Computed variables: dependency_ratio, is_female_headed
        - Constants: poverty_line, retirement_age
        - Boolean operators: and, or
        - Comparison: ==, >=, <, >
        """
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        # Track which features are used across all programs
        feature_usage = {
            "r.": False,  # Record field access
            "child_count": False,  # Aggregate variable
            "age": False,  # Computed variable
            "hh_size": False,  # Aggregate variable
            "hh_total_income": False,  # Aggregate variable
            "dependency_ratio": False,  # Computed variable
            "poverty_line": False,  # Constant
            "retirement_age": False,  # Constant
            " and ": False,  # Boolean AND
            " or ": False,  # Boolean OR
            " >= ": False,  # Greater than or equal
            " < ": False,  # Less than
            " > ": False,  # Greater than
        }

        for program in demo_programs.get_all_demo_programs():
            expr = program.get("cel_expression", "")
            for feature in feature_usage:
                if feature in expr:
                    feature_usage[feature] = True

        # Verify key features are demonstrated
        self.assertTrue(
            feature_usage["r."],
            "No program demonstrates 'r.' field access",
        )
        self.assertTrue(
            feature_usage["child_count"],
            "No program uses 'child_count' variable",
        )
        self.assertTrue(
            feature_usage["age"],
            "No program uses 'age' variable",
        )
        self.assertTrue(
            feature_usage["hh_total_income"],
            "No program uses 'hh_total_income' variable",
        )
        self.assertTrue(
            feature_usage["poverty_line"],
            "No program uses 'poverty_line' constant",
        )
        self.assertTrue(
            feature_usage[" and "],
            "No program demonstrates 'and' boolean operator",
        )
        self.assertTrue(
            feature_usage[" or "],
            "No program demonstrates 'or' boolean operator",
        )

    def test_cel_expression_identifiers(self):
        """Test CEL expressions use valid identifier patterns."""
        import re

        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        # Valid identifier pattern for CEL (field names, function names)
        valid_identifier = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

        for program in demo_programs.get_all_demo_programs():
            expr = program.get("cel_expression", "")
            program_name = program["name"]

            # Extract function calls like age_years(, metric(, etc.
            functions = re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", expr)
            for func in functions:
                self.assertTrue(
                    valid_identifier.match(func),
                    f"Program '{program_name}' has invalid function name: {func}",
                )

    def test_elderly_pension_cel_uses_age_variable(self):
        """Test Elderly Social Pension uses age variable and retirement_age constant."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        program = demo_programs.get_demo_program_by_name("Elderly Social Pension")
        self.assertIsNotNone(program)
        # Uses age computed variable
        self.assertIn("age", program["cel_expression"])
        # Uses retirement_age constant instead of hardcoded 65
        self.assertIn("retirement_age", program["cel_expression"])

    def test_universal_child_grant_cel_uses_child_count(self):
        """Test Universal Child Grant uses child_count variable."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        program = demo_programs.get_demo_program_by_name("Universal Child Grant")
        self.assertIsNotNone(program)
        # Uses child_count aggregate variable
        self.assertIn("child_count", program["cel_expression"])
        # Checks for households with children
        self.assertIn("> 0", program["cel_expression"])

    def test_cash_transfer_cel_uses_income_variable(self):
        """Test Cash Transfer Program uses hh_total_income and poverty_line."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        program = demo_programs.get_demo_program_by_name("Cash Transfer Program")
        self.assertIsNotNone(program)
        # Uses hh_total_income aggregate variable
        self.assertIn("hh_total_income", program["cel_expression"])
        # Uses hh_size aggregate variable
        self.assertIn("hh_size", program["cel_expression"])
        # Uses poverty_line constant
        self.assertIn("poverty_line", program["cel_expression"])

    def test_emergency_relief_cel_uses_dependency_ratio(self):
        """Test Emergency Relief Fund uses dependency_ratio and household variables."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        program = demo_programs.get_demo_program_by_name("Emergency Relief Fund")
        self.assertIsNotNone(program)
        # Uses dependency_ratio computed variable
        self.assertIn("dependency_ratio", program["cel_expression"])
        # Uses is_female_headed computed variable
        self.assertIn("is_female_headed", program["cel_expression"])
        # Uses elderly_count aggregate variable
        self.assertIn("elderly_count", program["cel_expression"])

    def test_food_assistance_cel_simple(self):
        """Test Food Assistance uses simple inline CEL expression."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        program = demo_programs.get_demo_program_by_name("Food Assistance")
        self.assertIsNotNone(program)
        # Simple active check, no Logic Pack
        self.assertIn("r.active", program["cel_expression"])
        self.assertIsNone(program.get("logic_pack"))

    # ═══════════════════════════════════════════════════════════════════════
    # LOGIC PACK LINKAGE TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_programs_link_to_logic_packs(self):
        """Test that programs correctly link to Logic Packs."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        expected_packs = {
            "Universal Child Grant": "child_benefit",
            "Elderly Social Pension": "social_pension",
            "Emergency Relief Fund": "vulnerability_assessment",
            "Cash Transfer Program": "cash_transfer_basic",
            "Food Assistance": None,  # No pack for simple CEL
        }

        for program_name, expected_pack in expected_packs.items():
            program = demo_programs.get_demo_program_by_name(program_name)
            self.assertIsNotNone(program, f"Program '{program_name}' not found")
            self.assertEqual(
                program.get("logic_pack"),
                expected_pack,
                f"Program '{program_name}' should link to pack '{expected_pack}'",
            )

    def test_get_programs_by_pack(self):
        """Test getting programs by Logic Pack code."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        programs = demo_programs.get_programs_by_pack("child_benefit")
        self.assertEqual(len(programs), 2)
        program_names = [p["name"] for p in programs]
        self.assertIn("Universal Child Grant", program_names)
        self.assertIn("Conditional Child Grant", program_names)

        # Non-existent pack should return empty
        programs = demo_programs.get_programs_by_pack("nonexistent")
        self.assertEqual(len(programs), 0)

    def test_get_demo_pack_codes(self):
        """Test getting list of Logic Pack codes used by demo."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        pack_codes = demo_programs.get_demo_pack_codes()
        self.assertIsInstance(pack_codes, list)
        self.assertIn("child_benefit", pack_codes)
        self.assertIn("social_pension", pack_codes)

    # ═══════════════════════════════════════════════════════════════════════
    # ENTITLEMENT FORMULA TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_entitlement_formulas_defined(self):
        """Test that programs with dynamic entitlements have formulas."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        # Programs with CEL entitlement formulas
        formula_programs = [
            "Universal Child Grant",  # base_child_grant * child_count
            "Emergency Relief Fund",  # Tiered based on vulnerability
        ]

        for program_name in formula_programs:
            program = demo_programs.get_demo_program_by_name(program_name)
            self.assertIn(
                "entitlement_formula",
                program,
                f"Program '{program_name}' missing entitlement formula",
            )

    def test_child_grant_entitlement_formula(self):
        """Test Universal Child Grant uses per-child calculation with variables."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        program = demo_programs.get_demo_program_by_name("Universal Child Grant")
        formula = program.get("entitlement_formula", "")
        # Uses base_child_grant constant
        self.assertIn("base_child_grant", formula)
        # Uses child_count variable
        self.assertIn("child_count", formula)

    def test_emergency_tiered_entitlement_formula(self):
        """Test Emergency Relief uses ternary tiered formula with dependency_ratio."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        program = demo_programs.get_demo_program_by_name("Emergency Relief Fund")
        formula = program.get("entitlement_formula", "")
        # Uses tier constants
        self.assertIn("emergency_tier_1", formula)
        self.assertIn("emergency_tier_2", formula)
        self.assertIn("emergency_tier_3", formula)
        # Uses dependency_ratio variable
        self.assertIn("dependency_ratio", formula)
        # Uses ternary operator
        self.assertIn("?", formula)

    # ═══════════════════════════════════════════════════════════════════════
    # STORY ELIGIBILITY VALIDATION TESTS
    # ═══════════════════════════════════════════════════════════════════════

    def test_story_program_alignment_complete(self):
        """Test that all stories are aligned with appropriate programs.

        Each story persona should be enrolled in programs that match their:
        - Demographics (age, household composition)
        - Circumstances (income, vulnerability)
        - Story narrative (elderly, displaced, etc.)
        """
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        # Expected story-to-program mappings based on V3 spec
        expected_mappings = {
            # Maria Santos - Cash Transfer (graduated) + Universal Child Grant + Food Assistance (individual)
            "maria_santos": ["Cash Transfer Program", "Universal Child Grant", "Food Assistance"],
            # Juan Dela Cruz - Cash Transfer recipient with GRM issue
            "juan_dela_cruz": ["Cash Transfer Program"],
            # Rosa Garcia - Elderly + Food Assistance
            "rosa_garcia": ["Elderly Social Pension", "Food Assistance"],
            # Carlos/Elena Morales - Household with 3 children
            "carlos_elena_morales": ["Universal Child Grant"],
            # Ramon Gutierrez - Emergency Relief (household) + Food Assistance (individual)
            "ibrahim_hassan": ["Emergency Relief Fund", "Food Assistance"],
            # Teresa Villanueva - Food Assistance recipient
            "fatima_al_rahman": ["Food Assistance"],
            # Roberto Castillo - Background Cash Transfer
            "ahmed_said": ["Cash Transfer Program"],
            # Manuel Pangilinan - Elderly Social Pension (individual)
            "manuel_gloria_elderly": ["Elderly Social Pension"],
            # Pedro Reyes - Food Assistance
            "pedro_reyes": ["Food Assistance"],
            # Ana Mendoza - Food Assistance
            "ana_mendoza": ["Food Assistance"],
        }

        for story_id, expected_programs in expected_mappings.items():
            enrollments = demo_programs.get_story_enrollments(story_id)
            enrolled_programs = [e.get("program") for e in enrollments]

            for expected in expected_programs:
                self.assertIn(
                    expected,
                    enrolled_programs,
                    f"Story '{story_id}' should be enrolled in '{expected}'",
                )

    def test_all_programs_have_enrolled_stories(self):
        """Test that demo programs have at least one enrolled story.

        Conditional Child Grant is excluded: it demonstrates compliance
        features and members.exists() CEL patterns without persona stories.
        """
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        # Programs that intentionally have no story personas
        programs_without_stories = {"Conditional Child Grant"}

        for program in demo_programs.get_all_demo_programs():
            program_name = program["name"]
            if program_name in programs_without_stories:
                continue
            stories = program.get("stories", [])
            self.assertGreater(
                len(stories),
                0,
                f"Program '{program_name}' has no enrolled stories",
            )

    def test_story_enrollment_has_required_fields(self):
        """Test that story enrollments have required fields for demo.

        Enrollments must have 'program' and either:
        - 'enrolled_days_back' for successful enrollments, OR
        - 'application_days_back' for rejected applications
        """
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        for story_id, enrollments in demo_programs.STORY_ENROLLMENTS.items():
            for i, enrollment in enumerate(enrollments):
                self.assertIn(
                    "program",
                    enrollment,
                    f"Story '{story_id}' enrollment {i} missing 'program'",
                )
                # Either enrolled_days_back OR application_days_back is valid
                has_timeline = "enrolled_days_back" in enrollment or "application_days_back" in enrollment
                self.assertTrue(
                    has_timeline,
                    f"Story '{story_id}' enrollment {i} missing timeline field "
                    "(need 'enrolled_days_back' or 'application_days_back')",
                )

    def test_elderly_story_eligibility(self):
        """Test Rosa Garcia meets elderly pension eligibility criteria.

        Rosa should be eligible because:
        - age >= retirement_age (using age computed variable)
        """
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        # Rosa should be in Elderly Social Pension
        programs = demo_programs.get_programs_for_story("rosa_garcia")
        program_names = [p["name"] for p in programs]
        self.assertIn("Elderly Social Pension", program_names)

    def test_child_grant_story_eligibility(self):
        """Test Carlos/Elena Morales meets child grant eligibility criteria.

        The Morales family should be eligible because:
        - is_group == true (household)
        - child_count > 0 (using child_count aggregate variable)
        """
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        programs = demo_programs.get_programs_for_story("carlos_elena_morales")
        program_names = [p["name"] for p in programs]
        self.assertIn("Universal Child Grant", program_names)

    def test_emergency_story_eligibility(self):
        """Test Ramon Gutierrez meets emergency eligibility criteria.

        Ramon Gutierrez should be eligible because:
        - dependency_ratio >= 1.5 (using computed variable)
        - OR is_female_headed and elderly_count > 0
        """
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        programs = demo_programs.get_programs_for_story("ibrahim_hassan")
        program_names = [p["name"] for p in programs]
        self.assertIn("Emergency Relief Fund", program_names)

    # ===================================================================
    # Compliance criteria tests
    # ===================================================================

    def test_cash_transfer_has_compliance_expression(self):
        """Cash Transfer Program must define a compliance CEL expression."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        for prog in demo_programs.get_all_demo_programs():
            if prog["id"] == "cash_transfer_program":
                self.assertIn("compliance_cel_expression", prog)
                self.assertEqual(
                    prog["compliance_cel_expression"],
                    "per_capita_income < poverty_line",
                )
                return
        self.fail("Cash Transfer Program not found")

    def test_conditional_child_grant_has_compliance_expression(self):
        """Conditional Child Grant must define a compliance CEL expression."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        for prog in demo_programs.get_all_demo_programs():
            if prog["id"] == "conditional_child_grant":
                self.assertIn("compliance_cel_expression", prog)
                self.assertEqual(
                    prog["compliance_cel_expression"],
                    "per_capita_income < income_threshold",
                )
                return
        self.fail("Conditional Child Grant not found")

    def test_conditional_child_grant_has_program_constants(self):
        """Conditional Child Grant must override income_threshold to 2000."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        for prog in demo_programs.get_all_demo_programs():
            if prog["id"] == "conditional_child_grant":
                self.assertIn("program_constants", prog)
                self.assertEqual(prog["program_constants"]["income_threshold"], "2000")
                return
        self.fail("Conditional Child Grant not found")

    def test_programs_without_compliance_have_no_expression(self):
        """Programs without compliance should not define compliance_cel_expression."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        programs_with_compliance = {"cash_transfer_program", "conditional_child_grant"}
        for prog in demo_programs.get_all_demo_programs():
            if prog["id"] not in programs_with_compliance:
                expr = prog.get("compliance_cel_expression")
                self.assertFalse(
                    expr,
                    f"Program '{prog['name']}' should not have compliance_cel_expression",
                )

    def test_santos_has_non_compliant_cycle(self):
        """Santos enrollment must define non_compliant_cycle for compliance failure."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        enrollments = demo_programs.get_story_enrollments("maria_santos")
        cash_transfer = [e for e in enrollments if e["program"] == "Cash Transfer Program"]
        self.assertEqual(len(cash_transfer), 1)
        self.assertIn("non_compliant_cycle", cash_transfer[0])
        self.assertIn("days_back", cash_transfer[0]["non_compliant_cycle"])

    def test_santos_has_graduated_days_back(self):
        """Santos Cash Transfer must have graduated_days_back (exited after compliance failure)."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        enrollments = demo_programs.get_story_enrollments("maria_santos")
        cash_transfer = [e for e in enrollments if e["program"] == "Cash Transfer Program"]
        self.assertEqual(len(cash_transfer), 1)
        self.assertIn("graduated_days_back", cash_transfer[0])

    def test_santos_enrolled_in_universal_child_grant(self):
        """Santos must also be enrolled in Universal Child Grant (partial exit story)."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        enrollments = demo_programs.get_story_enrollments("maria_santos")
        programs = [e["program"] for e in enrollments]
        self.assertIn("Universal Child Grant", programs)

    def test_only_two_programs_have_compliance(self):
        """Exactly 2 programs should have compliance CEL expressions."""
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        with_compliance = [p for p in demo_programs.get_all_demo_programs() if p.get("compliance_cel_expression")]
        self.assertEqual(len(with_compliance), 2)

    def test_rejected_story_documented(self):
        """Test that rejected application story is properly documented.

        Lorna Pascual should be rejected for age requirement not met.
        """
        from odoo.addons.spp_mis_demo_v2.models import demo_programs

        enrollments = demo_programs.get_story_enrollments("mary_johnson")
        self.assertGreater(len(enrollments), 0)

        enrollment = enrollments[0]
        self.assertEqual(enrollment.get("status"), "rejected")
        self.assertIn("Age requirement", enrollment.get("rejection_reason", ""))
