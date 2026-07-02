# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Allowlist enforcement for externally-supplied CEL predicates.

External callers (e.g. the DCI Social Registry search service) accept
sender-supplied CEL predicates and compile them to Odoo domains. Because a
predicate search returns counts and pageable matches, letting a sender filter on
sensitive data turns ``total_count``/pagination into an oracle that discloses a
value one query at a time even when the value never appears in the response body.

This module walks a *parsed* CEL AST and reports every symbol it references --
field paths, plain function calls, relation/namespaced method calls, and DCI
metric accessors -- so a caller can enforce a positive (default-deny) allowlist
*before* the expression is translated or executed. Working on the AST (rather
than the lowered query plan) is robust against source-text obfuscation
(backslash-escaped dots in ``metric('r\\.dci\\.dr\\.severity', ...)``) and
against domain rewriting (``_smart_op_domain`` turning ``r.gender`` into a
``gender_id`` domain): we see what the author wrote, not how it lowered.

DCI metric accessors are recognised both as the expanded ``metric('r.dci.…', me)``
call and as the raw dotted accessor ``r.dci.…`` (called or bare), so the same
allowlist governs an expression whether or not the cached-variable expansion has
run -- making the guard independent of which indicator variables are seeded.
"""

from dataclasses import dataclass, field

from . import cel_parser as P

# A metric() call whose first argument is not a plain string literal (e.g.
# string concatenation): its true name cannot be determined statically, so it is
# reported under this sentinel and will fail any positive allowlist.
DYNAMIC_METRIC = "<dynamic>"

# Roots that denote the record(s) under evaluation, not a field reference.
_RECORD_ROOTS = ("r", "me")

# Dotted accessor namespaces that denote DCI metrics (e.g. r.dci.dr.severity).
_DCI_METRIC_ROOTS = ("dci",)


@dataclass
class ReferencedSymbols:
    """Symbols a CEL expression references, grouped by kind."""

    fields: set = field(default_factory=set)
    functions: set = field(default_factory=set)
    methods: set = field(default_factory=set)
    metrics: set = field(default_factory=set)


def collect_referenced_symbols(ast) -> ReferencedSymbols:
    """Walk a parsed CEL AST and return the symbols it references.

    Args:
        ast: a node produced by ``cel_parser.parse``.

    Returns:
        ReferencedSymbols with:
          - fields:    dotted field paths (root ``r``/``me`` stripped), and bare
                       identifiers used as fields.
          - functions: names of plain ``name(...)`` calls (excluding ``metric``).
          - methods:   flattened names of ``a.b(...)`` calls that are not DCI
                       metric accessors (relation methods like
                       ``enrollments.exists``, namespaced calls, ...).
          - metrics:   canonical DCI metric names (``r.dci.…``) and the decoded
                       names of ``metric('…', …)`` calls; ``DYNAMIC_METRIC`` when
                       a metric name cannot be determined statically.
    """
    out = ReferencedSymbols()
    _walk(ast, out)
    return out


def _flatten_attr(node):
    """Flatten an Attr/Ident chain to a dotted string, or return None.

    ``r.dci.dr.severity`` -> "r.dci.dr.severity"; returns None if the chain is
    not rooted at a plain identifier (e.g. it is built on a call result).
    """
    parts = []
    cur = node
    while isinstance(cur, P.Attr):
        parts.append(cur.name)
        cur = cur.obj
    if isinstance(cur, P.Ident):
        parts.append(cur.name)
        return ".".join(reversed(parts))
    return None


def _classify_path(path, out):
    """Classify a flattened ``root.a.b`` path as a metric or a field."""
    head, _, rest = path.partition(".")
    if head in _RECORD_ROOTS:
        if rest:
            first = rest.split(".", 1)[0]
            if first in _DCI_METRIC_ROOTS:
                # Canonicalise me.dci.* to r.dci.* so the allowlist is uniform.
                out.metrics.add("r." + rest)
            else:
                out.fields.add(rest)
        # bare `r` / `me` alone is the record, not a field
        return
    # A dotted path not rooted at the record (e.g. a relation lambda var
    # `m.partner_id.x`): record the whole path so it fails the field allowlist.
    out.fields.add(path)


def _walk(node, out):  # noqa: C901 - explicit per-node dispatch is clearest here
    if node is None:
        return

    if isinstance(node, P.Call):
        _walk_call(node, out)
        return

    if isinstance(node, P.Attr):
        path = _flatten_attr(node)
        if path is not None:
            _classify_path(path, out)
        else:
            # Chain rooted at something other than an identifier (e.g. a call
            # result): walk the base so nested references are still seen.
            _walk(node.obj, out)
        return

    if isinstance(node, P.Ident):
        if node.name not in _RECORD_ROOTS:
            # The translator treats a bare identifier as a field on the root
            # model, so an external predicate could reference a field this way.
            out.fields.add(node.name)
        return

    if isinstance(node, P.Literal):
        return

    # Structural nodes: recurse into every child expression.
    for child in _children(node):
        _walk(child, out)


def _walk_call(node, out):
    func = node.func
    if isinstance(func, P.Ident):
        if func.name == "metric":
            out.metrics.add(_metric_name(node))
            # Skip the name literal; still walk the remaining args/kwargs.
            for arg in node.args[1:]:
                _walk(arg, out)
            for v in (node.kwargs or {}).values():
                _walk(v, out)
            return
        out.functions.add(func.name)
    elif isinstance(func, P.Attr):
        flat = _flatten_attr(func)
        if flat and _is_dci_metric_path(flat):
            head, _, rest = flat.partition(".")
            out.metrics.add("r." + rest)
        else:
            # Relation method (enrollments.exists), namespaced call, etc.
            out.methods.add(flat if flat is not None else "<dynamic-method>")
            if flat is None:
                _walk(func.obj, out)
    # Walk arguments and keyword-argument values of any call.
    for arg in node.args:
        _walk(arg, out)
    for v in (node.kwargs or {}).values():
        _walk(v, out)


def _is_dci_metric_path(path):
    head, _, rest = path.partition(".")
    return head in _RECORD_ROOTS and bool(rest) and rest.split(".", 1)[0] in _DCI_METRIC_ROOTS


def _metric_name(call):
    """Return the static name of a ``metric('name', ...)`` call, or DYNAMIC_METRIC."""
    if call.args and isinstance(call.args[0], P.Literal) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return DYNAMIC_METRIC


def _children(node):
    """Yield the child expression nodes of a structural AST node."""
    for attr in ("left", "right", "expr", "condition", "true_expr", "false_expr"):
        child = getattr(node, attr, None)
        if child is not None:
            yield child
    items = getattr(node, "items", None)
    if items:
        yield from items
