# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import _, api, models
from odoo.exceptions import AccessError


class ResPartner(models.Model):
    """Extend res.partner to track view history and control archive access for registrants."""

    _inherit = "res.partner"

    @api.model
    def get_formview_action(self, access_uid=None):
        """Override to record view history when opening registrant form.

        This ensures that whenever a registrant form is opened,
        it gets recorded in the user's view history.
        """
        action = super().get_formview_action(access_uid=access_uid)

        # Record view for registrants
        if self.is_registrant:
            self.env["spp.registry.view.history"].sudo().record_view(self.id)  # nosemgrep: odoo-sudo-without-context

        return action

    def _check_archive_permission(self):
        """Check if current user can archive/unarchive registrants.

        Only officers, managers, and admins can archive or unarchive registrants.
        Viewers and other read-only users should not have this capability.
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

    def action_archive(self):
        """Override to restrict archive action to authorized groups."""
        # Only check for registrants
        registrants = self.filtered(lambda p: p.is_registrant)
        if registrants and not self._check_archive_permission():
            raise AccessError(_("You do not have the necessary permissions to archive registrants."))
        return super().action_archive()

    def action_unarchive(self):
        """Override to restrict unarchive action to authorized groups."""
        # Only check for registrants
        registrants = self.filtered(lambda p: p.is_registrant)
        if registrants and not self._check_archive_permission():
            raise AccessError(_("You do not have the necessary permissions to unarchive registrants."))
        return super().action_unarchive()

    @api.model
    def get_search_config(self):
        """Return registry search configuration for the JS portal."""
        get_param = self.env["ir.config_parameter"].sudo().get_param  # nosemgrep: odoo-sudo-without-context
        result_limit = int(get_param("spp_registry_search.result_limit", "50"))
        min_chars = int(get_param("spp_registry_search.min_chars", "3"))
        return {
            "search_mode": get_param("spp_registry_search.search_mode", "unified"),
            "target_field": get_param("spp_registry_search.target_field", "name"),
            "result_limit": max(10, min(200, result_limit)),
            "min_chars": max(1, min(10, min_chars)),
        }

    @api.model
    def search_registrants(self, search_term, search_type="all", search_field=None, advanced_filters=None, limit=50):
        """Optimized registrant search that respects configured search mode.

        Instead of a single ORM domain with OR across JOINs, runs separate
        targeted queries per field and merges results. Each individual query
        can use indexes efficiently.

        Args:
            search_term: The search string
            search_type: 'all', 'individuals', or 'groups'
            search_field: If targeted mode, which field to search ('name', 'id_number', 'phone', 'email')
            advanced_filters: Dict with optional date range filters
            limit: Maximum results to return

        Returns:
            list: List of dicts with partner data
        """
        if not search_term:
            return []

        # Read config with fallback defaults
        get_param = self.env["ir.config_parameter"].sudo().get_param  # nosemgrep: odoo-sudo-without-context
        config_limit = int(get_param("spp_registry_search.result_limit", "50"))
        limit = max(10, min(200, limit or config_limit))

        search_mode = get_param("spp_registry_search.search_mode", "unified")

        # If targeted mode and a field is specified, only search that field
        if search_mode == "targeted" and search_field:
            partner_ids = self._search_by_field(search_term, search_field, limit)
        else:
            # Unified mode: run separate queries per field and merge
            partner_ids = self._search_unified(search_term, limit)

        if not partner_ids:
            return []

        # Build final domain with type and advanced filters
        domain = [("id", "in", list(partner_ids)), ("is_registrant", "=", True)]

        if search_type == "individuals":
            domain.append(("is_group", "=", False))
        elif search_type == "groups":
            domain.append(("is_group", "=", True))

        if advanced_filters:
            if advanced_filters.get("registrationDateFrom"):
                domain.append(("registration_date", ">=", advanced_filters["registrationDateFrom"]))
            if advanced_filters.get("registrationDateTo"):
                domain.append(("registration_date", "<=", advanced_filters["registrationDateTo"]))

        fields_to_read = ["name", "is_group", "phone", "email", "registration_date", "disabled"]
        return self.search_read(domain, fields_to_read, limit=limit, order="id desc")

    def _search_unified(self, search_term, limit):
        """Run separate indexed queries per field and merge results."""
        partner_ids = set()

        # Query 1: Name match (uses trigram index)
        name_matches = self.search(
            [("is_registrant", "=", True), ("name", "ilike", search_term)],
            limit=limit,
        )
        partner_ids.update(name_matches.ids)

        # Query 2: ID number exact match (uses B-tree index)
        reg_ids = self.env["spp.registry.id"].search(
            [("value", "=", search_term)],
            limit=limit,
        )
        partner_ids.update(reg_ids.mapped("partner_id").ids)

        # Query 3: Phone number match (uses trigram index)
        phones = self.env["spp.phone.number"].search(
            [("phone_no", "ilike", search_term)],
            limit=limit,
        )
        partner_ids.update(phones.mapped("partner_id").ids)

        # Query 4: Email match (uses trigram index)
        email_matches = self.search(
            [("is_registrant", "=", True), ("email", "ilike", search_term)],
            limit=limit,
        )
        partner_ids.update(email_matches.ids)

        return partner_ids

    def _search_by_field(self, search_term, search_field, limit):
        """Search a single field (targeted mode)."""
        if search_field == "name":
            return set(
                self.search(
                    [("is_registrant", "=", True), ("name", "ilike", search_term)],
                    limit=limit,
                ).ids
            )
        elif search_field == "id_number":
            reg_ids = self.env["spp.registry.id"].search(
                [("value", "=", search_term)],
                limit=limit,
            )
            return set(reg_ids.mapped("partner_id").ids)
        elif search_field == "phone":
            phones = self.env["spp.phone.number"].search(
                [("phone_no", "ilike", search_term)],
                limit=limit,
            )
            return set(phones.mapped("partner_id").ids)
        elif search_field == "email":
            return set(
                self.search(
                    [("is_registrant", "=", True), ("email", "ilike", search_term)],
                    limit=limit,
                ).ids
            )
        return set()
