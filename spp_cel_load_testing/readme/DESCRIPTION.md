Performance testing and benchmarking framework for CEL expression evaluation. Provides test suites for parser, translator, executor, eligibility, and bulk evaluation performance. Includes database query analysis tools and CLI scripts for index optimization and benchmark execution.

### Key Capabilities

- Test framework with benchmarking utilities, query analysis, and test data generation using Faker
- Performance test suites for parser, translator, executor, eligibility, bulk operations, event data, and variable resolver
- Database index analysis via IndexAdvisor with missing index recommendations for CEL-relevant tables
- Query optimization via ExplainAnalyzer to identify sequential scans and performance bottlenecks
- CLI scripts for benchmark execution and database index analysis with table, JSON, and CSV output formats
- Expression templates organized by complexity: simple, medium, complex_exists, complex_count, complex_aggregate, event-based

### Key Models

This module defines no Odoo models. It provides Python test utilities (`PerformanceTestCase`), analysis tools (`QueryCapture`, `ExplainAnalyzer`, `IndexAdvisor`, `SlowQueryTracker`), and CLI scripts.

### Test Suites

| Suite               | Tests                                                       |
| ------------------- | ----------------------------------------------------------- |
| parser              | Expression parsing throughput and cache effectiveness       |
| translator          | CEL-to-SQL translation performance                          |
| executor            | Expression execution on registrant datasets                 |
| eligibility         | Program eligibility evaluation with domain compilation      |
| bulk                | Bulk evaluation performance at scale                        |
| event               | Event data query performance and temporal expressions       |
| variable_resolver   | Variable resolution performance and caching                 |
| studio_validation   | Studio logic validation and expression correctness          |

### Analysis Tools

| Tool                | Purpose                                              |
| ------------------- | ---------------------------------------------------- |
| `QueryCapture`      | Intercept and capture SQL queries for analysis       |
| `ExplainAnalyzer`   | Parse EXPLAIN ANALYZE output and identify issues     |
| `IndexAdvisor`      | Recommend missing database indexes for CEL queries   |
| `SlowQueryTracker`  | Track queries exceeding configurable time thresholds |

### Configuration

After installing:

1. Run benchmarks: `./scripts/run_benchmarks.py --db mydb --suite all`
2. Check index coverage: `./scripts/analyze_indexes.py --db mydb --check-existing`
3. Generate missing index DDL: `./scripts/analyze_indexes.py --db mydb --generate-ddl --output sql`
4. Customize registrant count: `./scripts/run_benchmarks.py --db mydb --suite all --registrants 5000`

### UI Location

No UI components. This module provides test suites executed via Odoo test runner or CLI scripts in the `scripts/` directory.

### Security

No security groups or access control. Tests run with the executing user's permissions.

### Extension Points

- Inherit `spp_cel_load_testing.tests.common.PerformanceTestCase` to create custom performance tests
- Add expression templates in `data/expression_templates.py` following the complexity categorization pattern
- Extend `IndexAdvisor.get_recommended_cel_indexes()` to add domain-specific index recommendations
- Override `ExplainAnalyzer` methods to customize query analysis rules

### Dependencies

`spp_cel_domain`, `spp_programs`

External Python dependencies: `faker`
