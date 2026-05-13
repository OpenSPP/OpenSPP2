import logging
import time

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DCIDispatcher(models.AbstractModel):
    """Route CEL variable fetches to the appropriate DCI registry-type handler.

    The dispatcher is the single seam between the CEL bridge and the DCI client
    family. It looks at the DCI data source attached to a CEL variable's
    provider, picks the handler keyed by `registry_type`, and asks it to
    resolve `{subject_id: value}` for the given subjects.

    Handlers tolerate missing DCI client modules: if `spp_dci_client_dr` is
    not installed, the DR handler returns `{}` and logs a warning rather than
    raising. This keeps the bridge installable in deployments that only need
    some registry types.
    """

    _name = "spp.cel.dci.dispatcher"
    _description = "CEL <-> DCI Dispatcher"

    _HANDLERS = {
        "DR": "_handler_dr",
        "CRVS": "_handler_crvs",
        "IBR": "_handler_ibr",
        "SR": "_handler_sr",
        "FR": "_handler_fr",
    }

    # The existing DCI client modules use inconsistent registry_type strings:
    #   - spp_dci_client_dr checks for "DR"
    #   - spp_dci_client_crvs checks for "ns:org:RegistryType:Civil"
    #   - spp_dci_client_ibr checks for "ibr"
    # The bridge accepts every known form and maps it to a canonical key
    # before dispatching. Upstream cleanup of the registry_type field is
    # tracked separately; the bridge cannot wait on that.
    _REGISTRY_TYPE_ALIASES = {
        "DR": "DR",
        "dr": "DR",
        "ns:org:RegistryType:DR": "DR",
        "CRVS": "CRVS",
        "crvs": "CRVS",
        "ns:org:RegistryType:Civil": "CRVS",
        "IBR": "IBR",
        "ibr": "IBR",
        "ns:org:RegistryType:IBR": "IBR",
        "SR": "SR",
        "SOCIAL_REGISTRY": "SR",
        "ns:org:RegistryType:Social": "SR",
        "FR": "FR",
        "FUNCTIONAL_REGISTRY": "FR",
        "ns:org:RegistryType:FR": "FR",
    }

    @api.model
    def fetch_values_for_variable(self, variable, subject_ids, period_key):
        """Resolve values for a CEL variable backed by a DCI registry.

        Args:
            variable: spp.cel.variable record with source_type='external'
                and a DCI-backed external_provider_id.
            subject_ids: list of res.partner IDs to fetch values for.
            period_key: period key (e.g., 'current', '2026-Q2').

        Returns:
            dict mapping subject_id to the extracted attribute value.
            Subjects with no resolvable value are omitted from the dict;
            the cache manager records them as null.
        """
        if not subject_ids:
            return {}

        provider = variable.external_provider_id
        if not provider or not provider.is_dci_backed:
            return {}

        source = provider.dci_data_source_id
        if not source or not source.active:
            _logger.warning(
                "Variable %s: DCI source %s is missing or inactive",
                variable.name,
                source and source.code,
            )
            return {}

        canonical = self._REGISTRY_TYPE_ALIASES.get(source.registry_type)
        handler_name = self._HANDLERS.get(canonical) if canonical else None
        if not handler_name:
            raise UserError(
                _(
                    "No DCI handler for registry_type=%(reg)s on variable %(var)s",
                    reg=source.registry_type,
                    var=variable.name,
                )
            )

        handler = getattr(self, handler_name)
        return handler(variable, source, subject_ids, period_key)

    # ------------------------------------------------------------------
    # Registry-type handlers
    #
    # Each handler:
    #   - Checks the corresponding DCI client module is installed.
    #   - Iterates subject_ids, calling the underlying DCI service per subject.
    #   - Extracts the attribute named by variable.dci_attribute_path.
    #   - Returns {subject_id: value}; subjects with no value are omitted.
    # ------------------------------------------------------------------

    def _handler_dr(self, variable, source, subject_ids, period_key):
        """Call the Disability Registry DCI service for each subject.

        Returns {subject_id: value} where value is the attribute named by
        `variable.dci_attribute_path` extracted from the DR response payload.
        Subjects with no DR record, no matching identifier, or no value at
        the configured path are omitted from the returned dict.

        Records one spp.dci.fetch.audit row per subject regardless of outcome.
        """
        try:
            from odoo.addons.spp_dci_client_dr.services.dr_service import (
                DRService,
            )
        except ImportError:
            _logger.warning(
                "spp_dci_client_dr is not installed; cannot fetch variable "
                "%s. Install spp_dci_client_dr or remove the variable.",
                variable.name,
            )
            return {}

        service = DRService(self.env, data_source_code=source.code)
        Partner = self.env["res.partner"]
        partners = Partner.browse(subject_ids).exists()
        path = variable.dci_attribute_path

        result = {}
        for partner in partners:
            started = time.monotonic()
            try:
                payload = service.get_disability_status(partner)
            except Exception as e:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "error",
                    started,
                    error_message=str(e),
                )
                _logger.warning(
                    "DR fetch failed for partner %d (var=%s): %s",
                    partner.id,
                    variable.name,
                    e,
                )
                continue

            if payload is None:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "not_found",
                    started,
                )
                continue

            value = self._extract_by_path(payload, path)
            if value is None:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "not_found",
                    started,
                )
                continue

            result[partner.id] = value
            self._record_audit(
                variable,
                source,
                partner.id,
                "ok",
                started,
            )

        return result

    # ------------------------------------------------------------------
    # Audit logging
    # ------------------------------------------------------------------

    def _record_audit(self, variable, source, subject_id, result, started_at, error_message=None):
        """Write one spp.dci.fetch.audit row.

        Captures the acting user id BEFORE escalating to sudo so the audit
        preserves operator attribution. Without this, the user_id field's
        `default=lambda self: self.env.user` resolves against the sudoed env
        and every row records as user_root — defeating the compliance
        purpose. Audit writes go through sudo because background workers
        (precompute job, cycle pre-fetch) may not hold spp_admin rights,
        but every fetch must produce a row. Reading the audit is still
        ACL-gated.
        """
        try:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            acting_user_id = self.env.uid
            # sudo() is intentional: background workers may not have write
            # rights on the audit model, but every fetch must produce a row.
            # acting_user_id captured above preserves operator attribution.
            self.env["spp.dci.fetch.audit"].sudo().create(  # nosemgrep: odoo-sudo-without-context
                {
                    "user_id": acting_user_id,
                    "provider_code": variable.external_provider_id.code,
                    "data_source_code": source.code,
                    "registry_type": source.registry_type,
                    "variable_name": variable.name,
                    "subject_model": "res.partner",
                    "subject_id": subject_id,
                    "result": result,
                    "error_message": error_message,
                    "elapsed_ms": elapsed_ms,
                }
            )
        except Exception as e:  # never let audit failures break the fetch
            _logger.error("Failed to write DCI fetch audit row: %s", e)

    def _handler_crvs(self, variable, source, subject_ids, period_key):
        """Call the CRVS DCI service for each subject.

        CRVS's verify_birth takes (identifier_type, identifier_value) rather
        than a partner, so the handler resolves the partner's first identifier
        before calling the service. Subjects without any identifier are
        recorded as not_found and omitted from the result.
        """
        try:
            from odoo.addons.spp_dci_client_crvs.services.crvs_service import (
                CRVSService,
            )
        except ImportError:
            _logger.warning(
                "spp_dci_client_crvs is not installed; cannot fetch variable %s.",
                variable.name,
            )
            return {}

        service = CRVSService(self.env, data_source_code=source.code)
        Partner = self.env["res.partner"]
        partners = Partner.browse(subject_ids).exists()
        path = variable.dci_attribute_path

        result = {}
        for partner in partners:
            started = time.monotonic()
            identifier = self._first_identifier(partner)
            if identifier is None:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "not_found",
                    started,
                    error_message="no identifier",
                )
                continue

            id_type, id_value = identifier
            try:
                payload = service.verify_birth(id_type, id_value)
            except Exception as e:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "error",
                    started,
                    error_message=str(e),
                )
                _logger.warning(
                    "CRVS fetch failed for partner %d (var=%s): %s",
                    partner.id,
                    variable.name,
                    e,
                )
                continue

            if payload is None:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "not_found",
                    started,
                )
                continue

            value = self._extract_by_path(payload, path)
            if value is None:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "not_found",
                    started,
                )
                continue

            result[partner.id] = value
            self._record_audit(
                variable,
                source,
                partner.id,
                "ok",
                started,
            )

        return result

    def _handler_ibr(self, variable, source, subject_ids, period_key):
        """Call the IBR DCI service for each subject.

        IBR's check_duplication takes a partner directly and returns a dict
        with keys is_duplicate, matched_programs, raw_response. The variable's
        dci_attribute_path picks the field of interest.
        """
        try:
            from odoo.addons.spp_dci_client_ibr.services.ibr_service import (
                IBRService,
            )
        except ImportError:
            _logger.warning(
                "spp_dci_client_ibr is not installed; cannot fetch variable %s.",
                variable.name,
            )
            return {}

        # IBRService takes (data_source, env) — different from DR/CRVS
        service = IBRService(source, self.env)
        Partner = self.env["res.partner"]
        partners = Partner.browse(subject_ids).exists()
        path = variable.dci_attribute_path

        result = {}
        for partner in partners:
            started = time.monotonic()
            try:
                payload = service.check_duplication(partner)
            except Exception as e:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "error",
                    started,
                    error_message=str(e),
                )
                _logger.warning(
                    "IBR fetch failed for partner %d (var=%s): %s",
                    partner.id,
                    variable.name,
                    e,
                )
                continue

            if payload is None:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "not_found",
                    started,
                )
                continue

            value = self._extract_by_path(payload, path)
            if value is None:
                self._record_audit(
                    variable,
                    source,
                    partner.id,
                    "not_found",
                    started,
                )
                continue

            result[partner.id] = value
            self._record_audit(
                variable,
                source,
                partner.id,
                "ok",
                started,
            )

        return result

    @staticmethod
    def _first_identifier(partner):
        """Return (id_type_code, id_value) for the partner's first reg id, or None."""
        reg = partner.reg_ids[:1]
        if not reg or not reg.id_type_id:
            return None
        code = reg.id_type_id.code or reg.id_type_id.name
        if not code or not reg.value:
            return None
        return (code, reg.value)

    def _handler_sr(self, variable, source, subject_ids, period_key):
        """Social Registry handler; not implemented in v1."""
        _logger.info(
            "SR handler not implemented; returning empty for variable %s",
            variable.name,
        )
        return {}

    def _handler_fr(self, variable, source, subject_ids, period_key):
        """Functional Registry handler; not implemented in v1."""
        _logger.info(
            "FR handler not implemented; returning empty for variable %s",
            variable.name,
        )
        return {}

    # ------------------------------------------------------------------
    # Helpers shared by handlers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_by_path(payload, dotted_path):
        """Resolve a dotted path against a nested dict.

        Returns None if any segment is missing. Used to map a DCI response
        payload to the single scalar value the CEL variable represents.
        """
        if not payload or not dotted_path:
            return None
        cursor = payload
        for segment in dotted_path.split("."):
            if not isinstance(cursor, dict):
                return None
            if segment not in cursor:
                return None
            cursor = cursor[segment]
        return cursor
