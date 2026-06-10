/** @odoo-module **/

import {registry} from "@web/core/registry";
import {CharField} from "@web/views/fields/char/char_field";
import {Component, useState} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

/**
 * MaskedCharField - A field widget that displays masked PII values
 * with the ability to reveal the actual value for authorized users.
 *
 * Usage in XML:
 *   <field name="national_id" widget="masked_char"/>
 *
 * Options:
 *   - mask_pattern: Custom mask pattern (default: "****")
 *   - reveal_group: Security group required to reveal (default: any authenticated user)
 *   - audit_reveal: Log reveal actions (default: true)
 */
export class MaskedCharField extends CharField {
    static template = "spp_pii_encryption.MaskedCharField";
    static props = {
        ...CharField.props,
        maskPattern: {type: String, optional: true},
        revealGroup: {type: String, optional: true},
        auditReveal: {type: Boolean, optional: true},
    };

    setup() {
        super.setup();
        this.state = useState({
            isRevealed: false,
            isLoading: false,
        });
        this.rpc = useService("rpc");
        this.notification = useService("notification");
        this.user = useService("user");
    }

    get maskedValue() {
        const value = this.props.record.data[this.props.name];
        if (!value) return "";

        const pattern = this.props.maskPattern || this.getMaskPattern();
        return this.applyMask(value, pattern);
    }

    get displayValue() {
        if (this.state.isRevealed) {
            return this.props.record.data[this.props.name] || "";
        }
        return this.maskedValue;
    }

    getMaskPattern() {
        // Get mask pattern from field definition or use default
        const field = this.props.record.fields[this.props.name];
        if (field && field.mask_pattern) {
            return field.mask_pattern;
        }
        return "****-****-####";
    }

    applyMask(value, pattern) {
        if (!value || !pattern) return "****";

        // Pattern interpretation:
        // * = mask this character
        // # = show this character from the end
        // Other chars = literal

        const valueChars = value.split("");
        const patternChars = pattern.split("");
        let result = "";
        let valueIdx = 0;
        const endIdx = value.length - 1;

        // Count # in pattern to know how many chars to show from end
        const hashCount = patternChars.filter((c) => c === "#").length;
        let showFromEnd = hashCount;

        for (const patternChar of patternChars) {
            if (patternChar === "*") {
                // Mask character
                result += "•";
                valueIdx++;
            } else if (patternChar === "#") {
                // Show character from end
                const showIdx = value.length - showFromEnd;
                if (showIdx >= 0 && showIdx < value.length) {
                    result += value[showIdx];
                }
                showFromEnd--;
            } else {
                // Literal character (like - or space)
                result += patternChar;
            }
        }

        return result || "••••••••";
    }

    async toggleReveal() {
        if (this.state.isRevealed) {
            // Hide the value
            this.state.isRevealed = false;
            return;
        }

        // Check if user can reveal
        const canReveal = await this.checkRevealPermission();
        if (!canReveal) {
            this.notification.add("You don't have permission to view this data.", {
                type: "warning",
            });
            return;
        }

        this.state.isLoading = true;

        try {
            // Audit the reveal action if enabled
            if (this.props.auditReveal !== false) {
                await this.auditRevealAction();
            }

            this.state.isRevealed = true;
        } catch (error) {
            this.notification.add("Failed to reveal value.", {
                type: "danger",
            });
        } finally {
            this.state.isLoading = false;
        }
    }

    async checkRevealPermission() {
        const revealGroup = this.props.revealGroup;
        if (!revealGroup) {
            // Default: any authenticated user can reveal
            return true;
        }

        // Check if user has the required group
        return await this.user.hasGroup(revealGroup);
    }

    async auditRevealAction() {
        const recordId = this.props.record.resId;
        const modelName = this.props.record.resModel;
        const fieldName = this.props.name;

        await this.rpc("/web/dataset/call_kw", {
            model: "spp.pii.audit.log",
            method: "log_field_access",
            args: [modelName, recordId, fieldName, "reveal"],
            kwargs: {},
        });
    }
}

MaskedCharField.template = "spp_pii_encryption.MaskedCharField";

// Register the widget
registry.category("fields").add("masked_char", {
    component: MaskedCharField,
    supportedTypes: ["char", "text"],
    extractProps: ({attrs}) => ({
        maskPattern: attrs.mask_pattern,
        revealGroup: attrs.reveal_group,
        auditReveal: attrs.audit_reveal !== "false",
    }),
});
