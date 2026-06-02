"""Let CEL authors reference DCI variables with their dotted accessor.

The base resolver tokenizes with the CEL lexer and only matches single-identifier
variable references; a dotted accessor like ``crvs.dci.is_alive`` would be
mis-read as field navigation on the query root. This override runs a pre-pass
that rewrites any *registered cached-variable dotted accessor* into its
``metric('<accessor>', me)`` call before normal resolution, so users can write
``crvs.dci.is_alive == true`` and it resolves against the value cache.

Only accessors that exactly match a registered ttl/manual variable are touched;
ordinary navigation (``me.gender``, ``r.age``) matches no accessor and is left
untouched.
"""

import re

from odoo import api, models


class CelVariableResolverDCI(models.AbstractModel):
    _inherit = "spp.cel.variable.resolver"

    @api.model
    def expand_expression(self, expression, program_id=None, context_type="group", _depth=0, _seen_vars=None):
        # Only rewrite at the top level; once expanded, the dotted accessor lives
        # inside a metric('...') string literal and must not be touched again.
        if expression and _depth == 0:
            expression = self._expand_dotted_cached_accessors(expression)
        return super().expand_expression(
            expression,
            program_id=program_id,
            context_type=context_type,
            _depth=_depth,
            _seen_vars=_seen_vars,
        )

    @api.model
    def _expand_dotted_cached_accessors(self, expression):
        """Rewrite dotted cached-variable accessors into metric() calls."""
        Variable = self.env[self._get_variable_model()]
        dotted_vars = Variable.search(
            [
                ("active", "=", True),
                ("cache_strategy", "in", ["ttl", "manual"]),
                ("cel_accessor", "like", "%.%"),
            ]
        )
        # Longest accessors first, so a longer accessor is not partially matched
        # by a shorter one that is its prefix.
        for var in sorted(dotted_vars, key=lambda v: len(v.cel_accessor or ""), reverse=True):
            accessor = var.cel_accessor
            if not accessor or accessor not in expression:
                continue
            # Match the accessor as a standalone token: not part of a longer
            # dotted/identifier chain and not already inside a quoted string.
            pattern = rf"(?<![\w.'\"]){re.escape(accessor)}(?![\w.'\"])"
            expression = re.sub(pattern, f"metric('{accessor}', me)", expression)
        return expression
