#!/usr/bin/env python3
"""Prepare Philippine geodata from HDX COD-AB for OpenSPP demo modules.

Downloads administrative boundary shapefiles and population projection data from
the Humanitarian Data Exchange (HDX), processes them, and generates static data
files for the spp_demo and spp_demo_phl_luzon modules.

Data Sources:
    - COD-AB: https://data.humdata.org/dataset/cod-ab-phl (CC BY-IGO)
    - Population: https://data.humdata.org/dataset/a8fa512a-0a12-4753-ba46-b722eaac6d66

Outputs:
    Base tier (spp_demo/data/):
        - countries/phl/areas.xml: NCR + CALABARZON areas (regions, provinces, municipalities)
        - shapes/phl_curated.geojson: Simplified polygons for base areas

    Luzon tier (spp_demo_phl_luzon/data/):
        - areas_luzon.xml: All Luzon areas (8 regions, ~35 provinces, ~700 municipalities)
        - shapes/phl_luzon.geojson: Simplified polygons for all Luzon areas
        - population_weights.csv: Municipality-level population for weighted distribution

Usage:
    # Requires: geopandas, shapely, requests
    uv run --with geopandas --with requests --with pandas --with openpyxl scripts/prepare_phl_geodata.py

    # Custom simplification tolerance (default: 0.005 degrees, ~500m)
    uv run --with geopandas --with requests --with pandas --with openpyxl \\
        scripts/prepare_phl_geodata.py --simplify-tolerance 0.003

    # Force re-download (ignore cache)
    uv run --with geopandas --with requests --with pandas --with openpyxl scripts/prepare_phl_geodata.py --no-cache

Attribution (CC BY-IGO):
    Administrative boundaries: OCHA, PSA, NAMRIA
    Population data: PSA via HDX
"""

import argparse
import io
import json
import logging
import os
import sys
import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, indent, tostring

import geopandas as gpd
import requests
from shapely.validation import make_valid

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
_logger = logging.getLogger(__name__)

# HDX download URLs
COD_AB_URL = (
    "https://data.humdata.org/dataset/caf116df-f984-4deb-85ca-41b349d3f313"
    "/resource/12457689-6a86-4474-8032-5ca9464d38a8/download"
    "/phl_adm_psa_namria_20231106_shp.zip"
)

# Population projection dataset (admin 3)
# This dataset may have multiple resources; we look for the CSV
POP_DATASET_URL = "https://data.humdata.org/dataset/a8fa512a-0a12-4753-ba46-b722eaac6d66"

CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "openspp" / "geodata"

# HDX COD-AB region codes for Luzon island group (short format from shapefiles)
LUZON_REGION_CODES = {
    "PH13": "NCR",
    "PH14": "CAR",
    "PH01": "Region I",
    "PH02": "Region II",
    "PH03": "Region III",
    "PH04": "CALABARZON",
    "PH17": "MIMAROPA",
    "PH05": "Region V",
}

# Base tier: NCR + CALABARZON only (matches current curated set)
BASE_REGION_CODES = {"PH13", "PH04"}

# Shapefile name patterns inside the zip (without extensions)
SHP_PATTERNS = {
    1: "phl_admbnda_adm1_psa_namria_",
    2: "phl_admbnda_adm2_psa_namria_",
    3: "phl_admbnda_adm3_psa_namria_",
}

# Area type XML IDs (from spp_demo/data/countries/phl/area_kinds.xml)
AREA_TYPE_REFS = {
    1: "spp_demo.area_kind_phl_region",
    2: "spp_demo.area_kind_phl_province",
    3: "spp_demo.area_kind_phl_municipality",
}


def download_with_cache(url, filename, cache_dir, no_cache=False):
    """Download a file, caching it locally.

    Args:
        url: URL to download
        filename: Local filename for cache
        cache_dir: Cache directory path
        no_cache: If True, skip cache and re-download

    Returns:
        Path to cached file
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_path = cache_dir / filename

    if cached_path.exists() and not no_cache:
        _logger.info("Using cached %s", cached_path)
        return cached_path

    _logger.info("Downloading %s ...", filename)
    _logger.info("  URL: %s", url)
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(cached_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    print(
                        f"\r  Progress: {pct}% ({downloaded // (1024 * 1024)}MB / {total // (1024 * 1024)}MB)", end=""
                    )
    print()
    _logger.info("Saved to %s", cached_path)
    return cached_path


def find_shapefile_in_zip(zip_path, pattern):
    """Find a shapefile base name inside a zip by pattern.

    Shapefiles consist of multiple files (.shp, .dbf, .shx, .prj, etc.)
    sharing the same base name. We find the .shp file matching the pattern.

    Args:
        zip_path: Path to zip file
        pattern: String pattern to match in filenames

    Returns:
        Base name (without extension) of the matching shapefile, or None
    """
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if pattern in name.lower() and name.endswith(".shp"):
                return name
    return None


def read_shapefile_from_zip(zip_path, shp_name):
    """Read a shapefile from inside a zip archive using geopandas.

    Args:
        zip_path: Path to the zip file
        shp_name: Name of the .shp file inside the zip

    Returns:
        GeoDataFrame
    """
    uri = f"zip://{zip_path}!{shp_name}"
    _logger.info("Reading %s", uri)
    return gpd.read_file(uri)


def filter_luzon(gdf, level, region_codes):
    """Filter a GeoDataFrame to only Luzon regions.

    Uses the ADM1_PCODE column to filter to Luzon region codes.

    Args:
        gdf: GeoDataFrame with admin boundary data
        level: Admin level (1, 2, or 3)
        region_codes: Set of region p-codes to include

    Returns:
        Filtered GeoDataFrame
    """
    if level == 1:
        col = "ADM1_PCODE"
    else:
        # Level 2 and 3 have ADM1_PCODE as a column for their parent region
        col = "ADM1_PCODE"

    if col not in gdf.columns:
        _logger.warning("Column %s not found in level %d data. Available: %s", col, level, list(gdf.columns))
        return gdf

    mask = gdf[col].isin(region_codes)
    filtered = gdf[mask].copy()
    _logger.info("  Filtered level %d: %d -> %d features (Luzon)", level, len(gdf), len(filtered))
    return filtered


def simplify_geometries(gdf, tolerance):
    """Simplify geometries and validate results.

    Args:
        gdf: GeoDataFrame
        tolerance: Simplification tolerance in degrees

    Returns:
        GeoDataFrame with simplified geometries
    """
    _logger.info("  Simplifying with tolerance=%s ...", tolerance)
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].simplify(tolerance, preserve_topology=True)

    # Validate and fix any invalid geometries
    invalid_count = 0
    for idx in gdf.index:
        geom = gdf.at[idx, "geometry"]
        if geom is not None and not geom.is_valid:
            gdf.at[idx, "geometry"] = make_valid(geom)
            invalid_count += 1

    if invalid_count:
        _logger.info("  Fixed %d invalid geometries after simplification", invalid_count)

    return gdf


def get_pcode_col(level):
    """Get the p-code column name for a given admin level."""
    return f"ADM{level}_PCODE"


def get_name_col(level):
    """Get the English name column for a given admin level."""
    return f"ADM{level}_EN"


def build_areas_xml(regions_gdf, provinces_gdf, municipalities_gdf, module_name, xml_id_prefix):
    """Generate Odoo XML data file for spp.area records.

    Args:
        regions_gdf: GeoDataFrame of regions (level 1)
        provinces_gdf: GeoDataFrame of provinces (level 2)
        municipalities_gdf: GeoDataFrame of municipalities (level 3)
        module_name: Module name for external ID references (e.g., "spp_demo_phl_luzon")
        xml_id_prefix: Prefix for XML IDs (e.g., "area_luzon")

    Returns:
        bytes: UTF-8 encoded XML content
    """
    root = Element("odoo")
    root.set("noupdate", "0")
    root.text = "\n"

    # Add comment
    comment_text = (
        "\n    Philippine Administrative Areas (HDX COD-AB)\n"
        "    Source: https://data.humdata.org/dataset/cod-ab-phl\n"
        "    License: CC BY-IGO (OCHA, PSA, NAMRIA)\n"
        "    Generated by scripts/prepare_phl_geodata.py\n"
    )
    from xml.etree.ElementTree import Comment

    root.append(Comment(comment_text))

    def make_xml_id(pcode):
        """Convert a p-code to a valid XML ID."""
        return f"{xml_id_prefix}_{pcode.lower()}"

    def add_area_record(parent, pcode, name, area_type_ref, parent_pcode=None):
        """Add an spp.area record element."""
        record = SubElement(parent, "record")
        record.set("id", make_xml_id(pcode))
        record.set("model", "spp.area")

        name_field = SubElement(record, "field")
        name_field.set("name", "draft_name")
        name_field.text = name

        code_field = SubElement(record, "field")
        code_field.set("name", "code")
        code_field.text = pcode

        type_field = SubElement(record, "field")
        type_field.set("name", "area_type_id")
        type_field.set("ref", area_type_ref)

        if parent_pcode:
            parent_field = SubElement(record, "field")
            parent_field.set("name", "parent_id")
            parent_field.set("ref", make_xml_id(parent_pcode))

        record.tail = "\n\n"
        return record

    # Regions (level 1)
    root.append(Comment(" Regions "))
    for _, row in regions_gdf.sort_values(get_pcode_col(1)).iterrows():
        pcode = row[get_pcode_col(1)]
        name = row[get_name_col(1)]
        add_area_record(root, pcode, name, AREA_TYPE_REFS[1])

    # Provinces (level 2)
    root.append(Comment(" Provinces "))
    for _, row in provinces_gdf.sort_values(get_pcode_col(2)).iterrows():
        pcode = row[get_pcode_col(2)]
        name = row[get_name_col(2)]
        parent_pcode = row[get_pcode_col(1)]
        add_area_record(root, pcode, name, AREA_TYPE_REFS[2], parent_pcode)

    # Municipalities (level 3)
    root.append(Comment(" Municipalities / Cities "))
    for _, row in municipalities_gdf.sort_values(get_pcode_col(3)).iterrows():
        pcode = row[get_pcode_col(3)]
        name = row[get_name_col(3)]
        parent_pcode = row[get_pcode_col(2)]
        add_area_record(root, pcode, name, AREA_TYPE_REFS[3], parent_pcode)

    indent(root, space="    ")

    xml_decl = b'<?xml version="1.0" encoding="utf-8" ?>\n'
    return xml_decl + tostring(root, encoding="utf-8")


def build_geojson(regions_gdf, provinces_gdf, municipalities_gdf):
    """Build a GeoJSON FeatureCollection from all admin levels.

    Each feature has properties: code, name, level.

    Args:
        regions_gdf: GeoDataFrame of regions
        provinces_gdf: GeoDataFrame of provinces
        municipalities_gdf: GeoDataFrame of municipalities

    Returns:
        dict: GeoJSON FeatureCollection
    """
    features = []

    for level, gdf in [(1, regions_gdf), (2, provinces_gdf), (3, municipalities_gdf)]:
        pcode_col = get_pcode_col(level)
        name_col = get_name_col(level)
        level_names = {1: "region", 2: "province", 3: "municipality"}

        for _, row in gdf.iterrows():
            geom = row["geometry"]
            if geom is None:
                continue
            feature = {
                "type": "Feature",
                "properties": {
                    "code": row[pcode_col],
                    "name": row[name_col],
                    "level": level_names[level],
                },
                "geometry": json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"],
            }
            features.append(feature)

    return {
        "type": "FeatureCollection",
        "name": "phl_hdx_areas",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": features,
    }


def build_population_csv(municipalities_gdf, pop_data=None):
    """Build population weights CSV.

    If population data is available, merges it with municipality data.
    Otherwise, creates a placeholder with equal weights.

    Args:
        municipalities_gdf: GeoDataFrame of municipalities
        pop_data: Optional dict of {pcode: population}

    Returns:
        str: CSV content
    """
    import csv

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["pcode", "name", "province_pcode", "region_pcode", "population"])

    pcode_col = get_pcode_col(3)
    name_col = get_name_col(3)

    for _, row in municipalities_gdf.sort_values(pcode_col).iterrows():
        pcode = row[pcode_col]
        name = row[name_col]
        province_pcode = row[get_pcode_col(2)]
        region_pcode = row[get_pcode_col(1)]

        if pop_data and pcode in pop_data:
            population = pop_data[pcode]
        else:
            # Default weight of 10000 for municipalities without population data
            population = 10000

        writer.writerow([pcode, name, province_pcode, region_pcode, population])

    return output.getvalue()


def psgc_to_shp_pcode(psgc_code):
    """Convert a 10-digit PSGC code to the shorter HDX shapefile p-code format.

    PSGC format: PH + RR + PP + CC + BBB (2+2+2+3 digits = 9 digits after PH)
    SHP format:  PH + RR + 0PP + CC (region + zero-padded province + city)

    Examples:
        PH012801000 (Adams) -> PH0102801
        PH133901000 (Manila) -> PH1303901
        PH012800000 (Ilocos Norte province) -> PH01028
        PH010000000 (Region I) -> PH01

    Args:
        psgc_code: 10-digit PSGC code like "PH012801000"

    Returns:
        Short SHP-format p-code
    """
    digits = psgc_code[2:]  # Strip "PH" prefix
    rr = digits[0:2]  # Region (2 digits)
    pp = digits[2:4]  # Province (2 digits)
    cc = digits[4:6]  # City/Municipality (2 digits)
    bbb = digits[6:9]  # Barangay (3 digits)

    if pp == "00" and cc == "00" and bbb == "000":
        # Region level
        return f"PH{rr}"
    elif cc == "00" and bbb == "000":
        # Province level: zero-pad province to 3 digits
        return f"PH{rr}0{pp}"
    elif bbb == "000":
        # Municipality level
        return f"PH{rr}0{pp}{cc}"
    else:
        # Barangay level
        return f"PH{rr}0{pp}{cc}{bbb}"


def try_download_population_data(cache_dir, no_cache=False):
    """Try to download and parse population projection data from HDX.

    The population file uses 10-digit PSGC codes (e.g., PH012801000) while
    the shapefiles use shorter codes (e.g., PH0102801). This function returns
    data keyed by the short SHP codes for direct matching.

    This is best-effort: if the download fails or format changes, we
    fall back to equal weights.

    Returns:
        dict of {shp_pcode: population} or None
    """
    try:
        # Use the HDX CKAN API to find the download URL
        api_url = "https://data.humdata.org/api/3/action/package_show?id=a8fa512a-0a12-4753-ba46-b722eaac6d66"
        _logger.info("Fetching population dataset metadata...")
        resp = requests.get(api_url, timeout=30)
        resp.raise_for_status()
        dataset = resp.json()["result"]

        # Find the Excel/CSV resource (prefer one with "adm3" in name)
        download_url = None
        for resource in dataset.get("resources", []):
            fmt = resource.get("format", "").upper()
            name = resource.get("name", "").lower()
            if fmt in ("CSV", "XLSX", "XLS") and "adm3" in name:
                download_url = resource["url"]
                break

        if not download_url:
            for resource in dataset.get("resources", []):
                fmt = resource.get("format", "").upper()
                if fmt in ("CSV", "XLSX", "XLS"):
                    download_url = resource["url"]
                    break

        if not download_url:
            _logger.warning("No CSV/Excel resource found in population dataset")
            return None

        ext = ".xlsx" if "xlsx" in download_url.lower() or "xls" in download_url.lower() else ".csv"
        pop_file = download_with_cache(download_url, f"phl_population_adm3{ext}", cache_dir, no_cache)

        import pandas as pd

        if ext == ".xlsx":
            df = pd.read_excel(pop_file)
        else:
            df = pd.read_csv(pop_file)

        _logger.info("Population data columns: %s", list(df.columns))

        # Expected columns: Mun_Pcode (PSGC format), July2025 (or latest year)
        pcode_col = None
        pop_col = None

        for col in df.columns:
            col_lower = col.lower()
            if "mun" in col_lower and "pcode" in col_lower:
                pcode_col = col
            elif "adm3" in col_lower and "pcode" in col_lower:
                pcode_col = col

        # Find the most recent population year column (prefer July2025, then 2024, etc.)
        for year in ["2025", "2024", "2023", "2022", "2021", "2020"]:
            for col in df.columns:
                if year in col:
                    pop_col = col
                    break
            if pop_col:
                break

        if not pcode_col or not pop_col:
            _logger.warning(
                "Could not identify columns. pcode=%s, pop=%s. Available: %s",
                pcode_col,
                pop_col,
                list(df.columns),
            )
            return None

        _logger.info("Using columns: pcode=%s, population=%s", pcode_col, pop_col)

        # Build dict keyed by SHP-format p-codes
        pop_data = {}
        for _, row in df.iterrows():
            psgc_code = str(row[pcode_col]).strip()
            try:
                population = int(float(row[pop_col]))
                if population > 0:
                    shp_code = psgc_to_shp_pcode(psgc_code)
                    pop_data[shp_code] = population
            except (ValueError, TypeError):
                continue

        _logger.info("Loaded population data for %d municipalities", len(pop_data))
        return pop_data

    except Exception as e:
        _logger.warning("Failed to download population data: %s", e)
        _logger.warning("Falling back to equal weights")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Prepare Philippine geodata from HDX for OpenSPP demo modules.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--simplify-tolerance",
        type=float,
        default=0.005,
        help="Geometry simplification tolerance in degrees (default: 0.005, ~500m)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force re-download of all files",
    )
    parser.add_argument(
        "--luzon-only",
        action="store_true",
        help="Only generate Luzon tier (skip base tier)",
    )
    parser.add_argument(
        "--base-only",
        action="store_true",
        help="Only generate base tier (skip Luzon tier)",
    )
    args = parser.parse_args()

    # Determine project root (script is in scripts/)
    project_root = Path(__file__).parent.parent.resolve()
    _logger.info("Project root: %s", project_root)

    # Step 1: Download HDX shapefile
    shp_zip = download_with_cache(
        COD_AB_URL,
        "phl_adm_psa_namria_20231106_shp.zip",
        CACHE_DIR,
        args.no_cache,
    )

    # Step 2: Find shapefile names inside zip
    shp_names = {}
    for level, pattern in SHP_PATTERNS.items():
        shp_name = find_shapefile_in_zip(shp_zip, pattern)
        if not shp_name:
            _logger.error("Could not find level %d shapefile matching pattern '%s' in zip", level, pattern)
            sys.exit(1)
        shp_names[level] = shp_name
        _logger.info("Found level %d shapefile: %s", level, shp_name)

    # Step 3: Read shapefiles
    gdfs = {}
    for level, shp_name in shp_names.items():
        gdfs[level] = read_shapefile_from_zip(shp_zip, shp_name)
        _logger.info("  Level %d: %d features, columns: %s", level, len(gdfs[level]), list(gdfs[level].columns))

    # Step 4: Filter and simplify for each tier
    luzon_codes = set(LUZON_REGION_CODES.keys())

    # Luzon tier
    luzon_gdfs = {}
    for level in [1, 2, 3]:
        filtered = filter_luzon(gdfs[level], level, luzon_codes)
        luzon_gdfs[level] = simplify_geometries(filtered, args.simplify_tolerance)

    # Base tier (NCR + CALABARZON)
    base_gdfs = {}
    for level in [1, 2, 3]:
        filtered = filter_luzon(gdfs[level], level, BASE_REGION_CODES)
        base_gdfs[level] = simplify_geometries(filtered, args.simplify_tolerance)

    # Step 5: Download population data
    pop_data = try_download_population_data(CACHE_DIR, args.no_cache)

    # Step 6: Generate outputs
    if not args.luzon_only:
        _generate_base_tier(project_root, base_gdfs)

    if not args.base_only:
        _generate_luzon_tier(project_root, luzon_gdfs, pop_data)

    _logger.info("Done!")


def _generate_base_tier(project_root, gdfs):
    """Generate base tier output (NCR + CALABARZON) into spp_demo/data/."""
    _logger.info("=== Generating base tier (NCR + CALABARZON) ===")

    base_dir = project_root / "spp_demo" / "data"

    # Areas XML
    xml_content = build_areas_xml(
        gdfs[1],
        gdfs[2],
        gdfs[3],
        module_name="spp_demo",
        xml_id_prefix="area_phl",
    )
    areas_path = base_dir / "countries" / "phl" / "areas.xml"
    areas_path.parent.mkdir(parents=True, exist_ok=True)
    areas_path.write_bytes(xml_content)
    _logger.info("Wrote %s (%d bytes)", areas_path, len(xml_content))

    # Count records per level
    for level, name in [(1, "regions"), (2, "provinces"), (3, "municipalities")]:
        _logger.info("  %d %s", len(gdfs[level]), name)

    # GeoJSON
    geojson = build_geojson(gdfs[1], gdfs[2], gdfs[3])
    shapes_dir = base_dir / "shapes"
    shapes_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = shapes_dir / "phl_curated.geojson"
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f)
    size_mb = geojson_path.stat().st_size / (1024 * 1024)
    _logger.info("Wrote %s (%.1f MB, %d features)", geojson_path, size_mb, len(geojson["features"]))


def _generate_luzon_tier(project_root, gdfs, pop_data):
    """Generate Luzon tier output into spp_demo_phl_luzon/data/."""
    _logger.info("=== Generating Luzon tier (all 8 regions) ===")

    luzon_dir = project_root / "spp_demo_phl_luzon" / "data"
    luzon_dir.mkdir(parents=True, exist_ok=True)

    # Areas XML
    xml_content = build_areas_xml(
        gdfs[1],
        gdfs[2],
        gdfs[3],
        module_name="spp_demo_phl_luzon",
        xml_id_prefix="area_luzon",
    )
    areas_path = luzon_dir / "areas_luzon.xml"
    areas_path.write_bytes(xml_content)
    _logger.info("Wrote %s (%d bytes)", areas_path, len(xml_content))

    # Count records per level
    for level, name in [(1, "regions"), (2, "provinces"), (3, "municipalities")]:
        _logger.info("  %d %s", len(gdfs[level]), name)

    # GeoJSON
    geojson = build_geojson(gdfs[1], gdfs[2], gdfs[3])
    shapes_dir = luzon_dir / "shapes"
    shapes_dir.mkdir(parents=True, exist_ok=True)
    geojson_path = shapes_dir / "phl_luzon.geojson"
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f)
    size_mb = geojson_path.stat().st_size / (1024 * 1024)
    _logger.info("Wrote %s (%.1f MB, %d features)", geojson_path, size_mb, len(geojson["features"]))

    # Population weights CSV
    csv_content = build_population_csv(gdfs[3], pop_data)
    csv_path = luzon_dir / "population_weights.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    _logger.info("Wrote %s (%d municipalities)", csv_path, len(gdfs[3]))


if __name__ == "__main__":
    main()
