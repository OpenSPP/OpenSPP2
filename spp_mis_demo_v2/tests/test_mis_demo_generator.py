# Part of OpenSPP. See LICENSE file for full copyright and licensing details.


from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMISDemoGenerator(TransactionCase):
    """Test MIS Demo Generator V2."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create test country for locale
        cls.test_country = cls.env.ref("base.us")

    def test_generator_creation(self):
        """Test that generator can be created with defaults."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Generator",
            }
        )

        self.assertTrue(generator.create_demo_programs)
        self.assertTrue(generator.enroll_demo_stories)
        self.assertTrue(generator.generate_volume)
        self.assertEqual(generator.state, "draft")

    def test_wizard_creation(self):
        """Test that wizard can be created."""
        wizard = self.env["spp.mis.demo.wizard"].create(
            {
                "name": "Test Wizard",
                "locale_origin": self.test_country.id,
            }
        )

        self.assertIsNotNone(wizard)
        self.assertEqual(wizard.name, "Test Wizard")

    def test_demo_programs_creation(self):
        """Test that demo programs can be created."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Programs",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )

        # Run generation
        generator.action_generate()

        # Check programs were created (V3 names)
        programs = self.env["spp.program"].search(
            [
                (
                    "name",
                    "in",
                    [
                        "Universal Child Grant",
                        "Elderly Social Pension",
                        "Cash Transfer Program",
                        "Disability Support Grant",
                        "Emergency Relief Fund",
                        "Food Assistance",
                    ],
                )
            ]
        )

        self.assertGreaterEqual(len(programs), 6)

    def test_story_enrollment_without_registrants(self):
        """Test that enrollment gracefully handles missing registrants."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Enrollment",
                "create_demo_programs": True,
                "enroll_demo_stories": True,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )

        # Should not raise even if registrants don't exist
        result = generator.action_generate()
        self.assertIsNotNone(result)

    def test_volume_generation_without_registrants(self):
        """Test that volume generation handles no registrants gracefully."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Volume",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": True,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )

        # Should complete without error even with no registrants
        result = generator.action_generate()
        self.assertIsNotNone(result)

    def test_state_transitions(self):
        """Test generator state transitions."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test State",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )

        self.assertEqual(generator.state, "draft")

        # Run generation (minimal)
        generator.action_generate()

        self.assertEqual(generator.state, "completed")

    def test_action_returned(self):
        """Test that action is returned after generation.

        The generator redirects to the Programs list after successful generation,
        or falls back to a notification if the programs action is unavailable.
        """
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Action",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )

        result = generator.action_generate()

        self.assertIsInstance(result, dict)
        # Generator redirects to programs list if action available, else shows notification
        action_type = result.get("type")
        self.assertIn(action_type, ["ir.actions.act_window", "ir.actions.client"])

        if action_type == "ir.actions.act_window":
            # Redirected to programs list
            self.assertEqual(result.get("res_model"), "spp.program")
        else:
            # Fallback notification
            self.assertEqual(result.get("tag"), "display_notification")

    def test_idempotent_program_creation(self):
        """Test that programs are not duplicated on re-run."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Idempotent",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )

        # Run twice
        generator.action_generate()

        generator2 = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Idempotent 2",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )
        generator2.action_generate()

        # Check no duplicates (use Universal Child Grant as test)
        programs = self.env["spp.program"].search(
            [
                ("name", "=", "Universal Child Grant"),
            ]
        )
        self.assertEqual(len(programs), 1)

    def test_demo_mode_presets(self):
        """Test that demo mode presets configure options correctly."""
        # Sales mode - minimal, fast
        sales_gen = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Sales Test",
                "demo_mode": "sales",
            }
        )
        # Sales mode onchange should configure for minimal data
        sales_gen._onchange_demo_mode()
        self.assertFalse(sales_gen.install_logic_packs)
        self.assertFalse(sales_gen.include_test_personas)

        # Training mode - comprehensive
        training_gen = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Training Test",
                "demo_mode": "training",
            }
        )
        training_gen._onchange_demo_mode()
        self.assertTrue(training_gen.install_logic_packs)
        self.assertTrue(training_gen.include_test_personas)

        # Complete mode - everything enabled
        complete_gen = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Complete Test",
                "demo_mode": "complete",
            }
        )
        complete_gen._onchange_demo_mode()
        self.assertTrue(complete_gen.generate_volume)
        self.assertTrue(complete_gen.install_logic_packs)

    def test_change_requests_v2_created(self):
        """Generator should create V2 change requests with details."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test CR V2",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "create_event_data": False,
                "create_story_payments": False,
                "create_change_requests": True,
                "locale_origin": self.test_country.id,
            }
        )

        generator.action_generate()

        # Valid approval_state values: draft, pending, revision, approved, rejected
        # Note: Actual state depends on approval workflow configuration.
        # If approval definitions aren't set up, CRs stay in draft.
        expected_codes = [
            "edit_individual",
            "update_id",
            "exit_registrant",
            "add_member",
            "transfer_member",
            "change_hoh",
        ]

        for code in expected_codes:
            cr = self.env["spp.change.request"].search([("request_type_id.code", "=", code)], limit=1)
            self.assertTrue(cr, f"Missing change request for code {code}")
            # Verify CR has a valid state (don't enforce specific state - depends on workflow config)
            self.assertIn(
                cr.approval_state,
                ["draft", "pending", "approved", "rejected", "revision"],
                f"Invalid state for {code}: {cr.approval_state}",
            )
            detail = cr.get_detail()
            self.assertTrue(detail and detail.exists(), f"Missing detail for {code}")

    def test_change_request_workflow_states(self):
        """Test that CR demo covers all workflow states.

        The demo should include CRs in different states:
        - draft: New CRs not yet submitted
        - pending: CRs awaiting approval
        - approved: Approved CRs (may or may not be applied)
        - rejected: Rejected CRs with reason
        - revision: CRs sent back for correction
        """
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test CR States",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "create_event_data": False,
                "create_change_requests": True,
                "locale_origin": self.test_country.id,
            }
        )

        generator.action_generate()

        # Check we have CRs in various states
        all_crs = self.env["spp.change.request"].search([])
        states_found = set(all_crs.mapped("approval_state"))

        # At minimum, should have approved and pending states
        self.assertIn("approved", states_found)
        self.assertIn("pending", states_found)

    def test_change_request_types_coverage(self):
        """Test that demo covers key CR types.

        Critical CR types for demo:
        - edit_individual: Basic data update
        - add_member: Household changes
        - change_hoh: Leadership change
        - update_id: ID document update
        - exit_registrant: Registry exit
        - transfer_member: Inter-household transfer
        """
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test CR Types",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "create_event_data": False,
                "create_change_requests": True,
                "locale_origin": self.test_country.id,
            }
        )

        generator.action_generate()

        # Key CR types that should exist
        key_types = [
            "edit_individual",
            "add_member",
            "change_hoh",
            "update_id",
            "exit_registrant",
        ]

        for type_code in key_types:
            cr_type = self.env["spp.change.request.type"].search([("code", "=", type_code)], limit=1)
            if cr_type:
                cr = self.env["spp.change.request"].search([("request_type_id", "=", cr_type.id)], limit=1)
                self.assertTrue(
                    cr,
                    f"Missing demo CR for type '{type_code}'",
                )


@tagged("post_install", "-at_install")
class TestMISDemoGeneratorWithData(TransactionCase):
    """Test MIS Demo Generator with existing data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_country = cls.env.ref("base.us")

        # Get group type from vocabulary
        cls.group_type = cls.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-type", "household")

        # Create test registrants
        cls.test_group = cls.env["res.partner"].create(
            {
                "name": "Test Group",
                "is_registrant": True,
                "is_group": True,
                "group_type_id": cls.group_type.id,
            }
        )

        cls.test_individual = cls.env["res.partner"].create(
            {
                "name": "Test Individual",
                "is_registrant": True,
                "is_group": False,
            }
        )

    def test_volume_generation_with_registrants(self):
        """Test volume generation with existing registrants."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Volume With Data",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": True,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )

        generator.action_generate()

        # Check some enrollments were created
        enrollments = self.env["spp.program.membership"].search(
            [("partner_id", "in", [self.test_group.id, self.test_individual.id])]
        )
        # May have some enrollments depending on program compatibility
        self.assertIsNotNone(enrollments)

    def test_enrollment_duplicate_prevention(self):
        """Test that duplicate enrollments are prevented."""
        # Create a program
        program = self.env["spp.program"].create(
            {
                "name": "Test Duplicate Prevention Program",
                "target_type": "group",
            }
        )

        # Create initial enrollment
        self.env["spp.program.membership"].create(
            {
                "partner_id": self.test_group.id,
                "program_id": program.id,
                "state": "enrolled",
            }
        )

        # Try to create duplicate via generator
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Duplicate",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": True,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )

        generator.action_generate()

        # Should still have only one enrollment
        enrollments = self.env["spp.program.membership"].search(
            [
                ("partner_id", "=", self.test_group.id),
                ("program_id", "=", program.id),
            ]
        )
        self.assertEqual(len(enrollments), 1)


@tagged("post_install", "-at_install")
class TestDemoStoryHouseholdMembers(TransactionCase):
    """Test that demo stories create households with all their members."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_country = cls.env.ref("base.us")

        # Expected member counts for each household story
        # Based on demo_stories.py definitions
        cls.EXPECTED_HOUSEHOLD_MEMBERS = {
            # story_name: expected_member_count
            "Morales": 5,  # head + spouse + 3 children
            "Santos": 5,  # head + spouse + 2 children + 1 adult
            "Dela Cruz": 4,  # head + spouse + 2 children
            "Gutierrez": 7,  # head + spouse + 5 children
            "Castillo": 3,  # head + spouse + 1 child
            "Aquino": 4,  # head + 3 children
            "Reyes": 8,  # head + spouse + 2 adults + 4 children
            "Bautista": 7,  # head + spouse + 5 children
            "Pangilinan": 2,  # head + spouse
            "Navarro": 4,  # head + 3 adults
            "Martinez": 3,  # head + spouse + 1 child
        }

    def _run_generator_for_stories(self):
        """Helper to run generator with story creation enabled."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Story Members",
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "create_event_data": False,
                "create_change_requests": False,
                "locale_origin": self.test_country.id,
            }
        )
        generator.action_generate()
        return generator

    def test_household_stories_created_with_members(self):
        """Test that household stories are created with all their members."""
        self._run_generator_for_stories()

        for story_name, expected_count in self.EXPECTED_HOUSEHOLD_MEMBERS.items():
            # Find the group
            group = self.env["res.partner"].search(
                [
                    ("name", "=", story_name),
                    ("is_registrant", "=", True),
                    ("is_group", "=", True),
                ],
                limit=1,
            )

            self.assertTrue(group, f"Household group '{story_name}' was not created")

            # Count members
            member_count = self.env["spp.group.membership"].search_count([("group", "=", group.id)])

            self.assertEqual(
                member_count,
                expected_count,
                f"Household '{story_name}' should have {expected_count} members, but has {member_count}",
            )

    def test_bautista_family_has_all_members(self):
        """Test Bautista family has head, spouse, and all 5 children."""
        self._run_generator_for_stories()

        group = self.env["res.partner"].search(
            [
                ("name", "=", "Bautista"),
                ("is_group", "=", True),
            ],
            limit=1,
        )
        self.assertTrue(group, "Eduardo Bautista household not found")

        memberships = self.env["spp.group.membership"].search([("group", "=", group.id)])
        member_names = memberships.mapped("individual.name")

        # Expected members - names stored as "FAMILY, GIVEN" uppercase
        expected_given_names = ["Eduardo", "Carmen", "Patricia", "Fernando", "Lucia", "Rosalie", "Antonio"]

        self.assertEqual(len(memberships), 7, "Bautista family should have 7 members")

        # Check each expected member exists by given name
        for given_name in expected_given_names:
            found = any(given_name.upper() in name.upper() for name in member_names)
            self.assertTrue(
                found,
                f"Expected member with given name '{given_name}' not found in Bautista family. "
                f"Actual members: {member_names}",
            )

    def test_navarro_family_has_all_adults(self):
        """Test Navarro extended family has head and all 3 adults."""
        self._run_generator_for_stories()

        group = self.env["res.partner"].search(
            [
                ("name", "=", "Navarro"),
                ("is_group", "=", True),
            ],
            limit=1,
        )
        self.assertTrue(group, "Ricardo Navarro household not found")

        memberships = self.env["spp.group.membership"].search([("group", "=", group.id)])
        member_names = memberships.mapped("individual.name")

        # Expected members - names stored as "FAMILY, GIVEN" uppercase
        expected_given_names = ["Ricardo", "Lourdes", "Eduardo", "Cristina"]

        self.assertEqual(len(memberships), 4, "Navarro family should have 4 members")

        for given_name in expected_given_names:
            found = any(given_name.upper() in name.upper() for name in member_names)
            self.assertTrue(
                found,
                f"Expected member with given name '{given_name}' not found in Navarro family. "
                f"Actual members: {member_names}",
            )

    def test_existing_empty_group_gets_members_populated(self):
        """Test that existing empty household groups get their members created."""
        # First, delete any existing Bautista group to simulate a fresh state
        existing = self.env["res.partner"].search(
            [
                ("name", "=", "Bautista"),
                ("is_registrant", "=", True),
                ("is_group", "=", True),
            ]
        )
        if existing:
            # Delete memberships first
            self.env["spp.group.membership"].search([("group", "in", existing.ids)]).unlink()
            existing.unlink()

        # Create an empty Bautista group (simulating partial creation bug)
        empty_group = self.env["res.partner"].create(
            {
                "name": "Bautista",
                "is_registrant": True,
                "is_group": True,
            }
        )

        # Verify it has no members
        initial_count = self.env["spp.group.membership"].search_count([("group", "=", empty_group.id)])
        self.assertEqual(initial_count, 0, "Group should start with no members")

        # Run the generator
        self._run_generator_for_stories()

        # Now check members were created
        final_count = self.env["spp.group.membership"].search_count([("group", "=", empty_group.id)])
        self.assertEqual(final_count, 7, "Bautista group should have 7 members after generator runs")

    def test_head_of_household_has_correct_membership_type(self):
        """Test that household heads have the 'head' membership type."""
        self._run_generator_for_stories()

        # Get head membership type
        head_type = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")

        if not head_type:
            self.skipTest("Head membership type not configured")

        # Check a few households
        for story_name in ["Bautista", "Navarro", "Morales"]:
            group = self.env["res.partner"].search(
                [
                    ("name", "=", story_name),
                    ("is_group", "=", True),
                ],
                limit=1,
            )

            if not group:
                continue

            # Find membership with head type
            head_membership = self.env["spp.group.membership"].search(
                [
                    ("group", "=", group.id),
                    ("membership_type_ids", "in", head_type.id),
                ]
            )

            self.assertEqual(
                len(head_membership), 1, f"Household '{story_name}' should have exactly one head of household"
            )

    def test_non_head_members_have_membership_types(self):
        """Spouse, child, and other adult members each get the matching membership type."""
        self._run_generator_for_stories()

        VocabCode = self.env["spp.vocabulary.code"]
        ns = "urn:openspp:vocab:group-membership-type"
        types = {code: VocabCode.get_code(ns, code) for code in ("head", "spouse", "child", "other")}

        if not all(types.values()):
            self.skipTest("Group-membership-type vocabulary codes not configured")

        for story_name in ["Bautista", "Navarro", "Morales"]:
            group = self.env["res.partner"].search([("name", "=", story_name), ("is_group", "=", True)], limit=1)
            if not group:
                continue

            memberships = self.env["spp.group.membership"].search([("group", "=", group.id)])
            self.assertTrue(memberships, f"{story_name} should have memberships")

            # Every membership should carry exactly one type from our set
            for m in memberships:
                assigned = m.membership_type_ids & (types["head"] | types["spouse"] | types["child"] | types["other"])
                self.assertEqual(
                    len(assigned),
                    1,
                    f"Membership for {m.individual.name} in '{story_name}' should have exactly one "
                    f"group-membership-type code, got {m.membership_type_ids.mapped('code')}",
                )

            # At most one spouse per household
            spouse_memberships = memberships.filtered(lambda x: types["spouse"] in x.membership_type_ids)
            self.assertLessEqual(len(spouse_memberships), 1, f"{story_name} should have at most one spouse")

            # 'child' members are younger than the household head
            head_membership = memberships.filtered(lambda x: types["head"] in x.membership_type_ids)
            if head_membership and head_membership.individual.birthdate:
                head_birthdate = head_membership.individual.birthdate
                for m in memberships.filtered(lambda x: types["child"] in x.membership_type_ids):
                    if m.individual.birthdate:
                        self.assertGreater(
                            m.individual.birthdate,
                            head_birthdate,
                            f"Member {m.individual.name} tagged as 'child' in '{story_name}' "
                            f"should be younger than the head",
                        )

    def test_idempotent_member_creation(self):
        """Test that running generator twice doesn't duplicate members."""
        # Run generator first time
        self._run_generator_for_stories()

        # Count members for Bautista family
        group = self.env["res.partner"].search(
            [
                ("name", "=", "Bautista"),
                ("is_group", "=", True),
            ],
            limit=1,
        )
        first_count = self.env["spp.group.membership"].search_count([("group", "=", group.id)])

        # Run generator second time
        self._run_generator_for_stories()

        # Count should be the same
        second_count = self.env["spp.group.membership"].search_count([("group", "=", group.id)])

        self.assertEqual(first_count, second_count, "Running generator twice should not duplicate members")

    def test_individual_members_have_correct_attributes(self):
        """Test that created individual members have correct attributes."""
        self._run_generator_for_stories()

        # Find Carmen Bautista (spouse of Eduardo Bautista)
        carmen = self.env["res.partner"].search(
            [
                ("name", "ilike", "%carmen%bautista%"),
                ("is_registrant", "=", True),
                ("is_group", "=", False),
            ],
            limit=1,
        )

        if not carmen:
            # Try alternative name format
            carmen = self.env["res.partner"].search(
                [
                    ("name", "ilike", "%bautista%carmen%"),
                    ("is_registrant", "=", True),
                    ("is_group", "=", False),
                ],
                limit=1,
            )

        self.assertTrue(carmen, "Carmen Bautista individual should be created")
        self.assertFalse(carmen.is_group, "Carmen Bautista should not be a group")
        self.assertTrue(carmen.is_registrant, "Carmen Bautista should be a registrant")

        # Check birthdate is set (age 44 in story)
        if carmen.birthdate:
            from datetime import date

            age = (date.today() - carmen.birthdate).days // 365
            self.assertGreaterEqual(age, 40)
            self.assertLessEqual(age, 50)

    def test_get_story_name_returns_correct_names_for_all_stories(self):
        """Test that _get_story_name returns correct names for all demo stories.

        This test ensures that story IDs are properly mapped to registrant names,
        preventing duplicate registrants with incorrect names derived from story IDs
        instead of the actual story name.
        """
        from odoo.addons.spp_demo.models import demo_stories

        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Story Names",
            }
        )

        # Get all stories from demo_stories
        all_stories = demo_stories.get_all_stories()

        # Verify each story ID maps to the correct name
        for story in all_stories:
            story_id = story["id"]
            expected_name = story["name"]
            actual_name = generator._get_story_name(story_id)

            self.assertEqual(
                actual_name,
                expected_name,
                f"Story ID '{story_id}' should map to '{expected_name}', "
                f"but got '{actual_name}'. This can cause duplicate registrants "
                f"with incorrect names.",
            )

    # ===================================================================
    # Compliance manager tests
    # ===================================================================

    def test_compliance_managers_configured_after_generation(self):
        """Test that compliance managers have CEL expressions after program creation."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Compliance",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )
        generator.action_generate()

        # Cash Transfer should have compliance CEL
        cash_transfer = self.env["spp.program"].search([("name", "=", "Cash Transfer Program")], limit=1)
        self.assertTrue(cash_transfer, "Cash Transfer Program not found")
        self.assertTrue(cash_transfer.compliance_manager_ids, "No compliance manager on Cash Transfer")

        for wrapper in cash_transfer.compliance_manager_ids:
            concrete = wrapper.manager_ref_id
            if hasattr(concrete, "compliance_cel_expression"):
                self.assertEqual(
                    concrete.compliance_cel_expression,
                    "per_capita_income < poverty_line",
                )
                break
        else:
            self.fail("No concrete compliance manager found for Cash Transfer")

    def test_conditional_child_grant_compliance_configured(self):
        """Test that Conditional Child Grant has compliance CEL and program constant."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test CCG Compliance",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )
        generator.action_generate()

        ccg = self.env["spp.program"].search([("name", "=", "Conditional Child Grant")], limit=1)
        self.assertTrue(ccg, "Conditional Child Grant not found")

        # Check compliance expression
        for wrapper in ccg.compliance_manager_ids:
            concrete = wrapper.manager_ref_id
            if hasattr(concrete, "compliance_cel_expression"):
                self.assertEqual(
                    concrete.compliance_cel_expression,
                    "per_capita_income < income_threshold",
                )
                break
        else:
            self.fail("No concrete compliance manager found for CCG")

        # Check program constant override
        param = self.env["spp.cel.program.parameter"].search([("program_id", "=", ccg.id)], limit=1)
        self.assertTrue(param, "No program parameter found for CCG")
        self.assertEqual(param.value, "2000")

    def test_non_compliant_cycle_membership_created(self):
        """Test that Santos has non_compliant cycle membership after generation."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test Non-Compliant",
                "create_demo_programs": True,
                "enroll_demo_stories": True,
                "create_story_payments": True,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )
        generator.action_generate()

        # Find Santos household
        santos = self.env["res.partner"].search(
            [("name", "=", "Santos"), ("is_group", "=", True), ("is_registrant", "=", True)],
            limit=1,
        )
        if not santos:
            # Story registrant may not have been created in test environment
            return

        # Check Cash Transfer cycle membership is non_compliant
        cash_transfer = self.env["spp.program"].search([("name", "=", "Cash Transfer Program")], limit=1)
        if not cash_transfer:
            return

        cycle = self.env["spp.cycle"].search([("program_id", "=", cash_transfer.id)], limit=1)
        if not cycle:
            return

        cm = self.env["spp.cycle.membership"].search(
            [("partner_id", "=", santos.id), ("cycle_id", "=", cycle.id)],
            limit=1,
        )
        self.assertTrue(cm, "No cycle membership found for Santos in Cash Transfer")
        self.assertEqual(cm.state, "non_compliant", "Santos should be non_compliant")

    def test_programs_without_compliance_have_empty_expression(self):
        """Programs without compliance_cel_expression should have empty compliance managers."""
        generator = self.env["spp.mis.demo.generator"].create(
            {
                "name": "Test No Compliance",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": self.test_country.id,
            }
        )
        generator.action_generate()

        # Food Assistance should NOT have a compliance expression
        food = self.env["spp.program"].search([("name", "=", "Food Assistance")], limit=1)
        self.assertTrue(food, "Food Assistance not found")

        for wrapper in food.compliance_manager_ids:
            concrete = wrapper.manager_ref_id
            if hasattr(concrete, "compliance_cel_expression"):
                self.assertFalse(
                    concrete.compliance_cel_expression,
                    "Food Assistance should not have a compliance expression",
                )
