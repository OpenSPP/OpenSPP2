# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Individual fields that invalidate the sibling ranking when changed
BIRTH_ORDER_TRIGGER_FIELDS = {"birthdate", "citizen_by", "birth_sequence"}
# Membership fields that change the composition of a family
MEMBERSHIP_TRIGGER_FIELDS = {"group", "individual", "membership_type_ids", "is_ended", "ended_date", "active"}

GROUP_TYPE_NS = "urn:openspp:vocab:group-type"
MEMBERSHIP_TYPE_NS = "urn:openspp:vocab:group-membership-type"


class ResPartnerBirthOrder(models.Model):
    _inherit = "res.partner"

    citizen_by = fields.Selection(
        selection=[
            ("descent", "Descent"),
            ("adopted", "Adopted"),
            ("naturalization", "Naturalization"),
            ("other", "Other"),
        ],
        string="Citizenship By",
        default="descent",
        tracking=True,
        help="How citizenship was acquired, as recorded by the civil registry. "
        "Only children with citizenship by descent are counted in the birth order.",
    )
    birth_sequence = fields.Integer(
        string="Birth Sequence",
        default=0,
        tracking=True,
        help="Position within a multiple-birth event (1 = first born of the event). "
        "0 when not part of a multiple birth or not yet determined.",
    )
    birth_order = fields.Integer(
        string="Birth Order",
        default=0,
        readonly=True,
        index=True,
        tracking=True,
        help="Rank of this child within the mother's sibling sequence. 0 = not determined.",
    )
    birth_order_state = fields.Selection(
        selection=[
            ("none", "Not Applicable"),
            ("computed", "Computed"),
            ("pending_determination", "Pending Determination"),
        ],
        string="Birth Order Status",
        default="none",
        readonly=True,
        tracking=True,
        help="Pending Determination: part of a multiple-birth event whose internal "
        "sequence is not recorded; an authorized officer must record the birth sequence.",
    )

    def write(self, vals):
        res = super().write(vals)
        if BIRTH_ORDER_TRIGGER_FIELDS & set(vals):
            self._recompute_birth_order_families(self._birth_order_family_groups())
        return res

    def _birth_order_family_groups(self):
        """Family groups the individuals in `self` belong to."""
        memberships = self.env["spp.group.membership"].search(
            [
                ("individual", "in", self.ids),
                ("is_ended", "=", False),
            ]
        )
        return memberships.mapped("group").filtered(
            lambda g: g.group_type_id.code == "family" and g.group_type_id.namespace_uri == GROUP_TYPE_NS
        )

    @api.model
    def _recompute_birth_order_families(self, families):
        """Recompute the sibling ranking for each family group.

        Ranking rules:
        - only children with citizenship by descent (or unset) are counted;
        - children are ordered by date of birth, then by birth sequence within
          a multiple-birth event;
        - children of a multiple-birth event with no usable birth sequence are
          not ranked automatically and are flagged for determination — later
          siblings still rank correctly because the event size is known.
        """
        child_code = self.env.ref("spp_child_benefit.code_membership_type_child")
        for family in families:
            memberships = family.group_membership_ids.filtered(
                lambda m: not m.is_ended and m.active and child_code.id in m.membership_type_ids.ids
            )
            children = memberships.mapped("individual")
            unranked_vals = {"birth_order": 0, "birth_order_state": "none"}

            countable = children.filtered(lambda c: c.birthdate and (not c.citizen_by or c.citizen_by == "descent"))
            for child in children - countable:
                child._write_birth_order(unranked_vals)

            # Group countable children by date of birth, ascending
            by_date = {}
            for child in countable:
                by_date.setdefault(child.birthdate, []).append(child)

            rank_base = 0
            for birthdate in sorted(by_date):
                event = by_date[birthdate]
                if len(event) == 1:
                    event[0]._write_birth_order({"birth_order": rank_base + 1, "birth_order_state": "computed"})
                else:
                    sequences = [c.birth_sequence for c in event]
                    usable = all(s > 0 for s in sequences) and len(set(sequences)) == len(sequences)
                    if usable:
                        for offset, child in enumerate(sorted(event, key=lambda c: c.birth_sequence)):
                            child._write_birth_order(
                                {"birth_order": rank_base + offset + 1, "birth_order_state": "computed"}
                            )
                    else:
                        for child in event:
                            child._write_birth_order({"birth_order": 0, "birth_order_state": "pending_determination"})
                rank_base += len(event)

    def _write_birth_order(self, vals):
        """Write ranking results only when they changed, to keep chatter clean."""
        current = {"birth_order": self.birth_order, "birth_order_state": self.birth_order_state}
        if current != vals:
            super().write(vals)


class GroupMembershipBirthOrder(models.Model):
    _inherit = "spp.group.membership"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env["res.partner"]._recompute_birth_order_families(
            records.mapped("individual")._birth_order_family_groups()
        )
        return records

    def write(self, vals):
        groups_before = self.mapped("group")
        res = super().write(vals)
        if MEMBERSHIP_TRIGGER_FIELDS & set(vals):
            families = (groups_before | self.mapped("group")).filtered(
                lambda g: g.group_type_id.code == "family" and g.group_type_id.namespace_uri == GROUP_TYPE_NS
            )
            self.env["res.partner"]._recompute_birth_order_families(families)
        return res

    def unlink(self):
        families = self.mapped("individual")._birth_order_family_groups()
        res = super().unlink()
        self.env["res.partner"]._recompute_birth_order_families(families)
        return res
