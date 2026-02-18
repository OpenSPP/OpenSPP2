# OpenSPP HXL Area Integration

HXL import with area-level aggregation for humanitarian indicators.

## Overview

This module enables importing HXL-tagged field data and aggregating it to area-level
indicators for humanitarian coordination. It bridges individual-level observations to
area-level metrics used in humanitarian response coordination.

## Features

- **Multiple Matching Strategies**: Match HXL data to areas using P-codes, names, GPS
  coordinates, or fuzzy matching
- **Flexible Aggregation Rules**: Count, sum, average, min, max, distinct count, and
  percentage aggregations
- **Disaggregation Support**: Break down indicators by demographic attributes (gender,
  age, etc.)
- **Import Profiles**: Pre-configured templates for common data sources
- **Import Wizard**: User-friendly interface with data preview and validation
- **CEL Integration**: Sync indicators to `spp.data.value` for use in eligibility
  expressions
- **Queue Job Processing**: Background processing for large imports
- **Audit Trail**: Track import batches, results, and errors

## Architecture

- **Layer**: 2 (Capabilities)
- **Category**: OpenSPP/Integration
- **Dependencies**: `spp_hxl`, `spp_area`, `spp_cel_domain`, `queue_job`
- **External Dependencies**: `libhxl` (Python library for HXL data processing)

## Key Models

### `spp.hxl.import.profile`

Configuration for HXL data import:

- Area matching strategy (P-code, name, GPS, fuzzy)
- Area column HXL tag
- Target admin level
- Aggregation rules

### `spp.hxl.aggregation.rule`

Define how to aggregate data:

- Aggregation type (count, sum, avg, etc.)
- Source column HXL tag
- Filter expression
- Disaggregation attributes
- Target CEL variable

### `spp.hxl.import.batch`

Track individual import executions:

- Upload HXL file
- Auto-detect columns
- Process and aggregate
- View statistics and results

### `spp.hxl.area.indicator`

Aggregated indicator values:

- Area reference
- Variable reference
- Value and count
- Period key
- Disaggregation JSON
- Auto-sync to `spp.data.value`

## Pre-configured Profiles

### Sri Lanka Damage Assessment

- **Strategy**: Name matching
- **Level**: Admin Level 4 (GN Division)
- **Indicators**: Severely damaged households, partially damaged households, total
  affected

### Philippines Beneficiary Coverage

- **Strategy**: P-code matching
- **Level**: Admin Level 4 (Barangay)
- **Indicators**: Total beneficiaries (with gender/age disaggregation), beneficiary
  households

### OCHA 3W Import

- **Strategy**: P-code matching
- **Level**: Admin Level 2 (District)
- **Indicators**: People reached, number of organizations

### GPS Survey Import

- **Strategy**: GPS coordinates
- **Level**: Admin Level 3
- **Indicators**: Survey observations

## Usage

### Via Import Wizard

1. Navigate to **HXL Area > Import HXL Data**
2. Select an import profile
3. Upload HXL-tagged CSV/Excel file
4. Review data preview and area matching
5. Set period and context (optional incident)
6. Click **Import**

### Programmatically

```python
# Create import profile
profile = env['spp.hxl.import.profile'].create({
    'name': 'My Import',
    'code': 'my_import',
    'area_matching_strategy': 'pcode',
    'area_column_tag': '#adm2+pcode',
    'area_level': 2,
})

# Add aggregation rule
env['spp.hxl.aggregation.rule'].create({
    'profile_id': profile.id,
    'name': 'Count Records',
    'aggregation_type': 'count',
    'output_hxl_tag': '#meta+count',
})

# Create and process batch
batch = env['spp.hxl.import.batch'].create({
    'name': 'Import 2024-03',
    'profile_id': profile.id,
    'file_data': base64_encoded_file,
    'period_key': '2024-03',
})

batch.action_detect_columns()
batch.action_process()
```

## Area Matching Strategies

### P-code Matching (`pcode`)

- Exact match on `spp.area.code`
- Case-sensitive
- Most reliable for official administrative data

### Name Matching (`name`)

- Case-insensitive match on `spp.area.draft_name`
- Falls back to alternate names
- Good for data without P-codes

### GPS Matching (`gps`)

- Geographic coordinate lookup
- Requires latitude and longitude columns
- Note: Full implementation requires PostGIS

### Fuzzy Matching (`fuzzy`)

- Normalized name matching
- Removes common suffixes (District, Municipality, etc.)
- Partial matching with wildcards
- Good for inconsistent naming

## Aggregation Types

- **count**: Count number of records
- **sum**: Sum numeric values
- **avg**: Average numeric values
- **min**: Minimum value
- **max**: Maximum value
- **count_distinct**: Count unique values
- **percentage**: Percentage of total (filtered/total \* 100)

## Filter Expressions

Filter rows before aggregation using Python expressions:

```python
# Filter by severity
row.get('#impact+type') == 'severe'

# Multiple conditions
row.get('#status') == 'active' and int(row.get('#value', 0)) > 100

# List membership
row.get('#category') in ['food', 'shelter', 'health']
```

**Warning**: Uses `eval()` - in production, implement safe expression evaluator.

## Disaggregation

Break down indicators by HXL attributes:

```python
# In aggregation rule
disaggregate_by_tags = '+f,+m,+children,+elderly'

# Results in JSON
{
    '+f': 120,
    '+m': 130,
    '+children': 50,
    '+elderly': 30
}
```

## CEL Integration

Indicators are automatically synced to `spp.data.value` for use in CEL expressions:

```python
# Access in eligibility criteria
area.affected_households > 100

# Access historical data
area.beneficiaries['2024-03'] > 50
```

## Testing

Run tests:

```bash
# All tests
./scripts/test_single_module.sh spp_hxl_area

# Specific test
pytest spp_hxl_area/tests/test_area_matcher.py -v
```

Test coverage targets:

- Core functionality: 85%+
- Service classes: 90%+
- Models: 80%+

## Performance Considerations

- **Batch Size**: Process 500 rows at a time
- **Caching**: Area matcher caches lookups during import
- **Background Jobs**: Large imports run via queue_job
- **Bulk Operations**: Uses bulk SQL upsert for data values

## Security

- **Manager Role**: Full access to profiles and configuration
- **User Role**: Can create and view import batches
- **Filter Expressions**: Be cautious with eval() - consider implementing safe evaluator

## Known Limitations

1. **GPS Matching**: Simplified implementation - full version requires PostGIS
2. **Filter Expressions**: Uses eval() - security risk if user-provided
3. **HXL Detection**: Assumes standard HXL format (hashtags in row 2)
4. **Large Files**: Very large files (>10MB) may require chunking

## Troubleshooting

### Import fails with "No HXL hashtags detected"

- Verify file has HXL hashtag row (usually row 2)
- Check that hashtags start with `#`
- Ensure at least 50% of columns have hashtags

### Many unmatched areas

- Check area matching strategy matches your data
- Verify area codes/names in database match file
- Try fuzzy matching for name inconsistencies
- Check admin level filter

### Indicators not appearing in CEL

- Verify variable linked in aggregation rule
- Check that indicator has variable_id set
- Manually trigger sync: `indicator.sync_to_data_value()`

### Import stuck in processing

- Check queue job status
- Review error logs in batch form
- Check server logs for exceptions

## Contributing

Follow OpenSPP development guidelines:

- PEP8 code style
- 85%+ test coverage
- No `print()` statements - use `_logger`
- No bare `except:` - catch specific exceptions
- Document complex logic

## License

LGPL-3

## Authors

OpenSPP.org

## Links

- [HXL Standard](https://hxlstandard.org/)
- [libhxl Documentation](https://github.com/HXLStandard/libhxl-python)
- [OpenSPP Documentation](https://docs.openspp.org/)
