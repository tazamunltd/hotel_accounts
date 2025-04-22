from odoo import models, fields

class RateCode(models.Model):
    _name = 'rate.code'
    _description = 'Rate Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    rate_code = fields.Char(string="Rate Code", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    category = fields.Selection([
        ('corp', 'CORP'),
        ('line', 'LINE'),
        ('grps', 'GRPS'),
        ('ndv', 'NDV')
    ], string="Category",tracking=True)
    user_sort = fields.Integer(string="User Sort",tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)



class RatePromotion(models.Model):
    _name = 'rate.promotion'
    _description = 'Rate Promotion'
    _inherit = ['mail.thread', 'mail.activity.mixin']



    id_number = fields.Char(string="ID#", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    buy = fields.Integer(string="Buy",tracking=True)
    get = fields.Integer(string="Get",tracking=True)
    valid_from = fields.Date(string="Valid From",tracking=True)
    valid_to = fields.Date(string="Valid To",tracking=True)
