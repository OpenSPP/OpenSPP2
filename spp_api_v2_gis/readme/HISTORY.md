### 19.0.2.0.1

- fix(security): restrict spatial/proximity statistics to GIS-published
  indicators. Client-supplied ``variables`` were passed straight to the
  aggregation service, which resolves names via ``sudo()`` against all
  indicators and CEL variables, so a caller with only GIS/statistics read could
  request unpublished indicator or raw CEL variable names and receive their
  aggregates. Supplied variables are now filtered to the same GIS publication
  allowlist (``spp.indicator.is_published_gis``) already used for the default
  path; unpublished names are dropped before aggregation.

### 19.0.2.0.0

- Initial migration to OpenSPP2
