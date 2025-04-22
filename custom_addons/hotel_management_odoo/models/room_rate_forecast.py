from datetime import datetime, timedelta

# from cryptography.utils import read_only_property

from odoo import api, fields, models, _
from odoo import exceptions
from odoo.api import ondelete
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import pytz


class RoomRateForecast(models.Model):
    _name = 'room.rate.forecast'
    _description = 'Room Rate Forecast'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    room_booking_id = fields.Many2one('room.booking', string='Room Bookings',tracking=True)
    date = fields.Date(string="Date", required=True,tracking=True)
    rate = fields.Float(string="Rate",tracking=True)
    meals = fields.Float(string="Meals",tracking=True)
    packages = fields.Float(string="Packages",tracking=True)
    fixed_post = fields.Float(string="Fixed Post",tracking=True)
    total = fields.Float(string="Total",tracking=True)
    before_discount = fields.Float(string="Before Discount",tracking=True)

    booking_line_ids = fields.Many2many(
        'room.booking.line',
        'room_forecast_booking_line_rel',  # Relation table name
        'forecast_id',  # Field in the relation table for room.rate.forecast
        'booking_line_id',  # Field in the relation table for room.booking.line
        string="Room Lines",
        help="Related room booking lines for this forecast."
    )