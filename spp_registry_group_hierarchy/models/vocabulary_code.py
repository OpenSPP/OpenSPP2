# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class SPPVocabularyCode(models.Model):
    """Extend vocabulary code with group hierarchy flag.

    Adds allow_all_member_type to group type vocabulary codes so that
    groups of that type can contain both individuals and other groups
    as members (group-of-groups / cooperatives).
    """

    _inherit = "spp.vocabulary.code"

    allow_all_member_type = fields.Boolean(
        string="Allow group and individual members",
        default=False,
        help="When enabled on a group type, groups of this type can contain "
        "both individual registrants and other groups as members.",
    )
