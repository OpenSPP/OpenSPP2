from odoo import models


class JobRelateMixin(models.AbstractModel):
    _name = "spp.job.relate.mixin"
    _description = "Job Relate Mixin"

    def action_view_related_queue_jobs(self):
        """
        Create an action for opening a related queue jobs in form view
        - Create/ Inherit a model which can be delay when a function is
        called.
        - Set inherit to this model
        - Create a button to call this method
        - Override function `_get_related_job_domain` to create job domain
        :return: odoo UI action
        :rtype: dict
        :example:
        class Program(models.Model):
            _name = "spp.program"
            _inherit = ["spp.job.relate.mixin", ...]

            def _get_related_job_domain(self):
                return [("id", "in", [1, 2, 3])]
        """
        self.ensure_one()
        action = self.env.ref("queue_job.action_queue_job").read()[0]
        action["domain"] = self._get_related_job_domain()

        return action

    def _get_related_job_domain(self):
        """
        Override this function for creating related job queue domain for
        filtering to action.
        :return: odoo domain
        :rtype: list
        """
        raise NotImplementedError()
