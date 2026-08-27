# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#958 and children: invariants the generated demo data has to hold.

Each of these pins a gap where the demo's state did not back up what the
program forms claimed:

* OP#955 -- blueprints flag members as disabled, but nothing recorded it, so
  every disability-targeted program matched zero households.
* OP#957 -- cycle and entitlement managers were created with no approval
  definition, which is a hard failure rather than a bypass: approving a cycle
  raises "The cycle approval definition is not specified!".
"""

from datetime import date

from odoo.tests import TransactionCase, tagged

HEADLINE_PROGRAMS = [
    "Universal Child Grant",
    "Elderly Social Pension",
    "Cash Transfer Program",
    "Disability Support Grant",
    "Emergency Relief Fund",
    "Food Assistance",
]


@tagged("post_install", "-at_install")
class TestDemoManagerApprovals(TransactionCase):
    """OP#957: every demo program can actually run its approval flows."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.generator = cls.env["spp.mis.demo.generator"].create(
            {
                "name": "OP#957 approvals",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": cls.env.ref("base.us").id,
            }
        )
        cls.generator.action_generate()
        cls.programs = cls.env["spp.program"].search([("name", "in", HEADLINE_PROGRAMS)])

    def test_the_headline_programs_were_created(self):
        """Guards the fixture the rest of this class depends on."""
        self.assertGreaterEqual(len(self.programs), 6)

    def test_every_cycle_manager_has_an_approval_definition(self):
        """Without one, Approve Cycle raises instead of running."""
        missing = []
        for program in self.programs:
            manager = program.get_manager(program.MANAGER_CYCLE)
            if not manager:
                continue
            if not manager.approval_definition_id:
                missing.append(program.name)

        self.assertFalse(missing, f"cycle managers with no approval definition: {missing}")

    def test_every_entitlement_manager_has_an_approval_definition(self):
        """Without one, prepare_entitlements raises instead of running."""
        missing = []
        for program in self.programs:
            manager = program.get_manager(program.MANAGER_ENTITLEMENT)
            if not manager:
                continue
            if not manager.approval_definition_id:
                missing.append(program.name)

        self.assertFalse(missing, f"entitlement managers with no approval definition: {missing}")

    def test_each_definition_targets_the_right_model(self):
        """A definition for the wrong model would pass the domain but never fire."""
        for program in self.programs:
            cycle_manager = program.get_manager(program.MANAGER_CYCLE)
            if cycle_manager and cycle_manager.approval_definition_id:
                self.assertEqual(
                    cycle_manager.approval_definition_id.model_id.model,
                    "spp.cycle",
                    f"{program.name}: cycle manager wired to the wrong model",
                )
            ent_manager = program.get_manager(program.MANAGER_ENTITLEMENT)
            if ent_manager and ent_manager.approval_definition_id:
                self.assertEqual(
                    ent_manager.approval_definition_id.model_id.model,
                    "spp.entitlement",
                    f"{program.name}: entitlement manager wired to the wrong model",
                )

    def test_rerunning_does_not_overwrite_a_deliberate_choice(self):
        """Load Demo is re-runnable; it must not undo configuration done in the UI."""
        program = self.programs[0]
        manager = program.get_manager(program.MANAGER_CYCLE)
        custom = self.env["spp.approval.definition"].create(
            {
                "name": "OP#957 custom cycle workflow",
                "model_id": self.env["ir.model"]._get_id("spp.cycle"),
                "approval_type": "group",
                "approval_group_id": self.env.ref("base.group_user").id,
            }
        )
        manager.approval_definition_id = custom

        self.generator._wire_manager_approvals(program)

        self.assertEqual(manager.approval_definition_id, custom)


@tagged("post_install", "-at_install")
class TestDemoDisabilitySeeding(TransactionCase):
    """OP#955: a blueprint's is_disabled flag has to reach the registry."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.generator = cls.env["spp.mis.demo.generator"].create(
            {"name": "OP#955 disability", "locale_origin": cls.env.ref("base.us").id}
        )

    def _member(self, age, is_disabled):
        return self.generator._create_individual_member(
            {"name": "Test Person", "gender": "female", "age": age, "is_disabled": is_disabled},
            date(2024, 6, 1),
        )

    def test_a_flagged_adult_ends_up_with_a_disability(self):
        """The whole chain: WG answers -> assessment -> approved -> partner."""
        member = self._member(age=40, is_disabled=True)

        self.assertTrue(member.disability_assessment_ids, "no assessment was created")
        assessment = member.disability_assessment_ids[0]
        self.assertEqual(assessment.approval_state, "approved")
        self.assertTrue(assessment.has_disability, "the WG answers do not meet the threshold")
        self.assertEqual(member.current_disability_assessment_id, assessment)
        self.assertTrue(member.has_disability, "res.partner.has_disability did not follow")

    def test_a_flagged_child_uses_the_child_instrument(self):
        """assessment_type follows age, so the answers must match the instrument.

        Filling WG-SS fields on a CFM record would leave the domain count at
        zero and silently produce has_disability=False.
        """
        member = self._member(age=9, is_disabled=True)
        assessment = member.disability_assessment_ids[0]

        self.assertEqual(assessment.assessment_type, "cfm_5_17")
        self.assertTrue(assessment.has_disability)
        self.assertTrue(member.has_disability)

    def test_an_unflagged_member_gets_nothing(self):
        """Only flagged members are affected; the rest stay as they were."""
        member = self._member(age=40, is_disabled=False)

        self.assertFalse(member.disability_assessment_ids)
        self.assertFalse(member.has_disability)

    def test_the_assessment_date_respects_the_model_constraints(self):
        """The model refuses a future date or one before the birthdate.

        Demo registration dates are backdated and a member can be younger than
        the household's registration, so the date needs choosing, not passing
        through.
        """
        member = self._member(age=2, is_disabled=True)
        assessment = member.disability_assessment_ids[0]

        self.assertLessEqual(assessment.assessment_date, date.today())
        self.assertGreaterEqual(assessment.assessment_date, member.birthdate)


@tagged("post_install", "-at_install")
class TestDemoManagerHygiene(TransactionCase):
    """OP#1017: the managers the generator leaves behind have to make sense."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.generator = cls.env["spp.mis.demo.generator"].create(
            {
                "name": "OP#1017 managers",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": False,
                "create_cycles": False,
                "locale_origin": cls.env.ref("base.us").id,
            }
        )
        cls.generator.action_generate()
        cls.programs = cls.env["spp.program"].search([("name", "in", HEADLINE_PROGRAMS)])

    def test_a_dangling_wrapper_is_repaired_on_the_next_run(self):
        """manager_ref_id is a Reference: no foreign key, so it can dangle.

        The old check skipped a whole manager list when it held anything, so a
        wrapper whose concrete record had been deleted was never repaired --
        the card kept offering a method with nothing behind it.
        """
        program = self.programs[0]
        wrapper = program.eligibility_manager_ids[:1]
        self.assertTrue(wrapper, "the fixture needs an eligibility wrapper")
        concrete = wrapper.manager_ref_id
        self.assertTrue(concrete)
        # Delete the concrete out from under the wrapper, the way a manual
        # cleanup in the UI would.
        self.env.cr.execute(
            f"DELETE FROM {concrete._table} WHERE id = %s",  # noqa: S608 - table name from the registry
            (concrete.id,),
        )
        concrete.invalidate_recordset()
        wrapper.invalidate_recordset()

        self.generator._ensure_program_managers(program, {})

        repaired = wrapper.manager_ref_id
        self.assertTrue(repaired, "the wrapper should point at a manager again")
        self.assertTrue(repaired.exists())
        self.assertNotEqual(repaired.id, concrete.id, "it should be a new record, not the deleted one")

    def test_no_inert_compliance_manager_is_created(self):
        """An empty compliance manager is worse than none.

        has_compliance_criteria and the cycle's
        allow_filter_compliance_criteria are both bool(compliance_manager_ids),
        so an inert record makes the UI offer filtering that cannot match.
        """
        import odoo.addons.spp_mis_demo_v2.models.demo_programs as demo_programs

        with_rule = {p["name"] for p in demo_programs.get_all_demo_programs() if p.get("compliance_cel_expression")}
        for program in self.programs:
            if program.name in with_rule:
                self.assertTrue(
                    program.compliance_manager_ids,
                    f"{program.name} has a compliance rule and should have a manager",
                )
            else:
                self.assertFalse(
                    program.compliance_manager_ids,
                    f"{program.name} has no compliance rule; an empty manager would "
                    f"still switch on compliance filtering",
                )

    def test_a_configured_compliance_manager_carries_its_expression(self):
        """The ones that do exist must not be inert either."""
        for program in self.programs:
            for wrapper in program.compliance_manager_ids:
                concrete = wrapper.manager_ref_id
                if concrete and "compliance_cel_expression" in concrete._fields:
                    self.assertTrue(
                        concrete.compliance_cel_expression,
                        f"{program.name}: compliance manager exists but has no expression",
                    )

    def test_orphan_wrappers_are_cleaned_up(self):
        """Archiving a program used to leave its wrappers behind for good."""
        program = self.programs[0]
        wrapper_ids = program.eligibility_manager_ids.ids
        self.assertTrue(wrapper_ids)
        program.active = False

        self.generator._remove_orphan_manager_wrappers()

        survivors = self.env["spp.eligibility.manager"].search([("id", "in", wrapper_ids)])
        self.assertFalse(survivors, "wrappers of an archived program should be gone")

    def test_cleanup_leaves_live_programs_alone(self):
        """The sweep must not touch managers of programs still in use."""
        live = self.programs.filtered(lambda p: p.active)
        before = {p.id: len(p.eligibility_manager_ids) for p in live}

        self.generator._remove_orphan_manager_wrappers()

        for program in live:
            self.assertEqual(
                len(program.eligibility_manager_ids),
                before[program.id],
                f"{program.name} lost a manager to the orphan sweep",
            )


@tagged("post_install", "-at_install")
class TestDemoEnrollmentMatchesEligibility(TransactionCase):
    """OP#956: what a program enrolled and what its CEL matches must agree.

    The demo's whole claim is that CEL drives targeting. That collapsed when a
    program form said 102 households enrolled while its own preview matched 9:
    enrollment came from a static blueprint flag and nothing reconciled the two.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.generator = cls.env["spp.mis.demo.generator"].create(
            {
                "name": "OP#956 enrollment",
                "create_demo_programs": True,
                "enroll_demo_stories": False,
                "generate_volume": True,
                "create_cycles": False,
                "locale_origin": cls.env.ref("base.us").id,
            }
        )
        cls.generator.action_generate()

    def _preview_count(self, program):
        """The count the program form's Preview Beneficiaries would show."""
        expression = None
        for wrapper in program.eligibility_manager_ids:
            concrete = wrapper.manager_ref_id
            if concrete and "cel_expression" in concrete._fields and concrete.cel_expression:
                expression = concrete.cel_expression
                break
        if not expression:
            return None
        profile = "registry_groups" if program.target_type == "group" else "registry_individuals"
        result = self.env["spp.cel.service"].compile_expression(
            expression,
            profile=profile,
            base_domain=[["disabled", "=", False]],
            limit=0,
            materialize_sql=True,
        )
        if not result.get("valid"):
            self.fail(f"{program.name}: eligibility CEL does not compile: {result.get('error')}")
        return result.get("count", 0)

    def _enrolled_count(self, program):
        return self.env["spp.program.membership"].search_count(
            [("program_id", "=", program.id), ("state", "=", "enrolled")]
        )

    def test_enrolled_beneficiaries_all_satisfy_the_eligibility_cel(self):
        """The invariant that actually matters: no enrollee contradicts the CEL.

        Asserting only on counts would pass while enrolling the wrong people,
        so this checks membership of the matched set rather than its size.
        """
        from odoo.addons.spp_mis_demo_v2.models.seeded_volume_generator import SeededVolumeGenerator

        offenders = {}
        for program in self.env["spp.program"].search([("name", "in", HEADLINE_PROGRAMS)]):
            expression = None
            for wrapper in program.eligibility_manager_ids:
                concrete = wrapper.manager_ref_id
                if concrete and "cel_expression" in concrete._fields and concrete.cel_expression:
                    expression = concrete.cel_expression
                    break
            if not expression:
                continue
            # Programs whose CEL is not a targeting rule stay blueprint-driven.
            if any(program.name.lower().startswith(prefix) for prefix in ("food assistance", "emergency relief")):
                continue
            profile = "registry_groups" if program.target_type == "group" else "registry_individuals"
            matched = self.env["spp.cel.service"].compile_expression(
                expression, profile=profile, limit=0, materialize_sql=True
            )
            if not matched.get("valid"):
                continue
            matched_ids = set(self.env["res.partner"].search(matched.get("domain") or []).ids)
            enrolled_ids = set(
                self.env["spp.program.membership"]
                .search([("program_id", "=", program.id), ("state", "=", "enrolled")])
                .mapped("partner_id")
                .ids
            )
            contradicting = enrolled_ids - matched_ids
            if contradicting:
                offenders[program.name] = len(contradicting)

        self.assertFalse(
            offenders,
            f"enrolled beneficiaries that the program's own CEL rejects: {offenders}",
        )
        self.assertTrue(SeededVolumeGenerator.NON_SELECTIVE_CEL_PROGRAMS)

    def test_the_conditional_child_grant_is_no_longer_wildly_off(self):
        """The case the ticket was raised on: preview 9 vs enrolled 102.

        Its CEL wants a member under 2, and three of the four blueprints
        flagged for it produced older children -- one could never match at all.
        """
        program = self.env["spp.program"].search([("name", "=", "Conditional Child Grant")], limit=1)
        self.assertTrue(program, "the fixture needs the CCG program")

        preview = self._preview_count(program)
        enrolled = self._enrolled_count(program)

        self.assertIsNotNone(preview, "CCG should have an eligibility CEL")
        self.assertGreater(enrolled, 0, "CCG enrolled nobody at all")
        self.assertLessEqual(
            enrolled,
            preview,
            f"CCG enrolled {enrolled} but its CEL only matches {preview}",
        )

    def test_matching_and_enrolled_counts_agree(self):
        """The ticket's actual numeric bar, which a set-membership check misses.

        Compared against *all* memberships rather than the enrolled ones: the
        generator deliberately puts about a tenth of them into exited, paused
        or not-eligible for realism, so an enrolled-only comparison sits at the
        edge of the tolerance for reasons that have nothing to do with
        targeting.

        Programs whose rule is not a targeting rule are excluded -- Food
        Assistance matches every active registrant and Emergency Relief Fund
        has no rule at all.
        """
        from odoo.addons.spp_mis_demo_v2.models.seeded_volume_generator import SeededVolumeGenerator

        non_selective = {
            "Food Assistance": "matches every active registrant",
            "Emergency Relief Fund": "has no eligibility rule",
        }
        self.assertEqual(
            len(SeededVolumeGenerator.NON_SELECTIVE_CEL_PROGRAMS),
            len(non_selective),
            "the exclusion list changed; this test's reasoning needs revisiting",
        )

        offenders = {}
        for program in self.env["spp.program"].search([("name", "in", HEADLINE_PROGRAMS)]):
            if program.name in non_selective:
                continue
            preview = self._preview_count(program)
            if preview is None:
                continue
            memberships = self.env["spp.program.membership"].search_count([("program_id", "=", program.id)])
            if preview == 0 and memberships == 0:
                continue
            drift = abs(preview - memberships) / max(preview, 1) * 100
            if drift > 10:
                offenders[program.name] = f"preview {preview} vs {memberships} memberships ({drift:.0f}%)"

        self.assertFalse(offenders, f"eligibility and enrollment disagree: {offenders}")

    def test_the_enrolled_count_is_also_within_tolerance(self):
        """The number QA actually reads off the program form.

        The sibling test compares against all memberships, which is the right
        basis for judging targeting. But nobody clears the state filter before
        looking, and the enrolled count is what the Beneficiaries list shows by
        default -- so that number has to hold up too.

        It did not, at first: the generator moved 10% of memberships into
        exited, paused or not eligible, which is exactly the tolerance this
        ticket allows, so programs failed on a coin flip. The rates now total
        4%, leaving room inside the bar for the drift the ticket had in mind.
        """
        non_selective = ("Food Assistance", "Emergency Relief Fund")
        offenders = {}
        for program in self.env["spp.program"].search([("name", "in", HEADLINE_PROGRAMS)]):
            if program.name in non_selective:
                continue
            preview = self._preview_count(program)
            if preview is None or preview == 0:
                continue
            enrolled = self._enrolled_count(program)
            drift = abs(preview - enrolled) / preview * 100
            if drift > 10:
                offenders[program.name] = f"matched {preview}, enrolled {enrolled} ({drift:.1f}%)"

        self.assertFalse(
            offenders,
            f"enrolled counts outside the 10% bar QA measures against: {offenders}",
        )

    def test_memberships_still_show_a_mix_of_states(self):
        """Reducing the variety must not flatten it to nothing.

        The point of the mixed states is that a demo where every membership is
        enrolled looks synthetic. Tightening the rates to fit the tolerance is
        only acceptable while the mix is still visible.
        """
        states = set(self.env["spp.program.membership"].search([]).mapped("state"))

        self.assertIn("enrolled", states)
        self.assertTrue(
            {"exited", "paused", "not_eligible"} & states,
            "no membership is in any state other than enrolled; the variety is gone",
        )

    def test_a_disability_program_finally_matches_somebody(self):
        """OP#955 and OP#956 together: the DSG story works end to end."""
        program = self.env["spp.program"].search([("name", "=", "Disability Support Grant")], limit=1)
        self.assertTrue(program)

        self.assertGreater(
            self.env["res.partner"].search_count([("has_disability", "=", True)]),
            0,
            "no demo individual has a disability, so nothing can match",
        )
        self.assertGreater(self._preview_count(program) or 0, 0, "DSG still previews zero households")
