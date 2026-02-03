Reusable CEL (Common Expression Language) expression editor widget for Odoo forms. Provides a CodeMirror-based editor with syntax highlighting, autocompletion, live validation, and a symbol browser. Used by eligibility rules, program filters, entitlement formulas, and other modules that require expression editing.

### Key Capabilities

- **Syntax highlighting**: Keywords, operators, strings, and functions are color-coded for readability
- **Autocompletion**: Press Ctrl+Space to see available fields, functions, and operators for the current profile
- **Live validation**: Expressions are validated as you type, with inline error highlighting and match counts
- **Symbol browser**: Browse available fields, CEL variables, library expressions, and functions via a sidebar
- **Profile-based context**: Automatically loads symbols for registry individuals, groups, entitlements, memberships, or custom profiles
- **HTTP API**: JSONRPC endpoints for symbol retrieval and validation from frontend or external tools

### Key Models

| Model                     | Description                                                                      |
| ------------------------- | -------------------------------------------------------------------------------- |
| `spp.cel.symbol.provider` | Abstract model that extracts symbols for autocompletion and validates expressions |
| `spp.cel.widget.demo`     | Transient wizard for testing the widget (debug mode only)                        |

### Configuration

After installing, use the widget in any form view by adding `widget="cel_expression"` to a text or char field:

```xml
<field name="eligibility_expression"
       widget="cel_expression"
       options="{'cel_profile': 'registry_individuals'}"/>
```

Optional widget parameters:
- `cel_profile`: Profile name (default: `registry_individuals`)
- `profile_field`: Read profile from a field on the record
- `expression_type`: Expression type (filter, formula, scoring, validation, other)
- `expression_type_field`: Read expression type from a field
- `output_type`: Expected output type (boolean, number, string, money)
- `output_type_field`: Read output type from a field

### UI Location

- **Demo Wizard**: Settings > Technical > CEL Widget Demo (debug mode only)
- **Widget Usage**: Add to any form view with `widget="cel_expression"`

### Tabs in Demo Wizard

- **Dynamic Testing**: Test expressions with different profiles and see validation results
- **By Profile**: Test expressions for specific profiles (individuals, groups, entitlements)
- **Read-only Mode**: Verify the widget displays correctly in readonly mode
- **Help**: Keyboard shortcuts, features, and example expressions

### Security

| Group                | Model                   | Access                                          |
| -------------------- | ----------------------- | ----------------------------------------------- |
| Internal User        | HTTP endpoints          | Can call widget JSONRPC endpoints (auth="user") |
| Settings             | `spp.cel.widget.demo`   | Full CRUD (read, write, create, delete)         |
| Technical Features   | Menu visibility         | Can see demo menu in Settings > Technical       |

### HTTP Endpoints

All endpoints use JSONRPC authentication (`auth="user"`):

- **`/spp_cel/symbols/<profile>`**: Get symbols for a CEL profile (variables, functions, operators, keywords)
- **`/spp_cel/validate`**: Validate expression and return errors, warnings, match count
- **`/spp_cel/profiles`**: Get list of available CEL profiles with descriptions

### Extension Points

- Inherit `spp.cel.symbol.provider` and override `get_symbols_for_profile()` to add custom symbol sources
- Use the `CelEditor` JavaScript component standalone in client actions for custom editors
- Add custom profiles to `spp.cel.registry` for domain-specific contexts
- Customize the `_get_model_fields()` method to filter which fields appear in autocompletion
- Use HTTP endpoints from external tools or custom frontend components

### Dependencies

`web`, `spp_cel_domain`
