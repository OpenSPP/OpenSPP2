"""Bridge dispatcher override for OpenG2P-vendor sources.

When a CEL variable's DCI data source has ``vendor='openg2p'``, route the
DR handler to ``OpenG2PFRService`` instead of the upstream ``DRService``.
The handler is otherwise structurally identical to the bridge's
``_handler_dr``: same per-subject loop, same audit row shape, same
attribute-path extraction.

This is the Option C "adapter code" path from ADR-023 §6. Until OpenG2P's
real Disability Registry endpoint is available, the demo deployment uses
the Farmer Registry as a DR stand-in (FR-as-DR pretense). See
``services/openg2p_fr_service.py`` for the migration plan.
"""

import logging
import time

from odoo import models

from odoo.addons.spp_cel_dci_bridge.exceptions import DCIConfigurationError

_logger = logging.getLogger(__name__)


class DCIDispatcher(models.AbstractModel):
    _inherit = "spp.cel.dci.dispatcher"

    def _handler_dr(self, variable, source, subject_ids, period_key):
        # Route OpenG2P sources to the vendor-specific service. Sources
        # without a vendor (or with a different vendor) fall through to
        # the upstream DR handler.
        if getattr(source, "vendor", False) == "openg2p":
            return self._handler_openg2p_fr(variable, source, subject_ids, period_key)
        return super()._handler_dr(variable, source, subject_ids, period_key)

    def _handler_openg2p_fr(self, variable, source, subject_ids, period_key):
        """Mirror of _handler_dr but using OpenG2PFRService.

        Kept structurally identical to the upstream DR handler so the
        bridge's per-subject loop semantics (audit row shape, attribute
        extraction, error swallow) match exactly. This lets the upstream
        handler's tests stand in as parity checks until OpenG2P provides
        a real DR endpoint and this override becomes unnecessary.
        """
        try:
            from ..services.openg2p_fr_service import OpenG2PFRService
        except ImportError as e:
            # Should never happen — this module's __init__ imports the
            # service — but raise a clear error rather than silently
            # returning {} (would trigger Critical #2's silent failure).
            raise DCIConfigurationError(
                f"OpenG2P FR service is not importable; cannot fetch "
                f"variable {variable.name}. Reinstall spp_dci_openg2p."
            ) from e

        service = OpenG2PFRService(self.env, data_source_code=source.code)
        Partner = self.env["res.partner"]
        partners = Partner.browse(subject_ids).exists()
        path = variable.dci_attribute_path

        result = {}
        for partner in partners:
            started = time.monotonic()
            try:
                payload = service.get_disability_status(partner)
            except Exception as e:
                self._record_audit(variable, source, partner.id, "error", started, error_message=str(e))
                _logger.warning(
                    "OpenG2P FR fetch failed for partner %d (var=%s): %s",
                    partner.id,
                    variable.name,
                    e,
                )
                continue

            if payload is None:
                self._record_audit(variable, source, partner.id, "not_found", started)
                continue

            value = self._extract_by_path(payload, path)
            if value is None:
                self._record_audit(variable, source, partner.id, "not_found", started)
                continue

            result[partner.id] = value
            self._record_audit(variable, source, partner.id, "ok", started)

        return result
