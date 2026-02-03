/** @odoo-module */
import {Component, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

/**
 * LogicTestPanel Component
 *
 * Displays test results for a logic definition and allows running individual
 * or all tests. Shows pass/fail status, expected vs actual results, and
 * error messages.
 *
 * @component
 * @example
 * <LogicTestPanel
 *   tests={[{id: 1, name: "Test 1", passed: true, ...}]}
 *   onRunTest={(testId) => rpc(...)}
 *   onRunAllTests={() => rpc(...)}
 * />
 */
export class LogicTestPanel extends Component {
    static template = "spp_studio.TestPanel";

    static props = {
        tests: {type: Array},
        onRunTest: {type: Function},
        onRunAllTests: {type: Function},
    };

    setup() {
        this.state = useState({
            running: false,
            runningTestId: null,
            expandedTests: new Set(),
        });
        this.notification = useService("notification");
    }

    /**
     * Run a single test and display notification with result
     * @param {Object} test - Test object with id, name, etc.
     */
    async runTest(test) {
        this.state.running = true;
        this.state.runningTestId = test.id;

        try {
            const result = await this.props.onRunTest(test.id);

            if (result.passed) {
                this.notification.add(`Test "${test.name}" passed`, {
                    type: "success",
                });
            } else {
                this.notification.add(`Test "${test.name}" failed`, {
                    type: "danger",
                });
            }
        } catch (error) {
            this.notification.add(`Test failed: ${error.message}`, {
                type: "danger",
            });
        } finally {
            this.state.running = false;
            this.state.runningTestId = null;
        }
    }

    /**
     * Run all tests and display summary notification
     */
    async runAllTests() {
        this.state.running = true;

        try {
            const results = await this.props.onRunAllTests();
            const msg = `${results.passed}/${results.total} tests passed`;

            this.notification.add(msg, {
                type: results.failed > 0 ? "warning" : "success",
            });
        } catch (error) {
            this.notification.add(`Failed to run tests: ${error.message}`, {
                type: "danger",
            });
        } finally {
            this.state.running = false;
        }
    }

    /**
     * Get the appropriate icon class based on test status
     * @param {Object} test - Test object
     * @returns {string} CSS classes for the icon
     */
    getStatusIcon(test) {
        if (test.error_message) {
            return "fa-exclamation-circle text-danger";
        }
        if (test.passed === true) {
            return "fa-check-circle text-success";
        }
        if (test.passed === false) {
            return "fa-times-circle text-danger";
        }
        return "fa-circle-o text-muted";
    }

    /**
     * Get CSS classes for test row based on status
     * @param {Object} test - Test object
     * @returns {Object} Object with CSS class keys
     */
    getTestRowClass(test) {
        return {
            passed: test.passed === true,
            failed: test.passed === false || test.error_message,
            running: this.state.runningTestId === test.id,
        };
    }

    /**
     * Toggle expansion of test details
     * @param {number} testId - ID of test to toggle
     */
    toggleTestExpansion(testId) {
        if (this.state.expandedTests.has(testId)) {
            this.state.expandedTests.delete(testId);
        } else {
            this.state.expandedTests.add(testId);
        }
    }

    /**
     * Check if test is expanded
     * @param {number} testId - ID of test
     * @returns {boolean}
     */
    isTestExpanded(testId) {
        return this.state.expandedTests.has(testId);
    }

    /**
     * Calculate summary statistics
     * @returns {Object} Object with passed, failed, total counts
     */
    getSummary() {
        const total = this.props.tests.length;
        const passed = this.props.tests.filter((t) => t.passed === true).length;
        const failed = this.props.tests.filter((t) => t.passed === false || t.error_message).length;
        const pending = total - passed - failed;

        return {total, passed, failed, pending};
    }

    /**
     * Format execution time in milliseconds
     * @param {number} ms - Milliseconds
     * @returns {string} Formatted time string
     */
    formatExecutionTime(ms) {
        if (!ms) return "N/A";
        if (ms < 1000) return `${ms}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    }

    /**
     * Get test status text
     * @param {Object} test - Test object
     * @returns {string} Status text
     */
    getTestStatus(test) {
        if (this.state.runningTestId === test.id) return "Running...";
        if (test.error_message) return "Error";
        if (test.passed === true) return "Passed";
        if (test.passed === false) return "Failed";
        return "Not run";
    }
}

registry.category("components").add("LogicTestPanel", LogicTestPanel);
