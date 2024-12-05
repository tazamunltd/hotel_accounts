from datetime import datetime, timedelta
from odoo import api, fields, models, _

class RoomPayment(models.Model):
    _name = "room.payment"
    _order = 'create_date desc'
    _description = "Hotel Room Payment"

    reference = fields.Char(string="Reference")
    room_booking_id = fields.Many2one('room.booking', string='Room Bookings')
    amount = fields.Float(string="Amount")
    currency = fields.Char(string="Currency")
    name = fields.Char(string="Name")
    channel = fields.Char(string="Channel")
    category = fields.Char(string="Category")
    locale = fields.Char(string="Locale")
    order_id = fields.Char(string="Order ID")
    payment_type = fields.Selection(
        [
            ('card', 'Card'),
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('online', 'Online'),
        ],
        string="Payment Type",
    )
    payment_status = fields.Selection(
        [
            ('paid', 'Paid'),
            ('unpaid', 'Unpaid'),
        ],
        string="Payment Status",
    )