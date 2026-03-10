import logging

from odoo import api, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class IrFieldsConverter(models.AbstractModel):
    _inherit = "ir.fields.converter"

    @api.model
    def db_id_for(self, model, field, subfield, value, savepoint):
        """Override to scope name_search by field domain during CSV import.

        When importing Many2one fields pointing to spp.vocabulary.code,
        multiple vocabulary codes may share the same display name across
        different vocabularies. This passes the field's domain as extra
        search criteria via _import_name_search_domain context key so
        name_search can disambiguate.
        """
        if (
            subfield is None
            and getattr(field, "comodel_name", None) == "spp.vocabulary.code"
            and getattr(field, "domain", None)
        ):
            domain = field.domain
            if isinstance(domain, str):
                try:
                    domain = safe_eval(  # nosemgrep: odoo-unsafe-safe-eval
                        domain, {"context": self.env.context}
                    )
                except Exception as e:
                    _logger.warning(
                        "Failed to evaluate domain %r for field %s on model %s;"
                        "skipping domain scoping during import. Error: %r",
                        domain,
                        getattr(field, "name", "<unknown>"),
                        model._name if model else "<unknown>",
                        e,
                    )
                    domain = []
            if isinstance(domain, list) and domain:
                return super(
                    IrFieldsConverter,
                    self.with_context(_import_name_search_domain=domain),
                ).db_id_for(model, field, subfield, value, savepoint)
        return super().db_id_for(model, field, subfield, value, savepoint)
