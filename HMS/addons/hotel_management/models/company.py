from odoo import api, fields, models, _

class Company(models.Model):

    _inherit = "res.company"

    location= fields.Char(string="Location")