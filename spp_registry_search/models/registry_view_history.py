# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class RegistryViewHistory(models.Model):
    """Track individual user's recently viewed registrants.

    This model stores personal viewing history per user, supporting
    the "Recently Viewed" section in the search-first interface.
    Privacy-preserving: each user only sees their own history.
    """

    _name = "spp.registry.view.history"
    _description = "Registry View History"
    _order = "view_date desc, id desc"
    _rec_name = "partner_id"

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        ondelete="cascade",
        index=True,
        default=lambda self: self.env.user,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Registrant",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('is_registrant', '=', True)]",
    )
    view_date = fields.Datetime(
        string="Last Viewed",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )
    view_count = fields.Integer(
        string="View Count",
        default=1,
    )

    _unique_user_partner = models.Constraint(
        "UNIQUE(user_id, partner_id)",
        "Each user-registrant combination must be unique",
    )

    @api.model
    def record_view(self, partner_id):
        """Record that current user viewed a registrant.

        Updates existing record or creates new one.
        Maintains max 50 recent records per user for performance.

        Args:
            partner_id: ID of the partner being viewed

        Returns:
            bool: True if recorded successfully, False otherwise
        """
        if not partner_id:
            return False

        # Check partner is a registrant
        partner = self.env["res.partner"].browse(partner_id)
        if not partner.exists() or not partner.is_registrant:
            return False

        existing = self.search(
            [
                ("user_id", "=", self.env.uid),
                ("partner_id", "=", partner_id),
            ],
            limit=1,
        )

        if existing:
            existing.write(
                {
                    "view_date": fields.Datetime.now(),
                    "view_count": existing.view_count + 1,
                }
            )
        else:
            self.create(
                {
                    "user_id": self.env.uid,
                    "partner_id": partner_id,
                }
            )
            # Cleanup old records (keep max 50 per user)
            self._cleanup_old_records()

        return True

    def _cleanup_old_records(self, max_records=50):
        """Remove oldest records beyond max_records per user."""
        to_delete = self.search(
            [
                ("user_id", "=", self.env.uid),
            ],
            order="view_date desc",
            offset=max_records,
        )
        if to_delete:
            to_delete.unlink()

    @api.model
    def get_recent_registrants(self, limit=10):
        """Get current user's recently viewed registrants.

        Returns list of dict with partner info for OWL component.
        Optimized to avoid N+1 queries by batch-loading partner data.

        Filters out registrants not in user's assigned areas (if spp_area
        module is installed and user has center_area_ids assigned).

        Args:
            limit: Maximum number of recent records to return

        Returns:
            list: List of dicts with partner info
        """
        history = self.search(
            [
                ("user_id", "=", self.env.uid),
            ],
            limit=limit * 2,  # Fetch extra to account for area filtering
        )

        if not history:
            return []

        # Batch load all partner data to avoid N+1 queries
        history_data = history.read(["partner_id", "view_date"])
        partner_ids = [h["partner_id"][0] for h in history_data]

        # Check if area filtering should be applied (spp_area module installed)
        user = self.env.user
        center_area_ids = getattr(user, "center_area_ids", None)

        if center_area_ids:
            # Filter partners by user's assigned areas
            partners = self.env["res.partner"].search_read(
                [
                    ("id", "in", partner_ids),
                    ("area_id", "child_of", center_area_ids.ids),
                ],
                ["name", "is_group", "avatar_128"],
            )
        else:
            # No area restriction - show all
            partners = self.env["res.partner"].browse(partner_ids).read(["name", "is_group", "avatar_128"])

        partner_map = {p["id"]: p for p in partners}

        # Build result, filtering out partners not in user's areas
        result = []
        for h in history_data:
            partner_id = h["partner_id"][0]
            if partner_id in partner_map:
                result.append(
                    {
                        "id": partner_id,
                        "name": partner_map[partner_id].get("name", ""),
                        "is_group": partner_map[partner_id].get("is_group", False),
                        "avatar_128": partner_map[partner_id].get("avatar_128", False),
                        "view_date": h["view_date"].isoformat() if h["view_date"] else None,
                    }
                )
                if len(result) >= limit:
                    break

        return result

    @api.model
    def clear_user_history(self):
        """Clear current user's view history."""
        self.search([("user_id", "=", self.env.uid)]).unlink()
        return True

    @api.model
    def check_registrant_edit_permission(self):
        """Check if current user can edit registrants in the UI.

        Some users have programmatic write access but should not edit via UI.
        Only specific groups can manually edit registrants in the form.

        Returns:
            bool: True if user can edit registrants in UI
        """
        edit_groups = [
            "base.group_system",
            "spp_security.group_spp_admin",
            "spp_registry.group_registry_manager",
            "spp_registry.group_registry_officer",
        ]
        for group in edit_groups:
            try:
                if self.env.user.has_group(group):
                    return True
            except ValueError:
                # Group doesn't exist (module not installed)
                continue
        return False

    @api.model
    def check_registrant_create_permission(self):
        """Check if current user can create registrants from the UI (OP#1124).

        Generic ``res.partner`` create access is too broad — base Odoo grants it
        to most internal users — so it lets unintended roles (e.g. validators)
        initiate registrant creation from Registry Search. Only the same
        privileged registry roles allowed to edit may create.

        Returns:
            bool: True if user can create registrants in the UI
        """
        create_groups = [
            "base.group_system",
            "spp_security.group_spp_admin",
            "spp_registry.group_registry_manager",
            "spp_registry.group_registry_officer",
        ]
        for group in create_groups:
            try:
                if self.env.user.has_group(group):
                    return True
            except ValueError:
                # Group doesn't exist (module not installed)
                continue
        return False

    @api.model
    def check_registrant_archive_permission(self):
        """Check if current user can archive/unarchive registrants in the UI.

        Only officers, managers, and admins can archive or unarchive registrants.
        Viewers and other read-only users should not have this capability.

        Returns:
            bool: True if user can archive/unarchive registrants
        """
        archive_groups = [
            "base.group_system",
            "spp_security.group_spp_admin",
            "spp_registry.group_registry_manager",
            "spp_registry.group_registry_officer",
        ]
        for group in archive_groups:
            try:
                if self.env.user.has_group(group):
                    return True
            except ValueError:
                # Group doesn't exist (module not installed)
                continue
        return False
