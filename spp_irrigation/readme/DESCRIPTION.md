Manages irrigation infrastructure assets with GIS mapping capabilities. Tracks irrigation assets by category, capacity, and unique identifiers, and models water distribution networks by linking sources to destinations. Provides GIS visualization with point coordinates and polygon boundaries.

### Key Capabilities

- Record irrigation assets with name, category, and capacity
- Store GIS point coordinates and polygon boundaries for each asset
- Model water distribution networks by linking irrigation sources to destinations
- Visualize irrigation infrastructure on interactive GIS maps with configurable layers

### Key Models

| Model                  | Description                                               |
| ---------------------- | --------------------------------------------------------- |
| `spp.irrigation.asset` | Irrigation infrastructure with GIS data and network links |

### Configuration

After installing:

1. Access irrigation assets through the GIS mapping interface provided by `spp_gis`
2. Create irrigation records with coordinates and polygon data
3. Define water distribution networks by linking assets via source/destination relationships

### UI Location

No standalone menu. This module provides GIS views integrated into the `spp_gis` mapping interface. Access irrigation assets through the GIS map viewer.

### Security

| Group                                 | Access    |
| ------------------------------------- | --------- |
| `spp_irrigation.group_irrigation_manager` | Full CRUD |

The irrigation manager group is automatically granted to users in `spp_security.group_spp_admin`.

### Extension Points

- Extend `spp.irrigation.asset` to add domain-specific categories beyond "reservoir"
- Add computed fields for capacity utilization or coverage analysis
- Inherit the model to integrate with program eligibility or land records

### Dependencies

`base`, `spp_gis`, `spp_security`
