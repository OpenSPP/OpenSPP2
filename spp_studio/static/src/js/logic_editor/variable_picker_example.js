/** @odoo-module **/

/**
 * Variable Picker Usage Examples
 *
 * This file demonstrates how to use the VariablePicker component
 * in various scenarios within the Logic Studio.
 */

// ============================================================================
// Example 1: Basic Usage in an OWL Component
// ============================================================================

/*
import { Component, useState } from "@odoo/owl";
import { VariablePicker } from "./variable_picker";

export class MyLogicEditor extends Component {
    static template = "my_module.MyLogicEditor";
    static components = { VariablePicker };

    setup() {
        this.state = useState({
            selectedVariableId: false,
            variables: [],
        });

        // Load variables from backend
        this.loadVariables();
    }

    async loadVariables() {
        const orm = this.env.services.orm;
        const variables = await orm.searchRead(
            "spp.cel.variable",
            [],
            ["id", "name", "label", "value_type", "data_source",
             "category_id", "cel_accessor", "synonyms", "description"]
        );
        this.state.variables = variables;
    }

    onVariableSelect(variable) {
        console.log("Selected variable:", variable);
        this.state.selectedVariableId = variable.id;

        // Use the variable in your logic
        // For example, insert into CEL expression:
        const celAccessor = variable.cel_accessor;
        // this.insertIntoCelExpression(celAccessor);
    }
}
*/

// Template for Example 1:
/*
<t t-name="my_module.MyLogicEditor">
    <div class="logic-editor">
        <div class="mb-3">
            <label>Select Variable:</label>
            <VariablePicker
                variables="state.variables"
                selectedValue="state.selectedVariableId"
                placeholder="'Choose a variable...'"
                onSelect="(variable) => this.onVariableSelect(variable)"
                readonly="false"
            />
        </div>

        <div t-if="state.selectedVariableId">
            <p>Selected Variable ID: <t t-esc="state.selectedVariableId"/></p>
        </div>
    </div>
</t>
*/

// ============================================================================
// Example 2: Read-only Mode (Display Only)
// ============================================================================

/*
<VariablePicker
    variables="state.variables"
    selectedValue="record.variable_id"
    readonly="true"
/>
*/

// ============================================================================
// Example 3: With Custom Placeholder
// ============================================================================

/*
<VariablePicker
    variables="state.variables"
    selectedValue="state.selectedVariableId"
    placeholder="'Search for a demographic, income, or asset variable...'"
    onSelect="(variable) => this.handleVariableSelection(variable)"
/>
*/

// ============================================================================
// Example 4: Accessing Variable Data After Selection
// ============================================================================

/*
onVariableSelect(variable) {
    // Variable object contains:
    console.log("Variable ID:", variable.id);
    console.log("Variable Name:", variable.name);
    console.log("Display Name:", variable.label);
    console.log("CEL Accessor:", variable.cel_accessor); // e.g., "person.age"
    console.log("Value Type:", variable.value_type);     // e.g., "integer"
    console.log("Data Source:", variable.data_source);   // "local", "external", "computed"
    console.log("Category:", variable.category_id);      // [id, name]
    console.log("Synonyms:", variable.synonyms);         // "age, years old, birth year"
    console.log("Description:", variable.description);

    // Build a CEL expression
    const celExpression = `${variable.cel_accessor} >= 18`;

    // Or use in a condition object
    this.state.currentCondition = {
        variable_id: variable.id,
        cel_accessor: variable.cel_accessor,
        operator: ">=",
        value: 18,
    };
}
*/

// ============================================================================
// Example 5: Programmatically Clear Selection
// ============================================================================

/*
clearVariable() {
    this.state.selectedVariableId = false;
    // The VariablePicker will automatically update to show placeholder
}
*/

// ============================================================================
// Example 6: Integration with Form Views (Field Widget)
// ============================================================================

/*
// In your form view XML:
<field name="variable_id"
       widget="variable_picker"
       options="{'no_create': true}"/>

// The VariablePicker component is registered as a field widget
// and will automatically handle Many2one fields to spp.cel.variable
*/

// ============================================================================
// Example 7: Filtering Variables by Category
// ============================================================================

/*
export class CategoryAwareEditor extends Component {
    setup() {
        this.state = useState({
            selectedCategory: false,
            variables: [],
        });
    }

    get filteredVariables() {
        if (!this.state.selectedCategory) {
            return this.state.variables;
        }
        return this.state.variables.filter(
            v => v.category_id && v.category_id[0] === this.state.selectedCategory
        );
    }

    // In template:
    // <VariablePicker variables="filteredVariables" ... />
}
*/

// ============================================================================
// Notes on Variable Data Structure
// ============================================================================

/*
The variables array should contain objects with the following structure:

{
    id: 123,
    name: "person_age",
    label: "Person Age",
    value_type: "integer",           // "string", "integer", "float", "boolean", "date", "list"
    data_source: "local",             // "local", "external", "computed"
    category_id: [1, "Demographics"], // [category_id, category_name]
    cel_accessor: "person.age",       // CEL expression to access this variable
    synonyms: "age, years old",       // Comma-separated search terms
    description: "Age of the person in years",
}

The component will:
- Search across name, label, and synonyms
- Group variables by category_id
- Show data source indicators (✅ local, 🔗 external, ⚙️ computed)
- Track recently used variables in localStorage
- Provide keyboard navigation (Arrow keys, Enter, Escape)
*/
