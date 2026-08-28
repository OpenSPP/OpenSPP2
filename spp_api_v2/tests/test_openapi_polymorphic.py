# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Unit tests for the polymorphic_body helper and OpenAPI hook.

These tests do not require Odoo; they construct minimal FastAPI apps
and assert against the generated OpenAPI schema.
"""

from typing import Annotated

from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from odoo.tests.common import TransactionCase

from fastapi import Body, FastAPI

from ..utils.openapi_polymorphic import (
    install_polymorphic_openapi_hook,
    polymorphic_body,
    reset_polymorphic_registry,
)


class SimpleA(BaseModel):
    a_field: str = Field(..., description="A field")


class SimpleB(BaseModel):
    b_field: int


def _make_app():
    reset_polymorphic_registry()
    app = FastAPI(title="Test", version="0.0.1")

    class Body_(BaseModel):
        payload: dict = polymorphic_body(SimpleA, SimpleB, description="Payload")

    @app.post("/echo")
    def echo(body: Annotated[Body_, Body(...)]) -> dict:
        return {"type": type(body.payload).__name__, "value": body.payload}

    install_polymorphic_openapi_hook(app)
    return app


class TestPolymorphicBody(TransactionCase):
    """Unit tests for polymorphic_body helper."""

    def test_runtime_payload_is_dict(self):
        """Bodies matching SimpleA stay as dict, not parsed into a model."""
        client = TestClient(_make_app())
        r = client.post("/echo", json={"payload": {"a_field": "x"}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"type": "dict", "value": {"a_field": "x"}})

    def test_runtime_arbitrary_dict_accepted(self):
        """Bodies matching neither schema still pass (no validation regression)."""
        client = TestClient(_make_app())
        r = client.post("/echo", json={"payload": {"random": "stuff"}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["value"], {"random": "stuff"})

    def test_openapi_field_has_oneof_refs(self):
        """The body field renders as oneOf of $refs."""
        schema = _make_app().openapi()
        body_schema = schema["components"]["schemas"]["Body_"]
        payload = body_schema["properties"]["payload"]
        self.assertEqual(
            payload["oneOf"],
            [
                {"$ref": "#/components/schemas/SimpleA"},
                {"$ref": "#/components/schemas/SimpleB"},
            ],
        )

    def test_openapi_referenced_models_present(self):
        """Both typed models appear in components/schemas."""
        schema = _make_app().openapi()
        components = schema["components"]["schemas"]
        self.assertIn("SimpleA", components)
        self.assertIn("SimpleB", components)
        self.assertEqual(components["SimpleA"]["properties"]["a_field"]["description"], "A field")

    def test_openapi_unreferenced_models_not_injected(self):
        """Models registered but not referenced by any route are not added.

        Scoping check: registering SimpleA via polymorphic_body in one app
        must not cause it to leak into a different app that doesn't use it.
        """
        reset_polymorphic_registry()

        class WithBody(BaseModel):
            payload: dict = polymorphic_body(SimpleA, description="x")

        # First app uses the helper.
        app1 = FastAPI()

        @app1.post("/x")
        def _x(body: Annotated[WithBody, Body(...)]) -> dict:
            return {}

        install_polymorphic_openapi_hook(app1)
        self.assertIn("SimpleA", app1.openapi()["components"]["schemas"])

        # Second app does NOT use the helper but shares the registry.
        app2 = FastAPI()

        @app2.get("/y")
        def _y() -> dict:
            return {}

        install_polymorphic_openapi_hook(app2)
        self.assertNotIn(
            "SimpleA",
            app2.openapi().get("components", {}).get("schemas", {}),
        )

    def test_openapi_nested_model_refs_resolve(self):
        """Nested Pydantic types referenced by registered models also get injected."""
        reset_polymorphic_registry()

        class Inner(BaseModel):
            n: int

        class Outer(BaseModel):
            inner: Inner

        class Req(BaseModel):
            payload: dict = polymorphic_body(Outer)

        app = FastAPI()

        @app.post("/z")
        def _z(body: Annotated[Req, Body(...)]) -> dict:
            return {}

        install_polymorphic_openapi_hook(app)
        components = app.openapi()["components"]["schemas"]
        self.assertIn("Outer", components)
        self.assertIn("Inner", components)
        self.assertEqual(
            components["Outer"]["properties"]["inner"]["$ref"],
            "#/components/schemas/Inner",
        )

    def test_polymorphic_body_supports_optional_default(self):
        """Optional fields render correctly with `default=None`.

        For a `dict | None = polymorphic_body(..., default=None)` field, Pydantic
        emits `anyOf: [{type: object}, {type: null}]` and our hook attaches
        `oneOf: [<refs>]` at the same level. The two siblings are combined by
        JSON-Schema AND semantics; a deliberate trade-off that keeps the
        runtime type `dict` while Swagger renders the model choices.
        """
        reset_polymorphic_registry()

        class Req(BaseModel):
            payload: dict | None = polymorphic_body(SimpleA, default=None)

        app = FastAPI()

        @app.post("/x")
        def _x(body: Annotated[Req, Body(...)]) -> dict:
            return {"none": body.payload is None}

        install_polymorphic_openapi_hook(app)

        schema = app.openapi()
        payload = schema["components"]["schemas"]["Req"]["properties"]["payload"]
        self.assertIn("oneOf", payload)
        self.assertEqual(payload["oneOf"], [{"$ref": "#/components/schemas/SimpleA"}])
        # Pydantic adds the nullable shape as `anyOf`.
        self.assertIn({"type": "null"}, payload.get("anyOf", []))

        # And the model still resolves at runtime.
        self.assertIn("SimpleA", schema["components"]["schemas"])

        client = TestClient(app)
        r = client.post("/x", json={})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"none": True})
