import logging

from odoo import _, models
from odoo.exceptions import UserError

from ..exceptions import DCIConfigurationError

_logger = logging.getLogger(__name__)


class DataCacheManager(models.AbstractModel):
    """Route DCI-backed external CEL variables through the DCI dispatcher.

    The parent implementation (spp_cel_domain) treats source_type='external'
    as a push-only path: it returns {} and logs that values must be pushed
    via API. This override fills that gap by calling the dispatcher for
    variables whose external_provider_id is linked to a DCI data source.

    Non-DCI external variables continue to fall through to the parent
    implementation unchanged.
    """

    _inherit = "spp.data.cache.manager"

    def _compute_variable_values(self, variable, subject_ids, period_key, program_id):
        if (
            variable.source_type == "external"
            and variable.external_provider_id
            and variable.external_provider_id.is_dci_backed
        ):
            return self._compute_dci_values(variable, subject_ids, period_key, program_id)
        return super()._compute_variable_values(variable, subject_ids, period_key, program_id)

    def _compute_dci_values(self, variable, subject_ids, period_key, program_id):
        """Fetch DCI-backed values, then apply the variable's failure policy.

        Every queried subject ends up in the returned dict — either with the
        fetched value, the last-known cached value (last_known policy), or
        explicit None (null policy). This ensures the resulting cache covers
        the entire cohort, so the CEL executor's metric SQL fast path sees a
        'fresh' cache state and uses SQL instead of falling back to Python
        evaluation (which requires spp.indicator).
        """
        dispatcher = self.env["spp.cel.dci.dispatcher"]
        policy = variable.external_failure_policy or "null"

        try:
            values = dispatcher.fetch_values_for_variable(variable, subject_ids, period_key)
        except DCIConfigurationError:
            # Configuration errors (missing client module, unimplemented
            # handler) always propagate, regardless of policy. Silently
            # treating these as "no one is eligible" would be a compliance
            # hazard — operators must see the broken setup immediately.
            raise
        except Exception as e:
            _logger.error(
                "DCI fetch failed for variable %s (policy=%s): %s",
                variable.name,
                policy,
                e,
                exc_info=True,
            )
            if policy == "fail":
                raise UserError(
                    _(
                        "DCI fetch failed for variable '%(var)s': %(err)s",
                        var=variable.name,
                        err=e,
                    )
                ) from e
            values = {}

        if policy == "last_known":
            missing = set(subject_ids) - set(values.keys())
            if missing:
                values = self._augment_with_last_known(variable, values, missing)

        # Fill any still-missing subjects with explicit None. The cache writer
        # records {"value": null}; CEL boolean comparisons against null
        # evaluate to null (postgres) which fails WHERE clauses — i.e., the
        # subject does not match `has_disability == true`, which is the right
        # semantic for "we asked the registry and got nothing back."
        for sid in subject_ids:
            values.setdefault(sid, None)

        return values

    def _augment_with_last_known(self, variable, values, missing_subject_ids):
        """Fill missing subjects from the most recent cached non-null value.

        Ignores expiry — the whole point of 'last_known' policy is to surface
        stale-but-known answers when the live source is unavailable. Logs a
        warning per subject so operators can see what's degraded.

        Uses DISTINCT ON to pick the latest non-null row per subject in a
        single query. The ORM-search-then-filter approach would fetch every
        historical row for the missing subjects and Python-filter to the
        latest — fine at demo scale, but O(history × cohort) and degrades
        sharply for deployments with daily TTL refresh over months.

        Filters out JSON null (`{"value": null}`) at the SQL layer so we
        don't surface "we previously fetched nothing" as a last-known value.
        """
        if not missing_subject_ids:
            return values

        missing_list = list(missing_subject_ids)
        self.env.cr.execute(
            """
            SELECT DISTINCT ON (subject_id)
                subject_id,
                value_json,
                recorded_at
            FROM spp_data_value
            WHERE variable_name = %s
              AND subject_id = ANY(%s)
              AND subject_model = %s
              AND company_id = %s
              AND (value_json -> 'value') IS NOT NULL
              AND (value_json -> 'value') != 'null'::jsonb
            ORDER BY subject_id, recorded_at DESC, id DESC
            """,
            (
                variable.name,
                missing_list,
                "res.partner",
                self.env.company.id,
            ),
        )

        filled = dict(values)
        for subject_id, value_json, recorded_at in self.env.cr.fetchall():
            payload = value_json
            if not isinstance(payload, dict):
                continue
            inner = payload.get("value")
            if inner is None:
                continue  # belt-and-suspenders; SQL filter should have excluded these
            filled[subject_id] = inner
            _logger.warning(
                "Variable %s: using last-known value for subject %d (recorded_at=%s) due to fetch failure",
                variable.name,
                subject_id,
                recorded_at,
            )
        return filled
