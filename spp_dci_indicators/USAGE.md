# DCI Indicators Module - Usage Guide

## Quick Start

### 1. Installation

Install the module and its dependencies:

```bash
# Install the module
odoo-bin -d your_database -i spp_dci_indicators --stop-after-init
```

The module will automatically install:

- spp_dci_client_dr
- spp_dci_client_crvs
- spp_dci_client_ibr
- spp_indicators
- spp_cel_domain

### 2. Configure DCI Data Sources

Before using DCI symbols, ensure DCI data sources are configured:

1. Go to **Settings → DCI Configuration**
2. Configure data sources for:
   - Disability Registry (DR)
   - Civil Registration (CRVS)
   - Integrated Beneficiary Registry (IBR)
3. Test connections to ensure they work

### 3. Sync DCI Data

DCI symbols read from cached data. Sync data before using in eligibility:

**Option A: Manual Sync**

```
Navigate to: Registry → Partners → Select Partner → DCI Tab → Sync Data
```

**Option B: Batch Sync**

```python
# Via scheduled action or script
partners = env['res.partner'].search([('is_registrant', '=', True)])
for partner in partners:
    # Sync DR data
    env['spp.dci.disability.status'].create({'partner_id': partner.id})
    # Sync CRVS data
    # ... (depends on your DCI client implementation)
```

### 4. Use in Program Eligibility

#### Example 1: Disability Program

**Eligibility Criteria:**

- Must be alive
- Must have severe mobility disability
- Must be 18 years or older
- Must not be enrolled in other programs

**CEL Expression:**

```python
crvs.is_alive == true and
dr.severity('Mobility') >= 3 and
age_years(me.birthdate) >= 18 and
ibr.has_duplicate == false
```

**Steps:**

1. Navigate to **Programs → Your Program → Eligibility Manager**
2. Select **"CEL Expression"** mode
3. Enter the expression above
4. Click **Test Expression** to validate
5. Click **Preview Beneficiaries** to see matches
6. Save and run enrollment

#### Example 2: Child Support Program

**Eligibility Criteria:**

- Birth must be verified in CRVS
- Child must be under 5 years old
- Parent must not be enrolled in similar programs

**CEL Expression:**

```python
crvs.birth_verified == true and
age_years(me.birthdate) < 5 and
ibr.is_enrolled('Child Grant') == false
```

#### Example 3: Complex Multi-Criteria

**Eligibility Criteria:**

- Must be alive
- Either has disability OR is elderly (60+)
- Birth verified OR has functional assessment
- No duplicates in other programs

**CEL Expression:**

```python
crvs.is_alive == true and
(dr.has_disability == true or age_years(me.birthdate) >= 60) and
(crvs.birth_verified == true or dr.assessed == true) and
ibr.has_duplicate == false
```

## DCI Symbol Reference

### dr (Disability Registry)

| Symbol              | Type | Description               | Example                      |
| ------------------- | ---- | ------------------------- | ---------------------------- |
| `dr.has_disability` | bool | Has any disability        | `dr.has_disability == true`  |
| `dr.types`          | list | List of disability types  | `'Vision' in dr.types`       |
| `dr.assessed`       | bool | Has functional assessment | `dr.assessed == true`        |
| `dr.severity(type)` | int  | Severity (1-4) for type   | `dr.severity('Vision') >= 3` |
| `dr.has_type(type)` | bool | Has specific disability   | `dr.has_type('Mobility')`    |

**Disability Types:**

- Vision
- Hearing
- Mobility
- Cognition
- SelfCare
- Communication

**Severity Levels:**

- 1: No difficulty
- 2: Some difficulty
- 3: A lot of difficulty
- 4: Cannot do

### crvs (Civil Registration)

| Symbol                 | Type | Description        | Example                       |
| ---------------------- | ---- | ------------------ | ----------------------------- |
| `crvs.is_alive`        | bool | No death event     | `crvs.is_alive == true`       |
| `crvs.birth_verified`  | bool | Birth registered   | `crvs.birth_verified == true` |
| `crvs.is_married`      | bool | Currently married  | `crvs.is_married == true`     |
| `crvs.has_event(type)` | bool | Has specific event | `crvs.has_event('birth')`     |

**Event Types:**

- birth
- death
- marriage
- divorce

### ibr (Integrated Beneficiary Registry)

| Symbol                  | Type     | Description           | Example                          |
| ----------------------- | -------- | --------------------- | -------------------------------- |
| `ibr.has_duplicate`     | bool     | Duplicates found      | `ibr.has_duplicate == false`     |
| `ibr.last_check_date`   | datetime | Last check date       | `ibr.last_check_date != None`    |
| `ibr.matched_programs`  | list     | Programs with matches | `len(ibr.matched_programs) == 0` |
| `ibr.is_enrolled(name)` | bool     | Enrolled in program   | `ibr.is_enrolled('Cash')`        |

## Common Patterns

### Pattern: Must be alive and verified

```python
crvs.is_alive == true and crvs.birth_verified == true
```

### Pattern: Disability-based eligibility

```python
# Any disability
dr.has_disability == true

# Severe disability only
dr.severity('Vision') >= 3 or dr.severity('Hearing') >= 3 or dr.severity('Mobility') >= 3

# Multiple disabilities
len(dr.types) >= 2
```

### Pattern: No duplicates in similar programs

```python
ibr.has_duplicate == false or len(ibr.matched_programs) == 0
```

### Pattern: Combining age and DCI data

```python
# Elderly OR disabled
age_years(me.birthdate) >= 60 or dr.has_disability == true

# Child with verified birth
age_years(me.birthdate) < 18 and crvs.birth_verified == true
```

## Troubleshooting

### Issue: DCI symbols not available

**Solution:**

1. Verify module is installed: `spp_dci_indicators`
2. Check dependencies are installed
3. Restart Odoo server
4. Clear CEL cache: Settings → CEL Configuration → Clear Cache

### Issue: DCI symbols return default values

**Possible causes:**

1. DCI data not synced for partner
2. DCI client modules not configured
3. Partner not linked to DCI records

**Solution:**

1. Navigate to partner record
2. Check DCI tab
3. Sync data from DCI sources
4. Verify records exist in:
   - Disability Status
   - CRVS Events
   - Duplication Checks

### Issue: Expression returns no matches

**Debug steps:**

1. Test expression in CEL builder
2. Check error messages
3. Verify DCI data exists
4. Simplify expression to isolate issue:
   ```python
   # Test each part separately
   dr.has_disability == true  # Works?
   crvs.is_alive == true      # Works?
   ibr.has_duplicate == false # Works?
   ```

### Issue: Performance slow with DCI symbols

**Optimization:**

1. DCI symbols use lazy loading (already optimized)
2. Ensure database indexes exist on:
   - `spp.dci.disability.status.partner_id`
   - `spp.dci.crvs.event.person_id`
   - `spp.dci.duplication.check.partner_id`
3. Run eligibility checks in batch mode
4. Consider caching results in indicators

## Advanced Usage

### Custom DCI Functions

You can extend DCI symbols by adding custom functions to the CEL registry:

```python
# In your custom module
def custom_dci_check(env, partner):
    # Your custom logic
    return True

# Register function
env['spp.cel.function.registry'].register('my_dci_check', custom_dci_check)

# Use in CEL
my_dci_check(me) == true
```

### Batch DCI Data Sync

For large-scale operations, sync DCI data in batches:

```python
# Via scheduled action
partners = env['res.partner'].search([
    ('is_registrant', '=', True),
    ('disabled', '=', False)
])

# Sync in chunks
chunk_size = 100
for i in range(0, len(partners), chunk_size):
    chunk = partners[i:i+chunk_size]
    # Sync DR data
    for partner in chunk:
        env['spp.dci.disability.status'].sudo().create({
            'partner_id': partner.id,
            'state': 'draft'
        }).refresh_from_dr()
    env.cr.commit()  # Commit after each chunk
```

### Monitoring DCI Data Quality

Check data quality before running eligibility:

```python
# Partners with DCI data
total_partners = env['res.partner'].search_count([('is_registrant', '=', True)])
with_dr = env['spp.dci.disability.status'].search_count([('state', '=', 'active')])
with_crvs = env['spp.dci.crvs.event'].search_count([('state', '=', 'processed')])
with_ibr = env['spp.dci.duplication.check'].search_count([('state', '=', 'completed')])

print(f"DR coverage: {with_dr}/{total_partners} ({with_dr*100/total_partners:.1f}%)")
print(f"CRVS coverage: {with_crvs}/{total_partners} ({with_crvs*100/total_partners:.1f}%)")
print(f"IBR coverage: {with_ibr}/{total_partners} ({with_ibr*100/total_partners:.1f}%)")
```

## Support

For issues or questions:

- GitHub: https://github.com/OpenSPP/openspp-modules
- Documentation: https://docs.openspp.org
- Community: https://openspp.org/community
