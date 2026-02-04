/** @odoo-module **/

/**
 * CEL Syntax Highlighting Styles
 *
 * Defines the highlight styles for CEL tokens.
 */

/**
 * Create a token-to-class highlighter for StreamLanguage
 * StreamLanguage token types need to be mapped to CSS classes
 * @param {Object} cm - CodeMirror modules
 * @returns {Extension} Highlighter extension
 */
export function createCelHighlighter(cm) {
    const {tags, Tag} = cm;

    // Create custom tags for CEL-specific token types
    const celTags = {
        bool: Tag.define(tags.bool),
        null: Tag.define(tags.null),
        property: Tag.define(tags.propertyName),
        variable: Tag.define(tags.variableName),
        function: Tag.define(tags.function(tags.variableName)),
        builtin: Tag.define(tags.standard(tags.variableName)),
    };

    return celTags;
}

/**
 * Create CEL highlight style using CodeMirror's HighlightStyle
 * @param {Object} cm - CodeMirror modules
 * @returns {Extension} Highlight style extension
 */
export function createCelHighlightStyle(cm) {
    const {HighlightStyle, syntaxHighlighting} = cm;
    const {tags} = cm;

    const celHighlightStyle = HighlightStyle.define([
        // Keywords (and, or, not, in)
        {tag: tags.keyword, color: "#0000ff", fontWeight: "500"},

        // Booleans (true, false)
        {tag: tags.bool, color: "#0000ff"},

        // Null
        {tag: tags.null, color: "#808080"},

        // Strings
        {tag: tags.string, color: "#008000"},

        // Numbers
        {tag: tags.number, color: "#098658"},

        // Operators
        {tag: tags.operator, color: "#333333"},
        {tag: tags.compareOperator, color: "#333333"},
        {tag: tags.logicOperator, color: "#0000ff"},

        // Variables
        {tag: tags.variableName, color: "#795e26"},

        // Properties (after dot)
        {tag: tags.propertyName, color: "#267f99"},

        // Functions
        {tag: tags.function(tags.variableName), color: "#795e26"},

        // Built-in functions
        {
            tag: tags.standard(tags.function(tags.variableName)),
            color: "#795e26",
            fontWeight: "500",
        },

        // Punctuation
        {tag: tags.punctuation, color: "#333333"},
        {tag: tags.paren, color: "#333333"},

        // Comments
        {tag: tags.comment, color: "#6a9955", fontStyle: "italic"},

        // Invalid/Error
        {tag: tags.invalid, color: "#ff0000", textDecoration: "underline wavy"},
    ]);

    return syntaxHighlighting(celHighlightStyle);
}

/**
 * Map StreamLanguage token types to CodeMirror tags
 * This is used when creating the language support
 */
export const tokenTypeToTag = {
    keyword: "keyword",
    bool: "bool",
    null: "null",
    string: "string",
    number: "number",
    operator: "operator",
    variable: "variableName",
    property: "propertyName",
    function: "function(variableName)",
    "function builtin": "standard(function(variableName))",
    punctuation: "punctuation",
    comment: "comment",
};

/**
 * Create simple highlight theme for CEL using class-based highlighting
 * This works with StreamLanguage's default class output
 * @param {Object} cm - CodeMirror modules
 * @returns {Extension} Theme extension
 */
export function createCelSimpleTheme(cm) {
    const {EditorView} = cm;

    // StreamLanguage applies classes like "cm-keyword", "cm-string", etc.
    // based on the token type strings returned by the tokenizer
    return EditorView.theme({
        // Keywords (and, or, not, in)
        ".cm-keyword": {color: "#0000ff !important", fontWeight: "500"},

        // Booleans
        ".cm-bool": {color: "#0000ff !important"},

        // Null
        ".cm-null": {color: "#808080 !important"},

        // Strings
        ".cm-string": {color: "#008000 !important"},

        // Numbers
        ".cm-number": {color: "#098658 !important"},

        // Operators
        ".cm-operator": {color: "#666666 !important"},

        // Variables
        ".cm-variable": {color: "#795e26 !important"},

        // Properties (after dot)
        ".cm-property": {color: "#267f99 !important"},

        // Functions
        ".cm-function": {color: "#795e26 !important"},

        // Built-in functions get bold
        ".cm-function.cm-builtin": {
            color: "#795e26 !important",
            fontWeight: "500",
        },

        // Punctuation
        ".cm-punctuation": {color: "#333333 !important"},

        // Comments
        ".cm-comment": {color: "#6a9955 !important", fontStyle: "italic"},

        // Also handle ͡tok- prefixed classes (some CM versions use this)
        ".tok-keyword": {color: "#0000ff !important", fontWeight: "500"},
        ".tok-bool": {color: "#0000ff !important"},
        ".tok-null": {color: "#808080 !important"},
        ".tok-string": {color: "#008000 !important"},
        ".tok-number": {color: "#098658 !important"},
        ".tok-operator": {color: "#666666 !important"},
        ".tok-variable": {color: "#795e26 !important"},
        ".tok-property": {color: "#267f99 !important"},
        ".tok-function": {color: "#795e26 !important"},
        ".tok-punctuation": {color: "#333333 !important"},
        ".tok-comment": {color: "#6a9955 !important", fontStyle: "italic"},

        // CodeMirror 6 uses ͡cmt- for some highlighting
        ".cmt-keyword": {color: "#0000ff !important", fontWeight: "500"},
        ".cmt-bool": {color: "#0000ff !important"},
        ".cmt-string": {color: "#008000 !important"},
        ".cmt-number": {color: "#098658 !important"},
        ".cmt-operator": {color: "#666666 !important"},
        ".cmt-variableName": {color: "#795e26 !important"},
        ".cmt-propertyName": {color: "#267f99 !important"},
        ".cmt-comment": {color: "#6a9955 !important", fontStyle: "italic"},
    });
}
