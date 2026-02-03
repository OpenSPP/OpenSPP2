# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

import logging
import re

import requests

_logger = logging.getLogger(__name__)

HDX_API_BASE = "https://data.humdata.org/api/3"


class HdxClient:
    """
    Client for HDX CKAN API.

    Provides methods to interact with the Humanitarian Data Exchange (HDX)
    CKAN API for searching and downloading Common Operational Datasets (COD).
    """

    def __init__(self, api_key=None):
        """
        Initialize HDX API client.

        Args:
            api_key: Optional API key for authenticated requests
        """
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers["Authorization"] = api_key

    def search_cod_datasets(self, country_iso3):
        """
        Search for COD-AB datasets for a country.

        COD-AB datasets follow the naming convention: cod-ab-{iso3}

        Args:
            country_iso3: ISO3 country code (e.g., 'LKA', 'PHL')

        Returns:
            dict: Dataset metadata including resources

        Raises:
            requests.HTTPError: If the API request fails
        """
        dataset_id = f"cod-ab-{country_iso3.lower()}"
        return self.get_dataset(dataset_id)

    def get_dataset(self, dataset_id):
        """
        Get dataset metadata including resources.

        Args:
            dataset_id: HDX dataset identifier

        Returns:
            dict: Dataset metadata with resources list

        Raises:
            requests.HTTPError: If the API request fails
        """
        url = f"{HDX_API_BASE}/action/package_show"
        try:
            response = self.session.get(url, params={"id": dataset_id}, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result.get("result", {})
        except requests.RequestException as error:
            _logger.error("Failed to get HDX dataset %s: %s", dataset_id, str(error))
            raise

    def download_resource(self, resource_url):
        """
        Download a resource file.

        Args:
            resource_url: URL of the resource to download

        Returns:
            bytes: Resource file content

        Raises:
            requests.HTTPError: If the download fails
        """
        try:
            response = self.session.get(resource_url, stream=True, timeout=120)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            _logger.error("Failed to download resource from %s: %s", resource_url, str(error))
            raise

    def get_geojson_resources(self, dataset):
        """
        Filter resources to GeoJSON files.

        Args:
            dataset: Dataset metadata dictionary

        Returns:
            list: List of GeoJSON resource dictionaries
        """
        geojson_resources = []
        for resource in dataset.get("resources", []):
            resource_format = resource.get("format", "").lower()
            if resource_format in ["geojson", "json"]:
                geojson_resources.append(resource)
        return geojson_resources

    def detect_admin_level(self, resource_name):
        """
        Detect admin level from resource name.

        Attempts to extract admin level from resource name/description.
        Common patterns: "Admin Level 3", "ADM3", "adm_3"

        Args:
            resource_name: Resource name or description

        Returns:
            int: Admin level (0-4) or None if not detected
        """
        if not resource_name:
            return None

        name_lower = resource_name.lower()

        # Pattern: "admin level 3", "admin 3", "level 3"
        match = re.search(r"(?:admin\s*(?:level)?\s*|level\s*)(\d)", name_lower)
        if match:
            return int(match.group(1))

        # Pattern: "adm3", "adm_3"
        match = re.search(r"adm[_\s]*(\d)", name_lower)
        if match:
            return int(match.group(1))

        return None

    def detect_field_mappings(self, geojson_data):
        """
        Detect P-code and name field mappings from GeoJSON properties.

        Analyzes the first feature's properties to identify likely field names
        for P-codes, names, and parent P-codes based on common patterns.

        Args:
            geojson_data: Parsed GeoJSON dictionary

        Returns:
            dict: Field mappings with keys: pcode_field, name_field,
                  name_local_field, parent_pcode_field
        """
        mappings = {
            "pcode_field": None,
            "name_field": None,
            "name_local_field": None,
            "parent_pcode_field": None,
        }

        # Get first feature properties
        features = geojson_data.get("features", [])
        if not features:
            return mappings

        properties = features[0].get("properties", {})
        if not properties:
            return mappings

        # Detect P-code field
        pcode_candidates = ["pcode", "adm_pcode", "admin_pcode"]
        for key in properties.keys():
            key_lower = key.lower()
            # Match ADMn_PCODE (e.g., ADM3_PCODE)
            if "_pcode" in key_lower:
                mappings["pcode_field"] = key
                # Try to detect admin level from field name
                match = re.search(r"adm(\d)", key_lower)
                if match:
                    admin_level = int(match.group(1))
                    # Look for parent level
                    parent_level = admin_level - 1
                    parent_field = key.replace(str(admin_level), str(parent_level))
                    if parent_field in properties:
                        mappings["parent_pcode_field"] = parent_field
                break
            elif key_lower in pcode_candidates:
                mappings["pcode_field"] = key
                break

        # Detect name field (English)
        name_candidates = ["name", "name_en", "adm_en", "admin_en"]
        for key in properties.keys():
            key_lower = key.lower()
            if "_en" in key_lower or key_lower in name_candidates:
                mappings["name_field"] = key
                break

        # Detect local name field
        local_candidates = ["name_local", "name_si", "name_ta", "adm_local"]
        for key in properties.keys():
            key_lower = key.lower()
            if any(pattern in key_lower for pattern in ["_si", "_ta", "_local", "_alt"]):
                if key != mappings["name_field"]:
                    mappings["name_local_field"] = key
                    break

        return mappings
