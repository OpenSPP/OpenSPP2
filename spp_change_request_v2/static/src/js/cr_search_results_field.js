/** @odoo-module **/

import {Component, onMounted, onPatched, onWillUnmount, useRef} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

const ROW_SELECTOR = ".o_cr_search_result";
const PAGER_SELECTOR = ".o_cr_page_prev, .o_cr_page_next";
const STATUS_SELECTOR = ".o_cr_search_status";
// Live region hosted by the wizard form, outside the results block, so it
// already exists when the first results arrive and outlives a selection
// (see create_wizard_views.xml).
const LIVE_REGION_SELECTOR = ".o_cr_search_live";
const CLEAR_BUTTON_SELECTOR = "button[name='action_clear_registrant']";
// Upper bound on waiting for the form to re-render after a record update.
const RENDER_WAIT_MS = 2000;
// A live region filled in the same tick it is inserted is not announced, so
// the first write after mount waits a little.
const MOUNT_ANNOUNCE_DELAY_MS = 150;

/**
 * Custom widget that renders HTML search results and handles row selection
 * and paging by mouse or keyboard. The rows are options of a listbox: Enter
 * or Space selects the focused row, ArrowUp/ArrowDown/Home/End move between
 * rows. Selecting a row writes the partner ID to the _selected_partner_id
 * bridge field, which triggers a server-side onchange to set registrant_id;
 * paging writes _search_page the same way.
 */
export class CrSearchResultsField extends Component {
    static template = "spp_change_request_v2.CrSearchResultsField";
    static props = {...standardFieldProps};

    setup() {
        this.containerRef = useRef("container");
        // HTML as last rendered, to tell a re-render with new results from
        // any other patch of the form.
        this.renderedHtml = null;
        // Focus to restore once the results have been re-rendered after a page
        // change: the selectors to try in order, and the element that had
        // focus when the page change started.
        this.pendingFocus = null;
        onMounted(() => {
            // One delegated listener each: the server re-renders the whole
            // results blob on every search or page change, so per-row handlers
            // would have to be re-attached after each patch.
            const el = this.containerRef.el;
            el.addEventListener("click", (ev) => this._onClick(ev));
            el.addEventListener("keydown", (ev) => this._onKeydown(ev));
            el.addEventListener("focusin", (ev) => this._onFocusin(ev));
            this.renderedHtml = this.htmlContent;
            this.formEl = el.closest(".o_form_view");
            setTimeout(() => this._announceStatus(), MOUNT_ANNOUNCE_DELAY_MS);
        });
        onPatched(() => {
            // Compared as text: the record may hand out a new Markup object
            // for an unchanged value.
            if (String(this.htmlContent) === String(this.renderedHtml)) {
                return;
            }
            this.renderedHtml = this.htmlContent;
            this._announceStatus();
            this._applyPendingFocus();
        });
        // The results go away when the search is cleared or a registrant is
        // chosen; the range text must not linger in the live region. A
        // selection writes its own confirmation afterwards.
        onWillUnmount(() => this._announce(""));
    }

    get htmlContent() {
        return this.props.record.data[this.props.name] || "";
    }

    get rows() {
        return [...this.containerRef.el.querySelectorAll(ROW_SELECTOR)];
    }

    _onClick(ev) {
        const row = ev.target.closest(ROW_SELECTOR);
        if (row) {
            ev.preventDefault();
            ev.stopPropagation();
            this._selectRow(row);
            return;
        }
        const pager = ev.target.closest(PAGER_SELECTOR);
        if (pager && !pager.disabled) {
            ev.preventDefault();
            ev.stopPropagation();
            this._goToPage(pager);
        }
    }

    _onKeydown(ev) {
        // The pager buttons are native buttons: Enter and Space already click
        // them. Keys with a modifier belong to the browser or to Odoo's hotkeys:
        // Ctrl+Enter (Cmd+Enter on macOS) is the dialog's hotkey for its first
        // footer button, which is Cancel while no registrant is chosen, so it
        // discards the wizard rather than selecting a row. That is standard
        // Odoo dialog behaviour and is deliberately not intercepted here.
        const row = ev.target.closest(ROW_SELECTOR);
        if (!row || ev.altKey || ev.ctrlKey || ev.metaKey) {
            return;
        }
        const rows = this.rows;
        const index = rows.indexOf(row);
        let target = null;
        switch (ev.key) {
            case "Enter":
            case " ":
                ev.preventDefault();
                ev.stopPropagation();
                this._selectRow(row);
                return;
            case "ArrowDown":
                target = rows[Math.min(index + 1, rows.length - 1)];
                break;
            case "ArrowUp":
                target = rows[Math.max(index - 1, 0)];
                break;
            case "Home":
                target = rows[0];
                break;
            case "End":
                target = rows[rows.length - 1];
                break;
            default:
                return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        target.focus();
    }

    /**
     * Roving tabindex: the list is a single Tab stop, and the row that holds
     * focus is the one Tab returns to. Handled on focusin so it also covers
     * focus that arrives by mouse or from assistive technology.
     */
    _onFocusin(ev) {
        const row = ev.target.closest(ROW_SELECTOR);
        if (!row) {
            return;
        }
        for (const other of this.rows) {
            other.tabIndex = other === row ? 0 : -1;
        }
    }

    async _selectRow(row) {
        const partnerId = parseInt(row.dataset.partnerId, 10);
        if (!partnerId) {
            return;
        }
        const label = row.getAttribute("aria-label") || row.dataset.partnerName;
        const before = document.activeElement;
        // Setting the registrant hides the results block, which unmounts this
        // widget, so focus is handed to the button that brings the search back,
        // and the choice is confirmed in the live region after the focus move
        // so a screen reader speaks both.
        const formEl = this.formEl;
        await this.props.record.update({_selected_partner_id: partnerId});
        await this._focusWhenRendered(formEl, CLEAR_BUTTON_SELECTOR, before);
        this._announce(_t("Selected: %s", label));
    }

    async _goToPage(button) {
        const page = parseInt(button.dataset.page, 10);
        if (isNaN(page) || page < 0) {
            return;
        }
        // Keep focus on the button that was pressed so it can be pressed again;
        // on the last page it is disabled, so fall back to the other one, then
        // to the first row. The focus is applied by onPatched once the new
        // results are in the DOM, however long the onchange takes.
        const pressed = button.classList.contains("o_cr_page_next")
            ? ".o_cr_page_next"
            : ".o_cr_page_prev";
        const other =
            pressed === ".o_cr_page_next" ? ".o_cr_page_prev" : ".o_cr_page_next";
        this.pendingFocus = {
            selectors: [pressed, other, ROW_SELECTOR],
            before: document.activeElement,
        };
        await this.props.record.update({_search_page: page});
        // The server may answer with the same HTML (page clamped to the last
        // one), in which case no patch with new results ever comes. Only then
        // is the focus applied here; while a re-render is still due, onPatched
        // owns it, otherwise the old button would be focused and then removed.
        await new Promise(requestAnimationFrame);
        if (String(this.htmlContent) === String(this.renderedHtml)) {
            this._applyPendingFocus();
        }
    }

    /**
     * True when the user has put focus somewhere of their own (for example
     * back in the search box) while a request was in flight: focus is then
     * left alone. Focus that is still where it was when the action started
     * (a screen reader in browse mode activates a row without moving system
     * focus) or that was lost with the removed results (it sits on body) does
     * not count as moved.
     */
    _userMovedFocus(before) {
        const active = document.activeElement;
        if (!active || active === document.body || active === before) {
            return false;
        }
        const el = this.containerRef.el;
        return !(el && el.contains(active));
    }

    _applyPendingFocus() {
        const pending = this.pendingFocus;
        this.pendingFocus = null;
        const el = this.containerRef.el;
        if (!pending || !el || this._userMovedFocus(pending.before)) {
            return;
        }
        for (const selector of pending.selectors) {
            const target = el.querySelector(selector);
            if (target && !target.disabled) {
                target.focus();
                return;
            }
        }
    }

    /**
     * Focus the element matching the selector, polling animation frames
     * because it only appears once the form has re-rendered with the onchange
     * result.
     */
    async _focusWhenRendered(root, selector, before) {
        if (!root) {
            return;
        }
        const deadline = Date.now() + RENDER_WAIT_MS;
        while (Date.now() < deadline) {
            const target = root.querySelector(selector);
            if (target) {
                // Decided only now that the form has re-rendered: an element
                // the user moved to may have gone with the results (the search
                // box is hidden once a registrant is set), in which case focus
                // sits on body and is handed over after all.
                if (!this._userMovedFocus(before)) {
                    target.focus();
                }
                return;
            }
            await new Promise(requestAnimationFrame);
        }
    }

    /**
     * Mirror the range summary ("1-10 of 23") or the empty-result message into
     * the form's live region, so screen readers hear the outcome of a search
     * or a page change.
     */
    _announceStatus() {
        const el = this.containerRef.el;
        if (!el) {
            return;
        }
        const status = el.querySelector(STATUS_SELECTOR);
        this._announce(status ? status.textContent.trim() : "");
    }

    /**
     * Write into the live region, clearing it first so that an unchanged text
     * (a refined search with the same range) is announced again.
     */
    _announce(text) {
        const region = this.formEl && this.formEl.querySelector(LIVE_REGION_SELECTOR);
        if (!region) {
            return;
        }
        region.textContent = "";
        if (text) {
            requestAnimationFrame(() => {
                region.textContent = text;
            });
        }
    }
}

export const crSearchResultsField = {
    component: CrSearchResultsField,
    displayName: _t("CR Search Results"),
    supportedTypes: ["html"],
};

registry.category("fields").add("cr_search_results", crSearchResultsField);
