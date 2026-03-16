# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import csv
import logging

from odoo import models
from odoo.tools.misc import file_path

_logger = logging.getLogger(__name__)


class DemoPopulationWeights(models.TransientModel):
    _name = "spp.demo.population.weights"
    _description = "Demo Population Weights"

    # Class-level cache so the CSV is only parsed once per process lifetime.
    _weights_cache = None

    @classmethod
    def get_weights(cls):
        """Return a dict mapping pcode to population count.

        The CSV is read once and cached at the class level for subsequent calls.
        """
        if cls._weights_cache is not None:
            return cls._weights_cache

        csv_path = file_path("spp_demo_phl_luzon/data/population_weights.csv")
        weights = {}
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pcode = row["pcode"].strip()
                try:
                    population = int(row["population"])
                except (ValueError, KeyError):
                    _logger.warning(
                        "Skipping invalid population row for pcode: %s", pcode
                    )
                    continue
                weights[pcode] = population

        cls._weights_cache = weights
        return weights

    def get_weights_by_area_id(self):
        """Return a dict mapping spp.area record id to population count.

        Looks up each pcode from the CSV against spp.area records that have a
        matching code field, then substitutes the area id as the key.
        """
        pcode_weights = self.get_weights()
        if not pcode_weights:
            return {}

        areas = self.env["spp.area"].search(
            [("code", "in", list(pcode_weights.keys()))]
        )
        area_by_pcode = {area.code: area.id for area in areas}

        weights_by_area_id = {}
        for pcode, population in pcode_weights.items():
            area_id = area_by_pcode.get(pcode)
            if area_id is not None:
                weights_by_area_id[area_id] = population

        return weights_by_area_id
