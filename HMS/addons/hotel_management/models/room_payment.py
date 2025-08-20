from datetime import datetime, timedelta
from odoo import api, fields, models, _

class RoomPayment(models.Model):
    _name = "room.payment"
    _order = 'create_date desc'
    _description = "Hotel Room Payment"
    _inherit = ['mail.thread', 'mail.activity.mixin']


    reference = fields.Char(string="Reference",tracking=True)
    room_booking_id = fields.Many2one('room.booking', string='Room Bookings',tracking=True)
    amount = fields.Float(string="Amount",tracking=True)
    currency = fields.Char(string="Currency",tracking=True)
    name = fields.Char(string="Name",tracking=True)
    channel = fields.Char(string="Channel",tracking=True)
    category = fields.Char(string="Category",tracking=True)
    locale = fields.Char(string="Locale",tracking=True)
    order_id = fields.Char(string="Order ID",tracking=True)
    payment_type = fields.Selection(
        [
            ('card', 'Card'),
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('online', 'Online'),
        ],
        string="Payment Type"
    ,tracking=True)
    payment_status = fields.Selection(
        [
            ('paid', 'Paid'),
            ('unpaid', 'Unpaid'),
        ],
        string="Payment Status",tracking=True)