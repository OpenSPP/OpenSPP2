# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
from odoo import models
from odoo.tools import safe_eval


class BaseManager(models.AbstractModel):
    _name = "spp.base.programs.manager"
    _description = "Base Manager"

    def _get_eval_context(self):
        """Prepare the context used when evaluating python code
        :returns: dict -- evaluation context given to safe_eval
        """
        return {
            "datetime": safe_eval.datetime,
            "dateutil": safe_eval.dateutil,
            "time": safe_eval.time,
            "uid": self.env.uid,
            "user": self.env.user,
        }

    def _safe_eval(self, string, locals_dict=None):
        """Evaluates a string containing a Python expression.
        :param string: string expression to be evaluated
        :param locals_dict: local variables for evaluation
        :returns: the result of the evaluation
        """
        eval_context = self._get_eval_context()
        if locals_dict:
            eval_context.update(locals_dict)
        # Domain and expression strings here come from admin-managed configuration
        # (e.g., eligibility and payment managers), and the evaluation context only
        # exposes datetime/dateutil/time and the current user.
        return safe_eval.safe_eval(  # nosemgrep: odoo-unsafe-safe-eval - Used for admin-defined domains/expressions with a restricted evaluation context.
            string, eval_context
        )
