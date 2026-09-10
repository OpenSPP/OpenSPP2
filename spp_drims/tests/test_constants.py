# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OP#1165: prove every constant in ``constants.py`` resolves to real data.

Four constants used to hold values that existed in no vocabulary
(``PRIORITY_LOW``/``MEDIUM``/``HIGH``, ``DRIMS_TYPE_TRANSFER``). Nothing failed,
because a ``search`` for a non-existent code returns an empty set rather than
raising — so a comparison against one would simply never match. These tests turn
that silent drift into a build failure.
"""

import re

from lxml import etree

from odoo.tests import tagged

from ..models import constants
from .common import DrimsTestCommon


@tagged("post_install", "-at_install")
class TestDrimsConstants(DrimsTestCommon):
    """Every namespace and code constant must exist in the shipped data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vocabulary = cls.env["spp.vocabulary"]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _constants_with_prefix(prefix):
        """Every public ``prefix``-named string constant, as {name: value}."""
        return {
            name: value
            for name, value in vars(constants).items()
            if name.startswith(prefix) and isinstance(value, str) and not name.startswith("_")
        }

    def _codes_in(self, namespace_uri):
        """Every code in the vocabulary, including locally added ones."""
        return set(
            self.env["spp.vocabulary.code"].search([("vocabulary_id.namespace_uri", "=", namespace_uri)]).mapped("code")
        )

    def _canonical_codes_in(self, namespace_uri):
        """Only the codes this vocabulary ships with, excluding local overlays.

        ``is_local`` marks codes layered on by a country module or an admin —
        ``spp_drims_sl``, for instance, adds ``life_threatening`` to
        priority-levels. Extending a vocabulary that way is the intended design,
        so those codes must not be held against ``spp_drims``'s own constants.
        """
        return set(
            self.env["spp.vocabulary.code"]
            .search(
                [
                    ("vocabulary_id.namespace_uri", "=", namespace_uri),
                    ("is_local", "=", False),
                ]
            )
            .mapped("code")
        )

    # ------------------------------------------------------------------
    # namespaces
    # ------------------------------------------------------------------

    def test_every_vocab_namespace_exists(self):
        """Each VOCAB_* constant must name a vocabulary that is actually installed."""
        namespaces = self._constants_with_prefix("VOCAB_")
        namespaces.pop("VOCAB_BASE", None)
        self.assertTrue(namespaces, "no VOCAB_* constants found — has the module moved?")

        missing = {
            name: uri
            for name, uri in namespaces.items()
            if not self.vocabulary.search_count([("namespace_uri", "=", uri)])
        }
        self.assertFalse(
            missing,
            "VOCAB_* constants naming vocabularies that do not exist: "
            + ", ".join(f"{n} = {u!r}" for n, u in sorted(missing.items())),
        )

    def test_vocab_namespaces_use_the_base_uri(self):
        """A namespace typed out in full would drift from VOCAB_BASE unnoticed."""
        namespaces = self._constants_with_prefix("VOCAB_")
        namespaces.pop("VOCAB_BASE", None)
        for name, uri in sorted(namespaces.items()):
            self.assertTrue(
                uri.startswith(f"{constants.VOCAB_BASE}:"),
                f"{name} = {uri!r} does not build on VOCAB_BASE",
            )

    # ------------------------------------------------------------------
    # codes
    # ------------------------------------------------------------------

    def test_every_code_constant_resolves(self):
        """The regression this ticket is about.

        Reported all at once rather than failing on the first, so a rename in the
        vocabulary data shows the full list of constants to update.
        """
        self.assertTrue(constants.CODE_NAMESPACES, "CODE_NAMESPACES is empty")

        failures = []
        for prefix, namespace_uri in sorted(constants.CODE_NAMESPACES.items()):
            available = self._codes_in(namespace_uri)
            self.assertTrue(
                available,
                f"vocabulary {namespace_uri} has no codes — cannot verify {prefix}* constants",
            )
            for name, value in sorted(self._constants_with_prefix(prefix).items()):
                if value not in available:
                    failures.append(
                        f"{name} = {value!r} is not a code in {namespace_uri} "
                        f"(available: {', '.join(sorted(available))})"
                    )
        self.assertFalse(failures, "constants that resolve to nothing:\n  " + "\n  ".join(failures))

    def test_code_constants_are_named_after_their_code(self):
        """Keeps the file honest: the name states the value.

        ``PRIORITY_HIGH = "high"`` looked right and was wrong, because the
        vocabulary calls that level ``urgent``. Deriving the expected name from the
        value stops a concept-name being invented for a code that does not exist.
        """
        mismatches = []
        for prefix in sorted(constants.CODE_NAMESPACES):
            for name, value in sorted(self._constants_with_prefix(prefix).items()):
                expected = f"{prefix}{value.upper()}"
                if name != expected:
                    mismatches.append(f"{name} = {value!r} — expected the name {expected}")
        self.assertFalse(
            mismatches,
            "code constants whose name does not mirror their value:\n  " + "\n  ".join(mismatches),
        )

    def test_code_groups_cover_their_canonical_vocabulary(self):
        """Every code the vocabulary ships with should have a constant.

        A partially declared group is what sent an earlier caller back to
        hardcoding ``'urgent'``, which is how the bad values survived unnoticed.

        Deliberately limited to canonical codes. Asserting over *all* codes broke
        as soon as ``spp_drims_sl`` was installed, because it legitimately adds
        ``life_threatening`` to priority-levels — and ``spp_drims`` cannot be held
        responsible for declaring constants for codes a country module layers on.
        A non-local addition to one of these vocabularies would still fail here,
        which is intended: that genuinely does leave these constants incomplete.
        """
        gaps = []
        for prefix, namespace_uri in sorted(constants.CODE_NAMESPACES.items()):
            declared = set(self._constants_with_prefix(prefix).values())
            for code in sorted(self._canonical_codes_in(namespace_uri) - declared):
                gaps.append(f"{namespace_uri} code {code!r} has no {prefix}* constant")
        self.assertFalse(gaps, "vocabulary codes with no constant:\n  " + "\n  ".join(gaps))

    # ------------------------------------------------------------------
    # the specific values that were wrong
    # ------------------------------------------------------------------

    def test_the_previously_broken_constants_are_right_now(self):
        """Pins the four values from OP#1165 against a silent re-introduction."""
        self.assertEqual(constants.PRIORITY_ROUTINE, "routine")
        self.assertEqual(constants.PRIORITY_URGENT, "urgent")
        self.assertEqual(constants.PRIORITY_CRITICAL, "critical")
        self.assertEqual(constants.DRIMS_TYPE_INTERNAL_TRANSFER, "internal_transfer")

        # The old names described levels the vocabulary does not have.
        for gone in ("PRIORITY_LOW", "PRIORITY_MEDIUM", "PRIORITY_HIGH", "DRIMS_TYPE_TRANSFER"):
            self.assertFalse(
                hasattr(constants, gone),
                f"{gone} is back; it names a code that does not exist in the vocabulary",
            )

    # ------------------------------------------------------------------
    # the same mistake, in the consumers rather than the constants
    # ------------------------------------------------------------------

    def test_sla_hours_are_keyed_by_real_priority_codes(self):
        """Every shipped priority must get its own approval SLA.

        The lookup used to be keyed by 'high' and 'low', which no priority has,
        so an urgent request silently fell through to the routine default of 24
        hours instead of 8 — a wrong answer rather than an error, which is the
        whole failure mode OP#1165 is about.
        """
        settings = self.env["res.config.settings"]
        codes = self._codes_in(constants.VOCAB_PRIORITY_LEVELS)

        hours = {code: settings.get_approval_sla_hours(code) for code in codes}
        self.assertEqual(
            hours,
            {"routine": 24, "urgent": 8, "critical": 4},
            f"a priority is not getting its own SLA: {hours}",
        )

        # Urgent must not silently share the routine fallback.
        self.assertNotEqual(
            hours["urgent"],
            hours["routine"],
            "urgent is falling through to the routine default",
        )

    def test_priority_views_reference_codes_that_exist(self):
        """Decorations and filters keyed on a priority code must name a real one.

        A decoration or a search filter naming a code that does not exist is
        accepted silently and simply never matches — the filter returns nothing
        and the highlight never appears.
        """
        codes = set(self._codes_in(constants.VOCAB_PRIORITY_LEVELS))
        arch = etree.fromstring(self.env.ref("spp_drims.spp_drims_request_list").arch)
        referenced = set(re.findall(r"priority_id\.code\s*==\s*'([a-z_]+)'", etree.tostring(arch, encoding="unicode")))

        self.assertTrue(referenced, "no priority decorations found — has the view changed?")
        self.assertFalse(
            referenced - codes,
            f"these decorations name priority codes that do not exist: {sorted(referenced - codes)}",
        )

    def test_priority_search_filters_reference_codes_that_exist(self):
        search = etree.fromstring(self.env.ref("spp_drims.spp_drims_request_search").arch)
        codes = set(self._codes_in(constants.VOCAB_PRIORITY_LEVELS))
        referenced = set(
            re.findall(r"'priority_id\.code',\s*'=',\s*'([a-z_]+)'", etree.tostring(search, encoding="unicode"))
        )

        self.assertTrue(referenced, "no priority filters found — has the search view changed?")
        self.assertFalse(
            referenced - codes,
            f"these filters name priority codes that do not exist: {sorted(referenced - codes)}",
        )
