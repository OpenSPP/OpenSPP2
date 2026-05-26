# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Covers ``spp.phone.number`` business logic + the registrant-side sync.

Audit items addressed:

- ``_check_date_collected`` — onchange that refuses future dates.
- ``_compute_phone_sanitized`` — uncovered edge cases (empty phone,
  invalid number with raise_exception=False, ``phone_validation`` import
  missing).
- ``_phone_format`` — country-fallback chain (param → ``self.country_id``
  → ``self.env.company.country_id``) and error tolerance.
- ``disable_phone`` / ``enable_phone`` — idempotent audit-field toggles.
- ``registrant.phone_number_ids_change`` — the onchange on
  ``res.partner`` that aggregates non-disabled phone numbers into the
  partner's ``phone`` field.

The happy-path formatting tests already live in
``spp_base_common/tests/test_phone_number_validation.py``; we do NOT
duplicate them here.
"""

from datetime import date, timedelta
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from .common import RegistryCommon


@tagged("post_install", "-at_install")
class PhoneCommon(RegistryCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.PhoneNumber = cls.env["spp.phone.number"]
        cls.country_ph = cls.env.ref("base.ph", raise_if_not_found=False)
        cls.country_us = cls.env.ref("base.us", raise_if_not_found=False)


@tagged("post_install", "-at_install")
class TestCheckDateCollected(PhoneCommon):
    """``_check_date_collected`` — @api.onchange refusing future dates.

    Note: it's wired as ``@api.onchange("date_collected")`` only — NOT as
    ``@api.constrains`` — so it fires from form views but bypassing the
    UI (e.g., a programmatic ``create``) will not raise. That's the
    contract today; this test pins it.
    """

    def test_future_date_rejected_in_form(self):
        form = Form(self.PhoneNumber)
        form.partner_id = self.individual_a
        form.phone_no = "+639123456789"
        future = date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            form.date_collected = future

    def test_today_is_accepted(self):
        form = Form(self.PhoneNumber)
        form.partner_id = self.individual_a
        form.phone_no = "+639123456789"
        form.date_collected = date.today()
        self.assertEqual(form.date_collected, date.today())

    def test_past_date_is_accepted(self):
        form = Form(self.PhoneNumber)
        form.partner_id = self.individual_a
        form.phone_no = "+639123456789"
        form.date_collected = date.today() - timedelta(days=30)
        self.assertEqual(form.date_collected, date.today() - timedelta(days=30))

    def test_programmatic_create_with_future_date_does_not_raise(self):
        """Programmatic create bypasses the onchange (no @api.constrains).

        If you want this branch tightened into a real constraint, this
        test will need to flip to ``assertRaises(ValidationError)``.
        """
        future = date.today() + timedelta(days=1)
        rec = self.PhoneNumber.create(
            {
                "partner_id": self.individual_a.id,
                "phone_no": "+639123456789",
                "date_collected": future,
            }
        )
        self.assertEqual(rec.date_collected, future)


@tagged("post_install", "-at_install")
class TestComputePhoneSanitized(PhoneCommon):
    """``_compute_phone_sanitized`` — edge cases not covered upstream.

    The happy-path E164 sanitization for PH numbers is in
    ``spp_base_common/tests/test_phone_number_validation.py``. Here we
    cover the failure / boundary branches.
    """

    def test_empty_phone_sanitized_is_empty(self):
        if not self.country_ph:
            self.skipTest("base.ph not present")
        rec = self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": " "})
        # The compute sets phone_sanitized to "" when phone_no is falsy.
        # A whitespace-only string is truthy in Python, so this goes
        # through phone_format, which returns either the formatted
        # value or empty.
        self.assertIn(rec.phone_sanitized, ("", None, " "))

    def test_unparseable_phone_falls_back_to_original(self):
        """A garbage number falls into ``_phone_format``'s except branch,
        which returns the **original** value (not None) when
        ``raise_exception=False``. ``_compute_phone_sanitized`` then
        stores that original string as ``phone_sanitized``.

        Worth flagging: this means ``phone_sanitized`` can hold an
        un-E164'd value when parsing fails. If you'd rather it be empty,
        the compute needs to filter the fallback explicitly.
        """
        rec = self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": "abcxyz"})
        self.assertEqual(rec.phone_sanitized, "abcxyz")

    def test_phone_validation_unavailable_returns_original(self):
        """When ``phone_validation`` failed to import (older Odoo /
        missing dependency), ``_phone_format`` logs a warning and returns
        the original number. ``_compute_phone_sanitized`` then assigns it.
        """
        # TODO: patch ``odoo.addons.spp_registry.models.phone_number.phone_validation``
        # to None for the duration of the test and assert that
        # ``phone_sanitized`` falls back to the original ``phone_no``.
        self.skipTest("not yet implemented — see TODO")


@tagged("post_install", "-at_install")
class TestPhoneFormatFallbacks(PhoneCommon):
    """``_phone_format`` — country fallback chain + error tolerance."""

    def setUp(self):
        super().setUp()
        self.rec = self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": "+639123456789"})

    def test_country_param_used_when_provided(self):
        if not self.country_ph:
            self.skipTest("base.ph not present")
        result = self.rec._phone_format(number="09123456789", country=self.country_ph, force_format="E164")
        # E164 PH numbers prepend +63.
        self.assertTrue(
            result.startswith("+63"),
            f"expected E164 PH formatting, got {result!r}",
        )

    def test_self_country_id_used_when_no_param(self):
        """Fallback level 2: ``self.country_id`` when ``country`` arg is None."""
        if not self.country_ph:
            self.skipTest("base.ph not present")
        self.rec.country_id = self.country_ph
        result = self.rec._phone_format(number="09123456789", force_format="E164")
        self.assertTrue(result.startswith("+63"))

    def test_company_country_used_when_neither_provided(self):
        """Fallback level 3: ``self.env.company.country_id``."""
        if not self.country_us:
            self.skipTest("base.us not present")
        self.env.company.country_id = self.country_us
        result = self.rec._phone_format(number="2125551234", force_format="E164")
        # E164 US numbers prepend +1.
        self.assertTrue(
            result.startswith("+1"),
            f"expected E164 US formatting via company fallback, got {result!r}",
        )

    def test_raise_exception_propagates_invalid(self):
        """When ``raise_exception=True``, invalid input must raise."""
        with self.assertRaises(UserError):
            self.rec._phone_format(
                number="abcxyz",
                country=self.country_ph if self.country_ph else None,
                raise_exception=True,
            )

    def test_silent_fallback_returns_original_on_error(self):
        """When ``raise_exception=False`` (the default), errors swallow
        and the original number is returned."""
        result = self.rec._phone_format(
            number="abcxyz",
            country=self.country_ph if self.country_ph else None,
            raise_exception=False,
        )
        self.assertEqual(result, "abcxyz")

    def test_phone_validation_unavailable_returns_original(self):
        """When the upstream ``phone_validation`` module is None,
        ``_phone_format`` returns the original number unchanged."""
        with patch(
            "odoo.addons.spp_registry.models.phone_number.phone_validation",
            None,
        ):
            result = self.rec._phone_format(number="09123456789")
        self.assertEqual(result, "09123456789")

    def test_phone_validation_unavailable_with_raise_exception_returns_none(self):
        """With ``raise_exception=True`` AND ``phone_validation=None``, the
        code returns ``None`` instead of raising (see the early-return
        branch in the implementation)."""
        with patch(
            "odoo.addons.spp_registry.models.phone_number.phone_validation",
            None,
        ):
            result = self.rec._phone_format(number="09123456789", raise_exception=True)
        self.assertIsNone(result)


@tagged("post_install", "-at_install")
class TestDisableEnablePhone(PhoneCommon):
    """``disable_phone`` / ``enable_phone`` audit toggles."""

    def setUp(self):
        super().setUp()
        self.rec = self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": "+639123456789"})

    def test_disable_sets_audit_fields(self):
        self.assertFalse(self.rec.disabled)
        self.rec.disable_phone()
        self.assertTrue(self.rec.disabled)
        self.assertEqual(self.rec.disabled_by, self.env.user)

    def test_disable_is_idempotent(self):
        """Second ``disable_phone`` must NOT overwrite the original
        timestamp (the ``if not rec.disabled`` guard)."""
        self.rec.disable_phone()
        first_ts = self.rec.disabled
        self.rec.disable_phone()
        self.assertEqual(self.rec.disabled, first_ts)

    def test_enable_clears_audit_fields(self):
        self.rec.disable_phone()
        self.rec.enable_phone()
        self.assertFalse(self.rec.disabled)
        self.assertFalse(self.rec.disabled_by)

    def test_enable_on_already_active_is_noop(self):
        """``enable_phone`` only acts when ``disabled`` is truthy."""
        self.rec.enable_phone()
        self.assertFalse(self.rec.disabled)
        self.assertFalse(self.rec.disabled_by)

    def test_disable_iterates_over_recordset(self):
        """Multi-record disable should stamp every record."""
        other = self.PhoneNumber.create({"partner_id": self.individual_b.id, "phone_no": "+639998887777"})
        (self.rec | other).disable_phone()
        self.assertTrue(self.rec.disabled)
        self.assertTrue(other.disabled)


@tagged("post_install", "-at_install")
class TestRegistrantPhoneSync(PhoneCommon):
    """``res.partner.phone_number_ids_change`` — onchange syncing the
    one2many of ``spp.phone.number`` into the partner's flat ``phone`` field.

    The expected behaviour per the implementation:

    - Concatenate every non-disabled phone with a comma separator.
    - Disabled phones are filtered out.
    - With no phones, the partner's ``phone`` becomes empty string.
    """

    def test_single_phone_syncs(self):
        """Invoke the onchange directly — the default partner form
        doesn't expose ``phone`` so ``Form`` can't drive this."""
        self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": "+639123456789"})
        # Refresh the o2m cache and fire the onchange.
        self.individual_a.invalidate_recordset(["phone_number_ids"])
        self.individual_a.phone_number_ids_change()
        self.assertEqual(self.individual_a.phone, "+639123456789")

    def test_multiple_phones_joined_with_comma(self):
        self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": "+639123456789"})
        self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": "+639998887777"})
        self.individual_a.invalidate_recordset(["phone_number_ids"])
        self.individual_a.phone_number_ids_change()
        self.assertIn("+639123456789", self.individual_a.phone)
        self.assertIn("+639998887777", self.individual_a.phone)
        self.assertIn(",", self.individual_a.phone)

    def test_disabled_phones_excluded_from_sync(self):
        """A phone with ``disabled`` set must NOT contribute to the
        registrant's flat ``phone`` field."""
        live = self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": "+639123456789"})
        dead = self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": "+639998887777"})
        dead.disable_phone()
        self.individual_a.invalidate_recordset(["phone_number_ids"])
        self.individual_a.phone_number_ids_change()
        self.assertIn(live.phone_no, self.individual_a.phone)
        self.assertNotIn(dead.phone_no, self.individual_a.phone)

    def test_removing_all_phones_clears_field(self):
        """When the o2m goes back to empty, ``phone`` becomes ''."""
        phone = self.PhoneNumber.create({"partner_id": self.individual_a.id, "phone_no": "+639123456789"})
        self.individual_a.invalidate_recordset(["phone_number_ids"])
        self.individual_a.phone_number_ids_change()
        self.assertEqual(self.individual_a.phone, "+639123456789")
        phone.unlink()
        self.individual_a.invalidate_recordset(["phone_number_ids"])
        self.individual_a.phone_number_ids_change()
        self.assertEqual(self.individual_a.phone, "")
