# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Security: hazard models must not be readable by every internal user.

Regression test for "Broad internal read access exposes hazard impact records":
the ACL granted ``base.group_user`` read on the hazard models, so any internal
user could read hazard data (including registrant-linked impact records) via RPC,
even without a hazard role. Access must require a dedicated hazard group (or
``registry_viewer``/admin), not merely being an internal user.
"""

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import HazardTestCase

# The registrant-linked impact model is sensitive and must NOT be readable by
# every internal user. The other hazard models are non-PII reference/operational
# data that sibling modules (e.g. spp_drims) legitimately read broadly.
SENSITIVE_MODEL = "spp.hazard.impact"
NON_SENSITIVE_MODELS = [
    "spp.hazard.category",
    "spp.hazard.incident",
    "spp.hazard.incident.area",
    "spp.hazard.impact.type",
]
ALL_HAZARD_MODELS = [SENSITIVE_MODEL, *NON_SENSITIVE_MODELS]


@tagged("post_install", "-at_install")
class TestHazardBaseUserNoAccess(HazardTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plain_user = cls.env["res.users"].create(
            {
                "name": "Plain Internal User",
                "login": "plain_internal_hazard_test",
                "group_ids": [Command.link(cls.env.ref("base.group_user").id)],
            }
        )

    def test_plain_internal_user_cannot_read_impact(self):
        """base.group_user (any internal user) must NOT read the sensitive impact model."""
        with self.assertRaises(AccessError):
            self.env[SENSITIVE_MODEL].with_user(self.plain_user).check_access("read")

    def test_plain_internal_user_can_read_non_sensitive_models(self):
        """Non-PII hazard reference/operational models remain internally readable
        (sibling modules such as spp_drims depend on reading incidents)."""
        for model in NON_SENSITIVE_MODELS:
            # Raises AccessError only if broad read was wrongly removed here.
            self.env[model].with_user(self.plain_user).check_access("read")

    def test_hazard_viewer_retains_read(self):
        """A hazard-group user must keep read access to all hazard models."""
        for model in ALL_HAZARD_MODELS:
            self.env[model].with_user(self.hazard_viewer).check_access("read")

    def test_registry_user_can_still_read_registrant_hazard_fields(self):
        """Regression: the registrant form's hazard indicator fields read
        spp.hazard.impact in their compute. A registry user (Officer implies
        Registry Viewer, which retains hazard read) must still be able to load
        them after the ACL tightening — i.e. the fix must not break the form."""
        officer = self.env["res.users"].create(
            {
                "name": "Registry Officer (no hazard group)",
                "login": "registry_officer_hazard_test",
                "group_ids": [Command.link(self.env.ref("spp_registry.group_registry_officer").id)],
            }
        )
        # Sanity: this user is NOT in any hazard group.
        self.assertFalse(officer.has_group("spp_hazard.group_hazard_read"))

        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "Registry Officer Incident",
                "code": "ROI-HAZ-001",
                "category_id": self.category_typhoon.id,
                "start_date": "2024-01-01",
            }
        )
        self.env["spp.hazard.impact"].create(
            {
                "incident_id": incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_displacement.id,
                "damage_level": "moderate",
                "impact_date": "2024-01-02",
            }
        )
        registrant_as_officer = self.registrant.with_user(officer)
        # Force a live read through the impact O2M (not just the stored count),
        # which must not raise AccessError for a registry user.
        self.assertEqual(registrant_as_officer.hazard_impact_ids.mapped("damage_level"), ["moderate"])

    def test_plain_internal_user_cannot_read_affected_registrant_count(self):
        """spp.hazard.incident stays broadly readable, but its
        ``affected_registrant_count`` aggregate is derived from the sensitive
        impact table via raw ACL-bypassing SQL. A plain internal user must be
        able to read the incident yet be denied that field over RPC."""
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "Aggregate Leak Incident",
                "code": "ALI-HAZ-001",
                "category_id": self.category_typhoon.id,
                "start_date": "2024-01-01",
            }
        )
        self.env["spp.hazard.impact"].create(
            {
                "incident_id": incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_displacement.id,
                "damage_level": "moderate",
                "impact_date": "2024-01-02",
            }
        )
        incident_as_plain = incident.with_user(self.plain_user)
        # The incident itself remains readable (non-sensitive model)...
        incident_as_plain.read(["name"])
        # ...but the impact-derived aggregate must be denied.
        with self.assertRaises(AccessError):
            incident_as_plain.read(["affected_registrant_count"])
        with self.assertRaises(AccessError):
            # Attribute access goes through Field.__get__, which enforces the
            # field-level group guard independently of read().
            _ = incident_as_plain.affected_registrant_count

    def test_hazard_viewer_can_read_affected_registrant_count(self):
        """A hazard-group user must still read the affected-registrant aggregate."""
        incident = self.env["spp.hazard.incident"].create(
            {
                "name": "Aggregate Visible Incident",
                "code": "AVI-HAZ-001",
                "category_id": self.category_typhoon.id,
                "start_date": "2024-01-01",
            }
        )
        self.env["spp.hazard.impact"].create(
            {
                "incident_id": incident.id,
                "registrant_id": self.registrant.id,
                "impact_type_id": self.impact_type_displacement.id,
                "damage_level": "moderate",
                "impact_date": "2024-01-02",
            }
        )
        self.assertEqual(incident.with_user(self.hazard_viewer).affected_registrant_count, 1)

    def test_affected_registrant_count_column_hidden_from_non_hazard_user(self):
        """The incident list column reads the gated aggregate; it must be stripped
        from the arch for a plain internal user."""
        arch = self.env["spp.hazard.incident"].with_user(self.plain_user).get_view(view_type="list")["arch"]
        self.assertNotIn("affected_registrant_count", arch)

    def test_incident_form_hides_impacts_from_non_hazard_user(self):
        """The incident form's Impacts O2M reads spp.hazard.impact; it must be
        stripped from the arch for a user without impact read (e.g. a DRIMS-only
        user), so opening an incident does not raise AccessError."""
        arch = self.env["spp.hazard.incident"].with_user(self.plain_user).get_view(view_type="form")["arch"]
        self.assertNotIn("impact_ids", arch)

    def test_incident_form_shows_impacts_to_hazard_user(self):
        """A hazard user still gets the Impacts O2M on the incident form."""
        arch = self.env["spp.hazard.incident"].with_user(self.hazard_viewer).get_view(view_type="form")["arch"]
        self.assertIn("impact_ids", arch)

    def test_plain_internal_user_cannot_read_registrant_impact_fields(self):
        """``res.partner.hazard_impact_count`` / ``has_active_impact`` are stored
        columns derived from the sensitive impact table. Gating only the views is
        not enough: a plain internal user could still ``search_read`` them over RPC
        and enumerate which registrants are disaster victims. The fields must carry
        field-level ``groups=`` so the ORM refuses the read."""
        partner_as_plain = self.env["res.partner"].with_user(self.plain_user)
        with self.assertRaises(AccessError):
            partner_as_plain.search_read(
                [("id", "=", self.registrant.id)],
                ["name", "hazard_impact_count", "has_active_impact"],
            )

    def test_hazard_viewer_can_read_registrant_impact_fields(self):
        """A hazard-group user keeps read on the registrant impact indicator fields."""
        rows = (
            self.env["res.partner"]
            .with_user(self.hazard_viewer)
            .search_read([("id", "=", self.registrant.id)], ["hazard_impact_count", "has_active_impact"])
        )
        self.assertEqual(len(rows), 1)

    def test_contact_creator_without_impact_read_can_create_partner(self):
        """Guard: the two stored impact indicators are computed on every
        ``res.partner`` create by querying ``spp.hazard.impact``. Stored computes
        run as superuser (``compute_sudo`` defaults to True for stored fields), so
        removing ``base.group_user`` read on impacts must NOT break partner
        creation for an internal user who may create contacts but holds no
        hazard/registry role (e.g. Contact Creation only). Pins that behaviour,
        including the flush that actually runs the compute."""
        creator = self.env["res.users"].create(
            {
                "name": "Contact Creator (no hazard/registry group)",
                "login": "contact_creator_hazard_test",
                "group_ids": [
                    Command.link(self.env.ref("base.group_user").id),
                    Command.link(self.env.ref("base.group_partner_manager").id),
                ],
            }
        )
        self.assertFalse(creator.has_group("spp_hazard.group_hazard_read"))
        self.assertFalse(creator.has_group("spp_registry.group_registry_viewer"))
        with self.assertRaises(AccessError):
            self.env[SENSITIVE_MODEL].with_user(creator).check_access("read")

        partner = self.env["res.partner"].with_user(creator).create({"name": "Created by contact creator"})
        # Stored computes are deferred to flush time; flush in the CREATOR's env
        # (as a real request does at its end) so the compute runs as that user.
        partner.env.flush_all()
        self.assertTrue(partner.exists())
        self.assertEqual(partner.sudo().hazard_impact_count, 0)
        self.assertFalse(partner.sudo().has_active_impact)
