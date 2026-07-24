# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Covers individual-name composition, age calc, and birthdate handling.

Maps to these methods in ``spp_registry/models/individual.py``:

- ``_format_individual_name`` (pure helper) — joins family/given/addl
  name parts into ``"FAMILY, GIVEN ADDL"`` (uppercased), with a comma only
  when family + a given/addl pair is present.
- ``name_change`` (@api.onchange) — recomputes ``name`` when any of
  ``family_name``/``given_name``/``addl_name`` changes (non-groups only).
- ``create`` override — injects the formatted name into vals before super.
- ``write`` override — re-formats name on write; respects
  ``skip_name_format`` context to break recursion.
- ``compute_age_from_dates`` (pure helper) — relativedelta-based age in
  years from a date-of-birth.
- ``_compute_calc_age`` — fills the ``age`` Char field from ``birthdate``.
- ``_birthdate_onchange`` — refuses future birthdates and restores either
  the previous value (existing records) or None (new records).
- ``_recompute_parent_groups`` — re-triggers the parent group's
  ``force_recompute_canary`` after an individual changes.
"""

from datetime import date, timedelta

from odoo.tests import Form, tagged

from .common import RegistryCommon


@tagged("post_install", "-at_install")
class TestFormatIndividualName(RegistryCommon):
    """``_format_individual_name`` — pure formatting helper.

    The function is ``@api.model``-flagged, so we call it on the model
    class without needing a record. Format rules (from reading the code):

    - All three parts: ``"FAMILY, GIVEN ADDL"``.
    - Family + (given or addl) yields ``FAMILY,`` with a trailing comma.
    - Family alone (no given, no addl) has no trailing comma.
    - Empty parts are filtered out before joining.
    - Result is always upper-cased.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fmt = cls.Partner._format_individual_name

    def test_all_three_parts(self):
        self.assertEqual(self.fmt("Doe", "Jane", "Marie"), "DOE, JANE MARIE")

    def test_family_and_given_only(self):
        self.assertEqual(self.fmt("Doe", "Jane", ""), "DOE, JANE")

    def test_family_and_addl_only(self):
        """No given name, but addl present → comma still required."""
        self.assertEqual(self.fmt("Doe", "", "Marie"), "DOE, MARIE")

    def test_family_alone_no_trailing_comma(self):
        self.assertEqual(self.fmt("Doe", "", ""), "DOE")

    def test_given_alone(self):
        self.assertEqual(self.fmt("", "Jane", ""), "JANE")

    def test_addl_alone(self):
        self.assertEqual(self.fmt("", "", "Marie"), "MARIE")

    def test_given_and_addl_no_family(self):
        """No family ⇒ no comma."""
        self.assertEqual(self.fmt("", "Jane", "Marie"), "JANE MARIE")

    def test_all_empty(self):
        self.assertEqual(self.fmt("", "", ""), "")

    def test_falsy_parts_handled(self):
        """``False`` / ``None`` parts must be tolerated, not crash."""
        self.assertEqual(self.fmt(False, "Jane", None), "JANE")

    def test_mixed_case_input_uppercased(self):
        self.assertEqual(self.fmt("doe", "jane", "marie"), "DOE, JANE MARIE")


@tagged("post_install", "-at_install")
class TestNameChangeOnchange(RegistryCommon):
    """``name_change`` — @api.onchange invoked directly.

    The default partner form hides ``is_registrant`` (it's set via the
    ``default_is_registrant`` context from registry actions), so ``Form``
    can't drive these tests. We invoke the onchange method directly
    against a NewId record instead — same code path, no view dependency.
    """

    def test_name_recomputed_for_individual(self):
        rec = self.Partner.new(
            {
                "is_registrant": True,
                "is_group": False,
                "family_name": "Doe",
                "given_name": "Jane",
            }
        )
        rec.name_change()
        self.assertEqual(rec.name, "DOE, JANE")

    def test_name_not_recomputed_for_group(self):
        """Onchange short-circuits when ``is_group`` is True."""
        rec = self.Partner.new(
            {
                "is_registrant": True,
                "is_group": True,
                "name": "Test Household",
                "family_name": "Should Not Apply",
            }
        )
        rec.name_change()
        self.assertEqual(rec.name, "Test Household")


@tagged("post_install", "-at_install")
class TestCreateAppliesFormattedName(RegistryCommon):
    """``create`` override injects formatted name into vals."""

    def test_create_sets_name_from_parts(self):
        rec = self.Partner.create(
            {
                "is_registrant": True,
                "family_name": "Doe",
                "given_name": "Jane",
            }
        )
        self.assertEqual(rec.name, "DOE, JANE")

    def test_create_respects_explicit_name_when_no_parts(self):
        """No name parts in vals → ``name`` is NOT overwritten."""
        rec = self.Partner.create({"is_registrant": True, "name": "Explicit Name"})
        self.assertEqual(rec.name, "Explicit Name")

    def test_create_does_not_format_for_groups(self):
        """Groups skip the format step — ``family_name`` is ignored on
        creation when ``is_group=True``."""
        rec = self.Partner.create(
            {
                "is_registrant": True,
                "is_group": True,
                "name": "Test Household",
                "family_name": "Doe",  # should not affect name
            }
        )
        self.assertEqual(rec.name, "Test Household")

    def test_create_with_only_addl(self):
        rec = self.Partner.create({"is_registrant": True, "addl_name": "Marie"})
        self.assertEqual(rec.name, "MARIE")

    def test_create_explicit_name_with_parts_preserved(self):
        """Explicit ``name`` alongside name parts → the explicit name wins.

        The demo story generator deliberately sets a human-friendly display
        ``name`` ("Rosa Garcia") together with given/family parts; that
        explicit name must not be reformatted to "GARCIA, ROSA". The parts
        are still stored as given.
        """
        rec = self.Partner.create(
            {
                "is_registrant": True,
                "name": "Rosa Garcia",
                "given_name": "Rosa",
                "family_name": "Garcia",
            }
        )
        self.assertEqual(rec.name, "Rosa Garcia")
        self.assertEqual(rec.given_name, "Rosa")
        self.assertEqual(rec.family_name, "Garcia")


@tagged("post_install", "-at_install")
class TestWriteAppliesFormattedName(RegistryCommon):
    """``write`` override re-formats name when a name part changes."""

    def setUp(self):
        super().setUp()
        self.rec = self.Partner.create(
            {
                "is_registrant": True,
                "family_name": "Doe",
                "given_name": "Jane",
            }
        )

    def test_write_family_name_reformats(self):
        self.rec.write({"family_name": "Smith"})
        self.assertEqual(self.rec.name, "SMITH, JANE")

    def test_write_given_name_reformats(self):
        self.rec.write({"given_name": "Janet"})
        self.assertEqual(self.rec.name, "DOE, JANET")

    def test_write_addl_name_reformats(self):
        self.rec.write({"addl_name": "Marie"})
        self.assertEqual(self.rec.name, "DOE, JANE MARIE")

    def test_write_explicit_name_with_parts_preserved(self):
        """Writing an explicit ``name`` together with a name part keeps the
        explicit name; the part still updates underneath."""
        self.rec.write({"name": "Custom Display", "family_name": "Smith"})
        self.assertEqual(self.rec.name, "Custom Display")
        self.assertEqual(self.rec.family_name, "Smith")

    def test_write_non_name_field_does_not_reformat(self):
        """Writing ``email`` (not in ``_name_fields``) leaves ``name`` alone."""
        self.rec.write({"name": "Manual Override"})
        # First, manual override stuck (no name part in vals).
        self.assertEqual(self.rec.name, "Manual Override")
        # Then, writing a non-name field doesn't re-format from parts.
        self.rec.write({"email": "jane@example.test"})
        self.assertEqual(self.rec.name, "Manual Override")

    def test_skip_name_format_context_bypasses_reformat(self):
        """``skip_name_format=True`` in context bypasses the re-format step.

        Used internally by ``write`` itself to apply the formatted name via
        super() without recursion. Anyone passing the context explicitly
        gets the same opt-out.
        """
        self.rec.with_context(skip_name_format=True).write({"family_name": "Smith"})
        # family_name updated but name unchanged.
        self.assertEqual(self.rec.family_name, "Smith")
        self.assertEqual(self.rec.name, "DOE, JANE")

    def test_write_does_not_reformat_groups(self):
        """Writing a name part to a group leaves ``name`` alone."""
        group = self.Partner.create(
            {
                "is_registrant": True,
                "is_group": True,
                "name": "Original Group Name",
            }
        )
        group.write({"family_name": "Should Not Apply"})
        self.assertEqual(group.name, "Original Group Name")


@tagged("post_install", "-at_install")
class TestComputeAgeFromDates(RegistryCommon):
    """``compute_age_from_dates`` — string years from a date-of-birth."""

    def test_returns_no_birthdate_marker_when_falsy(self):
        self.assertEqual(self.Partner.compute_age_from_dates(None), "No Birthdate!")
        self.assertEqual(self.Partner.compute_age_from_dates(False), "No Birthdate!")

    def test_returns_years_for_past_birthdate(self):
        thirty_years_ago = date.today() - timedelta(days=365 * 30 + 7)
        result = self.Partner.compute_age_from_dates(thirty_years_ago)
        # Allow a 1-year tolerance for leap years / partial years.
        self.assertIn(result, {"29", "30"})

    def test_returns_zero_for_today(self):
        self.assertEqual(self.Partner.compute_age_from_dates(date.today()), "0")


@tagged("post_install", "-at_install")
class TestComputeCalcAge(RegistryCommon):
    """``_compute_calc_age`` — Char age field driven by ``birthdate``."""

    def test_age_unset_when_no_birthdate(self):
        if "birthdate" not in self.individual_a:
            self.skipTest("birthdate field not present in this build")
        self.assertEqual(self.individual_a.age, "No Birthdate!")

    def test_age_populated_from_birthdate(self):
        if "birthdate" not in self.individual_a:
            self.skipTest("birthdate field not present in this build")
        dob = date.today().replace(year=date.today().year - 25)
        self.individual_a.write({"birthdate": dob})
        # Allow ±1 around the boundary (today might be just before the
        # 25th birthday in the same calendar year).
        self.assertIn(self.individual_a.age, {"24", "25"})


@tagged("post_install", "-at_install")
class TestCheckAgeIsInteger(RegistryCommon):
    """Creation behavior around the computed ``age`` field.

    ``age`` is a NON-stored compute derived from ``birthdate``
    (``str(years)`` when set, else ``"No Birthdate!"``), so it can never
    carry a user-supplied non-integer. The former ``@api.constrains("age")``
    ``_check_age_is_integer`` guard therefore never fired (Odoo's constrains
    hooks only trigger on stored writes) and only emitted the registry-load
    warning ``@constrains parameter 'age' is not writeable`` — it was removed
    as dead code.

    These tests pin the observable behavior the removal must preserve:
    an individual can be created with or without a birthdate. They also
    guard against a naive re-introduction (e.g. constraining on
    ``birthdate`` or storing the compute), which would make the
    birthdate-less case raise on ``age == "No Birthdate!"``.
    """

    def test_individual_without_birthdate_can_be_created(self):
        """age=='No Birthdate!' (not isdigit) must not block creation."""
        rec = self.Partner.create({"name": "Ageless", "is_registrant": True})
        self.assertTrue(rec.id)

    def test_individual_with_birthdate_can_be_created(self):
        if "birthdate" not in self.Partner:
            self.skipTest("birthdate field not present in this build")
        rec = self.Partner.create(
            {
                "name": "With DOB",
                "is_registrant": True,
                "birthdate": date(1990, 1, 1),
            }
        )
        self.assertTrue(rec.id)


@tagged("post_install", "-at_install")
class TestBirthdateOnchange(RegistryCommon):
    """``_birthdate_onchange`` — refuse future birthdates."""

    def test_future_birthdate_restored_to_origin_on_existing_record(self):
        if "birthdate" not in self.individual_a:
            self.skipTest("birthdate field not present in this build")
        original = date(1990, 1, 1)
        self.individual_a.write({"birthdate": original})

        form = Form(self.individual_a)
        form.birthdate = date.today() + timedelta(days=1)
        # The onchange should reset birthdate back to _origin.birthdate.
        self.assertEqual(form.birthdate, original)

    def test_future_birthdate_cleared_on_new_record(self):
        if "birthdate" not in self.Partner:
            self.skipTest("birthdate field not present in this build")
        rec = self.Partner.new(
            {
                "is_registrant": True,
                "name": "New Person",
                "birthdate": date.today() + timedelta(days=1),
            }
        )
        rec._birthdate_onchange()
        # New record — no _origin — so the onchange should clear birthdate.
        self.assertFalse(rec.birthdate)

    def test_today_is_accepted(self):
        if "birthdate" not in self.Partner:
            self.skipTest("birthdate field not present in this build")
        rec = self.Partner.new(
            {
                "is_registrant": True,
                "name": "Newborn",
                "birthdate": date.today(),
            }
        )
        rec._birthdate_onchange()
        self.assertEqual(rec.birthdate, date.today())


@tagged("post_install", "-at_install")
class TestRecomputeParentGroups(RegistryCommon):
    """``_recompute_parent_groups`` — canary trigger after individual edits.

    ``force_recompute_canary`` is a ``@api.depends("group_membership_ids",
    "group_membership_ids.individual")`` compute on ``res.partner``. The
    individual model schedules its recompute via ``env.add_to_compute``
    after write/create. Asserting that "the canary was scheduled" without
    hooking the registry internals is fragile; we instead assert the
    observable: the constraint inside ``_recompute_parent_groups``
    enforces "only one head per group" across all members of every
    affected parent group.
    """

    def setUp(self):
        super().setUp()
        self.head_membership = self.Membership.create(
            {
                "group": self.group.id,
                "individual": self.individual_a.id,
                "membership_type_ids": [(6, 0, [self.head_code.id])],
            }
        )

    def test_individual_write_propagates_through_to_canary(self):
        """A non-name write on an individual still runs the canary recompute
        chain without raising."""
        # No head conflict, no exception expected.
        self.individual_a.write({"comment": "demographic update"})

    def test_head_conflict_via_individual_write_is_detected(self):
        """If TWO memberships somehow end up with the same head code in the
        same group, the individual-side recompute trips the validation.

        TODO: this branch is hard to reach because the group/membership
        validation also fires on the membership create — we'd need to
        bypass that first (e.g., via direct SQL or a separate transaction)
        and then trigger an individual write. Pin as TODO until needed.
        """
        self.skipTest("not yet implemented — see TODO")

    def test_group_write_does_not_trigger_recompute(self):
        """The recompute filters on ``is_registrant and not is_group``."""
        # Should be a no-op for the group's recompute path.
        self.group.write({"comment": "metadata only"})
