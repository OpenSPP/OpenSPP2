#!/usr/bin/env python3
"""Validate all vocabulary files against the JSON schema."""

import json
import sys
from collections import Counter
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("Error: jsonschema package required. Install with: pip install jsonschema")
    sys.exit(1)

SCHEMA_FILE = Path(__file__).parent.parent / "schema" / "vocabulary.schema.json"
VOCABULARIES_DIR = Path(__file__).parent.parent / "vocabularies"


def validate_vocabulary(vocab_file, schema):
    """Validate a single vocabulary file."""
    with open(vocab_file, encoding="utf-8") as f:
        data = json.load(f)

    try:
        jsonschema.validate(data, schema)
        return True, None
    except jsonschema.ValidationError as e:
        return False, str(e.message)


def check_duplicate_codes(vocab_file):
    """Check for duplicate codes in a vocabulary file."""
    with open(vocab_file, encoding="utf-8") as f:
        data = json.load(f)

    codes = [c["code"] for c in data.get("codes", [])]
    counts = Counter(codes)
    duplicates = [code for code, count in counts.items() if count > 1]

    if duplicates:
        return False, f"Duplicate codes: {set(duplicates)}"
    return True, None


def main():
    """Main entry point."""
    print("Validating vocabulary files...")
    print()

    # Load schema
    with open(SCHEMA_FILE, encoding="utf-8") as f:
        schema = json.load(f)

    # Find all vocabulary files
    vocab_files = list(VOCABULARIES_DIR.glob("*.json"))

    if not vocab_files:
        print("No vocabulary files found!")
        return 1

    errors = []
    for vocab_file in sorted(vocab_files):
        print(f"  {vocab_file.name}...")

        # Validate against schema
        valid, error = validate_vocabulary(vocab_file, schema)
        if not valid:
            errors.append((vocab_file.name, f"Schema: {error}"))
            print(f"    FAILED: {error}")
            continue

        # Check for duplicates
        valid, error = check_duplicate_codes(vocab_file)
        if not valid:
            errors.append((vocab_file.name, error))
            print(f"    FAILED: {error}")
            continue

        # Load and show stats
        with open(vocab_file, encoding="utf-8") as f:
            data = json.load(f)
        print(f"    OK ({len(data['codes'])} codes)")

    print()
    if errors:
        print(f"FAILED: {len(errors)} file(s) have errors")
        for filename, error in errors:
            print(f"  - {filename}: {error}")
        return 1

    print(f"SUCCESS: {len(vocab_files)} file(s) validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
