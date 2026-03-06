# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for geofence-based eligibility manager."""

import json

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGeofenceEligibility(TransactionCase):
    """Test the geofence eligibility manager with spatial queries."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                test_queue_job_no_delay=True,
                tracking_disable=True,
            )
        )

        # -- Geofence: a box from (100, 0) to (101, 1) --
        cls.geofence_geojson = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [[100, 0], [101, 0], [101, 1], [100, 1], [100, 0]]
                ],
            }
        )
        cls.geofence = cls.env["spp.gis.geofence"].create(
            {
                "name": "Test Geofence",
                "geometry": cls.geofence_geojson,
                "geofence_type": "custom",
            }
        )

        # -- Second geofence: a box from (110, 10) to (111, 11) --
        cls.geofence2_geojson = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [
                    [[110, 10], [111, 10], [111, 11], [110, 11], [110, 10]]
                ],
            }
        )
        cls.geofence2 = cls.env["spp.gis.geofence"].create(
            {
                "name": "Test Geofence 2",
                "geometry": cls.geofence2_geojson,
                "geofence_type": "custom",
            }
        )

        # -- Area that overlaps the first geofence --
        cls.area_type = cls.env["spp.area.type"].create({"name": "Test District"})
        cls.area_inside = cls.env["spp.area"].create(
            {
                "draft_name": "Area Inside",
                "code": "AREA_IN",
                "area_type_id": cls.area_type.id,
                "geo_polygon": json.dumps(
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [100.2, 0.2],
                                [100.8, 0.2],
                                [100.8, 0.8],
                                [100.2, 0.8],
                                [100.2, 0.2],
                            ]
                        ],
                    }
                ),
            }
        )

        # -- Area that does NOT overlap the first geofence --
        cls.area_outside = cls.env["spp.area"].create(
            {
                "draft_name": "Area Outside",
                "code": "AREA_OUT",
                "area_type_id": cls.area_type.id,
                "geo_polygon": json.dumps(
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [50, 50],
                                [51, 50],
                                [51, 51],
                                [50, 51],
                                [50, 50],
                            ]
                        ],
                    }
                ),
            }
        )

        # -- Registrants --
        point_inside = json.dumps(
            {"type": "Point", "coordinates": [100.5, 0.5]}
        )
        point_outside = json.dumps(
            {"type": "Point", "coordinates": [50, 50]}
        )
        point_in_geofence2 = json.dumps(
            {"type": "Point", "coordinates": [110.5, 10.5]}
        )

        cls.reg_inside = cls.env["res.partner"].create(
            {
                "name": "Inside Registrant",
                "is_registrant": True,
                "is_group": False,
                "coordinates": point_inside,
            }
        )
        cls.reg_outside = cls.env["res.partner"].create(
            {
                "name": "Outside Registrant",
                "is_registrant": True,
                "is_group": False,
                "coordinates": point_outside,
            }
        )
        cls.reg_no_coords_in_area = cls.env["res.partner"].create(
            {
                "name": "No Coords In Area",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_inside.id,
            }
        )
        cls.reg_no_coords_out_area = cls.env["res.partner"].create(
            {
                "name": "No Coords Out Area",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_outside.id,
            }
        )
        cls.reg_in_geofence2 = cls.env["res.partner"].create(
            {
                "name": "In Geofence 2",
                "is_registrant": True,
                "is_group": False,
                "coordinates": point_in_geofence2,
            }
        )
        cls.reg_disabled = cls.env["res.partner"].create(
            {
                "name": "Disabled Registrant",
                "is_registrant": True,
                "is_group": False,
                "disabled": True,
                "coordinates": point_inside,
            }
        )
        # Registrant with BOTH coordinates inside AND area inside
        cls.reg_both = cls.env["res.partner"].create(
            {
                "name": "Both Coords And Area",
                "is_registrant": True,
                "is_group": False,
                "coordinates": point_inside,
                "area_id": cls.area_inside.id,
            }
        )
        # Group registrant (for target_type tests)
        cls.group_reg = cls.env["res.partner"].create(
            {
                "name": "Group Registrant",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_inside.id,
            }
        )

        # -- Program --
        cls.program = cls.env["spp.program"].create(
            {
                "name": "Geofence Test Program",
                "target_type": "individual",
                "geofence_ids": [(6, 0, [cls.geofence.id])],
            }
        )

        # -- Geofence Eligibility Manager --
        cls.manager = cls.env["spp.program.membership.manager.geofence"].create(
            {
                "name": "Test Geofence Manager",
                "program_id": cls.program.id,
            }
        )

    # --- Manager registration ---

    def test_manager_selection_registered(self):
        """Geofence Eligibility appears in the manager selection."""
        selection = self.env["spp.eligibility.manager"]._selection_manager_ref_id()
        manager_names = [s[0] for s in selection]
        self.assertIn("spp.program.membership.manager.geofence", manager_names)

    # --- Tier 1: coordinate-based ---

    def test_tier1_coordinates_inside(self):
        """Registrant with coordinates inside geofence is eligible."""
        eligible = self.manager._find_eligible_registrants()
        self.assertIn(self.reg_inside, eligible)

    def test_tier1_coordinates_outside(self):
        """Registrant with coordinates outside geofence is not eligible."""
        eligible = self.manager._find_eligible_registrants()
        self.assertNotIn(self.reg_outside, eligible)

    def test_tier1_no_coordinates_not_matched(self):
        """Registrant without coordinates is not matched by Tier 1 alone."""
        self.manager.include_area_fallback = False
        eligible = self.manager._find_eligible_registrants()
        self.assertNotIn(self.reg_no_coords_in_area, eligible)
        # Restore
        self.manager.include_area_fallback = True

    # --- Tier 2: area fallback ---

    def test_tier2_area_intersects(self):
        """Registrant in intersecting area is eligible via fallback."""
        eligible = self.manager._find_eligible_registrants()
        self.assertIn(self.reg_no_coords_in_area, eligible)

    def test_tier2_area_no_intersection(self):
        """Registrant in non-intersecting area is not eligible."""
        eligible = self.manager._find_eligible_registrants()
        self.assertNotIn(self.reg_no_coords_out_area, eligible)

    def test_tier2_disabled(self):
        """When include_area_fallback=False, Tier 2 is skipped."""
        self.manager.include_area_fallback = False
        eligible = self.manager._find_eligible_registrants()
        self.assertNotIn(self.reg_no_coords_in_area, eligible)
        # Restore
        self.manager.include_area_fallback = True

    # --- Hybrid union ---

    def test_hybrid_no_duplicates(self):
        """Registrant matched by both tiers appears only once."""
        eligible = self.manager._find_eligible_registrants()
        count = len([r for r in eligible if r.id == self.reg_both.id])
        self.assertEqual(count, 1)

    # --- Multiple geofences ---

    def test_multiple_geofences(self):
        """Registrant in second geofence is eligible."""
        self.program.geofence_ids = [(6, 0, [self.geofence.id, self.geofence2.id])]
        eligible = self.manager._find_eligible_registrants()
        self.assertIn(self.reg_in_geofence2, eligible)
        self.assertIn(self.reg_inside, eligible)
        # Restore
        self.program.geofence_ids = [(6, 0, [self.geofence.id])]

    # --- No geofences ---

    def test_no_geofences_empty_result(self):
        """Program with no geofences returns no eligible registrants."""
        self.program.geofence_ids = [(5, 0, 0)]
        eligible = self.manager._find_eligible_registrants()
        self.assertEqual(len(eligible), 0)
        # Restore
        self.program.geofence_ids = [(6, 0, [self.geofence.id])]

    # --- Enrollment pipeline ---

    def test_enroll_eligible_registrants(self):
        """enroll_eligible_registrants filters memberships to eligible partners."""
        membership = self.env["spp.program.membership"].create(
            {
                "partner_id": self.reg_inside.id,
                "program_id": self.program.id,
                "state": "draft",
            }
        )
        membership_outside = self.env["spp.program.membership"].create(
            {
                "partner_id": self.reg_outside.id,
                "program_id": self.program.id,
                "state": "draft",
            }
        )
        result = self.manager.enroll_eligible_registrants(membership | membership_outside)
        self.assertIn(membership, result)
        self.assertNotIn(membership_outside, result)

    def test_import_eligible_registrants(self):
        """import_eligible_registrants creates memberships for eligible registrants."""
        # Use a fresh program to avoid pre-existing memberships
        program2 = self.env["spp.program"].create(
            {
                "name": "Import Test Program",
                "target_type": "individual",
                "geofence_ids": [(6, 0, [self.geofence.id])],
            }
        )
        manager2 = self.env["spp.program.membership.manager.geofence"].create(
            {
                "name": "Import Manager",
                "program_id": program2.id,
            }
        )
        count = manager2.import_eligible_registrants()
        self.assertGreater(count, 0)
        enrolled_partners = program2.program_membership_ids.mapped("partner_id")
        self.assertIn(self.reg_inside, enrolled_partners)
        self.assertNotIn(self.reg_outside, enrolled_partners)

    def test_import_excludes_already_enrolled(self):
        """import_eligible_registrants does not duplicate existing memberships."""
        program3 = self.env["spp.program"].create(
            {
                "name": "Dedup Test Program",
                "target_type": "individual",
                "geofence_ids": [(6, 0, [self.geofence.id])],
            }
        )
        manager3 = self.env["spp.program.membership.manager.geofence"].create(
            {
                "name": "Dedup Manager",
                "program_id": program3.id,
            }
        )
        # First import
        manager3.import_eligible_registrants()
        count1 = len(program3.program_membership_ids)

        # Second import should add nothing
        manager3.import_eligible_registrants()
        count2 = len(program3.program_membership_ids)
        self.assertEqual(count1, count2)

    # --- Disabled registrants ---

    def test_disabled_registrants_excluded(self):
        """Disabled registrants are never eligible."""
        eligible = self.manager._find_eligible_registrants()
        self.assertNotIn(self.reg_disabled, eligible)

    # --- Target type ---

    def test_target_type_individual(self):
        """When target_type is 'individual', groups are excluded."""
        eligible = self.manager._find_eligible_registrants()
        self.assertNotIn(self.group_reg, eligible)

    def test_target_type_group(self):
        """When target_type is 'group', individuals are excluded."""
        self.program.target_type = "group"
        eligible = self.manager._find_eligible_registrants()
        self.assertIn(self.group_reg, eligible)
        self.assertNotIn(self.reg_inside, eligible)
        # Restore
        self.program.target_type = "individual"

    # --- MultiPolygon geometry ---

    def test_multipolygon_geofence(self):
        """Program with multiple non-overlapping geofences uses MultiPolygon via unary_union."""
        self.program.geofence_ids = [(6, 0, [self.geofence.id, self.geofence2.id])]
        eligible = self.manager._find_eligible_registrants()
        # Both registrants from different geofences should be eligible
        self.assertIn(self.reg_inside, eligible)
        self.assertIn(self.reg_in_geofence2, eligible)
        # Outside registrant should not be
        self.assertNotIn(self.reg_outside, eligible)
        # Restore
        self.program.geofence_ids = [(6, 0, [self.geofence.id])]

    # --- Program geofence field ---

    def test_program_geofence_count(self):
        """geofence_count is computed correctly."""
        self.assertEqual(self.program.geofence_count, 1)
        self.program.geofence_ids = [(6, 0, [self.geofence.id, self.geofence2.id])]
        self.assertEqual(self.program.geofence_count, 2)
        # Restore
        self.program.geofence_ids = [(6, 0, [self.geofence.id])]


@tagged("post_install", "-at_install")
class TestGeofenceEligibilityOfficer(TransactionCase):
    """Test geofence eligibility with programs_officer user context."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                test_queue_job_no_delay=True,
                tracking_disable=True,
            )
        )

        # Create officer user
        cls.officer_user = cls.env["res.users"].create(
            {
                "name": "Test Officer",
                "login": "test_geofence_officer",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("spp_programs.group_programs_officer").id,
                            cls.env.ref("base.group_user").id,
                        ],
                    )
                ],
            }
        )

        # Create test data as admin
        cls.geofence = cls.env["spp.gis.geofence"].create(
            {
                "name": "Officer Test Geofence",
                "geometry": json.dumps(
                    {
                        "type": "Polygon",
                        "coordinates": [
                            [[100, 0], [101, 0], [101, 1], [100, 1], [100, 0]]
                        ],
                    }
                ),
                "geofence_type": "custom",
            }
        )

        cls.program = cls.env["spp.program"].create(
            {
                "name": "Officer Test Program",
                "target_type": "individual",
                "geofence_ids": [(6, 0, [cls.geofence.id])],
            }
        )

        cls.manager = cls.env["spp.program.membership.manager.geofence"].create(
            {
                "name": "Officer Manager",
                "program_id": cls.program.id,
            }
        )

    def test_officer_can_read_manager(self):
        """Programs officer can read the geofence eligibility manager."""
        manager_as_officer = self.manager.with_user(self.officer_user)
        self.assertEqual(manager_as_officer.name, "Officer Manager")

    def test_officer_can_create_manager(self):
        """Programs officer can create a geofence eligibility manager."""
        new_manager = (
            self.env["spp.program.membership.manager.geofence"]
            .with_user(self.officer_user)
            .create(
                {
                    "name": "Officer Created Manager",
                    "program_id": self.program.id,
                }
            )
        )
        self.assertTrue(new_manager.id)
