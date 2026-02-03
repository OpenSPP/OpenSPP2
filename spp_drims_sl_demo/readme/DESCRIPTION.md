Demo data generator for DRIMS (Disaster Response Inventory Management System) Sri Lanka implementation. Creates sample incidents, donations, requests, dispatches, personnel, and alerts based on realistic Sri Lanka disaster scenarios. Imports administrative boundaries from official Excel data and HDX polygon files for GIS visualization.

### Key Capabilities

- Import Sri Lanka administrative boundaries from Excel and HDX GeoJSON files (provinces, districts, DS/GN divisions)
- Generate disaster incidents with affected areas, severity levels, and coordination modes
- Create donations from UN agencies and NGOs at various workflow states
- Generate relief requests with priorities, SLA deadlines, life-threatening flags, and OCHA cluster assignments
- Populate warehouses with relief items, lot tracking, and expiry dates
- Create personnel deployments with roles, organizations, clusters, and contact information
- Generate low stock, SLA breach, and SLA warning alerts and trigger alert engine cron jobs
- Create completed dispatch pickings with beneficiary counts and POD data for dashboard KPIs
- Configure GIS reports for choropleth visualization of request distribution and affected populations

### Key Models

| Model                       | Description                                                      |
| --------------------------- | ---------------------------------------------------------------- |
| `spp.drims.demo.generator`  | Transient wizard that orchestrates demo data generation          |
| `spp.gis.report` (extended) | Adds `spp.drims.request` as supported GIS report data source     |

### Usage

After installing:

1. Navigate to **Settings > Demo Data > Load DRIMS Demo**
2. Click **Load Demo Data** to generate sample data
3. System redirects to DRIMS Dashboard after completion

The generator imports approximately 3,500 areas, creates 2-3 incidents with 40+ requests, 10+ donations, 15+ dispatches, 20+ personnel, and 5+ alerts. Full generation takes 2-5 minutes.

### Demo Data Included

- **Relief Products**: 27 product templates across 7 categories (Food & Nutrition, Water & Beverages, Medical & Health, Shelter & Housing, Hygiene & WASH, Clothing & Bedding, Equipment & Tools)
- **Demo Users**: 6 users with password `demo`: kumari (field officer), rajitha (approver), silva (manager), perera (warehouse worker), fernando (coordinator), secretary (viewer)
- **GIS Reports**: 5 pre-configured reports for request distribution, affected population, pending approvals, relief value, and fulfillment progress

### UI Location

- **Menu**: Settings > Demo Data > Load DRIMS Demo
- **Dashboard**: After loading, system redirects to Social Protection > DRIMS > Dashboard

### Security

| Group                           | Access    |
| ------------------------------- | --------- |
| `spp_drims.group_drims_manager` | Full CRUD |

### Extension Points

- Override `_generate_incidents()` to customize incident scenarios for country-specific disaster types
- Inherit `spp.drims.demo.generator` to add custom demo data generation steps
- Override area import methods to support alternative data sources beyond Excel/HDX

### Dependencies

`spp_drims_sl`, `spp_area_hdx`, `spp_gis_report`
