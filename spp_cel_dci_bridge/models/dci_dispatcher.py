import logging

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

        registry_type = source.registry_type
        handler_name = self._HANDLERS.get(registry_type)
        if not handler_name:
            raise UserError(
                _(
                    "No DCI handler for registry_type=%(reg)s on variable "
                    "%(var)s",
                    reg=registry_type,
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
        """Skeleton; filled in by step 4."""
        return {}

    def _handler_crvs(self, variable, source, subject_ids, period_key):
        """Skeleton; filled in by step 9."""
        return {}

    def _handler_ibr(self, variable, source, subject_ids, period_key):
        """Skeleton; filled in by step 10."""
        return {}

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
