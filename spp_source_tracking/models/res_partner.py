# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Extend res.partner with source tracking and merge capabilities."""

    _name = "res.partner"
    _inherit = ["res.partner", "spp.mixin.source.tracking"]

    merged_into_id = fields.Many2one(
        "res.partner",
        string="Merged Into",
        readonly=True,
        copy=False,
        index=True,
        help="If set, this record was merged into another and is inactive",
    )
    merge_provenance_ids = fields.One2many(
        "spp.merge.provenance",
        "survivor_id",
        string="Merge History",
    )
    merge_count = fields.Integer(
        compute="_compute_merge_count",
        store=True,
        string="Merged Records",
    )

    @api.constrains("merged_into_id")
    def _check_not_self_merge(self):
        """Ensure a partner cannot be merged into itself."""
        for rec in self:
            if rec.merged_into_id and rec.id == rec.merged_into_id.id:
                raise UserError(_("A partner cannot be merged into itself"))

    @api.depends("merge_provenance_ids")
    def _compute_merge_count(self):
        for rec in self:
            rec.merge_count = len(rec.merge_provenance_ids)

    def _check_merge_access(self):
        """Check if current user has permission to perform merge operations.

        Raises:
            AccessError: If user lacks merge permissions
        """
        # Allow system admin and SPP admin/manager
        if self.env.user._is_admin():
            return
        if self.env.user.has_group("spp_security.group_spp_admin"):
            return
        # Check for registry manager if the group exists
        try:
            if self.env.user.has_group("spp_registry.group_registry_manager"):
                return
        except ValueError:
            pass  # Group doesn't exist

        raise AccessError(
            _(
                "You do not have permission to merge registrants. "
                "This operation requires Manager or Administrator access."
            )
        )

    def merge_into(self, target, reason=None):
        """Merge self into target partner.

        This method:
        1. Creates a merge provenance record with data snapshot
        2. Transfers identifiers (reg_ids) to target
        3. Transfers relationships to target
        4. Transfers program memberships (handling duplicates)
        5. Archives the merged record with a redirect pointer

        Args:
            target: Partner record to merge into (survivor)
            reason: Optional explanation for the merge

        Returns:
            The target (surviving) partner record

        Raises:
            AccessError: If user lacks permission to merge
            UserError: If merge is not possible (same record, inactive, already merged)
        """
        self.ensure_one()
        target.ensure_one()

        # Check permissions first
        self._check_merge_access()

        # Validate merge is possible
        if self == target:
            raise UserError(_("Cannot merge a record into itself"))
        if not self.active:
            raise UserError(_("Cannot merge an inactive record"))
        if self.merged_into_id:
            raise UserError(_("This record was already merged"))
        if target.merged_into_id:
            raise UserError(_("Cannot merge into a record that has already been merged into another record"))

        # Log without PII - only IDs
        _logger.info(
            "Merging partner_id=%s into partner_id=%s by user_id=%s",
            self.id,
            target.id,
            self.env.user.id,
        )

        # 1. Record merge provenance with snapshot
        self.env["spp.merge.provenance"].create(
            {
                "survivor_id": target.id,
                "merged_id": self.id,
                "merge_reason": reason,
                "merged_source_system": self.source_system,
                "merged_source_reference": self.source_reference,
                "merged_collection_method": self.collection_method,
                "merged_collection_date": self.collection_date,
                "merged_data_snapshot": self._get_merge_snapshot(),
            }
        )

        # 2. Move identifiers to target
        if hasattr(self, "reg_ids") and self.reg_ids:
            self.reg_ids.write({"partner_id": target.id})

        # 3. Move relationships to target
        self._transfer_relationships(target)

        # 4. Handle program memberships
        self._transfer_memberships(target)

        # 5. Archive merged record with redirect
        self.with_context(skip_source_tracking=True).write(
            {
                "active": False,
                "merged_into_id": target.id,
            }
        )

        # 6. Update target's last_update
        target.with_context(skip_source_tracking=True).write(
            {
                "last_update_system": "merge",
                "last_update_reference": f"merged-from-{self.id}",
            }
        )

        _logger.info(
            "Successfully merged partner_id=%s into partner_id=%s",
            self.id,
            target.id,
        )

        return target

    def _get_merge_snapshot(self):
        """Capture key fields for audit trail.

        Returns a dictionary containing important fields that should be
        preserved for audit purposes when a record is merged.
        """
        self.ensure_one()
        snapshot = {
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
        }

        # Include birthdate if available
        if hasattr(self, "birthdate") and self.birthdate:
            snapshot["birthdate"] = str(self.birthdate)

        # Include identifiers if available
        if hasattr(self, "reg_ids"):
            snapshot["identifiers"] = [{"type": r.id_type_id.display, "value": r.value} for r in self.reg_ids]

        return snapshot

    def _transfer_relationships(self, target):
        """Move relationships from self to target.

        Updates both source and destination relationships to point to
        the target partner.
        """
        Relationship = self.env.get("spp.registry.relationship")
        if not Relationship:
            return

        # Update source relationships
        source_rels = Relationship.search([("source", "=", self.id)])
        if source_rels:
            source_rels.write({"source": target.id})

        # Update destination relationships
        dest_rels = Relationship.search([("destination", "=", self.id)])
        if dest_rels:
            dest_rels.write({"destination": target.id})

    def _transfer_memberships(self, target):
        """Move program memberships, handling duplicates.

        If the target is already enrolled in a program, the duplicate
        membership is archived. Otherwise, the membership is transferred.
        """
        if not hasattr(self, "program_membership_ids"):
            return

        # Pre-build set of target program IDs for O(n+m) instead of O(n*m)
        target_program_ids = set(target.program_membership_ids.mapped("program_id").ids)

        for membership in self.program_membership_ids:
            if membership.program_id.id in target_program_ids:
                # Already enrolled in same program - archive duplicate
                membership.with_context(skip_source_tracking=True).write({"active": False})
            else:
                # Move membership to target
                membership.write({"partner_id": target.id})

    @api.model
    def resolve_partner(self, partner_id):
        """Follow merge chain to find current active partner.

        When records are merged, the merged record points to the survivor.
        This method follows the chain to find the final active record.

        Args:
            partner_id: ID of the partner to resolve

        Returns:
            The current active partner record (may be the same if not merged)
        """
        partner = self.browse(partner_id)
        visited = set()

        while partner.merged_into_id and partner.id not in visited:
            visited.add(partner.id)
            partner = partner.merged_into_id

        # Warn if final partner is inactive (corrupted chain)
        if not partner.active:
            _logger.warning(
                "resolve_partner found inactive partner_id=%s at end of merge chain starting from partner_id=%s",
                partner.id,
                partner_id,
            )

        return partner
