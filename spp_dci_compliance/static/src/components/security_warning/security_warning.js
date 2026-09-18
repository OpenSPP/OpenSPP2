/** @odoo-module **/

import {Component, useState, onWillStart} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {rpc} from "@web/core/network/rpc";
import {user} from "@web/core/user";
import {useService} from "@web/core/utils/hooks";
import {_t} from "@web/core/l10n/translation";
import {Dropdown} from "@web/core/dropdown/dropdown";
import {DropdownItem} from "@web/core/dropdown/dropdown_item";

/**
 * Systray component that displays DCI security warnings.
 * Shows a red warning icon when development/testing security settings are enabled.
 * Only system administrators are told: they are the ones who can change the settings.
 */
export class DCISecurityWarning extends Component {
    static template = "spp_dci_compliance.SecurityWarning";
    static components = {Dropdown, DropdownItem};
    static props = {};

    setup() {
        this.actionService = useService("action");
        this.state = useState({
            hasWarnings: false,
            warningCount: 0,
            warnings: [],
            message: "",
            loaded: false,
        });

        onWillStart(async () => {
            if (await user.hasGroup("base.group_system")) {
                await this.loadWarnings();
            } else {
                this.state.loaded = true;
            }
        });
    }

    async loadWarnings() {
        try {
            const result = await rpc("/dci/security/warnings", {});
            this.state.hasWarnings = result.has_warnings;
            this.state.warningCount = result.warning_count;
            this.state.warnings = result.warnings || [];
            this.state.message = result.message;
            this.state.loaded = true;
        } catch (error) {
            console.error("Failed to load DCI security warnings:", error);
            this.state.loaded = true;
        }
    }

    get warningLabel() {
        return _t("%s DCI security warnings", this.state.warningCount);
    }

    openSettings() {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "ir.config_parameter",
            views: [
                [false, "list"],
                [false, "form"],
            ],
            domain: [["key", "=like", "dci.%"]],
            name: _t("DCI Configuration Parameters"),
        });
    }
}

const systrayItem = {
    Component: DCISecurityWarning,
    // Always displayed; the component itself decides visibility
    isDisplayed: () => true,
};

registry
    .category("systray")
    .add("spp_dci_compliance.SecurityWarning", systrayItem, {sequence: 1});
