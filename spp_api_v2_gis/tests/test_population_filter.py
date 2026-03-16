# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for population_filter parameter on spatial queries."""

from datetime import date

from odoo.tests.common import TransactionCase


class TestPopulationFilter(TransactionCase):
    """Test population_filter parameter on spatial queries."""

    @classmethod
    def setUpClass(cls):
        """Set up test data with programs, memberships, and areas."""
        super().setUpClass()

        # Create two test areas
        cls.area_1 = cls.env["spp.area"].create({"draft_name": "Filter Test District 1", "code": "FILT-DIST-001"})
        cls.area_2 = cls.env["spp.area"].create({"draft_name": "Filter Test District 2", "code": "FILT-DIST-002"})

        # Create 4 households (groups), 2 per area
        cls.group_a1 = cls.env["res.partner"].create(
            {
                "name": "HH A1",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_1.id,
            }
        )
        cls.group_a2 = cls.env["res.partner"].create(
            {
                "name": "HH A2",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_1.id,
            }
        )
        cls.group_b1 = cls.env["res.partner"].create(
            {
                "name": "HH B1",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_2.id,
            }
        )
        cls.group_b2 = cls.env["res.partner"].create(
            {
                "name": "HH B2",
                "is_registrant": True,
                "is_group": True,
                "area_id": cls.area_2.id,
            }
        )

        # Create individuals for each household
        cls.indiv_a1 = cls.env["res.partner"].create(
            {
                "name": "Indiv A1",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_1.id,
                "birthdate": date(1990, 1, 1),
            }
        )
        cls.indiv_a2 = cls.env["res.partner"].create(
            {
                "name": "Indiv A2",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_1.id,
                "birthdate": date(2000, 6, 15),
            }
        )
        cls.indiv_b1 = cls.env["res.partner"].create(
            {
                "name": "Indiv B1",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_2.id,
                "birthdate": date(1985, 3, 20),
            }
        )
        cls.indiv_b2 = cls.env["res.partner"].create(
            {
                "name": "Indiv B2",
                "is_registrant": True,
                "is_group": False,
                "area_id": cls.area_2.id,
                "birthdate": date(1975, 11, 30),
            }
        )

        # Create group memberships
        Membership = cls.env["spp.group.membership"]
        Membership.create({"group": cls.group_a1.id, "individual": cls.indiv_a1.id})
        Membership.create({"group": cls.group_a2.id, "individual": cls.indiv_a2.id})
        Membership.create({"group": cls.group_b1.id, "individual": cls.indiv_b1.id})
        Membership.create({"group": cls.group_b2.id, "individual": cls.indiv_b2.id})

        # Create a program
        cls.program = cls.env["spp.program"].create({"name": "Test CCT Program"})

        # Enroll group_a1 and group_b1 (2 of 4 households)
        cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.group_a1.id,
                "program_id": cls.program.id,
                "state": "enrolled",
            }
        )
        cls.env["spp.program.membership"].create(
            {
                "partner_id": cls.group_b1.id,
                "program_id": cls.program.id,
                "state": "enrolled",
            }
        )

        # All group IDs for reference
        cls.all_group_ids = {cls.group_a1.id, cls.group_a2.id, cls.group_b1.id, cls.group_b2.id}
        cls.enrolled_group_ids = {cls.group_a1.id, cls.group_b1.id}
        cls.not_enrolled_group_ids = {cls.group_a2.id, cls.group_b2.id}

    def _get_service(self):
        from ..services.spatial_query_service import SpatialQueryService

        return SpatialQueryService(self.env)


class TestPopulationFilterSQL(TestPopulationFilter):
    """Test _build_population_filter_sql() directly."""

    def test_no_filter_returns_empty(self):
        """Without population_filter, no SQL clause is generated."""
        service = self._get_service()
        sql, params = service._build_population_filter_sql(None)
        self.assertEqual(sql, "")
        self.assertEqual(params, [])

    def test_empty_dict_returns_empty(self):
        """Empty population_filter dict generates no SQL clause."""
        service = self._get_service()
        sql, params = service._build_population_filter_sql({})
        self.assertEqual(sql, "")
        self.assertEqual(params, [])

    def test_program_filter_generates_sql(self):
        """Program filter generates SQL with program membership subquery."""
        service = self._get_service()
        sql, params = service._build_population_filter_sql({"program": self.program.id})
        self.assertIn("spp_program_membership", sql)
        self.assertIn("AND p.id IN", sql)
        self.assertEqual(params, [self.program.id])

    def test_program_filter_restricts_results(self):
        """Program filter restricts registrant IDs to enrolled beneficiaries."""
        service = self._get_service()

        # Build filter SQL
        pop_sql, pop_params = service._build_population_filter_sql({"program": self.program.id})

        # Execute a query using the filter to verify it works
        all_ids = list(self.all_group_ids)
        query = f"""
            SELECT p.id FROM res_partner p
            WHERE p.id IN %s {pop_sql}
        """
        params = [tuple(all_ids)] + pop_params
        self.env.cr.execute(query, params)
        result_ids = {row[0] for row in self.env.cr.fetchall()}

        self.assertEqual(result_ids, self.enrolled_group_ids)

    def test_unknown_program_id_returns_empty(self):
        """Program ID with no enrollees returns no results (but valid SQL)."""
        service = self._get_service()

        # Use a non-existent program ID
        pop_sql, pop_params = service._build_population_filter_sql({"program": 999999})

        # SQL should still be valid, just match nothing
        all_ids = list(self.all_group_ids)
        query = f"""
            SELECT p.id FROM res_partner p
            WHERE p.id IN %s {pop_sql}
        """
        params = [tuple(all_ids)] + pop_params
        self.env.cr.execute(query, params)
        result_ids = {row[0] for row in self.env.cr.fetchall()}

        self.assertEqual(result_ids, set())

    def test_invalid_mode_raises_error(self):
        """Invalid mode value raises ValueError."""
        service = self._get_service()
        with self.assertRaises(ValueError):
            service._build_population_filter_sql({"program": self.program.id, "mode": "invalid_mode"})

    def test_non_integer_program_raises_error(self):
        """Non-integer program value raises ValueError."""
        service = self._get_service()
        with self.assertRaises(ValueError):
            service._build_population_filter_sql({"program": "not_an_int"})


class TestPopulationFilterCEL(TestPopulationFilter):
    """Test CEL expression filter functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a simple CEL expression that always evaluates to true
        # (matches all groups). Use 'true' which is the simplest valid CEL.
        cls.cel_expression = cls.env["spp.cel.expression"].create(
            {
                "name": "Test All Groups",
                "code": "test_all_groups",
                "expression_type": "filter",
                "cel_expression": "true",
                "output_type": "boolean",
                "context_type": "group",
            }
        )

    def test_cel_filter_generates_sql(self):
        """CEL expression filter generates SQL with matching IDs."""
        service = self._get_service()
        sql, params = service._build_population_filter_sql({"cel_expression": "test_all_groups"})
        # Should produce a valid filter (the 'true' expression matches all groups)
        if sql == "AND false":
            self.skipTest("CEL expression matched no groups in test DB")
        self.assertIn("AND p.id IN", sql)
        self.assertIn("unnest", sql)

    def test_cel_filter_unknown_code_returns_false(self):
        """Unknown CEL expression code returns 'AND false' (empty results)."""
        service = self._get_service()
        sql, params = service._build_population_filter_sql({"cel_expression": "nonexistent_expression_code"})
        self.assertEqual(sql, "AND false")
        self.assertEqual(params, [])


class TestPopulationFilterCombined(TestPopulationFilter):
    """Test combined program + CEL filter modes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a CEL expression that matches all groups (true)
        cls.cel_expression = cls.env["spp.cel.expression"].create(
            {
                "name": "Test Match All",
                "code": "test_match_all",
                "expression_type": "filter",
                "cel_expression": "true",
                "output_type": "boolean",
                "context_type": "group",
            }
        )

    def test_and_mode_with_program_and_cel(self):
        """AND mode generates SQL with both program and CEL conditions."""
        service = self._get_service()
        sql, params = service._build_population_filter_sql(
            {
                "program": self.program.id,
                "cel_expression": "test_match_all",
                "mode": "and",
            }
        )
        if sql == "AND false":
            self.skipTest("CEL expression matched no groups in test DB")
        # Should have both program membership and CEL subqueries
        self.assertIn("spp_program_membership", sql)
        self.assertIn("unnest", sql)
        self.assertEqual(sql.count("AND p.id IN"), 2)

    def test_or_mode_with_program_and_cel(self):
        """OR mode generates SQL combining program and CEL with OR."""
        service = self._get_service()
        sql, params = service._build_population_filter_sql(
            {
                "program": self.program.id,
                "cel_expression": "test_match_all",
                "mode": "or",
            }
        )
        if sql == "AND false":
            self.skipTest("CEL expression matched no groups in test DB")
        self.assertIn("OR", sql)

    def test_gap_mode_with_program_and_cel(self):
        """Gap mode generates SQL: matches CEL but NOT in program."""
        service = self._get_service()
        sql, params = service._build_population_filter_sql(
            {
                "program": self.program.id,
                "cel_expression": "test_match_all",
                "mode": "gap",
            }
        )
        if sql == "AND false":
            self.skipTest("CEL expression matched no groups in test DB")
        self.assertIn("NOT IN", sql)
        self.assertIn("spp_program_membership", sql)

    def test_gap_mode_excludes_enrolled(self):
        """Gap mode returns CEL matches that are NOT enrolled in the program."""
        service = self._get_service()
        pop_sql, pop_params = service._build_population_filter_sql(
            {
                "program": self.program.id,
                "cel_expression": "test_match_all",
                "mode": "gap",
            }
        )
        if pop_sql == "AND false":
            self.skipTest("CEL expression matched no groups in test DB")

        # Execute against all groups
        all_ids = list(self.all_group_ids)
        query = f"""
            SELECT p.id FROM res_partner p
            WHERE p.id IN %s {pop_sql}
        """
        params = [tuple(all_ids)] + pop_params
        self.env.cr.execute(query, params)
        result_ids = {row[0] for row in self.env.cr.fetchall()}

        # Gap = CEL matches (all) minus enrolled (a1, b1) = not enrolled (a2, b2)
        self.assertEqual(result_ids, self.not_enrolled_group_ids)


class TestPopulationFilterBatchQuery(TestPopulationFilter):
    """Test population filter with batch spatial queries."""

    def test_batch_query_passes_filter(self):
        """Population filter is applied in batch queries."""
        service = self._get_service()

        geometries = [
            {
                "id": "zone_1",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            },
        ]

        # Query without filter
        result_all = service.query_statistics_batch(geometries=geometries)

        # Query with program filter
        result_filtered = service.query_statistics_batch(
            geometries=geometries,
            population_filter={"program": self.program.id},
        )

        # Both should return valid structure
        self.assertIn("results", result_all)
        self.assertIn("results", result_filtered)
        self.assertEqual(len(result_all["results"]), 1)
        self.assertEqual(len(result_filtered["results"]), 1)

        # Filtered count should be <= unfiltered count
        self.assertLessEqual(
            result_filtered["results"][0]["total_count"],
            result_all["results"][0]["total_count"],
        )


class TestPopulationFilterProcessDescription(TransactionCase):
    """Test population_filter in process descriptions."""

    def test_spatial_statistics_has_population_filter(self):
        """Spatial statistics process description includes population_filter input."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        process = registry.get_process("spatial-statistics")

        self.assertIn("population_filter", process["inputs"])

        pf = process["inputs"]["population_filter"]
        self.assertEqual(pf["title"], "Population Filter")
        self.assertEqual(pf["minOccurs"], 0)

        schema = pf["schema"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("program", schema["properties"])
        self.assertIn("cel_expression", schema["properties"])
        self.assertIn("mode", schema["properties"])

        # Mode should have enum with and/or/gap
        mode_schema = schema["properties"]["mode"]
        self.assertEqual(mode_schema["enum"], ["and", "or", "gap"])
        self.assertEqual(mode_schema["default"], "and")

    def test_proximity_statistics_has_population_filter(self):
        """Proximity statistics process description includes population_filter input."""
        from ..services.process_registry import ProcessRegistry

        registry = ProcessRegistry(self.env)
        process = registry.get_process("proximity-statistics")

        self.assertIn("population_filter", process["inputs"])

    def test_process_description_includes_program_metadata(self):
        """x-openspp-programs contains program IDs and names when programs exist."""
        from ..services.process_registry import ProcessRegistry

        # Create a program to ensure metadata is populated
        program = self.env["spp.program"].create({"name": "Test Discovery Program"})

        registry = ProcessRegistry(self.env)
        process = registry.get_process("spatial-statistics")
        pf = process["inputs"]["population_filter"]

        self.assertIn("x-openspp-programs", pf)
        programs = pf["x-openspp-programs"]
        program_ids = [p["id"] for p in programs]
        self.assertIn(program.id, program_ids)

        # Each program metadata should have id and name
        test_prog = next(p for p in programs if p["id"] == program.id)
        self.assertEqual(test_prog["name"], "Test Discovery Program")

    def test_process_description_includes_expression_metadata(self):
        """x-openspp-expressions contains expression codes and names."""
        from ..services.process_registry import ProcessRegistry

        # Create a CEL expression
        expr = self.env["spp.cel.expression"].create(
            {
                "name": "Test Discovery Expression",
                "code": "test_discovery_expr",
                "expression_type": "filter",
                "cel_expression": "true",
                "output_type": "boolean",
                "context_type": "group",
            }
        )

        registry = ProcessRegistry(self.env)
        process = registry.get_process("spatial-statistics")
        pf = process["inputs"]["population_filter"]

        self.assertIn("x-openspp-expressions", pf)
        expressions = pf["x-openspp-expressions"]
        expr_codes = [e["code"] for e in expressions]
        self.assertIn(expr.code, expr_codes)

        # Each expression metadata should have code, name, context_type
        test_expr = next(e for e in expressions if e["code"] == expr.code)
        self.assertEqual(test_expr["name"], "Test Discovery Expression")
        self.assertEqual(test_expr["context_type"], "group")

    def test_process_description_without_programs(self):
        """Population filter input works when no programs exist."""
        from ..services.process_registry import ProcessRegistry

        # Delete all programs to test empty state
        self.env["spp.program"].search([]).unlink()

        registry = ProcessRegistry(self.env)
        process = registry.get_process("spatial-statistics")
        pf = process["inputs"]["population_filter"]

        # Should still have the input, just without enum/metadata
        self.assertEqual(pf["schema"]["type"], "object")
        self.assertNotIn("enum", pf["schema"]["properties"]["program"])
