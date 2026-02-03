Extends OpenSPP API V2 to expose product catalog data through REST endpoints. Allows external systems to query products, product categories, and units of measure for in-kind entitlement programs. Uses OAuth 2.0 with scope-based access control and product code/name as external identifiers.

### Key Capabilities

- Search and retrieve products by default_code (SKU) or name
- Query product categories for classification and filtering
- List units of measure with category filtering
- Paginated search with filters: name, code, category, last updated date
- OAuth 2.0 authentication with "product" resource scope
- Returns JSON responses with references to related resources (category, UoM)

### Key Models

This module extends existing models rather than introducing new ones:

| Model                   | Extension                                            |
| ----------------------- | ---------------------------------------------------- |
| `spp.api.client.scope`  | Adds "product" resource type for scope management   |
| `fastapi.endpoint`      | Registers Product, ProductCategory, UoM routers      |

### Configuration

After installing (auto-installs with `spp_api_v2` + `product`):

1. Navigate to **Registry > Configuration > API V2 > API Clients**
2. Create or edit an API client
3. Add scope with resource="product", permission="read"
4. Use OAuth 2.0 client credentials flow to authenticate

### UI Location

No standalone menu. This is an API-only module.

**API Endpoints**:
- `GET /api/v2/spp/Product` - Search products
- `GET /api/v2/spp/Product/{identifier}` - Read product by code or name
- `GET /api/v2/spp/ProductCategory` - Search categories
- `GET /api/v2/spp/ProductCategory/{identifier}` - Read category by name
- `GET /api/v2/spp/UnitOfMeasure` - Search units of measure
- `GET /api/v2/spp/UnitOfMeasure/{identifier}` - Read UoM by name

**Configuration**: Registry > Configuration > API V2 > API Clients

### Security

| Group/Mechanism          | Access                                               |
| ------------------------ | ---------------------------------------------------- |
| OAuth 2.0 scope          | Requires "product:read" scope on API client          |
| API authentication       | All endpoints require valid OAuth 2.0 access token   |

No `ir.model.access.csv` entries. Security is enforced at the API layer through OAuth scopes.

### Extension Points

- Inherit `ProductService`, `ProductCategoryService`, or `UomService` to customize API responses
- Override `to_api_schema()` methods to add fields to Product, ProductCategory, or UnitOfMeasure schemas
- Override `search()` methods to add custom filtering logic

### Dependencies

`spp_api_v2`, `product`, `uom`
