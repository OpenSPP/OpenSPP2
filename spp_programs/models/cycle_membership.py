# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class SPPCycleMembership(models.Model):
    _name = "spp.cycle.membership"
    _description = "Cycle Membership"
    _order = "partner_id asc,id desc"

    _unique_partner_cycle = models.Constraint(
        "UNIQUE(partner_id, cycle_id)",
        "Beneficiary must be unique per cycle.",
    )

    partner_id = fields.Many2one("res.partner", "Registrant", help="A beneficiary", required=True, index=True)
    cycle_id = fields.Many2one("spp.cycle", "Cycle", help="A cycle", required=True, index=True)
    enrollment_date = fields.Date(default=lambda self: fields.Datetime.now())
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("enrolled", "Enrolled"),
            ("paused", "Paused"),
            ("exited", "Exited"),
            ("not_eligible", "Not Eligible"),
            ("non_compliant", "Non-Compliant"),
        ],
        default="draft",
        copy=False,
    )

    def _compute_display_name(self):
        res = super()._compute_display_name()
        # Prefetch cycle_id and partner_id to avoid N+1 queries in loop
        self.mapped("cycle_id.name")
        self.mapped("partner_id.name")

        for rec in self:
            name = ""
            if rec.cycle_id:
                name += "[" + rec.cycle_id.name + "] "
            if rec.partner_id:
                name += rec.partner_id.name
            rec.display_name = name
        return res

    def open_cycle_membership_form(self):
        return {
            "name": "Cycle Membership",
            "view_mode": "form",
            "res_model": "spp.cycle.membership",
            "res_id": self.id,
            "view_id": self.env.ref("spp_programs.view_cycle_membership_form").id,
            "type": "ir.actions.act_window",
            "target": "new",
        }

    def open_registrant_form(self):
        if self.partner_id.is_group:
            return {
                "name": "Group Member",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.partner_id.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
                "context": {
                    "default_is_group": True,
                    "create": False,
                    "edit": False,
                },
            }
        else:
            return {
                "name": "Individual Member",
                "view_mode": "form",
                "res_model": "res.partner",
                "res_id": self.partner_id.id,
                "view_id": self.env.ref("spp_registry.view_individuals_form").id,
                "type": "ir.actions.act_window",
                "target": "new",
                "context": {
                    "default_is_group": False,
                    "create": False,
                    "edit": False,
                },
            }

    @api.model
    def bulk_create_memberships(self, vals_list, chunk_size=1000, skip_duplicates=False):
        """Create cycle memberships in bulk with optional duplicate skipping.

        :param vals_list: List of dicts with membership values
        :param chunk_size: Number of records per batch (default 1000)
        :param skip_duplicates: When True, use INSERT ... ON CONFLICT DO NOTHING
            to silently skip duplicate (partner_id, cycle_id) pairs.
            Returns the count of inserted rows.
        :return: Recordset (skip_duplicates=False) or int count (skip_duplicates=True)
        """
        if not vals_list:
            return 0 if skip_duplicates else self.env["spp.cycle.membership"]

        if skip_duplicates:
            return self._bulk_insert_on_conflict(vals_list, chunk_size)

        return self.create(vals_list)

    def _bulk_insert_on_conflict(self, vals_list, chunk_size=1000):
        """Insert cycle memberships using raw SQL with ON CONFLICT DO NOTHING.

        :param vals_list: List of dicts with at least partner_id, cycle_id, state
        :param chunk_size: Number of records per SQL INSERT batch
        :return: Total number of rows actually inserted
        """
        cr = self.env.cr
        uid = self.env.uid
        total_inserted = 0

        for i in range(0, len(vals_list), chunk_size):
            batch = vals_list[i : i + chunk_size]
            values = []
            params = []
            for v in batch:
                values.append("(%s, %s, %s, %s, %s, %s, now(), now())")
                params.extend(
                    [
                        v["partner_id"],
                        v["cycle_id"],
                        v.get("state", "draft"),
                        v.get("enrollment_date", fields.Date.today()),
                        uid,
                        uid,
                    ]
                )

            sql = """
                INSERT INTO spp_cycle_membership
                    (partner_id, cycle_id, state, enrollment_date,
                     create_uid, write_uid, create_date, write_date)
                VALUES {}
                ON CONFLICT (partner_id, cycle_id) DO NOTHING
            """.format(  # noqa: S608  # nosec B608
                ", ".join(values)
            )
            cr.execute(sql, params)
            total_inserted += cr.rowcount

        _logger.info(
            "Bulk inserted %d cycle memberships (%d skipped as duplicates)",
            total_inserted,
            len(vals_list) - total_inserted,
        )
        return total_inserted

    def unlink(self):
        if not self:
            return
        draft_records = self.filtered(lambda x: x.cycle_id.state == "draft")
        if not draft_records:
            raise ValidationError(
                _("Beneficiaries can only be deleted when both the cycle and entitlement are unapproved.")
            )

        # Prefetch partner_id and cycle_id.entitlement_ids to avoid N+1 queries in loop
        draft_records.mapped("partner_id")
        draft_records.mapped("cycle_id.entitlement_ids.partner_id")
        draft_records.mapped("cycle_id.entitlement_ids.state")

        for record in draft_records:
            partner_id = record.partner_id.id
            entitlement = record.cycle_id.entitlement_ids.filtered(lambda x, pid=partner_id: x.partner_id.id == pid)

            if entitlement:
                if entitlement.state == "approved":
                    raise ValidationError(
                        _("Beneficiaries can only be deleted when both the cycle andentitlement are unapproved.")
                    )
                entitlement.unlink()

        return super().unlink()
