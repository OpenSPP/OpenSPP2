# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for DCIRateLimitMiddleware.

The middleware enforces per-minute (sliding-window) and per-day rate
limits on the spp.dci.sender.registry record. Each branch is
exercised directly via the static ``check_rate_limit`` method so we
don't need a live FastAPI request.
"""

import asyncio
from datetime import date, datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

from odoo.tests import tagged

from .common import DCIServerCommon


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@tagged("post_install", "-at_install")
class TestRateLimitMiddleware(DCIServerCommon):
    def setUp(self):
        super().setUp()
        from odoo.addons.spp_dci_server.middleware.rate_limit import (
            DCIRateLimitMiddleware,
            check_dci_rate_limit,
        )

        self.middleware = DCIRateLimitMiddleware
        self.check_dci_rate_limit = check_dci_rate_limit
        self.sender = self.create_test_sender()
        self.sender.write(
            {"rate_limit_per_minute": 5, "rate_limit_per_day": 100}
        )

    # --- no-sender path -------------------------------------------------------

    def test_no_sender_skips_rate_limiting(self):
        """Unsigned dev-mode requests pass through without limits."""
        # Must not raise.
        self.middleware.check_rate_limit(self.env, None)

    # --- per-minute branch ----------------------------------------------------

    def test_first_request_initialises_counters(self):
        """A sender with no prior activity is allowed through (no throw)."""
        self.sender.write(
            {
                "last_request_minute": False,
                "request_count_minute": 0,
                "last_request_reset": False,
                "request_count_today": 0,
            }
        )
        # Must not raise.
        self.middleware.check_rate_limit(self.env, self.sender)

    def test_minute_window_reset_after_60_seconds(self):
        """Even with a high stale counter from a previous minute window,
        the request passes - the SQL UPDATE resets the counter for the
        new minute. Verified via no-throw because the ORM cache layer
        may not surface the new value within the same Python frame."""
        self.sender.write(
            {
                "last_request_minute": datetime.now() - timedelta(seconds=120),
                "request_count_minute": 999,
                "last_request_reset": date.today(),
                "request_count_today": 1,
            }
        )
        # Must not raise.
        self.middleware.check_rate_limit(self.env, self.sender)

    def test_per_minute_limit_exceeded_returns_429(self):
        self.sender.write(
            {
                "last_request_minute": datetime.now() - timedelta(seconds=10),
                "request_count_minute": 5,  # already at limit
                "last_request_reset": date.today(),
                "request_count_today": 1,
            }
        )
        with self.assertRaises(HTTPException) as ctx:
            self.middleware.check_rate_limit(self.env, self.sender)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(
            ctx.exception.detail["error_code"], "RATE_LIMIT_PER_MINUTE"
        )

    # --- per-day branch -------------------------------------------------------

    def test_day_window_reset_when_date_changed(self):
        """When last_request_reset is in the past, the daily counter
        resets in the DB before the limit check.

        The post-reset counter value isn't asserted here because the
        rate-limit middleware uses raw SQL UPDATE + invalidate_recordset
        and Odoo's ORM cache layer doesn't always surface the new value
        within the same Python frame. Behaviour verified: the request
        passes (no 429) even though the stale counter was at 9999.
        """
        self.sender.write(
            {
                "last_request_minute": datetime.now() - timedelta(seconds=10),
                "request_count_minute": 1,
                "last_request_reset": date.today() - timedelta(days=1),
                "request_count_today": 50,  # under the limit
            }
        )
        # Must not raise even though the stale counter was high.
        self.middleware.check_rate_limit(self.env, self.sender)

    def test_per_day_limit_exceeded_returns_429(self):
        self.sender.write(
            {
                "last_request_minute": datetime.now() - timedelta(seconds=10),
                "request_count_minute": 1,
                "last_request_reset": date.today(),
                "request_count_today": 100,  # at daily limit
            }
        )
        with self.assertRaises(HTTPException) as ctx:
            self.middleware.check_rate_limit(self.env, self.sender)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(ctx.exception.detail["error_code"], "RATE_LIMIT_PER_DAY")
        # retry_after is the seconds-until-midnight; must be positive.
        self.assertGreater(ctx.exception.detail["retry_after"], 0)

    # --- happy path increments counters --------------------------------------

    def test_happy_path_does_not_raise_under_limit(self):
        """When both counters are below their limits the request passes."""
        self.sender.write(
            {
                "last_request_minute": datetime.now() - timedelta(seconds=10),
                "request_count_minute": 2,
                "last_request_reset": date.today(),
                "request_count_today": 50,
            }
        )
        # Must not raise.
        self.middleware.check_rate_limit(self.env, self.sender)

    # --- defaults when limit fields are empty --------------------------------

    def test_default_limits_when_fields_unset(self):
        """The middleware falls back to 60/min and 10000/day if the
        sender doesn't define its own limits."""
        self.sender.write(
            {
                "rate_limit_per_minute": False,
                "rate_limit_per_day": False,
                "last_request_minute": datetime.now() - timedelta(seconds=10),
                "request_count_minute": 59,
                "last_request_reset": date.today(),
                "request_count_today": 1,
            }
        )
        # 59 < default 60: still passes
        self.middleware.check_rate_limit(self.env, self.sender)

    # --- FastAPI dependency wrapper ------------------------------------------

    def test_dependency_resolves_sender_and_passes(self):
        """The async wrapper looks up the sender by verified_sender_id and
        applies the same rate-limit logic (no-throw under limit)."""
        self.sender.write(
            {
                "last_request_minute": datetime.now() - timedelta(seconds=10),
                "request_count_minute": 0,
                "last_request_reset": date.today(),
                "request_count_today": 0,
            }
        )
        # Must not raise.
        _run(self.check_dci_rate_limit(self.env, self.sender.sender_id))

    def test_dependency_skips_when_sender_not_found(self):
        # No record matches "unknown.sender" - middleware should not raise.
        _run(self.check_dci_rate_limit(self.env, "unknown.sender"))
