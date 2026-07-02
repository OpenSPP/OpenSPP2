# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from .common import DrimsTestCommon


class TestIncidentAreaSeverity(DrimsTestCommon):
    """Effective severity / numeric severity for the GIS choropleth.

    Guards the spp_hazard severity migration (Selection -> CAP vocabulary
    Many2one): spp_drims extends spp.hazard.incident.area and must follow the
    new severity_id / severity_override_id fields.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        VocabCode = cls.env["spp.vocabulary.code"]
        ns = "urn:oasis:names:tc:cap:severity"
        cls.sev_extreme = VocabCode.get_code(ns, "extreme")
        cls.sev_severe = VocabCode.get_code(ns, "severe")
        cls.sev_moderate = VocabCode.get_code(ns, "moderate")

    def _make_area(self, severity_override_id=False):
        return self.env["spp.hazard.incident.area"].create(
            {
                "incident_id": self.incident.id,
                "area_id": self.area.id,
                "severity_override_id": severity_override_id,
            }
        )

    def test_effective_severity_uses_override(self):
        """Area override takes precedence over the incident severity."""
        self.incident.severity_id = self.sev_moderate
        area = self._make_area(severity_override_id=self.sev_extreme.id)
        self.assertEqual(area.effective_severity_id, self.sev_extreme)
        self.assertEqual(area.severity_numeric, 5)

    def test_effective_severity_falls_back_to_incident(self):
        """Without an override, severity is inherited from the incident."""
        self.incident.severity_id = self.sev_severe
        area = self._make_area()
        self.assertEqual(area.effective_severity_id, self.sev_severe)
        self.assertEqual(area.severity_numeric, 4)

    def test_severity_numeric_zero_when_unset(self):
        """No override and no incident severity -> numeric 0 (no choropleth value)."""
        self.incident.severity_id = False
        area = self._make_area()
        self.assertFalse(area.effective_severity_id)
        self.assertEqual(area.severity_numeric, 0)
