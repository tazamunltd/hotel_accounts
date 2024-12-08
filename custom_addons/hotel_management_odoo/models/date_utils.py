from odoo import api, fields, models
from datetime import datetime
import pytz

def get_sa_datetime():
    """Get current datetime in Saudi Arabia timezone"""
    sa_tz = pytz.timezone('Asia/Riyadh')
    utc_dt = datetime.now(pytz.UTC)
    return utc_dt.astimezone(sa_tz)

class RoomBookingDatetime(models.Model):
    _inherit = 'room.booking'

    @api.model
    def default_get(self, fields_list):
        """Override default_get to set Saudi Arabia timezone for datetime fields"""
        res = super(RoomBookingDatetime, self).default_get(fields_list)
        
        if 'checkin_date' in fields_list:
            sa_datetime = get_sa_datetime()
            res['checkin_date'] = fields.Datetime.to_string(sa_datetime)
            
        return res

    @api.model
    def create(self, vals):
        """Override create to ensure dates are in Saudi Arabia timezone"""
        if 'checkin_date' in vals:
            sa_tz = pytz.timezone('Asia/Riyadh')
            checkin_dt = fields.Datetime.from_string(vals['checkin_date'])
            if checkin_dt.tzinfo is None:
                checkin_dt = pytz.UTC.localize(checkin_dt)
            vals['checkin_date'] = fields.Datetime.to_string(checkin_dt.astimezone(sa_tz))
            
        if 'checkout_date' in vals:
            sa_tz = pytz.timezone('Asia/Riyadh')
            checkout_dt = fields.Datetime.from_string(vals['checkout_date'])
            if checkout_dt.tzinfo is None:
                checkout_dt = pytz.UTC.localize(checkout_dt)
            vals['checkout_date'] = fields.Datetime.to_string(checkout_dt.astimezone(sa_tz))
            
        return super(RoomBookingDatetime, self).create(vals)

    def write(self, vals):
        """Override write to ensure dates are in Saudi Arabia timezone"""
        if 'checkin_date' in vals:
            sa_tz = pytz.timezone('Asia/Riyadh')
            checkin_dt = fields.Datetime.from_string(vals['checkin_date'])
            if checkin_dt.tzinfo is None:
                checkin_dt = pytz.UTC.localize(checkin_dt)
            vals['checkin_date'] = fields.Datetime.to_string(checkin_dt.astimezone(sa_tz))
            
        if 'checkout_date' in vals:
            sa_tz = pytz.timezone('Asia/Riyadh')
            checkout_dt = fields.Datetime.from_string(vals['checkout_date'])
            if checkout_dt.tzinfo is None:
                checkout_dt = pytz.UTC.localize(checkout_dt)
            vals['checkout_date'] = fields.Datetime.to_string(checkout_dt.astimezone(sa_tz))
            
        return super(RoomBookingDatetime, self).write(vals)
