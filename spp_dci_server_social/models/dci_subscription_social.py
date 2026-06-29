# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Social Registry scoping for DCI event subscriptions.

Implements the registry-specific hooks the generic subscription model uses to
deliver notifications per subscriber: evaluating the subscription's stored
filter against a registrant, and building the DCI record payload with the
subscription's sender context (so consent/sender-scoped serialization applies).
"""

import json
import logging
from types import SimpleNamespace

from odoo import models

_logger = logging.getLogger(__name__)

_SOCIAL = "SOCIAL_REGISTRY"


class DCISubscriptionSocial(models.Model):
    _inherit = "spp.dci.subscription"

    def _filter_matching_partners(self, partner_ids):
        """Evaluate the subscription's filter_expression against registrants in batch.

        No filter -> all. Otherwise the stored filter (with its filter_type
        discriminator) is compiled to a domain via the Social Registry search
        service and intersected with partner_ids in a single query. Any
        parse/eval failure is treated as matching NOTHING (fail closed) so an
        unparseable filter never widens delivery.
        """
        self.ensure_one()
        if self.reg_type != _SOCIAL:
            return super()._filter_matching_partners(partner_ids)
        if not self.filter_expression:
            return list(partner_ids or [])
        if not partner_ids:
            return []
        try:
            from ..services.search_service import DCISocialSearchService

            criteria = SimpleNamespace(
                query_type=self.filter_type or "expression",
                query=json.loads(self.filter_expression),
            )
            service = DCISocialSearchService(self.env, self.sender_id)
            domain = service._build_domain(criteria)
            # sudo: matching the sender's declared filter against the registry;
            # consent/authorization is enforced separately by _consent_allows_partner.
            # nosemgrep: odoo-sudo-on-sensitive-models, odoo-sudo-without-context
            Partner = self.env["res.partner"].sudo()
            return Partner.search([("id", "in", list(partner_ids))] + domain).ids
        except Exception as e:
            _logger.warning(
                "Subscription %s: could not evaluate filter, dropping records (fail-closed): %s",
                self.subscription_code,
                e,
            )
            return []

    def _build_notification_records(self, partner_ids):
        """Build DCI records for partner_ids using this subscription's sender.

        Called only for already-eligible partners (consent + filter checked by
        the generic layer). Builds with sender context so any sender-scoped
        serialization applies.
        """
        self.ensure_one()
        if self.reg_type != _SOCIAL:
            return super()._build_notification_records(partner_ids)

        from ..services.search_service import DCISocialSearchService

        service = DCISocialSearchService(self.env, self.sender_id)
        partners = self.env["res.partner"].browse(partner_ids).exists()
        records = []
        for partner in partners:
            try:
                dci_record = service._to_dci_group(partner) if partner.is_group else service._to_dci_person(partner)
                records.append(dci_record.model_dump(mode="json", by_alias=True, exclude_none=True))
            except Exception as e:
                _logger.warning("Failed to convert partner %d to DCI format: %s", partner.id, e)
        return records
