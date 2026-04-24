# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Helpers for documenting polymorphic dict-typed request bodies.

A polymorphic body is a request field whose Python type stays `dict` (so
downstream code can keep calling `.get(...)`) but whose OpenAPI schema is
documented as a `oneOf` of typed Pydantic models.

Usage in a schema:

    from ..utils.openapi_polymorphic import polymorphic_body

    class ExecuteRequest(BaseModel):
        inputs: dict = polymorphic_body(
            SpatialStatisticsInputs,
            ProximityStatisticsInputs,
            description="Process input values; structure depends on process_id.",
        )

Wiring the hook (once per FastAPI app):

    from .utils.openapi_polymorphic import install_polymorphic_openapi_hook
    install_polymorphic_openapi_hook(app)

Why a hook is needed: models passed to `polymorphic_body` are referenced only
via `$ref` strings in `json_schema_extra`. FastAPI's OpenAPI generator does not
discover them from endpoint signatures, so the hook injects them into
`components/schemas` after generation.
"""

import logging
from typing import Any

from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from pydantic.json_schema import models_json_schema

from fastapi import FastAPI

_logger = logging.getLogger(__name__)

# Module-level registry. Shared across all FastAPI apps in the process; the
# hook scopes injection to models actually referenced by each app's routes.
_REGISTRY: list[type[BaseModel]] = []


def polymorphic_body(
    *models: type[BaseModel],
    description: str = "",
    default: Any = ...,
) -> Any:
    """Return a Pydantic Field documenting a dict body as `oneOf` of models.

    The runtime type stays `dict` (or `dict | None` if `default=None` and the
    annotation is `dict | None`). Downstream validation and access patterns
    are unaffected. Models are registered for OpenAPI injection by
    `install_polymorphic_openapi_hook`.

    For optional fields (e.g. `BundleEntry.resource`), pass `default=None`
    alongside a `dict | None` annotation.
    """
    if not models:
        raise ValueError("polymorphic_body requires at least one model")
    for m in models:
        if not (isinstance(m, type) and issubclass(m, BaseModel)):
            raise TypeError(f"polymorphic_body expects BaseModel subclasses, got {m!r}")
        if m not in _REGISTRY:
            _REGISTRY.append(m)
    return Field(
        default,
        description=description,
        json_schema_extra={
            "oneOf": [{"$ref": f"#/components/schemas/{m.__name__}"} for m in models],
        },
    )


def register_polymorphic_models(*models: type[BaseModel]) -> None:
    """Register models for OpenAPI injection without attaching them to a Field.

    Useful when a polymorphic schema is built outside `polymorphic_body`
    (e.g., for response unions). Idempotent.
    """
    for m in models:
        if m not in _REGISTRY:
            _REGISTRY.append(m)


def reset_polymorphic_registry() -> None:
    """Clear the registry. Test-only."""
    _REGISTRY.clear()


def _collect_refs(node: Any, refs: set[str] | None = None) -> set[str]:
    """Recursively collect every $ref string from a JSON-Schema-shaped object."""
    if refs is None:
        refs = set()
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            refs.add(ref)
        for v in node.values():
            _collect_refs(v, refs)
    elif isinstance(node, list):
        for v in node:
            _collect_refs(v, refs)
    return refs


def install_polymorphic_openapi_hook(app: FastAPI) -> None:
    """Wrap `app.openapi` so registered models referenced by this app's routes
    are injected into `components/schemas`.

    Models registered globally but not referenced by any route in `app` are
    NOT injected, so cross-app pollution is avoided.
    """

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {}).setdefault("schemas", {})

        all_refs = _collect_refs(schema)
        missing = {ref.rsplit("/", 1)[-1] for ref in all_refs if ref.startswith("#/components/schemas/")} - set(
            components.keys()
        )

        wanted = [m for m in _REGISTRY if m.__name__ in missing]
        if wanted:
            _, defs = models_json_schema(
                [(m, "validation") for m in wanted],
                ref_template="#/components/schemas/{model}",
            )
            generated = defs.get("$defs", {})
            if not generated:
                _logger.warning(
                    "polymorphic OpenAPI hook found %d unresolved $refs (%s) "
                    "but models_json_schema produced no $defs; the schema may "
                    "still have dangling refs. Pydantic shape may have changed.",
                    len(wanted),
                    ", ".join(m.__name__ for m in wanted),
                )
            for name, model_schema in generated.items():
                components.setdefault(name, model_schema)

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
