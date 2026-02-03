/**
 * CodeMirror 6 Bundle for CEL Expression Widget
 *
 * This is a minimal bundle containing only the features needed for CEL editing.
 * For production, this should be built from npm packages using a bundler.
 *
 * Required packages:
 * - @codemirror/state
 * - @codemirror/view
 * - @codemirror/autocomplete
 * - @codemirror/lint
 * - @codemirror/language
 * - @lezer/highlight
 *
 * For now, we use a CDN-loaded approach with a compatibility layer.
 */

(function (global) {
    "use strict";

    // Check if CodeMirror is already loaded
    if (global.CelCodeMirror) {
        return;
    }

    // Create namespace for our CodeMirror implementation
    const CelCodeMirror = {
        loaded: false,
        loadPromise: null,
        callbacks: [],

        // CDN URLs for CodeMirror 6 (using esm.sh for ES modules)
        cdnUrls: {
            state: "https://esm.sh/@codemirror/state@6",
            view: "https://esm.sh/@codemirror/view@6",
            autocomplete: "https://esm.sh/@codemirror/autocomplete@6",
            lint: "https://esm.sh/@codemirror/lint@6",
            language: "https://esm.sh/@codemirror/language@6",
            highlight: "https://esm.sh/@lezer/highlight@1",
            commands: "https://esm.sh/@codemirror/commands@6",
        },

        // Loaded modules
        modules: {},

        /**
         * Load CodeMirror from CDN
         * @returns {Promise} Resolves when all modules are loaded
         */
        load: function () {
            if (this.loaded) {
                return Promise.resolve(this.modules);
            }

            if (this.loadPromise) {
                return this.loadPromise;
            }

            this.loadPromise = this._loadFromCDN();
            return this.loadPromise;
        },

        _loadFromCDN: async function () {
            try {
                // Load all modules in parallel
                const [state, view, autocomplete, lint, language, highlight, commands] = await Promise.all([
                    import(this.cdnUrls.state),
                    import(this.cdnUrls.view),
                    import(this.cdnUrls.autocomplete),
                    import(this.cdnUrls.lint),
                    import(this.cdnUrls.language),
                    import(this.cdnUrls.highlight),
                    import(this.cdnUrls.commands),
                ]);

                this.modules = {
                    // State module
                    EditorState: state.EditorState,
                    StateField: state.StateField,
                    StateEffect: state.StateEffect,
                    Compartment: state.Compartment,
                    Transaction: state.Transaction,

                    // View module
                    EditorView: view.EditorView,
                    keymap: view.keymap,
                    lineNumbers: view.lineNumbers,
                    highlightActiveLineGutter: view.highlightActiveLineGutter,
                    highlightSpecialChars: view.highlightSpecialChars,
                    drawSelection: view.drawSelection,
                    dropCursor: view.dropCursor,
                    rectangularSelection: view.rectangularSelection,
                    crosshairCursor: view.crosshairCursor,
                    highlightActiveLine: view.highlightActiveLine,
                    placeholder: view.placeholder,
                    Decoration: view.Decoration,
                    ViewPlugin: view.ViewPlugin,
                    WidgetType: view.WidgetType,

                    // Autocomplete module
                    autocompletion: autocomplete.autocompletion,
                    completionKeymap: autocomplete.completionKeymap,
                    closeBrackets: autocomplete.closeBrackets,
                    closeBracketsKeymap: autocomplete.closeBracketsKeymap,
                    CompletionContext: autocomplete.CompletionContext,
                    startCompletion: autocomplete.startCompletion,
                    acceptCompletion: autocomplete.acceptCompletion,

                    // Lint module
                    linter: lint.linter,
                    lintGutter: lint.lintGutter,
                    lintKeymap: lint.lintKeymap,
                    Diagnostic: lint.Diagnostic,

                    // Language module
                    syntaxHighlighting: language.syntaxHighlighting,
                    indentOnInput: language.indentOnInput,
                    bracketMatching: language.bracketMatching,
                    foldGutter: language.foldGutter,
                    foldKeymap: language.foldKeymap,
                    HighlightStyle: language.HighlightStyle,
                    StreamLanguage: language.StreamLanguage,
                    LanguageSupport: language.LanguageSupport,

                    // Highlight module
                    tags: highlight.tags,
                    styleTags: highlight.styleTags,
                    Tag: highlight.Tag,

                    // Commands module
                    defaultKeymap: commands.defaultKeymap,
                    history: commands.history,
                    historyKeymap: commands.historyKeymap,
                    indentWithTab: commands.indentWithTab,
                };

                this.loaded = true;

                // Notify callbacks
                this.callbacks.forEach((cb) => cb(this.modules));
                this.callbacks = [];

                console.log("[CelCodeMirror] Loaded from CDN");
                return this.modules;
            } catch (error) {
                console.error("[CelCodeMirror] Failed to load from CDN:", error);
                throw error;
            }
        },

        /**
         * Register callback for when modules are loaded
         * @param {Function} callback
         */
        onReady: function (callback) {
            if (this.loaded) {
                callback(this.modules);
            } else {
                this.callbacks.push(callback);
            }
        },

        /**
         * Create a basic editor setup
         * @param {Object} options
         * @returns {Array} Array of extensions
         */
        basicSetup: function (options = {}) {
            const m = this.modules;
            if (!m.EditorView) {
                throw new Error("CodeMirror not loaded. Call CelCodeMirror.load() first.");
            }

            const extensions = [
                m.highlightActiveLineGutter(),
                m.highlightSpecialChars(),
                m.history(),
                m.drawSelection(),
                m.dropCursor(),
                m.EditorState.allowMultipleSelections.of(true),
                m.indentOnInput(),
                m.bracketMatching(),
                m.closeBrackets(),
                m.rectangularSelection(),
                m.crosshairCursor(),
                m.highlightActiveLine(),
                // Note: indentWithTab is NOT included here - it's handled separately
                // by the editor to allow Tab to accept autocomplete first
                m.keymap.of([...m.closeBracketsKeymap, ...m.defaultKeymap, ...m.historyKeymap]),
            ];

            if (options.lineNumbers !== false) {
                extensions.push(m.lineNumbers());
            }

            if (options.placeholder) {
                extensions.push(m.placeholder(options.placeholder));
            }

            return extensions;
        },
    };

    // Expose to global scope
    global.CelCodeMirror = CelCodeMirror;
})(typeof window !== "undefined" ? window : this);
