No-code customization interface for OpenSPP that enables program staff, M&E officers, and country coordinators to configure business logic and registry fields without developer involvement. Provides a CEL expression editor with variable discovery, custom field builder, pre-built logic packs for common social protection programs, and integrated testing with personas. Includes governance workflows with approval, versioning, and scheduled activation.

### Key Capabilities

- Create and test CEL expressions with real-time variable discovery and validation
- Add custom fields to Individual and Group registries through a guided builder
- Install pre-built logic packs for cash transfers, PMT targeting, child benefits, social pensions, and other programs
- Test expressions using personas with example data before deployment
- Manage lifecycle through governance workflow: draft, pending approval, published, archived
- Track version history with scheduled activation for future changes
- Monitor where logic and fields are used across programs

### Key Models

| Model                        | Description                                          |
| ---------------------------- | ---------------------------------------------------- |
| `spp.cel.expression`         | Business logic definitions with CEL expressions      |
| `spp.cel.variable`           | Variable definitions for use in expressions          |
| `spp.cel.variable.category`  | Categories for organizing variables                  |
| `spp.studio.field`           | Custom field definitions for registry extension      |
| `spp.studio.pack`            | Pre-built logic bundles for common use cases         |
| `spp.studio.pack.item`       | Individual logic definitions within a pack           |
| `spp.studio.test`            | Test cases for validating logic expressions          |
| `spp.studio.test.persona`    | Test personas with example data for logic validation |
| `spp.studio.placement.zone`  | Form zones where custom fields can be placed         |
| `spp.studio.version`         | Version history tracking for logic changes           |
| `spp.studio.usage`           | Usage tracking for logic and field references        |

### Configuration

After installing:

1. Navigate to **Studio > Settings > General** to enable governance mode (optional)
2. Review **Studio > Settings > Registry > Field Zones** to understand form placement options
3. Import standard variables via **Studio > Rules > Variables > All Variables**
4. Explore **Studio > Rules > Packages** for pre-built logic templates

### UI Location

- **Menu**: Studio (top-level menu)
- **Home**: Studio > Home
- **Rules**: Studio > Rules > Expressions, Variables, Packages, Test Personas
- **Custom Fields**: Studio > Forms & Fields > Custom Fields
- **Settings**: Studio > Settings (managers only)

### Security

| Group                                    | Access                                         |
| ---------------------------------------- | ---------------------------------------------- |
| `spp_studio.group_studio_viewer`         | Read                                           |
| `spp_studio.group_studio_editor_officer` | Read/Write/Create on logic and fields (no delete on fields) |
| `spp_studio.group_studio_manager`        | Full CRUD                                      |

### Extension Points

- Inherit `spp.cel.expression` to add domain-specific validation or compilation steps
- Override `_pre_activate()` on `spp.studio.field` to customize field creation behavior
- Add new logic pack categories by extending the `category` selection field
- Implement custom variable sources by inheriting `spp.cel.variable` and overriding discovery methods

### Dependencies

`base`, `mail`, `spp_audit`, `spp_security`, `spp_registry`, `spp_base_common`, `spp_programs`, `spp_user_roles`, `spp_custom_field`, `spp_cel_domain`, `spp_cel_widget`, `spp_vocabulary`, `spp_approval`, `spp_versioning`
