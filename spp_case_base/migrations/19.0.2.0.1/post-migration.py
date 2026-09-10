# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Release ``is_current`` on intervention plans that already finished.

``action_complete`` never cleared ``is_current`` (#458), and the only other
writer of ``is_current = False`` is the revision path, so a plan that finished
NORMALLY stayed its case's current plan forever. The code fix covers future
completions only; the rows already in a released database keep the incoherent
pair — ``case.current_plan_id`` pointing at completed work while
``has_active_plan`` reads False — and keep tripping the one-current-plan-per-case
constraint, so they are cleared here.

Deliberately narrow: only ``completed``. ``action_create_revision`` writes
``is_current = False`` together with ``revised``, so that state has no
equivalent stale population, and widening the predicate would demote plans this
fix makes no claim about.

Affected cases are left with NO current plan, which is the intended end state —
the plan is finished, and marking a fresh plan current is now possible again
(that constraint failure is the user-facing half of #458). The plan's own record
is untouched: ``state``, ``actual_end_date`` and its interventions all stay.

Raw SQL with no ORM invalidation, matching
``spp_grm_cel/migrations/19.0.2.0.2/post-migration.py``: nothing reads
``is_current`` through the ORM later in this transaction, and a flush-and-
invalidate would risk writing a cached value back over the UPDATE. Callers that
DO read back in the same transaction — the test for this script, for one — must
invalidate on their side.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        "UPDATE spp_case_intervention_plan SET is_current = false "
        "WHERE state = 'completed' AND is_current = true "
        "RETURNING case_id"
    )
    # One row per demoted plan; the one-current-plan constraint means a case
    # cannot appear twice, but sort and de-duplicate so the log is stable.
    case_ids = sorted({row[0] for row in cr.fetchall()})

    if case_ids:
        _logger.warning(
            "Released is_current on %s completed intervention plan(s) that were still "
            "flagged as their case's current plan. Cases affected (spp.case ids): %s. "
            "Those cases now report no current plan; where case work is continuing, "
            "mark the successor plan current on the case's Intervention Plans tab.",
            len(case_ids),
            ", ".join(str(cid) for cid in case_ids),
        )
