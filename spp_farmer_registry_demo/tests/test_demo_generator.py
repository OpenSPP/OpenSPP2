# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for Farmer Registry Demo Generator.

Tests cover:
- Story farm generation (8 personas with Filipino names)
- Active season creation
- Blueprint-based farm generation
- Demo program creation via wizard
- Story enrollment with draft-first state machine
- Vocabulary code lookup helper
"""

import time

from odoo.tests import TransactionCase, tagged


def _unique(base):
    """Generate unique name for test isolation."""
    return f"{base}_{int(time.time() * 1000)}"


@tagged("post_install", "-at_install")
class TestFarmerDemoGenerator(TransactionCase):
    """Test spp.farmer.demo.generator wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.Generator = cls.env["spp.farmer.demo.generator"]

    def test_create_generator_wizard(self):
        """Test creating the demo generator wizard."""
        wizard = self.Generator.create(
            {
                "name": _unique("Test Demo"),
            }
        )

        self.assertTrue(wizard.create_demo_farms)
        self.assertTrue(wizard.create_active_season)
        self.assertTrue(wizard.generate_volume)
        self.assertTrue(wizard.create_demo_programs)
        self.assertTrue(wizard.enroll_demo_stories)
        self.assertTrue(wizard.create_cycles)

    def test_create_active_season(self):
        """Test active season creation."""
        wizard = self.Generator.create(
            {
                "name": _unique("Season Test"),
            }
        )

        season = wizard._create_active_season()

        self.assertIsNotNone(season)
        self.assertEqual(season.state, "active")
        self.assertIn(str(time.localtime().tm_year), season.name)

    def test_create_active_season_existing(self):
        """Test returns existing active season if present."""
        wizard = self.Generator.create(
            {
                "name": _unique("Existing Season Test"),
            }
        )

        season1 = wizard._create_active_season()
        season2 = wizard._create_active_season()

        self.assertEqual(season1.id, season2.id)

    def test_get_vocab_code_existing(self):
        """Test _get_vocab_code finds existing vocabulary code."""
        wizard = self.Generator.create(
            {
                "name": _unique("Vocab Test"),
            }
        )

        code_id = wizard._get_vocab_code("urn:openspp:vocab:farm-type", "crop")

        if code_id:
            code = self.env["spp.vocabulary.code"].browse(code_id)
            self.assertEqual(code.code, "crop")

    def test_get_vocab_code_nonexistent(self):
        """Test _get_vocab_code returns False for nonexistent code."""
        wizard = self.Generator.create(
            {
                "name": _unique("Nonexistent Vocab Test"),
            }
        )

        code_id = wizard._get_vocab_code("urn:nonexistent:vocab", "fake_code")

        self.assertFalse(code_id)


@tagged("post_install", "-at_install")
class TestFarmerDemoGeneratorStoryFarms(TransactionCase):
    """Test story farm generation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.Generator = cls.env["spp.farmer.demo.generator"]

        cls._create_test_vocabularies()

    @classmethod
    def _create_test_vocabularies(cls):
        """Create vocabularies needed for demo generation."""
        Vocabulary = cls.env["spp.vocabulary"]
        VocabCode = cls.env["spp.vocabulary.code"]

        vocab_defs = [
            {
                "name": "Farm Type",
                "namespace_uri": "urn:openspp:vocab:farm-type",
                "codes": [
                    ("crop", "Crop Farming"),
                    ("livestock", "Livestock Farming"),
                    ("mixed", "Mixed Farming"),
                    ("aquaculture", "Aquaculture"),
                ],
            },
            {
                "name": "Land Tenure",
                "namespace_uri": "urn:openspp:vocab:land-tenure",
                "codes": [
                    ("self", "Self-owned"),
                    ("family", "Family-owned"),
                    ("leased", "Leased"),
                    ("cooperative", "Cooperative"),
                ],
            },
            {
                "name": "Holder Type",
                "namespace_uri": "urn:openspp:vocab:holder-type",
                "codes": [("individual", "Individual")],
            },
            {
                "name": "Gender",
                "namespace_uri": "urn:openspp:vocab:gender",
                "codes": [("male", "Male"), ("female", "Female")],
            },
            {
                "name": "Group Membership Type",
                "namespace_uri": "urn:openspp:vocab:group-membership-type",
                "codes": [("head", "Head of Household")],
            },
        ]

        for vocab_def in vocab_defs:
            vocab = Vocabulary.search([("namespace_uri", "=", vocab_def["namespace_uri"])], limit=1)
            if not vocab:
                vocab = Vocabulary.create(
                    {
                        "name": vocab_def["name"],
                        "namespace_uri": vocab_def["namespace_uri"],
                    }
                )
                for code, display in vocab_def["codes"]:
                    VocabCode.create(
                        {
                            "vocabulary_id": vocab.id,
                            "namespace_uri": vocab_def["namespace_uri"],
                            "code": code,
                            "display": display,
                        }
                    )

    def test_create_story_farms_count(self):
        """Test that 8 story farms are created."""
        wizard = self.Generator.create(
            {
                "name": _unique("Story Farms Test"),
            }
        )

        story_farms = wizard._create_story_farms()

        self.assertEqual(len(story_farms), 8)

    def test_create_story_farms_names(self):
        """Test story farm names match Filipino personas."""
        wizard = self.Generator.create(
            {
                "name": _unique("Story Names Test"),
            }
        )

        story_farms = wizard._create_story_farms()
        farm_names = [f.name for f in story_farms.values()]

        self.assertIn("Santos Farm", farm_names)
        self.assertIn("Dela Cruz Farm", farm_names)
        self.assertIn("Garcia Farm", farm_names)
        self.assertIn("Mangudadatu Farm", farm_names)
        self.assertIn("Martinez Farm", farm_names)
        self.assertIn("Dela Cruz Fishpond", farm_names)
        self.assertIn("Pangandaman Farm", farm_names)
        self.assertIn("Villanueva Farm", farm_names)

    def test_create_story_farms_are_groups(self):
        """Test story farms are created as groups."""
        wizard = self.Generator.create(
            {
                "name": _unique("Group Test"),
            }
        )

        story_farms = wizard._create_story_farms()

        for farm in story_farms.values():
            self.assertTrue(farm.is_group)
            self.assertTrue(farm.is_registrant)

    def test_create_story_farms_have_members(self):
        """Test story farms have farmer members."""
        wizard = self.Generator.create(
            {
                "name": _unique("Members Test"),
            }
        )

        story_farms = wizard._create_story_farms()

        for farm in story_farms.values():
            members = self.env["spp.group.membership"].search([("group", "=", farm.id)])
            self.assertGreaterEqual(len(members), 1)

    def test_create_farm_helper(self):
        """Test _create_farm helper method."""
        wizard = self.Generator.create(
            {
                "name": _unique("Create Farm Test"),
            }
        )

        farm_type_id = wizard._get_vocab_code("urn:openspp:vocab:farm-type", "crop")
        holder_type_id = wizard._get_vocab_code("urn:openspp:vocab:holder-type", "individual")
        tenure_id = wizard._get_vocab_code("urn:openspp:vocab:land-tenure", "self")

        if all([farm_type_id, holder_type_id, tenure_id]):
            farm = wizard._create_farm(
                name="Test Farm",
                farmer_name="Test Farmer",
                farm_type_id=farm_type_id,
                holder_type_id=holder_type_id,
                land_tenure_id=tenure_id,
                farm_total_size=3.0,
                farm_size_under_crops=2.5,
                experience_years=10,
                is_female=True,
            )

            self.assertEqual(farm.name, "Test Farm")
            self.assertTrue(farm.is_group)
            self.assertEqual(farm.farm_total_size, 3.0)

    def test_maria_santos_profile(self):
        """Test Maria Santos persona - smallholder rice farmer."""
        wizard = self.Generator.create(
            {
                "name": _unique("Maria Test"),
            }
        )

        story_farms = wizard._create_story_farms()
        maria_farm = story_farms.get("maria_santos")

        self.assertIsNotNone(maria_farm)
        self.assertEqual(maria_farm.name, "Santos Farm")
        self.assertEqual(maria_farm.farm_total_size, 2.0)
        self.assertEqual(maria_farm.farm_size_under_crops, 2.0)

    def test_danilo_villanueva_profile(self):
        """Test Danilo Villanueva persona - large mixed farm."""
        wizard = self.Generator.create(
            {
                "name": _unique("Danilo Test"),
            }
        )

        story_farms = wizard._create_story_farms()
        danilo_farm = story_farms.get("danilo_villanueva")

        self.assertIsNotNone(danilo_farm)
        self.assertEqual(danilo_farm.name, "Villanueva Farm")
        self.assertEqual(danilo_farm.farm_total_size, 5.0)

    def test_story_farms_returns_dict(self):
        """Test _create_story_farms returns dict keyed by story_id."""
        wizard = self.Generator.create(
            {
                "name": _unique("Dict Test"),
            }
        )

        story_farms = wizard._create_story_farms()

        self.assertIsInstance(story_farms, dict)
        self.assertIn("maria_santos", story_farms)
        self.assertIn("amir_mangudadatu", story_farms)
        self.assertIn("ramon_dela_cruz", story_farms)
        self.assertIn("sittie_pangandaman", story_farms)


@tagged("post_install", "-at_install")
class TestFarmerDemoGeneratorFullRun(TransactionCase):
    """Test full demo generation workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._test_id = int(time.time() * 1000)
        cls.Generator = cls.env["spp.farmer.demo.generator"]

    def test_action_generate_demo_returns_notification(self):
        """Test action_generate_demo returns notification."""
        wizard = self.Generator.create(
            {
                "name": _unique("Full Run Test"),
                "create_demo_farms": False,
                "create_active_season": True,
                "generate_volume": False,
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "create_cycles": False,
            }
        )

        result = wizard.action_generate_demo()

        self.assertEqual(result["type"], "ir.actions.client")
        self.assertEqual(result["tag"], "display_notification")
        self.assertEqual(result["params"]["type"], "success")

    def test_action_generate_demo_season_only(self):
        """Test generating only season."""
        wizard = self.Generator.create(
            {
                "name": _unique("Season Only Test"),
                "create_demo_farms": False,
                "create_active_season": True,
                "generate_volume": False,
                "create_demo_programs": False,
                "enroll_demo_stories": False,
                "create_cycles": False,
            }
        )

        result = wizard.action_generate_demo()

        self.assertIn("season", result["params"]["message"].lower())


@tagged("post_install", "-at_install")
class TestDemoProgramsHelpers(TransactionCase):
    """Test demo_programs.py utility functions."""

    def test_get_all_demo_programs(self):
        """get_all_demo_programs should return list of program dicts."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_all_demo_programs,
        )

        programs = get_all_demo_programs()
        self.assertIsInstance(programs, list)
        self.assertGreaterEqual(len(programs), 5)
        for prog in programs:
            self.assertIn("id", prog)
            self.assertIn("name", prog)

    def test_get_demo_program_by_id_found(self):
        """get_demo_program_by_id should find existing program."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_demo_program_by_id,
        )

        prog = get_demo_program_by_id("input_subsidy")
        self.assertIsNotNone(prog)
        self.assertEqual(prog["id"], "input_subsidy")
        self.assertEqual(prog["name"], "Input Subsidy Program")

    def test_get_demo_program_by_id_not_found(self):
        """get_demo_program_by_id returns None for unknown ID."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_demo_program_by_id,
        )

        self.assertIsNone(get_demo_program_by_id("nonexistent"))

    def test_get_demo_program_by_name_found(self):
        """get_demo_program_by_name should find existing program."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_demo_program_by_name,
        )

        prog = get_demo_program_by_name("Input Subsidy Program")
        self.assertIsNotNone(prog)
        self.assertEqual(prog["id"], "input_subsidy")

    def test_get_demo_program_by_name_not_found(self):
        """get_demo_program_by_name returns None for unknown name."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_demo_program_by_name,
        )

        self.assertIsNone(get_demo_program_by_name("Nonexistent Program"))

    def test_get_programs_for_story(self):
        """get_programs_for_story returns programs for a story ID."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_programs_for_story,
        )

        programs = get_programs_for_story("maria_santos")
        self.assertIsInstance(programs, list)
        self.assertGreaterEqual(len(programs), 1)
        prog_ids = [p["id"] for p in programs]
        self.assertIn("input_subsidy", prog_ids)

    def test_get_programs_for_story_unknown(self):
        """get_programs_for_story returns empty for unknown story."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_programs_for_story,
        )

        programs = get_programs_for_story("nonexistent_story")
        self.assertEqual(programs, [])

    def test_get_story_enrollments(self):
        """get_story_enrollments returns enrollment details."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_story_enrollments,
        )

        enrollments = get_story_enrollments("maria_santos")
        self.assertIsInstance(enrollments, list)
        self.assertGreaterEqual(len(enrollments), 1)
        enrollment = enrollments[0]
        self.assertIn("program", enrollment)
        self.assertIn("enrolled_days_back", enrollment)
        self.assertIn("payments", enrollment)

    def test_get_story_enrollments_unknown(self):
        """get_story_enrollments returns empty for unknown story."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_story_enrollments,
        )

        self.assertEqual(get_story_enrollments("nonexistent"), [])

    def test_get_cycles_needed_per_program(self):
        """_get_cycles_needed_per_program returns max payment counts."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            _get_cycles_needed_per_program,
        )

        needed = _get_cycles_needed_per_program()
        self.assertIsInstance(needed, dict)
        # Maria Santos has 3 payments for Input Subsidy Program
        self.assertGreaterEqual(needed.get("Input Subsidy Program", 0), 3)

    def test_story_enrollments_have_valid_programs(self):
        """All story enrollment program names must match demo program names."""
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            DEMO_PROGRAMS,
            STORY_ENROLLMENTS,
        )

        valid_names = {p["name"] for p in DEMO_PROGRAMS}
        for story_id, enrollments in STORY_ENROLLMENTS.items():
            for enrollment in enrollments:
                self.assertIn(
                    enrollment["program"],
                    valid_names,
                    f"Story {story_id} references unknown program: {enrollment['program']}",
                )


@tagged("post_install", "-at_install")
class TestBlueprintHelpers(TransactionCase):
    """Test blueprint helper functions."""

    def test_get_total_member_count(self):
        """get_total_member_count should return reasonable count."""
        from odoo.addons.spp_farmer_registry_demo.models.farmer_blueprints import (
            get_total_member_count,
        )

        total = get_total_member_count()
        self.assertGreaterEqual(total, 1000)
        self.assertLessEqual(total, 3000)


@tagged("post_install", "-at_install")
class TestDemoGeneratorGIS(TransactionCase):
    """Test GIS data generation methods on the demo generator."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.Generator = cls.env["spp.farmer.demo.generator"]

    def test_generate_farm_polygon(self):
        """_generate_farm_polygon should return valid GeoJSON polygon."""
        import json

        wizard = self.Generator.create({"name": _unique("Polygon Test")})
        result = wizard._generate_farm_polygon(121.0, 14.5, 2.0)
        geojson = json.loads(result)
        self.assertEqual(geojson["type"], "Polygon")
        ring = geojson["coordinates"][0]
        self.assertEqual(len(ring), 5)
        self.assertEqual(ring[0], ring[-1])

    def test_create_demo_areas(self):
        """_create_demo_areas should create Philippine provinces."""
        wizard = self.Generator.create({"name": _unique("Areas Test")})
        area_map = wizard._create_demo_areas()
        self.assertIsInstance(area_map, dict)
        if area_map:
            for code, area in area_map.items():
                self.assertTrue(code.startswith("PH-"))
                self.assertTrue(area.exists())

    def test_ensure_land_use_vocabularies(self):
        """_ensure_land_use_vocabularies should create vocab codes without error."""
        wizard = self.Generator.create({"name": _unique("LandUse Test")})
        wizard._ensure_land_use_vocabularies()
        # Verify at least one code exists
        code = self.env["spp.vocabulary.code"].search(
            [("namespace_uri", "=", "urn:openspp:vocab:land-use"), ("code", "=", "cultivation")],
            limit=1,
        )
        self.assertTrue(code)

    def test_compute_demo_already_loaded(self):
        """_compute_demo_already_loaded should reflect config parameter."""
        wizard = self.Generator.create({"name": _unique("Loaded Test")})
        # Clear the param
        self.env["ir.config_parameter"].sudo().set_param("spp.farmer.demo.loaded", "False")
        wizard._compute_demo_already_loaded()
        self.assertFalse(wizard.demo_already_loaded)

        # Set the param
        self.env["ir.config_parameter"].sudo().set_param("spp.farmer.demo.loaded", "True")
        wizard._compute_demo_already_loaded()
        self.assertTrue(wizard.demo_already_loaded)


@tagged("post_install", "-at_install")
class TestFarmerDemoProgramConfiguration(TransactionCase):
    """Program managers wired by the demo generator (OP#915 round 7).

    Covers compliance-manager creation and formula-based cash entitlement
    line items, plus the cycle/entitlement approver demo user.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                mail_create_nolog=True,
            )
        )
        cls.Generator = cls.env["spp.farmer.demo.generator"]

    def _program_def(self, program_id):
        from odoo.addons.spp_farmer_registry_demo.models.demo_programs import (
            get_demo_program_by_id,
        )

        return get_demo_program_by_id(program_id)

    def test_compliance_manager_created_with_cel(self):
        """Programs that ship a compliance CEL get a compliance manager.

        The base create wizard never makes one; the generator must enable
        compliance verification so the manager exists and carries the rule.
        """
        wizard = self.Generator.create({"name": _unique("Compliance Test")})
        program_def = self._program_def("input_subsidy")
        program = wizard._create_program_via_wizard(program_def)

        self.assertTrue(program, "Program should be created")
        self.assertTrue(
            program.compliance_manager_ids,
            "A compliance manager should be created for a program with a compliance CEL",
        )
        concrete = program.compliance_manager_ids[0].manager_ref_id
        self.assertEqual(
            concrete.compliance_cel_expression,
            program_def["compliance_cel_expression"],
            "Compliance manager must carry the program's compliance CEL expression",
        )

    def test_entitlement_formula_lines_per_hectare(self):
        """Input Subsidy entitlement = base line + per-hectare multiplier line."""
        wizard = self.Generator.create({"name": _unique("Formula Test PH")})
        program = wizard._create_program_via_wizard(self._program_def("input_subsidy"))

        entitlement_manager = program.get_manager(program.MANAGER_ENTITLEMENT)
        items = entitlement_manager.entitlement_item_ids
        self.assertEqual(len(items), 2, "Input Subsidy should have a base + per-hectare line")

        base = items.filtered(lambda i: not i.multiplier_field)
        scaled = items.filtered(lambda i: i.multiplier_field)
        self.assertEqual(base.amount, 100.0)
        self.assertEqual(scaled.amount, 50.0)
        self.assertEqual(
            scaled.multiplier_field.name,
            "farm_size_hectares",
            "Per-hectare line must multiply by farm_size_hectares",
        )

    def test_entitlement_formula_lines_per_head(self):
        """Livestock entitlement = base line + per-head multiplier line."""
        wizard = self.Generator.create({"name": _unique("Formula Test Head")})
        program = wizard._create_program_via_wizard(self._program_def("livestock_support"))

        entitlement_manager = program.get_manager(program.MANAGER_ENTITLEMENT)
        items = entitlement_manager.entitlement_item_ids
        self.assertEqual(len(items), 2, "Livestock should have a base + per-head line")

        scaled = items.filtered(lambda i: i.multiplier_field)
        self.assertEqual(scaled.amount, 10.0)
        self.assertEqual(
            scaled.multiplier_field.name,
            "total_livestock_heads",
            "Per-head line must multiply by total_livestock_heads",
        )

    def test_flat_program_keeps_single_line(self):
        """A program without an entitlement_items spec keeps its flat amount."""
        wizard = self.Generator.create({"name": _unique("Flat Test")})
        program = wizard._create_program_via_wizard(self._program_def("equipment_grant"))

        entitlement_manager = program.get_manager(program.MANAGER_ENTITLEMENT)
        items = entitlement_manager.entitlement_item_ids
        self.assertEqual(len(items), 1, "Equipment Grant is a flat grant — one line")
        self.assertFalse(items.multiplier_field, "Flat grant line has no multiplier")

    def test_program_manager_demo_user_can_approve_and_enqueue(self):
        """The Program Manager demo user holds the groups needed to approve a
        cycle (program manager) and enqueue the entitlement-validation job
        (queue.job create → queue job manager)."""
        user = self.env.ref("spp_farmer_registry_demo.demo_user_program_manager")
        self.assertTrue(
            user.has_group("spp_programs.group_programs_manager"),
            "Approver must be a Program Manager to satisfy the cycle approval definition",
        )
        self.assertTrue(
            user.has_group("job_worker.group_queue_job_manager"),
            "Approver must have queue job manager rights to enqueue entitlement validation",
        )
