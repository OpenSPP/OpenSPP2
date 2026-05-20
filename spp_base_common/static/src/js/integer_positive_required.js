/** @odoo-module **/
/*
 * `integer_positive_required` field widget — a reusable Integer field that
 * treats 0 as invalid when the field is required.
 *
 * Why: Odoo 19's `_checkValidity` (web/static/src/model/relational_model/
 * record.js) explicitly skips numeric field types (`boolean`, `float`,
 * `integer`, `monetary`) from the required-empty validation. That means
 * a required Integer with value 0 is NEVER added to `_invalidFields`,
 * the `o_field_invalid` class is NEVER applied, and the user gets no
 * visual cue (asterisk on label / pink highlight on input) that the
 * field is unfilled. The model-side validation still rejects 0 on save,
 * but the form is silent until then.
 *
 * `fieldVisualFeedback` calls `field.isValid(record, fieldName, fieldInfo)`
 * BEFORE falling back to `record.isFieldInvalid(...)`. So a widget can
 * override `isValid` to plug its own check into the visual-feedback
 * pipeline. We use that hook to mark the field invalid when value <= 0
 * AND `required` evaluates true.
 *
 * Usage:
 *   <field name="beneficiary_count"
 *          widget="integer_positive_required"
 *          required="..."/>
 */

import {evaluateBooleanExpr} from "@web/core/py_js/py";
import {registry} from "@web/core/registry";
import {integerField} from "@web/views/fields/integer/integer_field";

export const integerPositiveRequiredField = {
    ...integerField,
    isEmpty: (record, fieldName) => {
        const value = record.data[fieldName];
        return value === false || value === 0;
    },
    isValid: (record, fieldName, fieldInfo) => {
        const value = record.data[fieldName];
        // Field is valid if value is a positive integer.
        if (typeof value === "number" && value > 0) {
            return true;
        }
        // 0, false (unset), or non-numeric — only valid when field is not
        // required. Evaluate the required modifier against the record's
        // eval context (it may be a dynamic expression like
        // `drims_type == 'request_dispatch'`).
        const required = evaluateBooleanExpr(
            fieldInfo.required,
            record.evalContextWithVirtualIds
        );
        return !required;
    },
};

registry
    .category("fields")
    .add("integer_positive_required", integerPositiveRequiredField);
