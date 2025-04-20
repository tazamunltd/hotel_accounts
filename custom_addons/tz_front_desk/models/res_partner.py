from odoo import fields, models, api


class RssPartner(models.Model):
    _inherit = 'res.partner'

    is_guest = fields.Char()
#     We are waiting for Neomoment for finish this first and take it from them, because to be the same approach
