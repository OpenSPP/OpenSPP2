# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
import importlib.util
from pathlib import Path

from .common import GISReportTestBase

MIGRATION_PATH = Path(__file__).parent.parent / "migrations" / "19.0.2.1.0" / "post-migrate.py"

_LEGACY_COLUMNS = ("disaggregate_by_gender", "disaggregate_by_age", "disaggregate_by_disability")


def _load_migration():
    spec = importlib.util.spec_from_file_location("spp_gis_report_bool_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestBooleanDimensionMigration(GISReportTestBase):
    """Exercise the 19.0.2.1.0 post-migration linking legacy boolean flags
    to dimension_ids.

    Legacy columns do not exist in a fresh database, so each test recreates
    them with SQL (Postgres DDL rolls back with the test transaction).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Dim = cls.env["spp.demographic.dimension"]
        cls.gender_dim = Dim.search([("name", "=", "gender")], limit=1) or Dim.create(
            {"name": "gender", "label": "Gender", "dimension_type": "field", "field_path": "gender_id.code"}
        )
        cls.age_dim = Dim.search([("name", "=", "age_group")], limit=1) or Dim.create(
            {"name": "age_group", "label": "Age Group", "dimension_type": "field", "field_path": "is_group"}
        )

    def _add_legacy_columns(self):
        for col in _LEGACY_COLUMNS:
            self.env.cr.execute(f"ALTER TABLE spp_gis_report ADD COLUMN IF NOT EXISTS {col} boolean")

    def _make_report(self, name):
        return self.create_test_report(name=name, code=f"mig_{name.lower().replace(' ', '_')}")

    def _set_flag(self, report, column):
        self.env.cr.execute(f"UPDATE spp_gis_report SET {column} = true WHERE id = %s", (report.id,))

    def _migrate(self, version="19.0.2.0.1"):
        _load_migration().migrate(self.env.cr, version)
        self.env.invalidate_all()

    def test_01_flags_link_matching_dimensions(self):
        self._add_legacy_columns()
        r_gender = self._make_report("Mig Gender Report")
        r_age = self._make_report("Mig Age Report")
        self._set_flag(r_gender, "disaggregate_by_gender")
        self._set_flag(r_age, "disaggregate_by_age")

        self._migrate()

        self.assertIn(self.gender_dim, r_gender.dimension_ids)
        self.assertIn(self.age_dim, r_age.dimension_ids)
        self.assertNotIn(self.age_dim, r_gender.dimension_ids)

    def test_02_idempotent_on_rerun(self):
        self._add_legacy_columns()
        report = self._make_report("Mig Idempotent Report")
        self._set_flag(report, "disaggregate_by_gender")

        self._migrate()
        self._migrate()

        self.assertEqual(report.dimension_ids.filtered(lambda d: d == self.gender_dim), self.gender_dim)
        self.assertEqual(len(report.dimension_ids), 1)

    def test_03_fresh_install_noop(self):
        """A falsy version (fresh install) must return before touching anything."""
        self._add_legacy_columns()
        report = self._make_report("Mig Fresh Report")
        self._set_flag(report, "disaggregate_by_gender")

        self._migrate(version=False)

        self.assertFalse(report.dimension_ids)

    def test_04_missing_dimension_warns_and_continues(self):
        self._add_legacy_columns()
        report = self._make_report("Mig Missing Dim Report")
        self._set_flag(report, "disaggregate_by_gender")
        self.gender_dim.name = "gender_renamed_away"

        with self.assertLogs(level="WARNING"):
            self._migrate()

        self.assertFalse(report.dimension_ids)

    def test_05_no_legacy_columns_noop(self):
        report = self._make_report("Mig No Columns Report")
        self._migrate()
        self.assertFalse(report.dimension_ids)
