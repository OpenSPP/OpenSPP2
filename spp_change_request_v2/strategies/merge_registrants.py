import logging

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SPPCRApplyMergeRegistrants(models.AbstractModel):
    """Custom apply strategy for Merge Registrants CR type."""

    _name = "spp.cr.apply.merge_registrants"
    _inherit = "spp.cr.strategy.base"
    _description = "CR Apply: Merge Registrants"

    def apply(self, change_request):
        """Merge duplicate registrants into the primary."""
        primary = change_request.registrant_id
        if not primary:
            raise UserError(_("No primary registrant found."))

        detail = change_request.get_detail()
        if not detail:
            raise UserError(_("No detail record found."))

        if not detail.duplicate_registrant_ids:
            raise UserError(_("No duplicate registrants selected."))

        duplicates = detail.duplicate_registrant_ids
        is_group = primary.is_group

        # Merge memberships if requested
        if detail.is_merge_memberships:
            self._merge_memberships(primary, duplicates, is_group)

        # Merge IDs if requested
        if detail.is_merge_ids:
            self._merge_ids(primary, duplicates)

        # Deactivate duplicates if requested
        if detail.is_deactivate_duplicates:
            duplicates.write({"disabled": fields.Date.today()})
            _logger.info(
                "Deactivated %d duplicate registrants",
                len(duplicates),
            )

        _logger.info(
            "Merged %d duplicates into primary partner_id=%s via CR %s",
            len(duplicates),
            primary.id,
            change_request.name,
        )

        return True

    def _merge_memberships(self, primary, duplicates, is_group):
        """Transfer memberships from duplicates to primary."""
        if is_group:
            # Get head membership type to check for head members
            head_type = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")

            # For groups: transfer members from duplicate groups
            for dup in duplicates:
                memberships = self.env["spp.group.membership"].search(
                    [
                        ("group", "=", dup.id),
                        ("status", "=", "active"),
                    ]
                )
                for membership in memberships:
                    # Check if this is a head member from duplicate group
                    is_head_from_duplicate = head_type and head_type in membership.membership_type_ids

                    # Check if individual already in primary group
                    existing = self.env["spp.group.membership"].search(
                        [
                            ("group", "=", primary.id),
                            ("individual", "=", membership.individual.id),
                            ("status", "=", "active"),
                        ],
                        limit=1,
                    )
                    if not existing:
                        # Transfer membership, but remove head role if from duplicate
                        if is_head_from_duplicate:
                            # Remove head membership type when transferring
                            new_types = membership.membership_type_ids.filtered(lambda t: t != head_type)
                            membership.write({"group": primary.id, "membership_type_ids": [Command.set(new_types.ids)]})
                            _logger.info(
                                "Transferred membership_id=%s from group %s to group %s (removed head role)",
                                membership.id,
                                dup.id,
                                primary.id,
                            )
                        else:
                            # Transfer membership as is
                            membership.write({"group": primary.id})
                            _logger.info(
                                "Transferred membership_id=%s from group %s to group %s",
                                membership.id,
                                dup.id,
                                primary.id,
                            )
                    else:
                        # End duplicate membership
                        membership.write({"ended_date": fields.Datetime.now()})
        else:
            # For individuals: transfer group memberships
            for dup in duplicates:
                memberships = self.env["spp.group.membership"].search(
                    [
                        ("individual", "=", dup.id),
                        ("status", "=", "active"),
                    ]
                )
                for membership in memberships:
                    # Check if primary already in this group
                    existing = self.env["spp.group.membership"].search(
                        [
                            ("group", "=", membership.group.id),
                            ("individual", "=", primary.id),
                            ("status", "=", "active"),
                        ],
                        limit=1,
                    )
                    if not existing:
                        # Transfer membership
                        membership.write({"individual": primary.id})
                        _logger.info(
                            "Transferred membership_id=%s from individual %s to individual %s",
                            membership.id,
                            dup.id,
                            primary.id,
                        )
                    else:
                        # End duplicate membership
                        membership.write({"ended_date": fields.Datetime.now()})

    def _merge_ids(self, primary, duplicates):
        """Transfer IDs from duplicates to primary."""
        for dup in duplicates:
            ids_to_transfer = self.env["spp.registry.id"].search(
                [
                    ("partner_id", "=", dup.id),
                ]
            )
            for id_rec in ids_to_transfer:
                # Check if primary already has this ID type
                existing = self.env["spp.registry.id"].search(
                    [
                        ("partner_id", "=", primary.id),
                        ("id_type_id", "=", id_rec.id_type_id.id),
                    ],
                    limit=1,
                )
                if not existing:
                    # Transfer ID
                    id_rec.write({"partner_id": primary.id})
                    _logger.info(
                        "Transferred ID record_id=%s from partner %s to partner %s",
                        id_rec.id,
                        dup.id,
                        primary.id,
                    )
                else:
                    # Mark as invalid
                    id_rec.write({"status": "invalid"})

    def preview(self, change_request):
        """Preview what will be changed."""
        detail = change_request.get_detail()
        if not detail:
            return {}

        return {
            "_action": "merge_registrants",
            "primary": change_request.registrant_id.name,
            "duplicates": [d.name for d in detail.duplicate_registrant_ids],
            "duplicate_count": detail.duplicate_count,
            "merge_memberships": detail.is_merge_memberships,
            "merge_ids": detail.is_merge_ids,
            "deactivate_duplicates": detail.is_deactivate_duplicates,
            "reason": detail.reason,
        }
