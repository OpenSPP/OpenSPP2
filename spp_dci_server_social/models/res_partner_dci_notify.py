# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend res.partner to trigger DCI notifications on changes.

Uses post-commit hooks + queue_job with identity_key for deduplication:
- Post-commit ensures notifications only fire after successful transaction
- Identity_key deduplicates multiple writes in the same request window
"""

import hashlib
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

# Fields that trigger update notifications when modified
TRACKED_FIELDS = {
    "name",
    "given_name",
    "family_name",
    "addl_name",
    "birthdate",
    "gender",
    "gender_id",
    "phone",
    "mobile",
    "email",
    "street",
    "street2",
    "city",
    "zip",
    "state_id",
    "country_id",
    "is_group",
    "active",
}

# Batch window for deduplication (seconds) - jobs within this window are collapsed
DEDUP_WINDOW_SECONDS = 60


class ResPartnerDCINotify(models.Model):
    """Extend res.partner to trigger DCI event notifications.

    When registrants are created, modified, or deleted, queues
    notification jobs to deliver callbacks to DCI subscribers.
    """

    _inherit = "res.partner"

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger DCI registration notifications."""
        records = super().create(vals_list)

        # Filter to only registrants
        registrants = records.filtered(lambda r: r.is_registrant)
        if registrants:
            self._schedule_dci_notification("registration", registrants.ids)

        return records

    def write(self, vals):
        """Override write to trigger DCI update notifications."""
        # Check if any tracked fields are being modified
        tracked_modified = bool(TRACKED_FIELDS & set(vals.keys()))

        # Store pre-write state for registrant IDs
        registrant_ids = []
        if tracked_modified:
            registrant_ids = self.filtered(lambda r: r.is_registrant).ids

        result = super().write(vals)

        # Queue update notification for affected registrants
        if registrant_ids and tracked_modified:
            self._schedule_dci_notification("update", registrant_ids)

        return result

    def unlink(self):
        """Override unlink to trigger DCI delete notifications."""
        # Snapshot identifiers before deletion - the records are gone by the
        # time the notification job runs, and subscribers must receive
        # external identifiers, never raw database ids.
        registrants = self.filtered(lambda r: r.is_registrant)
        registrant_ids = registrants.ids
        delete_payloads = registrants._dci_delete_payloads()

        result = super().unlink()

        if registrant_ids:
            self._schedule_dci_notification("delete", registrant_ids, payloads=delete_payloads)

        return result

    def _dci_delete_payloads(self):
        """Snapshot external identifiers + per-subscription eligibility for delete.

        Returns one payload dict per registrant in ``self`` containing the
        registrant's external identifiers (namespace URI preferred, falling
        back to the vocabulary code) and the ids of the delete subscriptions
        whose sender is allowed to be told about this registrant (consent +
        filter), computed now while the record still exists. Raw database ids
        are deliberately not included (api-design principle: never expose DB IDs).
        """
        delete_subs = self.env["spp.dci.subscription"]
        if "spp.dci.subscription" in self.env:
            delete_subs = delete_subs._matching_subscriptions("delete", "SOCIAL_REGISTRY")

        payloads = []
        for partner in self:
            identifiers = [
                {
                    "identifier_type": reg_id.id_type_id.namespace_uri or reg_id.id_type_id.code,
                    "identifier_value": reg_id.value,
                }
                for reg_id in partner.reg_ids
                if reg_id.value and reg_id.id_type_id
            ]
            eligible_subscription_ids = [
                sub.id
                for sub in delete_subs
                if sub._consent_allows_partner(partner.id) and sub._partner_matches_filter(partner.id)
            ]
            payloads.append(
                {
                    "identifiers": identifiers,
                    "eligible_subscription_ids": eligible_subscription_ids,
                }
            )
        return payloads

    def _schedule_dci_notification(self, event_type, partner_ids, payloads=None):
        """Schedule DCI notification via post-commit hook.

        Uses post-commit to ensure notification only fires after
        successful transaction commit. Multiple calls within the
        same request are batched together.

        Args:
            event_type: One of 'registration', 'update', 'delete'
            partner_ids: List of partner IDs to notify about
        """
        if not partner_ids:
            return

        # Check if notifications are enabled
        if not self._dci_notifications_enabled():
            return

        # Use post-commit hook to defer notification until transaction commits
        # This ensures we don't notify about rolled-back changes
        def notify_on_commit():
            self._queue_dci_notification_job(event_type, partner_ids, payloads=payloads)

        # Register post-commit callback
        self.env.cr.postcommit.add(notify_on_commit)

        _logger.debug(
            "Scheduled DCI %s notification for %d partner(s) on commit",
            event_type,
            len(partner_ids),
        )

    def _dci_notifications_enabled(self):
        """Check if DCI notifications are enabled.

        Returns:
            bool: True if notifications should be sent
        """
        # Check system parameter
        config = self.env["ir.config_parameter"].sudo()  # nosemgrep: odoo-sudo-without-context
        enabled = config.get_param("dci.notifications_enabled", "true").lower() == "true"
        return enabled

    def _queue_dci_notification_job(self, event_type, partner_ids, payloads=None):
        """Queue the actual notification job with deduplication.

        Uses queue_job with identity_key to deduplicate multiple
        notifications for the same partners within a time window.

        Args:
            event_type: One of 'registration', 'update', 'delete'
            partner_ids: List of partner IDs to notify about
        """
        if not partner_ids:
            return

        # Create identity key for deduplication
        # Jobs with same identity key within the window are collapsed
        identity_key = self._get_notification_identity_key(event_type, partner_ids)

        # Queue the notification job
        try:
            self.with_delay(
                channel="root.dci",
                description=f"DCI {event_type} notification ({len(partner_ids)} records)",
                identity_key=identity_key,
            )._execute_dci_notification(event_type, partner_ids, payloads=payloads)

            _logger.debug(
                "Queued DCI %s notification job for partner IDs: %s",
                event_type,
                partner_ids,
            )
        except Exception as e:
            _logger.error("Failed to queue DCI notification job: %s", str(e))

    def _get_notification_identity_key(self, event_type, partner_ids):
        """Generate identity key for job deduplication.

        Creates a deterministic key based on event type and partner IDs.
        Jobs with the same key are deduplicated by queue_job.

        Args:
            event_type: The event type
            partner_ids: List of partner IDs

        Returns:
            str: Identity key for deduplication
        """
        # Sort IDs for consistent key regardless of order
        sorted_ids = sorted(partner_ids)
        key_data = f"dci_notify:{event_type}:{','.join(map(str, sorted_ids))}"
        # Use hash to keep key length manageable
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def _execute_dci_notification(self, event_type, partner_ids, payloads=None):
        """Execute the DCI notification (called by queue_job).

        Builds notification payload and calls subscription.notify_event().

        Args:
            event_type: One of 'registration', 'update', 'delete'
            partner_ids: List of partner IDs to notify about
            payloads: For delete events, identifier payloads snapshotted
                before the records were removed
        """
        if not partner_ids:
            return

        _logger.info(
            "Executing DCI %s notification for %d partner(s)",
            event_type,
            len(partner_ids),
        )

        # Get subscription model. env.get() returns an empty recordset
        # when the model is registered, which is *falsy*, so an
        # ``if not Subscription`` check would incorrectly bail out. Test
        # membership against env explicitly instead.
        if "spp.dci.subscription" not in self.env:
            _logger.warning("DCI subscription model not available")
            return
        Subscription = self.env["spp.dci.subscription"]

        # notify_event scopes delivery per subscription: each matching
        # subscription only receives records its sender is permitted to see
        # (consent/legal-basis) and that match its filter, with the payload
        # built using that subscription's sender context. The record building
        # and filter evaluation live in the per-subscription hooks
        # (see dci_subscription_social.py), so this method only hands off the
        # affected partner ids (create/update) or the eligibility-scoped
        # identifier payloads snapshotted at unlink (delete).
        if event_type == "delete":
            # Jobs queued before eligibility snapshotting carry no payloads;
            # emit nothing rather than leaking to unscoped subscribers.
            delete_payloads = payloads if payloads is not None else []
            Subscription.notify_event(event_type, partner_ids, "SOCIAL_REGISTRY", delete_payloads=delete_payloads)
            return

        Subscription.notify_event(event_type, partner_ids, "SOCIAL_REGISTRY")
