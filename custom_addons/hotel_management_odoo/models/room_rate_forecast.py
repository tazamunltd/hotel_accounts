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

    # @api.depends('rate', 'meals', 'packages', 'fixed_post')
    # def _compute_total(self):
    #     for record in self:
    #         record.total = record.rate + record.meals + record.packages + record.fixed_post + record.total
    #         record.before_discount = record.rate + record.meals + record.packages + record.fixed_post