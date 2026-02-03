/** @odoo-module **/

/**
 * CEL Symbol Browser Component
 *
 * Collapsible panel showing available fields, variables, library expressions, and functions.
 * Organized in tabs:
 * - Fields: Model fields from profile symbols (r.name, r.income, etc.)
 * - Variables: CEL variables from spp.cel.variable (is_female, is_female_headed, etc.)
 * - Library: Published expressions from spp.cel.expression
 * - Functions: Built-in CEL functions
 */

import {Component, useState} from "@odoo/owl";

export class CelSymbolBrowser extends Component {
    static template = "spp_cel_widget.CelSymbolBrowser";
    static props = {
        symbols: {type: Object, optional: true},
        onInsert: {type: Function},
        onClose: {type: Function},
    };

    setup() {
        this.state = useState({
            searchQuery: "",
            expandedVariables: new Set(),
            activeTab: "fields", // fields, variables, library, functions
            valueTypeFilter: "", // "", "boolean", "number", etc.
            categoryFilter: "", // "" or category name
        });
    }

    // ─── FIELDS TAB (previously "variables") ─────────────────────────────

    get filteredFields() {
        if (!this.props.symbols?.variables) {
            return [];
        }

        const query = this.state.searchQuery.toLowerCase();
        if (!query) {
            return this.props.symbols.variables;
        }

        return this.props.symbols.variables.filter((v) => {
            // Match variable name
            if (v.name.toLowerCase().includes(query)) {
                return true;
            }
            // Match any field name
            if (v.fields?.some((f) => f.name.toLowerCase().includes(query))) {
                return true;
            }
            return false;
        });
    }

    getFilteredModelFields(variable) {
        if (!variable.fields) {
            return [];
        }

        const query = this.state.searchQuery.toLowerCase();
        if (!query) {
            return variable.fields;
        }

        return variable.fields.filter(
            (f) => f.name.toLowerCase().includes(query) || f.doc?.toLowerCase().includes(query)
        );
    }

    // ─── VARIABLES TAB (CEL Variables) ───────────────────────────────────

    get filteredCelVariables() {
        let vars = this.props.symbols?.cel_variables || [];

        // Apply value type filter
        if (this.state.valueTypeFilter) {
            vars = vars.filter((v) => v.value_type === this.state.valueTypeFilter);
        }

        // Apply category filter
        if (this.state.categoryFilter) {
            vars = vars.filter((v) => v.category === this.state.categoryFilter);
        }

        // Apply search query
        if (this.state.searchQuery) {
            const q = this.state.searchQuery.toLowerCase();
            vars = vars.filter(
                (v) =>
                    v.name.toLowerCase().includes(q) ||
                    (v.label && v.label.toLowerCase().includes(q)) ||
                    (v.description && v.description.toLowerCase().includes(q))
            );
        }

        return vars;
    }

    get availableCategories() {
        const vars = this.props.symbols?.cel_variables || [];
        const categories = new Set();
        for (const v of vars) {
            if (v.category) {
                categories.add(v.category);
            }
        }
        return Array.from(categories).sort();
    }

    get valueTypeOptions() {
        return [
            {value: "", label: "All Types"},
            {value: "boolean", label: "Boolean"},
            {value: "number", label: "Number"},
            {value: "string", label: "Text"},
            {value: "date", label: "Date"},
            {value: "money", label: "Money"},
            {value: "list", label: "List"},
        ];
    }

    // ─── LIBRARY TAB ─────────────────────────────────────────────────────

    get filteredLibrary() {
        let exprs = this.props.symbols?.library || [];

        // Apply search query
        if (this.state.searchQuery) {
            const q = this.state.searchQuery.toLowerCase();
            exprs = exprs.filter(
                (e) =>
                    e.name.toLowerCase().includes(q) ||
                    (e.code && e.code.toLowerCase().includes(q)) ||
                    (e.description && e.description.toLowerCase().includes(q))
            );
        }

        return exprs;
    }

    // ─── FUNCTIONS TAB ───────────────────────────────────────────────────

    get filteredFunctions() {
        if (!this.props.symbols?.functions) {
            return [];
        }

        const query = this.state.searchQuery.toLowerCase();
        if (!query) {
            return this.props.symbols.functions;
        }

        return this.props.symbols.functions.filter(
            (f) => f.name.toLowerCase().includes(query) || f.doc?.toLowerCase().includes(query)
        );
    }

    // ─── UI INTERACTIONS ─────────────────────────────────────────────────

    /**
     * Stop mouse events from propagating to parent Odoo form handlers
     * and prevent focus theft from the CodeMirror editor.
     *
     * Without stopPropagation, clicks get intercepted by Odoo's form
     * event handlers. Without preventDefault on mousedown, clicking
     * any item steals focus from CodeMirror, so insertSymbol dispatches
     * to a blurred editor (which silently fails or inserts at position 0).
     */
    onBrowserClick(ev) {
        ev.stopPropagation();
    }

    onBrowserMousedown(ev) {
        // Allow default for inputs/selects (search box, filter dropdowns)
        const tag = ev.target.tagName;
        if (tag !== "INPUT" && tag !== "SELECT" && tag !== "TEXTAREA") {
            ev.preventDefault();
        }
        ev.stopPropagation();
    }

    toggleVariable(varName) {
        if (this.state.expandedVariables.has(varName)) {
            this.state.expandedVariables.delete(varName);
        } else {
            this.state.expandedVariables.add(varName);
        }
    }

    isVariableExpanded(varName) {
        return this.state.expandedVariables.has(varName);
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
    }

    onValueTypeChange(ev) {
        this.state.valueTypeFilter = ev.target.value;
    }

    onCategoryChange(ev) {
        this.state.categoryFilter = ev.target.value;
    }

    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    /**
     * Check if key event is an activation key (Enter or Tab).
     * Prevents default Tab behavior to allow using Tab as selection.
     */
    isActivationKey(ev) {
        if (ev.key === "Enter" || ev.key === "Tab") {
            ev.preventDefault();
            return true;
        }
        return false;
    }

    // ─── INSERT METHODS ──────────────────────────────────────────────────

    insertVariable(varName) {
        this.props.onInsert(varName);
    }

    insertField(varName, fieldName) {
        this.props.onInsert(`${varName}.${fieldName}`);
    }

    insertCelVariable(variable) {
        // Insert the full CEL expression
        this.props.onInsert(variable.cel_expression);
    }

    insertLibraryExpression(expr) {
        // Insert the full CEL expression
        this.props.onInsert(expr.cel_expression);
    }

    insertFunction(func) {
        // Insert function with parentheses
        const text = func.name + "()";
        this.props.onInsert(text);
    }

    // ─── ICONS ───────────────────────────────────────────────────────────

    getFieldTypeIcon(fieldType) {
        switch (fieldType) {
            case "char":
            case "text":
            case "string":
                return "fa-font";
            case "integer":
            case "float":
            case "monetary":
            case "number":
            case "money":
                return "fa-hashtag";
            case "boolean":
                return "fa-toggle-on";
            case "date":
            case "datetime":
                return "fa-calendar";
            case "selection":
                return "fa-list";
            case "many2one":
                return "fa-link";
            case "list":
                return "fa-list-ul";
            default:
                return "fa-circle";
        }
    }

    getVariableIcon(variable) {
        if (variable.iterable) {
            return "fa-layer-group";
        }
        return "fa-cube";
    }

    getExpressionTypeIcon(exprType) {
        switch (exprType) {
            case "eligibility":
                return "fa-check-circle";
            case "benefit":
                return "fa-coins";
            case "compliance":
                return "fa-clipboard-check";
            case "scoring":
                return "fa-star";
            case "validation":
                return "fa-shield";
            default:
                return "fa-code";
        }
    }

    getExpressionTypeBadgeClass(exprType) {
        switch (exprType) {
            case "eligibility":
                return "bg-success";
            case "benefit":
                return "bg-info";
            case "compliance":
                return "bg-warning";
            case "scoring":
                return "bg-primary";
            case "validation":
                return "bg-secondary";
            default:
                return "bg-light text-dark";
        }
    }
}
