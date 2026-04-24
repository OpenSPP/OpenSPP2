# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Contract test: every $ref in the OpenAPI schema must resolve.

Catches the failure mode where polymorphic_body declares a oneOf of $refs
but the referenced model isn't registered or the OpenAPI hook isn't
installed.
"""

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestOpenAPIContract(HttpCase):
    """Walk the live OpenAPI schema; assert every $ref resolves."""

    def test_all_refs_resolve(self):
        response = self.url_open("/api/v2/spp/openapi.json")
        self.assertEqual(response.status_code, 200, response.text)
        schema = response.json()
        components = schema.get("components", {}).get("schemas", {})

        unresolved = []

        def walk(node, path):
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                    name = ref.rsplit("/", 1)[-1]
                    if name not in components:
                        unresolved.append((path, ref))
                for k, v in node.items():
                    walk(v, f"{path}.{k}")
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")

        walk(schema, "$")

        self.assertEqual(
            unresolved,
            [],
            "Unresolved $refs in OpenAPI schema. Either install_polymorphic_openapi_hook "
            "is not wired, or a polymorphic_body() references a model not in components/schemas.\n"
            f"Found: {unresolved[:5]}",
        )
