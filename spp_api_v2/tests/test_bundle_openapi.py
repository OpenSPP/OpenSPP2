# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""OpenAPI-shape tests for the Bundle schema.

Asserts that `BundleEntry.resource` documents its accepted resource types
(Individual, Group) via `oneOf` of $refs instead of a bare `dict | None`.
"""

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestBundleEntryOpenAPI(HttpCase):
    """Bundle schema renders polymorphic resource documentation."""

    def test_bundle_entry_resource_documented_as_oneof(self):
        """BundleEntry.resource should document oneOf of supported FHIR types.

        Bundle service only supports Individual and Group (see
        spp_api_v2/services/bundle_service.py:299, 324, 350); anything else
        is rejected at runtime, so oneOf must list exactly those.
        """
        response = self.url_open("/api/v2/spp/openapi.json")
        self.assertEqual(response.status_code, 200, response.text)
        schema = response.json()
        components = schema["components"]["schemas"]

        self.assertIn("RegistrantBundleEntry", components)
        resource_schema = components["RegistrantBundleEntry"]["properties"]["resource"]

        # The base BundleEntry is reused by other modules (e.g. Products) for
        # non-registrant resources, so it must stay generic: no oneOf there.
        if "BundleEntry" in components:
            self.assertNotIn("oneOf", components["BundleEntry"]["properties"]["resource"])

        # Shape note: for `dict | None = polymorphic_body(...)`,
        # Pydantic emits `anyOf: [{type: object}, {type: null}]` and our hook
        # attaches `oneOf` at the SAME top level (siblings, not nested).
        self.assertIn("oneOf", resource_schema, f"no oneOf at top level: {resource_schema}")
        refs = [item.get("$ref") for item in resource_schema["oneOf"]]
        self.assertIn("#/components/schemas/Individual", refs)
        self.assertIn("#/components/schemas/Group", refs)

        # And the nullable shape comes from anyOf alongside.
        self.assertIn(
            {"type": "null"},
            resource_schema.get("anyOf", []),
            f"missing nullable anyOf branch: {resource_schema}",
        )

        # Both referenced models must actually be present in components.
        self.assertIn("Individual", components)
        self.assertIn("Group", components)
