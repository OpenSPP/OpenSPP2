# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Farm Model Extension - V2 with Vocabulary Integration.

Extends res.partner (registrant groups) with farm-specific fields.
A farm IS a res.partner, just like a company is a res.partner.

Uses _inherits delegation to spp.farm.details so that farm classification
and acreage fields are stored in a separate table but accessed transparently
on the partner record. The ORM auto-creates the delegated record on create.
"""

import json
import logging

import pyproj
from shapely.geometry import mapping
from shapely.ops import transform

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Farm(models.Model):
    """Farm extension of res.partner with vocabulary and CEL support."""

    _inherit = "res.partner"
    _inherits = {"spp.farm.details": "farm_details_id"}

    # ═══════════════════════════════════════════════════════════════════════
    # FARM DETAILS LINK (required by _inherits)
    # ═══════════════════════════════════════════════════════════════════════

    farm_details_id = fields.Many2one(
        "spp.farm.details",
        string="Farm Details",
        required=True,
        ondelete="cascade",
        delegate=True,
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CORE FARM FIELDS (remain on partner for GIS)
    # ═══════════════════════════════════════════════════════════════════════

    coordinates = fields.GeoPointField(string="GPS Coordinates")

    # ═══════════════════════════════════════════════════════════════════════
    # RELATIONAL FIELDS
    # ═══════════════════════════════════════════════════════════════════════

    # Farm assets
    farm_asset_ids = fields.One2many(
        "spp.farm.asset",
        "asset_farm_id",
        string="Farm Assets",
    )
    farm_machinery_ids = fields.One2many(
        "spp.farm.asset",
        "machinery_farm_id",
        string="Farm Machinery",
    )

    # Land records
    farm_land_rec_ids = fields.One2many(
        "spp.land.record",
        "land_farm_id",
        string="Land Parcels",
    )

    # Extension services
    farm_extension_ids = fields.One2many(
        "spp.farm.extension",
        "farm_id",
        string="Extension Services",
    )

    # Agricultural activities (by type for UI organization)
    farm_crop_act_ids = fields.One2many(
        "spp.farm.activity",
        "crop_farm_id",
        string="Crop Activities",
    )
    farm_livestock_act_ids = fields.One2many(
        "spp.farm.activity",
        "livestock_farm_id",
        string="Livestock Activities",
    )
    farm_aquaculture_act_ids = fields.One2many(
        "spp.farm.activity",
        "aquaculture_farm_id",
        string="Aquaculture Activities",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS (farm details — on partner so onchange works)
    # ═══════════════════════════════════════════════════════════════════════

    farm_size_hectares = fields.Float(
        string="Farm Size (Hectares)",
        compute="_compute_farm_size_hectares",
        store=True,
        help="Alias for farm_total_size, used by CEL variables",
    )
    is_smallholder = fields.Boolean(
        string="Is Smallholder",
        compute="_compute_is_smallholder",
        store=True,
        help="Computed based on configurable threshold (default 5 hectares)",
    )
    has_productive_land = fields.Boolean(
        string="Has Productive Land",
        compute="_compute_has_productive_land",
        store=True,
        help="True if farm has any land under crops, livestock, or aquaculture",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED FIELDS FOR CEL VARIABLES (activity counts)
    # ═══════════════════════════════════════════════════════════════════════

    crop_activity_count = fields.Integer(
        string="Crop Activity Count",
        compute="_compute_activity_counts",
        store=True,
    )
    livestock_activity_count = fields.Integer(
        string="Livestock Activity Count",
        compute="_compute_activity_counts",
        store=True,
    )
    aquaculture_activity_count = fields.Integer(
        string="Aquaculture Activity Count",
        compute="_compute_activity_counts",
        store=True,
    )
    land_parcel_count = fields.Integer(
        string="Land Parcel Count",
        compute="_compute_land_parcel_count",
        store=True,
    )

    # Livestock total (sum of quantities)
    total_livestock_heads = fields.Integer(
        string="Total Livestock Heads",
        compute="_compute_total_livestock_heads",
        store=True,
        help="Sum of all livestock activity quantities",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # MEMBERSHIP COMPLETENESS (#939)
    # ═══════════════════════════════════════════════════════════════════════
    # Farm-registry users need to surface farms that aren't usable yet because
    # nobody is associated with them, or because no member is flagged as the
    # head of household. Stored so the search filters and list-row decoration
    # can use them without triggering N+1 reads.

    member_count = fields.Integer(
        string="# Members",
        compute="_compute_member_membership_state",
        store=True,
        help="Number of non-ended members linked to this farm/group.",
    )

    # ═══════════════════════════════════════════════════════════════════════
    # COMPUTED METHODS
    # ═══════════════════════════════════════════════════════════════════════

    @api.depends("farm_total_size")
    def _compute_farm_size_hectares(self):
        """Alias for CEL variable access."""
        for record in self:
            record.farm_size_hectares = record.farm_total_size or 0.0

    @api.depends("farm_total_size")
    def _compute_is_smallholder(self):
        """Determine smallholder status based on configurable threshold."""
        ICP = self.env["ir.config_parameter"].sudo()  # nosemgrep
        threshold = float(ICP.get_param("spp.farmer.smallholder_threshold", "5.0"))
        for record in self:
            record.is_smallholder = (record.farm_total_size or 0.0) <= threshold

    @api.depends("farm_size_under_crops", "farm_size_under_livestock", "farm_size_under_aquaculture")
    def _compute_has_productive_land(self):
        """Check if farm has any productive land."""
        for record in self:
            record.has_productive_land = (
                (record.farm_size_under_crops or 0.0) > 0
                or (record.farm_size_under_livestock or 0.0) > 0
                or (record.farm_size_under_aquaculture or 0.0) > 0
            )

    @api.depends("farm_crop_act_ids", "farm_livestock_act_ids", "farm_aquaculture_act_ids")
    def _compute_activity_counts(self):
        """Compute activity counts by type."""
        for record in self:
            record.crop_activity_count = len(record.farm_crop_act_ids)
            record.livestock_activity_count = len(record.farm_livestock_act_ids)
            record.aquaculture_activity_count = len(record.farm_aquaculture_act_ids)

    @api.depends("farm_land_rec_ids")
    def _compute_land_parcel_count(self):
        """Compute total land parcel count."""
        for record in self:
            record.land_parcel_count = len(record.farm_land_rec_ids)

    @api.depends("farm_livestock_act_ids.quantity")
    def _compute_total_livestock_heads(self):
        """Sum all livestock activity quantities."""
        for record in self:
            record.total_livestock_heads = sum(act.quantity or 0 for act in record.farm_livestock_act_ids)

    @api.depends(
        "group_membership_ids",
        "group_membership_ids.is_ended",
    )
    def _compute_member_membership_state(self):
        """Compute member_count from non-ended memberships."""
        for record in self:
            record.member_count = len(record.group_membership_ids.filtered(lambda m: not m.is_ended))

    # ═══════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def get_group_head_member(self):
        """Get the head of household/farm.

        Returns the individual member with 'head' membership type.
        """
        self.ensure_one()
        if not self.is_registrant or not self.is_group:
            return None

        head_kind_id = self.env["spp.vocabulary.code"].get_code("urn:openspp:vocab:group-membership-type", "head")
        for member in self.group_membership_ids:
            if head_kind_id in member.membership_type_ids:
                return member.individual
        return None

    def is_female_farmer(self):
        """Check if farm is female-headed.

        Returns True if the head of household is female.
        """
        self.ensure_one()
        head = self.get_group_head_member()
        if not head or not head.gender_id:
            return False
        # Check if gender vocabulary code indicates female
        return head.gender_id.code in ("female", "F")

    def get_farm_type_code(self):
        """Get the farm type vocabulary code string."""
        self.ensure_one()
        return self.farm_type_id.code if self.farm_type_id else None

    def get_land_tenure_code(self):
        """Get the land tenure vocabulary code string."""
        self.ensure_one()
        return self.land_tenure_id.code if self.land_tenure_id else None

    def is_farm_type(self, code):
        """Check if farm matches a specific type code.

        Args:
            code: The vocabulary code to check (e.g., 'crop', 'livestock', 'mixed')

        Returns:
            bool: True if farm type matches
        """
        self.ensure_one()
        return self.farm_type_id and self.farm_type_id.code == code

    # ═══════════════════════════════════════════════════════════════════════
    # GIS / GEOJSON METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _process_record_to_feature(self, record, transformer):
        """Convert a farm record to a GeoJSON feature.

        Args:
            record: The farm record to process.
            transformer: pyproj transformer for coordinate conversion.

        Returns:
            A GeoJSON feature dictionary or None if coordinates are not found.
        """
        if not record.coordinates:
            return None

        point_transformed = mapping(transform(transformer, record.coordinates))

        return {
            "type": "Feature",
            "geometry": point_transformed,
            "properties": {
                "name": record.name,
                "farm_type": record.farm_type_id.display_name if record.farm_type_id else None,
                "farm_size": record.farm_total_size,
            },
        }

    @api.model
    def get_geojson(self, domain=None):
        """Generate a GeoJSON representation of farm records.

        Args:
            domain: Optional search domain to filter farms.

        Returns:
            A GeoJSON string of farm records.
        """
        domain = domain or [("is_group", "=", True), ("is_registrant", "=", True)]
        farms = self.search(domain)

        geojson_features = {"type": "FeatureCollection", "features": []}

        # Transform from EPSG:3857 to WGS84
        proj_from = pyproj.Proj("epsg:3857")
        proj_to = pyproj.Proj("epsg:4326")
        transformer = pyproj.Transformer.from_proj(proj_from, proj_to, always_xy=True).transform

        for farm in farms:
            feature = self._process_record_to_feature(farm, transformer)
            if feature:
                geojson_features["features"].append(feature)

        return json.dumps(geojson_features, indent=2)

    # ═══════════════════════════════════════════════════════════════════════
    # VOCABULARY ACCESS METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def get_all_species(self):
        """Get all unique species across all activities.

        Returns:
            Recordset of spp.vocabulary.code records for all species.
        """
        self.ensure_one()
        species = self.env["spp.vocabulary.code"]
        for act in self.farm_crop_act_ids | self.farm_livestock_act_ids | self.farm_aquaculture_act_ids:
            if act.species_id:
                species |= act.species_id
        return species

    def get_crop_diversity_count(self):
        """Get count of unique crop species.

        Returns:
            int: Number of distinct crop species cultivated.
        """
        self.ensure_one()
        return len(set(act.species_id.id for act in self.farm_crop_act_ids if act.species_id))

    def has_irrigation(self):
        """Check if any crop activities use irrigation.

        Returns:
            bool: True if any activity has irrigated cultivation method.
        """
        self.ensure_one()
        for act in self.farm_crop_act_ids:
            if act.cultivation_method_id and act.cultivation_method_id.code == "irrigated":
                return True
        return False

    # ═══════════════════════════════════════════════════════════════════════
    # ACTION METHODS (for view buttons)
    # ═══════════════════════════════════════════════════════════════════════

    def action_view_crop_activities(self):
        """Open crop activities for this farm."""
        self.ensure_one()
        return {
            "name": "Crop Activities",
            "type": "ir.actions.act_window",
            "res_model": "spp.farm.activity",
            "view_mode": "list,form",
            "domain": [("crop_farm_id", "=", self.id)],
            "context": {"default_crop_farm_id": self.id, "default_activity_type": "crop"},
        }

    def action_view_livestock_activities(self):
        """Open livestock activities for this farm."""
        self.ensure_one()
        return {
            "name": "Livestock Activities",
            "type": "ir.actions.act_window",
            "res_model": "spp.farm.activity",
            "view_mode": "list,form",
            "domain": [("livestock_farm_id", "=", self.id)],
            "context": {"default_livestock_farm_id": self.id, "default_activity_type": "livestock"},
        }

    def action_view_aquaculture_activities(self):
        """Open aquaculture activities for this farm."""
        self.ensure_one()
        return {
            "name": "Aquaculture Activities",
            "type": "ir.actions.act_window",
            "res_model": "spp.farm.activity",
            "view_mode": "list,form",
            "domain": [("aquaculture_farm_id", "=", self.id)],
            "context": {"default_aquaculture_farm_id": self.id, "default_activity_type": "aquaculture"},
        }

    def action_view_land_parcels(self):
        """Open land parcels for this farm."""
        self.ensure_one()
        return {
            "name": "Land Parcels",
            "type": "ir.actions.act_window",
            "res_model": "spp.land.record",
            "view_mode": "list,form,gis",
            "domain": [("land_farm_id", "=", self.id)],
            "context": {"default_land_farm_id": self.id},
        }
