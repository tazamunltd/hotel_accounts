from odoo import models, fields

class RateCode(models.Model):
    _name = 'rate.code'
    _description = 'Rate Code'

    rate_code = fields.Char(string="Rate Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    category = fields.Selection([
        ('corp', 'CORP'),
        ('line', 'LINE'),
        ('grps', 'GRPS'),
        ('ndv', 'NDV')
    ], string="Category")
    user_sort = fields.Integer(string="User Sort")
    obsolete = fields.Boolean(string="Obsolete", default=False)



class RatePromotion(models.Model):
    _name = 'rate.promotion'
    _description = 'Rate Promotion'

    id_number = fields.Char(string="ID#", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    buy = fields.Integer(string="Buy")
    get = fields.Integer(string="Get")
    valid_from = fields.Date(string="Valid From")
    valid_to = fields.Date(string="Valid To")
