Translates CEL-like expressions into Odoo domains for filtering records. Defines reusable variables (field mappings, constants, aggregations, external sources), writes business rules in CEL syntax, and compiles them to executable Odoo queries. Supports variable resolution, external data providers, and cached values with TTL-based expiration.

### Key Capabilities

- Define variables mapping to model fields, constants, computed values, member aggregations, or external APIs
- Write filter and formula expressions using CEL syntax with variable references
- Resolve variable references into expanded CEL expressions before compilation
- Configure external data providers with authentication, TTL, and ID mapping for API-based data sources
- Cache computed and external variable values with TTL-based expiration and manual invalidation
- Support historical data queries with configurable period granularity (daily, monthly, quarterly, yearly)
- Evaluate expressions against context data for testing and validation

### Key Models

| Model                      | Description                                                       |
| -------------------------- | ----------------------------------------------------------------- |
| `spp.cel.variable`         | Variable definitions with source type, CEL accessor, and caching  |
| `spp.cel.variable.category`| Variable categories for organization                              |
| `spp.cel.expression`       | Business rule expressions with CEL syntax and variable tracking   |
| `spp.data.provider`        | External data provider configuration with auth and connection settings |
| `spp.data.credential`      | Secure encrypted credential storage for external providers        |
| `spp.data.value`           | Cached variable values with period keys and expiration tracking   |
| `spp.cel.service`          | Service facade for compiling and evaluating CEL expressions       |
| `spp.cel.variable.resolver`| Resolves variable references into expanded CEL expressions        |

### Configuration

After installing:

1. Navigate to **Custom > CEL Domain > Data Management > Data Providers** to configure external data sources
2. Define variables at the program or global level (UI provided by `spp_studio`)
3. Variables can reference model fields, constants, or external providers
4. Configure caching strategy (none, session, TTL, manual) for each variable
5. Set period granularity for variables requiring historical data support

### UI Location

- **Menu**: Custom > CEL Domain
- **Submenus**: Data Management > Data Providers, Data Management > Data Cache
- **Tools**: Tools > Rule Preview wizard for testing expressions
- **Variable/Expression UI**: Provided by `spp_studio` module

### Security

| Group                                  | Access                                    |
| -------------------------------------- | ----------------------------------------- |
| `spp_cel_domain.group_cel_domain_viewer` | Read variables, expressions, and data cache |
| `spp_cel_domain.group_cel_domain_manager` | Full CRUD on variables, expressions, providers, and cache |
| `spp_cel_domain.group_cel_domain_admin` | Full CRUD on credentials and sensitive configs  |

### Extension Points

- Inherit `spp.cel.variable` to add custom source types or validation logic
- Register custom CEL functions via `spp.cel.function.registry`
- Override `spp.cel.variable._compute_cel_expression()` to customize aggregate expression generation
- Implement custom data providers by inheriting `spp.data.provider`
- Add profile configurations in `spp.cel.registry` for new evaluation contexts

### Dependencies

`base`, `spp_base_common`, `spp_security`, `spp_registry`
