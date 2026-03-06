# HXL Area Import - Quick Start Guide

## 5-Minute Setup

### Step 1: Install Module

```bash
# Install with dependencies
odoo -d your_database -i spp_hxl_area
```

### Step 2: Prepare Your Data

Your HXL file should look like:

```csv
Area Name,Affected People,Severity
#adm2+name,#affected+ind,#impact+type
District A,100,severe
District B,50,minor
District C,200,severe
```

Key requirements:

- Row 1: Human-readable headers
- Row 2: HXL hashtags (starting with `#`)
- Rows 3+: Data

### Step 3: Import Data

1. Navigate to: **HXL Area > Import HXL Data**
2. Select profile: **"Sri Lanka Damage Assessment"** (or create custom)
3. Upload your CSV/Excel file
4. Review preview
5. Click **Import**

### Step 4: View Results

Navigate to: **HXL Area > Area Indicators**

Your data is now aggregated by area and ready to use!

## Common Use Cases

### Use Case 1: Damage Assessment

**Data**: GPS coordinates of damaged houses

**Profile Configuration**:

- Strategy: GPS
- Level: Admin 3
- Aggregation: Count by severity

**Result**: Map showing number of damaged houses per area

### Use Case 2: Beneficiary Tracking

**Data**: List of beneficiaries with household IDs

**Profile Configuration**:

- Strategy: P-code
- Level: Admin 4
- Aggregation: Count individuals, count distinct households

**Result**: Coverage statistics per barangay/village

### Use Case 3: Multi-Organization Response

**Data**: 3W data (Who does What Where)

**Profile Configuration**:

- Strategy: P-code
- Level: Admin 2
- Aggregation: Sum beneficiaries, count distinct organizations

**Result**: Coordination dashboard per district

## Creating Custom Profiles

### Basic Profile

```python
profile = env['spp.hxl.import.profile'].create({
    'name': 'My Custom Import',
    'code': 'my_import',
    'area_matching_strategy': 'pcode',  # or 'name', 'gps', 'fuzzy'
    'area_column_tag': '#adm2+pcode',   # HXL tag for area column
    'area_level': 2,                     # Admin level (1=Province, 2=District, etc.)
})
```

### Add Aggregation Rules

```python
# Count all records
env['spp.hxl.aggregation.rule'].create({
    'profile_id': profile.id,
    'name': 'Total Records',
    'aggregation_type': 'count',
    'output_hxl_tag': '#meta+count',
})

# Sum numeric values
env['spp.hxl.aggregation.rule'].create({
    'profile_id': profile.id,
    'name': 'Total Affected',
    'aggregation_type': 'sum',
    'source_column_tag': '#affected+ind',
    'output_hxl_tag': '#affected+ind+total',
})

# Count with filter
env['spp.hxl.aggregation.rule'].create({
    'profile_id': profile.id,
    'name': 'Severe Cases',
    'aggregation_type': 'count',
    'filter_expression': "row.get('#severity') == 'severe'",
    'output_hxl_tag': '#affected+severe',
})
```

## Matching Strategies Cheat Sheet

| Strategy  | Use When                  | Pros                       | Cons                     |
| --------- | ------------------------- | -------------------------- | ------------------------ |
| **pcode** | You have official P-codes | Most reliable, exact match | Requires P-codes in data |
| **name**  | Names are consistent      | Simple, case-insensitive   | Spelling variations fail |
| **fuzzy** | Names vary slightly       | Handles variations         | May match incorrectly    |
| **gps**   | You have coordinates      | Works without admin data   | Requires PostGIS setup   |

## HXL Tags Reference

Common tags for humanitarian data:

| Tag             | Meaning              | Example                |
| --------------- | -------------------- | ---------------------- |
| `#adm1+pcode`   | Province P-code      | PH-01                  |
| `#adm2+pcode`   | District P-code      | PH-01-02               |
| `#adm3+name`    | Municipality name    | Quezon City            |
| `#affected+ind` | Affected individuals | 1234                   |
| `#affected+hh`  | Affected households  | 256                    |
| `#reached+ind`  | Reached individuals  | 890                    |
| `#org+name`     | Organization name    | Red Cross              |
| `#sector`       | Sector               | Food, Health, Shelter  |
| `#impact+type`  | Damage severity      | severe, partial, minor |
| `#geo+lat`      | Latitude             | 14.5995                |
| `#geo+lon`      | Longitude            | 120.9842               |

Gender/age disaggregation:

- `+f` = Female
- `+m` = Male
- `+children` = Children
- `+elderly` = Elderly
- `+i` = Infants
- `+adult` = Adults

## Troubleshooting

### Problem: "No HXL hashtags detected"

**Solution**: Check your file format:

```csv
Header Row              ← Row 1
#hxl+tags               ← Row 2 (hashtags)
data                    ← Row 3+
```

### Problem: "All areas unmatched"

**Solutions**:

1. Check area codes in database: `SELECT code FROM spp_area WHERE level = 2`
2. Try different matching strategy (pcode → name → fuzzy)
3. Check admin level matches your data
4. View unmatched values in import wizard

### Problem: "Import stuck in processing"

**Solutions**:

1. Check queue jobs: **Settings > Technical > Queue Jobs**
2. Check server logs: `tail -f /var/log/odoo/odoo.log`
3. Verify file size is reasonable (<10MB)

### Problem: "Indicators not in CEL"

**Solutions**:

1. Link variable in aggregation rule
2. Check variable exists: **HXL > Configuration > Variables**
3. Manually sync: Select indicator → **Sync to Data Values**

## Performance Tips

- **Small files (<1MB)**: Process immediately
- **Medium files (1-10MB)**: Use wizard (background processing)
- **Large files (>10MB)**: Split into smaller batches
- **Caching**: Matcher caches area lookups automatically
- **Bulk operations**: Uses efficient SQL upserts

## Next Steps

1. **Explore demo profiles**: Check pre-configured examples
2. **Create custom profiles**: Tailor to your data sources
3. **Integrate with CEL**: Use indicators in eligibility criteria
4. **Automate imports**: Schedule regular data updates
5. **Build dashboards**: Visualize area-level metrics

## Support

- Documentation: https://docs.openspp.org/
- HXL Standard: https://hxlstandard.org/
- Issues: https://github.com/OpenSPP/openspp-modules/issues

## Quick Links

- Import Wizard: HXL Area > Import HXL Data
- Profiles: HXL Area > Configuration > Import Profiles
- Batches: HXL Area > Import Batches
- Indicators: HXL Area > Area Indicators
