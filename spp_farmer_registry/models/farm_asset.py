# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class FarmAsset(models.Model):
    """Farm Assets and Technology.

    Tracks equipment, machinery, and other assets owned by farms.
    """

    _name = "spp.farm.asset"
    _description = "Farm Assets and Technology"

    asset_farm_id = fields.Many2one("res.partner", string="Asset Farm")
    machinery_farm_id = fields.Many2one("res.partner", string="Machinery Farm")

    display_name = fields.Char(compute="_compute_display_name")

    @api.depends("asset_type_id", "machinery_type_id", "technology_used", "machine_working_status", "quantity")
    def _compute_display_name(self):
        for rec in self:
            if rec.asset_type_id:
                parts = [rec.asset_type_id.name]
                if rec.technology_used:
                    parts.append(f"({rec.technology_used})")
                if rec.quantity:
                    parts.append(f"x{rec.quantity}")
                rec.display_name = " ".join(parts)
            elif rec.machinery_type_id:
                parts = [rec.machinery_type_id.name]
                if rec.machine_working_status:
                    parts.append(f"({rec.machine_working_status})")
                if rec.quantity:
                    parts.append(f"x{rec.quantity}")
                rec.display_name = " ".join(parts)
            else:
                rec.display_name = f"Asset #{rec.id}"

    land_id = fields.Many2one(
        "spp.land.record",
        string="Land",
        required=False,
        domain="[('farm_id', '=', asset_farm_id)]",
    )

    asset_type_id = fields.Many2one("spp.asset.type", string="Asset Type")
    machinery_type_id = fields.Many2one("spp.machinery.type", string="Machinery Type")
    technology_used = fields.Char()
    quantity = fields.Integer()
    machine_working_status = fields.Char("Working Status")

    @api.onchange("asset_farm_id")
    def _onchange_farm_id(self):
        for rec in self:
            rec.land_id = False


class AssetType(models.Model):
    """Asset Type classification."""

    _name = "spp.asset.type"
    _description = "Asset Type"

    name = fields.Char(string="Asset Type")


class MachineryType(models.Model):
    """Machinery Type classification."""

    _name = "spp.machinery.type"
    _description = "Machinery Type"

    name = fields.Char(string="Machinery Type")


class FarmExtension(models.Model):
    """Farm Extension Services.

    Tracks extension services provided to farms.
    """

    _name = "spp.farm.extension"
    _description = "Farm Extension Services"

    farm_id = fields.Many2one("res.partner", string="Farm")
    service_type = fields.Char(string="Service Type")
    provider = fields.Char(string="Provider")
    date = fields.Date(string="Date")
    notes = fields.Text(string="Notes")
