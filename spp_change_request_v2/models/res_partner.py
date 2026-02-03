# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Extend res.partner for better registrant display in CR wizard."""

from odoo import api, models


class ResPartner(models.Model):
    """Extend res.partner to show more info when searching for registrants."""

    _inherit = "res.partner"

    def _compute_display_name(self):
        """Add registrant ID to display name when in CR wizard context."""
        super()._compute_display_name()

        # Only modify display for registrants when specific context is set
        if not self.env.context.get("show_registrant_id"):
            return

        for partner in self:
            if not partner.is_registrant:
                continue

            # Build enhanced display name with ID
            name_parts = [partner.name or "Unknown"]

            # Add primary ID if available
            if hasattr(partner, "reg_ids") and partner.reg_ids:
                first_id = partner.reg_ids[0]
                if first_id.value:
                    name_parts.append(f"({first_id.value})")

            # Add member count for groups
            if partner.is_group and hasattr(partner, "group_membership_ids"):
                member_count = len(partner.group_membership_ids)
                name_parts.append(f"- {member_count} members")

            # Add location hint if available
            if partner.city:
                name_parts.append(f"- {partner.city}")
            elif partner.street:
                # Truncate street if too long
                street = partner.street[:20] + "..." if len(partner.street) > 20 else partner.street
                name_parts.append(f"- {street}")

            partner.display_name = " ".join(name_parts)

    @api.model
    def _name_search(self, name, domain=None, operator="ilike", limit=100, order=None):
        """Also search by registrant ID value when in CR wizard context."""
        domain = domain or []

        # If searching for registrants, also search by reg_ids.value
        if self.env.context.get("show_registrant_id") and name and operator in ("ilike", "like", "="):
            # Add search by reg_ids.value
            # This is done via a subquery approach
            reg_id_domain = [("reg_ids.value", operator, name)]
            domain = ["&"] + domain + ["|", ("name", operator, name)] + reg_id_domain

            return self._search(domain, limit=limit, order=order)

        return super()._name_search(name, domain=domain, operator=operator, limit=limit, order=order)
