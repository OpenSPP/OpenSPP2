# CEL Widget Tests - Quick Reference

## Running Tests

### All Tests (Unit + HTTP + E2E)

```bash
# From project root
./scripts/test_single_module.sh spp_cel_widget
```

### Unit Tests Only

```bash
# Run specific test class
./scripts/test_single_module.sh spp_cel_widget --test-tags=TestCelSymbolProvider

# Run specific test method
./scripts/test_single_module.sh spp_cel_widget --test-tags=TestCelSymbolProvider.test_get_symbols_individuals_profile
```

### HTTP Controller Tests

```bash
./scripts/test_single_module.sh spp_cel_widget --test-tags=TestCelWidgetController
```

### E2E Tour Tests

```bash
# Run all tours
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget

# Run specific tour
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_basic_rendering
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_autocomplete
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_validation_success
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_validation_error
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_symbol_browser
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_symbol_search
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_manual_autocomplete
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_readonly
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_empty_validation
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_complex_expression
```

### With Screenshots (for debugging tour failures)

```bash
./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget --screenshots
```

## Test Files

### Python Tests (Backend)

1. **tests/test_symbol_provider.py** - Symbol provider unit tests
   - Profile retrieval
   - Symbol structure validation
   - Expression validation
   - Function and operator metadata

2. **tests/test_controller.py** - HTTP endpoint tests
   - Authentication
   - JSON endpoints
   - Error handling
   - Response format validation

### JavaScript Tests (Frontend)

3. **static/tests/tours/cel_widget_tour.js** - E2E tour tests
   - Widget rendering
   - User interactions
   - Autocomplete
   - Validation feedback
   - Symbol browser
   - Search functionality

## Test Coverage

### Current Coverage

| Component                 | Coverage | Status    |
| ------------------------- | -------- | --------- |
| Symbol Provider (Backend) | 85%      | Good      |
| HTTP Controller           | 60%      | Fair      |
| Widget UI (E2E)           | 90%      | Excellent |
| **Overall**               | **78%**  | **Good**  |

### Coverage Gaps

See `TEST_RECOMMENDATIONS.md` for detailed analysis of:

- Missing edge cases
- Negative test cases needed
- Integration test opportunities
- Performance test suggestions

## Continuous Integration

Tests are automatically run on:

- Pull requests
- Commits to main branches
- Nightly builds

View test results in CI pipeline logs.

## Debugging Failed Tests

### Tour Test Failures

1. **Enable screenshots:**

   ```bash
   ./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_basic_rendering --screenshots
   ```

2. **Check screenshots in:** `/tmp/openspp-odoo19-test-logs/screenshots/`

3. **Enable verbose logging:**
   ```bash
   ./scripts/test_single_module.sh spp_cel_widget --test-tags=/cel_widget_basic_rendering --log-level=debug
   ```

### Unit Test Failures

1. **Run with verbose output:**

   ```bash
   ./scripts/test_single_module.sh spp_cel_widget --log-level=test
   ```

2. **Use Python debugger:** Add `import pdb; pdb.set_trace()` in test code

3. **Check test logs:** `/tmp/openspp-odoo19-test-logs/test_spp_cel_widget.log`

## Writing New Tests

### Unit Test Template

```python
from odoo.tests.common import TransactionCase

class TestYourFeature(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["spp.cel.symbol.provider"]

    def test_your_feature(self):
        """Clear description of what this tests."""
        # Arrange
        # Act
        # Assert
        self.assertEqual(actual, expected)
```

### HTTP Test Template

```python
import json
from odoo.tests.common import HttpCase

class TestYourEndpoint(HttpCase):
    def test_endpoint(self):
        """Clear description of endpoint test."""
        self.authenticate("admin", "admin")

        response = self.url_open(
            "/your/endpoint",
            data=json.dumps({"params": {}}),
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Assertions
```

### Tour Test Template

```javascript
registry.category("web_tour.tours").add("your_tour_name", {
  test: true,
  url: "/web",
  steps: () => [
    stepUtils.showAppsMenuItem(),
    {
      content: "Description of step",
      trigger: "css-selector",
      run: "click", // or "edit text"
    },
    {
      content: "Verify result",
      trigger: "selector-for-expected-element",
    },
  ],
});
```

## Best Practices

1. **Test names** - Use descriptive names: `test_validate_empty_expression`
2. **Documentation** - Add docstrings explaining what is tested
3. **Arrange-Act-Assert** - Structure tests clearly
4. **Independence** - Tests should not depend on each other
5. **Clean up** - Use `setUp`/`tearDown` or `@classmethod` methods
6. **Fast tests** - Keep unit tests fast (< 1s each)
7. **Realistic data** - Use realistic test data, not "test" everywhere
8. **Edge cases** - Test boundary conditions and error cases
9. **Coverage** - Aim for 85%+ coverage on core functionality
10. **No flaky tests** - Ensure tests pass consistently

## Performance Benchmarks

Expected test execution times:

- Unit tests: < 5 seconds total
- HTTP tests: < 10 seconds total
- E2E tours: < 2 minutes total
- **All tests: < 3 minutes**

If tests are slower, investigate:

- Database queries (use `self.assertQueryCount()`)
- External API calls (mock them)
- Large data sets (reduce test data size)
- Sleep/wait statements (minimize waits in tours)

## Getting Help

- **Test failures:** Check CI logs and screenshots
- **Writing tests:** See examples in existing test files
- **Test infrastructure:** See `/docs/principles/testing.md`
- **Odoo testing docs:**
  https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html
- **Tour testing:**
  https://www.odoo.com/documentation/19.0/developer/reference/frontend/javascript_reference.html#tours

## Related Documentation

- `TEST_RECOMMENDATIONS.md` - Comprehensive test review and gap analysis
- `/docs/principles/testing.md` - OpenSPP testing principles
- `CLAUDE.md` - Development guidelines
