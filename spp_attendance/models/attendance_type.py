from odoo import fields, models


class SPPAttendanceType(models.Model):
    _name = "spp.attendance.type"
    _description = "Attendance Type"
    _order = "name ASC"

    name = fields.Char(required=True)
    description = fields.Char()

    _name_uniq = models.Constraint("unique(name)", "Attendance Type must be unique!")
