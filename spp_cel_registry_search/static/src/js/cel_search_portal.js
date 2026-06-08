/** @odoo-module **/

/**
 * CEL Search Portal Component
 *
 * Search interface for the registry using CEL expressions.
 * Uses the shared CelEditor component for expression editing.
 *
 * Features:
 * - CEL expression editor with syntax highlighting
 * - Search triggered only on button click
 * - Results displayed in a list
 * - Profile selection (Individuals/Groups)
 */

import {Component, onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";

import {CelEditor} from "@spp_cel_widget/js/cel_editor";

const SEARCH_RESULT_LIMIT = 50;

export class CelSearchPortal extends Component {
    static template = "spp_cel_registry_search.CelSearchPortal";
    static components = {CelEditor};
    static props = {
        "*": true,
    };

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");

        this.editorApi = null;

        onWillStart(() => this._checkAccess());

        this.state = useState({
            profile: "registry_individuals",
            celExpression: "",
            isSearching: false,
            hasSearched: false,
            results: [],
            totalCount: 0,
            hasMoreResults: false,
            validation: null,
            currentPage: 1,
        });
    }

    async _checkAccess() {
        const allowed = await this.orm.call(
            "spp.cel.service",
            "check_search_access",
            []
        );
        if (!allowed) {
            this.notification.add(
                _t("You do not have permission to access Advanced Search."),
                {type: "danger"}
            );
            this.action.doAction("mail.action_discuss", {clearBreadcrumbs: true});
        }
    }

    onEditorReady(api) {
        this.editorApi = api;
    }

    onProfileChange(ev) {
        this.state.profile = ev.target.value;

        // Re-validate with new profile if there's an expression
        if (this.state.celExpression && this.editorApi) {
            this.editorApi.forceValidate();
        }
    }

    onEditorChange(value) {
        this.state.celExpression = value;
    }

    onValidation(result) {
        this.state.validation = result;
    }

    async performSearch(page = 1) {
        const expression = this.state.celExpression.trim();

        if (!expression) {
            this.notification.add(_t("Please enter a CEL expression to search."), {
                type: "warning",
            });
            return;
        }

        if (this.state.validation && !this.state.validation.valid) {
            this.notification.add(
                _t("Please fix the expression errors before searching."),
                {
                    type: "warning",
                }
            );
            return;
        }

        this.state.isSearching = true;
        this.state.hasSearched = true;

        const offset = (page - 1) * SEARCH_RESULT_LIMIT;

        try {
            // Request preview records directly from backend to avoid JSON serialization
            // issues with SQL subquery domains
            const result = await this.orm.call(
                "spp.cel.service",
                "compile_expression",
                [],
                {
                    expression: expression,
                    profile: this.state.profile,
                    limit: SEARCH_RESULT_LIMIT,
                    offset: offset,
                    fields: [
                        "id",
                        "name",
                        "is_group",
                        "phone_number_ids",
                        "email",
                        "registration_date",
                        "disabled",
                    ],
                }
            );

            if (result.error) {
                this.notification.add(result.error, {type: "danger"});
                this.state.hasSearched = false;
                this.state.results = [];
                this.state.totalCount = 0;
                return;
            }

            const count = result.count || 0;
            const records = result.preview_records || [];

            this.state.results = records;
            this.state.totalCount = count;
            this.state.currentPage = page;
            this.state.hasMoreResults = count > offset + records.length;
        } catch (error) {
            console.error("[CelSearchPortal] Search error:", error);
            this.notification.add(
                _t("Search failed. Please try again or check your expression."),
                {
                    type: "danger",
                }
            );
            this.state.hasSearched = false;
            this.state.results = [];
            this.state.totalCount = 0;
        } finally {
            this.state.isSearching = false;
        }
    }

    goToPage(page) {
        this.performSearch(page);
    }

    togglePhones(ev, result) {
        result._showAllPhones = !result._showAllPhones;
    }

    get totalPages() {
        return Math.ceil(this.state.totalCount / SEARCH_RESULT_LIMIT);
    }

    get showingFrom() {
        return (this.state.currentPage - 1) * SEARCH_RESULT_LIMIT + 1;
    }

    get showingTo() {
        return Math.min(
            this.state.currentPage * SEARCH_RESULT_LIMIT,
            this.state.totalCount
        );
    }

    clearSearch() {
        this.state.celExpression = "";
        this.state.hasSearched = false;
        this.state.results = [];
        this.state.totalCount = 0;
        this.state.hasMoreResults = false;
        this.state.validation = null;
        this.state.currentPage = 1;

        if (this.editorApi) {
            this.editorApi.clear();
        }
    }

    async openRegistrant(id, isGroup) {
        const viewRef = isGroup
            ? "spp_registry.view_groups_form_membership"
            : "spp_registry.view_individuals_form";

        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.partner",
            res_id: id,
            views: [[false, "form"]],
            view_mode: "form",
            target: "current",
            context: {
                form_view_ref: viewRef,
            },
        });
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

    get canSearch() {
        return (
            this.state.celExpression.trim() &&
            (!this.state.validation || this.state.validation.valid)
        );
    }

    get validationStatusClass() {
        if (!this.state.validation) {
            return "";
        }
        return this.state.validation.valid ? "text-success" : "text-danger";
    }

    get validationIcon() {
        if (!this.state.validation) {
            return "";
        }
        return this.state.validation.valid ? "fa-check-circle" : "fa-times-circle";
    }

    get validationMessage() {
        if (!this.state.validation) {
            return "";
        }
        if (this.state.validation.valid) {
            const count = this.state.validation.matching_count;
            if (count !== null && count !== undefined) {
                return _t("%s match(es)", count.toLocaleString());
            }
            return _t("Valid expression");
        }
        const firstError = this.state.validation.errors?.[0];
        return firstError?.message || _t("Invalid expression");
    }
}

registry
    .category("actions")
    .add("spp_cel_registry_search.cel_search_portal", CelSearchPortal);
