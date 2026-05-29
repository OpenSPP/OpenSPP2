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
        # Capture registrant IDs before deletion
        registrant_ids = self.filtered(lambda r: r.is_registrant).ids

        result = super().unlink()

        # Queue delete notification (IDs only since records are gone)
        if registrant_ids:
            self._schedule_dci_notification("delete", registrant_ids)

        return result

    def _schedule_dci_notification(self, event_type, partner_ids):
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
            self._queue_dci_notification_job(event_type, partner_ids)

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
        enabled = (
            self.env["ir.config_parameter"].sudo().get_param("dci.notifications_enabled", "true").lower() == "true"
        )
        return enabled

    def _queue_dci_notification_job(self, event_type, partner_ids):
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
            )._execute_dci_notification(event_type, partner_ids)

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

    def _execute_dci_notification(self, event_type, partner_ids):
        """Execute the DCI notification (called by queue_job).

        Builds notification payload and calls subscription.notify_event().

        Args:
            event_type: One of 'registration', 'update', 'delete'
            partner_ids: List of partner IDs to notify about
        """
        if not partner_ids:
            return

        _logger.info(
            "Executing DCI %s notification for %d partner(s)",
            event_type,
            len(partner_ids),
        )

        # Get subscription model
        Subscription = self.env.get("spp.dci.subscription")
        if not Subscription:
            _logger.warning("DCI subscription model not available")
            return

        # For delete events, we only have IDs (records are gone)
        if event_type == "delete":
            # Build minimal records with just identifiers
            records = [{"id": pid} for pid in partner_ids]
            Subscription.notify_event(event_type, records, "SOCIAL_REGISTRY")
            return

        # For create/update, fetch current partner data and convert to DCI format
        partners = self.env["res.partner"].browse(partner_ids).exists()
        if not partners:
            _logger.warning("No partners found for notification IDs: %s", partner_ids)
            return

        # Import search service to convert to DCI format
        try:
            from ..services.search_service import DCISocialSearchService

            search_service = DCISocialSearchService(self.env)

            records = []
            for partner in partners:
                try:
                    if partner.is_group:
                        dci_record = search_service._to_dci_group(partner)
                    else:
                        dci_record = search_service._to_dci_person(partner)
                    # Convert to dict
                    records.append(dci_record.model_dump(mode="json", by_alias=True, exclude_none=True))
                except Exception as e:
                    _logger.warning(
                        "Failed to convert partner %d to DCI format: %s",
                        partner.id,
                        str(e),
                    )

            if records:
                Subscription.notify_event(event_type, records, "SOCIAL_REGISTRY")

        except ImportError:
            _logger.error("DCISocialSearchService not available for notification conversion")
        except Exception as e:
            _logger.exception("Error executing DCI notification: %s", str(e))
