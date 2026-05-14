"""Pre-warm the cache before CEL eligibility compilation.

The Import Eligible / Enroll Eligible flow on a Program (program-level,
not cycle-level) calls the eligibility manager's `_prepare_eligible_domain`
which compiles `has_disability == true` to `metric('has_disability', me)
== true`. When the executor checks the cache freshness and finds it
incomplete (no rows yet, or stale), it falls back to a legacy Python
evaluation path that calls `spp.indicator.evaluate` — a method that no
longer exists in this Odoo 19 installation, producing:

    AttributeError: 'spp.indicator' object has no attribute 'evaluate'

The cycle-based flow doesn't hit this because `cycle_manager_base.py`
already calls `_precompute_cycle_cached_variables` (and thus
`cache_mgr.precompute_cached_variables`) before each eligibility check.
The program-level flow has no equivalent pre-fetch — the SQL fast path
is never available, the Python fallback is broken.

This module patches `spp.program.membership.manager.default` so its
`_prepare_eligible_domain` warms the cache for the candidate cohort
before the CEL compile runs. After pre-fetch, the cache is "fresh" and
the executor takes the SQL fast path, never touching the broken legacy
Python path.

The pre-fetch is a no-op when:
  - The eligibility manager has no CEL expression (parent flow runs)
  - The CEL expression has no cached-strategy variables (no metric() calls)
  - `spp.data.cache.manager` is not in the environment (spp_cel_domain
    missing — defensive guard)
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)


class DefaultEligibilityManagerCacheWarmer(models.Model):
    _inherit = "spp.program.membership.manager.default"

    def _prepare_eligible_domain(self, membership=None):
        # No CEL expression -> nothing to pre-warm
        if not self.cel_expression:
            return super()._prepare_eligible_domain(membership)

        self._precompute_cached_variables_for_cohort(membership)
        return super()._prepare_eligible_domain(membership)

    def _precompute_cached_variables_for_cohort(self, membership):
        """Warm `spp.data.value` for the cohort that the CEL filter will
        evaluate over.

        Cohort definition mirrors the base domain that
        `spp_programs/models/cel/eligibility_cel.py:_prepare_eligible_domain`
        will apply BEFORE the CEL filter:

          - is_registrant = True
          - is_group respects target_type
          - disabled = False
          - id IN membership.partner_ids (if membership provided — only
            then we have a bounded cohort; otherwise we pre-warm for ALL
            registrants matching the base domain)

        Note on scale: for a deployment with 100k registrants and no
        membership filter, this fetches DCI data for every registrant.
        That's expensive but it's the only way the SQL fast path can run
        on demand. For cycle-based enrollment this isn't a concern
        because the cycle manager limits the cohort to existing
        memberships. For Import Eligible (program-level), the cohort IS
        the full registrant base by design — the operator is looking
        for new eligibles among everyone.
        """
        if "spp.data.cache.manager" not in self.env:
            return

        target_type = self.program_id.target_type
        base_domain = [
            ("is_registrant", "=", True),
            ("disabled", "=", False),
        ]
        if target_type == "group":
            base_domain.append(("is_group", "=", True))
        elif target_type == "individual":
            base_domain.append(("is_group", "=", False))

        if membership is not None:
            partner_ids = membership.mapped("partner_id.id")
            if not partner_ids:
                return
            base_domain.append(("id", "in", partner_ids))

        # Resolve the cohort before fetching cached variable values.
        # No sudo: respect the operator's record rules, matching the
        # behaviour of cycle_manager_base._precompute_cycle_cached_variables.
        # Partners the operator can't see are excluded from the cohort and
        # cannot be enrolled — that's the correct outcome.
        subject_ids = self.env["res.partner"].search(base_domain).ids
        if not subject_ids:
            return

        cache_mgr = self.env["spp.data.cache.manager"]
        try:
            result = cache_mgr.precompute_cached_variables(
                subject_ids,
                period_key="current",
                program_id=self.program_id.id,
            )
        except Exception as e:
            # Don't let pre-warm failure block the eligibility check.
            # The CEL evaluator will report its own error if the cache
            # is still incomplete.
            _logger.warning(
                "Cache pre-warm failed for program %s (manager %s): %s",
                self.program_id.name,
                self.name,
                e,
            )
            return

        if result.get("success"):
            _logger.info(
                "Pre-warmed %d cached variable(s) for %d subject(s) before CEL eligibility on program %s",
                result.get("variables_processed", 0),
                len(subject_ids),
                self.program_id.name,
            )
        else:
            _logger.warning(
                "Cache pre-warm returned no success for program %s: %s",
                self.program_id.name,
                result.get("error_message"),
            )
