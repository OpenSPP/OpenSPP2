### 19.0.2.1.1

- fix(security): deactivate the default-credential demo users (including the
  ``sppadmin`` SPP admin, all created with the well-known password ``demo``)
  when the module is installed on a database without demo data, so the known
  credentials cannot be used to log in on a production instance. The accounts
  stay active on demo/evaluation databases. Also lowers ``development_status``
  from ``Production/Stable`` to ``Alpha`` so the demo module no longer signals
  production-readiness.

### 19.0.2.1.0

- feat(demo): re-land curated PHL geodata and demo generator updates from #76: refreshed `data/shapes/phl_curated.geojson` and `data/countries/phl/areas.xml` (prepared via `scripts/prepare_phl_geodata.py`), with matching demo data generator and area loader test updates. Adds the companion `spp_demo_phl_luzon` module providing Luzon-scale demo areas and population weights.

### 19.0.2.0.0

- Initial migration to OpenSPP2
