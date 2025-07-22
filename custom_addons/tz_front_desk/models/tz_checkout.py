from odoo import models, fields, tools, api, _
from odoo.exceptions import UserError, ValidationError


class TzCheckout(models.Model):
    _name = 'tz.checkout'
    _description = 'FrontDesk Checkout'
    _auto = False
    _check_company_auto = True

    name = fields.Char('Room')
    all_name = fields.Char('Room', compute='_compute_name', store=False)
    booking_id = fields.Many2one('room.booking', string='Booking Id')
    group_booking_id = fields.Many2one('group.booking', string='Group Booking')
    dummy_id = fields.Many2one('tz.dummy.group', string='Dummy')
    room_id = fields.Many2one('hotel.room', string='Room')
    partner_id = fields.Many2one('res.partner', string='Guest')
    checkin_date = fields.Datetime('Check-in Date')
    checkout_date = fields.Datetime('Check-out Date')
    adult_count = fields.Integer('Adults')
    child_count = fields.Integer('Children')
    infant_count = fields.Integer('Infants')
    rate_code = fields.Many2one('rate.code', string='Rate Code')
    meal_pattern = fields.Many2one('meal.pattern', string='Meal Pattern')
    state = fields.Char('Status')
    company_id = fields.Many2one('res.company', string='Company')
    v_state = fields.Char('Status', compute='_compute_v_state', store=False)
    folio_id = fields.Many2one('tz.master.folio', string="Master Folio")

    # def _compute_name(self):
    #     for record in self:
    #         if record.partner_id:
    #             # Check if this is a group booking
    #             group_booking = self.env['group.booking'].search([
    #                 ('company', '=', record.partner_id.id),
    #                 ('status_code', '=', 'confirmed')
    #             ], limit=1)
    #             if group_booking:
    #                 # Handle group name which might be a translation dictionary
    #                 if isinstance(group_booking.group_name, dict):
    #                     record.all_name = group_booking.group_name.get('en_US', 'Unnamed')
    #                 else:
    #                     record.all_name = group_booking.group_name or 'Unnamed'
    #             elif record.room_id:
    #                 # Handle room name which might be a string or translation dict
    #                 if isinstance(record.room_id.name, dict):
    #                     record.all_name = record.room_id.name.get('en_US', 'Unnamed')
    #                 else:
    #                     record.all_name = record.room_id.name or 'Unnamed'
    #             else:
    #                 record.all_name = 'Unnamed'
    #         elif not record.room_id and not record.partner_id:
    #             # For dummy groups, use the name from the view
    #             record.all_name = record.name
    #         else:
    #             record.all_name = record.name
    #
    # def _compute_v_state(self):
    #     for record in self:
    #         # If it's from room_booking (has room_id)
    #         if record.room_id:
    #             record.v_state = 'In' if record.state == 'check_in' else 'Out'
    #         # If it's from group_booking (no room_id but has partner_id)
    #         elif record.partner_id:
    #             # We need to check if it's confirmed and has room bookings
    #             group_booking = self.env['group.booking'].search([
    #                 ('company', '=', record.partner_id.id),
    #                 ('status_code', '=', 'confirmed')
    #             ], limit=1)
    #             if group_booking and group_booking.room_booking_ids:
    #                 record.v_state = 'In'
    #             else:
    #                 record.v_state = 'Out'
    #         # If it's from dummy group (no room_id and no partner_id)
    #         else:
    #             record.v_state = 'In' if record.state == 'in' else 'Out'
    #
    # def search(self, domain, offset=0, limit=None, order=None):
    #     return super().search(domain, offset=offset, limit=limit, order=order)


