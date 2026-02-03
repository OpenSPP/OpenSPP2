/** @odoo-module **/

/**
 * CEL Autocomplete Provider
 *
 * Provides context-aware autocompletion for CEL expressions.
 */

/**
 * Create CEL autocomplete extension
 * @param {Object} cm - CodeMirror modules
 * @param {Function} getSymbols - Function that returns symbols promise
 * @returns {Extension} Autocomplete extension
 */
export function createCelAutocomplete(cm, getSymbols) {
    const {autocompletion} = cm;

    return autocompletion({
        override: [
            async (context) => {
                const symbols = await getSymbols();
                if (!symbols) {
                    return null;
                }

                return celCompletionSource(context, symbols);
            },
        ],
        activateOnTyping: true,
        maxRenderedOptions: 50,
    });
}

/**
 * CEL completion source
 * @param {CompletionContext} context
 * @param {Object} symbols - Symbol data from backend
 * @returns {CompletionResult|null}
 */
function celCompletionSource(context, symbols) {
    // Match word before cursor
    const word = context.matchBefore(/[\w.]+/);

    if (!word && !context.explicit) {
        return null;
    }

    const text = word ? word.text : "";
    const from = word ? word.from : context.pos;

    // Check if we're after a dot (property access)
    if (text.includes(".")) {
        return getPropertyCompletions(text, from, symbols);
    }

    // Get top-level completions
    return getTopLevelCompletions(text, from, symbols);
}

/**
 * Get property completions after a dot
 * @param {string} text - Text including the dot
 * @param {number} from - Start position
 * @param {Object} symbols
 * @returns {CompletionResult}
 */
function getPropertyCompletions(text, from, symbols) {
    const parts = text.split(".");
    const prefix = parts.pop() || "";
    const basePath = parts.join(".");

    // Find the base variable
    const baseVar = symbols.variables?.find((v) => v.name === parts[0]);

    if (!baseVar) {
        return null;
    }

    // Get fields for the base variable (or nested path)
    let fields = baseVar.fields || [];

    // If there are nested parts, try to resolve them
    if (parts.length > 1) {
        // For nested paths like me.partner.name, we need to traverse
        // For now, just use the first level fields
        // TODO: Implement deep field resolution
    }

    const completions = [];

    // Add field completions
    for (const field of fields) {
        if (prefix && !field.name.toLowerCase().startsWith(prefix.toLowerCase())) {
            continue;
        }

        completions.push({
            label: field.name,
            type: field.type === "many2one" ? "property" : getCompletionType(field.type),
            detail: field.type,
            info: field.doc,
            apply: field.name,
        });
    }

    // For iterable collections, also suggest exists/count
    if (baseVar.iterable && parts.length === 1) {
        const collectionFns = ["exists", "count"];
        for (const fn of collectionFns) {
            if (prefix && !fn.startsWith(prefix.toLowerCase())) {
                continue;
            }
            completions.push({
                label: fn,
                type: "function",
                detail: fn === "exists" ? "-> bool" : "-> int",
                info: fn === "exists" ? "Check if any item matches condition" : "Count items matching condition",
                apply: `${fn}(, )`,
            });
        }
    }

    return {
        from: from + basePath.length + 1, // After the last dot
        options: completions,
        validFor: /^[\w]*$/,
    };
}

/**
 * Get top-level completions (variables, functions, keywords)
 * @param {string} text - Current word
 * @param {number} from - Start position
 * @param {Object} symbols
 * @returns {CompletionResult}
 */
function getTopLevelCompletions(text, from, symbols) {
    const prefix = text.toLowerCase();
    const completions = [];

    // Add variables
    for (const v of symbols.variables || []) {
        if (prefix && !v.name.toLowerCase().startsWith(prefix)) {
            continue;
        }

        completions.push({
            label: v.name,
            type: "variable",
            detail: v.model || v.type,
            info: v.doc,
            boost: 10, // Variables first
        });
    }

    // Add functions
    for (const f of symbols.functions || []) {
        if (prefix && !f.name.toLowerCase().startsWith(prefix)) {
            continue;
        }

        // Create apply text with parentheses
        let apply = f.name + "(";
        if (f.params && f.params.length > 0) {
            // Add placeholder for first param
            apply += "";
        }
        apply += ")";

        completions.push({
            label: f.name,
            type: "function",
            detail: f.signature,
            info: formatFunctionInfo(f),
            apply: apply,
            boost: 5,
        });
    }

    // Add keywords
    for (const kw of symbols.keywords || []) {
        if (prefix && !kw.toLowerCase().startsWith(prefix)) {
            continue;
        }

        completions.push({
            label: kw,
            type: "keyword",
            boost: 0,
        });
    }

    // Add operators (only if typing something that looks like an operator start)
    if (!prefix || "andornot".includes(prefix)) {
        for (const op of symbols.operators || []) {
            if (op.type === "logical") {
                if (prefix && !op.symbol.toLowerCase().startsWith(prefix)) {
                    continue;
                }

                completions.push({
                    label: op.symbol,
                    type: "keyword",
                    info: op.doc,
                    boost: -1,
                });
            }
        }
    }

    return {
        from: from,
        options: completions,
        validFor: /^[\w]*$/,
    };
}

/**
 * Format function info for tooltip
 * @param {Object} f - Function info
 * @returns {string}
 */
function formatFunctionInfo(f) {
    let info = f.doc || "";

    if (f.params && f.params.length > 0) {
        info += "\n\nParameters:";
        for (const p of f.params) {
            info += `\n  ${p.name}: ${p.type}`;
            if (p.doc) {
                info += ` - ${p.doc}`;
            }
        }
    }

    if (f.examples && f.examples.length > 0) {
        info += "\n\nExamples:";
        for (const ex of f.examples) {
            info += `\n  ${ex}`;
        }
    }

    return info;
}

/**
 * Get completion type for a field type
 * @param {string} fieldType
 * @returns {string}
 */
function getCompletionType(fieldType) {
    switch (fieldType) {
        case "char":
        case "text":
            return "text";
        case "integer":
        case "float":
        case "monetary":
            return "property";
        case "boolean":
            return "property";
        case "date":
        case "datetime":
            return "property";
        case "selection":
            return "enum";
        default:
            return "property";
    }
}

/**
 * Trigger autocomplete manually
 * @param {EditorView} view
 */
export function triggerAutocomplete(view, cm) {
    const {startCompletion} = cm;
    startCompletion(view);
}
