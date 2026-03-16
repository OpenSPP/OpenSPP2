### Prerequisites

- Log in as a user with **Settings / System admin** access (`base.group_system`). The GIS Configuration menus are only visible to this group.
- The following modules must be installed: `spp_gis`, `spp_hxl_area`, `spp_registry`, `spp_security`.
- At least one `spp.cel.variable` record and some `spp.hxl.area.indicator` records must exist for indicator layers to display meaningful data.

### Color Scales — List View

1. Go to **Settings > GIS Configuration > Color Scales**.
2. The list view shows columns: **Sequence** (drag handle), **Scale Name**, **Scale Type**, **Description**, **Active**.
3. Eleven preset ColorBrewer scales are installed as demo data (loaded with `noupdate="1"`, so they survive module upgrades).

### Color Scales — Form View

Open any preset scale (e.g., "Blues (Sequential)"). Verify the form shows:

- **Scale Name** — e.g., "Blues (Sequential)"
- **Scale Type** — dropdown with three options: "Sequential (low to high)", "Diverging (negative to positive)", "Categorical (distinct values)"
- **Sequence** — numeric ordering value
- **Description** — free-text field below a "Description" separator
- **Colors** section — a text area labeled "Colors (JSON)" containing a JSON array of hex color codes
- **Preview** section — static help text showing the expected JSON format

To create a custom scale: click **New**, fill in **Scale Name** (required), select a **Scale Type** (defaults to "Sequential"), and enter a JSON array of at least 2 hex colors in the **Colors (JSON)** field. Valid formats: `#RGB` (3-digit) or `#RRGGBB` (6-digit), e.g., `["#f00", "#00ff00", "#0000ff"]`.

To archive: open a scale, click **Action > Archive**. An "Archived" ribbon appears. Archived scales no longer appear in dropdowns on indicator layers.

### Color Scale — Validation Tests

| Action | Expected Result |
|--------|----------------|
| Enter invalid JSON (e.g., `not json`) | ValidationError: "Invalid JSON in colors_json" |
| Enter a non-array (e.g., `{"a": 1}`) | ValidationError: "colors_json must be a JSON array" |
| Enter fewer than 2 colors (e.g., `["#fff"]`) | ValidationError: "Color scale must have at least 2 colors" |
| Enter a non-string element (e.g., `[123, "#fff"]`) | ValidationError: "All colors must be strings" |
| Enter invalid hex (e.g., `["red", "#fff"]`) | ValidationError: "Invalid hex color format" |
| Enter 5-digit hex (e.g., `["#12345"]`) | ValidationError: "Invalid hex color format" |

### Indicator Layers — List and Search

1. Go to **Settings > GIS Configuration > Indicator Layers**.
2. The list view shows: **Sequence** (drag handle), **Name**, **Variable Name**, **Period Key**, **Classification Method**, **Number of Classes**, **Active**.
3. The default search filter is "Active" (only active records shown).
4. Search bar supports filtering by **Name**, **Variable**, and **Period Key**.
5. Predefined filters: **Active**, **Archived** (under the Filters menu).
6. Group By options: **Variable**, **Period**, **Classification Method**.

### Indicator Layer — Form: Data Source Tab

Click **New** and fill in **Configuration Name** (required). The form has three tabs: **Data Source**, **Visualization**, and **Legend Preview**.

The **Data Source** tab contains:

| Field | Description | Required |
|-------|-------------|----------|
| **Indicator Variable** | Dropdown of `spp.cel.variable` records (no inline create/open) | Yes |
| **Period Key** | Free-text, defaults to "current". Examples: "2024-12", "current" | No |
| **Incident/Disaster** | Dropdown of `spp.hazard.incident` records. Filters indicator data by incident. | No |

### Indicator Layer — Form: Visualization Tab

| Field | Description | Visibility |
|-------|-------------|------------|
| **Color Scale** | Dropdown of `spp.gis.color.scale` records (no inline create) | Always visible |
| **Classification Method** | Dropdown: "Quantile (Equal count per class)", "Equal Interval (Equal range per class)", "Manual Breaks" | Always visible |
| **Number of Classes** | Integer (2–10). Controls how many color buckets to create. | Hidden when method is "Manual Breaks" |
| **Manual Break Points** | Comma-separated numbers, e.g., "10,50,100,500" | Only visible when method is "Manual Breaks" |
| **Computed Breaks** (read-only) | Shows the computed break values as a JSON array | Always visible (in "Computed Classification" section) |

Classification method behavior:

- **Quantile**: Breaks computed so each class contains approximately the same number of areas. Requires indicator data. If no data, Computed Breaks is empty.
- **Equal Interval**: Breaks evenly spaced between minimum and maximum indicator values. If all values are equal, Computed Breaks is empty.
- **Manual Breaks**: Uses user-supplied break points directly. Does not depend on indicator data.

### Indicator Layer — Form: Legend Preview Tab

- Displays a read-only HTML preview of the legend.
- Each legend item shows a colored box and a label with the value range (e.g., "< 10.00", "10.00 - 50.00", ">= 500.00").
- The legend updates automatically when break values or color scale changes.

### Indicator Layer — Validation Tests

**Number of Classes:**

| Action | Expected Result |
|--------|----------------|
| Set Number of Classes to 1 | ValidationError: "Number of classes must be at least 2" |
| Set Number of Classes to 11 | ValidationError: "Number of classes must not exceed 10" |
| Set Number of Classes to 5 | Saves successfully |

**Manual Breaks:**

| Action | Expected Result |
|--------|----------------|
| Select "Manual Breaks" but leave the field empty | ValidationError: "Manual breaks are required when using manual classification" |
| Enter non-numeric text (e.g., "a,b,c") | ValidationError: "Invalid manual breaks format" |
| Enter descending values (e.g., "100,50,10") | ValidationError: "Manual breaks must be in ascending order" |
| Enter valid ascending values (e.g., "10,50,100") | Saves successfully; Computed Breaks shows `[10.0, 50.0, 100.0]` |

### GIS Data Layer — Choropleth Integration

This module extends the GIS data layer form to support indicator-based choropleth visualization. Data layers are configured within GIS view definitions, not through a standalone menu — they appear as inline records on the GIS view form.

To set up: open a GIS data layer form, set **Geo Repr** to "Choropleth (Color by Value)". The "Colors" section hides and the "Choropleth Configuration" and "Choropleth Settings" sections appear. In the **Choropleth Settings** section (added by this module), select an **Indicator Configuration** from the dropdown.

When `geo_repr` is set to "Choropleth", two configuration paths are available:

| Path | Source | When to Use |
|------|--------|-------------|
| **Value Field** (base `spp_gis`) | `choropleth_field_id` — picks a numeric field directly from the layer's model | Simple field-based coloring |
| **Indicator Configuration** (this module) | `indicator_layer_id` — uses a pre-configured indicator layer with CEL variables | Area-level indicator data from `spp.hxl.area.indicator` |

Either one satisfies the choropleth validation. Setting both is allowed; when an Indicator Configuration is set, it takes priority over the Value Field.

### Data Layer — Choropleth Validation Tests

| Action | Expected Result |
|--------|----------------|
| Set Geo Repr to "Choropleth" with neither Value Field nor Indicator Configuration | ValidationError: "Choropleth layers require a Value Field or Indicator Configuration." |
| Set Geo Repr to "Choropleth" with only Indicator Configuration set | Saves successfully |
| Set Geo Repr to "Choropleth" with only Value Field set | Saves successfully |
| Set Geo Repr to "Basic" with no choropleth config | Saves successfully (no validation) |

### Edge Cases to Verify

| Scenario | Expected Behavior |
|----------|-------------------|
| Indicator layer with no matching indicator data | Computed Breaks is empty; Legend Preview is blank |
| Indicator layer where all indicator values are identical | Equal Interval returns empty breaks; Quantile returns empty breaks; Legend shows single class |
| Color scale with exactly 2 colors | Works correctly; values map to one of two colors |
| Manual breaks with a single value (e.g., "50") | Creates 2 classes: "< 50.00" and ">= 50.00" |
| Archiving an indicator layer used by a data layer | The data layer still references it but `get_feature_colors()` returns no colors for inactive config |
| Deleting a color scale used by an indicator layer | Standard Odoo referential integrity behavior (blocked or cascaded depending on `ondelete`) |
