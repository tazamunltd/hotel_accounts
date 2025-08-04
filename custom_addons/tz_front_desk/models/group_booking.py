from odoo import models, fields

class GroupBooking(models.Model):
    _inherit = 'group.booking'

    has_master_folio = fields.Boolean(default=False)

    state = fields.Selection([
        ('in', 'In'),
        ('out', 'Out')
    ], string='State', default='in')

    # Redefining computed fields with store=True
    first_visit = fields.Date(
        string='First Arrive',
        compute='_compute_first_and_last_visit',
        store=True,
        tracking=True,
    )

    last_visit = fields.Date(
        string='Last Departure',
        compute='_compute_first_and_last_visit',
        store=True,
        tracking=True,
    )
