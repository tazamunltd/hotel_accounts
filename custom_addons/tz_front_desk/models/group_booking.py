from odoo import models, fields

class GroupBooking(models.Model):
    _inherit = 'group.booking'

    description = fields.Text(string='Description')
    discount = fields.Float(string='Discount (%)')
    reopen = fields.Boolean(string='Open or reopen a group account automatically')
    obsolete = fields.Boolean(string='Obsolete')
