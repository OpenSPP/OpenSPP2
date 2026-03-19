import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class IrrigationAsset(models.Model):
    _name = "spp.irrigation.asset"
    _description = "Irrigation Asset Details"

    name = fields.Char(string="Irrigation Name/ID")

    # Farm relationship - links irrigation asset to a farm
    farm_id = fields.Many2one(
        "res.partner",
        string="Farm",
        domain="[('is_group', '=', True), ('is_registrant', '=', True)]",
        help="Farm that owns or uses this irrigation asset",
    )

    # Vocabulary-based asset type
    asset_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Asset Type",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:openspp:vocab:irrigation-asset-type')]",
        help="Type of irrigation infrastructure",
    )

    # Computed field for backward compatibility
    category = fields.Char(
        string="Category Code",
        compute="_compute_category",
        store=True,
        help="Deprecated: Use asset_type_id instead",
    )

    @api.depends("asset_type_id", "asset_type_id.code")
    def _compute_category(self):
        for record in self:
            record.category = record.asset_type_id.code if record.asset_type_id else False

    total_capacity = fields.Float()

    coordinates = fields.GeoPointField()
    geo_polygon = fields.GeoPolygonField()

    irrigation_source_ids = fields.Many2many(
        "spp.irrigation.asset",
        string="Irrigation Sources",
        relation="spp_irrigation_asset_source_rel",
        column1="source_id",
        column2="destination_id",
    )
    irrigation_destination_ids = fields.Many2many(
        "spp.irrigation.asset",
        string="Irrigation Destinations",
        relation="spp_irrigation_asset_destination_rel",
        column1="destination_id",
        column2="source_id",
    )
