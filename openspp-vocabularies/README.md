# OpenSPP Vocabularies

[![Validate](https://github.com/OpenSPP/openspp-vocabularies/actions/workflows/validate.yml/badge.svg)](https://github.com/OpenSPP/openspp-vocabularies/actions/workflows/validate.yml)

Curated, standardized vocabulary data files for OpenSPP social protection platforms.

## Purpose

This repository provides authoritative vocabulary data in a consistent JSON format, sourced from international standards
(ISO, UN, ILO, etc.). It serves as the single source of truth for vocabulary synchronization in OpenSPP deployments.

## Structure

```
openspp-vocabularies/
├── vocabularies/           # JSON vocabulary files
│   ├── iso-3166-1-country.json
│   ├── iso-639-1-language.json
│   └── ...
├── scripts/                # Fetch/update scripts
│   ├── fetch_iso_3166.py
│   └── ...
├── schema/                 # JSON Schema for validation
│   └── vocabulary.schema.json
└── CHANGELOG.md
```

## Vocabulary Format

All vocabularies follow a standard JSON schema:

```json
{
  "name": "ISO 3166-1 Country Codes",
  "namespace": "urn:iso:std:iso:3166-1",
  "version": "2024",
  "source_url": "https://www.iso.org/iso-3166-country-codes.html",
  "source_standard": "ISO 3166-1:2020",
  "last_updated": "2024-01-15",
  "domain": "core",
  "codes": [
    {
      "code": "AF",
      "display": "Afghanistan"
    }
  ]
}
```

## Available Vocabularies

| File                               | Standard   | Codes | Description                          |
| ---------------------------------- | ---------- | ----- | ------------------------------------ |
| `iso-3166-1-country.json`          | ISO 3166-1 | 252   | Country codes (alpha-2)              |
| `iso-639-1-language.json`          | ISO 639-1  | 186   | Language codes                       |
| `iso-4217-currency.json`           | ISO 4217   | 179   | Currency codes                       |
| `iso-5218-gender.json`             | ISO 5218   | 4     | Gender codes                         |
| `isced-2011-education.json`        | ISCED 2011 | 10    | Education levels                     |
| `isco-08-occupation.json`          | ISCO-08    | 10    | Occupation categories (major groups) |
| `un-marital-status.json`           | UN         | 6     | Marital status                       |
| `washington-group-disability.json` | WG-SS      | 24    | Disability assessment                |
| `religion.json`                    | UN Census  | 10    | Religious affiliation                |

## Updating Vocabularies

Scripts in `scripts/` can fetch updates from official sources:

```bash
# Update a specific vocabulary
python scripts/fetch_iso_3166.py

# Update all vocabularies
python scripts/fetch_all.py
```

## Usage in OpenSPP

The `spp_vocabulary_sync` module fetches from this repository:

```
https://raw.githubusercontent.com/OpenSPP/openspp-vocabularies/main/vocabularies/
```

## CI/CD

### Automated Validation

All pull requests and pushes to `main` are automatically validated:

- JSON schema validation
- Duplicate code detection
- JSON syntax verification

### Automated Updates

A scheduled workflow runs monthly to:

1. Fetch latest data from official sources (DataHub.io, GitHub)
2. Compare with current vocabularies
3. Create a PR if changes are detected

You can also trigger updates manually via the Actions tab.

### Releases

Tag a version (e.g., `v1.0.0`) to create a GitHub release with vocabulary statistics.

## Contributing

1. Fork this repository
2. Run the appropriate fetch script or manually update
3. Validate against schema: `python scripts/validate.py`
4. Submit a pull request with changelog entry

## License

Data sourced from international standards organizations. See individual vocabulary files for source attribution.
