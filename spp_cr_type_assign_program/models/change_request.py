from odoo import models


class SPPChangeRequest(models.Model):
    """Custom conflict-detection hook for the assign-program CR type.

    The rule uses `scope='custom'`, so the base domain does not pre-filter by
    registrant. We narrow the candidate set to those targeting the same
    `(registrant, program)` pair: two CRs assigning the same registrant to
    *different* programs may proceed, and two CRs assigning *different*
    registrants to the same program may also proceed.
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

        # `check_same_type_only=True` on our rule guarantees all candidates
        # share our detail model, but defend against edge cases where a
        # candidate has no detail yet.
        detail_model = my_detail._name
        candidate_detail_ids = [
            c.detail_res_id for c in candidates if c.detail_res_model == detail_model and c.detail_res_id
        ]
        if not candidate_detail_ids:
            return self.env["spp.change.request"]

        matching_detail_ids = set(
            self.env[detail_model]
            .search(
                [
                    ("id", "in", candidate_detail_ids),
                    ("program_id", "=", my_detail.program_id.id),
                ]
            )
            .ids
        )
        return candidates.filtered(
            lambda c: c.detail_res_id in matching_detail_ids and c.registrant_id == self.registrant_id
        )
