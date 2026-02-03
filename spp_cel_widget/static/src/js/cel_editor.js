/** @odoo-module **/

/**
 * CelEditor - Reusable CEL Expression Editor Component
 *
 * A CodeMirror-based editor for CEL expressions that can be used:
 * - As a child component in form field widgets (CelEditorField)
 * - Standalone in client actions (CelSearchPortal)
 *
 * Features:
 * - Syntax highlighting
 * - Autocompletion
 * - Live validation with inline error highlighting
 * - Symbol browser support
 */

import {Component, useState, useRef, onMounted, onWillDestroy, onWillUpdateProps} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

import {celLanguageMode, createCelTokenTable} from "./cel_language/syntax";
import {createCelSimpleTheme, createCelHighlightStyle} from "./cel_language/highlight";
import {createCelAutocomplete} from "./cel_language/autocomplete";
import {createCelLinter, createCelLintGutter} from "./cel_language/lint";
import {CelSymbolBrowser} from "./cel_symbol_browser";

export class CelEditor extends Component {
    static template = "spp_cel_widget.CelEditor";
    static components = {CelSymbolBrowser};
    static props = {
        value: {type: String, optional: true},
        profile: {type: String, optional: true},
        expressionType: {type: String, optional: true}, // filter, formula, scoring, validation, other
        outputType: {type: String, optional: true}, // boolean, number, string, money
        readonly: {type: Boolean, optional: true},
        placeholder: {type: String, optional: true},
        minHeight: {type: String, optional: true},
        showToolbar: {type: Boolean, optional: true},
        showSymbolBrowser: {type: Boolean, optional: true},
        showValidationCount: {type: Boolean, optional: true},
        showHelpText: {type: Boolean, optional: true},
        onChange: {type: Function, optional: true},
        onValidation: {type: Function, optional: true},
        onReady: {type: Function, optional: true}, // Callback to expose editor API
    };

    static defaultProps = {
        value: "",
        profile: "registry_individuals",
        readonly: false,
        placeholder: "Start typing or press Ctrl+Space for suggestions...\nExample: age_years(r.birthdate) >= 18",
        minHeight: "80px",
        showToolbar: true,
        showSymbolBrowser: true,
        showValidationCount: true,
        showHelpText: true,
    };

    setup() {
        this.editorContainerRef = useRef("editorContainer");
        this.celSymbols = useService("cel_symbols");

        this.state = useState({
            symbols: null,
            validation: null,
            isValidating: false,
            showBrowser: false,
            editorReady: false,
            error: null,
        });

        this.editor = null;
        this.cm = null;
        this.debounceTimer = null;
        this.symbolsPromise = null;
        this._currentProfile = this.props.profile;

        // Delegated click handler for [data-cel-insert] elements
        // (e.g., rows in the Show Symbols HTML output)
        this._onCelInsertClick = (ev) => {
            const row = ev.target.closest("[data-cel-insert]");
            if (row && this.editor) {
                const text = row.dataset.celInsert;
                if (text) {
                    const existing = this.getValue().trim();
                    const insert = existing ? " and " + text : text;
                    this.insertSymbol(insert);
                }
            }
        };

        onMounted(() => {
            this.initEditor();
            document.addEventListener("click", this._onCelInsertClick);
        });

        onWillDestroy(() => {
            document.removeEventListener("click", this._onCelInsertClick);
            this.destroyEditor();
        });

        onWillUpdateProps((nextProps) => {
            // Update editor content if value changed externally
            if (nextProps.value !== undefined && nextProps.value !== this.getValue()) {
                this.setValue(nextProps.value);
            }

            // Reload symbols if profile changed
            if (nextProps.profile && nextProps.profile !== this._currentProfile) {
                this._currentProfile = nextProps.profile;
                this.symbolsPromise = this.loadSymbols();
                // Re-validate with new profile
                if (this.getValue()) {
                    this.scheduleValidation(this.getValue());
                }
            }
        });
    }

    get currentProfile() {
        return this._currentProfile || this.props.profile || "registry_individuals";
    }

    get placeholderText() {
        return this.props.placeholder || CelEditor.defaultProps.placeholder;
    }

    get isReadonly() {
        return this.props.readonly || false;
    }

    async initEditor() {
        try {
            if (!window.CelCodeMirror) {
                this.state.error = "CodeMirror not loaded";
                return;
            }

            this.cm = await window.CelCodeMirror.load();
            this.symbolsPromise = this.loadSymbols();
            this.createEditor();
            this.state.editorReady = true;

            // Expose API via callback
            if (this.props.onReady) {
                this.props.onReady({
                    getValue: () => this.getValue(),
                    setValue: (v) => this.setValue(v),
                    clear: () => this.clear(),
                    focus: () => this.focus(),
                    forceValidate: () => this.forceValidate(),
                    triggerAutocomplete: () => this.triggerAutocomplete(),
                });
            }

            // Initial validation if there's content
            if (this.props.value) {
                this.scheduleValidation(this.props.value);
            }
        } catch (error) {
            console.error("[CelEditor] Init error:", error);
            this.state.error = error.message;
        }
    }

    async loadSymbols() {
        try {
            const symbols = await this.celSymbols.getSymbols(this.currentProfile);
            this.state.symbols = symbols;
            return symbols;
        } catch (error) {
            console.error("[CelEditor] Failed to load symbols:", error);
            return null;
        }
    }

    createEditor() {
        const cm = this.cm;
        const container = this.editorContainerRef.el;

        if (!container || !cm) {
            return;
        }

        const validateForLinter = async (expression) => {
            try {
                return await this.celSymbols.validate(expression, this.currentProfile, {
                    expression_type: this.props.expressionType,
                    output_type: this.props.outputType,
                });
            } catch (e) {
                console.error("[CelEditor] Lint validation error:", e);
                return null;
            }
        };

        const tokenTable = createCelTokenTable(cm.tags);

        const extensions = [
            ...window.CelCodeMirror.basicSetup({
                lineNumbers: false,
                placeholder: this.placeholderText,
            }),

            cm.StreamLanguage.define(celLanguageMode, {tokenTable}),
            createCelHighlightStyle(cm),
            createCelSimpleTheme(cm),
            createCelAutocomplete(cm, () => this.symbolsPromise || Promise.resolve(this.state.symbols)),

            cm.keymap.of([
                {
                    key: "Tab",
                    run: (view) => {
                        if (cm.acceptCompletion(view)) {
                            return true;
                        }
                        return cm.indentWithTab.run(view);
                    },
                },
            ]),

            createCelLinter(cm, validateForLinter, this.currentProfile),
            createCelLintGutter(cm),

            cm.EditorView.updateListener.of((update) => {
                if (update.docChanged) {
                    this.onEditorChange(update.state.doc.toString());
                }
            }),

            cm.EditorView.theme({
                "&": {
                    minHeight: this.props.minHeight || "80px",
                },
                ".cm-content": {
                    fontFamily: '"Roboto Mono", monospace',
                    fontSize: "13px",
                },
                ".cm-scroller": {
                    overflow: "auto",
                },
                ".cm-lintRange-error": {
                    backgroundImage: "none",
                    textDecoration: "underline wavy #dc3545",
                    textDecorationSkipInk: "none",
                },
                ".cm-lintRange-warning": {
                    backgroundImage: "none",
                    textDecoration: "underline wavy #ffc107",
                    textDecorationSkipInk: "none",
                },
                ".cm-lintRange-info": {
                    backgroundImage: "none",
                    textDecoration: "underline wavy #17a2b8",
                    textDecorationSkipInk: "none",
                },
                ".cm-lint-marker-error": {
                    content: '"\\26a0"',
                    color: "#dc3545",
                },
                ".cm-lint-marker-warning": {
                    content: '"\\26a0"',
                    color: "#ffc107",
                },
            }),

            cm.EditorState.readOnly.of(this.isReadonly),
        ];

        this.editor = new cm.EditorView({
            state: cm.EditorState.create({
                doc: this.props.value || "",
                extensions,
            }),
            parent: container,
        });
    }

    destroyEditor() {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        if (this.editor) {
            this.editor.destroy();
            this.editor = null;
        }
    }

    onEditorChange(value) {
        if (this.props.onChange) {
            this.props.onChange(value);
        }
        this.scheduleValidation(value);
    }

    scheduleValidation(value) {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        this.debounceTimer = setTimeout(() => {
            this.validateExpression(value);
        }, 500);
    }

    async validateExpression(expression) {
        if (!expression || !expression.trim()) {
            this.state.validation = null;
            if (this.props.onValidation) {
                this.props.onValidation(null);
            }
            return;
        }

        this.state.isValidating = true;

        try {
            const result = await this.celSymbols.validate(expression, this.currentProfile, {
                expression_type: this.props.expressionType,
                output_type: this.props.outputType,
            });
            this.state.validation = result;
            if (this.props.onValidation) {
                this.props.onValidation(result);
            }
        } catch (error) {
            console.error("[CelEditor] Validation error:", error);
            const errorResult = {
                valid: false,
                errors: [{message: error.message}],
            };
            this.state.validation = errorResult;
            if (this.props.onValidation) {
                this.props.onValidation(errorResult);
            }
        } finally {
            this.state.isValidating = false;
        }
    }

    // ─── PUBLIC METHODS ─────────────────────────────────────────────────

    getValue() {
        if (this.editor) {
            return this.editor.state.doc.toString();
        }
        return this.props.value || "";
    }

    setValue(value) {
        if (!this.editor) {
            return;
        }

        const currentValue = this.editor.state.doc.toString();
        if (currentValue !== value) {
            this.editor.dispatch({
                changes: {
                    from: 0,
                    to: currentValue.length,
                    insert: value || "",
                },
            });
        }
    }

    clear() {
        this.setValue("");
        this.state.validation = null;
    }

    focus() {
        if (this.editor) {
            this.editor.focus();
        }
    }

    forceValidate() {
        const value = this.getValue();
        this.validateExpression(value);
    }

    triggerAutocomplete() {
        if (!this.editor || !this.cm) {
            return;
        }
        this.cm.startCompletion(this.editor);
    }

    // ─── SYMBOL BROWSER ─────────────────────────────────────────────────

    toggleSymbolBrowser() {
        this.state.showBrowser = !this.state.showBrowser;
    }

    closeSymbolBrowser() {
        this.state.showBrowser = false;
    }

    insertSymbol(text) {
        if (!this.editor || this.isReadonly) {
            return;
        }

        const pos = this.editor.state.selection.main.head;
        this.editor.dispatch({
            changes: {from: pos, insert: text},
            selection: {anchor: pos + text.length},
        });

        this.editor.focus();
    }

    // ─── COMPUTED GETTERS ───────────────────────────────────────────────

    get validationStatusClass() {
        if (this.state.isValidating) {
            return "text-muted";
        }
        if (!this.state.validation) {
            return "";
        }
        return this.state.validation.valid ? "text-success" : "text-danger";
    }

    get validationIcon() {
        if (this.state.isValidating) {
            return "fa-spinner fa-spin";
        }
        if (!this.state.validation) {
            return "";
        }
        return this.state.validation.valid ? "fa-check-circle" : "fa-times-circle";
    }

    get validationMessage() {
        if (this.state.isValidating) {
            return "Validating...";
        }
        if (!this.state.validation) {
            return "";
        }
        if (this.state.validation.valid) {
            if (this.props.showValidationCount !== false) {
                const count = this.state.validation.matching_count;
                if (count !== null && count !== undefined) {
                    return `${count.toLocaleString()} match${count === 1 ? "" : "es"}`;
                }
            }
            return "Valid";
        }
        const firstError = this.state.validation.errors?.[0];
        return firstError?.message || "Invalid expression";
    }

    get hasValue() {
        return Boolean(this.getValue());
    }
}
