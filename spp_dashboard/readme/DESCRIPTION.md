Dashboard for statistics published via `spp.statistic` with `is_published_dashboard=True`. Materializes
pre-computed values into a snapshot table and renders them through kanban, list, pivot, and graph views
with area and program filtering.

### Key Capabilities

- Kanban KPI cards grouped by category for at-a-glance overview
- List view with category grouping, optional columns, and native Excel/CSV export
- Pivot cross-tab of statistics by area or program with Excel export
- Background refresh via `queue_job` (manual trigger or daily cron)
- k-anonymity suppression applied to small-cell values

### Key Models

| Model              | Description                                             |
| ------------------ | ------------------------------------------------------- |
| `spp.dashboard.data` | Materialized snapshot of computed statistic values     |

### Configuration

After installing:

1. Mark statistics for dashboard publication via **Settings > Statistics > [Statistic] > Publish to Dashboard**
2. Trigger an initial refresh from the dashboard action menu ("Refresh Statistics (Background)")
3. The **Dashboard Refresh** scheduled action runs daily by default

### UI Location

- **Menu**: Statistics Dashboard (top-level)
- **URL**: `/odoo/statistics-dashboard`

### Security

| Group                                    | Access                              |
| ---------------------------------------- | ----------------------------------- |
| `spp_dashboard.group_dashboard_read`     | Read only                           |
| `spp_dashboard.group_dashboard_manage`   | Read/Write (for refresh upsert)     |

### Extension Points

- Override `_get_dashboard_areas()` to customize which areas appear in the dashboard
- Override `_get_dashboard_programs()` to customize which programs appear
- Override `_build_scope()` to customize aggregation scope construction

### Dependencies

`spp_statistic`, `spp_aggregation`, `spp_area`, `spp_programs`, `spp_security`, `queue_job`
