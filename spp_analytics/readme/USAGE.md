This guide covers manual testing of the OpenSPP Analytics module for QA
verification. All tests assume you are logged in as an administrator.

### Prerequisites

- The module **OpenSPP Analytics** is installed
- Test registrants exist in the system (individuals and groups)
- At least one administrative area exists under **Registry > Configuration > Areas**
- At least one area tag exists (e.g., "Urban", "Rural")

### Accessing the Module

1. Navigate to **Settings > Analytics > Configuration**
2. Verify the following three menu items are visible:
   - **Scopes**
   - **Demographic Dimensions**
   - **Access Rules**

> **Note**: The Analytics menu requires the **Analytics Manager** role. If the
> menu is not visible, check that your user has the Manager privilege under the
> **Analytics Engine** category in **Settings > Users & Companies > Users**.

### Test 1: Create and Validate Scopes

**1.1 Create an Administrative Area Scope**

1. Go to **Settings > Analytics > Configuration > Scopes**
2. Click **New**
3. Fill in:
   - **Name**: "District Test Scope"
   - **Scope Type**: "Administrative Area"
4. Verify that the **Administrative Area** tab appears in the notebook
5. Select an area in the **Area** field
6. Leave **Include Child Areas** checked
7. Click **Save**
8. Verify the **Registrants** stat button in the top-right shows a count > 0
9. Click the **Registrants** stat button and verify it opens a list of
   registrants filtered to those in the selected area

**1.2 Create a CEL Expression Scope**

1. Click **New** from the Scopes list
2. Fill in:
   - **Name**: "Adult Individuals"
   - **Scope Type**: "CEL Expression"
3. Verify the **CEL Expression** tab appears
4. Set **CEL Profile** to "Individuals"
5. Enter a CEL expression, e.g.: `r.is_group == false`
6. Click **Save**
7. Verify the **Registrants** count updates

**1.3 Create an Explicit IDs Scope**

1. Click **New**
2. Fill in:
   - **Name**: "Manual Selection"
   - **Scope Type**: "Explicit IDs"
3. Verify the **Explicit Registrants** tab appears
4. Add 3-5 registrants using the **Add a line** button
5. Click **Save**
6. Verify the **Registrants** count matches the number of registrants added

**1.4 Create an Area Tags Scope**

1. Click **New**
2. Fill in:
   - **Name**: "Urban Areas"
   - **Scope Type**: "Area Tags"
3. Verify the **Area Tags** tab appears
4. Add one or more area tags (e.g., "Urban")
5. Click **Save**
6. Verify the scope is saved without errors

**1.5 Validation Error Tests**

Test that required fields are enforced for each scope type:

| Scope Type | Leave blank | Expected result |
|---|---|---|
| CEL Expression | CEL Expression field | Validation error: "CEL expression is required..." |
| Administrative Area | Area field | Validation error: "Area is required..." |
| Explicit IDs | Explicit Registrants list | Validation error: "At least one registrant is required..." |
| Area Tags | Area Tags field | Validation error: "At least one area tag is required..." |
| Within Polygon | Geometry (GeoJSON) field | Validation error: "GeoJSON geometry is required..." |
| Within Distance | Buffer Radius | Validation error: "Buffer radius must be a positive number." |

**1.6 Spatial Polygon Validation**

1. Create a scope with type "Within Polygon"
2. Enter invalid JSON (e.g., `not json`) and save
   - Expected: Validation error about invalid GeoJSON
3. Enter valid JSON but wrong type (e.g., `{"type": "Point", "coordinates": [0, 0]}`)
   - Expected: Validation error about requiring Polygon, MultiPolygon, Feature, or FeatureCollection

**1.7 Spatial Buffer Validation**

1. Create a scope with type "Within Distance"
2. Enter latitude `100` (out of range), longitude `0`, radius `10`
   - Expected: Validation error "Latitude must be between -90 and 90."
3. Enter latitude `0`, longitude `200` (out of range), radius `10`
   - Expected: Validation error "Longitude must be between -180 and 180."

### Test 2: Scope List View and Search

1. Go to **Settings > Analytics > Configuration > Scopes**
2. Verify the list shows columns: **Name**, **Scope Type**, **Registrant Count**, **Active**
3. Test search filters:
   - Click the **CEL** filter and verify only CEL scopes appear
   - Click the **Area** filter and verify only area scopes appear
   - Click the **Spatial** filter and verify only spatial scopes appear
4. Test the **Scope Type** group-by and verify scopes are grouped correctly
5. Test the **Archived** filter:
   - Archive a scope (open it, uncheck **Active**, save)
   - Verify it disappears from the default list
   - Enable the **Archived** filter and verify it appears with the "Archived" ribbon

### Test 3: Cache Management

**3.1 Refresh Cache Button**

1. Open any scope record
2. Verify the **Cache Settings** tab exists in the notebook
3. Note the **Last Cache Refresh** field is empty (or has a previous date)
4. Click the **Refresh Cache** button (refresh icon in the stat button area)
5. Verify the **Last Cache Refresh** field is now populated with the current timestamp

**3.2 Cache Settings Tab**

1. Open a scope record and go to the **Cache Settings** tab
2. Verify the following fields are visible:
   - **Enable Caching** (checkbox, default checked)
   - **Cache TTL (seconds)** (visible only when caching is enabled)
   - **Last Cache Refresh** (read-only)
3. Uncheck **Enable Caching** and verify the **Cache TTL** field is hidden
4. Re-check **Enable Caching** and verify **Cache TTL** reappears

**3.3 Scheduled Action**

1. Go to **Settings > Technical > Scheduled Actions**
2. Search for "Analytics: Cache Cleanup"
3. Verify the scheduled action exists and is **Active**
4. Verify the interval is set to **1 Hour**

### Test 4: Access Rules

**4.1 Create a User-Specific Access Rule**

1. Go to **Settings > Analytics > Configuration > Access Rules**
2. Click **New**
3. Fill in:
   - **Name**: "Test User Rule"
   - **User**: Select a specific user
   - **Access Level**: "Aggregates Only" (radio button)
   - **Minimum K-Anonymity**: 5
4. Click **Save**
5. Verify the record saves without errors

**4.2 Create a Group-Based Access Rule**

1. Click **New**
2. Fill in:
   - **Name**: "Test Group Rule"
   - **Security Group**: Select a group (e.g., "Internal User")
   - **Access Level**: "Individual Records"
3. Click **Save**

**4.3 Validation: User and Group Mutual Exclusivity**

1. Create a new access rule
2. Set both **User** and **Security Group** fields
3. Click **Save**
   - Expected: Validation error "A rule cannot apply to both a specific user and a group."
4. Clear both **User** and **Security Group** fields
5. Click **Save**
   - Expected: Validation error "A rule must apply to either a user or a group."

**4.4 K-Anonymity Validation**

1. Create a new access rule with a user set
2. Set **Minimum K-Anonymity** to `0` and save
   - Expected: Validation error "Minimum k-anonymity must be at least 1."
3. Set **Minimum K-Anonymity** to `101` and save
   - Expected: Validation error "Minimum k-anonymity should not exceed 100."

**4.5 Max Dimensions Validation**

1. Set **Max Group By Dimensions** to `-1` and save
   - Expected: Validation error "Maximum group_by dimensions cannot be negative."
2. Set **Max Group By Dimensions** to `11` and save
   - Expected: Validation error "Maximum group_by dimensions should not exceed 10."

**4.6 Scope Restrictions**

1. Create an access rule with **Allowed Scope Types** set to "Predefined Scopes Only"
2. Verify the **Allowed Scopes** tab appears in the notebook
3. Add one or more scopes to the allowed list
4. Change **Allowed Scope Types** to "All Scope Types"
5. Verify the **Allowed Scopes** tab is hidden

**4.7 Dimension Restrictions**

1. Open an access rule
2. Go to the **Allowed Dimensions** tab
3. Add one or more demographic dimensions
4. Verify the dimensions are displayed with **Name** and **Label** columns

### Test 5: Access Rules List View and Search

1. Go to **Settings > Analytics > Configuration > Access Rules**
2. Verify the list columns: drag handle (sequence), **Name**, **User**, **Security Group**,
   **Access Level**, **Minimum K-Anonymity**, **Active**
3. Verify rules can be reordered by dragging the handle
4. Test search filters:
   - **Aggregate Only**: Shows only rules with access level "Aggregates Only"
   - **Individual Access**: Shows only rules with access level "Individual Records"
   - **Archived**: Shows archived rules
5. Test the **Access Level** group-by

### Test 6: Security Groups

Verify that users with different security roles see the appropriate menus:

| Role | Expected Access |
|---|---|
| No Analytics role | Cannot see the **Analytics** menu under Settings |
| Viewer | Cannot see the Analytics menu (Viewer implies read-only data access, not config) |
| Analyst | Cannot see the Analytics menu (Analyst implies query access, not config) |
| Manager | Can see and use all three menu items under **Settings > Analytics > Configuration** |
| Administrator | Full access (admin implies Manager) |

To test:

1. Go to **Settings > Users & Companies > Users**
2. Open a test user
3. Under the **Analytics Engine** section, set the privilege level
4. Log in as that user and verify menu visibility matches the table above

### Test 7: Demographic Dimensions

1. Go to **Settings > Analytics > Configuration > Demographic Dimensions**
2. Verify the menu opens the demographic dimension list (provided by `spp_metric_service`)
3. This view should show available dimensions like "registrant_type", "area", etc.
4. Verify dimensions can be viewed but that create/edit depends on your permission level

### Common Issues

| Symptom | Likely Cause |
|---|---|
| Analytics menu not visible | User lacks the **Manager** role under Analytics Engine |
| Registrant count shows 0 on area scope | No registrants assigned to the selected area |
| CEL scope shows 0 registrants | CEL expression syntax error or no matching registrants |
| Spatial scopes return empty results | The `spp_aggregation_spatial` bridge module is not installed |
| "Refresh Cache" button has no visible effect | Cache was already empty; check **Last Cache Refresh** timestamp |
