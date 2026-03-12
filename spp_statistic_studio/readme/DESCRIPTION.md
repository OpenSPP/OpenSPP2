Bridge module that exposes statistics configuration in the Studio no-code UI.
Auto-installs when both `spp_statistic` and `spp_studio` are present. Adds
tree/form views for statistics and metric categories under the Studio settings menu.

### Key Capabilities

- Manage statistics (create, edit, archive) through Studio forms
- Manage metric categories through Studio forms
- Grants Studio managers full CRUD on statistics, contexts, and categories

### Key Models

No new models. Provides views and menu entries for `spp.statistic`,
`spp.statistic.context`, and `spp.metric.category`.

### UI Location

- **Menu**: Studio > Settings > Statistics > All Statistics
- **Menu**: Studio > Settings > Statistics > Categories

### Security

| Group                              | Access    |
| ---------------------------------- | --------- |
| `spp_studio.group_studio_manager`  | Full CRUD |

### Dependencies

`spp_statistic`, `spp_studio`
