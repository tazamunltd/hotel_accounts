from odoo import api, fields, models
from datetime import datetime
import pytz

def get_sa_datetime():
    """Get current datetime in Saudi Arabia timezone"""
    sa_tz = pytz.timezone('Asia/Riyadh')
    # Create datetime with user's timezone
    user_tz = pytz.timezone('Asia/Kolkata')  # Your timezone is +05:30
    local_dt = user_tz.localize(datetime.now())
    # Convert to UTC first
    utc_dt = local_dt.astimezone(pytz.UTC)
    # Then convert to Saudi timezone
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
            checkin_dt = fields.Datetime.from_string(vals['checkin_date'])
            if checkin_dt.tzinfo is None:
                # If no timezone info, assume it's in user's timezone (Asia/Kolkata)
                user_tz = pytz.timezone('Asia/Kolkata')
                checkin_dt = user_tz.localize(checkin_dt)
            # Convert to Saudi timezone
            sa_tz = pytz.timezone('Asia/Riyadh')
            vals['checkin_date'] = fields.Datetime.to_string(checkin_dt.astimezone(sa_tz))
            
        if 'checkout_date' in vals:
            checkout_dt = fields.Datetime.from_string(vals['checkout_date'])
            if checkout_dt.tzinfo is None:
                # If no timezone info, assume it's in user's timezone (Asia/Kolkata)
                user_tz = pytz.timezone('Asia/Kolkata')
                checkout_dt = user_tz.localize(checkout_dt)
            # Convert to Saudi timezone
            sa_tz = pytz.timezone('Asia/Riyadh')
            vals['checkout_date'] = fields.Datetime.to_string(checkout_dt.astimezone(sa_tz))
            
        return super(RoomBookingDatetime, self).create(vals)

    def write(self, vals):
        """Override write to ensure dates are in Saudi Arabia timezone"""
        if 'checkin_date' in vals:
            checkin_dt = fields.Datetime.from_string(vals['checkin_date'])
            if checkin_dt.tzinfo is None:
                # If no timezone info, assume it's in user's timezone (Asia/Kolkata)
                user_tz = pytz.timezone('Asia/Kolkata')
                checkin_dt = user_tz.localize(checkin_dt)
            # Convert to Saudi timezone
            sa_tz = pytz.timezone('Asia/Riyadh')
            vals['checkin_date'] = fields.Datetime.to_string(checkin_dt.astimezone(sa_tz))
            
        if 'checkout_date' in vals:
            checkout_dt = fields.Datetime.from_string(vals['checkout_date'])
            if checkout_dt.tzinfo is None:
                # If no timezone info, assume it's in user's timezone (Asia/Kolkata)
                user_tz = pytz.timezone('Asia/Kolkata')
                checkout_dt = user_tz.localize(checkout_dt)
            # Convert to Saudi timezone
            sa_tz = pytz.timezone('Asia/Riyadh')
            vals['checkout_date'] = fields.Datetime.to_string(checkout_dt.astimezone(sa_tz))
            
        return super(RoomBookingDatetime, self).write(vals)
