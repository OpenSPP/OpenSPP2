#!/usr/bin/env python3
"""Fetch ISO 4217 currency codes from official sources.

Sources:
- Primary: https://datahub.io/core/currency-codes (CC-BY licensed)
"""

import json
import sys
from datetime import date
from pathlib import Path

import requests

DATAHUB_URL = "https://datahub.io/core/currency-codes/r/codes-all.json"

OUTPUT_FILE = Path(__file__).parent.parent / "vocabularies" / "iso-4217-currency.json"


def fetch_currencies():
    """Fetch currency codes from DataHub.io."""
    response = requests.get(DATAHUB_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    # Use dict to deduplicate (same currency used in multiple countries)
    seen = {}
    for item in data:
        code = item.get("AlphabeticCode")
        if code and code not in seen:
            seen[code] = {"code": code, "display": item.get("Currency", "")}

    return list(seen.values())


def add_special_codes(codes):
    """Add special currency codes."""
    existing = {c["code"] for c in codes}

    special = [
        {
            "code": "XXX",
            "display": "No currency",
            "definition": "Used when no currency is involved",
        },
    ]

    for code in special:
        if code["code"] not in existing:
            codes.append(code)

    return codes


def main():
    """Main entry point."""
    print("Fetching ISO 4217 currency codes...")

    codes = fetch_currencies()
    print(f"  Fetched {len(codes)} codes from DataHub.io")

    codes = add_special_codes(codes)
    codes.sort(key=lambda x: x["code"])

    vocabulary = {
        "name": "ISO 4217 Currency Codes",
        "namespace": "urn:iso:std:iso:4217",
        "version": "2024",
        "source_url": "https://www.iso.org/iso-4217-currency-codes.html",
        "source_standard": "ISO 4217:2015",
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
