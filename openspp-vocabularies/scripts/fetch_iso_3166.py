#!/usr/bin/env python3
"""Fetch ISO 3166-1 country codes from official sources.

Sources:
- Primary: https://datahub.io/core/country-list (CC-BY licensed)
- Backup: https://github.com/lukes/ISO-3166-Countries-with-Regional-Codes
"""

import json
import sys
from datetime import date
from pathlib import Path

import requests

# DataHub.io provides CC-BY licensed ISO 3166 data
DATAHUB_URL = "https://datahub.io/core/country-list/r/data.json"

# Backup source
GITHUB_URL = "https://raw.githubusercontent.com/lukes/ISO-3166-Countries-with-Regional-Codes/master/all/all.json"

OUTPUT_FILE = Path(__file__).parent.parent / "vocabularies" / "iso-3166-1-country.json"


def fetch_from_datahub():
    """Fetch country codes from DataHub.io."""
    response = requests.get(DATAHUB_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    codes = []
    for item in data:
        codes.append({"code": item["Code"], "display": item["Name"]})
    return codes


def fetch_from_github():
    """Fetch country codes from GitHub backup source."""
    response = requests.get(GITHUB_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    codes = []
    for item in data:
        codes.append({"code": item["alpha-2"], "display": item["name"]})
    return codes


def add_special_codes(codes):
    """Add OpenSPP special codes not in ISO standard."""
    existing = {c["code"] for c in codes}

    special = [
        {"code": "XA", "display": "Stateless", "definition": "Person without citizenship of any country"},
        {"code": "XK", "display": "Kosovo", "definition": "User-assigned code for Kosovo"},
        {"code": "ZZ", "display": "Unknown", "definition": "Unknown or unspecified country"},
    ]

    for code in special:
        if code["code"] not in existing:
            codes.append(code)

    return codes


def main():
    """Main entry point."""
    print("Fetching ISO 3166-1 country codes...")

    try:
        codes = fetch_from_datahub()
        print(f"  Fetched {len(codes)} codes from DataHub.io")
    except requests.RequestException as e:
        print(f"  DataHub.io failed: {e}")
        print("  Trying GitHub backup...")
        codes = fetch_from_github()
        print(f"  Fetched {len(codes)} codes from GitHub")

    codes = add_special_codes(codes)
    codes.sort(key=lambda x: x["code"])

    vocabulary = {
        "name": "ISO 3166-1 Country Codes",
        "namespace": "urn:iso:std:iso:3166-1",
        "version": "2020",
        "source_url": "https://www.iso.org/iso-3166-country-codes.html",
        "source_standard": "ISO 3166-1:2020",
        "last_updated": date.today().isoformat(),
        "domain": "core",
        "is_hierarchical": False,
        "codes": codes,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(vocabulary, f, indent=2, ensure_ascii=False)

    print(f"  Wrote {len(codes)} codes to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
