# OpenSPP Demo: Philippines Luzon Geodata

Provides Philippine Luzon administrative boundary data and population weights for the
OpenSPP demo data generator.

## Contents

- **Area records**: Regions, provinces, and municipalities of Luzon, importable as
  `spp.area` records via the bundled loader (`spp.demo.luzon.area.loader`). The data is
  not loaded automatically on install; invoking the loader (e.g. from demo tooling or an
  Odoo shell) is a deliberate step. Automatic wiring into the demo generator is planned
  as a follow-up.
- **GeoJSON shapes**: Polygon geometries for all Luzon administrative units, located at
  `data/shapes/phl_luzon.geojson`.
- **Population weights**: Municipality-level population figures used to generate
  geographically realistic distributions of demo registrants.

## Data Attribution

Administrative boundary data sourced from OCHA Humanitarian Data Exchange (HDX) COD-AB
dataset. Source: PSA and NAMRIA. License: CC BY-IGO.

Dataset URL: https://data.humdata.org/dataset/cod-ab-phl
