# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: GIS spatial stats must honor the GIS publication boundary.

`request.variables` is client-supplied and flows to the aggregation service,
which resolves names via sudo() against all indicators and all CEL variables.
Only names an admin published to GIS (`spp.indicator.is_published_gis`) may be
computed — supplying an unpublished indicator name, or a raw CEL variable name,
must not return an aggregate for it.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGisPublishedVariables(TransactionCase):
    """Supplied variables are restricted to the GIS-published allowlist."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        Indicator = cls.env["spp.indicator"]
        CelVariable = cls.env["spp.cel.variable"]

        cls.group = Partner.create({"name": "GIS Pub Group", "is_registrant": True, "is_group": True})
        cls.member = Partner.create({"name": "GIS Pub Member", "is_registrant": True, "is_group": False})
        if "spp.group.membership" in cls.env:
            cls.env["spp.group.membership"].create({"group": cls.group.id, "individual": cls.member.id})
        cls.registrant_ids = [cls.group.id, cls.member.id]

        def _make_var(name):
            return CelVariable.create(
                {
                    "name": name,
                    "cel_accessor": name,
                    "source_type": "aggregate",
                    "aggregate_type": "count",
                    "aggregate_target": "members",
                    "aggregate_filter": "true",
                    "value_type": "number",
                    "applies_to": "group",
                    "state": "active",
                }
            )

        # Published-to-GIS indicator (allowed).
        cls.published_var = _make_var("gis_pub_var")
        cls.published = Indicator.create(
            {
                "name": "gis_published_stat",
                "label": "GIS Published Stat",
                "variable_id": cls.published_var.id,
                "format": "count",
                "is_published_gis": True,
            }
        )
        # Indicator NOT published to GIS (must be denied).
        cls.unpublished_var = _make_var("gis_unpub_var")
        cls.unpublished = Indicator.create(
            {
                "name": "gis_unpublished_stat",
                "label": "GIS Unpublished Stat",
                "variable_id": cls.unpublished_var.id,
                "format": "count",
                "is_published_gis": False,
            }
        )
        # Raw CEL variable, never surfaced as a GIS indicator (must be denied).
        cls.raw_var = _make_var("gis_raw_cel_var")

    def _service(self):
        from ..services.spatial_query_service import SpatialQueryService

        return SpatialQueryService(self.env)

    def _flat_stat_keys(self, result):
        return {k for k in result.get("statistics", {}) if k != "_grouped"}

    def test_unpublished_indicator_name_is_not_computed(self):
        result = self._service()._compute_statistics(self.registrant_ids, ["gis_unpublished_stat"])
        self.assertNotIn("gis_unpublished_stat", self._flat_stat_keys(result))

    def test_raw_cel_variable_name_is_not_computed(self):
        result = self._service()._compute_statistics(self.registrant_ids, ["gis_raw_cel_var"])
        self.assertNotIn("gis_raw_cel_var", self._flat_stat_keys(result))

    def test_published_indicator_name_is_computed(self):
        result = self._service()._compute_statistics(self.registrant_ids, ["gis_published_stat"])
        self.assertIn("gis_published_stat", self._flat_stat_keys(result))

    def test_default_path_uses_published_only(self):
        result = self._service()._compute_statistics(self.registrant_ids, [])
        keys = self._flat_stat_keys(result)
        self.assertIn("gis_published_stat", keys)
        self.assertNotIn("gis_unpublished_stat", keys)
