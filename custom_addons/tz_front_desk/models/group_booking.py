from odoo import models, fields

class GroupBooking(models.Model):
    _inherit = 'group.booking'

    description = fields.Text(string='Description')
    discount = fields.Float(string='Discount (%)')
    reopen = fields.Boolean(string='Open or reopen a group account automatically', default=False)
    has_master_folio = fields.Boolean(default=False)
    is_fake = fields.Boolean(string='Is Fake', default=False)
    obsolete = fields.Boolean(string='Obsolete', default=False)

    def create(self, vals):
        vals['is_fake'] = True
        return super(GroupBooking, self).create(vals)


