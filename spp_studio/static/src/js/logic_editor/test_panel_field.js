/** @odoo-module **/

import {Component, useState, onWillUpdateProps} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {standardFieldProps} from "@web/views/fields/standard_field_props";
import {LogicTestPanel} from "./test_panel";

/**
 * Test Panel Field Widget
 *
 * Wraps the LogicTestPanel component to work with Odoo's One2Many field
 * for test_ids. Provides enhanced UI for viewing and running tests.
 */
export class TestPanelField extends Component {
    static template = "spp_studio.TestPanelField";
    static components = {LogicTestPanel};
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            loading: false,
        });

        onWillUpdateProps(async (nextProps) => {
            // Handle prop updates if needed
        });
    }

    get tests() {
        // Get tests from the One2Many field
        const testIds = this.props.record.data[this.props.name];
        if (!testIds || !testIds.records) {
            return [];
        }

        // Transform Odoo records to component-friendly format
        return testIds.records.map((record) => ({
            id: record.data.id,
            name: record.data.name || "",
            description: record.data.description || "",
            persona_id: record.data.persona_id || null,
            expected_result: record.data.expected_result,
            actual_result: record.data.actual_result,
            result: record.data.result || null,
            passed: record.data.result === "pass",
            error_message: record.data.error_message || "",
            execution_time_ms: record.data.execution_time_ms || 0,
            last_run: record.data.last_run || null,
            input_context: record.data.input_context || null,
            execution_log: record.data.execution_log || null,
        }));
    }

    get readonly() {
        return this.props.readonly;
    }

    get logicId() {
        // Get the parent logic record ID
        return this.props.record.resId;
    }

    /**
     * Run a single test
     */
    async onRunTest(testId) {
        this.state.loading = true;
        try {
            // Call the action_run_test method on the test record
            const result = await this.orm.call("spp.studio.test", "action_run_test", [[testId]]);

            // Reload the record to get updated test results
            await this.props.record.load();

            // Find the updated test to check if it passed
            const test = this.tests.find((t) => t.id === testId);

            return {
                passed: test?.passed || false,
                result: test?.result || "fail",
            };
        } catch (error) {
            console.error("[TestPanelField] Failed to run test:", error);
            this.notification.add(`Failed to run test: ${error.message}`, {
                type: "danger",
            });
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Run all tests
     */
    async onRunAllTests() {
        this.state.loading = true;
        try {
            // Call the action_test_all method on the logic record
            const result = await this.orm.call("spp.logic", "action_test_all", [[this.logicId]]);

            // Reload the record to get updated test results
            await this.props.record.load();

            // Calculate summary
            const tests = this.tests;
            const passed = tests.filter((t) => t.passed).length;
            const failed = tests.filter((t) => !t.passed && t.result === "fail").length;
            const total = tests.length;

            return {
                passed,
                failed,
                total,
            };
        } catch (error) {
            console.error("[TestPanelField] Failed to run all tests:", error);
            this.notification.add(`Failed to run tests: ${error.message}`, {
                type: "danger",
            });
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    /**
     * Open the add test wizard or form
     */
    async onAddTest() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "spp.studio.test",
            views: [[false, "form"]],
            target: "new",
            context: {
                default_logic_id: this.logicId,
            },
        });
    }
}

// Register the field widget
registry.category("fields").add("logic_test_panel", {
    component: TestPanelField,
    supportedTypes: ["one2many"],
});
