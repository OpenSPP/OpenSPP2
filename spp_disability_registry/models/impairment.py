from odoo import fields, models


class SppDisabilityImpairment(models.Model):
    _name = "spp.disability.impairment"
    _description = "Disability Impairment Classification"
    _rec_name = "impairment_type_id"
    _order = "severity_sequence desc, id"

    assessment_id = fields.Many2one(
        "spp.disability.assessment",
        string="Assessment",
        required=True,
        ondelete="cascade",
        index=True,
    )
    impairment_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Impairment Type",
        required=True,
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:dci:cd:dr:01')]",
    )
    impairment_cause_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Impairment Cause",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:dci:cd:dr:03')]",
    )
    severity_level_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Severity Level",
        domain="[('vocabulary_id.namespace_uri', '=', 'urn:dci:cd:dr:02')]",
    )
    # Stored so the assessment can roll up the "most severe" line and the list
    # can order by severity.
    severity_sequence = fields.Integer(
        related="severity_level_id.sequence",
        store=True,
    )
