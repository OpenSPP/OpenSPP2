### 19.0.2.0.1

- fix(security): build the API V2 FastAPI app from the current router module.
  ``fastapi_endpoint.py`` still imported ``aggregation_router`` from the removed
  ``routers/aggregation`` module (renamed to ``routers/analytics``), so
  ``_get_fastapi_routers()`` raised ``ModuleNotFoundError`` during app
  construction — which FastAPI dispatch performs, before endpoint OAuth/JWT
  checks, for a request to the API root. An unauthenticated request could
  therefore take the whole API V2 endpoint down. The import now targets
  ``routers/analytics`` (which still exports ``aggregation_router``).

### 19.0.2.0.0

- Initial migration to OpenSPP2
