/** @odoo-module **/

/**
 * CEL Language Syntax Definition
 *
 * Defines the CEL language grammar for CodeMirror using StreamLanguage.
 * This provides tokenization for syntax highlighting.
 */

// CEL keywords
const CEL_KEYWORDS = new Set(["and", "or", "not", "in", "true", "false", "null"]);

// CEL built-in functions
const CEL_FUNCTIONS = new Set([
    "age_years",
    "today",
    "now",
    "days_ago",
    "months_ago",
    "years_ago",
    "between",
    "exists",
    "count",
    "head",
    "has_role",
    "contains",
    "startswith",
    "metric",
    "program",
    "has_tag",
    "date",
    "days_since",
    "hours_since",
    "is_business_day",
]);

/**
 * CEL Language mode for CodeMirror StreamLanguage
 */
export const celLanguageMode = {
    name: "cel",

    startState: function () {
        return {
            inString: false,
            stringChar: null,
            afterDot: false,
        };
    },

    token: function (stream, state) {
        // Handle string continuation
        if (state.inString) {
            while (!stream.eol()) {
                const ch = stream.next();
                if (ch === state.stringChar) {
                    state.inString = false;
                    state.stringChar = null;
                    return "string";
                }
                if (ch === "\\") {
                    stream.next(); // Skip escaped char
                }
            }
            return "string";
        }

        // Skip whitespace
        if (stream.eatSpace()) {
            state.afterDot = false;
            return null;
        }

        // Handle comments (if we want to support them)
        if (stream.match("//")) {
            stream.skipToEnd();
            return "comment";
        }

        // Handle strings
        if (stream.match('"') || stream.match("'")) {
            state.inString = true;
            state.stringChar = stream.current();
            while (!stream.eol()) {
                const ch = stream.next();
                if (ch === state.stringChar) {
                    state.inString = false;
                    state.stringChar = null;
                    return "string";
                }
                if (ch === "\\") {
                    stream.next();
                }
            }
            return "string";
        }

        // Handle numbers
        if (stream.match(/^-?\d+\.?\d*/)) {
            state.afterDot = false;
            return "number";
        }

        // Handle operators
        if (
            stream.match("==") ||
            stream.match("!=") ||
            stream.match(">=") ||
            stream.match("<=")
        ) {
            state.afterDot = false;
            return "operator";
        }

        if (stream.match(/^[><=]/)) {
            state.afterDot = false;
            return "operator";
        }

        // Handle dot (property access)
        if (stream.match(".")) {
            state.afterDot = true;
            return "punctuation";
        }

        // Handle punctuation
        if (stream.match(/^[(),\[\]]/)) {
            state.afterDot = false;
            return "punctuation";
        }

        // Handle identifiers, keywords, and functions
        if (stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/)) {
            const word = stream.current();

            // Keywords
            if (CEL_KEYWORDS.has(word)) {
                state.afterDot = false;
                if (word === "true" || word === "false") {
                    return "bool";
                }
                if (word === "null") {
                    return "atom";
                }
                return "keyword";
            }

            // Check if followed by '(' - it's a function
            if (stream.peek() === "(") {
                state.afterDot = false;
                if (CEL_FUNCTIONS.has(word)) {
                    return "builtin";
                }
                return "def";
            }

            // Property access (after dot)
            if (state.afterDot) {
                state.afterDot = false;
                return "property";
            }

            // Variable
            state.afterDot = false;
            return "variableName";
        }

        // Skip unknown characters
        stream.next();
        state.afterDot = false;
        return null;
    },

    indent: function () {
        return 0;
    },

    languageData: {
        commentTokens: {line: "//"},
        closeBrackets: {brackets: ["(", '"', "'"]},
    },
};

/**
 * Create token table for StreamLanguage highlighting
 * Maps token type strings to Lezer Tag objects
 * @param {Object} tags - CodeMirror tags from @lezer/highlight
 * @returns {Object} Token table mapping
 */
export function createCelTokenTable(tags) {
    return {
        keyword: tags.keyword,
        bool: tags.bool,
        atom: tags.atom,
        string: tags.string,
        number: tags.number,
        operator: tags.operator,
        punctuation: tags.punctuation,
        variableName: tags.variableName,
        property: tags.propertyName,
        def: tags.function(tags.definition(tags.variableName)),
        builtin: tags.function(tags.standard(tags.variableName)),
        comment: tags.comment,
    };
}

/**
 * Get CEL keywords for autocomplete
 * @returns {Array} Array of keyword strings
 */
export function getCelKeywords() {
    return Array.from(CEL_KEYWORDS);
}

/**
 * Get CEL built-in function names for autocomplete
 * @returns {Array} Array of function name strings
 */
export function getCelFunctions() {
    return Array.from(CEL_FUNCTIONS);
}
