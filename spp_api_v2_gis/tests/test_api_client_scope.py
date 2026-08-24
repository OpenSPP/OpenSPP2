# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Tests for the GIS-specific actions on spp.api.client.scope.

``routers/geofence.py`` gates create/delete on ``has_scope("gis", "geofence")``,
so ``geofence`` has to be a selectable value of the ``action`` field. Otherwise
the only client able to reach those endpoints is one holding ``action = all``.
"""

from uuid import uuid4

from odoo.tests.common import TransactionCase


class TestGisActionScopes(TransactionCase):
    """The GIS module must contribute its own scope actions."""

    @classmethod
    def setUpClass(cls):
        """Set up an organization and type usable by API clients."""
        super().setUpClass()
        cls.ApiClient = cls.env["spp.api.client"]
        cls.ApiScope = cls.env["spp.api.client.scope"]

        cls.test_partner = cls.env["res.partner"].create({"name": "Geofence Scope Organization"})

        cls.org_type = cls.env.ref("spp_consent.org_type_government", raise_if_not_found=False)
        if not cls.org_type:
            cls.org_type = cls.env["spp.consent.org.type"].search([("code", "=", "government")], limit=1)
        if not cls.org_type:
            cls.org_type = cls.env["spp.consent.org.type"].create({"name": "Government", "code": "government"})

    def _create_client_with_scopes(self, scopes):
        """Create an API client holding the given (resource, action) scopes."""
        # uuid4, not id(scopes): CPython reuses freed addresses, so two
        # throwaway scope lists can collide on the unique client_id.
        unique = uuid4().hex
        client = self.ApiClient.create(
            {
                "name": f"Geofence Scope Client {unique}",
                "client_id": f"test_geofence_client_{unique}",
                "partner_id": self.test_partner.id,
                "organization_type_id": self.org_type.id,
            }
        )
        for resource, action in scopes:
            self.ApiScope.create(
                {
                    "client_id": client.id,
                    "resource": resource,
                    "action": action,
                }
            )
        return client

    def test_geofence_action_is_selectable(self):
        """The geofence action is offered by the action selection."""
        selection = dict(self.ApiScope.fields_get(["action"])["action"]["selection"])
        self.assertIn("geofence", selection)

    def test_incident_action_is_selectable(self):
        """The incident action is offered by the action selection."""
        selection = dict(self.ApiScope.fields_get(["action"])["action"]["selection"])
        self.assertIn("incident", selection)

    def test_geofence_scope_can_be_stored(self):
        """A gis:geofence scope record can be created."""
        client = self._create_client_with_scopes([("gis", "geofence")])

        scope = client.scope_ids.filtered(lambda s: s.resource == "gis")
        self.assertEqual(scope.action, "geofence")

    def test_geofence_scope_grants_access(self):
        """A client holding gis:geofence passes the endpoint check."""
        client = self._create_client_with_scopes([("gis", "geofence")])

        self.assertTrue(client.has_scope("gis", "geofence"))

    def test_read_scope_does_not_grant_geofence_access(self):
        """gis:read is not enough to manage geofences."""
        client = self._create_client_with_scopes([("gis", "read")])

        self.assertFalse(client.has_scope("gis", "geofence"))

    def test_all_action_still_grants_geofence_access(self):
        """gis:all keeps granting geofence access."""
        client = self._create_client_with_scopes([("gis", "all")])

        self.assertTrue(client.has_scope("gis", "geofence"))

    def test_geofence_scope_does_not_grant_other_actions(self):
        """gis:geofence does not widen into unrelated actions."""
        client = self._create_client_with_scopes([("gis", "geofence")])

        self.assertFalse(client.has_scope("gis", "read"))
        self.assertFalse(client.has_scope("gis", "delete"))

    def test_incident_scope_can_be_stored(self):
        """A gis:incident scope record can be created."""
        client = self._create_client_with_scopes([("gis", "incident")])

        self.assertTrue(client.has_scope("gis", "incident"))
