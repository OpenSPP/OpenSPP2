/** @odoo-module **/

/**
 * CEL Expression Linter for CodeMirror
 *
 * Provides inline error highlighting by integrating with the backend validation.
 */

/**
 * Create a CEL linter extension for CodeMirror
 *
 * @param {Object} cm - CodeMirror modules
 * @param {Function} getValidation - Function that returns validation result promise
 * @param {string} profile - CEL profile name
 * @returns {Extension} CodeMirror linter extension
 */
export function createCelLinter(cm, getValidation, profile) {
    return cm.linter(
        async (view) => {
            const doc = view.state.doc.toString();

            // Don't lint empty documents
            if (!doc.trim()) {
                return [];
            }

            try {
                const result = await getValidation(doc, profile);

                if (!result || result.valid) {
                    return [];
                }

                const diagnostics = [];

                // Convert errors to CodeMirror diagnostics
                if (result.errors && result.errors.length > 0) {
                    for (const error of result.errors) {
                        diagnostics.push(createDiagnostic(view, error, "error"));
                    }
                }

                // Convert warnings to CodeMirror diagnostics
                if (result.warnings && result.warnings.length > 0) {
                    for (const warning of result.warnings) {
                        diagnostics.push(createDiagnostic(view, warning, "warning"));
                    }
                }

                return diagnostics;
            } catch (e) {
                console.error("[CelLinter] Validation error:", e);
                return [];
            }
        },
        {
            // Delay validation to avoid too frequent requests
            delay: 750,
        }
    );
}

/**
 * Create a CodeMirror diagnostic from a validation error
 *
 * @param {EditorView} view - CodeMirror editor view
 * @param {Object} error - Error object from validation
 * @param {string} severity - "error" | "warning" | "info"
 * @returns {Diagnostic} CodeMirror diagnostic
 */
function createDiagnostic(view, error, severity) {
    const doc = view.state.doc;
    const docLength = doc.length;

    // Calculate position from line/column if provided
    let from = 0;
    let to = docLength;

    if (error.col_start !== undefined && error.col_end !== undefined) {
        // Use column positions directly (0-indexed)
        from = Math.min(Math.max(0, error.col_start), docLength);
        to = Math.min(Math.max(from, error.col_end), docLength);

        // If positions are the same, highlight at least one character or the whole line
        if (from === to) {
            if (to < docLength) {
                to = from + 1;
            } else if (from > 0) {
                from = to - 1;
            }
        }
    } else if (error.line !== undefined) {
        // Use line number (1-indexed from backend)
        const lineNum = Math.max(1, Math.min(error.line, doc.lines));
        const line = doc.line(lineNum);
        from = line.from;
        to = line.to;
    }

    // Build diagnostic object
    const diagnostic = {
        from,
        to,
        severity,
        message: error.message || "Unknown error",
    };

    // Add suggestion as action if available
    if (error.suggestion) {
        diagnostic.actions = [
            {
                name: "Did you mean: " + error.suggestion + "?",
                apply: (view, from, to) => {
                    // Extract the suggested value (first suggestion if comma-separated)
                    const suggestion = error.suggestion.split(",")[0].trim();
                    view.dispatch({
                        changes: {from, to, insert: suggestion},
                    });
                },
            },
        ];
    }

    return diagnostic;
}

/**
 * Create lint gutter extension with custom styling
 *
 * @param {Object} cm - CodeMirror modules
 * @returns {Extension} Lint gutter extension
 */
export function createCelLintGutter(cm) {
    return cm.lintGutter({
        hoverTime: 300,
    });
}
