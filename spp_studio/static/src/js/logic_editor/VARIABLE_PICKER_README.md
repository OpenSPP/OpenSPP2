# Variable Picker Component

## Overview

The Variable Picker is a searchable, categorized dropdown component for selecting variables in the OpenSPP Logic Studio.
It provides an intuitive interface for discovering and selecting variables from the Logic Variable Dictionary.

## Files Created

### 1. JavaScript Component

**Location:** `/home/user/openspp-modules-v2/spp_studio/static/src/js/logic_editor/variable_picker.js`

- **Lines:** 490
- **Purpose:** Main OWL component with all logic and state management

### 2. XML Template

**Location:** `/home/user/openspp-modules-v2/spp_studio/static/src/xml/variable_picker.xml`

- **Lines:** 171
- **Purpose:** Component template with UI structure

### 3. CSS Stylesheet

**Location:** `/home/user/openspp-modules-v2/spp_studio/static/src/css/variable_picker.css`

- **Lines:** 339
- **Purpose:** Complete styling with animations and responsive design

### 4. Usage Examples

**Location:** `/home/user/openspp-modules-v2/spp_studio/static/src/js/logic_editor/variable_picker_example.js`

- **Purpose:** Documentation and usage examples for developers

### 5. Manifest Update

**File:** `/home/user/openspp-modules-v2/spp_studio/__manifest__.py`

- **Updated:** Added CSS file to assets bundle

## Features

### ✅ Implemented Features

1. **Smart Search**

   - Search across variable name, label, and synonyms
   - Multi-word search (matches all terms)
   - Debounced input (150ms delay)
   - Real-time filtering

2. **Recently Used Variables**

   - Last 5 used variables stored in localStorage
   - Displayed at top of dropdown
   - Persists across sessions

3. **Category Grouping**

   - Variables organized by category
   - Expandable/collapsible sections
   - Smart category icons based on name
   - Category item counts

4. **Keyboard Navigation**

   - Arrow Up/Down: Navigate items
   - Enter: Select highlighted item
   - Escape: Close dropdown
   - Auto-scroll to highlighted item

5. **Data Availability Indicators**

   - ✅ Local data (green checkmark)
   - 🔗 External API (link icon)
   - ⚙️ Computed (gear icon)
   - 📊 Unknown (chart icon)
   - Tooltips explain each type

6. **User Experience**

   - Click outside to close
   - Clear button to remove selection
   - Empty state messages
   - "Create new variable" quick link
   - Smooth animations
   - Responsive design

7. **Read-only Mode**
   - Disabled input when readonly=true
   - Visual feedback (grayed out)

## Component API

### Props

```javascript
{
    variables: Array,           // REQUIRED - Array of variable objects
    selectedValue: Number|false, // OPTIONAL - Currently selected variable ID
    placeholder: String,         // OPTIONAL - Placeholder text
    onSelect: Function,          // REQUIRED - Callback(variable)
    readonly: Boolean,           // OPTIONAL - Disable interaction
}
```

### Variable Object Structure

```javascript
{
    id: 123,
    name: "person_age",
    label: "Person Age",
    source_type: "field",            // field|indicator|scoring|vocabulary|computed|constant|aggregate
    applies_to: "both",              // individual|group|both
    value_type: "integer",           // string|integer|float|boolean|date|list
    data_source: "local",             // local|external|computed
    category_id: [1, "Demographics"], // [category_id, category_name]
    cel_accessor: "person.age",       // CEL expression
    synonyms: "age, years old",       // Search terms
    description: "Age of the person in years",
}
```

## Usage Example

### Basic Usage

```javascript
import {VariablePicker} from "./variable_picker";

export class MyEditor extends Component {
  static components = {VariablePicker};

  setup() {
    this.state = useState({
      variables: [],
      selectedVariableId: false,
    });
    this.loadVariables();
  }

  async loadVariables() {
    const variables = await this.orm.searchRead(
      "spp.cel.variable",
      [],
      [
        "id",
        "name",
        "label",
        "source_type",
        "applies_to",
        "value_type",
        "data_source",
        "category_id",
        "cel_accessor",
        "synonyms",
        "description",
      ]
    );
    this.state.variables = variables;
  }

  onVariableSelect(variable) {
    this.state.selectedVariableId = variable.id;
    console.log("Selected:", variable.cel_accessor);
  }
}
```

### Template

```xml
<VariablePicker
    variables="state.variables"
    selectedValue="state.selectedVariableId"
    placeholder="'Select a variable...'"
    onSelect="(variable) => this.onVariableSelect(variable)"
    readonly="false"
/>
```

## State Management

### Component State

```javascript
state = {
  searchTerm: "", // Current search text
  isOpen: false, // Dropdown visibility
  highlightedIndex: -1, // Keyboard navigation index
  recentlyUsed: [], // Recently used variable IDs
  expandedCategories: Set, // Expanded category IDs
};
```

### LocalStorage

The component stores recently used variables in localStorage:

- **Key:** `logic_studio_recent_variables`
- **Value:** JSON array of up to 5 variable IDs
- **Persistence:** Across browser sessions

## Key Methods

### Public Methods

- `selectVariable(variable)` - Select a variable
- `clearSelection()` - Clear current selection
- `toggleDropdown()` - Open/close dropdown
- `toggleCategory(categoryId)` - Expand/collapse category

### Computed Properties

- `filteredVariables` - Variables matching search term
- `variablesByCategory` - Variables grouped by category
- `recentlyUsedVariables` - Recently used variable objects
- `displayValue` - Display text for selected variable

## Styling

### CSS Classes

- `.variable-picker` - Main container
- `.vp-input-container` - Input wrapper
- `.vp-search-input` - Search input field
- `.vp-dropdown` - Dropdown container
- `.vp-section` - Section container
- `.vp-section-header` - Section header
- `.vp-item` - Variable item
- `.vp-item.highlighted` - Highlighted item
- `.vp-footer` - Footer with create link

### Customization

The CSS file is well-documented and organized by sections:

- Input styling
- Dropdown animations
- Section headers
- Item states
- Keyboard navigation
- Responsive breakpoints

## Integration Points

### With Form Views

Registered as a field widget for Many2one fields:

```xml
<field name="variable_id" widget="variable_picker"/>
```

## Performance Considerations

1. **Debounced Search** - 150ms delay prevents excessive re-renders
2. **Efficient Filtering** - Single-pass filter with early returns
3. **Lazy Category Expansion** - Only render visible items
4. **LocalStorage Caching** - Reduces API calls for recent items

## Accessibility

- Keyboard navigation (Arrow keys, Enter, Escape)
- Focus management (auto-focus on open)
- ARIA attributes (future enhancement)
- Focus-visible styles for keyboard users

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- ES6+ features (Arrow functions, Set, template literals)
- LocalStorage API
- CSS Grid and Flexbox

## Future Enhancements

Potential improvements for future versions:

1. **ARIA Labels** - Add aria-\* attributes for screen readers
2. **Fuzzy Matching** - Implement fuzzy search algorithm
3. **Variable Preview** - Show variable details on hover
4. **Bulk Selection** - Allow multiple variable selection
5. **Custom Filters** - Filter by type, source, or category
6. **Sorting Options** - Sort by name, type, or usage
7. **Export/Import** - Save/load variable sets
8. **Analytics** - Track which variables are most used

## Testing

To test the component:

```bash
# From openspp-odoo-19-migration/ directory
invoke test-spp-deps --modules=spp_studio --mode=update
```

## Support

For issues or questions:

- Check the usage examples in `variable_picker_example.js`
- Review the inline documentation in the source code
- Consult the Logic Studio specification

## License

LGPL-3 (consistent with OpenSPP project)
