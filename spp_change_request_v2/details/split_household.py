import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ROLE_NAMESPACE = "urn:openspp:vocab:group-membership-type"
HEAD_ROLE_CODE = "head"


class SPPCRDetailSplitHousehold(models.Model):
    """Detail model for Split Household CR type (OP#877).

    Splits members out of a source household into a brand-new household. The new
    household captures the same group fields as Create Group (OP#876). Moving a
    member is a relational update only: each move line picks an existing source
    member and their role in the new household - the member's own data is not
    edited here. At most one moved member may be Head, and a head is not mandatory.
    """

    _name = "spp.cr.detail.split_household"
    _description = "CR Detail: Split Household"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    # ──────────────────────────────────────────────────────────────────────
    # Source household (prefilled from the registrant) + reason
    # ──────────────────────────────────────────────────────────────────────
    source_group_id = fields.Many2one(
        "res.partner",
        string="Source Household",
        related="change_request_id.registrant_id",
        store=True,
        readonly=True,
    )
    source_group_name = fields.Char(related="source_group_id.name", readonly=True)
    split_reason = fields.Selection(
        [
            ("marriage", "Marriage"),
            ("separation", "Separation/Divorce"),
            ("independence", "Member Independence"),
            ("relocation", "Relocation"),
            ("correction", "Data Correction"),
            ("other", "Other"),
        ],
        string="Reason for Split",
        tracking=True,
    )
    remarks = fields.Text(string="Remarks", tracking=True)

    # Source members that may be moved (active, non-head). Used by the move-line
    # member picker's domain via parent reference in the view.
    available_member_ids = fields.Many2many(
        "res.partner",
        string="Available Members",
        compute="_compute_available_member_ids",
        help="Active members of the source household, excluding the head (who cannot be moved).",
    )

    # ──────────────────────────────────────────────────────────────────────
    # Members to move (table with per-member role + edit modal)
    # ──────────────────────────────────────────────────────────────────────
    member_line_ids = fields.One2many(
        "spp.cr.detail.split_household.member",
        "detail_id",
        string="Members to Move",
    )

    # ──────────────────────────────────────────────────────────────────────
    # New household — same group fields as Create Group (OP#876)
    # ──────────────────────────────────────────────────────────────────────
    new_group_name = fields.Char(string="New Household Name", tracking=True)
    new_group_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Group Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-type')]",
        tracking=True,
        help="Leave empty to use the same type as the source household.",
    )
    new_area_id = fields.Many2one("spp.area", string="Area", tracking=True)
    new_address = fields.Text(string="Address", tracking=True)
    new_email = fields.Char(string="Email", tracking=True)
    # New household location (OP#877). Latitude/Longitude are the editable
    # source of truth (mirrors Create Group and drives the dispatch/location
    # string in the strategy); new_coordinates is a GeoPoint kept in sync so the
    # location can be viewed/picked on the map below the fields.
    new_latitude = fields.Float(string="Latitude", digits=(13, 10), tracking=True)
    new_longitude = fields.Float(string="Longitude", digits=(13, 10), tracking=True)
    new_coordinates = fields.GeoPointField(string="Map Location")
    new_phone_line_ids = fields.One2many(
        "spp.cr.detail.create_group.phone", "split_household_detail_id", string="Phone Numbers"
    )
    new_bank_line_ids = fields.One2many(
        "spp.cr.detail.create_group.bank", "split_household_detail_id", string="Bank Accounts"
    )
    new_id_doc_line_ids = fields.One2many(
        "spp.cr.detail.create_group.id_doc", "split_household_detail_id", string="Identity Documents"
    )

    created_group_id = fields.Many2one("res.partner", string="Created Household", readonly=True)

    # ──────────────────────────────────────────────────────────────────────
    # Stat counters
    # ──────────────────────────────────────────────────────────────────────
    members_to_split_count = fields.Integer(compute="_compute_members_count", string="Moving")
    remaining_members_count = fields.Integer(compute="_compute_members_count", string="Remaining")

    # ──────────────────────────────────────────────────────────────────────
    # Computes / constraints
    # ──────────────────────────────────────────────────────────────────────
    @api.onchange("new_latitude", "new_longitude")
    def _onchange_new_latlon(self):
        """Reflect typed Latitude/Longitude onto the map pin (OP#877).

        Guard the WGS84 ranges: an out-of-range value must never reach the map
        widget, otherwise MapLibre throws "Invalid LngLat ...". When invalid, the
        pin is cleared and the user is warned to correct the value (the typed
        value is left in place so they can fix it).
        """
        for rec in self:
            lat, lon = rec.new_latitude, rec.new_longitude
            if not lat and not lon:
                rec.new_coordinates = False
                continue
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                rec.new_coordinates = False
                return {
                    "warning": {
                        "title": _("Invalid coordinates"),
                        "message": _("Latitude must be between -90 and 90 and Longitude between -180 and 180."),
                    }
                }
            rec.new_coordinates = json.dumps({"type": "Point", "coordinates": [lon, lat]})

    @api.constrains("new_latitude", "new_longitude")
    def _check_coordinates_range(self):
        """Reject coordinates outside the valid WGS84 ranges (OP#877)."""
        for rec in self:
            if rec.new_latitude and not (-90 <= rec.new_latitude <= 90):
                raise ValidationError(_("Latitude must be between -90 and 90."))
            if rec.new_longitude and not (-180 <= rec.new_longitude <= 180):
                raise ValidationError(_("Longitude must be between -180 and 180."))

    @api.onchange("new_coordinates")
    def _onchange_new_coordinates(self):
        """Reflect a pin dropped on the map back onto Latitude/Longitude (OP#877)."""
        for rec in self:
            geom = rec.new_coordinates
            if geom and not geom.is_empty:
                # GeoPoint stores (x=longitude, y=latitude); only write when the
                # value actually differs so the two onchanges don't ping-pong.
                if rec.new_longitude != geom.x:
                    rec.new_longitude = geom.x
                if rec.new_latitude != geom.y:
                    rec.new_latitude = geom.y

    @api.depends("source_group_id")
    def _compute_available_member_ids(self):
        head = self.env["spp.vocabulary.code"].get_code(ROLE_NAMESPACE, HEAD_ROLE_CODE)
        for rec in self:
            individuals = self.env["res.partner"]
            if rec.source_group_id and rec.source_group_id.is_group:
                memberships = self.env["spp.group.membership"].search(
                    [("group", "=", rec.source_group_id.id), ("status", "=", "active")]
                )
                non_head = memberships.filtered(lambda m, h=head: not h or h not in m.membership_type_ids)
                individuals = non_head.mapped("individual")
            rec.available_member_ids = individuals

    @api.depends("member_line_ids", "source_group_id")
    def _compute_members_count(self):
        for rec in self:
            rec.members_to_split_count = len(rec.member_line_ids)
            total = 0
            if rec.source_group_id:
                total = self.env["spp.group.membership"].search_count(
                    [("group", "=", rec.source_group_id.id), ("status", "=", "active")]
                )
            rec.remaining_members_count = total - rec.members_to_split_count

    @api.constrains("member_line_ids", "source_group_id")
    def _check_minimum_remaining(self):
        """At least one member must remain in the source household."""
        for rec in self:
            if rec.source_group_id and rec.member_line_ids:
                total = self.env["spp.group.membership"].search_count(
                    [("group", "=", rec.source_group_id.id), ("status", "=", "active")]
                )
                if len(rec.member_line_ids) >= total:
                    raise ValidationError(
                        "Cannot move all members. At least one member must remain in the source household."
                    )

    @api.constrains("member_line_ids")
    def _check_single_head(self):
        """At most one moved member may be designated Head of the new household."""
        head = self.env["spp.vocabulary.code"].get_code(ROLE_NAMESPACE, HEAD_ROLE_CODE)
        if not head:
            return
        for rec in self:
            heads = rec.member_line_ids.filtered(lambda line, h=head: line.membership_type_id == h)
            if len(heads) > 1:
                raise ValidationError("Only one member can be moved as Head of the new household.")

    @api.constrains("member_line_ids")
    def _check_no_duplicate_members(self):
        """The same member cannot be moved more than once."""
        for rec in self:
            ids = [line.individual_id.id for line in rec.member_line_ids if line.individual_id]
            if len(ids) != len(set(ids)):
                raise ValidationError("Each member can only be added once to the members to move.")


class SPPCRDetailSplitHouseholdMember(models.Model):
    """A member moved to the new household (OP#877).

    Moving is a pure relational update: the line references an existing source
    member and the role they take in the new household. The member's own
    attributes are not edited here.
    """

    _name = "spp.cr.detail.split_household.member"
    _description = "CR Detail: Split Household - Member to Move"

    detail_id = fields.Many2one("spp.cr.detail.split_household", required=True, ondelete="cascade")
    individual_id = fields.Many2one("res.partner", string="Member", required=True)
    membership_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Role",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:group-membership-type')]",
    )
