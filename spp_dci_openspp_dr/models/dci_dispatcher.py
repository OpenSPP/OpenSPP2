"""Bridge dispatcher override for vendor=openspp DR sources.

When a CEL variable's DCI data source has ``vendor='openspp'`` AND
``registry_type='DR'``, route the DR handler to ``OpenSPPDRService``
instead of the upstream ``DRService``. The handler is otherwise
structurally identical to the bridge's other handlers: per-subject
loop, audit row shape, attribute-path extraction.

Why this override exists: upstream ``DRService._extract_disability_data``
reads disability fields from ``data`` directly, but the SPDCI spec
(and our ``spp_dci_server_disability`` implementation) place records
at ``data.reg_records[0]``. Until upstream is fixed, this adapter owns
the response unwrap.

Clearing the ``vendor`` field on the data source returns the variable
to upstream ``DRService`` — useful once upstream is fixed and the
override becomes unnecessary.
"""

import logging
import time

from odoo import models

from odoo.addons.spp_cel_dci_bridge.exceptions import DCIConfigurationError

_logger = logging.getLogger(__name__)


class DCIDispatcher(models.AbstractModel):
    _inherit = "spp.cel.dci.dispatcher"

    def _handler_dr(self, variable, source, subject_ids, period_key):
        if getattr(source, "vendor", False) == "openspp":
            return self._handler_openspp_dr(variable, source, subject_ids, period_key)
        return super()._handler_dr(variable, source, subject_ids, period_key)

    def _handler_openspp_dr(self, variable, source, subject_ids, period_key):
        """DR handler backed by OpenSPPDRService.

        Structurally identical to the bridge's other handlers: per-subject
        loop, one audit row per subject, attribute extraction via
        variable.dci_attribute_path, error swallow with audit row capture.
        """
        try:
            from ..services.openspp_dr_service import OpenSPPDRService
        except ImportError as e:
            raise DCIConfigurationError(
                f"OpenSPP-DR service is not importable; cannot fetch "
                f"variable {variable.name}. Reinstall spp_dci_openspp_dr."
            ) from e

        service = OpenSPPDRService(self.env, data_source_code=source.code)
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
                    "OpenSPP-DR fetch failed for partner %d (var=%s): %s",
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
