from odoo import models, fields, api

class GroupBooking(models.Model):
    _inherit = 'group.booking'

    has_master_folio = fields.Boolean(default=False)
