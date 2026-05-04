from odoo import models


class SPPChangeRequest(models.Model):
    """Custom conflict-detection hook for the assign-program CR type.

    The base conflict rule scoped to the same registrant flags every in-flight
    `assign_program` CR for that registrant. We narrow the match to those
    targeting the same `(registrant, program)` pair so two CRs assigning the
    same registrant to *different* programs are allowed to proceed.
    """

    _inherit = "spp.change.request"

    def _check_custom_conflicts(self, candidates, rule):
        candidates = super()._check_custom_conflicts(candidates, rule)

        rule_xmlid = "spp_cr_type_assign_program.cr_conflict_rule_assign_program_duplicate"
        our_rule = self.env.ref(rule_xmlid, raise_if_not_found=False)
        if not our_rule or rule != our_rule:
            return candidates

        my_detail = self.get_detail()
        if not my_detail or not my_detail.program_id:
            return self.env["spp.change.request"]

        my_program = my_detail.program_id
        matching = self.env["spp.change.request"]
        for candidate in candidates:
            cand_detail = candidate.get_detail()
            if cand_detail and cand_detail.program_id == my_program:
                matching |= candidate
        return matching
