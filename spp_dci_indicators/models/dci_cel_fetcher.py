"""DCI CEL value fetcher.

Implements the outbound fetch for DCI-backed external CEL variables: given a
variable whose data provider is linked to a DCI Data Source, resolve each
subject's identifier, call the appropriate DCI registry service against that
Data Source, and return the computed metric values keyed by subject id.

The result is consumed by the cache manager override (see
data_cache_manager_dci.py), which stores the values in spp.data.value, so all
CEL consumers read them uniformly. The metric a variable represents is keyed
by its cel_accessor, following the <registry>.dci.<metric> convention.
"""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Identifier-type priority when resolving a partner's identifier to send to a
# registry. Mirrors DRService._get_partner_identifier.
_IDENTIFIER_PRIORITY = ["UIN", "DRN", "NATIONAL_ID", "NID", "BRN"]

# Parameterized DCI methods: cel_accessor -> the enumerated argument set + value
# type. Each (subject, arg) is cached as a separate spp.data.value row keyed by
# params (params_hash), e.g. dr.dci.severity('Vision') or crvs.dci.has_event('death').
DCI_METHOD_ACCESSORS = {
    "dr.dci.severity": {"args": ["Vision", "Hearing", "Mobility"], "value_type": "number"},
    "crvs.dci.has_event": {"args": ["birth", "death"], "value_type": "boolean"},
}


class DCICelFetcher(models.AbstractModel):
    _name = "spp.dci.cel.fetcher"
    _description = "DCI CEL Value Fetcher"

    def fetch_values(self, variable, subject_ids):
        """Fetch DCI metric values for a variable across subjects.

        Args:
            variable: spp.cel.variable (source_type='external', DCI-backed provider)
            subject_ids: list of res.partner ids

        Returns:
            dict: {subject_id: value} for subjects a value could be fetched for.
        """
        data_source = variable.external_provider_id.dci_data_source_id
        if not data_source:
            return {}

        handler = self._dci_metric_handlers().get(variable.cel_accessor)
        if not handler:
            _logger.warning(
                "No DCI fetch handler registered for accessor '%s' (variable %s)",
                variable.cel_accessor,
                variable.name,
            )
            return {}

        results = {}
        for partner in self.env["res.partner"].browse(subject_ids):
            identifier = self._get_partner_identifier(partner)
            if not identifier:
                _logger.debug("No identifier for partner %s; skipping DCI fetch", partner.id)
                continue
            id_type, id_value = identifier
            try:
                # Handlers are bound methods from _dci_metric_handlers().
                value = handler(data_source, partner, id_type, id_value)
            except Exception as e:
                # A single subject's failure must not abort the batch.
                _logger.error(
                    "DCI fetch failed for accessor '%s' on partner %s: %s",
                    variable.cel_accessor,
                    partner.id,
                    e,
                )
                continue
            if value is not None:
                results[partner.id] = value
        return results

    @api.model
    def _dci_backed_variables(self):
        """All active, cached, DCI-backed external CEL variables."""
        return self.env["spp.cel.variable"].search(
            [
                ("active", "=", True),
                ("source_type", "=", "external"),
                ("cache_strategy", "in", ["ttl", "manual"]),
                ("external_provider_id.is_dci_backed", "=", True),
            ]
        )

    @api.model
    def sync_for_partners(self, partner_ids, variables=None):
        """Fetch + cache all DCI-backed variables for the given partners.

        Returns the number of (variable, subject) values cached. Reuses the cache
        manager's precompute path, which calls this fetcher and stores the result
        in spp.data.value.
        """
        partner_ids = list(partner_ids or [])
        if not partner_ids:
            return 0
        if variables is None:
            variables = self._dci_backed_variables()
        mgr = self.env["spp.data.cache.manager"]
        total = 0
        for variable in variables:
            if variable.cel_accessor in DCI_METHOD_ACCESSORS:
                # Parameterized method: materialize one params-keyed row per argument.
                total += self._materialize_method_variable(variable, partner_ids)
            else:
                result = mgr.precompute_variable(variable.name, partner_ids)
                if isinstance(result, dict):
                    total += result.get("cached", 0)
        return total

    def _materialize_method_variable(self, variable, partner_ids):
        """Cache a parameterized method variable: one spp.data.value row per
        (subject, argument), keyed by params={'arg': <argument>}."""
        accessor = variable.cel_accessor
        data_source = variable.external_provider_id.dci_data_source_id
        if not data_source:
            return 0
        value_type = DCI_METHOD_ACCESSORS[accessor]["value_type"]
        rows = []
        for partner in self.env["res.partner"].browse(partner_ids):
            identifier = self._get_partner_identifier(partner)
            if not identifier:
                continue
            id_type, id_value = identifier
            try:
                pairs = self._compute_method_values(accessor, data_source, partner, id_type, id_value)
            except Exception as e:
                _logger.error("DCI method fetch failed for '%s' on partner %s: %s", accessor, partner.id, e)
                continue
            for params, value in pairs:
                if value is None:
                    continue
                rows.append(
                    {
                        "variable_name": accessor,
                        "subject_model": "res.partner",
                        "subject_id": partner.id,
                        "period_key": "current",
                        "value_json": {"value": int(value) if isinstance(value, bool) else value},
                        "value_type": value_type,
                        "source_type": "external",
                        "params": params,
                        "ttl_seconds": variable.cache_ttl_seconds or None,
                    }
                )
        if rows:
            self.env["spp.data.value"].upsert_values(rows)
        return len(rows)

    def _compute_method_values(self, accessor, data_source, partner, id_type, id_value):
        """Return [(params, value), ...] for each enumerated argument of a method."""
        args = DCI_METHOD_ACCESSORS[accessor]["args"]
        if accessor == "dr.dci.severity":
            scores = self._dr_status(data_source, partner).get("functional_scores") or {}
            return [({"arg": t}, scores.get(t) or 0) for t in args]
        if accessor == "crvs.dci.has_event":
            svc = self._crvs_service(data_source)
            out = []
            for event in args:
                if event == "birth":
                    value = svc.verify_birth(id_type, id_value) is not None
                elif event == "death":
                    value = svc.check_death(id_type, id_value)
                else:
                    continue
                out.append(({"arg": event}, value))
            return out
        return []

    @api.model
    def cron_sync_all_registrants(self, batch_size=500):
        """Scheduled sync of all registrants' DCI variables (inactive by default)."""
        variables = self._dci_backed_variables()
        if not variables:
            return
        partners = self.env["res.partner"].search([("is_registrant", "=", True)])
        for offset in range(0, len(partners), batch_size):
            batch = partners[offset : offset + batch_size]
            self.sync_for_partners(batch.ids, variables=variables)

    def _get_partner_identifier(self, partner):
        """Resolve a (identifier_type, identifier_value) for the partner from
        its spp.registry.id records, using the registry priority order."""
        # The One2many is prefetched across the whole browsed batch, so
        # per-partner access here does not issue one query per partner.
        reg_ids = partner.reg_ids
        for id_type in _IDENTIFIER_PRIORITY:
            for reg_id in reg_ids:
                if reg_id.id_type_id.code == id_type and reg_id.value:
                    return (reg_id.id_type_id.code, reg_id.value)
        if reg_ids:
            first = reg_ids[0]
            if first.value:
                return (first.id_type_id.code, first.value)
        return None

    @api.model
    def _dci_metric_handlers(self):
        """Map a variable's cel_accessor to a handler computing its value.

        Handlers receive (self, data_source, id_type, id_value) and return the
        metric value (or None to skip). Keyed by the <registry>.dci.<metric>
        accessor convention.
        """
        return {
            "crvs.dci.is_alive": self._crvs_is_alive,
            "crvs.dci.birth_verified": self._crvs_birth_verified,
            "dr.dci.has_disability": self._dr_has_disability,
            "dr.dci.assessed": self._dr_assessed,
            "dr.dci.vision_severe": self._dr_vision_severe,
            "dr.dci.hearing_severe": self._dr_hearing_severe,
            "dr.dci.mobility_severe": self._dr_mobility_severe,
            "sr.dci.is_registered": self._sr_is_registered,
            "sr.dci.program_count": self._sr_program_count,
            "sr.dci.has_programs": self._sr_has_programs,
            "sr.dci.household_size": self._sr_household_size,
            "sr.dci.is_head_of_household": self._sr_is_head_of_household,
            "sr.dci.large_household": self._sr_large_household,
        }

    # ── CRVS handlers (identifier-based) ──────────────────────────────────────

    def _crvs_service(self, data_source):
        from odoo.addons.spp_dci_client_crvs.services import CRVSService

        return CRVSService(self.env, data_source.code)

    def _crvs_is_alive(self, data_source, partner, id_type, id_value):
        # Alive == no death record found in CRVS.
        return not self._crvs_service(data_source).check_death(id_type, id_value)

    def _crvs_birth_verified(self, data_source, partner, id_type, id_value):
        return self._crvs_service(data_source).verify_birth(id_type, id_value) is not None

    # ── SR handlers (identifier-based; one person record feeds all metrics) ────

    # "more than 5 members" per the seeded dci.sr.large_household variable
    _SR_LARGE_HOUSEHOLD_THRESHOLD = 5

    def _sr_service(self, data_source):
        from odoo.addons.spp_dci_client_sr.services import SRService

        return SRService(self.env, data_source.code)

    def _sr_person(self, data_source, id_type, id_value):
        """Fetch the person record from the Social Registry, or None."""
        return self._sr_service(data_source).search_person(id_type, id_value)

    def _sr_is_registered(self, data_source, partner, id_type, id_value):
        # Not found is a meaningful False, not missing data.
        return self._sr_person(data_source, id_type, id_value) is not None

    def _sr_program_count(self, data_source, partner, id_type, id_value):
        person = self._sr_person(data_source, id_type, id_value)
        if person is None:
            return None
        return len(person.get("enrolled_programs") or [])

    def _sr_has_programs(self, data_source, partner, id_type, id_value):
        person = self._sr_person(data_source, id_type, id_value)
        if person is None:
            return None
        return bool(person.get("enrolled_programs"))

    def _sr_household_size(self, data_source, partner, id_type, id_value):
        person = self._sr_person(data_source, id_type, id_value)
        if person is None:
            return None
        # No household summary -> size unknown, skip (no cache row).
        return (person.get("household_info") or {}).get("household_size")

    def _sr_is_head_of_household(self, data_source, partner, id_type, id_value):
        person = self._sr_person(data_source, id_type, id_value)
        if person is None:
            return None
        # Registered but household-less -> not a head.
        return bool((person.get("household_info") or {}).get("is_household_head"))

    def _sr_large_household(self, data_source, partner, id_type, id_value):
        person = self._sr_person(data_source, id_type, id_value)
        if person is None:
            return None
        size = (person.get("household_info") or {}).get("household_size") or 0
        return size > self._SR_LARGE_HOUSEHOLD_THRESHOLD

    # ── DR handlers (partner-based; the service resolves the identifier) ───────

    def _dr_status(self, data_source, partner):
        """Return the DR disability-status dict for a partner (or {})."""
        from odoo.addons.spp_dci_client_dr.services.dr_service import DRService

        return DRService(self.env, data_source.code).get_disability_status(partner) or {}

    def _dr_has_disability(self, data_source, partner, id_type, id_value):
        return bool(self._dr_status(data_source, partner).get("has_disability"))

    def _dr_assessed(self, data_source, partner, id_type, id_value):
        return bool(self._dr_status(data_source, partner).get("assessment_date"))

    def _dr_severity(self, data_source, partner, kind):
        scores = self._dr_status(data_source, partner).get("functional_scores") or {}
        return (scores.get(kind) or 0) >= 3

    def _dr_vision_severe(self, data_source, partner, id_type, id_value):
        return self._dr_severity(data_source, partner, "Vision")

    def _dr_hearing_severe(self, data_source, partner, id_type, id_value):
        return self._dr_severity(data_source, partner, "Hearing")

    def _dr_mobility_severe(self, data_source, partner, id_type, id_value):
        return self._dr_severity(data_source, partner, "Mobility")
