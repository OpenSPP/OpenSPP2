# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Notary evidence accessors for CEL variable resolution."""

import re

from odoo import _, api, models


class CELVariableResolver(models.AbstractModel):
    _inherit = "spp.cel.variable.resolver"

    EVIDENCE_ACCESSOR_PATTERN = re.compile(
        r"\b(?P<alias>[rm])\.evidence\.(?P<provider>[a-zA-Z_][a-zA-Z0-9_]*)\.(?P<claim>[a-zA-Z_][a-zA-Z0-9_]*)\b"
    )

    @api.model
    def _resolve_custom_accessors(self, expression, context_type="group"):
        result = super()._resolve_custom_accessors(expression, context_type=context_type)
        resolved_expression = result.get("expression") or expression
        variables_used = list(result.get("variables_used", []))
        errors = list(result.get("errors", []))
        warnings = list(result.get("warnings", []))

        def replace(match):
            alias = match.group("alias")
            provider_code = match.group("provider")
            claim_code = match.group("claim")
            claim, error = self._notary_claim_for_evidence_accessor(provider_code, claim_code, alias, context_type)
            if error:
                errors.append(error)
                return match.group(0)
            variables_used.append(claim.variable_id.name)
            return f"metric('{claim.variable_id.name}', {alias})"

        resolved_expression = self.EVIDENCE_ACCESSOR_PATTERN.sub(replace, resolved_expression)
        errors.extend(self._errors_for_bare_notary_variables(resolved_expression))

        return {
            "expression": resolved_expression,
            "variables_used": variables_used,
            "warnings": warnings,
            "errors": errors,
        }

    @api.model
    def _notary_claim_for_evidence_accessor(self, provider_code, claim_code, alias, context_type):
        Provider = self.env["spp.data.provider"]
        Claim = self.env["spp.notary.claim"]
        slug = Claim._slug_part

        providers = Provider.search([("provider_kind", "=", "notary")])
        matching_providers = providers.filtered(
            lambda provider: provider_code in {slug(provider.code), slug(provider.name)}
        )
        if not matching_providers:
            return Claim, _("Unknown Notary provider '%s' in evidence accessor.") % provider_code
        if len(matching_providers) > 1:
            return Claim, _("Notary provider code '%s' is ambiguous.") % provider_code

        provider = matching_providers[0]
        claims = provider.notary_claim_ids.filtered(lambda claim: claim.active and claim.variable_id)
        matching_claims = claims.filtered(lambda claim: claim._evidence_claim_code() == claim_code)
        if not matching_claims:
            return Claim, _("Unknown Notary claim '%(claim)s' for provider '%(provider)s'.") % {
                "claim": claim_code,
                "provider": provider_code,
            }
        if len(matching_claims) > 1:
            return Claim, _("Notary claim code '%(claim)s' for provider '%(provider)s' is ambiguous.") % {
                "claim": claim_code,
                "provider": provider_code,
            }

        claim = matching_claims[0]
        subject_context = "individual" if alias == "m" or context_type == "individual" else "group"
        if subject_context == "individual" and claim.subject_type == "group":
            return Claim, _("Notary claim '%s' cannot be used for individual subjects.") % claim_code
        if subject_context == "group" and claim.subject_type == "individual":
            return Claim, _("Notary claim '%s' cannot be used for group subjects.") % claim_code
        return claim, None

    @api.model
    def _errors_for_bare_notary_variables(self, expression):
        try:
            from odoo.addons.spp_cel_domain.services.cel_parser import Lexer
        except ImportError:
            return []

        token_names = {token.value for token in Lexer(expression).tokens() if token.kind in ("IDENT",)}
        if not token_names:
            return []

        Variable = self.env["spp.cel.variable"]
        variables = Variable.search(
            [
                ("active", "=", True),
                ("source_type", "=", "external"),
                "|",
                ("name", "in", list(token_names)),
                ("cel_accessor", "in", list(token_names)),
            ]
        ).filtered(lambda variable: variable.notary_claim_id)
        errors = []
        seen = set()
        for variable in variables:
            accessor = variable.cel_accessor or variable.name
            if accessor in seen:
                continue
            seen.add(accessor)
            errors.append(
                _("Bare Notary variable '%(accessor)s' is no longer supported. Use '%(explicit)s' instead.")
                % {
                    "accessor": accessor,
                    "explicit": variable.notary_claim_id._evidence_accessor("r"),
                }
            )
        return errors
