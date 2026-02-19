# Changelog

All notable changes to the OpenSPP HDX COD Integration module will be documented in this
file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [19.0.1.0.0] - 2026-01-07

### Added

- Initial implementation of HDX COD integration module
- HDX COD Source model (`spp.hdx.cod.source`) for tracking COD datasets
- HDX COD Resource model (`spp.hdx.cod.resource`) for admin level resources
- HDX API client with automatic field mapping detection
- Multi-step import wizard with preview functionality
- Dual import modes: HDX API download and manual file upload
- GPS-based area lookup using PostGIS spatial queries:
  - `find_by_coordinates(lat, lon, level)` - Find containing area
  - `find_all_containing(lat, lon)` - Get full hierarchy
  - `find_by_pcode(pcode)` - Find by P-code
- Extension of `spp.area` model with:
  - `hdx_pcode` field for official P-codes
  - `hdx_last_update` timestamp
- Pre-configured COD sources for 10 humanitarian countries:
  - Sri Lanka, Philippines, Nepal, Bangladesh, Pakistan
  - Afghanistan, Myanmar, Yemen, Somalia, South Sudan
- Security groups and privileges:
  - HDX User (read-only)
  - HDX Manager (full CRUD and import)
- Comprehensive test coverage (28 tests across 4 test files)
- Batch processing for large datasets (100 features per commit)
- Field mapping auto-detection from GeoJSON properties
- Import options: update existing, create missing, update names
- Integration with spp_gis for polygon storage and spatial queries
- Documentation: README.rst, inline docstrings, HTML description

### Technical Details

- 1810 lines of Python code
- 444 lines of XML configuration
- 27 files total
- Compatible with Odoo 19.0
- Dependencies: spp_area, spp_gis, requests, geojson
- PostGIS integration for spatial operations
- LGPL-3 license
