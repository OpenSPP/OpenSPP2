# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Covers the registry → indicator-buffer invalidation chain.

When ``spp_indicators`` is installed it provides
``spp.indicator.invalidation.buffer`` (a small queue of metric keys to
recompute). The registry models hook into it from three places:

- ``res.partner (group).invalidate_group_metrics`` (entry funnel)
- ``spp.group.membership`` ``create`` / ``write`` / ``unlink`` overrides
  → ``_invalidate_group_metrics(groups)`` → group entry funnel
- ``res.partner (individual).write`` override (when ``birthdate``,
  ``gender_id`` or ``disabled`` changes) → ``_invalidate_parent_group_metrics``
  → group entry funnel

The buffer model is **optional** — both entry points early-return when
``"spp.indicator.invalidation.buffer" not in self.env``. So this file has
two kinds of test:

1. Safe no-op: when the buffer model isn't registered, the entry funnel
   must not raise. (Runs in any environment.)
2. Funnel invocation: ``invalidate_group_metrics`` *is* called with the
   correct group recordset whenever membership / individual demographics
   change. We patch the funnel using ``autospec=True`` so the recordset
   passed as ``self`` is observable.

Direct assertion of ``buffer.add(pattern=..., subject_ids=...)`` requires
a stub buffer model, which the skipped tests below leave as TODOs.
"""

from unittest.mock import patch

from odoo.tests import tagged

from .common import RegistryCommon


def _patch_invalidate_funnel(env):
    """Patch ``res.partner.invalidate_group_metrics`` with autospec.

    autospec=True preserves the method signature so the patched mock
    receives the recordset as its first arg (``self``), making it
    inspectable via ``mock.call_args.args[0]``.
    """
    return patch.object(
        type(env["res.partner"]),
        "invalidate_group_metrics",
        autospec=True,
    )


@tagged("post_install", "-at_install")
class MetricInvalidationCommon(RegistryCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # A second individual + a second group give us enough fixtures for
        # group-change scenarios in write().
        cls.individual_c = cls.Partner.create({"name": "Carol", "is_registrant": True, "is_group": False})
        cls.group_b = cls.Partner.create({"name": "Second Household", "is_registrant": True, "is_group": True})


@tagged("post_install", "-at_install")
class TestSafeNoOpWithoutIndicatorBuffer(MetricInvalidationCommon):
    """Branch coverage for the ``"buffer" not in self.env`` early returns.

    These tests assume the unit-test env does NOT register
    ``spp.indicator.invalidation.buffer``. If a fork or future module
    starts auto-registering it, these tests need a guard — see TODO.
    """

    def test_group_invalidate_is_silent_no_op(self):
        """Calling the funnel on a group with no buffer model must not raise."""
        if "spp.indicator.invalidation.buffer" in self.env:
            self.skipTest("spp_indicators is installed; this branch is unreachable")
        # Should be a no-op, no exception.
        self.group.invalidate_group_metrics()

    def test_individual_invalidate_is_silent_no_op(self):
        """``_invalidate_parent_group_metrics`` early-returns the same way."""
        if "spp.indicator.invalidation.buffer" in self.env:
            self.skipTest("spp_indicators is installed; this branch is unreachable")
        self.individual_a._invalidate_parent_group_metrics(self.individual_a)

    def test_empty_recordset_no_op(self):
        """``invalidate_group_metrics`` on an empty recordset returns early."""
        self.env["res.partner"].browse().invalidate_group_metrics()


@tagged("post_install", "-at_install")
class TestMembershipInvalidatesGroup(MetricInvalidationCommon):
    """The three CRUD overrides on ``spp.group.membership``.

    Each must call ``invalidate_group_metrics`` on the affected groups —
    including the *old* group when ``write({"group": ...})`` reassigns a
    membership to a different group.
    """

    def test_create_invalidates_group(self):
        with _patch_invalidate_funnel(self.env) as mock:
            self.Membership.create({"group": self.group.id, "individual": self.individual_a.id})
        self.assertTrue(mock.called, "invalidate_group_metrics was never called")
        recordset = mock.call_args.args[0]
        self.assertIn(self.group.id, recordset.ids)

    def test_write_invalidates_group(self):
        membership = self.Membership.create({"group": self.group.id, "individual": self.individual_a.id})
        with _patch_invalidate_funnel(self.env) as mock:
            membership.write({"individual": self.individual_b.id})
        self.assertTrue(mock.called)
        recordset = mock.call_args.args[0]
        self.assertIn(self.group.id, recordset.ids)

    def test_write_reassigning_group_invalidates_both(self):
        """When ``group`` is in vals, BOTH the original and new group must
        be invalidated."""
        membership = self.Membership.create({"group": self.group.id, "individual": self.individual_a.id})
        with _patch_invalidate_funnel(self.env) as mock:
            membership.write({"group": self.group_b.id})
        self.assertTrue(mock.called)
        recordset = mock.call_args.args[0]
        self.assertIn(
            self.group.id,
            recordset.ids,
            "old group missing from invalidation set",
        )
        self.assertIn(
            self.group_b.id,
            recordset.ids,
            "new group missing from invalidation set",
        )

    def test_unlink_invalidates_group(self):
        membership = self.Membership.create({"group": self.group.id, "individual": self.individual_a.id})
        with _patch_invalidate_funnel(self.env) as mock:
            membership.unlink()
        self.assertTrue(mock.called)
        recordset = mock.call_args.args[0]
        self.assertIn(self.group.id, recordset.ids)


@tagged("post_install", "-at_install")
class TestIndividualDemographicChangesInvalidateGroups(MetricInvalidationCommon):
    """``res.partner (individual).write`` invalidates parent groups when
    demographic fields change.

    The ``demographic_fields`` set in individual.py is
    ``{"birthdate", "gender_id", "disabled"}``. Any other field write is
    NOT supposed to trigger invalidation.
    """

    def setUp(self):
        super().setUp()
        # Active membership: alice is in the test household.
        self.Membership.create({"group": self.group.id, "individual": self.individual_a.id})

    def test_birthdate_change_invalidates_parent_group(self):
        if "birthdate" not in self.individual_a:
            self.skipTest("birthdate field not present in this build")
        with _patch_invalidate_funnel(self.env) as mock:
            self.individual_a.write({"birthdate": "1990-01-01"})
        # The funnel is called via groups.invalidate_group_metrics() in
        # ``_invalidate_parent_group_metrics`` -- but only if the buffer
        # model is registered. Without it, the early-return short-circuits
        # BEFORE the funnel call.
        if "spp.indicator.invalidation.buffer" not in self.env:
            self.skipTest("spp_indicators not installed — chain short-circuits before funnel")
        self.assertTrue(mock.called)
        recordset = mock.call_args.args[0]
        self.assertIn(self.group.id, recordset.ids)

    def test_disabled_change_invalidates_parent_group(self):
        if "spp.indicator.invalidation.buffer" not in self.env:
            self.skipTest("spp_indicators not installed — chain short-circuits before funnel")
        with _patch_invalidate_funnel(self.env) as mock:
            self.individual_a.write({"disabled": "2025-06-01 00:00:00"})
        self.assertTrue(mock.called)
        recordset = mock.call_args.args[0]
        self.assertIn(self.group.id, recordset.ids)

    def test_non_demographic_write_does_not_invalidate(self):
        """Changing ``name`` or ``email`` is NOT a demographic change."""
        with _patch_invalidate_funnel(self.env) as mock:
            self.individual_a.write({"email": "alice@example.test"})
        self.assertFalse(
            mock.called,
            "non-demographic write should not trigger group invalidation",
        )

    def test_individual_without_active_membership_does_not_invalidate(self):
        """An individual with no active membership has no parent groups."""
        if "spp.indicator.invalidation.buffer" not in self.env:
            self.skipTest("spp_indicators not installed — chain short-circuits before funnel")
        # individual_c has no membership.
        with _patch_invalidate_funnel(self.env) as mock:
            self.individual_c.write({"disabled": "2025-06-01 00:00:00"})
        self.assertFalse(mock.called)


@tagged("post_install", "-at_install")
class TestBufferAddPayload(MetricInvalidationCommon):
    """Direct coverage of the ``buffer.add(...)`` arguments.

    Requires a stub ``spp.indicator.invalidation.buffer`` model to be
    registered in the test registry. The skipped tests below pin the
    expected payload:

    - pattern=``"household.*"``, subject_model=``"res.partner"``,
      subject_ids=<group ids>
    - pattern=``"scoring.*"``, subject_model=``"res.partner"``,
      subject_ids=<group ids>

    TODO: register a TransientModel stub with an ``add(**kwargs)`` recorder
    via ``self.env.registry`` + ``self.env.registry.setup_models``, or
    monkey-patch ``self.env.__contains__`` / ``__getitem__`` for the
    duration of the test.
    """

    def test_buffer_receives_household_pattern(self):
        self.skipTest("not yet implemented — see TODO")

    def test_buffer_receives_scoring_pattern(self):
        self.skipTest("not yet implemented — see TODO")

    def test_buffer_receives_subject_ids(self):
        self.skipTest("not yet implemented — see TODO")
