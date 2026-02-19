/** @odoo-module **/

/**
 * Registry Search Portal Component
 *
 * Search-first interface for the registry to protect beneficiary privacy.
 * Users must search to find registrants rather than browsing a full list.
 *
 * Features:
 * - Quick search with minimum character requirement
 * - Advanced filters (type, phone, email, dates)
 * - Recently viewed registrants (personal to user)
 * - Create new registrant buttons
 * - Accessibility support (ARIA, keyboard navigation)
 */

import {Component, onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

const SEARCH_RESULT_LIMIT = 50;

export class RegistrySearchPortal extends Component {
    static template = "spp_registry_search.SearchPortal";
    static props = {
        // Client action props
        "*": true,
    };

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");

        this.state = useState({
            searchTerm: "",
            searchType: "all", // All, individuals, groups
            isSearching: false,
            hasSearched: false,
            results: [],
            totalCount: 0,
            hasMoreResults: false,
            recentlyViewed: [],
            showAdvanced: false,
            canCreate: false,
            canEdit: false,
            advancedFilters: {
                registrationDateFrom: "",
                registrationDateTo: "",
            },
        });

        // Minimum characters before search triggers
        this.minSearchChars = 3;
        this.searchDebounceMs = 300;
        this._searchTimeout = null;

        onWillStart(async () => {
            // Check permissions via Python methods
            try {
                const [canCreate, canEdit] = await Promise.all([
                    this.orm.call("res.partner", "check_access_rights", [
                        "create",
                        false,
                    ]),
                    this.orm.call(
                        "spp.registry.view.history",
                        "check_registrant_edit_permission",
                        []
                    ),
                ]);
                this.state.canCreate = canCreate;
                this.state.canEdit = canEdit;
            } catch {
                this.state.canCreate = false;
                this.state.canEdit = false;
            }

            await this.loadRecentlyViewed();
        });
    }

    async loadRecentlyViewed() {
        try {
            this.state.recentlyViewed = await this.orm.call(
                "spp.registry.view.history",
                "get_recent_registrants",
                [10]
            );
        } catch {
            // Silently fail - recently viewed is not critical
            this.state.recentlyViewed = [];
        }
    }

    onSearchInput(ev) {
        this.state.searchTerm = ev.target.value;

        // Clear previous timeout
        if (this._searchTimeout) {
            clearTimeout(this._searchTimeout);
        }

        // Debounce search
        if (this.state.searchTerm.length >= this.minSearchChars) {
            this._searchTimeout = setTimeout(() => {
                this.performSearch();
            }, this.searchDebounceMs);
        } else if (this.state.searchTerm.length === 0) {
            this.clearSearch();
        }
    }

    onSearchTypeChange(ev) {
        this.state.searchType = ev.target.value;
        if (this.state.hasSearched) {
            this.performSearch();
        }
    }

    onSearchKeydown(ev) {
        if (ev.key === "Enter" && this.state.searchTerm.length >= this.minSearchChars) {
            ev.preventDefault();
            this.performSearch();
        }
    }

    async performSearch() {
        if (this.state.searchTerm.length < this.minSearchChars) {
            this.notification.add(
                _t(
                    "Please enter at least %s characters to search.",
                    this.minSearchChars
                ),
                {
                    type: "warning",
                }
            );
            return;
        }

        this.state.isSearching = true;
        this.state.hasSearched = true;

        try {
            // Build domain
            const domain = this._buildSearchDomain();

            // Search registrants
            const fields = [
                "id",
                "name",
                "is_group",
                "phone",
                "email",
                "registration_date",
                "disabled",
            ];
            const results = await this.orm.searchRead("res.partner", domain, fields, {
                limit: SEARCH_RESULT_LIMIT,
            });

            this.state.results = results;
            this.state.totalCount = results.length;
            // Indicate if there may be more results beyond the limit
            this.state.hasMoreResults = results.length >= SEARCH_RESULT_LIMIT;
        } catch {
            this.notification.add(_t("Search failed. Please try again."), {
                type: "danger",
            });
        } finally {
            this.state.isSearching = false;
        }
    }

    _buildSearchDomain() {
        const searchTerm = this.state.searchTerm;

        // Base domain: must be a registrant and match search term
        // Using OR for main search terms, AND for advanced filters
        // Note: ID numbers use exact match (=), other fields use partial match (ilike)
        const domain = [
            ["is_registrant", "=", true],
            "|",
            "|",
            "|",
            ["name", "ilike", searchTerm],
            ["reg_ids.value", "=", searchTerm], // Exact match for ID numbers
            ["phone_number_ids.phone_no", "ilike", searchTerm],
            ["email", "ilike", searchTerm],
        ];

        // Filter by type (AND)
        if (this.state.searchType === "individuals") {
            domain.push(["is_group", "=", false]);
        } else if (this.state.searchType === "groups") {
            domain.push(["is_group", "=", true]);
        }

        // Advanced filters (AND logic - all conditions must be met)
        if (this.state.showAdvanced) {
            if (this.state.advancedFilters.registrationDateFrom) {
                domain.push([
                    "registration_date",
                    ">=",
                    this.state.advancedFilters.registrationDateFrom,
                ]);
            }
            if (this.state.advancedFilters.registrationDateTo) {
                domain.push([
                    "registration_date",
                    "<=",
                    this.state.advancedFilters.registrationDateTo,
                ]);
            }
        }

        return domain;
    }

    clearSearch() {
        this.state.searchTerm = "";
        this.state.hasSearched = false;
        this.state.results = [];
        this.state.totalCount = 0;
        this.state.hasMoreResults = false;
    }

    toggleAdvanced() {
        this.state.showAdvanced = !this.state.showAdvanced;
    }

    clearAdvancedFilters() {
        this.state.advancedFilters = {
            registrationDateFrom: "",
            registrationDateTo: "",
        };
        // Re-run search if already searched
        if (this.state.hasSearched) {
            this.performSearch();
        }
    }

    onAdvancedFilterChange(filterName, ev) {
        if (ev.target.type === "checkbox") {
            this.state.advancedFilters[filterName] = ev.target.checked;
        } else {
            this.state.advancedFilters[filterName] = ev.target.value;
        }
    }

    onRecentCardKeydown(ev, id, isGroup) {
        // Handle Enter and Space for keyboard accessibility
        if (ev.key === "Enter" || ev.key === " ") {
            ev.preventDefault();
            this.openRegistrant(id, isGroup);
        }
    }

    async openRegistrant(id, isGroup) {
        // Record the view
        try {
            await this.orm.call("spp.registry.view.history", "record_view", [id]);
        } catch {
            // Silently fail - view recording is not critical
        }

        // Determine which form view to use
        const viewRef = isGroup
            ? "spp_registry.view_groups_form_membership"
            : "spp_registry.view_individuals_form";

        // Build context - readonly for users without edit access
        const context = {
            form_view_ref: viewRef,
        };
        if (!this.state.canEdit) {
            context.edit = false;
            context.create = false;
            context.archive = false;
        }

        // Open the form view
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: id,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
            context,
        });
    }

    async createNewIndividual() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
            context: {
                default_is_registrant: true,
                default_is_group: false,
                form_view_ref: "spp_registry.view_individuals_form",
            },
        });
    }

    async createNewGroup() {
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
            context: {
                default_is_registrant: true,
                default_is_group: true,
                form_view_ref: "spp_registry.view_groups_form_membership",
            },
        });
    }

    async clearHistory() {
        try {
            await this.orm.call("spp.registry.view.history", "clear_user_history", []);
            this.state.recentlyViewed = [];
            this.notification.add(_t("View history cleared."), {type: "success"});
        } catch {
            this.notification.add(_t("Failed to clear history."), {type: "danger"});
        }
    }

    getRegistrantIcon(isGroup) {
        return isGroup ? "fa-users" : "fa-user";
    }

    getRegistrantTypeLabel(isGroup) {
        return isGroup ? _t("Group") : _t("Individual");
    }

    formatDate(dateStr) {
        if (!dateStr) {
            return "";
        }
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString();
        } catch {
            return dateStr;
        }
    }

    formatRelativeTime(dateStr) {
        if (!dateStr) {
            return "";
        }
        try {
            // Odoo returns datetime in UTC without timezone indicator
            // Append 'Z' to parse as UTC
            const utcDateStr = dateStr.includes("Z")
                ? dateStr
                : dateStr.replace(" ", "T") + "Z";
            const date = new Date(utcDateStr);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            const diffDays = Math.floor(diffMs / 86400000);

            if (diffMins < 1) {
                return _t("just now");
            }
            if (diffMins < 60) {
                return _t("%s min ago", diffMins);
            }
            if (diffHours < 24) {
                return _t("%s hour(s) ago", diffHours);
            }
            if (diffDays < 7) {
                return _t("%s day(s) ago", diffDays);
            }
            return this.formatDate(dateStr);
        } catch {
            return dateStr;
        }
    }
}

// Register as client action
registry
    .category("actions")
    .add("spp_registry_search.search_portal", RegistrySearchPortal);
