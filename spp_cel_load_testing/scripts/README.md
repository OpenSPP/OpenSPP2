# CEL Load Testing Scripts

Standalone CLI scripts for analyzing and optimizing CEL expression performance.

## analyze_indexes.py

Database index analysis tool for CEL query performance optimization.

### Features

- **Check Existing Indexes**: Report current index coverage for CEL-relevant tables
- **Generate DDL**: Output CREATE INDEX CONCURRENTLY statements for missing indexes
- **Multiple Output Formats**: Table (ASCII), SQL (DDL), or JSON
- **Export to File**: Save results for documentation or automation

### Installation

Install required dependency:

```bash
pip install psycopg2-binary
```

### Usage

#### Basic Usage

Check existing index coverage:

```bash
./analyze_indexes.py --db openspp_db --check-existing
```

Generate CREATE INDEX DDL:

```bash
./analyze_indexes.py --db openspp_db --generate-ddl --output sql
```

#### Output Formats

**Table format** (default) - ASCII table with status icons:

```bash
./analyze_indexes.py --db openspp_db --check-existing --output table
```

**SQL format** - Ready-to-run DDL statements:

```bash
./analyze_indexes.py --db openspp_db --check-existing --output sql
```

**JSON format** - Machine-readable for automation:

```bash
./analyze_indexes.py --db openspp_db --check-existing --output json
```

#### Export to File

```bash
# Export coverage report to JSON
./analyze_indexes.py --db openspp_db --check-existing \
  --output json --output-file coverage.json

# Generate DDL file
./analyze_indexes.py --db openspp_db --generate-ddl \
  --output sql --output-file indexes.sql

# Apply the generated indexes
psql openspp_db < indexes.sql
```

#### Database Connection

Use environment variables or command-line arguments:

```bash
# Using environment variables
export PGHOST=localhost
export PGPORT=5432
export PGUSER=odoo
export PGPASSWORD=odoo

./analyze_indexes.py --db openspp_db --check-existing

# Using command-line arguments
./analyze_indexes.py --db openspp_db --host localhost \
  --port 5432 --user odoo --password odoo --check-existing
```

### Analyzed Tables

The script analyzes indexes for these CEL-relevant tables:

- `res_partner` - Registrant lookups and age calculations
- `spp_group_membership` - Household member queries
- `spp_program_membership` - Program enrollment checks
- `spp_entitlement` - Payment history queries
- `spp_grm_ticket` - Grievance checks
- `spp_indicator_value` - Indicator-based eligibility
- `spp_event_data` - Event-based conditions

### Recommended Indexes

The script checks for standard CEL performance indexes including:

- Registrant type filtering (`is_registrant`, `is_group`)
- Active status checks (`is_registrant`, `active`)
- Age-based eligibility (`birthdate`)
- Household membership lookups (`group`, `individual`)
- Program enrollment status (`partner_id`, `program_id`, `state`)
- Entitlement queries (`partner_id`, `cycle_id`, `state`)
- And more...

### Example Output

#### Table Format

```
================================================================================
DATABASE INDEX ANALYSIS FOR CEL PERFORMANCE
================================================================================

OVERALL COVERAGE:
  Total Recommended: 24
  Existing:          18
  Missing:           6
  Coverage:          75.0%

COVERAGE BY TABLE:
--------------------------------------------------------------------------------
Table                          Recommended     Missing         Coverage
--------------------------------------------------------------------------------
res_partner                    3               1               ⚠️  66.7%
spp_group_membership           3               0               ✅ 100.0%
spp_program_membership         3               2               ❌  33.3%
...
```

#### SQL Format

```sql
-- Database Index Recommendations for CEL Performance
-- Database: openspp_db
-- Total Missing Indexes: 6
-- Coverage: 75.0%

-- Filter active registrants in eligibility checks
CREATE INDEX CONCURRENTLY IF NOT EXISTS res_partner__is_registrant_active_idx
  ON res_partner (is_registrant, active);

-- Check program enrollment status
CREATE INDEX CONCURRENTLY IF NOT EXISTS spp_program_membership__partner_id_program_id_idx
  ON spp_program_membership (partner_id, program_id);
```

### Integration with Performance Testing

This script can be integrated into CI/CD pipelines:

```bash
# Check index coverage in CI
./analyze_indexes.py --db test_db --check-existing --output json > coverage.json

# Parse coverage percentage
coverage=$(jq -r '.coverage_pct' coverage.json)

# Fail if coverage is below threshold
if (( $(echo "$coverage < 80" | bc -l) )); then
  echo "Index coverage below 80%: $coverage%"
  exit 1
fi
```

### Troubleshooting

**Connection refused:**

- Verify database is running: `pg_isready -h localhost`
- Check connection parameters
- Ensure PostgreSQL is accepting connections

**Permission denied:**

- Ensure user has SELECT permissions on `pg_index`, `pg_class`, `pg_attribute`
- For DDL generation, user needs CREATE INDEX permissions

**Import errors:**

- Ensure script is run from the module directory
- Analysis modules must be importable from `../analysis/`

### Notes

- Uses `CREATE INDEX CONCURRENTLY` to avoid locking tables
- Analyzes existing indexes from `pg_index` catalog
- Recommendations based on common CEL query patterns
- Expression analysis mode requires Odoo environment (not yet implemented)

### See Also

- `/home/user/openspp-modules-v2/spp_cel_load_testing/analysis/index_advisor.py` - Index recommendation engine
- `/home/user/openspp-modules-v2/spp_cel_load_testing/analysis/explain_analyzer.py` - Query analysis
- `/home/user/openspp-modules-v2/spp_cel_load_testing/data/expression_templates.py` - Sample CEL expressions

---

## run_benchmarks.py

A comprehensive CLI benchmark runner that executes CEL performance tests and generates detailed reports.

### Features

- **Multiple test suites**: Run parser, translator, executor, eligibility, bulk evaluation, and event data tests
- **Flexible output formats**: Table (ASCII), JSON, and CSV
- **Detailed metrics**: Execution time, pass/fail status, performance regressions
- **Odoo integration**: Connects to real Odoo database for realistic testing
- **Comprehensive logging**: Verbose mode for debugging
- **Exit codes**: Standard exit codes for CI/CD integration

### Prerequisites

1. **Odoo installation**: Odoo must be in your PYTHONPATH or in a standard location
2. **Database setup**: Target database must have `spp_cel_load_testing` module installed
3. **Dependencies**: All required Python packages (faker, etc.) must be installed

### Installation

Make the script executable (if not already):

```bash
chmod +x run_benchmarks.py
```

### Usage

#### Basic Usage

Run all benchmark suites:

```bash
./run_benchmarks.py --db mydb --suite all
```

Run specific suite:

```bash
./run_benchmarks.py --db mydb --suite parser
```

#### Advanced Usage

Run multiple specific suites:

```bash
./run_benchmarks.py --db mydb --suite parser --suite translator --suite executor
```

Generate JSON output:

```bash
./run_benchmarks.py --db mydb --suite all --output json
```

Export results to CSV file:

```bash
./run_benchmarks.py --db mydb --suite all --output csv --output-file results.csv
```

Run with verbose logging:

```bash
./run_benchmarks.py --db mydb --suite all --verbose
```

### AI / CI Friendly Usage

For runs intended to be consumed by automation or AI tools:

```bash
./run_benchmarks.py \
  --db mydb \
  --suite all \
  --registrants 10000 \
  --output json \
  --output-file results_10k.json \
  --ai-friendly \
  --log-file cel_bench_10k.log
```

Then summarize:

```bash
./summarize_results.py results_10k.json
```

Run eligibility tests with custom registrant count:

```bash
./run_benchmarks.py --db mydb --suite eligibility --registrants 5000
```

### Command-Line Options

| Option               | Description                                                | Default |
| -------------------- | ---------------------------------------------------------- | ------- |
| `--db DB`            | Odoo database name (required)                              | -       |
| `--suite SUITE`      | Test suite to run (can be specified multiple times)        | -       |
| `--registrants N`    | Number of test registrants to generate                     | 1000    |
| `--output FORMAT`    | Output format: table, json, or csv                         | table   |
| `--output-file FILE` | Write benchmark report to file instead of stdout           | stdout  |
| `--log-file FILE`    | Write detailed logs (DEBUG/INFO) to this file              | -       |
| `--ai-friendly`      | Reduce console logs to essentials (warnings/errors)        | false   |
| `--verbose, -v`      | Enable verbose console logging (overrides `--ai-friendly`) | false   |

### Available Test Suites

| Suite         | Description                    | Tests                                                                |
| ------------- | ------------------------------ | -------------------------------------------------------------------- |
| `all`         | Run all test suites            | All tests below                                                      |
| `parser`      | CEL parser performance         | Simple/complex parsing, cache effectiveness, adversarial expressions |
| `translator`  | CEL translator performance     | Translation speed, caching, domain compilation                       |
| `executor`    | CEL executor performance       | Expression execution, bulk operations                                |
| `eligibility` | Program eligibility evaluation | Simple/complex criteria, domain preparation                          |
| `bulk`        | Bulk evaluation performance    | Large-scale batch processing                                         |
| `event`       | Event data query performance   | Event-based expressions, temporal queries                            |

### Output Formats

#### Table (ASCII)

Human-readable table format suitable for terminal display:

```
====================================================================================================
CEL PERFORMANCE BENCHMARK RESULTS
====================================================================================================

Test Name                                          Status     Time
----------------------------------------------------------------------------------------------------
parser.test_parse_simple_expressions_throughput    ✓ PASS     1.23s
parser.test_parse_complex_expressions_throughput   ✓ PASS     456.78ms
...

SUMMARY
----------------------------------------------------------------------------------------------------
Total Tests:     24
Passed:          23 (95.8%)
Failed:          1
Errors:          0
Total Time:      45.67s
====================================================================================================
```

#### JSON

Machine-readable format for programmatic analysis:

```json
{
  "summary": {
    "total_tests": 24,
    "passed": 23,
    "failed": 1,
    "errors": 0,
    "total_time": 45.67,
    "pass_rate": 95.8,
    "regressions": []
  },
  "results": [
    {
      "test_name": "parser.test_parse_simple_expressions_throughput",
      "status": "passed",
      "elapsed_time": 1.234,
      "error_message": null,
      "metrics": {},
      "warnings": []
    }
  ]
}
```

#### CSV

Spreadsheet-compatible format for analysis in Excel/Google Sheets:

```csv
Test Name,Status,Elapsed Time (s),Error Message
parser.test_parse_simple_expressions_throughput,passed,1.234000,
parser.test_parse_complex_expressions_throughput,passed,0.456780,
```

### Exit Codes

| Code | Meaning                                                      |
| ---- | ------------------------------------------------------------ |
| 0    | All tests passed successfully                                |
| 1    | Some tests failed or had errors                              |
| 2    | Configuration error (missing database, Odoo not found, etc.) |

### Integration with CI/CD

Use in CI/CD pipelines to catch performance regressions:

```bash
#!/bin/bash
# Example CI script

# Run benchmarks and save results
./run_benchmarks.py --db test_db --suite all --output json --output-file results.json

# Check exit code
if [ $? -ne 0 ]; then
    echo "Performance tests failed!"
    exit 1
fi

# Parse results and compare with baseline (example)
python compare_benchmarks.py results.json baseline.json
```

### Troubleshooting

#### "Cannot import Odoo"

Ensure Odoo is in your PYTHONPATH:

```bash
export PYTHONPATH=/path/to/odoo:$PYTHONPATH
./run_benchmarks.py --db mydb --suite all
```

#### "spp_cel_load_testing module is not installed"

Install the module in your target database:

```bash
odoo -d mydb -i spp_cel_load_testing --stop-after-init
```

#### Tests timing out

Some tests with large datasets may take time. Use `--verbose` to see progress:

```bash
./run_benchmarks.py --db mydb --suite all --verbose
```

### Recommended SLOs / Interpretation

The built-in thresholds in the tests target the following ballpark SLOs on typical hardware (per run of the suite):

- Parser / translator:
  - Multi-thousand expression parsing / translation in **≤ a few seconds**.
  - Individual operations usually complete in **sub-millisecond to low-ms**.
- Executor:
  - Simple expressions on up to **10k registrants**: **≪ 1s** end-to-end.
  - Complex nested expressions and EXISTS/COUNT patterns: **≤ a few seconds** on 10k registrants.
- Eligibility:
  - End-to-end eligibility checks on a 10k registrant dataset in **≤ a few seconds**, including domain preparation and
    execution.
- Bulk evaluation:
  - Compile + execute against 2.5k–10k registrants: **≤ a few seconds**.
  - Average time per expression in multi-expression tests: **≪ 200ms**.

If tests start failing, they will point to the specific area (parser, translator, executor, eligibility, bulk, or event
data) where the SLO is not met.

### Examples

#### Nightly Performance Testing

```bash
#!/bin/bash
# nightly-perf-test.sh

DATE=$(date +%Y%m%d)
OUTPUT_FILE="benchmark-results-${DATE}.json"

./run_benchmarks.py \
    --db production_replica \
    --suite all \
    --output json \
    --output-file "$OUTPUT_FILE"

# Upload to monitoring system
curl -X POST \
    -H "Content-Type: application/json" \
    -d "@${OUTPUT_FILE}" \
    https://monitoring.example.com/api/metrics
```

#### Quick Development Check

```bash
# Quick check before committing changes
./run_benchmarks.py --db dev --suite parser --suite translator
```

#### Performance Regression Detection

```bash
# Run tests and save baseline
./run_benchmarks.py --db mydb --suite all --output json --output-file baseline.json

# ... make code changes ...

# Run tests again and compare
./run_benchmarks.py --db mydb --suite all --output json --output-file current.json

# Compare results (implement comparison script as needed)
python -c "
import json
baseline = json.load(open('baseline.json'))
current = json.load(open('current.json'))
# Compare results and detect regressions...
"
```

---

## Contributing

When adding new benchmark scripts:

1. Follow OpenSPP naming conventions
2. Include comprehensive help text
3. Support multiple output formats
4. Use standard exit codes
5. Add examples to this README

## License

Part of OpenSPP. See LICENSE file for full copyright and licensing details.
