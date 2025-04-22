from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    test_field = fields.Char(string='Test Field')
