# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import importlib.util
from pathlib import Path

from odoo.tests.common import TransactionCase

CAP_SEVERITY_NS = "urn:oasis:names:tc:cap:severity"

MIGRATION_PATH = Path(__file__).parent.parent / "migrations" / "19.0.2.1.0" / "post-migration.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("spp_hazard_severity_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSeverityMigration(TransactionCase):
    """Exercise the 19.0.2.1.0 post-migration that backfills severity
    vocabulary codes from the legacy 1-5 Selection columns.

    The legacy columns do not exist in a fresh database, so each test
    recreates them with SQL before running the migration (Postgres DDL is
    transactional and rolls back with the test).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.VocabCode = cls.env["spp.vocabulary.code"]
        cls.category = cls.env["spp.hazard.category"].create({"name": "Migration Cat", "code": "MIG-CAT"})
        cls.area = cls.env["spp.area"].create({"draft_name": "Migration Area", "code": "MIG-AREA"})

    def _make_incident(self, code):
        return self.env["spp.hazard.incident"].create(
            {"name": f"Migration incident {code}", "code": code, "category_id": self.category.id}
        )

    def _add_legacy_columns(self):
        self.env.cr.execute("ALTER TABLE spp_hazard_incident ADD COLUMN IF NOT EXISTS severity varchar")
        self.env.cr.execute("ALTER TABLE spp_hazard_incident_area ADD COLUMN IF NOT EXISTS severity_override varchar")

    def _set_legacy(self, incident, value):
        self.env.cr.execute("UPDATE spp_hazard_incident SET severity = %s WHERE id = %s", (value, incident.id))

    def _cap_code(self, code):
        return self.VocabCode.get_code(CAP_SEVERITY_NS, code)

    def _migrate(self):
        _load_migration().migrate(self.env.cr, "19.0.2.0.2")
        self.env.invalidate_all()

    def test_01_mapping_a_backfills_incident_severity(self):
        """Legacy 1-5 values map label-faithfully to CAP codes (mapping A)."""
        expected = {"1": "minor", "2": "moderate", "3": "severe", "4": "severe", "5": "extreme"}
        self._add_legacy_columns()
        incidents = {}
        for legacy in expected:
            incidents[legacy] = self._make_incident(f"MIG-{legacy}")
            self._set_legacy(incidents[legacy], legacy)

        self._migrate()

        for legacy, cap in expected.items():
            self.assertEqual(
                incidents[legacy].severity_id,
                self._cap_code(cap),
                f"legacy severity {legacy!r} should map to CAP {cap!r}",
            )

    def test_02_backfills_area_severity_override(self):
        self._add_legacy_columns()
        incident = self._make_incident("MIG-AREA-1")
        area_link = self.env["spp.hazard.incident.area"].create({"incident_id": incident.id, "area_id": self.area.id})
        self.env.cr.execute(
            "UPDATE spp_hazard_incident_area SET severity_override = %s WHERE id = %s", ("5", area_link.id)
        )

        self._migrate()

        self.assertEqual(area_link.severity_override_id, self._cap_code("extreme"))

    def test_03_does_not_overwrite_existing_value(self):
        """Idempotent: a severity_id already set (e.g. manually re-entered) wins."""
        self._add_legacy_columns()
        incident = self._make_incident("MIG-KEEP")
        incident.severity_id = self._cap_code("minor")
        self._set_legacy(incident, "5")

        self._migrate()

        self.assertEqual(incident.severity_id, self._cap_code("minor"))

    def test_04_unmapped_value_left_empty(self):
        self._add_legacy_columns()
        incident = self._make_incident("MIG-JUNK")
        self._set_legacy(incident, "not-a-level")

        with self.assertLogs("odoo.addons.spp_hazard.migrations.severity", level="WARNING"):
            self._migrate()

        self.assertFalse(incident.severity_id)

    def test_05_noop_without_legacy_columns(self):
        """Fresh installs have no legacy columns; the migration must not fail."""
        incident = self._make_incident("MIG-FRESH")
        self._migrate()
        self.assertFalse(incident.severity_id)
