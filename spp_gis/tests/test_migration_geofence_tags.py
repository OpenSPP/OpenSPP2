# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import importlib.util
from pathlib import Path

from odoo.tests.common import TransactionCase

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations" / "19.0.2.1.0"


def _load(script):
    spec = importlib.util.spec_from_file_location(f"spp_gis_tag_migration_{script}", MIGRATIONS_DIR / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestGeofenceTagMigration(TransactionCase):
    """Exercise the 19.0.2.1.0 migration pair that remaps geofence tags.

    Up to v19.0.2.0.0 (release Biliran) geofence tag_ids pointed at
    spp.vocabulary through spp_gis_geofence_tag_rel. The field now points at
    spp.gis.geofence.tag over the SAME rel table. The pre-migration parks
    legacy rows in an aux table (so the FK swap during upgrade succeeds); the
    post-migration creates one tag per legacy vocabulary and restores links.

    Tests simulate the legacy state by dropping the new FK inside the test
    transaction (Postgres DDL rolls back with the test).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.geofence = cls.env["spp.gis.geofence"].create(
            {
                "name": "Migration Geofence",
                "geometry": '{"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]}',
            }
        )
        cls.vocab_a = cls.env["spp.vocabulary"].create(
            {"name": "Legacy Tag A", "namespace_uri": "urn:test:legacy-tag-a"}
        )
        cls.vocab_b = cls.env["spp.vocabulary"].create(
            {"name": "Legacy Tag B", "namespace_uri": "urn:test:legacy-tag-b"}
        )

    def _simulate_legacy_links(self, vocab_ids):
        cr = self.env.cr
        cr.execute(
            "ALTER TABLE spp_gis_geofence_tag_rel DROP CONSTRAINT IF EXISTS spp_gis_geofence_tag_rel_tag_id_fkey"
        )
        for vid in vocab_ids:
            cr.execute(
                "INSERT INTO spp_gis_geofence_tag_rel (geofence_id, tag_id) VALUES (%s, %s)",
                (self.geofence.id, vid),
            )

    def _run_both(self):
        cr = self.env.cr
        _load("pre-migration.py").migrate(cr, "19.0.2.0.0")
        _load("post-migration.py").migrate(cr, "19.0.2.0.0")
        self.env.invalidate_all()

    def test_01_legacy_links_remapped_to_new_tags(self):
        self._simulate_legacy_links([self.vocab_a.id, self.vocab_b.id])

        self._run_both()

        tags = self.geofence.tag_ids
        self.assertEqual(sorted(tags.mapped("name")), ["Legacy Tag A", "Legacy Tag B"])
        # links point at real spp.gis.geofence.tag records
        self.assertTrue(all(t._name == "spp.gis.geofence.tag" for t in tags))

    def test_02_shared_vocabulary_creates_single_tag(self):
        other = self.env["spp.gis.geofence"].create(
            {
                "name": "Migration Geofence 2",
                "geometry": '{"type": "Polygon", "coordinates": [[[0, 0], [0, 2], [2, 2], [0, 0]]]}',
            }
        )
        cr = self.env.cr
        self._simulate_legacy_links([self.vocab_a.id])
        cr.execute(
            "INSERT INTO spp_gis_geofence_tag_rel (geofence_id, tag_id) VALUES (%s, %s)",
            (other.id, self.vocab_a.id),
        )

        self._run_both()

        tags_a = self.env["spp.gis.geofence.tag"].search([("name", "=", "Legacy Tag A")])
        self.assertEqual(len(tags_a), 1, "one tag per legacy vocabulary, shared across geofences")
        self.assertIn(tags_a, self.geofence.tag_ids)
        self.assertIn(tags_a, other.tag_ids)

    def test_03_valid_new_links_survive(self):
        """Rel rows that already reference a real tag are left untouched."""
        tag = self.env["spp.gis.geofence.tag"].create({"name": "Already New"})
        self.geofence.tag_ids = [(4, tag.id)]

        self._run_both()

        self.assertIn(tag, self.geofence.tag_ids)

    def test_04_noop_on_fresh_database(self):
        self._run_both()
        self.assertFalse(self.geofence.tag_ids)
