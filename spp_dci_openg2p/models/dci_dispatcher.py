"""Bridge dispatcher override for OpenG2P-vendor sources.

When a CEL variable's DCI data source has ``vendor='openg2p'``, route the
SR handler to ``OpenG2PSocialService`` instead of failing through the
bridge's not-implemented stub. The handler is otherwise structurally
identical to the bridge's other registry-type handlers: same per-subject
loop, same audit row shape, same attribute-path extraction.

This is the Option C "adapter code" path from ADR-023 §6, retargeted by
ADR-024 — OpenG2P now plays its proper Social Registry role rather than
the FR-as-DR pretense it briefly held during v1 demo prep.
"""

import logging
import time

from odoo import models

from odoo.addons.spp_cel_dci_bridge.exceptions import DCIConfigurationError

_logger = logging.getLogger(__name__)


class DCIDispatcher(models.AbstractModel):
    _inherit = "spp.cel.dci.dispatcher"

    def _handler_sr(self, variable, source, subject_ids, period_key):
        # Route OpenG2P sources to the vendor-specific service. Sources
        # without a vendor (or with a different vendor) fall through to
        # the bridge's not-implemented stub, which raises
        # DCIConfigurationError — preserving the silent-failure guard.
        if getattr(source, "vendor", False) == "openg2p":
            return self._handler_openg2p_sr(variable, source, subject_ids, period_key)
        return super()._handler_sr(variable, source, subject_ids, period_key)

    def _handler_openg2p_sr(self, variable, source, subject_ids, period_key):
        """SR handler backed by OpenG2PSocialService.

        Structurally identical to the bridge's other handlers (_handler_dr,
        _handler_crvs, _handler_ibr): per-subject loop, audit row per
        subject, attribute extraction via variable.dci_attribute_path,
        error swallow with audit row capture.
        """
        try:
            from ..services.openg2p_social_service import OpenG2PSocialService
        except ImportError as e:
            # Should never happen — this module's __init__ imports the
            # service — but raise a clear error rather than silently
            # returning {} (would trigger ADR-023 Critical #2's silent
            # failure mode).
            raise DCIConfigurationError(
                f"OpenG2P Social service is not importable; cannot fetch "
                f"variable {variable.name}. Reinstall spp_dci_openg2p."
            ) from e

        service = OpenG2PSocialService(self.env, data_source_code=source.code)
        Partner = self.env["res.partner"]
        partners = Partner.browse(subject_ids).exists()
        path = variable.dci_attribute_path

        result = {}
        for partner in partners:
            started = time.monotonic()
            try:
                payload = service.get_partner_record(partner)
            except Exception as e:
                self._record_audit(variable, source, partner.id, "error", started, error_message=str(e))
                _logger.warning(
                    "OpenG2P SR fetch failed for partner %d (var=%s): %s",
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
