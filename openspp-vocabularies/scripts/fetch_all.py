#!/usr/bin/env python3
"""Fetch all vocabulary data from official sources."""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent

# Scripts to run in order
FETCH_SCRIPTS = [
    "fetch_iso_3166.py",
    "fetch_iso_639.py",
    "fetch_iso_4217.py",
]


def main():
    """Main entry point."""
    print("=" * 60)
    print("Fetching all vocabulary data from official sources")
    print("=" * 60)
    print()

    failed = []
    for script in FETCH_SCRIPTS:
        script_path = SCRIPTS_DIR / script
        if not script_path.exists():
            print(f"Script not found: {script}")
            continue

        print(f"Running {script}...")
        result = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)

        if result.returncode != 0:
            print("  FAILED!")
            if result.stderr:
                print(f"  Error: {result.stderr}")
            failed.append(script)
        else:
            print(result.stdout)

    print()
    print("=" * 60)
    if failed:
        print(f"FAILED: {len(failed)} script(s) failed: {', '.join(failed)}")
        return 1

    print("SUCCESS: All vocabularies updated")

    # Run validation
    print()
    print("Running validation...")
    result = subprocess.run([sys.executable, str(SCRIPTS_DIR / "validate.py")])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
