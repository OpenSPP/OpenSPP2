# Integration Tests for spp_analytics

## Overview

The integration tests in `test_integration_demo.py` use realistic demo data from
`spp_mis_demo_v2` to thoroughly test the aggregation service with real-world scenarios.

## Test Coverage

The integration tests cover:

1. **Area-based aggregation** with hierarchical areas (Philippines demo data)
2. **Multi-dimensional breakdowns** (2D and 3D: gender × area × disability)
3. **K-anonymity suppression** with realistic demographic distributions
4. **Cache behavior** with repeated queries
5. **Performance testing** with larger datasets (50+ groups with members)
6. **Privacy scenarios**:
   - Differencing attack prevention
   - Complementary suppression across dimensions
7. **Spatial aggregation** using GPS coordinates
8. **Age group dimensions** with realistic birth dates
9. **Program enrollment** correlation with demographics

## Running Integration Tests

### Option 1: Run with spp_mis_demo_v2 (Full Integration)

To run the full integration tests with realistic demo data:

```bash
# Test both modules together
./scripts/test_single_module.sh spp_analytics,spp_mis_demo_v2
```

This will:

- Install both `spp_analytics` and `spp_mis_demo_v2`
- Generate ~50 household groups with members (realistic demographics)
- Run all aggregation tests including the 15+ integration test scenarios

**Note:** This takes longer (~3-5 minutes) due to demo data generation.

### Option 2: Run without Demo Module (Unit Tests Only)

To run just the unit tests without demo data:

```bash
# Test aggregation module only
./scripts/test_single_module.sh spp_analytics
```

This will:

- Install only `spp_analytics` with minimal dependencies
- Run all unit tests (85+ tests)
- Skip integration tests that require demo data

The integration tests will be automatically skipped with message:

```
spp_mis_demo_v2 module not installed - integration tests skipped
```

## Demo Data Generated

When running with `spp_mis_demo_v2`, the following data is created:

- **Registrants**: 50 household groups + 150-250 individual members
- **Areas**: Full Philippines hierarchy (country → region → province → municipality)
- **Demographics**:
  - Gender: Realistic male/female distribution
  - Ages: Children (<18), adults (18-59), elderly (60+)
  - Disability: ~5% of population (realistic rate)
  - Income: Varied distribution (70% low, 25% moderate, 5% higher)
- **Geographic**: GPS coordinates for spatial queries
- **Programs**: Multiple demo programs with enrollments

## Test Scenarios

### K-Anonymity Testing

Tests verify that with k=5 or k=10 thresholds:

- Small cells (count < k) are suppressed
- Complementary suppression prevents differencing attacks
- Users with aggregate-only access cannot identify individuals

### Performance Testing

Tests measure aggregation performance with:

- 50+ household groups
- 2D breakdowns (gender × age_group)
- Full area hierarchies
- Expected completion: < 10 seconds

### Multi-Dimensional Breakdowns

Tests verify correct breakdown structure:

- 2D: gender × area
- 3D: gender × disability × area (max dimensions)
- Proper dimension ordering and metadata
- Cell counts sum to total

### Privacy Scenarios

Tests verify protection against:

- **Differencing attacks**: Complementary suppression when one cell is small
- **Single-cell isolation**: Multiple suppressions to prevent math-based identification
- **Cross-dimension differencing**: Protection across multiple dimensions

## CI/CD Integration

In CI pipelines, use the unit-only approach for faster feedback:

```yaml
# .gitlab-ci.yml or .github/workflows
test-aggregation:
  script:
    - ./scripts/test_single_module.sh spp_analytics
```

For comprehensive integration testing (nightly builds):

```yaml
test-aggregation-integration:
  script:
    - ./scripts/test_single_module.sh spp_analytics,spp_mis_demo_v2
  only:
    - schedules
```

## Debugging Integration Tests

If integration tests fail:

1. **Check demo data generation**:

   ```python
   # In test output, look for:
   "Test setup complete: X registrants, Y areas"
   ```

2. **Verify area hierarchy**:

   ```python
   # Should see: country → region → province → municipality
   "X regions, Y provinces, Z municipalities"
   ```

3. **Check demographic distribution**:

   ```python
   # Should have varied gender, age, disability
   "Age groups found in demo data: {child, adult, elderly}"
   ```

4. **Review suppression patterns**:
   ```python
   # In k-anonymity tests, should see:
   "K-anonymity test: X visible cells, Y suppressed cells"
   ```

## Test Data Consistency

The demo generator creates consistent, reproducible data:

- **Deterministic names**: Uses Faker with controlled randomness
- **Realistic distributions**: 70% low income, ~5% disability
- **Area assignment**: All registrants assigned to geographic areas
- **Complete demographics**: Gender, birth date, area, income

## Future Enhancements

Planned improvements for integration tests:

- [ ] Test with larger datasets (1000+ registrants)
- [ ] Benchmark queries for performance regression detection
- [ ] Test with multiple programs and enrollments
- [ ] CEL expression evaluation in breakdowns
- [ ] Statistics computation (not just counts)
- [ ] Fairness analysis with demo data

## Troubleshooting

### "Module spp_mis_demo_v2 not installed"

This is expected when running `./scripts/test_single_module.sh spp_analytics` alone.
To run integration tests, use:

```bash
./scripts/test_single_module.sh spp_analytics,spp_mis_demo_v2
```

### "No areas found in demo data"

The demo generator may have failed. Check logs for:

- Geographic data loading errors
- Philippines area data availability

### "Performance test timeout"

If aggregation takes > 10s:

- Check database indices on `res.partner.area_id`
- Review `spp.analytics.cache` configuration
- Ensure PostgreSQL has sufficient resources

## Related Documentation

- `spp_analytics/README.md` - Module overview and architecture
- `spp_mis_demo_v2/README.md` - Demo data generator documentation
- `docs/principles/privacy-protection.md` - K-anonymity principles
- `docs/principles/performance-scalability.md` - Performance guidelines
