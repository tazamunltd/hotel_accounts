
from odoo import fields, models


class AccountMove(models.Model):
    """Inherited account. move for adding hotel booking reference field to
    invoicing model."""
    _inherit = "account.move"
    

    hotel_booking_id = fields.Many2one('room.booking',
                                       string="Booking Reference",
                                       readonly=True, help="Choose the Booking"
                                                           "Reference")
