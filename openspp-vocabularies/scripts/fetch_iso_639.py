#!/usr/bin/env python3
"""Fetch ISO 639-1 language codes from official sources.

Sources:
- Primary: https://datahub.io/core/language-codes (CC-BY licensed)
"""

import json
import sys
from datetime import date
from pathlib import Path

import requests

DATAHUB_URL = "https://datahub.io/core/language-codes/r/language-codes.json"

OUTPUT_FILE = Path(__file__).parent.parent / "vocabularies" / "iso-639-1-language.json"


def fetch_languages():
    """Fetch language codes from DataHub.io."""
    response = requests.get(DATAHUB_URL, timeout=30)
    response.raise_for_status()
    data = response.json()

    codes = []
    for item in data:
        # Filter to only ISO 639-1 codes (2 characters)
        code = item.get("alpha2")
        if code and len(code) == 2:
            codes.append({"code": code.lower(), "display": item.get("English", item.get("name", ""))})
    return codes


def add_special_codes(codes):
    """Add special language codes."""
    existing = {c["code"] for c in codes}

    special = [
        {"code": "sgn", "display": "Sign Languages", "definition": "ISO 639-3 macrolanguage for sign languages"},
        {"code": "und", "display": "Undetermined", "definition": "Used when language cannot be determined"},
        {"code": "zxx", "display": "No linguistic content", "definition": "Used for non-linguistic content"},
    ]

    for code in special:
        if code["code"] not in existing:
            codes.append(code)

    return codes


def main():
    """Main entry point."""
    print("Fetching ISO 639-1 language codes...")

    codes = fetch_languages()
    print(f"  Fetched {len(codes)} codes from DataHub.io")

    codes = add_special_codes(codes)
    codes.sort(key=lambda x: x["code"])

    vocabulary = {
        "name": "ISO 639-1 Language Codes",
        "namespace": "urn:iso:std:iso:639-1",
        "version": "2023",
        "source_url": "https://www.iso.org/iso-639-language-codes.html",
        "source_standard": "ISO 639-1:2002",
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
