/** @odoo-module **/

import {Component, onMounted, onWillUnmount, useEffect, useRef, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

/**
 * Variable Picker Component
 *
 * A searchable, categorized dropdown for selecting variables in Logic Studio.
 * Features:
 * - Search with synonyms
 * - Recently used variables
 * - Category grouping
 * - Keyboard navigation
 * - Data availability indicators
 */
export class VariablePicker extends Component {
    static template = "spp_studio.VariablePicker";
    static props = {
        variables: {type: Array, optional: false},
        selectedValue: {type: [Number, Boolean], optional: true},
        placeholder: {type: String, optional: true},
        onSelect: {type: Function, optional: false},
        readonly: {type: Boolean, optional: true},
    };
    static defaultProps = {
        selectedValue: false,
        placeholder: "Select a variable...",
        readonly: false,
    };

    setup() {
        this.state = useState({
            searchTerm: "",
            isOpen: false,
            highlightedIndex: -1,
            recentlyUsed: [],
            expandedCategories: new Set(),
            scopeFilter: "all", // All, individual, group, shared
        });

        this.inputRef = useRef("vpInput");
        this.dropdownRef = useRef("vpDropdown");
        this.orm = useService("orm");
        this.action = useService("action");

        // Debounce search
        this.searchDebounceTimer = null;
        this.DEBOUNCE_DELAY = 150;

        // Load recently used on mount
        onMounted(() => {
            this.loadRecentlyUsed();
            this.updateSearchTerm();
            document.addEventListener("click", this.handleClickOutside);
        });

        onWillUnmount(() => {
            document.removeEventListener("click", this.handleClickOutside);
            if (this.searchDebounceTimer) {
                clearTimeout(this.searchDebounceTimer);
            }
        });

        // Update search term when selectedValue changes
        useEffect(
            () => {
                this.updateSearchTerm();
            },
            () => [this.props.selectedValue]
        );
    }

    /**
     * Update search term based on selected value
     */
    updateSearchTerm() {
        if (this.props.selectedValue) {
            const selected = this.props.variables.find((v) => v.id === this.props.selectedValue);
            if (selected) {
                this.state.searchTerm = selected.label || selected.name;
            }
        } else {
            this.state.searchTerm = "";
        }
    }

    /**
     * Load recently used variables from localStorage
     */
    loadRecentlyUsed() {
        const key = "logic_studio_recent_variables";
        try {
            const stored = localStorage.getItem(key);
            this.state.recentlyUsed = stored ? JSON.parse(stored) : [];
        } catch (e) {
            console.warn("Failed to load recently used variables", e);
            this.state.recentlyUsed = [];
        }
    }

    /**
     * Add a variable to recently used list
     */
    addToRecentlyUsed(variableId) {
        const key = "logic_studio_recent_variables";
        let recent = [...this.state.recentlyUsed];

        // Remove if already exists
        recent = recent.filter((id) => id !== variableId);

        // Add to front
        recent.unshift(variableId);

        // Keep only last 5
        recent = recent.slice(0, 5);

        // Update state and localStorage
        this.state.recentlyUsed = recent;
        try {
            localStorage.setItem(key, JSON.stringify(recent));
        } catch (e) {
            console.warn("Failed to save recently used variables", e);
        }
    }

    /**
     * Get recently used variables
     */
    get recentlyUsedVariables() {
        const vars = this.state.recentlyUsed
            .map((id) => this.props.variables.find((v) => v.id === id))
            .filter((v) => v !== undefined);
        return this.filterByScope(vars);
    }

    /**
     * Filter variables based on search term
     */
    get filteredVariables() {
        const baseVars = this.filterByScope(this.props.variables);

        if (!this.state.searchTerm) {
            return baseVars;
        }

        const terms = this.state.searchTerm.toLowerCase().split(/\s+/);

        return baseVars.filter((v) => {
            const searchableText = [v.name || "", v.label || "", v.synonyms || "", v.cel_accessor || ""]
                .join(" ")
                .toLowerCase();

            // Variable matches if it contains all search terms
            return terms.every((term) => searchableText.includes(term));
        });
    }

    /**
     * Group variables by category
     */
    get variablesByCategory() {
        const grouped = {};
        const base = this.filterByScope(this.props.variables);
        const variables = this.state.searchTerm ? this.filteredVariables : base;

        for (const variable of variables) {
            // Constants are handled in a dedicated section
            if (variable.source_type === "constant") {
                continue;
            }

            const catId = variable.category_id?.[0] || 0;
            const catName = variable.category_id?.[1] || "Other";

            if (!grouped[catId]) {
                grouped[catId] = {
                    id: catId,
                    name: catName,
                    icon: this.getCategoryIcon(catName),
                    variables: [],
                };
            }
            grouped[catId].variables.push(variable);
        }

        // Sort categories by name
        const categories = Object.values(grouped);
        categories.sort((a, b) => {
            if (a.id === 0) return 1; // "Other" goes last
            if (b.id === 0) return -1;
            return a.name.localeCompare(b.name);
        });

        return categories;
    }

    /**
     * Variables that are constants/parameters
     */
    get constantVariables() {
        const base = this.state.searchTerm ? this.filteredVariables : this.filterByScope(this.props.variables);
        return base.filter((v) => v.source_type === "constant");
    }

    /**
     * Get icon for category based on name
     */
    getCategoryIcon(categoryName) {
        const iconMap = {
            Demographics: "fa-users",
            Family: "fa-home",
            Income: "fa-dollar",
            Assets: "fa-building",
            Health: "fa-heartbeat",
            Education: "fa-graduation-cap",
            Location: "fa-map-marker",
            Program: "fa-clipboard",
            Payment: "fa-money",
            Eligibility: "fa-check-circle",
        };

        for (const [key, icon] of Object.entries(iconMap)) {
            if (categoryName.toLowerCase().includes(key.toLowerCase())) {
                return icon;
            }
        }

        return "fa-folder";
    }

    /**
     * Get availability icon based on data source
     */
    getAvailabilityIcon(variable) {
        switch (variable.data_source) {
            case "local":
                return "✅";
            case "external":
                return "🔗";
            case "computed":
                return "⚙️";
            default:
                return "📊";
        }
    }

    /**
     * Get availability title (tooltip text)
     */
    getAvailabilityTitle(variable) {
        switch (variable.data_source) {
            case "local":
                return "Local data - Available immediately";
            case "external":
                return "External API - May require network call";
            case "computed":
                return "Computed - Calculated on demand";
            default:
                return "Data availability unknown";
        }
    }

    /**
     * Filter variables by scope (applies_to)
     * - all: no filter
     * - individual: individual + both
     * - group: group + both
     * - shared: both only
     */
    filterByScope(variables) {
        const scope = this.state.scopeFilter || "all";
        if (scope === "all") {
            return variables;
        }

        return variables.filter((v) => {
            const applies = v.applies_to || "both";
            if (scope === "individual") {
                return applies === "individual" || applies === "both";
            }
            if (scope === "group") {
                return applies === "group" || applies === "both";
            }
            if (scope === "shared") {
                return applies === "both";
            }
            return true;
        });
    }

    /**
     * Human-readable scope label
     */
    getScopeLabel(variable) {
        const applies = variable.applies_to || "both";
        switch (applies) {
            case "individual":
                return "Individual";
            case "group":
                return "Group";
            case "both":
                return "Shared";
            default:
                return "";
        }
    }

    /**
     * Human-readable source type label
     */
    getSourceTypeLabel(variable) {
        switch (variable.source_type) {
            case "field":
                return "Field";
            case "indicator":
                return "Indicator";
            case "scoring":
                return "Scoring";
            case "vocabulary":
                return "Vocabulary";
            case "computed":
                return "Computed";
            case "constant":
                return "Constant";
            case "aggregate":
                return "Aggregate";
            default:
                return "";
        }
    }

    /**
     * Toggle dropdown open/closed
     */
    toggleDropdown(ev) {
        if (this.props.readonly) {
            return;
        }

        ev.stopPropagation();
        this.state.isOpen = !this.state.isOpen;

        if (this.state.isOpen) {
            this.state.highlightedIndex = -1;
            // Focus input when opening
            setTimeout(() => {
                if (this.inputRef.el) {
                    this.inputRef.el.focus();
                }
            }, 0);
        }
    }

    /**
     * Handle search input
     */
    onSearchInput(ev) {
        const value = ev.target.value;

        // Debounce search
        if (this.searchDebounceTimer) {
            clearTimeout(this.searchDebounceTimer);
        }

        this.searchDebounceTimer = setTimeout(() => {
            this.state.searchTerm = value;
            this.state.highlightedIndex = -1;

            // Open dropdown if not already open
            if (!this.state.isOpen && value) {
                this.state.isOpen = true;
            }
        }, this.DEBOUNCE_DELAY);
    }

    /**
     * Handle keyboard navigation
     */
    onKeyDown(ev) {
        if (!this.state.isOpen) {
            // Open dropdown on arrow down
            if (ev.key === "ArrowDown") {
                ev.preventDefault();
                this.state.isOpen = true;
            }
            return;
        }

        const items = this.state.searchTerm ? this.filteredVariables : this.getAllVisibleItems();

        switch (ev.key) {
            case "ArrowDown":
                ev.preventDefault();
                this.state.highlightedIndex = Math.min(this.state.highlightedIndex + 1, items.length - 1);
                this.scrollToHighlighted();
                break;

            case "ArrowUp":
                ev.preventDefault();
                this.state.highlightedIndex = Math.max(this.state.highlightedIndex - 1, 0);
                this.scrollToHighlighted();
                break;

            case "Enter":
                ev.preventDefault();
                if (this.state.highlightedIndex >= 0 && items[this.state.highlightedIndex]) {
                    this.selectVariable(items[this.state.highlightedIndex]);
                }
                break;

            case "Escape":
                ev.preventDefault();
                this.state.isOpen = false;
                this.state.highlightedIndex = -1;
                if (this.inputRef.el) {
                    this.inputRef.el.blur();
                }
                break;
        }
    }

    /**
     * Get all visible items for keyboard navigation
     */
    getAllVisibleItems() {
        const items = [];
        const seen = new Set();

        // Add recently used if visible
        if (this.recentlyUsedVariables.length && !this.state.searchTerm) {
            for (const v of this.recentlyUsedVariables) {
                if (!seen.has(v.id)) {
                    seen.add(v.id);
                    items.push(v);
                }
            }
        }

        // Add constants section items when not searching
        if (this.constantVariables.length && !this.state.searchTerm) {
            for (const v of this.constantVariables) {
                if (!seen.has(v.id)) {
                    seen.add(v.id);
                    items.push(v);
                }
            }
        }

        // Add category items
        for (const category of this.variablesByCategory) {
            if (this.isCategoryExpanded(category.id) || this.state.searchTerm) {
                for (const v of category.variables) {
                    if (!seen.has(v.id)) {
                        seen.add(v.id);
                        items.push(v);
                    }
                }
            }
        }

        return items;
    }

    /**
     * Scroll to highlighted item
     */
    scrollToHighlighted() {
        setTimeout(() => {
            const dropdown = this.dropdownRef.el;
            if (!dropdown) return;

            const highlightedEl = dropdown.querySelector(".vp-item.highlighted");
            if (highlightedEl) {
                highlightedEl.scrollIntoView({
                    block: "nearest",
                    behavior: "smooth",
                });
            }
        }, 0);
    }

    /**
     * Check if item is highlighted
     */
    isHighlighted(variable) {
        const items = this.getAllVisibleItems();
        const index = items.findIndex((v) => v.id === variable.id);
        return index === this.state.highlightedIndex;
    }

    /**
     * Set current scope filter
     */
    setScopeFilter(scope) {
        if (this.state.scopeFilter === scope) {
            return;
        }
        this.state.scopeFilter = scope;
        this.state.highlightedIndex = -1;
    }

    /**
     * Select a variable
     */
    selectVariable(variable) {
        if (!variable) return;

        this.addToRecentlyUsed(variable.id);
        this.state.isOpen = false;
        this.state.searchTerm = variable.label || variable.name;
        this.state.highlightedIndex = -1;
        this.props.onSelect(variable);
    }

    /**
     * Toggle category expanded/collapsed
     */
    toggleCategory(categoryId) {
        if (this.state.expandedCategories.has(categoryId)) {
            this.state.expandedCategories.delete(categoryId);
        } else {
            this.state.expandedCategories.add(categoryId);
        }
        // Force re-render
        this.state.expandedCategories = new Set(this.state.expandedCategories);
    }

    /**
     * Check if category is expanded
     */
    isCategoryExpanded(categoryId) {
        return this.state.expandedCategories.has(categoryId);
    }

    /**
     * Handle click outside to close dropdown
     */
    handleClickOutside = (ev) => {
        const target = ev.target;
        const vpElement = target.closest(".variable-picker");

        if (!vpElement && this.state.isOpen) {
            this.state.isOpen = false;
            this.state.highlightedIndex = -1;
        }
    };

    /**
     * Open create variable dialog
     */
    async openCreateVariable(ev) {
        ev.preventDefault();
        ev.stopPropagation();

        this.state.isOpen = false;

        try {
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "spp.cel.variable",
                views: [[false, "form"]],
                target: "new",
                context: {
                    default_name: this.state.searchTerm || "",
                },
            });
        } catch (e) {
            console.error("Failed to open create variable dialog", e);
        }
    }

    /**
     * Clear selection
     */
    clearSelection(ev) {
        ev.stopPropagation();
        this.state.searchTerm = "";
        this.props.onSelect(null);
    }

    /**
     * Get display value for selected variable
     */
    get displayValue() {
        if (this.props.selectedValue) {
            const selected = this.props.variables.find((v) => v.id === this.props.selectedValue);
            return selected ? selected.label || selected.name : "";
        }
        return "";
    }
}

// Register as a field widget (Odoo 19 format)
registry.category("fields").add("variable_picker", {
    component: VariablePicker,
    supportedTypes: ["many2one", "integer"],
});
