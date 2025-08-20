import ast
import psycopg2
from odoo.exceptions import UserError
from odoo import api, fields, models, _
from odoo import exceptions
from odoo.exceptions import ValidationError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.safe_eval import pytz
import bcrypt
import convertdate.islamic as hijri
import datetime
# from ummalqura import umalqura
from hijri_converter import Gregorian
import logging
from datetime import datetime, timedelta, date, time
from odoo.models import NewId
from odoo.fields import Datetime
from pytz import timezone
import re
from collections import defaultdict
from odoo.tools.translate import _
from odoo.tools.float_utils import float_round
from textwrap import dedent

_logger = logging.getLogger(__name__)

class RoomBooking(models.Model):
    """Model that handles the hotel room booking and all operations related
     to booking"""
    _name = "room.booking"
    _order = 'create_date desc'
    _description = "Waiting List Room Availability"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    checkin_date_only = fields.Date(compute="_compute_date_only", store=False)
    checkout_date_only = fields.Date(compute="_compute_date_only", store=False)

    def action_room_assignment_wizard(self):
        """Button on booking to open wizard with computed floors"""
        # self.ensure_one()

        # min_floor = max_floor = floor_from = floor_to = 0

        # if self.hotel_room_type:
        #     rooms = self.env['hotel.room'].search([
        #         ('room_type_name', '=', self.hotel_room_type.id),
        #         ('active', '=', True)
        #     ])
        #     floor_numbers = []
        #     for r in rooms:
        #         if r.fsm_location and r.fsm_location.name:
        #             match = re.search(r'\d+', r.fsm_location.name)
        #             if match:
        #                 floor_numbers.append(int(match.group()))

        #     if floor_numbers:
        #         min_floor = min(floor_numbers)
        #         max_floor = max(floor_numbers)
        #         floor_from = min_floor
        #         floor_to = max_floor

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'room.assignment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'name': 'Floor Selection',
            'context': {
                'default_booking_id': self.id,
                # 'default_min_floor': min_floor,
                # 'default_max_floor': max_floor,
                # 'default_floor_from': floor_from,
                # 'default_floor_to': floor_to,
            }
        }

    discount = fields.Float(
        string="Discount",
        compute="_compute_discount",
        store=True,
        tracking=True
    )

    @api.depends('state', 'rate_forecast_ids.total', 'rate_forecast_ids.before_discount', 'room_count')
    def _compute_discount(self):
        for booking in self:
            if booking.state in ['confirmed', 'block', 'check_in', 'check_out'] and booking.rate_forecast_ids:
                # Take first line (sorted by date or id)
                first_line = booking.rate_forecast_ids.sorted(key=lambda r: r.date)[0]
                diff =  first_line.before_discount - first_line.total 
                booking.discount = diff / booking.room_count if booking.room_count else 0.0

            else:
                booking.discount = 0.0
            # print(f"Booking ID {booking.id} → Calculated Discount: {booking.discount}")

    @api.depends('checkin_date', 'checkout_date')
    def _compute_date_only(self):
        for r in self:
            r.checkin_date_only = r.checkin_date.date() if r.checkin_date else False
            r.checkout_date_only = r.checkout_date.date() if r.checkout_date else False

    def action_unarchive_record(self):
        for record in self:
            record.active = True
    
    previous_room_count = fields.Integer(string='Previous Room Count')

    def action_open_room_booking_update_wizard(self):
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return {'type': 'ir.actions.act_window_close'}

        bookings = self.env['room.booking'].browse(active_ids)
        if all(not booking.parent_booking_id for booking in bookings):
            # allowed_states = {'confirmed', 'not_confirmed'}
            allowed_states = {'confirmed', 'not_confirmed','block', 'check_in'}
            if all(booking.state in allowed_states for booking in bookings):
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Update Room Booking',
                    'res_model': 'room.booking.update.wizard',
                    'view_mode': 'form',
                    'view_id': self.env.ref('hotel_management.view_room_booking_update_wizard').id,
                    'target': 'new',
                }
        
        # Separate parent and child bookings
        parent_bookings = bookings.filtered(lambda b: not b.parent_booking_id)
        child_bookings = bookings.filtered(lambda b: b.parent_booking_id)

        # --- Condition 1: Only child bookings ---
        if child_bookings and not parent_bookings:
            parent_booking_id = child_bookings[0].parent_booking_id
            for booking in child_bookings:
                if booking.parent_booking_id != parent_booking_id:
                    raise UserError("Please select only child bookings with the same parent booking ID.")
        
        # --- Condition 2: Parent booking + its children ---
        elif child_bookings and parent_bookings:
            if len(parent_bookings) > 1:
                raise UserError("Only one parent booking can be selected with its children.")
            parent_booking_id = child_bookings[0].parent_booking_id
            for booking in child_bookings:
                if booking.parent_booking_id != parent_booking_id:
                    raise UserError("All child bookings must have the same parent booking ID.")
            # Ensure the selected parent matches the child's parent
            if parent_bookings[0].id != parent_booking_id.id:
                raise UserError("Selected parent booking does not match the children's parent booking.")
        
        else:
            # If only parent(s) without children or multiple parents -> not allowed
            raise UserError("Please select either only child bookings (same parent) or parent booking with its children.")

        # If validation passes, return wizard action
        return {
            'type': 'ir.actions.act_window',
            'name': 'Update Room Booking',
            'res_model': 'room.booking.update.wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('hotel_management.view_room_booking_update_wizard').id,
            'target': 'new',
        }

    @api.model
    def check_extended_room_conflicts(self, booking_id, new_checkout_str):
        booking = self.browse(booking_id)
        try:
            try:
                new_checkout_date = datetime.strptime(new_checkout_str, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                new_checkout_date = datetime.strptime(new_checkout_str, "%d/%m/%Y %H:%M")
        except Exception as e:
            _logger.debug(f"❌ Date parsing failed for '{new_checkout_str}': {e}")
            return {'has_conflict': False, 'conflicted_rooms': []}

        # _logger.debug(f"\n✅ Booking ID: {booking_id}")
        # _logger.debug(f"🟢 New Checkout Date from JS: {new_checkout_date}")
        # _logger.debug(f"🟡 Original Check-in Date: {booking.checkin_date}")

        conflict_rooms = []
        for line in booking.room_line_ids:
            if not line.room_id:
                _logger.debug("⚠ Skipping line without room_id")
                continue
            domain = [
                ('room_id', '=', line.room_id.id),
                ('id', '!=', line.id),
                ('state_', 'in', ['block', 'check_in']),
                ('checkin_date', '<=', new_checkout_date),  # booking started before or at new checkout
                ('checkout_date', '>=', booking.checkin_date),  # booking ends after new checkout
            ]

            overlap = self.env['room.booking.line'].search_count(domain)
            # _logger.debug(f"❗ Overlapping Bookings: {overlap}")

            if overlap:
                conflict_rooms.append(line.room_id.display_name)

        # _logger.debug(f"\n🚨 Conflicted Rooms: {conflict_rooms}")
        return {
            'has_conflict': bool(conflict_rooms),
            'conflicted_rooms': conflict_rooms,
        }
        

    @api.model
    def check_extended_reservation_conflicts(self, booking_id, new_checkin_str, new_checkout_str):
        booking = self.browse(booking_id)
        def _parse(dt_str):
            for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
                try:
                    return datetime.strptime(dt_str, fmt)
                except ValueError:
                    continue
            raise ValueError(f"Invalid date format: {dt_str}")

        try:
            new_ci = _parse(new_checkin_str)
            new_co = _parse(new_checkout_str)
        except Exception as e:
            _logger.error("Failed to parse dates %s, %s: %s", new_checkin_str, new_checkout_str, e)
            return {'has_conflict': False, 'conflicted_rooms': []}

        conflicts = []
        for line in booking.room_line_ids:
            if not line.room_id:
                continue

            # overlap if existing.checkin <= new_co AND existing.checkout >= new_ci
            domain = [
                ('room_id', '=', line.room_id.id),
                ('id', '!=', line.id),
                ('state_', 'in', ['block', 'check_in']),
                ('checkin_date', '<=', new_co),
                ('checkout_date', '>=', new_ci),
            ]
            if self.env['room.booking.line'].search_count(domain):
                conflicts.append(line.room_id.display_name)

        return {
            'has_conflict': bool(conflicts),
            'conflicted_rooms': conflicts,
        }


    @api.model
    def check_block_date_conflicts(self, booking_id, new_date_str, is_checkin=False):
        booking = self.browse(booking_id)
        try:
            try:
                new_date = datetime.strptime(new_date_str, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                new_date = datetime.strptime(new_date_str, "%d/%m/%Y %H:%M")
        except Exception as e:
            print(f"❌ Date parsing failed for '{new_date_str}': {e}")
            return {'has_conflict': False, 'conflicted_rooms': []}

        # print(f"\n✅ Block Booking ID: {booking_id}")
        if is_checkin:
            start_date = new_date
            end_date = booking.checkout_date
        else:
            start_date = booking.checkin_date
            end_date = new_date
            
        # Make sure we have valid dates for comparison
        if not start_date or not end_date or start_date >= end_date:
            print("⚠ Invalid date range: start_date must be before end_date")
            return {'has_conflict': True, 'conflicted_rooms': ['Invalid date range']}

        conflict_rooms = []
        for line in booking.room_line_ids:
            if not line.room_id:
                print("⚠ Skipping line without room_id")
                continue


            # Check if any bookings overlap with our new date range
            domain = [
                ('room_id', '=', line.room_id.id),
                ('id', '!=', line.id),
                ('state_', 'in', ['block', 'check_in']),
                '|',
                    '&', ('checkin_date', '<', end_date),   # starts before our end
                         ('checkout_date', '>', start_date), # ends after our start
                    '&', ('checkin_date', '>=', start_date), # starts during our period
                         ('checkin_date', '<', end_date),    # but before our end
            ]

            overlap = self.env['room.booking.line'].search_count(domain)

            if overlap:
                conflict_rooms.append(line.room_id.display_name)

        # print(f"\n🚨 Conflicted Rooms: {conflict_rooms}")
        return {
            'has_conflict': bool(conflict_rooms),
            'conflicted_rooms': conflict_rooms,
        }
    

    def _check_checkout_availability(self, new_checkout_date, is_checkin_change):
        conflict_rooms = []
        for line in self.room_line_ids:
            if not line.room_id:
                _logger.warning("⚠ Skipping line without room_id")
                continue

            # Use checkin_date or checkout_date depending on change type
            check_date = self.checkin_date if is_checkin_change else self.checkout_date

            # Search for overlapping bookings
            domain = [
                ('room_id', '=', line.room_id.id),
                ('id', '!=', line.id),
                ('booking_id', '!=', self.id),
                ('state_', 'in', ['block', 'check_in']),
                ('checkin_date', '<=', new_checkout_date),
                ('checkout_date', '>=', check_date),
            ]
            conflict_lines = self.env['room.booking.line'].search(domain)
            my_checkout_date = new_checkout_date if isinstance(new_checkout_date, date) else new_checkout_date.date()
            filtered_conflicts = conflict_lines.filtered(
                lambda l: l.booking_id.checkin_date
                        and l.booking_id.checkin_date.date() != my_checkout_date
            )
            
            if filtered_conflicts and len(filtered_conflicts) > 0:
                conflict_rooms.append(line.room_id.display_name)
        
        # Raise error only if there are actual conflicts after filtering
        if conflict_rooms:
            error_message = _(
                "The following rooms %s have a conflict with the new checkout date"
            ) % ', '.join(conflict_rooms)
            raise UserError(error_message)
        else:
            #add code here to update the room booking  line

            return True

    
    def _check_checkin_availability(self, new_checkin_date):
        conflict_rooms = []

        # Ensure new_checkin_date is a datetime.date or datetime.datetime
        if isinstance(new_checkin_date, str):
            try:
                # Try parsing as datetime first
                new_checkin_date = datetime.strptime(new_checkin_date, DEFAULT_SERVER_DATETIME_FORMAT)
            except ValueError:
                # Fallback: parse as date
                new_checkin_date = datetime.strptime(new_checkin_date, DEFAULT_SERVER_DATE_FORMAT)

        # Choose correct period to check
        if new_checkin_date < self.checkin_date:
            period_start = new_checkin_date
            period_end = self.checkin_date
        else:
            period_start = new_checkin_date
            period_end = self.checkout_date

        for line in self.room_line_ids:
            if not line.room_id:
                continue
            _logger.debug(f"line 305 {period_end}  {period_start}")
            domain = [
                ('checkin_date', '<=', period_end),
                ('checkout_date', '>=', period_start),
                ('state', 'in', ['confirmed','block', 'check_in']),
                ('id', '!=', self.id),
            ]
            overlap = self.env['room.booking'].search(domain)
            if overlap:
                conflicting_room_ids = self.env['room.booking.line'].search([
                    ('booking_id', 'in', overlap.ids),
                    ('id', '!=', line.id)
                ]).mapped('room_id.id')

                if line.room_id.id in conflicting_room_ids:
                    conflict_rooms.append(line.room_id.display_name)

        if conflict_rooms:
            raise ValidationError(_(
                "The following rooms have a conflict with the updated check-in date range:\n%s"
            ) % ", ".join(conflict_rooms))

    
    
    
    # def check_confirmed_availability_for_confirmed(self, record_id, new_checkin, new_checkout):
    #     # 3) Build parameters for the SQL with the new dates
    #     booking = self.browse(record_id)
    #     query = booking._get_room_search_query()
    #     params = {
    #         'company_id': booking.env.company.id,
    #         'from_date': new_checkin,
    #         'to_date': new_checkout,
    #         'room_count': booking.room_count,
    #         'room_type_id': booking.hotel_room_type.id if booking.hotel_room_type else None,
    #     }
    #
    #     # 4) Execute the query and fetch the results
    #     booking.env.cr.execute(query, params)
    #     rooms = booking.env.cr.dictfetchall()
    #     conflicted = []
    #     _logger.debug("cecking rooms:",rooms)
    #     for r in rooms:
    #         # Cast to int to drop ".0"
    #         min_free = int(r.get('min_free_to_sell', 0))
    #         _logger.debug("for loop started")
    #         if min_free == 0:
    #             booking_line_count = self.env['room.booking.line'].search_read(
    #                 [
    #                     ('booking_id', '=', booking.id),
    #                     ('state_', '=', 'confirmed'),
    #                     ('hotel_room_type', '=', booking.hotel_room_type.id),
    #                 ])
    #             # If the sum of adult_count equals room_count, skip conflict
    #             _logger.debug(f" %s →%s {booking_line_count}, {booking.room_count}")
    #             if len(booking_line_count) == booking.room_count:
    #                 _logger.debug("in the continue")
    #                 continue
    #             elif booking.room_count > min_free:
    #                 conflicted.append(r.get('room_type_name') or str(r.get('room_type_id')))
    #         else:
    #             if booking.room_count > min_free:
    #                 conflicted.append(r.get('room_type_name') or str(r.get('room_type_id')))
    #
    #     # for r in rooms:
    #     #     _logger.debug("  →", r)
    #     # Check if there are conflicts
    #     _logger.debug("in the continue %s",conflicted)
    #     if conflicted:
    #         # Raise ValidationError with a custom message
    #         raise ValidationError(_("Rooms are not available for the new check-in and check-out dates."))
    #     else:
    #         _logger.debug(f"[OK] Booking {record_id} can be accommodated with {booking.room_count} rooms.")
    #
    #     return {
    #         'has_conflict': bool(conflicted),
    #         'conflicted_rooms': conflicted,
    #     }
    def check_confirmed_availability_for_confirmed(self, record_id, new_checkin, new_checkout):
        """
        Enhanced validation logic for confirmed booking date changes.
        Only validates when dates extend beyond existing booking line dates.
        """
        booking = self.browse(record_id)

        # Get current booking dates for comparison
        current_checkin = booking.checkin_date
        current_checkout = booking.checkout_date

        # Convert string dates to datetime objects if needed
        if isinstance(new_checkin, str):
            try:
                new_checkin = datetime.strptime(new_checkin, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                new_checkin = datetime.strptime(new_checkin, "%Y-%m-%d")
        if isinstance(new_checkout, str):
            try:
                new_checkout = datetime.strptime(new_checkout, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                new_checkout = datetime.strptime(new_checkout, "%Y-%m-%d")

        # Check if new dates are within existing booking line date range
        if (new_checkin >= current_checkin and new_checkout <= current_checkout):
            _logger.debug("New dates are within existing range - no validation needed")
            return {'has_conflict': False, 'conflicted_rooms': []}

        # Determine search date ranges based on what changed
        search_ranges = []

        # Case 1: Check-in changed to earlier date
        if new_checkin < current_checkin:
            search_ranges.append({
                'from_date': new_checkin,
                'to_date': current_checkin,
                'reason': 'earlier_checkin'
            })
            _logger.debug(f"Check-in moved earlier: searching {new_checkin} to {current_checkin}")

        # Case 2: Check-out changed to later date
        if new_checkout > current_checkout:
            search_ranges.append({
                'from_date': current_checkout,
                'to_date': new_checkout,
                'reason': 'later_checkout'
            })
            _logger.debug(f"Check-out moved later: searching {current_checkout} to {new_checkout}")

        # If no date extensions, use original full range logic
        if not search_ranges:
            search_ranges.append({
                'from_date': new_checkin,
                'to_date': new_checkout,
                'reason': 'within_range'
            })

        conflicted = []

        # Check each search range
        for search_range in search_ranges:
            query = booking._get_room_search_query()
            # params = {
            #     'company_id': booking.env.company.id,
            #     'from_date': search_range['from_date'],
            #     'to_date': search_range['to_date'],
            #     'room_count': booking.room_count,
            #     'room_type_id': booking.hotel_room_type.id if booking.hotel_room_type else None,
            # }
            # Adjust to_date: subtract 1 day if from_date != to_date
            to_date_adjusted = search_range['to_date']
            if search_range['from_date'].date() != search_range['to_date'].date():
                to_date_adjusted = search_range['to_date'] - timedelta(days=1)

            params = {
                'company_id': booking.env.company.id,
                'from_date': search_range['from_date'],
                'to_date': to_date_adjusted,
                'room_count': booking.room_count,
                'room_type_id': booking.hotel_room_type.id if booking.hotel_room_type else None,
            }
            # Execute the query and fetch the results
            booking.env.cr.execute(query, params)
            rooms = booking.env.cr.dictfetchall()

            _logger.debug(
                f"Checking {search_range['reason']} range: {search_range['from_date']} to {search_range['to_date']}")

            for r in rooms:
                min_free = int(r.get('min_free_to_sell', 0))

                # Only validate if min_sell < booking count
                if min_free < booking.room_count:
                    _logger.debug(f"min_sell ({min_free}) < booking_count ({booking.room_count}) - validation required")

                    # Enhanced validation logic for min_sell = 0 case
                    if min_free == 0:
                        booking_line_count = self.env['room.booking.line'].search_count([
                            ('booking_id', '=', booking.id),
                            ('state_', '=', 'confirmed'),
                            ('hotel_room_type', '=', booking.hotel_room_type.id),
                        ])

                        # # Check if there are blocked rooms in the extension period that would conflict
                        # blocked_rooms_in_period = self.env['room.booking.line'].search_count([
                        #     ('hotel_room_type', '=', booking.hotel_room_type.id),
                        #     ('state_', 'in', ['confirmed','block', 'check_in']),
                        #     ('booking_id', '!=', booking.id),  # Exclude current booking
                        #     ('checkin_date', '<', search_range['to_date']),
                        #     ('checkout_date', '>', search_range['from_date']),
                        # ])
                        # For same-day checkout/checkin scenarios, we need to compare dates only, not datetime
                        blocked_rooms_in_period = self.env['room.booking.line'].search([
                            ('hotel_room_type', '=', booking.hotel_room_type.id),
                            ('state_', 'in', ['confirmed', 'block', 'check_in']),
                            ('booking_id', '!=', booking.id),  # Exclude current booking
                            ('checkin_date', '<', search_range['to_date']),
                            ('checkout_date', '>', search_range['from_date']),
                        ])


                        # Filter out rooms where checkin date equals new checkout date (same day)
                        filtered_blocked_rooms = blocked_rooms_in_period.filtered(
                            lambda r: r.checkin_date.date() != new_checkout.date()
                        )
                        # Filter based on the search range reason
                        if search_range['reason'] == 'earlier_checkin':
                            # For earlier check-in: exclude rooms where checkout date equals new checkin date (same day)
                            filtered_blocked_rooms = blocked_rooms_in_period.filtered(
                                lambda r: r.checkout_date.date() != new_checkin.date()
                            )
                        elif search_range['reason'] == 'later_checkout':
                            # For later check-out: exclude rooms where checkin date equals new checkout date (same day)
                            filtered_blocked_rooms = blocked_rooms_in_period.filtered(
                                lambda r: r.checkin_date.date() != new_checkout.date()
                            )
                        else:
                            # For within_range: no filtering needed
                            filtered_blocked_rooms = blocked_rooms_in_period

                        blocked_rooms_count = len(filtered_blocked_rooms)
                        _logger.debug(f"Booking line count: {booking_line_count}, Room count: {booking.room_count}")
                        _logger.debug(f"Blocked rooms in extension period: {blocked_rooms_in_period}")
                        _logger.debug(f"Min free to sell: {min_free}")

                        # BOTH CONDITIONS must be checked:
                        # 1. Check if room_count > min_free_to_sell (always required)
                        # 2. Check if there are blocked rooms in extension period

                        if booking.room_count > min_free:  # Condition 1: Always check this
                            if booking_line_count == booking.room_count:
                                # Even if confirmed lines match room count, check for blocked rooms
                                if blocked_rooms_count > 0:  # Condition 2: Blocked rooms exist
                                    _logger.debug(
                                        "Room count > min_free AND blocked rooms exist in extension period - validation required")
                                    conflicted.append(r.get('room_type_name') or str(r.get('room_type_id')))
                                else:
                                    _logger.debug(
                                        "Room count > min_free but no blocked rooms in extension period - no conflict")
                                    continue
                            else:
                                # Confirmed lines don't match room count and room_count > min_free
                                _logger.debug(
                                    "Room count > min_free and confirmed lines don't match room count - validation required")
                                conflicted.append(r.get('room_type_name') or str(r.get('room_type_id')))
                        else:
                            _logger.debug(
                                f"Room count ({booking.room_count}) <= min_free ({min_free}) - no validation needed")
                            continue

        # Check if there are conflicts
        _logger.debug(f"Final conflicts: {conflicted}")
        if conflicted:
            raise ValidationError(_("Rooms are not available for the new check-in and check-out dates."))
        else:
            _logger.debug(f"[OK] Booking {record_id} can be accommodated with {booking.room_count} rooms.")

        return {
            'has_conflict': bool(conflicted),
            'conflicted_rooms': conflicted,
        }
    @api.model
    def check_confirmed_availability_for_date_change(self, record_id, new_checkin, new_checkout):
        # Only act when the booking is in 'confirmed' state
        booking = self.browse(record_id)
        if booking.state != 'confirmed':
            return {'has_conflict': False, 'conflicted_rooms': []}

        # Print the new dates to stdout
        print(f"[DateChange] Booking {record_id}: check-in = {new_checkin}, check-out = {new_checkout}")

         # 2) Parse "DD/MM/YYYY HH:MM:SS" into Python dates
        fmt = '%d/%m/%Y %H:%M:%S'
        try:
            dt_checkin  = datetime.strptime(new_checkin, fmt).date()
            dt_checkout = datetime.strptime(new_checkout, fmt).date()
        except ValueError:
            # fallback to stored values if parsing fails
            dt_checkin, dt_checkout = booking.checkin_date, booking.checkout_date

        # 3) Build params for your SQL with the new dates
        query = booking._get_room_search_query()
        params = {
            'company_id':    booking.env.company.id,
            'from_date':     dt_checkin,
            'to_date':       dt_checkout,
            'room_count':    booking.room_count,
            'room_type_id':  booking.hotel_room_type.id if booking.hotel_room_type else None,
        }

        # 4) Execute and fetch
        booking.env.cr.execute(query, params)
        rooms = booking.env.cr.dictfetchall()

        conflicted = []
        for r in rooms:
            # cast to int to drop ".0"
            min_free = int(r.get('min_free_to_sell', 0))
            if booking.room_count > min_free:
                conflicted.append(r.get('room_type_name') or str(r.get('room_type_id')))

        for r in rooms:
            _logger.debug("  → %s", r)
        if conflicted:
            _logger.debug(f"[Conflict] Booking {record_id} requests {booking.room_count} rooms,")
            _logger.debug(f"but min_free_to_sell = {int(rooms[0].get('min_free_to_sell',0))}  (conflicts: {conflicted})")
        else:
            _logger.debug(f"[OK] Booking {record_id} can be accommodated with {booking.room_count} rooms.")

        return {
            'has_conflict': bool(conflicted),
            'conflicted_rooms': conflicted,
        }

    
    @api.onchange('room_count')
    def _onchange_room_count(self):
        for record in self:
            if record._origin and not record.previous_room_count:
                previous_db_room_count = record._origin.room_count
                record.previous_room_count = previous_db_room_count
            else:
                print(f"[DEBUG] Room Count Changed: Previous={record.previous_room_count}, Current={record.room_count}")
    

    def generateRcGuestPDF(self):
        # Redirect to the controller to generate the PDFs
        booking_ids = ','.join(map(str, self.ids))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/generate_rc+guest/bookings_pdf?booking_ids={booking_ids}',
            'target': 'self',
        }

    hide_unconfirm_button = fields.Boolean(
        compute="_compute_hide_unconfirm_button",
        string="Hide Unconfirm Button",
        store=False
    )

    @api.depends('state')
    def _compute_hide_unconfirm_button(self):
        crs_user_group = self.env.ref('hotel_management.crs_user_group')
        for record in self:
            record.hide_unconfirm_button = (
                    record.state == 'confirmed' and crs_user_group in self.env.user.groups_id
            )

    hide_confirm_button = fields.Boolean(
        compute="_compute_hide_confirm_button",
        string="Hide confirm Button",
        store=False
    )

    @api.depends('state')
    def _compute_hide_confirm_button(self):
        crs_user_group = self.env.ref('hotel_management.crs_user_group')
        for record in self:
            record.hide_confirm_button = (
                    record.state == 'block' and crs_user_group in self.env.user.groups_id
            )

    hide_admin_buttons = fields.Boolean(
        compute="_compute_hide_admin_buttons",
        string="Hide Admin Buttons",
        store=False
    )

    @api.depends('state')
    def _compute_hide_admin_buttons(self):
        crs_admin_group = self.env.ref('hotel_management.crs_admin_group')
        for record in self:
            record.hide_admin_buttons = (
                    record.state == 'block' and crs_admin_group in self.env.user.groups_id
            )

    hide_buttons_front_desk = fields.Boolean(
        compute="_compute_hide_buttons_front_desk",
        string="Hide Buttons for Front Desk",
        store=False
    )

    @api.depends('state')
    def _compute_hide_buttons_front_desk(self):
        front_desk_group = self.env.ref(
            'hotel_management.front_desk_user_group')
        for record in self:
            record.hide_buttons_front_desk = (
                    record.state == 'block' and front_desk_group in self.env.user.groups_id
            )

    is_checkout_in_past = fields.Boolean(
        string="Is Checkout in Past",
        compute="_compute_is_checkout_in_past",
        store=True
    )

    @api.depends('checkout_date')
    def _compute_is_checkout_in_past(self):
        # today = fields.Date.context_today(self)
        today = self.env.company.system_date.date()
        for record in self:
            if record.checkout_date:
                checkout_date = (
                    record.checkout_date.date()
                    if isinstance(record.checkout_date, datetime)
                    else record.checkout_date
                )
                record.is_checkout_in_past = checkout_date < today
            else:
                record.is_checkout_in_past = False

    notification_sent = fields.Boolean(
        string="Notification Sent", default=False)

    @api.model
    def check_waiting_list_and_notify(self):
        today = self.env.company.system_date.date()

        # Step 1: Search for bookings in the 'cancel' state for today
        canceled_bookings = self.env['room.booking'].search([
            ('state', '=', 'cancel'),
            ('checkin_date', '>=', today),
            ('checkout_date', '>=', today),
            ('notification_sent', '=', False)
        ])

        if not canceled_bookings:
            return


        for canceled_booking in canceled_bookings:

            # Step 2: Search for bookings in the 'waiting' state with matching dates
            waiting_bookings = self.env['room.booking'].search([
                ('state', '=', 'waiting'),
                ('checkin_date', '>=', datetime.combine(
                    today, datetime.min.time())),
                ('checkout_date', '<=', canceled_booking.checkout_date.date()),
                ('company_id', '=', self.env.company.id)
            ], order='create_date asc')

            cumulative_room_count = 0
            selected_bookings = []  # To store the bookings that satisfy the criteria

            for booking in waiting_bookings:
                # Check if the booking already has a notification activity
                existing_activity = self.env['mail.activity'].search([
                    ('res_id', '=', booking.id),
                    ('res_model', '=', 'room.booking'),
                    ('summary', '=', "Room Availability Notification"),
                    # Ensure it is linked to the current canceled booking
                    ('note', 'ilike', canceled_booking.name)
                ], limit=1)

                if existing_activity:
                    continue

                cumulative_room_count += booking.room_count
                selected_bookings.append(booking)

                # Stop when the cumulative room count matches or exceeds the canceled booking's room count
                if cumulative_room_count >= canceled_booking.room_count:
                    break

            # Notify about the selected bookings
            if selected_bookings:
                for booking in selected_bookings:
                    message = f"Booking '{booking.name}' is now available for the canceled booking '{canceled_booking.name}'."

                    # Create a scheduled activity if not already created
                    self.env['mail.activity'].create({
                        'res_id': booking.id,
                        'res_model_id': self.env['ir.model']._get('room.booking').id,
                        'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                        'summary': "Room Availability Notification",
                        'note': message,
                        'user_id': booking.create_uid.id,
                        'date_deadline': fields.Date.today(),
                    })

                    # Send real-time notification (optional)
                    self.env['bus.bus']._sendone(
                        'res.partner',
                        booking.create_uid.partner_id.id,
                        {'type': 'simple_notification', 'message': message}
                    )
                canceled_booking.notification_sent = True
            
    
    @api.model
    def action_send_pre_reminder_emails(self):
        today = datetime.now().date()

        # Step 1: Search all companies with a notification configuration
        companies = self.env['res.company'].search(
            [('reminder_days_before', '>', 0), ('template_id', '!=', False)])

        for company in companies:
            notification_days = company.reminder_days_before
            start_datetime = datetime.combine(
                (datetime.today() + timedelta(days=notification_days)).date(), time.min)
            end_datetime = datetime.combine(
                (datetime.today() + timedelta(days=notification_days)).date(), time.max)
            # Step 2: Search for bookings in the current company that meet the criteria
            bookings = self.search([
                ('checkin_date', '<=', end_datetime),
                ('company_id', '=', company.id),
                ('checkin_date', '>=', start_datetime),
            ])
            for booking in bookings:
                # Step 3: Send the email using the company's mail template
                mail_template = company.template_id
                if mail_template:
                    mail_template.send_mail(booking.id, force_send=True)

    @api.model
    def action_send_pre_arrival_emails(self):
        today = datetime.now().date()

        # Step 1: Search all companies with a notification configuration
        companies = self.env['res.company'].search(
            [('pre_arrival_days_before', '>', 0), ('pre_template_id', '!=', False)])

        for company in companies:
            notification_days = company.pre_arrival_days_before
            start_datetime = datetime.combine(
                (datetime.today() + timedelta(days=notification_days)).date(), time.min)
            end_datetime = datetime.combine(
                (datetime.today() + timedelta(days=notification_days)).date(), time.max)
            # Step 2: Search for bookings in the current company that meet the criteria
            bookings = self.search([
                ('checkin_date', '<=', end_datetime),
                ('company_id', '=', company.id),
                ('checkin_date', '>=', start_datetime),
            ])
            for booking in bookings:
                # Step 3: Send the email using the company's mail template
                mail_template = company.pre_template_id
                if mail_template:
                    mail_template.send_mail(booking.id, force_send=True)

    

    def generatePDF(self):
        # Redirect to the controller to generate the PDFs
        booking_ids = ','.join(map(str, self.ids))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/generate/bookings_pdf?booking_ids={booking_ids}',
            'target': 'self',
        }

    previous_state = fields.Char(string=_("Previous State"), translate=True)

    is_checkin_in_past = fields.Boolean(
        string="Is Check-in in Past",
        compute="_compute_is_checkin_in_past",
        store=True
    )
    active = fields.Boolean(string="Active", default=True)

    is_offline_search = fields.Boolean(string="Is Offline search", default=True)

    @api.model
    def action_archive_as_delete_redirect(self,record_ids):
        records = self.browse(record_ids)
        if records.exists():
            records.action_archive_as_delete()
        

    def action_archive_as_delete(self):
        """Validate states and archive records."""
        # Define allowed states
        allowed_states = ['cancel', 'no_show', 'not_confirmed']

        # Check if all records are in allowed states
        invalid_records = self.filtered(
            lambda r: r.state not in allowed_states)

        if invalid_records:
            raise exceptions.ValidationError(
                "You can only delete bookings in the following states: Cancel, No Show, or Not Confirmed.\n"
                "The following bookings are in invalid states:\n"
                + "\n".join(f"Booking ID: {rec.id}, State: {rec.state}" for rec in invalid_records)
            )
        for record in self:
            record.active = False
      

    @api.depends('checkin_date')
    def _compute_is_checkin_in_past(self):
        # Fetch system_date from the company configuration
        system_date = self.env.company.system_date.date()
        # if system_date:
        #     # Ensure system_date is correctly formatted to a date
        #     system_date = system_date.date() if isinstance(system_date, datetime) else fields.Date.to_date(system_date)
        # else:
        #     print("System Date is not set!")

        for record in self:
            if record.checkin_date:
                # Convert checkin_date to a date if it's a datetime object
                checkin_date_ = record.checkin_date.date()

                # Compare checkin_date with system_date
                record.is_checkin_in_past = (checkin_date_ < system_date)
                
            else:
                record.is_checkin_in_past = False


    @api.onchange('no_of_nights')
    def _check_no_of_nights(self):
        """ Validate that the number of nights does not exceed 999 """
        for record in self:
            if record.no_of_nights > 999:
                raise ValidationError(_("Number of nights cannot exceed 999."))
    

    def move_to_no_show(self):
        # 1) Load every company’s ID and system_date
        self.env.cr.execute("SELECT id, system_date FROM res_company")
        companies = self.env.cr.fetchall()  # [(company_id, system_date), ...]

        today = self.env.company.system_date.date()

        for company_id, system_date in companies:
            # scope all subsequent queries to this company
            # company_env = self.with_context(
            #     allowed_company_ids=[company_id],
            #     force_company=company_id,
            # )
            company_env = self.with_company(company_id).with_context(
                allowed_company_ids=[company_id]
            )
            cr = company_env.env.cr

            # yesterday (00:00) in that company’s calendar
            yesterday = datetime.combine(
                (system_date - timedelta(days=1)),
                time.min
            ).date()
            _logger.debug("%s system date %s company",yesterday,company_id)
            current_time = datetime.now().time()
            get_sys_date = datetime.combine(system_date, current_time)
            _logger.debug("Date time  %s %s %s", today, current_time, get_sys_date)
            # 2) Find bookings whose checkin_date < yesterday and still open
            cr.execute("""
                SELECT id
                FROM room_booking
                WHERE state IN ('not_confirmed','confirmed','block')
                  AND checkin_date::date <= %s
                  AND company_id = %s
            """, (yesterday, company_id))
            booking_ids = [row[0] for row in cr.fetchall()]
            

            if not booking_ids:
                _logger.debug("No bookings to mark no_show for company %s", company_id)
                continue

            # 3) Mark all those bookings as no_show
            cr.execute("""
                UPDATE room_booking
                SET state = 'no_show'
                WHERE id = ANY(%s)
            """, (booking_ids,))

            # 4) Fetch every line on those bookings
            cr.execute("""
                SELECT id, room_id
                FROM room_booking_line
                WHERE booking_id = ANY(%s)
            """, (booking_ids,))
            lines = cr.fetchall()  # list of (line_id, room_id)
            line_ids = [l[0] for l in lines]

            if line_ids:
                # 5) Clear the rooms and set state_ = 'no_show'
                cr.execute("""
                    UPDATE room_booking_line
                    SET room_id = NULL,
                        state_  = 'no_show'
                    WHERE id = ANY(%s)
                """, (line_ids,))

                # 6) Insert status-history rows
                for line_id in line_ids:
                    cr.execute("""
                        INSERT INTO room_booking_line_status (
                            booking_line_id,
                            create_uid, write_uid,
                            status,
                            change_time,
                            create_date, write_date
                        ) VALUES (
                            %s,    -- booking_line_id
                            %s,    -- create_uid
                            %s,    -- write_uid
                            'no_show',
                            %s,    -- change_time (use get_sys_date)
                            NOW(), -- create_date
                            NOW()  -- write_date
                        )
                    """, (line_id, self.env.uid, self.env.uid, get_sys_date))

            

    start_line = fields.Integer(string="Start Record", default=1)
    end_line = fields.Integer(string="End Record", default=1)

    notes = fields.Text(string="Notes", tracking=True)
    special_request = fields.Text(string="Special Request", tracking=True)
    room_booking_id = fields.Many2one(
        'report.model',
        string="Report Model",
        help="Reference to the consolidated report model",
    )
    name = fields.Char(string="Room Number", tracking=True)
    adult_ids = fields.One2many(
        'room.booking.adult', 'booking_id', string="Adults")  #
    child_ids = fields.One2many(
        'room.booking.child', 'booking_id', string="Children")  #
    infant_ids = fields.One2many(
        'room.booking.infant', 'booking_id', string="Infant")  #
    web_cancel = fields.Boolean(string="Web cancel", default=False, help="Reservation cancelled by website",
                                tracking=True)
    web_cancel_time = fields.Datetime(string="Web Cancel Time", compute="_compute_web_cancel_time", store=True,
                                      readonly=True, tracking=True)
    ref_id_bk = fields.Char(string="Ref. ID(booking.com)", tracking=True)

    @api.depends('web_cancel')
    def _compute_web_cancel_time(self):
        for record in self:
            if record.web_cancel and not record.web_cancel_time:
                record.web_cancel_time = datetime.now()

    hotel_id = fields.Many2one('res.company', string="Hotel ID", tracking=True)
    
    address_id = fields.Many2one(
        'res.partner', string="Address", tracking=True)
    phone = fields.Char(related='address_id.phone',
                        string="Phone Number", tracking=True)
    # room_booking_line_id = fields.Many2one('room.booking.line', string="Room Line", tracking=True)

    room_id = fields.Many2one(
        'room.booking.line', string="Room Line", tracking=True)
    room_type = fields.Many2one('room.type', string="Hotel Room Type", tracking=True)

    # no_of_nights = fields.Integer(
    #     string="Number of Nights",
    #     compute="_compute_no_of_nights",
    #     store=True,
    #     help="Computed field to calculate the number of nights based on check-in and check-out dates.",
    #     tracking=True
    # )

    phone_number = fields.Char(
        related='adult_id.phone_number', string='Phone Number', store=True, tracking=True)
    adult_id = fields.Many2one(
        "reservation.adult",
        string="Full Name",
    )
    
    hijri_checkin_date = fields.Char(
        string="Hijri Check-In Date",
        compute='_compute_hijri_dates',
        store=False
    )
    hijri_checkout_date = fields.Char(
        string="Hijri Check-Out Date",
        compute='_compute_hijri_dates',
        store=False,
    )
    number_of_pax = fields.Integer(string="Number of Pax", tracking=True)
    number_of_children = fields.Integer(
        string="Number of Children", tracking=True)
    number_of_infants = fields.Integer(
        string="Number of Infants", tracking=True)

    # Tax and Municipality
    vat = fields.Float(string="VAT (%)", tracking=True)
    municipality = fields.Float(string="Municipality (%)", tracking=True)
    vat_id = fields.Char(string="VAT ID", tracking=True)

    # Rates
    daily_room_rate = fields.Float(string="Daily Room Rate", tracking=True)
    daily_meals_rate = fields.Float(string="Daily Meals Rate", tracking=True)

    # Payments
    payments = fields.Float(string="Payments", tracking=True)
    remaining = fields.Float(string="Remaining", tracking=True)
    hijri_date = fields.Char(
        string="Hijri Date", compute="_compute_dates", store=True, tracking=True)
    gregorian_date = fields.Char(
        string="Gregorian Date", compute="_compute_dates", store=True, tracking=True)

    def _compute_dates(self):
        for record in self:
            today = date.today()
            # Gregorian date as string
            record.gregorian_date = today.strftime('%Y-%m-%d')

            # Convert to Hijri
            hijri_date = Gregorian(
                today.year, today.month, today.day).to_hijri()
            record.hijri_date = f"{hijri_date.year}-{hijri_date.month:02d}-{hijri_date.day:02d}"

    
    @api.depends('checkin_date', 'checkout_date')
    def _compute_hijri_dates(self):
        for record in self:
            # Convert Check-In Date to Hijri
            if record.checkin_date:
                record.hijri_checkin_date = self._convert_to_hijri(
                    record.checkin_date)
            else:
                record.hijri_checkin_date = False

            # Convert Check-Out Date to Hijri
            if record.checkout_date:
                record.hijri_checkout_date = self._convert_to_hijri(
                    record.checkout_date)
            else:
                record.hijri_checkout_date = False

    def _convert_to_hijri(self, gregorian_date):
        """Convert a Gregorian date to Hijri date."""
        try:
            if isinstance(gregorian_date, str):
                gregorian_date = datetime.datetime.strptime(
                    gregorian_date, '%Y-%m-%d').date()
            hijri_date = hijri.from_gregorian(
                gregorian_date.year, gregorian_date.month, gregorian_date.day)
            return f"{hijri_date[0]}-{hijri_date[1]:02d}-{hijri_date[2]:02d}"
        except Exception as e:
            return False

    def get_report_data(self):
        # Fetch the active_id from the context
        active_id = self.env.context.get('active_id')
        if active_id:
            # Fetch the specific record using active_id
            record = self.browse(active_id)
            # Perform any operations with the record
            return record
        else:
            # Handle case where active_id is not found
            raise ValueError("No active_id found in the context")

    

    def action_delete_lines(self):
        for record in self:
            # Validate that the record has valid start_line and end_line
            if not record.start_line or not record.end_line:
                raise ValueError("Start Line and End Line must be provided.")

            # Fetch all lines for the current booking, ordered by ID
            booking_lines = self.env['room.booking.line'].search(
                [('booking_id', '=', record.id)],
                order="id"
            )
            total_lines = len(booking_lines)

            # Validate the range of start_line and end_line
            if not (1 <= record.start_line <= total_lines and 1 <= record.end_line <= total_lines):
                raise ValueError(
                    f"Invalid range: start_line={record.start_line}, end_line={record.end_line}, total_lines={total_lines}")

            if record.start_line > record.end_line:
                raise ValueError("Start Line cannot be greater than End Line.")

            # Select lines to delete based on start_line and end_line
            lines_to_delete = booking_lines[record.start_line -
                                            1:record.end_line]
            lines_to_delete.unlink()


    posting_item_ids = fields.One2many(
        'room.booking.posting.item',
        'booking_id',
        string="Posting Items",
        help="Select posting items for this booking uniquely."
    )

    booking_posting_item_ids = fields.One2many(
        'booking.posting.item', 'booking_id', string="Booking Posting Items"
    )

    show_in_tree = fields.Boolean(
        compute='_compute_show_in_tree',
        store=True,  # Computed dynamically, not stored in the database
    )


    @api.depends('parent_booking_id', 'room_count', 'room_line_ids')
    def _compute_show_in_tree(self):
        for record in self:
            if not record.room_line_ids:
                record.show_in_tree = True
            else:
                # record.show_in_tree = True
                record.show_in_tree = not (
                        not record.parent_booking_id
                        and record.room_count > 1
                        and all(line.room_id for line in record.room_line_ids)
                )
    
    
    no_show_ = fields.Boolean(string="No Show", help="Mark booking as No Show")

    is_room_line_readonly = fields.Boolean(
        string="Room Line Readonly", default=False)

    availability_results = fields.One2many(
        'room.availability.result', 'room_booking_id', string="Availability Results", readonly=True
    )

    @api.model
    def get_today_checkin_domain(self):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            ('checkin_date', '>=', today),
            ('checkin_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_in')
        ]

    @api.model
    def get_today_checkout_domain(self):
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            ('checkout_date', '>=', today),
            ('checkout_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_out')
        ]

    @api.model
    def retrieve_dashboard(self):

        company = self.env.company  # This fetches the current company
        
        system_date = (
            company.system_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if company.system_date
            else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )
        end_of_day = system_date + timedelta(days=1) - timedelta(seconds=1)
        self.env.cr.commit()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        actual_checkin_count = self.search_count([
            # ('checkin_date', '>=', today),
            ('checkin_date', '>=', system_date),
            ('checkin_date', '<=', system_date + timedelta(days=1) - timedelta(seconds=1)),
            ('state', '=', 'check_in'),
        ])

        actual_checkout_count = self.search_count([
            # ('checkout_date', '>=', today),
            ('checkout_date', '>=', system_date),
            ('checkout_date', '<=', system_date + timedelta(days=1) - timedelta(seconds=1)),
            # ('checkout_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_out'),
            # ('parent_booking_name', '!=', False)

        ])

        today_checkin_count = self.search_count([
            # ('checkin_date', '>=', today),
            ('checkin_date', '>=', system_date),
            ('checkin_date', '<=', system_date + timedelta(days=1) - timedelta(seconds=1)),
            # ('checkin_date', '<', today + timedelta(days=1)),
            ('state', '=', 'block'),
            # ('parent_booking_name', '!=', False)

        ])
        today_checkout_count = self.search_count([
            # ('checkout_date', '>=', today),
            ('checkout_date', '>=', system_date),
            # ('checkout_date', '<=', end_of_day),
            ('checkout_date', '<=', system_date + timedelta(days=1) - timedelta(seconds=1)),
            # ('checkout_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_in'),
            # ('parent_booking_name', '!=', False)

        ])

        # Counts for each specific booking state
        not_confirm_count = self.env['room.booking'].search_count(
            [('state', '=', 'not_confirmed')])
        confirmed_count = self.env['room.booking'].search_count(
            [('state', '=', 'confirmed')])
        waiting_count = self.env['room.booking'].search_count(
            [('state', '=', 'waiting')])
        blocked_count = self.env['room.booking'].search_count(
            [('state', '=', 'block')])
        cancelled_count = self.env['room.booking'].search_count(
            [('state', '=', 'cancel')])
        checkin_count = self.search_count([('state', '=', 'check_in')])
        checkout_count = self.search_count([('state', '=', 'check_out')])

        total_rooms_count = self.env['hotel.room'].search_count([])
        # get_total_reservation_count = self.env['room.booking'].search_count([('company_id', '=', self.env.company.id)])
        get_total_reservation_count = confirmed_count + not_confirm_count + waiting_count + checkin_count + checkout_count

        

        # Calculate vacant count
        vacant_count = total_rooms_count - actual_checkin_count
        # Return all counts
        result = {
            'today_checkin': today_checkin_count,
            'today_checkout': today_checkout_count,
            'not_confirm': not_confirm_count,
            'confirmed': confirmed_count,
            'waiting': waiting_count,
            'blocked': blocked_count,
            'cancelled': cancelled_count,
            'checkin': checkin_count,
            'checkout': checkout_count,
            'actual_checkin_count': actual_checkin_count,
            'actual_checkout_count': actual_checkout_count,
            'vacant': get_total_reservation_count,
            # 'default': confirmed_count + not_confirm_count + waiting_count + checkin_count + checkout_count,
        }
        return result


    adult_ids = fields.One2many(
        'reservation.adult', 'reservation_id', string='Adults')  #
    child_ids = fields.One2many(
        'reservation.child', 'reservation_id', string='Children')  #

    infant_ids = fields.One2many(
        'reservation.infant', 'reservation_id', string='Infant')  #

    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern", domain=lambda self: [('company_id', '=', self.env.company.id)], tracking=True)

    group_booking_id = fields.Many2one(
        'group.booking',  # The source model (group bookings)
        string='Group Booking ID',
        ondelete='cascade',
        tracking=True
    )

    name = fields.Char(string="Booking ID", readonly=True, index=True,copy=False, default="New", help="Name of Folio", tracking=True)

    rate_forecast_ids = fields.One2many(
        'room.rate.forecast',
        'room_booking_id',
        compute='_get_forecast_rates',
        store=True,
    ) 

    

    room_rate_municiplaity_tax = fields.Float(string="Room Rate Municipality Tax", store=False, tracking=True)    
    room_rate_vat = fields.Float(string="Room Rate VAT", store=False, tracking=True)
    room_rate_untaxed = fields.Float(string="Room Rate Untaxed", store=False, tracking=True)

    meal_rate_municiplaity_tax = fields.Float(string="Meal Rate Municipality Tax", store=False, tracking=True)    
    meal_rate_vat = fields.Float(string="Meal Rate VAT", store=False, tracking=True)
    meal_rate_untaxed = fields.Float(string="Meal Rate Untaxed", store=False, tracking=True)

    packages_municiplaity_tax = fields.Float(string="Packages Municipality Tax", store=False, tracking=True)
    packages_vat = fields.Float(string="Packages VAT", store=False, tracking=True)
    packages_untaxed = fields.Float(string="Packages Untaxed", store=False, tracking=True)

    fixed_post_vat = fields.Float(string="Fixed Post VAT", store=False, tracking=True)
    fixed_post_municiplaity_tax = fields.Float(string="Fixed Post Municipality Tax", store=False, tracking=True)
    fixed_post_untaxed = fields.Float(string="Fixed Post Untaxed", store=False, tracking=True)

    total_municipality_tax = fields.Float(string="Total Municipality Tax", tracking=True)
    total_vat = fields.Float(string="Total VAT", tracking=True)
    total_untaxed = fields.Float(string="Total Untaxed", store=False, tracking=True)

    

    @api.depends(
        'total_rate_after_discount',
        'rate_code',
        'rate_code.rate_posting_item',
        'rate_code.rate_posting_item.taxes',
        'rate_code.rate_posting_item.taxes.amount',  # Catch tax % change
        'rate_code.rate_posting_item.taxes.amount_type', 
        'rate_code.rate_posting_item.taxes.include_base_amount', 
        'rate_code.rate_posting_item.taxes.price_include', 
        'rate_code.rate_posting_item.taxes.tax_group_id', 
        'rate_code.rate_posting_item.taxes.name',    # Optional: for UI tracking
    )
    def _compute_room_taxes(self):
        if self.env.context.get('skip_total_forecast_computation'):
            return
        for rec in self:
            amount = rec.total_rate_after_discount or 0.0
            _logger.debug(f"Computing room taxes for booking {rec.id} with amount {amount}")
            taxes = rec.rate_code.rate_posting_item.taxes if rec.rate_code and rec.rate_code.rate_posting_item else self.env['account.tax']
            currency = self.env.company.currency_id

            rec.room_rate_vat = 0.0
            rec.room_rate_municiplaity_tax = 0.0
            rec.room_rate_untaxed = amount

            if not taxes:
                continue

            tax_result = taxes.compute_all(amount, currency=currency)

            for tax in tax_result.get('taxes', []):
                tax_obj = self.env['account.tax'].browse(tax['id'])
                tax_name = tax_obj.with_context(lang='en_US').name.lower().strip()
                
                # if 'vat' in tax_name:
                if 'vat' in tax_name or 'ضريبة القيمة المضافة' in tax_name:
                    rec.room_rate_vat += tax['amount']
                # if 'muncipality' in tax_name:
                if 'muncipality' in tax_name or 'municipality' in tax_name or 'muni' in tax_name or 'بلدية' in tax_name or 'رسوم البلدية' in tax_name:
                    rec.room_rate_municiplaity_tax += tax['amount']

            rec.room_rate_untaxed = tax_result['total_excluded']



    # working
    def _onchange_rate_code_taxes(self):
        for rec in self:
            total = rec.total_rate_after_discount or 0.0
            _logger.debug(f"Computing rate code taxes for booking {rec.id} with total {total}")
            taxes = rec.rate_code.rate_posting_item.taxes or self.env['account.tax']

            # pick out VAT and Municipality taxes (if any)
            vat_tax = taxes[0] if len(taxes) > 0 else None
            muni_tax = taxes[1] if len(taxes) > 1 else None

            if not vat_tax and not muni_tax:
                rec.room_rate_vat = 0.0
                rec.room_rate_municiplaity_tax = 0.0
                rec.room_rate_untaxed = total
                continue

            rec.room_rate_vat = 0.0
            if vat_tax and vat_tax.amount:
                pct_vat = vat_tax.amount / 100.0
                # total includes VAT, so base = total / (1 + pct)
                untaxed_base = total / (1 + pct_vat)
                rec.room_rate_vat = total - untaxed_base
            else:
                untaxed_base = total

            if muni_tax and muni_tax.amount:
                pct_muni = muni_tax.amount / 100.0
                # amount after removing VAT
                base_after_vat = total - rec.room_rate_vat
                untaxed_after_muni = base_after_vat / (1 + pct_muni)
                rec.room_rate_municiplaity_tax = base_after_vat - untaxed_after_muni
                rec.room_rate_untaxed = untaxed_after_muni
            else:
                # no municipality tax: untaxed = total minus VAT
                rec.room_rate_municiplaity_tax = 0.0
                rec.room_rate_untaxed = total - rec.room_rate_vat

    
    def _onchange_meal_rate_taxes(self):
        for rec in self:
            meal_base_amount = rec.total_meal_after_discount or 0.0
            total_vat = 0.0
            total_municipality = 0.0
            total_untaxed = 0.0

            posting_items = []

            if rec.meal_pattern and rec.meal_pattern.meal_posting_item:
                posting_items.append(rec.meal_pattern.meal_posting_item)
            elif rec.meal_pattern and rec.meal_pattern.meals_list_ids:
                for line in rec.meal_pattern.meals_list_ids:
                    if line.meal_code and line.meal_code.posting_item:
                        posting_items.append(line.meal_code.posting_item)

            if posting_items:
                for posting_item in posting_items:
                    meal_taxes = posting_item.taxes
                    vat_amount = 0.0
                    muni_amount = 0.0
                    untaxed_amount = 0.0

                    # Step 1: VAT
                    vat_tax = meal_taxes[0] if len(meal_taxes) > 0 else None
                    if vat_tax:
                        vat_pct = vat_tax.amount
                        vat_amount = meal_base_amount * (vat_pct / (100 + vat_pct))
                        base_after_vat = meal_base_amount - vat_amount
                    else:
                        base_after_vat = meal_base_amount

                    # Step 2: Municipality
                    municipality_tax = meal_taxes[1] if len(meal_taxes) > 1 else None
                    if municipality_tax:
                        muni_pct = municipality_tax.amount
                        muni_amount = base_after_vat * (muni_pct / (100 + muni_pct))
                        untaxed_amount = base_after_vat - muni_amount
                    else:
                        untaxed_amount = base_after_vat

                    # Accumulate — base stays same, so taxes stack
                    total_vat += vat_amount
                    total_municipality += muni_amount
                    total_untaxed += untaxed_amount

            else:
                total_untaxed = meal_base_amount

            # Assign with rounding
            rec.meal_rate_vat = round(total_vat, 2)
            rec.meal_rate_municiplaity_tax = round(total_municipality, 2)
            rec.meal_rate_untaxed = round(total_untaxed, 2)
    
    
    def _onchange_packaged_taxes(self):
        if self.env.context.get('skip_total_forecast_computation'):
            return
        for rec in self:
            # Initialize all package tax fields
            rec.packages_vat = 0.0
            rec.packages_municiplaity_tax = 0.0
            rec.packages_untaxed = rec.total_package_after_discount or 0.0  # Default to total package amount
            
            # Get date range for rate details
            checkin_date = fields.Date.from_string(rec.checkin_date)
            checkout_date = fields.Date.from_string(rec.checkout_date)

            # Find applicable rate details
            rate_details = self.env['rate.detail'].search([
                ('rate_code_id', '=', rec.rate_code.id),
                ('from_date', '<=', checkin_date),
                ('to_date', '>=', checkout_date)
            ], limit=1)

            if rate_details:
                package_base_total = 0.0
                total_package_vat = 0.0
                total_package_municipality = 0.0
                total_package_untaxed = 0.0

                for line in rate_details.line_ids:
                    base = rec.total_package_after_discount or 0.0
                    package_base_total += base
                    posting_item_taxes = line.packages_posting_item.taxes if line.packages_posting_item else []

                    if posting_item_taxes:
                        # Calculate VAT if exists
                        vat_tax = posting_item_taxes[0] if len(posting_item_taxes) > 0 else None
                        if vat_tax:
                            try:
                                percentage = vat_tax.amount
                                total_with_vat = base + (base * percentage / 100)
                                if total_with_vat != 0:
                                    unit_price = base * (base / total_with_vat)
                                    package_vat = base - unit_price
                                    total_package_vat += package_vat
                                    base = unit_price  # Update base for next tax calculation
                            except (ZeroDivisionError, ValueError):
                                pass

                        # Calculate Municipality tax if exists
                        municipality_tax = posting_item_taxes[1] if len(posting_item_taxes) > 1 else None
                        if municipality_tax:
                            try:
                                percentage = municipality_tax.amount
                                total_with_municipality = base + (base * percentage / 100)
                                if total_with_municipality != 0:
                                    unit_price_municipality = base * (base / total_with_municipality)
                                    package_municipality = base - unit_price_municipality
                                    total_package_municipality += package_municipality
                                    base = unit_price_municipality  # Final untaxed amount
                            except (ZeroDivisionError, ValueError):
                                pass

                    total_package_untaxed += base

                # Update record fields
                rec.packages_vat = total_package_vat
                rec.packages_municiplaity_tax = total_package_municipality
                # rec.packages_untaxed = total_package_untaxed
                rec.packages_untaxed = (rec.total_package_after_discount or 0.0) - total_package_vat - total_package_municipality

                # Final check - if both taxes are 0, set untaxed to total package amount
                if rec.packages_vat == 0.0 and rec.packages_municiplaity_tax == 0.0:
                    rec.packages_untaxed = rec.total_package_after_discount or 0.0

   
   
    def _onchange_fixed_post_taxes(self):
        for record in self:
            # Initialize all tax fields
            record.fixed_post_vat = 0.0
            record.fixed_post_municiplaity_tax = 0.0
            record.fixed_post_untaxed = record.total_fixed_post_after_discount or 0.0  # Default to total fixed post amount
            
            fixed_base = record.total_fixed_post_after_discount or 0.0
            total_vat = 0.0
            total_municipality = 0.0
            total_untaxed = 0.0

            for line in record.posting_item_ids:
                posting_item = line.posting_item_id
                if not posting_item or not posting_item.taxes:
                    # No taxes - add full amount to untaxed
                    total_untaxed += fixed_base
                    continue
                
                base = fixed_base
                taxes = posting_item.taxes
                
                # Calculate VAT if exists
                vat_tax = taxes[0] if len(taxes) > 0 else None
                if vat_tax:
                    try:
                        percentage = vat_tax.amount
                        total_with_vat = base + (base * percentage / 100)
                        if total_with_vat != 0:
                            unit_price = base * (base / total_with_vat)
                            vat_amount = base - unit_price
                            total_vat += vat_amount
                            base = unit_price  # Update base for next tax calculation
                    except (ZeroDivisionError, ValueError):
                        pass

                # Calculate Municipality tax if exists
                municipality_tax = taxes[1] if len(taxes) > 1 else None
                if municipality_tax:
                    try:
                        percentage = municipality_tax.amount
                        total_with_municipality = base + (base * percentage / 100)
                        if total_with_municipality != 0:
                            unit_price_municipality = base * (base / total_with_municipality)
                            municipality_amount = base - unit_price_municipality
                            total_municipality += municipality_amount
                            base = unit_price_municipality  # Final untaxed amount
                    except (ZeroDivisionError, ValueError):
                        pass

                total_untaxed += base

            # Update record fields
            record.fixed_post_vat = total_vat
            record.fixed_post_municiplaity_tax = total_municipality
            record.fixed_post_untaxed = total_untaxed

            # Final check - if both taxes are 0, set untaxed to total fixed post amount
            if record.fixed_post_vat == 0.0 and record.fixed_post_municiplaity_tax == 0.0:
                record.fixed_post_untaxed = record.total_fixed_post_after_discount or 0.0
    
    
    @api.depends(
        'total_meal_after_discount',
        'meal_pattern',
        'meal_pattern.meal_posting_item.taxes',
        'meal_pattern.meal_posting_item.taxes.amount',
        'meal_pattern.meal_posting_item.taxes.amount_type',
        'meal_pattern.meal_posting_item.taxes.price_include',
        'meal_pattern.meals_list_ids.meal_code.posting_item.taxes',
        'meal_pattern.meals_list_ids.meal_code.posting_item.taxes.amount',
        'meal_pattern.meals_list_ids.meal_code.posting_item.taxes.amount_type',
        'meal_pattern.meals_list_ids.meal_code.posting_item.taxes.price_include',
    )
    def _compute_meal_taxes(self):
        if self.env.context.get('skip_total_forecast_computation'):
            return
        for rec in self:
            base_amount = rec.total_meal_after_discount or 0.0
            currency = rec.currency_id or rec.env.company.currency_id

            total_vat = 0.0
            total_municipality = 0.0
            total_untaxed = 0.0

            posting_items = []

            if rec.meal_pattern and rec.meal_pattern.meal_posting_item:
                posting_items.append(rec.meal_pattern.meal_posting_item)

            elif rec.meal_pattern and rec.meal_pattern.meals_list_ids:
                for line in rec.meal_pattern.meals_list_ids:
                    if line.meal_code and line.meal_code.posting_item:
                        posting_items.append(line.meal_code.posting_item)

            if posting_items:
                for posting_item in posting_items:
                    taxes = posting_item.taxes or rec.env['account.tax']
                    result = taxes.compute_all(base_amount, currency=currency, quantity=1.0)

                    total_untaxed += result['total_excluded']

                    for tax_line in result['taxes']:
                        tax_obj = rec.env['account.tax'].browse(tax_line['id'])
                        if 'vat' in tax_obj.name.lower() or 'ضريبة القيمة المضافة' in tax_obj.name.lower():
                            total_vat += tax_line['amount']
                        if 'muncipality' in tax_obj.name.lower() or 'municipality' in tax_obj.name.lower() or 'muni' in tax_obj.name.lower() or 'بلدية' in tax_obj.name.lower() or 'رسوم البلدية' in tax_obj.name.lower() or 'رسوم  إيواء' in tax_obj.name.lower():
                            total_municipality += tax_line['amount']
            else:
                total_untaxed = base_amount

            rec.meal_rate_vat = float_round(total_vat, precision_digits=2)
            rec.meal_rate_municiplaity_tax = float_round(total_municipality, precision_digits=2)
            rec.meal_rate_untaxed = float_round(
                                        rec.total_meal_after_discount - total_vat - total_municipality,
                                        precision_digits=2
                                    )

    
    @api.depends(
        'total_fixed_post_after_discount',
        'posting_item_ids',
        'posting_item_ids.posting_item_id',
        'posting_item_ids.posting_item_id.taxes',
        'posting_item_ids.posting_item_id.taxes.amount',
        'posting_item_ids.posting_item_id.taxes.amount_type',
        'posting_item_ids.posting_item_id.taxes.include_base_amount',
        'posting_item_ids.posting_item_id.taxes.price_include',
        'posting_item_ids.posting_item_id.taxes.tax_group_id',
    )
    def _compute_fixed_post_taxes(self):
        if self.env.context.get('skip_total_forecast_computation'):
            return
        for rec in self:
            rec.fixed_post_vat = 0.0
            rec.fixed_post_municiplaity_tax = 0.0
            rec.fixed_post_untaxed = 0.0

            currency = rec.env.company.currency_id
            total_amount = rec.total_fixed_post_after_discount or 0.0

            vat_total = 0.0
            muni_total = 0.0
            untaxed_total = 0.0

            if not rec.posting_item_ids:
                rec.fixed_post_untaxed = total_amount
                continue

            for line in rec.posting_item_ids:
                posting_item = line.posting_item_id
                if not posting_item or not posting_item.taxes:
                    untaxed_total += total_amount
                    continue

                taxes = posting_item.taxes
                tax_result = taxes.compute_all(total_amount, currency=currency)

                for tax in tax_result.get('taxes', []):
                    tax_obj = self.env['account.tax'].browse(tax['id'])
                    tax_name = tax_obj.with_context(lang='en_US').name.lower().strip()

                    if 'vat' in tax_name or 'ضريبة القيمة المضافة' in tax_name:
                        vat_total += tax['amount']
                    if 'municipality' in tax_name or 'muncipality' in tax_name or 'muni' in tax_name or 'بلدية' in tax_name or 'رسوم البلدية' in tax_name:
                        muni_total += tax['amount']

                untaxed_total += tax_result.get('total_excluded', total_amount)

            rec.fixed_post_vat = vat_total
            rec.fixed_post_municiplaity_tax = muni_total
            rec.fixed_post_untaxed = untaxed_total


    total_rate_forecast = fields.Float(
        string='Total Rate',
        compute='_compute_total_rate_forecast',
        store=False,
        tracking=True
    )

    
    
    # @api.depends('rate_forecast_ids.rate')
    # def _compute_total_rate_forecast(self):
    #     if self.env.context.get('skip_total_forecast_computation'):
    #         return
    #     for record in self:
    #         # -------------------- RATE CALCULATION --------------------
    #         checkin_date = fields.Date.from_string(record.checkin_date)
    #         checkout_date = fields.Date.from_string(record.checkout_date)
    #         if record.is_offline_search == False:
    #             total_days = (checkout_date - checkin_date).days
    #         else:
    #             total_days = 1
    #         total_days = 1 if total_days == 0 else total_days

    #         rate_details = self.env['rate.detail'].search([
    #             ('rate_code_id', '=', record.rate_code.id),
    #             ('from_date', '<=', checkin_date),
    #             ('to_date', '>=', checkin_date)
    #         ], limit=1)

    #         is_amount_value = rate_details.is_amount if rate_details else None
    #         is_percentage_value = rate_details.is_percentage if rate_details else None
    #         amount_selection_value = rate_details.amount_selection if rate_details else None
    #         percentage_selection_value = rate_details.percentage_selection if rate_details else None
    #         rate_detail_discount_value = int(rate_details.rate_detail_dicsount) if rate_details else 0

    #         total = sum(line.rate for line in record.rate_forecast_ids)
    #         record.total_rate_forecast = total

    #         if record.use_price:
    #             if record.room_is_amount:
    #                 if record.room_amount_selection and record.room_amount_selection.lower() == "total":
    #                     record.total_rate_forecast = total
    #                     _logger.debug("State value: %s", record.state)  # Debugging log
    #                     # if record.state == 'confirmed':
    #                     if record.state in ['not_confirmed','confirmed']:
    #                         _logger.debug("Total rate after discount will be calculated.")
    #                         record.total_rate_after_discount = total - (record.room_discount * record.no_of_nights)
    #                     elif record.state in ['block', 'check_in', 'check_out']:
    #                     # elif record.state == 'block':
    #                         # Find parent or use current record as parent
    #                         parent_booking = record.parent_booking_id if record.parent_booking_id else record

    #                         # Get all child bookings of this parent
    #                         child_bookings = self.env['room.booking'].search([
    #                             ('parent_booking_id', '=', parent_booking.id)
    #                         ])
                            
    #                         if record.parent_booking_id:  # It is a child booking
    #                             room_count = len(child_bookings) + parent_booking.room_count
    #                         else:  # It is a parent booking
    #                             room_count = parent_booking.room_count + len(child_bookings)

    #                         _logger.debug(">>> Parent booking: %s", parent_booking.name)
    #                         _logger.debug(">>> Child bookings count: %s", len(child_bookings))
    #                         _logger.debug(">>> Room count used: %s", room_count)

    #                         discount = record.room_discount / room_count if room_count else 0
    #                         nights = record.no_of_nights if record.no_of_nights != 0 else 1
    #                         total_discount = discount * nights
    #                         # total_discount = discount * record.no_of_nights
    #                         record.total_rate_after_discount = total - total_discount

    #                         _logger.debug("Discount per room: %s", discount)
    #                         _logger.debug("Total discount: %s", total_discount)
    #                         _logger.debug("Total rate after discount: %s", record.total_rate_after_discount)
    #                         # record.total_rate_after_discount = total - (record.room_discount * record.room_count)

    #                 elif record.room_amount_selection and record.room_amount_selection.lower() == "line_wise":
    #                     record.total_rate_forecast = total
    #                     if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
    #                         record.total_rate_after_discount = total - (record.room_discount * record.room_count * total_days)

    #                 else:
    #                     record.total_rate_forecast = total
    #                     record.total_rate_after_discount = total

    #             elif record.room_is_percentage:
    #                 record.total_rate_forecast = total
    #                 if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
    #                     discount_amount = total * record.room_discount
    #                     record.total_rate_after_discount = total - discount_amount
    #             else:
    #                 record.total_rate_forecast = total
    #                 record.total_rate_after_discount = total

    #         else:
    #             record.total_rate_forecast = total  # ✅ Ensure assignment even without use_price
    #             if is_amount_value and amount_selection_value == 'total':
    #                 # if record.state == 'confirmed':
    #                 if record.state in ['not_confirmed','confirmed']:
    #                     record.total_rate_after_discount = total - (rate_detail_discount_value * record.no_of_nights)
    #                 elif record.state in ['block', 'check_in', 'check_out']:
    #                 # elif record.state == 'block':
    #                     # Find parent or use current record as parent
    #                     parent_booking = record.parent_booking_id if record.parent_booking_id else record

    #                     # Get all child bookings of this parent
    #                     child_bookings = self.env['room.booking'].search([
    #                         ('parent_booking_id', '=', parent_booking.id)
    #                     ])
                        
    #                     if record.parent_booking_id:  # It is a child booking
    #                         room_count = len(child_bookings) + parent_booking.room_count
    #                     else:  # It is a parent booking
    #                         room_count = parent_booking.room_count + len(child_bookings)

    #                     _logger.debug(">>> Parent booking: %s", parent_booking.name)
    #                     _logger.debug(">>> Child bookings count: %s", len(child_bookings))
    #                     _logger.debug(">>> Room count used: %s", room_count)

    #                     discount = rate_detail_discount_value / room_count if room_count else 0
    #                     nights = record.no_of_nights if record.no_of_nights != 0 else 1
    #                     total_discount = discount * nights
    #                     # total_discount = discount * record.no_of_nights
    #                     record.total_rate_after_discount = total - total_discount

    #                     _logger.debug("Discount per room: %s", discount)
    #                     _logger.debug("Total discount: %s", total_discount)
    #                     _logger.debug("Total rate after discount: %s", record.total_rate_after_discount)

                        
    #                     # record.total_rate_after_discount = total - (rate_detail_discount_value * record.room_count) * record.room_count)
    #             elif is_amount_value and amount_selection_value == 'line_wise':
    #                 if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
    #                     record.total_rate_after_discount = total - (rate_detail_discount_value * record.room_count * total_days)
    #             elif is_percentage_value and percentage_selection_value in ['total', 'line_wise']:
    #                 if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
    #                     discount_amount = total * (rate_detail_discount_value / 100)
    #                     record.total_rate_after_discount = total - discount_amount
    #             else:
    #                 record.total_rate_after_discount = total

    #             if self.env.context.get('early_checkout_override') and record.id in self.env.context.get('override_values', {}):
    #                 override_value = self.env.context['override_values'][record.id]
    #                 _logger.debug("Applying early-checkout override for record %s: %s", record.id, override_value)
    #                 record.total_rate_after_discount = override_value
    #                 _logger.debug(f"Total Rate After Discount (with override): {record.total_rate_after_discount}")

    #         # -------------------- MEAL CALCULATION --------------------
    #         total_meal = sum(line.meals for line in record.rate_forecast_ids)

    #         if record.use_meal_price:
    #             if record.meal_is_amount:
    #                 if record.meal_amount_selection and record.meal_amount_selection.lower() == "total":
    #                     record.total_meal_forecast = total_meal
    #                     if record.state in ['not_confirmed','confirmed']:
    #                         # add condition here
    #                         if rate_details:# and rate_details.price_type != 'room_only':
    #                             record.total_meal_after_discount = total_meal - (record.meal_discount * record.no_of_nights)
    #                         else:
    #                             record.total_meal_after_discount = total_meal
    #                     elif record.state in ['block', 'check_in', 'check_out']:
    #                     # elif record.state == 'block':
    #                         # Find parent or use current record as parent
    #                         parent_booking = record.parent_booking_id if record.parent_booking_id else record

    #                         # Get all child bookings of this parent
    #                         child_bookings = self.env['room.booking'].search([
    #                             ('parent_booking_id', '=', parent_booking.id)
    #                         ])

    #                         if record.parent_booking_id:  # It is a child booking
    #                             room_count = len(child_bookings) + parent_booking.room_count
    #                         else:  # It is a parent booking
    #                             room_count = parent_booking.room_count + len(child_bookings)

    #                         _logger.debug(">>> Parent booking: %s", parent_booking.name)
    #                         _logger.debug(">>> Child bookings count: %s", len(child_bookings))
    #                         _logger.debug(">>> Room count used: %s", room_count)

    #                         discount = record.meal_discount / room_count if room_count else 0
    #                         nights = record.no_of_nights if record.no_of_nights != 0 else 1
    #                         total_discount = 0
    #                         if rate_details:# and rate_details.price_type != 'room_only':
    #                             total_discount = discount * nights
    #                         # total_discount = discount * record.no_of_nights
    #                         record.total_meal_after_discount = total_meal - total_discount

    #                         _logger.debug("Discount per room: %s", discount)
    #                         _logger.debug("Total discount: %s", total_discount)
    #                         _logger.debug("Total rate after discount: %s", record.total_rate_after_discount)
    #                         _logger.debug("Total rate after discount: %s", record.total_meal_after_discount)
    #                     # record.total_meal_after_discount = total_meal - (record.meal_discount * record.room_count)

    #                 elif record.meal_amount_selection and record.meal_amount_selection.lower() == "line_wise":
    #                     record.total_meal_forecast = total_meal
    #                     if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
    #                         if rate_details:# and rate_details.price_type != 'room_only':
    #                             record.total_meal_after_discount = total_meal - (record.meal_discount * record.room_count * total_days)

    #                 else:
    #                     record.total_meal_forecast = total_meal
    #                     record.total_meal_after_discount = total_meal

    #             elif record.meal_is_percentage:
    #                 record.total_meal_forecast = total_meal
    #                 if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
    #                     if rate_details and rate_details.price_type != 'room_only':
    #                         discount_amount_meal = total_meal * record.meal_discount
    #                         record.total_meal_after_discount = total_meal - discount_amount_meal
    #                     else:
    #                         record.total_meal_after_discount = total_meal
    #             else:
    #                 record.total_meal_forecast = total_meal
    #                 record.total_meal_after_discount = total_meal
    #         else:
    #             record.total_meal_forecast = total_meal  # ✅ Ensure assignment even without use_price
    #             if is_amount_value and amount_selection_value == 'total':
    #                 if record.state in ['not_confirmed','confirmed']:
    #                     if rate_details and rate_details.price_type != 'room_only':
    #                         record.total_meal_after_discount = total_meal - (rate_detail_discount_value * record.no_of_nights)
    #                     else:
    #                         record.total_meal_after_discount = total_meal
                         
    #                 elif record.state in ['block', 'check_in', 'check_out']:
    #                 # elif record.state == 'block':
    #                     # Find parent or use current record as parent
    #                     parent_booking = record.parent_booking_id if record.parent_booking_id else record

    #                     # Get all child bookings of this parent
    #                     child_bookings = self.env['room.booking'].search([
    #                         ('parent_booking_id', '=', parent_booking.id)
    #                     ])

    #                     if record.parent_booking_id:  # It is a child booking
    #                         room_count = len(child_bookings) + parent_booking.room_count
    #                     else:  # It is a parent booking
    #                         room_count = parent_booking.room_count + len(child_bookings)

    #                     _logger.debug(">>> Parent booking: %s", parent_booking.name)
    #                     _logger.debug(">>> Child bookings count: %s", len(child_bookings))
    #                     _logger.debug(">>> Room count used: %s", room_count)

    #                     discount = rate_detail_discount_value / room_count if room_count else 0
    #                     nights = record.no_of_nights if record.no_of_nights != 0 else 1
    #                     total_discount = 0
    #                     if rate_details and rate_details.price_type != 'room_only':
    #                         total_discount = discount * nights
    #                     # total_discount = discount * record.no_of_nights
    #                     record.total_meal_after_discount = total_meal - total_discount

    #                     _logger.debug("Discount per room: %s", discount)
    #                     _logger.debug("Total discount: %s", total_discount)
    #                     _logger.debug("Total rate after discount: %s", record.total_rate_after_discount)
    #                     _logger.debug("Total rate after discount: %s", record.total_meal_after_discount)
    #                 # record.total_meal_after_discount = total_meal - (rate_detail_discount_value * record.room_count)
    #             elif is_amount_value and amount_selection_value == 'line_wise':
    #                 if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
    #                     if rate_details and rate_details.price_type != 'room_only':
    #                         record.total_meal_after_discount = total_meal - (rate_detail_discount_value * record.room_count * total_days)
    #                     else:
    #                         record.total_meal_after_discount = total_meal
    #             elif is_percentage_value and percentage_selection_value in ['total', 'line_wise']:
    #                 if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
    #                     if rate_details and rate_details.price_type != 'room_only':
    #                         discount_amount = total_meal * (rate_detail_discount_value / 100)
    #                     else:
    #                         discount_amount = 0
    #                     record.total_meal_after_discount = total_meal - discount_amount
    #             else:
    #                 record.total_meal_after_discount = total_meal

    #         record.total_fixed_post_after_discount = record.total_fixed_post_forecast 

    #         # -------------------- FINAL TOTAL FORECAST --------------------
    #         _logger.debug(f'TOTAL FORECAST: {record.total_rate_after_discount}')
    #         if record.total_rate_after_discount < 0:
    #             record.total_rate_after_discount = 0.0
    #         if record.total_meal_after_discount < 0:
    #             record.total_meal_after_discount = 0.0
    #         if record.total_fixed_post_after_discount < 0:
    #             record.total_fixed_post_after_discount = 0.0

    #         record.total_total_forecast = (
    #             (record.total_rate_after_discount or 0.0) +
    #             (record.total_meal_after_discount or 0.0) +
    #             (record.total_package_after_discount or 0.0) +
    #             (record.total_fixed_post_after_discount or 0.0)
    #         )

    #     self._compute_room_taxes()
    #     self._compute_meal_taxes()
    #     self._compute_fixed_post_taxes()
    #     self._onchange_packaged_taxes()

    #     # ✅ Total Tax Summary
    #     record.total_municipality_tax = (
    #         record.room_rate_municiplaity_tax +
    #         record.meal_rate_municiplaity_tax +
    #         record.packages_municiplaity_tax +
    #         record.fixed_post_municiplaity_tax
    #     )

    #     record.total_vat = (
    #         record.room_rate_vat +
    #         record.meal_rate_vat +
    #         record.packages_vat +
    #         record.fixed_post_vat
    #     )

    #     record.total_untaxed = (
    #         record.room_rate_untaxed +
    #         record.meal_rate_untaxed +
    #         record.packages_untaxed +
    #         record.fixed_post_untaxed
    #     )

    
    @api.depends('rate_forecast_ids.rate')
    def _compute_total_rate_forecast(self):
        # CRITICAL: Skip expensive computation during onchange operations
        if (self.env.context.get('skip_total_forecast_computation') or
            self.env.context.get('from_onchange') or
            self.env.context.get('skip_tax_computation')):
            return
        
        # Cache for rate_details and child_bookings to avoid repeated searches
        rate_details_cache = {}
        child_bookings_cache = {}
        debug_mode = self.env.context.get('debug_forecast', False)
        
        for record in self:
            # Early validation to skip invalid records
            if not record.checkin_date or not record.checkout_date or not record.rate_code:
                record.total_rate_forecast = 0
                record.total_rate_after_discount = 0
                record.total_meal_forecast = 0
                record.total_meal_after_discount = 0
                record.total_fixed_post_after_discount = 0
                record.total_total_forecast = 0
                continue
                
            # -------------------- RATE CALCULATION --------------------
            checkin_date = fields.Date.from_string(record.checkin_date)
            checkout_date = fields.Date.from_string(record.checkout_date)
            
            if record.is_offline_search == False:
                total_days = (checkout_date - checkin_date).days
            else:
                total_days = 1
            total_days = 1 if total_days == 0 else total_days

            # OPTIMIZATION: Cache rate_details lookup to avoid repeated database queries
            rate_details_key = (record.rate_code.id, checkin_date)
            if rate_details_key not in rate_details_cache:
                rate_details_cache[rate_details_key] = self.env['rate.detail'].search([
                    ('rate_code_id', '=', record.rate_code.id),
                    ('from_date', '<=', checkin_date),
                    ('to_date', '>=', checkin_date)
                ], limit=1)
            
            rate_details = rate_details_cache[rate_details_key]

            # Pre-calculate discount variables to avoid repeated access
            is_amount_value = rate_details.is_amount if rate_details else None
            is_percentage_value = rate_details.is_percentage if rate_details else None
            amount_selection_value = rate_details.amount_selection if rate_details else None
            percentage_selection_value = rate_details.percentage_selection if rate_details else None
            rate_detail_discount_value = rate_details.rate_detail_dicsount if rate_details else 0

            total = sum(line.rate for line in record.rate_forecast_ids)
            record.total_rate_forecast = total

            # Helper function to get child bookings with caching
            def get_child_bookings_cached(parent_booking):
                parent_key = parent_booking.id
                if parent_key not in child_bookings_cache:
                    child_bookings_cache[parent_key] = self.env['room.booking'].search([
                        ('parent_booking_id', '=', parent_booking.id)
                    ])
                return child_bookings_cache[parent_key]

            # Helper function to calculate room count
            def calculate_room_count(record, parent_booking, child_bookings):
                if record.parent_booking_id:  # It is a child booking
                    return len(child_bookings) + parent_booking.room_count
                else:  # It is a parent booking
                    return parent_booking.room_count + len(child_bookings)

            # Helper function for debug logging
            def debug_log(message, *args):
                if debug_mode:
                    _logger.debug(message, *args)

            if record.use_price:
                if record.room_is_amount:
                    if record.room_amount_selection and record.room_amount_selection.lower() == "total":
                        record.total_rate_forecast = total
                        debug_log("State value: %s", record.state)
                        
                        if record.state in ['not_confirmed','confirmed']:
                            debug_log("Total rate after discount will be calculated.")
                            record.total_rate_after_discount = total - (record.room_discount * record.no_of_nights)
                        elif record.state in ['block', 'check_in', 'check_out']:
                            # Find parent or use current record as parent
                            parent_booking = record.parent_booking_id if record.parent_booking_id else record
                            
                            # OPTIMIZATION: Use cached child bookings lookup
                            child_bookings = get_child_bookings_cached(parent_booking)
                            room_count = calculate_room_count(record, parent_booking, child_bookings)

                            debug_log(">>> Parent booking: %s", parent_booking.name)
                            debug_log(">>> Child bookings count: %s", len(child_bookings))
                            debug_log(">>> Room count used: %s", room_count)

                            discount = record.room_discount / room_count if room_count else 0
                            nights = record.no_of_nights if record.no_of_nights != 0 else 1
                            total_discount = discount * nights
                            record.total_rate_after_discount = total - total_discount

                            debug_log("Discount per room: %s", discount)
                            debug_log("Total discount: %s", total_discount)
                            debug_log("Total rate after discount: %s", record.total_rate_after_discount)

                    elif record.room_amount_selection and record.room_amount_selection.lower() == "line_wise":
                        record.total_rate_forecast = total
                        if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
                            record.total_rate_after_discount = total - (record.room_discount * record.room_count * total_days)
                    else:
                        record.total_rate_forecast = total
                        record.total_rate_after_discount = total

                elif record.room_is_percentage:
                    record.total_rate_forecast = total
                    if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
                        discount_amount = total * record.room_discount
                        record.total_rate_after_discount = total - discount_amount
                else:
                    record.total_rate_forecast = total
                    record.total_rate_after_discount = total

            else:
                record.total_rate_forecast = total
                if is_amount_value and amount_selection_value == 'total':
                    if record.state in ['not_confirmed','confirmed']:
                        record.total_rate_after_discount = total - (rate_detail_discount_value * record.no_of_nights)
                    elif record.state in ['block', 'check_in', 'check_out']:
                        # nights = record.no_of_nights or 1
                        # per_night = (
                        #     (record.total_rate_after_discount or 0.0)
                        # + (record.total_meal_after_discount or 0.0)
                        # + (record.total_fixed_post_after_discount or 0.0)
                        # ) / nights
            
                        # # write to forecast lines (guard to avoid recompute loop)
                        # if record.rate_forecast_ids:
                        #     record.rate_forecast_ids.write({
                        #         'total': per_night
                        #     })
                        # self.env.cr.flush()
                        
                        # Clear cache after forecast line updates
                        # rate_details_cache.clear()
                        # child_bookings_cache.clear()
                    
                        # Find parent or use current record as parent
                        parent_booking = record.parent_booking_id if record.parent_booking_id else record
                        
                        # OPTIMIZATION: Use cached child bookings lookup
                        child_bookings = get_child_bookings_cached(parent_booking)
                        room_count = calculate_room_count(record, parent_booking, child_bookings)

                        debug_log(">>> Parent booking: %s", parent_booking.name)
                        debug_log(">>> Child bookings count: %s", len(child_bookings))
                        debug_log(">>> Room count used: %s", room_count)

                        discount = rate_detail_discount_value / room_count if room_count else 0
                        nights = record.no_of_nights if record.no_of_nights != 0 else 1
                        total_discount = discount * nights
                        record.total_rate_after_discount = total - total_discount

                        debug_log("Discount per room: %s", discount)
                        debug_log("Total discount: %s", total_discount)
                        debug_log("Total rate after discount: %s", record.total_rate_after_discount)
                            
                elif is_amount_value and amount_selection_value == 'line_wise':
                    if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
                        record.total_rate_after_discount = total - (rate_detail_discount_value * record.room_count * total_days)
                elif is_percentage_value and percentage_selection_value in ['total', 'line_wise']:
                    if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
                        discount_amount = total * (rate_detail_discount_value / 100)
                        record.total_rate_after_discount = total - discount_amount
                else:
                    record.total_rate_after_discount = total

                # Handle early checkout override
                if self.env.context.get('early_checkout_override') and record.id in self.env.context.get('override_values', {}):
                    override_value = self.env.context['override_values'][record.id]
                    debug_log("Applying early-checkout override for record %s: %s", record.id, override_value)
                    record.total_rate_after_discount = override_value
                    debug_log("Total Rate After Discount (with override): %s", record.total_rate_after_discount)

            # -------------------- MEAL CALCULATION --------------------
            total_meal = sum(line.meals for line in record.rate_forecast_ids)

            if record.use_meal_price:
                if record.meal_is_amount:
                    if record.meal_amount_selection and record.meal_amount_selection.lower() == "total":
                        record.total_meal_forecast = total_meal
                        if record.state in ['not_confirmed','confirmed']:
                            if rate_details:
                                record.total_meal_after_discount = total_meal - (record.meal_discount * record.no_of_nights)
                            else:
                                record.total_meal_after_discount = total_meal
                        elif record.state in ['block', 'check_in', 'check_out']:
                            # Find parent or use current record as parent
                            parent_booking = record.parent_booking_id if record.parent_booking_id else record
                            
                            # OPTIMIZATION: Use cached child bookings lookup
                            child_bookings = get_child_bookings_cached(parent_booking)
                            room_count = calculate_room_count(record, parent_booking, child_bookings)

                            debug_log(">>> Parent booking: %s", parent_booking.name)
                            debug_log(">>> Child bookings count: %s", len(child_bookings))
                            debug_log(">>> Room count used: %s", room_count)

                            discount = record.meal_discount / room_count if room_count else 0
                            nights = record.no_of_nights if record.no_of_nights != 0 else 1
                            total_discount = 0
                            if rate_details:
                                total_discount = discount * nights
                            record.total_meal_after_discount = total_meal - total_discount

                            debug_log("Discount per room: %s", discount)
                            debug_log("Total discount: %s", total_discount)
                            debug_log("Total meal after discount: %s", record.total_meal_after_discount)

                    elif record.meal_amount_selection and record.meal_amount_selection.lower() == "line_wise":
                        record.total_meal_forecast = total_meal
                        if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
                            if rate_details:
                                record.total_meal_after_discount = total_meal - (record.meal_discount * record.room_count * total_days)
                            else:
                                record.total_meal_after_discount = total_meal
                    else:
                        record.total_meal_forecast = total_meal
                        record.total_meal_after_discount = total_meal

                elif record.meal_is_percentage:
                    record.total_meal_forecast = total_meal
                    if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
                        if rate_details and rate_details.price_type != 'room_only':
                            discount_amount_meal = total_meal * record.meal_discount
                            record.total_meal_after_discount = total_meal - discount_amount_meal
                        else:
                            record.total_meal_after_discount = total_meal
                else:
                    record.total_meal_forecast = total_meal
                    record.total_meal_after_discount = total_meal
            else:
                record.total_meal_forecast = total_meal
                if is_amount_value and amount_selection_value == 'total':
                    if record.state in ['not_confirmed','confirmed']:
                        if rate_details and rate_details.price_type != 'room_only':
                            record.total_meal_after_discount = total_meal - (rate_detail_discount_value * record.no_of_nights)
                        else:
                            record.total_meal_after_discount = total_meal
                    elif record.state in ['block', 'check_in', 'check_out']:
                        # Find parent or use current record as parent
                        parent_booking = record.parent_booking_id if record.parent_booking_id else record
                        
                        # OPTIMIZATION: Use cached child bookings lookup
                        child_bookings = get_child_bookings_cached(parent_booking)
                        room_count = calculate_room_count(record, parent_booking, child_bookings)

                        debug_log(">>> Parent booking: %s", parent_booking.name)
                        debug_log(">>> Child bookings count: %s", len(child_bookings))
                        debug_log(">>> Room count used: %s", room_count)

                        discount = rate_detail_discount_value / room_count if room_count else 0
                        nights = record.no_of_nights if record.no_of_nights != 0 else 1
                        total_discount = 0
                        if rate_details and rate_details.price_type != 'room_only':
                            total_discount = discount * nights
                        record.total_meal_after_discount = total_meal - total_discount

                        debug_log("Discount per room: %s", discount)
                        debug_log("Total discount: %s", total_discount)
                        debug_log("Total meal after discount: %s", record.total_meal_after_discount)
                            
                elif is_amount_value and amount_selection_value == 'line_wise':
                    if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
                        if rate_details and rate_details.price_type != 'room_only':
                            record.total_meal_after_discount = total_meal - (rate_detail_discount_value * record.room_count * total_days)
                        else:
                            record.total_meal_after_discount = total_meal
                elif is_percentage_value and percentage_selection_value in ['total', 'line_wise']:
                    if record.state in ['not_confirmed','confirmed','block', 'check_in', 'check_out']:
                        if rate_details and rate_details.price_type != 'room_only':
                            discount_amount = total_meal * (rate_detail_discount_value / 100)
                        else:
                            discount_amount = 0
                        record.total_meal_after_discount = total_meal - discount_amount
                else:
                    record.total_meal_after_discount = total_meal

            record.total_fixed_post_after_discount = record.total_fixed_post_forecast 

            # -------------------- FINAL TOTAL FORECAST --------------------
            debug_log('TOTAL FORECAST: %s', record.total_rate_after_discount)
            
            # Ensure non-negative values
            if record.total_rate_after_discount < 0:
                record.total_rate_after_discount = 0.0
            if record.total_meal_after_discount < 0:
                record.total_meal_after_discount = 0.0
            if record.total_fixed_post_after_discount < 0:
                record.total_fixed_post_after_discount = 0.0

            record.total_total_forecast = (
                (record.total_rate_after_discount or 0.0) +
                (record.total_meal_after_discount or 0.0) +
                (record.total_package_after_discount or 0.0) +
                (record.total_fixed_post_after_discount or 0.0)
            )

        # OPTIMIZATION: Call tax computation methods only once for all records
        # instead of calling them for each record individually
        if self:  # Only call if there are records to process
            self._compute_room_taxes()
            self._compute_meal_taxes()
            self._compute_fixed_post_taxes()
            self._onchange_packaged_taxes()

            # ✅ Total Tax Summary - Calculate for each record
            for record in self:
                record.total_municipality_tax = (
                    record.room_rate_municiplaity_tax +
                    record.meal_rate_municiplaity_tax +
                    record.packages_municiplaity_tax +
                    record.fixed_post_municiplaity_tax
                )

                record.total_vat = (
                    record.room_rate_vat +
                    record.meal_rate_vat +
                    record.packages_vat +
                    record.fixed_post_vat
                )

                record.total_untaxed = (
                    record.room_rate_untaxed +
                    record.meal_rate_untaxed +
                    record.packages_untaxed +
                    record.fixed_post_untaxed   
                )

        # Update forecast lines after all computations are complete
        for record in self:
            if record.state in ['block', 'check_in', 'check_out'] and record.rate_forecast_ids:
                nights = record.no_of_nights or 1
                per_night = (
                    (record.total_rate_after_discount or 0.0)
                    + (record.total_meal_after_discount or 0.0)
                    + (record.total_fixed_post_after_discount or 0.0)
                ) / nights
                
                # write to forecast lines (guard to avoid recompute loop)
                record.rate_forecast_ids.write({
                    'total': per_night
                })
        
        # Flush and clear cache after all forecast line updates
        # self.env.cr.flush()
        # rate_details_cache.clear()
        # child_bookings_cache.clear()


    total_meal_forecast = fields.Float(
        string='Total Meals',
        compute='_compute_total_meal_forecast',
        tracking=True
    )
    
    meal_taxes = fields.Many2many(
        comodel_name='account.tax',
        string='Meal Taxes',
        help='Taxes from meal posting item'
    )

    
    @api.depends('rate_forecast_ids.meals')
    def _compute_total_meal_forecast(self):
        for record in self:
            
            if record.use_meal_price:
                if record.meal_amount_selection.lower() == "total":
                    total = sum(
                        line.meals for line in record.rate_forecast_ids)
                    if record.meal_is_amount:
                        # record.total_meal_forecast = total - (record.meal_discount * record.adult_count)
                        record.total_meal_forecast = total - \
                                                     (record.meal_discount)
                    else:
                        record.total_meal_forecast = sum(
                            line.meals for line in record.rate_forecast_ids)
                else:
                    record.total_meal_forecast = sum(
                        line.meals for line in record.rate_forecast_ids)
            else:
                record.total_meal_forecast = sum(
                    line.meals for line in record.rate_forecast_ids)

    total_package_forecast = fields.Float(
        string='Total Packages',
        compute='_compute_total_package_forecast',
        tracking=True
    )

    @api.depends('rate_forecast_ids.packages')
    def _compute_total_package_forecast(self):
        for record in self:
            record.total_package_forecast = sum(line.packages for line in record.rate_forecast_ids)
            record.total_package_forecast = 0.0

    total_fixed_post_forecast = fields.Float(
        string='Total Fixed Pst.',
        compute='_compute_total_fixed_post_forecast',
        tracking=True
    )

    @api.depends('rate_forecast_ids.fixed_post')
    def _compute_total_fixed_post_forecast(self):
        for record in self:
            record.total_fixed_post_forecast = sum(line.fixed_post for line in record.rate_forecast_ids)

    total_total_forecast = fields.Float(
        string='Grand Total',
        compute='_compute_total_total_forecast',
        store = True,
        tracking=True
    )

   
    total_rate_after_discount = fields.Float(
        string='Total Rate After Discount',
        store=True
    )

    total_meal_after_discount = fields.Float(
        string='Total Meal After Discount'
    )

    total_package_after_discount = fields.Float(
        string='Total Package After Discount'
    )

    total_fixed_post_after_discount = fields.Float(
        string='Total Fixed Post After Discount'
    )

    total_before_discount_forecast = fields.Float(
        string='Grand Total Before Discount',
        compute='_compute_total_before_discount_forecast'
    )

    @api.depends('rate_forecast_ids.before_discount')
    def _compute_total_before_discount_forecast(self):
        for record in self:
            # record.total_before_discount_forecast = record.total_rate_forecast + record.total_meal_forecast + record.total_package_forecast + record.total_fixed_post_forecast
            record.total_before_discount_forecast = sum(line.before_discount for line in record.rate_forecast_ids)

    def get_meal_rates(self, id):
        meal_rate_pax = 0
        meal_rate_child = 0
        meal_rate_infant = 0
        posting_item_id = None
        

        meal_pattern = self.env['meal.pattern'].search([('id', '=', id)])
        if meal_pattern:
            posting_item_id = meal_pattern.meal_posting_item.id
            for meal_code in meal_pattern.meals_list_ids:
                meal_rate_pax += meal_code.meal_code.price_pax
                meal_rate_child += meal_code.meal_code.price_child
                meal_rate_infant += meal_code.meal_code.price_infant
            

        return posting_item_id, meal_rate_pax, meal_rate_child, meal_rate_infant

    
    def get_all_prices(self, forecast_date, record):
        # Ensure we're working with a single record
        if isinstance(record, list) or (hasattr(record, '_ids') and len(record._ids) > 1):
            # If multiple records, just use the first one
            if hasattr(record, '_ids'):
                record = record[0] if record else record
            else:
                record = record[0] if record else record
        
        meal_price = 0
        room_price = 0
        package_price = 0
        take_meal_price = True
        take_room_price = True
        posting_item_value = None
        line_posting_items = []

        rate_details = self.env['rate.detail'].search([
            ('rate_code_id', '=', record.rate_code.id),
            ('from_date', '<=', forecast_date),
            ('to_date', '>=', forecast_date)
        ], limit=1)

        if not record.use_meal_price:
            if rate_details.price_type == "rate_meals":
                take_meal_price = True

            if rate_details.price_type == "room_only":
                take_meal_price = False

            # Check if meal_pattern.id exists
            if record.meal_pattern.id:
                take_meal_price = True

        if take_meal_price:
            if not record.use_meal_price:
                _1, meal_rate_pax, meal_rate_child, _not_used = self.get_meal_rates(
                    record.meal_pattern.id)

                if meal_rate_pax == 0:
                    if rate_details:
                        if rate_details.customize_meal == 'meal_pattern':
                            _1, meal_rate_pax, meal_rate_child, _not_used = self.get_meal_rates(
                                rate_details[0].meal_pattern_id.id)
                        elif rate_details.customize_meal == 'customize':
                            meal_rate_pax = rate_details.adult_meal_rate
                            meal_rate_child = rate_details.child_meal_rate
                            # meal_rate_infant = rate_details.infant_meal_rate

                meal_rate_pax_price = meal_rate_pax * record.adult_count * record.room_count
                meal_rate_child_price = meal_rate_child * \
                                        record.child_count * record.room_count

                meal_price += (meal_rate_pax_price + meal_rate_child_price)
            else:
                meal_price += record.meal_price * record.adult_count * record.room_count
                meal_price += record.meal_child_price * record.child_count * record.room_count
                

        if record.adult_count > 0:
            _day = forecast_date.strftime('%A').lower()
            _var = f"{_day}_pax_{record.adult_count}"
            _var_child = f"{_day}_child_pax_1"
            _var_infant = f"{_day}_infant_pax_1"
            _adult_count = 1
            if record.adult_count > 6:
                _var = f"{_day}_pax_1"
                _adult_count = record.adult_count

            if record.rate_code.id and not record.use_price:
                if rate_details:
                    posting_item_value = rate_details[0].posting_item.id
                    if record.hotel_room_type:
                        room_type_specific_rate = self.env['room.type.specific.rate'].search([
                            ('rate_code_id', '=', record.rate_code.id),
                            ('from_date', '<=', forecast_date),
                            ('to_date', '>=', forecast_date),
                            ('room_type_id', '=', record.hotel_room_type.id),
                            ('company_id', '=', self.env.company.id)
                        ], limit=1)

                        if room_type_specific_rate.id:
                            _room_type_var = f"room_type_{_day}_pax_{record.adult_count}"
                            if record.adult_count > 6:
                                _room_type_var = f"room_type_{_day}_pax_1"
                                room_price += room_type_specific_rate[_room_type_var] * record.adult_count
                            else:
                                room_price += room_type_specific_rate[_room_type_var]

                            _room_type_child_rate = f"room_type_{_day}_child_pax_1"
                            room_price += room_type_specific_rate[_room_type_child_rate] * record.child_count

                            _room_type_infant_rate = f"room_type_{_day}_infant_pax_1"
                            room_price += room_type_specific_rate[_room_type_infant_rate] * record.infant_count

                        else:
                            room_price += rate_details[0][_var] * record.room_count * _adult_count
                            room_price += rate_details[0][_var_child] * record.room_count * record.child_count
                            room_price += rate_details[0][_var_infant] * record.room_count * record.infant_count
                    else:
                        room_price += rate_details[0][_var] * record.room_count * _adult_count
                        room_price += rate_details[0][_var_child] * record.room_count * record.child_count
                        room_price += rate_details[0][_var_infant] * record.room_count * record.infant_count

                    room_price_room_line = self.get_rate_details_on_room_number_specific_rate(_day, record, forecast_date)
                    if room_price_room_line > 0:
                        room_price = room_price_room_line

                elif len(rate_details) > 1:
                    room_price += rate_details[0][_var] * record.room_count
                    room_price += rate_details[0][_var_child] * record.room_count
                    room_price += rate_details[0][_var_infant] * record.room_count

            elif record.use_price:
                room_price += record.room_price * record.room_count
                room_price += record.room_child_price * record.room_count
                room_price += record.room_infant_price * record.room_count

        if record.rate_code.id:
            for line in rate_details.line_ids:
                posting_item_id = line.packages_posting_item.id
                line_posting_items.append(posting_item_id)
                # print(f"Posting Item ID lne: {posting_item_id}")
                if line.packages_rhythm == "every_night" and line.packages_value_type == "added_value":
                    package_price += line.packages_value

                if line.packages_rhythm == "every_night" and line.packages_value_type == "per_pax":
                    package_price += line.packages_value * record.adult_count

                if line.packages_rhythm == "first_night" and line.packages_value_type == "added_value":
                    package_price += line.packages_value

                if line.packages_rhythm == "first_night" and line.packages_value_type == "per_pax":
                    package_price += line.packages_value * record.adult_count

        return meal_price, room_price, package_price, posting_item_value, line_posting_items

    
    @api.model
    def calculate_room_meal_discount(self, record_, 
                                    use_price, room_is_amount, room_amount_selection, room_discount,
                                    use_meal_price, meal_is_amount, meal_amount_selection, meal_discount,room_is_percentage,meal_is_percentage,forecast_date):
        total = 0.0

        # ---------- Room ----------
        if use_price and room_is_amount and room_amount_selection == 'line_wise':
            # print("inside use room line wise")
            if record_:
                if len(record_) > 1:
                    total += room_discount * record_[0].room_count 
                else:
                    total += room_discount * record_.room_count 
            else:
                total += room_discount * self.ensure_one().room_count 

        if use_price and room_is_amount and room_amount_selection == 'total':
            # print("inside use room total")
            total += room_discount 

        # ---------- Meal ----------
        if use_meal_price and meal_is_amount and meal_amount_selection == 'line_wise':
            # print("inside use meal line wise")
            if record_:
                if len(record_) > 1:
                    total += meal_discount * record_[0].room_count 
                else:
                    total += meal_discount * record_.room_count 
            else:
                total += meal_discount * self.ensure_one().room_count 

        if use_meal_price and meal_is_amount and meal_amount_selection == 'total':
            # print("inside use meal total")
            total += meal_discount 

            # ---------- Room Percentage ----------
        if room_is_percentage or meal_is_percentage:
            if record_ and forecast_date:
                if isinstance(record_, list) or (hasattr(record_, '_ids') and len(record_._ids) > 1):
                    if hasattr(record_, '_ids'):
                        record_singleton = record_[0] if record_ else record_
                    else:
                        record_singleton = record_[0] if record_ else record_
                    meals, rate, packages, _1, _2 = self.get_all_prices(forecast_date, record_singleton)
                else:
                    meals, rate, packages, _1, _2 = self.get_all_prices(forecast_date, record_)
            else:
                if len(self) > 1:
                    record_id = self[0].id
                else:
                    record_id = self.id
                forecast_line = self.env['room.rate.forecast'].search([
                    ('room_booking_id', '=', record_id)
                ], order='date asc', limit=1)

                if forecast_line:
                    rate = forecast_line.rate or 0.0
                    meals = forecast_line.meals or 0.0
                    packages = forecast_line.packages or 0.0
                else:
                    rate = meals = packages = 0.0

            price = rate + meals + 0.0  
            discount_ = price * room_discount
            total += round(discount_, 2)

        return total
    
    @api.model
    def calculate_total(self, price, discount, is_percentage, is_amount, percentage_selection, amount_selection, condition,
                        room_price=0.0, meal_price=0.0, package_price=0.0,
                        forecast_date=False, record_=False, use_price=False,
                        room_is_amount=False, room_amount_selection=False, room_discount=False,
                        use_meal_price=False, meal_is_amount=False, meal_amount_selection=False, meal_discount=False,
                        room_is_percentage=False, meal_is_percentage=False):

        total = 0.0
        if not condition:
            return 0.0

        # Fetch the relevant rate detail
        rate_details = self.env['rate.detail'].search([
            ('rate_code_id', '=', record_.rate_code.id),
            ('from_date', '<=', forecast_date),
            ('to_date', '>=', forecast_date)
        ], limit=1)
        price_type = rate_details.price_type if rate_details else 'default'

        # Determine multiplier: always count room; only count meal for rate_meals
        multiplier = 0
        if room_price != 0:
            multiplier += 1
        if price_type == 'rate_meals' and meal_price != 0:
            multiplier += 1

        # Determine which parts of the price are discount-able
        if price_type == 'room_only':
            _logger.debug("ROOM ONLY SELECTED")
            room_price_after_discount = room_price
            meal_price_after_discount = 0.0
        else:
            # Covers both 'rate_meals' and default fall-through
            if price_type == 'rate_meals':
                _logger.debug("RATE MEALS SELECTED")
            else:
                _logger.debug("DEFAULT RATE TYPE SELECTED")
            room_price_after_discount = room_price
            meal_price_after_discount = meal_price

        _logger.debug("room_price_after_discount: %s", room_price_after_discount)
        _logger.debug("meal_price_after_discount: %s", meal_price_after_discount)

        before_discount = room_price_after_discount + meal_price_after_discount + package_price

        # Amount-based discounts
        if is_amount:
            if amount_selection == 'line_wise':
                count = record_[0].room_count if (record_ and len(record_) > 1) else (record_.room_count if record_ else self.ensure_one().room_count)
                total = discount * count * multiplier
            elif amount_selection == 'total':
                total = discount * multiplier

        # Percentage-based discounts
        elif is_percentage and percentage_selection in ('line_wise', 'total'):
            # pull the base price (room only or room+meal)
            if price_type == 'room_only':
                base_price = room_price_after_discount
            else:
                base_price = room_price_after_discount + meal_price_after_discount

            total = round(base_price * discount, 2)

        return total

    
    @api.model
    def calculate_meal_rates(self, rate_details):
        total_default_value = 0

        # Retrieve the posting item from rate details
        rate_detail_posting_item = rate_details.posting_item if rate_details else 0
        if rate_detail_posting_item:
            # Get the default value of the posting item
            default_value = getattr(rate_detail_posting_item, 'default_value', 0)
            # Add this default value to the total
            total_default_value += default_value
        else:
            print("No Posting Item found. Default Value: 0")

        # Retrieve the meal pattern from rate details
        rate_detail_meal_pattern = rate_details.meal_pattern_id if rate_details else 0
        if rate_detail_meal_pattern:
            # Get the default value of meal_posting_item
            meal_posting_item = rate_detail_meal_pattern.meal_posting_item
            meal_posting_item_default_value = getattr(
                meal_posting_item, 'default_value', 0)

            # Add this default value to the total
            total_default_value += meal_posting_item_default_value

            # Loop through meal codes and calculate their default values
            for meal_code in rate_detail_meal_pattern.meals_list_ids:
                # Access the posting_item of each meal_code
                posting_item = meal_code.meal_code.posting_item

                # Get the default value of the posting_item
                meal_code_default_value = getattr(
                    posting_item, 'default_value', 0)
                print(
                    f"Posting Item Default Value (Meal Code): {meal_code_default_value}")

                # Add this default value to the total
                total_default_value += meal_code_default_value
        else:
            print("No Meal Pattern found.")

        return total_default_value

    manual_override = fields.Boolean(string="Manual Override Forecast", default=False)

    # @api.depends('adult_count', 'room_count', 'child_count', 'infant_count', 'checkin_date', 'checkout_date',
    #              'meal_pattern', 'rate_code', 'room_price', 'room_child_price', 'room_infant_price', 'meal_price',
    #              'meal_child_price', 'meal_infant_price', 'posting_item_ids', 'room_discount', 'room_is_percentage',
    #              'room_is_amount', 'room_amount_selection', 'meal_discount', 'meal_is_percentage', 'meal_is_amount',
    #              'meal_amount_selection', 'use_price', 'use_meal_price', 'complementary',
    #              'complementary_codes','room_line_ids.room_id')
    # def _get_forecast_rates(self, from_rate_code=False):
    #     _logger.debug("Calculating forecast rates for room bookings...")
    #     _logger.debug("from_rate_code: %s", self.rate_code)
    #     _logger.debug("from_rate_code: %s", self.meal_pattern)
    #     if not self.rate_code and not self.meal_pattern:
    #         return True
    #     for record in self:

    #         if record.manual_override:
    #             continue
    #         checkin_date = fields.Date.from_string(record.checkin_date)
    #         checkout_date = fields.Date.from_string(record.checkout_date)
    #         if checkin_date == checkout_date:
    #             total_days = 1
    #         else:
    #             if record.is_offline_search == False:
    #                 total_days = (checkout_date - checkin_date).days
    #                 if total_days == 0:
    #                     total_days = 1
    #             else:
    #                 total_days = 1

    #         _system_date = fields.Date.from_string(self.env.company.system_date)

    #         for rate_forecast in record.rate_forecast_ids:
    #             if rate_forecast:
    #                 if isinstance(rate_forecast.room_booking_id, NewId):
    #                     continue

    #                 # Check if rate_forecast's date is between checkin_date and checkout_date
    #                 forecast_date = fields.Date.from_string(rate_forecast.date)
    #                 if not (checkin_date <= forecast_date < checkout_date):
    #                     # Set room_booking_id to None if not in range
    #                     rate_forecast.room_booking_id = None

    #         if not record.checkin_date or not record.checkout_date:
    #             record.rate_forecast_ids = []
    #             continue

    #         checkin_date = fields.Date.from_string(record.checkin_date)
    #         checkout_date = fields.Date.from_string(record.checkout_date)
    #         total_days = (checkout_date - checkin_date).days
    #         if total_days == 0:
    #             total_days = 1

    #         _system_date = self.env.company.system_date

    #         from_start = True
    #         if record.state == 'check_in':
    #             from_start = False

            
    #         posting_items = record.posting_item_ids

    #         # Initialize variables for calculation
    #         first_night_value = sum(
    #             line.default_value for line in posting_items if line.posting_item_selection == 'first_night')
    #         every_night_value = sum(
    #             line.default_value for line in posting_items if line.posting_item_selection == 'every_night')

    #         # Get all rate detail records for the booking
    #         posting_items_ = self.env['room.rate.forecast'].search(
    #             [('room_booking_id', '=', record.id)])

    #         total_lines = len(posting_items_)

    #         fixed_post_value = 0

    #         # Fetch rate details for the record's rate code
    #         rate_details = self.env['rate.detail'].search([
    #             ('rate_code_id', '=', record.rate_code.id),
    #             ('from_date', '<=', checkin_date),
    #             ('to_date', '>=', checkin_date)
    #         ], limit=1)

    #         # Initialize discount-related variables
    #         is_amount_value = rate_details.is_amount if rate_details else None
    #         is_percentage_value = rate_details.is_percentage if rate_details else None
    #         amount_selection_value = rate_details.amount_selection if rate_details else None
    #         percentage_selection_value = rate_details.percentage_selection if rate_details else None
    #         if is_amount_value:
    #             rate_detail_discount_value = int(rate_details.rate_detail_dicsount) if rate_details else 0
    #         else:
    #             rate_detail_discount_value = int(rate_details.rate_detail_dicsount) / 100 if rate_details else 0

    #         forecast_lines = []

    #         for day in range(total_days):
    #             forecast_date = checkin_date + timedelta(days=day)
    #             change = True
    #             today_date = fields.Date.today()
    #             if record.state == 'check_in':
    #                 _date = _system_date.date()
    #                 if forecast_date < _date and not from_rate_code:
    #                     change = False

    #                 if forecast_date == _date and from_rate_code:
    #                     change = True

    #             # if today_date < forecast_date and _system_date > today_date:
    #             #     change = False

    #             if change:
    #                 meal_price, room_price, package_price, _1, _2 = self.get_all_prices(forecast_date, record)
    #                 if day == 0:  # First day logic
    #                     if every_night_value is None:
    #                         # Adjusted for room_count
    #                         fixed_post_value = (first_night_value or 0) * record.room_count
    #                     elif first_night_value is None:
    #                         # Adjusted for room_count
    #                         fixed_post_value = (every_night_value or 0) * record.room_count
    #                     else:
    #                         fixed_post_value = (first_night_value + every_night_value) * record.room_count
    #                 else:  # Other days
    #                     if every_night_value is None:
    #                         # Adjusted for room_count
    #                         fixed_post_value = (first_night_value or 0) * record.room_count
    #                     else:
    #                         fixed_post_value = every_night_value * record.room_count

    #                 # Add custom date values if the forecast_date falls within any custom date ranges
    #                 for line in posting_items:
    #                     if line.posting_item_selection == 'custom_date' and line.from_date and line.to_date:
    #                         from_date = fields.Date.from_string(line.from_date)
    #                         to_date = fields.Date.from_string(line.to_date)
    #                         checkin_date = fields.Date.from_string(
    #                             record.checkin_date)
    #                         checkout_date = fields.Date.from_string(
    #                             record.checkout_date)
    #                         # Check if current forecast_date falls within the custom date range
    #                         if from_date <= forecast_date <= to_date:
    #                             fixed_post_value += line.default_value * record.room_count

    #                 room_booking_id = record.id
    #                 room_booking_str = str(record.id).split('_')[-1]
    #                 if record.id is not int or record.id is not str or record.id is hex:
    #                     room_booking_id = record.id

    #                 elif record.id is not int:
    #                     if "0x" in str(record.id):
    #                         room_booking_id = record.id
    #                     else:
    #                         room_booking_id = int(str(record.id).split('_')[-1])

    #                 # Search for existing forecast record
    #                 existing_forecast = self.env['room.rate.forecast'].search([
    #                     ('room_booking_id', '=', room_booking_id),
    #                     ('date', '=', forecast_date)
    #                 ], limit=1)


    #                 if not record.use_price:
    #                     _room_price = room_price
    #                 else:
    #                     _room_price = record.room_price * record.room_count

    #                 room_price_after_discount = record.calculate_total(
    #                                                     _room_price,
    #                                                     record.room_discount,
    #                                                     record.room_is_percentage,
    #                                                     percentage_selection_value,
    #                                                     record.room_is_amount,
    #                                                     record.room_amount_selection,
    #                                                     record.use_price, 0, 0 ,0, forecast_date, self)

    #                 if not record.use_meal_price:
    #                     _meal_price = meal_price
    #                 else:
    #                     _meal_price = record.meal_price * record.adult_count * record.room_count
    #                     _meal_price += record.meal_child_price * record.child_count * record.room_count
    #                 meal_price_after_discount = record.calculate_total(
    #                     _meal_price,
    #                     record.meal_discount,
    #                     record.meal_is_percentage,
    #                     percentage_selection_value,
    #                     record.meal_is_amount,
    #                     record.meal_amount_selection, record.use_meal_price, 0, 0, 0, forecast_date, self)
                    
    #                 #  Get rate details to check price type
    #                 rate_details = self.env['rate.detail'].search([
    #                     ('rate_code_id', '=', record.rate_code.id),
    #                     ('from_date', '<=', forecast_date),
    #                     ('to_date', '>=', forecast_date)
    #                 ], limit=1)

    #                 meal_price_after_discount = 0 if rate_details and rate_details.price_type == 'room_only' else meal_price_after_discount

    #                 before_discount = room_price + meal_price + 0.0 + fixed_post_value

    #                 if len(self) > 1:
    #                     if record.use_price or record.use_meal_price:
    #                         get_discount = self[0].calculate_room_meal_discount(
    #                             self[0], 
    #                             record.use_price, record.room_is_amount, record.room_amount_selection, record.room_discount,
    #                             record.use_meal_price, record.meal_is_amount, record.meal_amount_selection, record.meal_discount,
    #                             record.room_is_percentage, record.meal_is_percentage, forecast_date
    #                         )
    #                     else:

    #                         get_discount = self[0].calculate_total(before_discount, rate_detail_discount_value,
    #                                                         is_percentage_value, is_amount_value, percentage_selection_value,
    #                                                         amount_selection_value, True, room_price, meal_price, package_price, forecast_date, self[0], 
    #                                                         use_price=record.use_price,
    #                                                         room_is_amount=record.room_is_amount,
    #                                                         room_amount_selection=record.room_amount_selection,
    #                                                         room_discount = record.room_discount,
    #                                                         use_meal_price = record.meal_price,
    #                                                         meal_is_amount = record.meal_is_amount,
    #                                                         meal_amount_selection = record.meal_amount_selection,
    #                                                         meal_discount = record.meal_discount,
    #                                                         room_is_percentage= record.room_is_percentage,
    #                                                         meal_is_percentage = record.meal_is_percentage)
    #                 else:
    #                     if record.use_price or record.use_meal_price:
    #                         get_discount = self.calculate_room_meal_discount(
    #                             self,
    #                             record.use_price, record.room_is_amount, record.room_amount_selection, record.room_discount,
    #                             record.use_meal_price, record.meal_is_amount, record.meal_amount_selection, record.meal_discount,
    #                             record.room_is_percentage, record.meal_is_percentage, forecast_date
    #                         )

    #                     else:
    #                         get_discount = self.calculate_total(before_discount, rate_detail_discount_value,
    #                                                         is_percentage_value, is_amount_value, percentage_selection_value,
    #                                                         amount_selection_value, True, room_price, meal_price, package_price, forecast_date, self,
    #                                                         use_price=record.use_price,
    #                                                         room_is_amount=record.room_is_amount,
    #                                                         room_amount_selection=record.room_amount_selection,
    #                                                         room_discount = record.room_discount,
    #                                                         use_meal_price = record.meal_price,
    #                                                         meal_is_amount = record.meal_is_amount,
    #                                                         meal_amount_selection = record.meal_amount_selection,
    #                                                         meal_discount = record.meal_discount,
    #                                                         room_is_percentage= record.room_is_percentage,
    #                                                         meal_is_percentage = record.meal_is_percentage)

    #                 total = before_discount - get_discount - room_price_after_discount - meal_price_after_discount
    #                 room_line_ids = record.room_line_ids.ids
    #                 actual_room_price = room_price - room_price_after_discount
    #                 actual_meal_price = meal_price - meal_price_after_discount
    #                 if record.complementary and record.complementary_codes.id:
    #                     if record.complementary_codes.type == 'room':
    #                         actual_room_price = 0

    #                     elif record.complementary_codes.type == 'fb':
    #                         actual_meal_price = 0

    #                     elif record.complementary_codes.type == "both":
    #                         actual_room_price = 0
    #                         actual_meal_price = 0
                        
    #                     before_discount = actual_room_price + actual_meal_price + package_price + fixed_post_value

    #                     total = before_discount - get_discount - \
    #                         room_price_after_discount - meal_price_after_discount


    #                 if existing_forecast:
    #                     existing_forecast.write({
    #                         'rate': actual_room_price,
    #                         'meals': actual_meal_price,
    #                         'packages': 0.0,
    #                         'fixed_post': fixed_post_value,
    #                         'total': total,
    #                         'before_discount': before_discount,
    #                         'booking_line_ids': [(6, 0, room_line_ids)]
    #                     })
    #                 else:
    #                     # Append new forecast line
    #                     forecast_lines.append((0, 0, {
    #                         'date': forecast_date,
    #                         'rate': actual_room_price,
    #                         # 'rate': room_price_after_discount if record.room_price else room_price,
    #                         # 'meals': meal_price_after_discount if record.meal_price else meal_price,
    #                         'meals': actual_meal_price,
    #                         # 'packages': package_price,
    #                         'packages': 0.0,
    #                         'fixed_post': fixed_post_value,
    #                         'total': total,
    #                         'before_discount': before_discount,
    #                         'booking_line_ids': [(6, 0, room_line_ids)]
    #                     }))


    #         record.rate_forecast_ids = forecast_lines

    
    @api.depends('adult_count', 'room_count', 'child_count', 'infant_count', 'checkin_date', 'checkout_date',
             'meal_pattern', 'rate_code', 'room_price', 'room_child_price', 'room_infant_price', 'meal_price',
             'meal_child_price', 'meal_infant_price', 'posting_item_ids', 'room_discount', 'room_is_percentage',
             'room_is_amount', 'room_amount_selection', 'meal_discount', 'meal_is_percentage', 'meal_is_amount',
             'meal_amount_selection', 'use_price', 'use_meal_price', 'complementary',
             'complementary_codes','room_line_ids.room_id')
    def _get_forecast_rates(self, from_rate_code=False):
        _logger.info("_get_forecast_rates")
        # CRITICAL: Skip expensive computation during onchange operations
        if (self.env.context.get('from_onchange') or 
            self.env.context.get('skip_forecast_computation') or
            self.env.context.get('skip_tax_computation')):
            return True
        
        # Reduce logging verbosity - only log once at start
        if self.env.context.get('debug_forecast'):
            _logger.debug("Calculating forecast rates for %d room bookings...", len(self))
        
        if not self.rate_code and not self.meal_pattern:
            return True
        
        # Cache for rate_details to avoid repeated searches
        rate_details_cache = {}
        
        for record in self:
            if record.manual_override:
                record.manual_override = False
                continue
                
            # Early validation
            if not record.checkin_date or not record.checkout_date:
                record.rate_forecast_ids = []
                continue
                
            checkin_date = fields.Date.from_string(record.checkin_date)
            checkout_date = fields.Date.from_string(record.checkout_date)
            
            # Calculate total_days once
            if checkin_date == checkout_date:
                total_days = 1
            else:
                if record.is_offline_search == False:
                    total_days = (checkout_date - checkin_date).days
                    if total_days == 0:
                        total_days = 1
                else:
                    total_days = 1

            _system_date = fields.Date.from_string(self.env.company.system_date)
            # Clean up existing forecasts outside date range (preserve original logic)
            for rate_forecast in record.rate_forecast_ids:
                if rate_forecast:
                    if isinstance(rate_forecast.room_booking_id, NewId):
                        continue
                    forecast_date = fields.Date.from_string(rate_forecast.date)
                    if not (checkin_date <= forecast_date < checkout_date):
                        rate_forecast.room_booking_id = None

            from_start = True
            if record.state == 'check_in':
                from_start = False
            
            posting_items = record.posting_item_ids

            # Pre-calculate fixed values outside the loop
            first_night_value = sum(
                line.default_value for line in posting_items if line.posting_item_selection == 'first_night')
            every_night_value = sum(
                line.default_value for line in posting_items if line.posting_item_selection == 'every_night')

            # OPTIMIZATION: Cache rate_details lookup outside the day loop
            rate_details_key = (record.rate_code.id, checkin_date)
            if rate_details_key not in rate_details_cache:
                rate_details_cache[rate_details_key] = self.env['rate.detail'].search([
                    ('rate_code_id', '=', record.rate_code.id),
                    ('from_date', '<=', checkin_date),
                    ('to_date', '>=', checkin_date)
                ], limit=1)
            
            rate_details = rate_details_cache[rate_details_key]

            # Pre-calculate discount-related variables
            is_amount_value = rate_details.is_amount if rate_details else None
            is_percentage_value = rate_details.is_percentage if rate_details else None
            amount_selection_value = rate_details.amount_selection if rate_details else None
            percentage_selection_value = rate_details.percentage_selection if rate_details else None
            
            if is_amount_value:
                rate_detail_discount_value = rate_details.rate_detail_dicsount if rate_details else 0
            else:
                rate_detail_discount_value = (rate_details.rate_detail_dicsount) / 100 if rate_details else 0

            # OPTIMIZATION: Bulk fetch existing forecasts for all dates at once
            room_booking_id = record.id
            room_booking_str = str(record.id).split('_')[-1]
            if record.id is not int or record.id is not str or record.id is hex:
                room_booking_id = record.id
            elif record.id is not int:
                if "0x" in str(record.id):
                    room_booking_id = record.id
                else:
                    room_booking_id = int(str(record.id).split('_')[-1])

            # Bulk search for existing forecasts
            forecast_dates = [checkin_date + timedelta(days=day) for day in range(total_days)]
            existing_forecasts = self.env['room.rate.forecast'].search([
                ('room_booking_id', '=', room_booking_id),
                ('date', 'in', forecast_dates)
            ])
            
            # Create a mapping for quick lookup
            existing_forecast_map = {forecast.date: forecast for forecast in existing_forecasts}

            forecast_lines = []
            room_line_ids = record.room_line_ids.ids

            for day in range(total_days):
                forecast_date = checkin_date + timedelta(days=day)
                change = True
                today_date = fields.Date.today()
                
                if record.state == 'check_in':
                    _date = _system_date
                    if forecast_date < _date and not from_rate_code:
                        change = False
                    if forecast_date == _date and from_rate_code:
                        change = True

                if change:
                    meal_price, room_price, package_price, _1, _2 = self.get_all_prices(forecast_date, record)
                    
                    # Calculate fixed_post_value for this day
                    if day == 0:  # First day logic
                        if every_night_value is None:
                            fixed_post_value = (first_night_value or 0) * record.room_count
                        elif first_night_value is None:
                            fixed_post_value = (every_night_value or 0) * record.room_count
                        else:
                            fixed_post_value = (first_night_value + every_night_value) * record.room_count
                    else:  # Other days
                        if every_night_value is None:
                            fixed_post_value = (first_night_value or 0) * record.room_count
                        else:
                            fixed_post_value = every_night_value * record.room_count

                    # Add custom date values if the forecast_date falls within any custom date ranges
                    for line in posting_items:
                        if line.posting_item_selection == 'custom_date' and line.from_date and line.to_date:
                            from_date = fields.Date.from_string(line.from_date)
                            to_date = fields.Date.from_string(line.to_date)
                            if from_date <= forecast_date <= to_date:
                                fixed_post_value += line.default_value * record.room_count

                    # Calculate prices and discounts (preserve original logic)
                    if not record.use_price:
                        _room_price = room_price
                    else:
                        _room_price = record.room_price * record.room_count

                    room_price_after_discount = record.calculate_total(
                        _room_price, record.room_discount, record.room_is_percentage,
                        percentage_selection_value, record.room_is_amount, record.room_amount_selection,
                        record.use_price, 0, 0, 0, forecast_date, self)

                    if not record.use_meal_price:
                        _meal_price = meal_price
                    else:
                        _meal_price = record.meal_price * record.adult_count * record.room_count
                        _meal_price += record.meal_child_price * record.child_count * record.room_count
                        
                    meal_price_after_discount = record.calculate_total(
                        _meal_price, record.meal_discount, record.meal_is_percentage,
                        percentage_selection_value, record.meal_is_amount, record.meal_amount_selection,
                        record.use_meal_price, 0, 0, 0, forecast_date, self)
                    
                    # Get rate details to check price type (cache this lookup too)
                    rate_details_for_date_key = (record.rate_code.id, forecast_date)
                    if rate_details_for_date_key not in rate_details_cache:
                        rate_details_cache[rate_details_for_date_key] = self.env['rate.detail'].search([
                            ('rate_code_id', '=', record.rate_code.id),
                            ('from_date', '<=', forecast_date),
                            ('to_date', '>=', forecast_date)
                        ], limit=1)
                    
                    rate_details_for_date = rate_details_cache[rate_details_for_date_key]
                    meal_price_after_discount = 0 if rate_details_for_date and rate_details_for_date.price_type == 'room_only' else meal_price_after_discount

                    before_discount = room_price + meal_price + 0.0 + fixed_post_value

                    # Calculate discount (preserve original logic)
                    if len(self) > 1:
                        if record.use_price or record.use_meal_price:
                            get_discount = self[0].calculate_room_meal_discount(
                                self[0], record.use_price, record.room_is_amount, record.room_amount_selection, record.room_discount,
                                record.use_meal_price, record.meal_is_amount, record.meal_amount_selection, record.meal_discount,
                                record.room_is_percentage, record.meal_is_percentage, forecast_date)
                        else:
                            get_discount = self[0].calculate_total(before_discount, rate_detail_discount_value,
                                                            is_percentage_value, is_amount_value, percentage_selection_value,
                                                            amount_selection_value, True, room_price, meal_price, package_price, forecast_date, self[0], 
                                                            use_price=record.use_price, room_is_amount=record.room_is_amount,
                                                            room_amount_selection=record.room_amount_selection, room_discount=record.room_discount,
                                                            use_meal_price=record.meal_price, meal_is_amount=record.meal_is_amount,
                                                            meal_amount_selection=record.meal_amount_selection, meal_discount=record.meal_discount,
                                                            room_is_percentage=record.room_is_percentage, meal_is_percentage=record.meal_is_percentage)
                    else:
                        if record.use_price or record.use_meal_price:
                            get_discount = self.calculate_room_meal_discount(
                                self, record.use_price, record.room_is_amount, record.room_amount_selection, record.room_discount,
                                record.use_meal_price, record.meal_is_amount, record.meal_amount_selection, record.meal_discount,
                                record.room_is_percentage, record.meal_is_percentage, forecast_date)
                        else:
                            get_discount = self.calculate_total(before_discount, rate_detail_discount_value,
                                                            is_percentage_value, is_amount_value, percentage_selection_value,
                                                            amount_selection_value, True, room_price, meal_price, package_price, forecast_date, self,
                                                            use_price=record.use_price, room_is_amount=record.room_is_amount,
                                                            room_amount_selection=record.room_amount_selection, room_discount=record.room_discount,
                                                            use_meal_price=record.meal_price, meal_is_amount=record.meal_is_amount,
                                                            meal_amount_selection=record.meal_amount_selection, meal_discount=record.meal_discount,
                                                            room_is_percentage=record.room_is_percentage, meal_is_percentage=record.meal_is_percentage)

                    total = before_discount - get_discount - room_price_after_discount - meal_price_after_discount
                    actual_room_price = room_price - room_price_after_discount
                    actual_meal_price = meal_price - meal_price_after_discount
                    
                    # Handle complementary codes (preserve original logic)
                    if record.complementary and record.complementary_codes.id:
                        if record.complementary_codes.type == 'room':
                            actual_room_price = 0
                            room_price_after_discount = 0
                            get_discount = get_discount / 2
                        elif record.complementary_codes.type == 'fb':
                            actual_meal_price = 0
                            meal_price_after_discount = 0
                            get_discount = get_discount / 2
                        elif record.complementary_codes.type == "both":
                            actual_room_price = 0
                            actual_meal_price = 0
                            meal_price_after_discount = 0
                            room_price_after_discount = 0
                            get_discount = 0

                        before_discount = actual_room_price + actual_meal_price + package_price + fixed_post_value
                        total = before_discount - get_discount - room_price_after_discount - meal_price_after_discount
                        _logger.debug(f"line 3212 {before_discount}, {get_discount},{room_price_after_discount},{meal_price_after_discount}")
                    # OPTIMIZATION: Use the pre-fetched existing forecast map
                    existing_forecast = existing_forecast_map.get(forecast_date)
                    
                    if existing_forecast:
                        existing_forecast.write({
                            'rate': actual_room_price,
                            'meals': actual_meal_price,
                            'packages': 0.0,
                            'fixed_post': fixed_post_value,
                            'total': total,
                            'before_discount': before_discount,
                            'booking_line_ids': [(6, 0, room_line_ids)]
                        })
                    else:
                        # Append new forecast line
                        forecast_lines.append((0, 0, {
                            'date': forecast_date,
                            'rate': actual_room_price,
                            'meals': actual_meal_price,
                            'packages': 0.0,
                            'fixed_post': fixed_post_value,
                            'total': total,
                            'before_discount': before_discount,
                            'booking_line_ids': [(6, 0, room_line_ids)]
                        }))

            # Only assign if there are new forecast lines
            if forecast_lines:
                record.rate_forecast_ids = forecast_lines
    
    
    is_readonly_group_booking = fields.Boolean(
        string="Is Readonly", compute="_compute_is_readonly_group_booking", store=False
    )

    @api.depends('group_booking')
    def _compute_is_readonly_group_booking(self):
        for record in self:
            record.is_readonly_group_booking = bool(record.group_booking)


    group_booking = fields.Many2one(
        'group.booking', string="Group Booking", domain=[('group_name', '!=', False)],
        help="Group associated with this booking", tracking=True)

    show_group_booking = fields.Boolean(
        string="Show Group Booking", compute="_compute_show_group_booking", store=False)

    
    @api.onchange('room_count')
    def _compute_show_group_booking(self):
        for record in self:
            record.show_group_booking = record.room_count > 1

    @api.onchange('group_booking')
    def _onchange_group_booking(self):
        if self.group_booking:
            self.nationality = self.group_booking.nationality.id if self.group_booking.nationality else False
            self.reference_contact_= self.group_booking.reference if self.group_booking.reference else False
            
            self.source_of_business = self.group_booking.source_of_business.id if self.group_booking.source_of_business else False
            self.rate_code = self.group_booking.rate_code.id if self.group_booking.rate_code else False
            self.meal_pattern = self.group_booking.group_meal_pattern.id if self.group_booking.group_meal_pattern else False
            self.market_segment = self.group_booking.market_segment.id if self.group_booking.market_segment else False
            self.house_use = self.group_booking.house_use
            self.complementary = self.group_booking.complimentary
            self.payment_type = self.group_booking.payment_type

            
            self.complementary_codes = self.group_booking.complimentary_codes.id if self.group_booking.complimentary_codes else False
            self.house_use_codes = self.group_booking.house_use_codes_.id if self.group_booking.house_use_codes_ else False
            if self.group_booking.company and self.group_booking.company.is_vip:
                self.vip = True
                self.vip_code = self.group_booking.company.vip_code.id if self.group_booking.company.vip_code else False
            else:
                self.vip = False
                self.vip_code = False

            self.is_agent = self.group_booking.is_grp_company
            if self.group_booking.company:
                self.partner_id = self.group_booking.company.id
            else:
                self.partner_id = False  # Reset partner_id if no company is set

    agent = fields.Many2one('agent.agent', string="Agent",
                            help="Agent associated with this booking", tracking=True)
    is_vip = fields.Boolean(related='partner_id.is_vip',
                            string="IS VIP", store=True,
                            tracking=True)

    allow_profile_change = fields.Boolean(
        related='group_booking.allow_profile_change',
        string='Allow changing profile data in the reservation form?',
        readonly=True,
        tracking=True
    )


    company_id = fields.Many2one('res.company', string="Hotel",
                                 help="Choose the Hotel",
                                 index=True,
                                 default=lambda self: self.env.company,
                                 readonly=True)

    is_agent = fields.Boolean(string='Is Company')
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=False
        
    )

    company_ids_ = fields.Many2many(
        'res.partner',
        compute='_compute_company_ids',
        store=False
        )

    def _compute_company_ids(self):
        for rec in self:
            companies = self.env['res.company'].search([]).mapped('partner_id').ids
            rec.company_ids_ = companies


    
    @api.onchange('is_agent')
    def _onchange_is_agent(self):
        # (Optional) Clear the previously selected partner:
        # self.partner_id = False
        
        # Gather partner IDs used by Odoo companies
        company_partner_ids = self.env['res.company'].search([]).mapped('partner_id').ids
        
        # Return a domain excluding those company-partner IDs
        return {
            'domain': {
                'partner_id': [
                    ('is_company', '=', self.is_agent),
                    ('id', 'not in', company_partner_ids),
                ]
            }
        }

    reference_contact_ = fields.Char(string=_('Contact Reference'))

    @api.onchange('partner_id')
    def _onchange_customer(self):
        if self.group_booking:
            return

        if self.partner_id:
            self.nationality = self.partner_id.nationality.id
            self.source_of_business = self.partner_id.source_of_business.id
            self.market_segment = self.partner_id.market_segments.id

            # Fetch the rate_code and meal_pattern from partner.detail based on partner_id and current company
            partner_detail = self.env['partner.details'].search([
                ('partner_id', '=', self.partner_id.id),
                ('partner_company_id', '=', self.env.company.id)  # Ensure it matches the current company
            ], limit=1)

            if partner_detail:
                self.rate_code = partner_detail.rate_code.id
                self.meal_pattern = partner_detail.meal_pattern.id
            else:
                self.rate_code = False
                self.meal_pattern = False

            # Set VIP details
            if self.partner_id.is_vip:
                self.vip = True
                self.vip_code = self.partner_id.vip_code.id if self.partner_id.vip_code else False
            else:
                self.vip = False
                self.vip_code = False

    date_order = fields.Datetime(string='Order Date', required=True, default=lambda self: self.env.company.system_date)

    @api.onchange('company_id')
    def _onchange_company_id_date_order(self):
        if self.company_id:
            self.date_order = self.company_id.system_date

    search_done = fields.Boolean(string="Search Done", default=False)

    def _check_room_availability(self, checkout_date):
        query = self._get_room_search_query()
        # Construct the parameters for the SQL
        params = {
            'company_id': self.env.company.id,
            'from_date': self.checkin_date,
            'to_date': checkout_date,
            'room_count': self.room_count,
            'room_type_id': self.hotel_room_type and self.hotel_room_type.id or None,
        }

        # Execute the query
        self.env.cr.execute(query, params)
        results = self.env.cr.dictfetchall()

        for room in results:
            if room.get('min_free_to_sell', 0) == 0:
                # Raise a ValidationError if no rooms are available
                raise ValidationError(f"No available rooms for {room['room_type_name']} from {self.checkin_date} to {checkout_date}.")
        
        if results:
            print("Available rooms from")
            for room in results:
                print("room", room)
        else:
            raise ValidationError(f"No available rooms from {self.checkin_date} to {checkout_date}.")


    def write(self, vals):
        if 'hotel_room_type' in vals and not vals.get('hotel_room_type'):
            raise ValidationError(_("Room Type cannot be empty."))
        self.check_room_meal_validation(vals, True)
        for record in self:
            if record.state == 'confirmed':
                protected_fields = [
                    'partner_id', 'nationality', 'source_of_business',
                    'market_segment', 'rate_code', 'meal_pattern'
                ]
                # Friendly display names
                field_labels = {
                    'partner_id': 'Contact',
                    'nationality': 'Nationality',
                    'source_of_business': 'Source of Business',
                    'market_segment': 'Market Segment',
                    'rate_code': 'Rate Code',
                    'meal_pattern': 'Meal Pattern'
                }
                for field in protected_fields:
                    if field in vals and not vals.get(field):
                        label = field_labels.get(field, field.replace('_', ' ').title())
                        raise ValidationError(_("You cannot remove the field %s after confirmation.") % label)
        
        if 'checkout_date' in vals:

            if self.state in ['check_in', 'block']:
                new_checkout_date = vals['checkout_date']
                current_checkout_date = self.checkout_date  # Existing checkout date
                if isinstance(new_checkout_date, str):
                    new_checkout_date = fields.Date.from_string(new_checkout_date)
                elif isinstance(new_checkout_date, datetime):
                    new_checkout_date = new_checkout_date.date()
                if isinstance(current_checkout_date, datetime):
                    current_checkout_date = current_checkout_date.date()
                
                
                # Only call the availability check if the new checkout date is later than the current one
                if new_checkout_date > current_checkout_date:
                    try:
                        if 'checkin_date' in vals:
                            self._check_checkout_availability(new_checkout_date, True)
                        else:
                            self._check_checkout_availability(new_checkout_date, False)
                    except ValidationError as e:
                        # Show the error to the user or handle accordingly
                        raise e
                    line_ids = self.room_line_ids.ids
                    if line_ids:
                        _logger.debug("  SQL‑updating %d lines of booking", len(line_ids))
                        self.env.cr.execute("""
                                            UPDATE room_booking_line
                                            SET checkout_date = %s
                                            WHERE id IN %s
                                        """, (new_checkout_date, tuple(line_ids)))
                        _logger.debug("  Done updating room_booking_line dates")

                print('line 3698',new_checkout_date,current_checkout_date)
            if self.state == 'confirmed':
                new_checkin = vals.get('checkin_date', self.checkin_date)  # Get new check-in date
                new_checkout = vals['checkout_date']
                self.check_confirmed_availability_for_confirmed(self.id, new_checkin, new_checkout)
                line_ids = self.room_line_ids.ids
                if line_ids:
                    _logger.debug("  SQL‑updating %d lines of booking", len(line_ids))
                    self.env.cr.execute("""
                        UPDATE room_booking_line
                        SET checkin_date  = %s,
                            checkout_date = %s
                        WHERE id IN %s
                    """, (new_checkin, new_checkout, tuple(line_ids)))
                    _logger.debug("  Done updating room_booking_line dates")

        

        if 'checkin_date' in vals:
            if self.state == 'block':
                new_checkin_date = vals['checkin_date']
                _logger.debug("new checkin date:",new_checkin_date)
                try:
                    self._check_checkin_availability(new_checkin_date)
                except ValidationError as e:
                    # Show the error to the user or handle accordingly
                    raise e
            if self.state == 'confirmed':
                # Call the function for confirmed state when checkin_date changes
                new_checkin = vals['checkin_date']
                new_checkout = vals.get('checkout_date', self.checkout_date)  # Default to existing checkout_date
                # print("Line 2641 new_checkin", new_checkin, "new_checkout", new_checkout)
                self.check_confirmed_availability_for_confirmed(self.id, new_checkin, new_checkout)
        if 'company_id' in vals:
            company = self.env['res.company'].browse(vals['company_id'])
            if 'checkin_date' not in vals:  # Only update if not explicitly provided
                vals['checkin_date'] = company.system_date
        
        if 'active' in vals and vals['active'] is False:
            res = super(RoomBooking, self).write(vals)
            return res

        if 'room_count' in vals and vals['room_count'] <= 0:
            raise ValidationError(_("Room count cannot be zero or less. Please select at least one room.")
                )
                
        if 'adult_count' in vals and vals['adult_count'] <= 0:
            raise ValidationError(
                "Adult count cannot be zero or less. Please select at least one adult.")

        if 'child_count' in vals and vals['child_count'] < 0:
            raise ValidationError("Child count cannot be less than zero.")

        if 'checkin_date' in vals and not vals['checkin_date']:
            raise ValidationError(_("Check-In Date is required and cannot be empty."))

        if 'checkout_date' in vals and not vals['checkout_date']:
            raise ValidationError(_("Check-Out Date is required and cannot be empty."))
        
        
        if 'checkin_date' in vals or 'checkout_date' in vals:
            for booking in self:
                if 'checkin_date' in vals:
                    updated_checkin_date = vals.get('checkin_date', booking.checkin_date)
                else:
                    updated_checkin_date = vals.get('checkin_date', self.checkout_date)
                updated_checkout_date = vals.get('checkout_date', booking.checkout_date)
                if booking.state == 'block' and booking.room_line_ids:
                    for line in booking.room_line_ids:
                        overlapping_bookings = self.env['room.booking.line'].search([
                            ('room_id', '=', line.room_id.id),
                            ('id', '!=', line.id),  # Exclude current line
                            ('state', '=', 'block'),  # You can also include other active states like 'confirmed'
                            ('checkin_date', '<', updated_checkout_date),
                            ('checkout_date', '>', updated_checkin_date)
                        ])
        

                        updated_checkout_date = (
                            updated_checkout_date if isinstance(updated_checkout_date, date)
                            else fields.Date.from_string(updated_checkout_date)
                        )
                        updated_checkin_date = (
                            updated_checkin_date if isinstance(updated_checkin_date, date)
                            else fields.Date.from_string(updated_checkin_date)
                        )
                        

                        filtered_overlaps = overlapping_bookings.filtered(
                            lambda l: not (
                                (l.booking_id.checkin_date.date() and l.booking_id.checkin_date.date() != updated_checkout_date)
                                or
                                (l.booking_id.checkout_date.date() and l.booking_id.checkout_date.date() != updated_checkin_date)
                            )
                        )
                        if filtered_overlaps:
                            msg = _("Room %s is already booked for the selected date range.")
                            raise UserError(msg % line.room_id.name)

                    # No conflicts found, update the dates
                    booking.room_line_ids.write({
                        'checkin_date': vals.get('checkin_date', self.checkin_date),
                        'checkout_date': updated_checkout_date
                    })

        
        state_changed = 'state' in vals and vals['state'] != self.state

        res = super(RoomBooking, self).write(vals)

        if state_changed:
            new_state = vals.get('state')
            get_sys_date = self.env.company.system_date.date() 
            current_time = datetime.now().time()
            get_sys_date = datetime.combine(get_sys_date, current_time)
            for record in self:
                for line in record.room_line_ids:
                    self.env['room.booking.line.status'].create({
                        'booking_line_id': line.id,
                        'status': new_state,
                        # 'change_time': fields.Datetime.now(),
                        'change_time': get_sys_date,
                    })
        room_line_count = self.env['room.booking.line'].search_count([
            # Replace with the correct relation field for room lines
            ('booking_id', '=', self.id)
        ])
        if 'state' in vals and 'parent_booking_id' in vals and 'parent_booking_name' in vals and room_line_count > 1:
            # Check if there is more than one room line and remove the others
            room_lines = self.env['room.booking.line'].search([
                # Correct relation field
                ('booking_id', '=', vals.get('parent_booking_id'))
            ], order='counter asc')
            # Get the count of the lines in the sorted order
            room_line_count = len(room_lines)
            final_room_line = room_lines[room_line_count - 1]
            if room_line_count > 1:
                # Unlink all but the last record
                # Iterate over all but the last record
                for ctr in range(room_line_count - 1):
                    room_lines[ctr].unlink()
                # vals['room_count'] = 1
                res = super(RoomBooking, self).write({'room_count': 1})

                adult_lines = self.env['reservation.adult'].search([
                    # Match parent booking ID
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)  # Exclude matching counter value
                ], order='room_sequence asc')
                # adult_lines.write({'room_sequence': final_room_line.counter})
                adult_count = len(adult_lines)
                if adult_count > 1:
                    # for ctr in range(1 * self.adult_count, adult_count):
                    for ctr in range(adult_count - self.adult_count):
                        adult_lines[ctr].unlink()

                adult_lines = self.env['reservation.adult'].search(
                    [('reservation_id', '=', vals.get('parent_booking_id')),
                     # ('room_sequence', '!=', final_room_line.counter)  # Exclude matching counter value
                     ], order='room_sequence asc')
                adult_count = len(adult_lines)

                for ctr in range(self.adult_count):
                    if ctr < len(adult_lines):
                        # Update existing record
                        record = adult_lines[ctr]
                        if record.exists():
                            if final_room_line.counter is not None:
                                record.write(
                                    {'room_sequence': final_room_line.counter})
                            else:
                                print("final_room_line.counter is not set.")
                        else:
                            print(
                                f"Record at index {ctr} does not exist in adult_lines.")

                child_lines = self.env['reservation.child'].search([
                    # Match parent booking ID
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)  # Exclude matching counter value
                ], order='room_sequence asc')
                # adult_lines.write({'room_sequence': final_room_line.counter})
                child_count = len(child_lines)
                if child_count > 1:
                    # for ctr in range(1 * self.adult_count, adult_count):
                    for ctr in range(child_count - self.child_count):
                        child_lines[ctr].unlink()

                child_lines = self.env['reservation.child'].search([
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)# Correct relation field
                ], order='room_sequence asc')
                # child_count = len(child_lines)

                for ctr in range(self.child_count):
                    if ctr < len(child_lines):
                        # Update existing record
                        record = child_lines[ctr]
                        if record.exists():
                            if final_room_line.counter is not None:
                                record.write(
                                    {'room_sequence': final_room_line.counter})
                            else:
                                print("final_room_line.counter is not set.")
                        else:
                            print(
                                f"Record at index {ctr} does not exist in child_lines.")

                infant_lines = self.env['reservation.infant'].search([
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)
                ], order='room_sequence asc')
                infant_count = len(infant_lines)
                if infant_count > 1:
                    for ctr in range(infant_count - self.infant_count):
                        infant_lines[ctr].unlink()

                infant_lines = self.env['reservation.infant'].search([
                    ('reservation_id', '=', vals.get('parent_booking_id')),
                    # ('room_sequence', '!=', final_room_line.counter)
                ], order='room_sequence asc')
                # infant_count = len(infant_lines)
                for ctr in range(self.infant_count):
                    if ctr < len(infant_lines):
                        # Update existing record
                        record = infant_lines[ctr]
                        if record.exists():
                            if final_room_line.counter is not None:
                                record.write(
                                    {'room_sequence': final_room_line.counter})
                            else:
                                print("final_room_line.counter is not set.")
                        else:
                            print(
                                f"Record at index {ctr} does not exist in infant_lines.")

                for adult in self.adult_ids:
                    if final_room_line:
                        adult.room_id = final_room_line.room_id.id
                        self.hotel_room_type = final_room_line.hotel_room_type.id
                for child in self.child_ids:
                    if final_room_line:
                        child.room_id = final_room_line.room_id.id

                for infant in self.infant_ids:
                    if final_room_line:
                        infant.room_id = final_room_line.room_id.id

                # Return window action to refresh the view
                return {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                }
        return res

    
    is_checkin = fields.Boolean(default=False, string="Is Checkin",
                                help="sets to True if the room is occupied")
    maintenance_request_sent = fields.Boolean(default=False,
                                              string="Maintenance Request sent"
                                                     "or Not",
                                              help="sets to True if the "
                                                   "maintenance request send "
                                                   "once", tracking=True)

    checkin_date = fields.Datetime(string="Check In",
                                #    default=lambda self: self.env.user.company_id.system_date.date() + datetime.now().time(),
                                default=lambda self: self.env.user.company_id.system_date.replace(hour=0, minute=0, second=0, microsecond=0),
                                   #    default=lambda self: fields.Datetime.now(),
                                   help="Date of Checkin", required=True, tracking=True)

    # default=fields.Datetime.now()
    checkout_date = fields.Datetime(string="Check Out",
                                    help="Date of Checkout", required=True, tracking=True)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """Update checkin_date based on the new company's system_date."""
        if self.company_id:
            self.checkin_date = self.company_id.system_date.replace(hour=0, minute=0, second=0, microsecond=0)


    no_of_nights = fields.Integer(
        string="No of Nights",
        compute="_compute_no_of_nights",
        inverse="_inverse_no_of_nights",
        default=1,
        store=False,
        # readonly=False,  # so the user can edit it if you want to allow that
    )


    @api.depends('checkin_date', 'checkout_date')
    def _compute_no_of_nights(self):
        for rec in self:
            if rec.checkin_date and rec.checkout_date:
                # Convert to date objects so time of day is ignored
                in_date = fields.Date.to_date(rec.checkin_date)
                out_date = fields.Date.to_date(rec.checkout_date)
                diff_days = (out_date - in_date).days
                rec.no_of_nights = diff_days if diff_days >= 0 else 0
            else:
                rec.no_of_nights = 0


    def _inverse_no_of_nights(self):
        """
        When a user edits no_of_nights directly, recompute checkout_date
        based on checkin_date + no_of_nights days.
        If no_of_nights is 0, set checkout_date to 2 hours after checkin_date.
        """
        for rec in self:
            if rec.checkin_date and rec.no_of_nights is not None:
                if rec.no_of_nights > 0:
                    # Normal case: Add no_of_nights days
                    rec.checkout_date = rec.checkin_date + timedelta(days=rec.no_of_nights)
                else:
                    # If no_of_nights is 0, set checkout_date to 2 hours after checkin_date
                    rec.checkout_date = rec.checkin_date + timedelta(hours=2)
    
    
    @api.onchange('checkin_date', 'no_of_nights')
    def _onchange_checkin_date_or_no_of_nights(self):
        if self.state == 'block':
            return
        if self.checkin_date:
            # Convert current time to user's timezone
            current_time = fields.Datetime.context_timestamp(self, fields.Datetime.now())
            buffer_time = current_time - timedelta(minutes=10)
        
            # Convert checkin_date to user's timezone for comparison
            checkin_user_tz = fields.Datetime.context_timestamp(
                self, self.checkin_date)

            # Validate no_of_nights field
            # if not self.no_of_nights or self.no_of_nights < 0:
            # if self.no_of_nights is not None and self.no_of_nights < 0:
            #     # self.no_of_nights = 1
            #     return {
            #         'warning': {
            #             'title': 'Invalid Number of Nights',
            #             'message': "Number of nights must be at least 0."
            #         }
            #     }
            if self.no_of_nights == 0:
                # If no_of_nights is 0, add 30 minutes to checkin_date
                self.checkout_date = self.checkin_date + timedelta(minutes=30)
            else:
                # Calculate checkout_date based on checkin_date and no_of_nights
                self.checkout_date = self.checkin_date + \
                                     timedelta(days=self.no_of_nights)
                
    @api.onchange('no_of_nights')
    def _check_no_of_nights(self):
        for record in self:
            if record.no_of_nights is not None and record.no_of_nights < 0:
                raise ValidationError("Number of nights must be 0 or more.")

    
    
    def _adjust_checkout_date(self):
        """Adjust checkout_date to one day after checkin_date if invalid."""
        if self.checkin_date:
            self.checkout_date = self.checkin_date + timedelta(days=1)

    hotel_policy = fields.Selection([("prepaid", "On Booking"),
                                     ("manual", "On Check In"),
                                     ("picking", "On Checkout"),
                                     ],
                                    default="manual", string="Hotel Policy",
                                    help="Hotel policy for payment that "
                                         "either the guest has to pay at "
                                         "booking time, check-in "
                                         "or check-out time.", tracking=True)
    duration = fields.Integer(string="Duration in Days",
                              help="Number of days which will automatically "
                                   "count from the check-in and check-out "
                                   "date.", )
    invoice_button_visible = fields.Boolean(string='Invoice Button Display',
                                            help="Invoice button will be "
                                                 "visible if this button is "
                                                 "True")
    invoice_status = fields.Selection(
        selection=[('no_invoice', 'Nothing To Invoice'),
                   ('to_invoice', 'To Invoice'),
                   ('invoiced', 'Invoiced'),
                   ], string="Invoice Status",
        help="Status of the Invoice",
        default='no_invoice', tracking=True)
    hotel_invoice_id = fields.Many2one("account.move",
                                       string="Invoice",
                                       help="Indicates the invoice",
                                       copy=False)
    duration_visible = fields.Float(string="Duration",
                                    help="A dummy field for Duration")
    need_service = fields.Boolean(default=False, string="Need Service",
                                  help="Check if a Service to be added with"
                                       " the Booking")
    need_fleet = fields.Boolean(default=False, string="Need Vehicle",
                                help="Check if a Fleet to be"
                                     " added with the Booking")
    need_food = fields.Boolean(default=False, string="Need Food",
                               help="Check if a Food to be added with"
                                    " the Booking")
    need_event = fields.Boolean(default=False, string="Need Event",
                                help="Check if a Event to be added with"
                                     " the Booking")
    service_line_ids = fields.One2many("service.booking.line",
                                       "booking_id",
                                       string="Service",
                                       help="Hotel services details provided to"
                                            "Customer and it will included in "
                                            "the main Invoice.")  #
    event_line_ids = fields.One2many("event.booking.line",
                                     'booking_id',
                                     string="Event",
                                     help="Hotel event reservation detail.")  #
    vehicle_line_ids = fields.One2many("fleet.booking.line",
                                       "booking_id",
                                       string="Vehicle",
                                       help="Hotel fleet reservation detail.")  #
    room_line_ids = fields.One2many("room.booking.line",
                                    "booking_id", string="Room",
                                    help="Hotel room reservation detail.")  #

    
    food_order_line_ids = fields.One2many("food.booking.line",
                                          "booking_id",
                                          string='Food',
                                          help="Food details provided"
                                               " to Customer and"
                                               " it will included in the "
                                               "main invoice.", )  #
    state = fields.Selection(selection=[
        ('not_confirmed', 'Not Confirmed'),
        # ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('waiting', 'Waiting List'),
        ('no_show', 'No Show'),
        ('block', 'Block'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('reserved', 'Reserved')
    ], string='State', help="State of the Booking", default='not_confirmed', tracking=True)

    reservation_status_id = fields.Many2one(
        'reservation.status.code',
        string="Reservation Status",
        help="Select the reservation status for this booking."
    )


    reservation_status_count_as = fields.Selection(
        selection=[
            ('not_confirmed', 'Not Confirmed'),
            ('confirmed', 'Confirmed'),
            ('wait_list', 'Wait List'),
            # ('tentative', 'Tentative'),
            ('release', 'Release'),
            ('cancelled', 'Cancelled'),
            ('other', 'Other'),
        ],
        string="Reservation Count As",
        readonly=True,
        store=True,
        compute='_compute_reservation_status_count_as', tracking=True)

    @api.depends('state', 'reservation_status_id')
    def _compute_reservation_status_count_as(self):
        """Automatically set reservation_status_count_as based on state and reservation_status_id."""
        state_mapping = {
            'not_confirmed': 'not_confirmed',
            'confirmed': 'confirmed',
            'waiting': 'wait_list',
            'block': 'confirmed',
            'no_show': 'confirmed',
            'check_in': 'confirmed',
            'check_out': 'confirmed',
            'done': 'confirmed',
            'cancel': 'cancelled',
            'reserved': 'wait_list',
        }
        for record in self:
            # First, map based on state.
            state_based_value = state_mapping.get(
                record.state, 'confirmed')  # Default to 'confirmed'

            # Then, prioritize the related reservation status if it exists.
            if record.reservation_status_id and record.reservation_status_id.count_as:
                record.reservation_status_count_as = record.reservation_status_id.count_as
            else:
                record.reservation_status_count_as = state_based_value

        

    @api.onchange('no_show_')
    def _onchange_no_show(self):
        """Update child room lines to 'no_show' when parent is marked as 'No Show'."""
        if self.no_show_:
            for line in self.room_line_ids:
                if line.state == 'block':
                    line.state = 'no_show'

    show_confirm_button = fields.Boolean(string="Confirm Button")
    show_cancel_button = fields.Boolean(string="Cancel Button")

    hotel_room_type = fields.Many2one(
        'room.type', string="Room Type",
        domain=lambda self: [
        ('obsolete', '=', False),
        ('id', 'in', self.env['hotel.inventory'].search([
            ('company_id', '=', self.env.company.id),
        ]).mapped('room_type.id'))
        ],tracking=True)

    
    def action_confirm_booking(self):
        # 1) Ensure all selected records share the same state
        states = set(self.mapped('state'))
        if len(states) > 1:
            raise ValidationError(_("Please select records with the same state."))

        # 2) Only allow 'not_confirmed' or 'no_show'
        state = states.pop()
        allowed = {'not_confirmed', 'no_show'}
        if state not in allowed:
            raise ValidationError(_(
                "Please select only records in the Not Confirmed or No Show state to confirm."
            ))

        # 3) Mandatory-field checks
        for rec in self:
            if not rec.nationality:
                raise ValidationError(
                    _("The field 'Nationality' is required for record '%s'. Please fill it before confirming.") % rec.name
                )
            if not rec.source_of_business:
                raise ValidationError(
                    _("The field 'Source of Business' is required for record '%s'. Please fill it before confirming.") % rec.name
                )
            if not rec.market_segment:
                raise ValidationError(
                    _("The field 'Market Segment' is required for record '%s'. Please fill it before confirming.") % rec.name
                )
            if not rec.rate_code:
                raise ValidationError(
                    _("The field 'Rate Code' is required for record '%s'. Please fill it before confirming.") % rec.name
                )
            if not rec.meal_pattern:
                raise ValidationError(
                    _("The field 'Meal Pattern' is required for record '%s'. Please fill it before confirming.") % rec.name
                )

        # 4) Confirm logic for both parent and children
        state_changed = False
        for booking in self:
            # Confirm the booking itself if in allowed state
            if booking.state in allowed:
                booking.action_split_rooms()
                for res in booking.availability_results:
                    res.available_rooms -= res.rooms_reserved
                booking.write({'state': 'confirmed'})
                state_changed = True

            # Then confirm any child bookings
            children = self.search([('parent_booking_name', '=', booking.name)])
            for child in children:
                if child.state in allowed:
                    child.action_split_rooms()
                    for res in child.availability_results:
                        res.available_rooms -= res.rooms_reserved
                    child.write({'state': 'confirmed'})
                    state_changed = True

        # 5) Notify success or raise error
        if state_changed:
            dashboard_data = self.retrieve_dashboard()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _("Booking(s) confirmed successfully!"),
                    'next': {'type': 'ir.actions.act_window_close'},
                    'dashboard_data': dashboard_data,
                },
            }
        else:
            raise ValidationError(_(
                "No bookings were confirmed. Please ensure the state is 'Not Confirmed' or 'No Show' before confirming."
            ))

    
    def action_no_show_tree(self):
        """Convert parent + children *block* bookings to **no_show**
        (only on the check‑in date) and wipe related availability lines."""
        today = self.env.company.system_date.date()
        state_changed = False

        for parent in self:
            # ---------------- Children ----------------
            children = self.search([
                ("parent_booking_name", "=", parent.name)
            ])
            for child in children:
                if child.state == "block":
                    child._to_no_show(today)
                    state_changed = True

            # ---------------- Parent ------------------
            if parent.state == "block":
                parent._to_no_show(today)
                state_changed = True

        # ---------------- UI feedback ---------------
        if state_changed:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "type": "success",
                    "message": _("Booking(s) marked as 'No Show' successfully!"),
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }
        raise ValidationError(_(
            "Nothing was marked as 'No Show'.Bookings must be in state 'block' and today must be the Check In date."
        ))

    
    
    def _to_no_show(self, today):
        self.ensure_one()

        # Date guard
        if fields.Date.to_date(self.checkin_date) != today:
            raise ValidationError(_(
                "Booking %s: No Show can only be done on the check-in date."
            ) % self.name)

        # ---- 1) Release rooms, update state_, insert status history ----------------
        if self.room_line_ids:
            room_line_ids = self.room_line_ids.ids
            _logger.debug("Room line IDs to process: %s", room_line_ids)

            # Bulk clear room assignments and set state_
            self.env.cr.execute(
                """
                UPDATE room_booking_line
                SET room_id = NULL,
                    state_  = 'no_show'
                WHERE id = ANY(%s)
                """,
                (room_line_ids,)
            )

            # Insert a no_show entry in the status history for each line
            for line_id in room_line_ids:
                system_date = self.env.company.system_date.date()
                current_time = datetime.now().strftime('%H:%M:%S')

                # Combine date and time
                change_time = f"{system_date} {current_time}"
                self.env.cr.execute(
                    """
                    INSERT INTO room_booking_line_status (
                        booking_line_id,
                        create_uid, write_uid,
                        status,
                        change_time,
                        create_date, write_date
                    ) VALUES (%s, %s, %s, 'no_show', %s, NOW(), NOW())
                    """,
                    (line_id, self.env.uid, self.env.uid, change_time)
                )

        # ---- 2) Delete availability result rows -------------------------
        _logger.debug("Deleting availability lines for booking: %s", self.name)
        self.env.cr.execute(
            """
            DELETE FROM room_availability_result
            WHERE room_booking_id = %s
            """,
            (self.id,)
        )

        # ---- 3) Switch booking state ------------------------------------
        _logger.debug("Updating state to 'no_show' for booking %s", self.name)
        self.env.cr.execute(
            """
            UPDATE room_booking
            SET state = 'no_show'
            WHERE id = %s
            """,
            (self.id,)
        )

        if self.room_line_ids:
            _logger.debug("Re-flagging room lines for booking %s", self.name)
            self.env.cr.execute(
                """
                UPDATE room_booking_line
                SET state_ = 'no_show'
                WHERE booking_id = %s
                """,
                (self.id,)
            )
            _logger.debug("Room lines updated to 'no_show' for booking %s", self.name)


    def action_cancel_booking(self):
        # 1) Sanity checks
        states = self.mapped('state')
        if len(set(states)) > 1:
            raise ValidationError(_("Please select records with the same state."))
        allowed = {'not_confirmed', 'confirmed', 'waiting'}
        bad = self.filtered(lambda b: b.state not in allowed)
        if bad:
            state_translation = {
                'cancel': 'مُلْغى',
                'check_out': 'مغادرة',
                'check_in': 'وصول',
                'confirmed': 'مؤكد',
                'not_confirmed': 'غير مؤكد',
                'waiting': 'في الانتظار',
                'block': 'مخصص',
                'no_show': 'عدم الحضور',
            }
            state_arabic = state_translation.get(bad[0].state, bad[0].state)
            raise ValidationError(
                _("You cannot cancel bookings in state %s.") % state_arabic)

        # 2) For each booking in the selection...
        for booking in self:
            # 2a) If it's a parent, cancel its children too
            children = self.search([
                ('parent_booking_name', '=', booking.name),
                ('state', 'in', list(allowed))
            ])
            if children:
                children.write({'state': 'cancel'})
                # Free up rooms on those children
                for line in children.mapped('room_line_ids'):
                    line.room_id.write({
                        'status': 'available',
                        'is_room_avail': True,
                    })
                # Set 'state_' to 'cancel' for room booking lines of children
                self.env.cr.execute("""
                    UPDATE room_booking_line
                    SET state_ = 'cancel'
                    WHERE booking_id IN %s
                """, (tuple(children.ids),))

            # 2b) Now cancel the booking itself
            booking.write({'state': 'cancel'})
            for line in booking.room_line_ids:
                line.room_id.write({
                    'status': 'available',
                    'is_room_avail': True,
                })
            
            # Set 'state_' to 'cancel' for room booking lines of the current booking
            self.env.cr.execute("""
                UPDATE room_booking_line
                SET state_ = 'cancel'
                WHERE booking_id = %s
            """, (booking.id,))

        # 3) Commit & refresh dashboard
        self.env.cr.commit()
        data = self.retrieve_dashboard()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking(s) cancelled successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
                'dashboard_data': data,
            }
        }


    def action_checkin_booking(self):
        # today = datetime.now().date()
        today = self.env.company.system_date.date()
        all_bookings = self
        

        # -------- Ensure same room number on same day shouldn't check-in twice --------
        for booking in all_bookings:
            for line in booking.room_line_ids:
                overlapping_reservation = self.env['room.booking.line'].search([
                    ('room_id', '=', line.room_id.id),
                    ('id', '!=', line.id),
                    ('state_', '=', 'check_in'),
                    ('checkin_date', '<=', booking.checkout_date),
                    ('checkout_date', '>=', booking.checkin_date),
                ], limit=1)

                if overlapping_reservation:
                    raise ValidationError(_(
                        "Selected room number %s is already checked in for this date. Please change the room number to do check-in."
                    ) % (line.room_id.name))



        for booking in all_bookings:
            if len(booking.room_line_ids) > 1:
                continue
            if booking.state != 'block':
                raise ValidationError(
                    _("All selected bookings must be in the block state to proceed with check-in."))
            if booking.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot check-in  booking with a check-in date in the past."))

        future_bookings = all_bookings.filtered(
            lambda b: fields.Date.to_date(b.checkin_date) > today)

        if future_bookings:
            # Return wizard if any booking is in the future
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'booking.checkin.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_booking_ids': future_bookings.mapped('id'),
                }
            }

        # If no future bookings, continue directly
        # return self._perform_bulk_checkin(all_bookings, today)
        self._perform_bulk_checkin(all_bookings, today)
        self.env.cr.commit()

        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _("Booking Checked In Successfully!"),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

    def _perform_bulk_checkin(self, all_bookings, today):
        # today = datetime.now()
        today = self.env.company.system_date.date()
        state_changed = False
        for booking in all_bookings:
            if len(booking.room_line_ids) > 1:
                continue

            booking._perform_checkin()
            booking._log_room_line_status(
                line_ids=booking.room_line_ids.ids,
                status='check_in'
            )
            state_changed = True

        # Only retrieve dashboard counts and display notification if state changed
        if state_changed:
            dashboard_data = self.retrieve_dashboard()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _("Booking Checked In Successfully!"),
                    'next': {'type': 'ir.actions.act_window_close'},
                    'dashboard_data': dashboard_data,
                }
            }
        else:
            raise ValidationError(
                _("No bookings were checked in. Please ensure the state is 'block' before checking in."))

    def _perform_checkout(self):
        """Helper method to perform check-out and update room availability."""
        parent_booking_id = self.parent_booking_id.id if self.parent_booking_id else self.id

        system_date_checkout = self.env.company.system_date.date()
        get_current_time = datetime.now().time()

        checkout_datetime = datetime.combine(system_date_checkout, get_current_time)

        # Loop through each room in the room_line_ids
        for room in self.room_line_ids:
            # Update room status to 'available'
            room.room_id.write({
                'status': 'available',
            })
            room.room_id.is_room_avail = True

            # Update the available rooms count and increase rooms_reserved count
            if room.room_id:
                availability_result = self.env['room.availability.result'].search([
                    ('room_booking_id', '=', parent_booking_id)
                ], limit=1)

                if availability_result:
                    # Use room count from the room line or a default value of 1
                    reserved_rooms = room.room_count if hasattr(
                        room, 'room_count') else 1

                    # Increase available_rooms and decrease rooms_reserved
                    availability_result.available_rooms += reserved_rooms
                    availability_result.rooms_reserved -= reserved_rooms

        self.write({"state": "check_out", "checkout_date": checkout_datetime})
        self.room_line_ids.write({"state_": "check_out"})
    
        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking Checked Out Successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


    def action_checkout_booking(self):
        today = self.env.company.system_date.date()
        all_bookings = self

        eligible_bookings = all_bookings.filtered(lambda b: len(b.room_line_ids) <= 1)

        for booking in eligible_bookings:
            if booking.state != 'check_in':
                raise ValidationError(_("All selected bookings must be in the check_in state."))

        future_bookings = eligible_bookings.filtered(
            lambda b: b.checkout_date and fields.Date.to_date(b.checkout_date) > today
        )

        if future_bookings:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'confirm.early.checkout.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_booking_ids': future_bookings.mapped('id'),
                }
            }

        current_time = datetime.now().time()
        current_datetime = datetime.combine(today, current_time)

        cr = self.env.cr
        booking_ids = []
        room_line_ids = []
        move_vals_list = []
        move_map = {}  # booking.id → account.move

        line_vals = []

        for booking in eligible_bookings:
            booking_ids.append(booking.id)
            room_line_ids.extend(booking.room_line_ids.ids)

            # Meal & rate info
            posting_item_meal, _1, _2, _3 = booking.get_meal_rates(booking.meal_pattern.id)
            _a, _b, _c, posting_item_rate, line_posting_items = booking.get_all_prices(booking.checkin_date, booking)

            forecast_lines = [line for line in booking.rate_forecast_ids if line.date == today]
            if not forecast_lines:
                continue  # skip if no forecast lines

            move_vals_list.append({
                'move_type': 'out_invoice',
                'invoice_date': today,
                'partner_id': booking.partner_id.id,
                'ref': booking.name,
                'hotel_booking_id': booking.id,
                'group_booking_name': booking.group_booking.name if booking.group_booking else '',
                'parent_booking_name': booking.parent_booking_name or '',
                'room_numbers': booking.room_ids_display or '',
            })

        # 1️⃣ Create all invoices in one go
        created_moves = self.env['account.move'].create(move_vals_list)

        # 2️⃣ Map invoices to bookings
        for booking, move in zip(eligible_bookings, created_moves):
            move_map[booking.id] = move

        # 3️⃣ Collect all invoice lines in one list
        for booking in eligible_bookings:
            move = move_map.get(booking.id)
            if not move:
                continue

            posting_item_meal, _1, _2, _3 = booking.get_meal_rates(booking.meal_pattern.id)
            _a, _b, _c, posting_item_rate, line_posting_items = booking.get_all_prices(booking.checkin_date, booking)

            for line in booking.rate_forecast_ids.filtered(lambda l: l.date == today):
                if line.rate and line.rate > 0:
                    line_vals.append({
                        'posting_item_id': posting_item_rate,
                        'posting_description': 'Rate',
                        'posting_default_value': line.rate,
                        'move_id': move.id,
                    })
                if line.meals and line.meals > 0:
                    line_vals.append({
                        'posting_item_id': posting_item_meal,
                        'posting_description': 'Meal',
                        'posting_default_value': line.meals,
                        'move_id': move.id,
                    })
                if line.packages and line.packages > 0:
                    line_vals.append({
                        'posting_item_id': line_posting_items[-1],
                        'posting_description': 'Package',
                        'posting_default_value': line.packages,
                        'move_id': move.id,
                    })

        # 4️⃣ Create all invoice lines in one go
        if line_vals:
            self.env['account.move.line'].create(line_vals)

        # 5️⃣ Fast SQL updates for booking state and invoice button
        cr.execute("""
            UPDATE room_booking
            SET invoice_status = 'invoiced', state = 'check_out', checkout_date = %s, invoice_button_visible = TRUE
            WHERE id IN %s
        """, (current_datetime, tuple(booking_ids)))

        if room_line_ids:
            lines = self.env['room.booking.line'].browse(room_line_ids)
            to_log = lines.filtered(lambda l: l.state_ == 'check_in').ids
            cr.execute("""
                UPDATE room_booking_line
                SET state_ = 'check_out'
                WHERE id IN %s
            """, (tuple(room_line_ids),))

            if to_log:
                self._log_room_line_status(room_line_ids, status='check_out')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking Checked Out Successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _perform_bulk_checkout(self, all_bookings, today):
        state_changed = False

        for booking in all_bookings:
            if len(booking.room_line_ids) > 1:
                continue

            booking._perform_checkout()
            booking.room_line_ids.write({"state_": "check_out"})
            state_changed = True

        # Display notification if any state changed
        if state_changed:
            dashboard_data = self.retrieve_dashboard()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _t("Booking Checked Out Successfully!"),
                    'next': {'type': 'ir.actions.act_window_close'},
                    'dashboard_data': dashboard_data,
                }
            }
        else:
            raise ValidationError(
                _("No bookings were checked out. Please ensure the state is 'check_in' before checking out."))

    visible_states = fields.Char(compute='_compute_visible_states')

    @api.depends('state')
    def _compute_visible_states(self):
        for record in self:
            if record.state == 'not_confirmed':
                record.visible_states = 'not_confirmed,confirmed,cancel'
            elif record.state == 'confirmed':
                record.visible_states = 'confirmed,check_in,check_out,no_show'
            else:
                record.visible_states = 'not_confirmed,confirmed,waiting,no_show,block,check_in,check_out,done'

    room_type_name = fields.Many2one('room.type', string='Room Type Name')

    def action_unconfirm(self):
        self.ensure_one()
        self.action_clear_rooms()
        """Set the booking back to 'not_confirmed' state from 'confirmed' or 'block'"""
        for record in self:
            if record.state in ['block', 'confirmed', 'waiting', 'cancel']:
                record.state = 'not_confirmed'

    def _open_confirm_wizard(self, title, message, block_line=False):
        self.ensure_one()
        return {
            'name': "",
            'type': 'ir.actions.act_window',
            'res_model': 'confirm.booking.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_message': message,
                'default_line_id': block_line.id if block_line else False,
                'default_booking_id': self.id,
            },
        }


    def action_confirm(self):
        # today = datetime.now().date()
        bookings = self.sudo()
        today = self.env.company.system_date.date()
        for record in bookings:
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot confirm a booking with a check-in date in the past."))

            if not record.partner_id:
                raise ValidationError(_("The field Contact is required. Please fill it before confirming."))

            if not record.nationality:
                raise ValidationError(_("The field Nationality is required. Please fill it before confirming."))
            if not record.source_of_business:
                raise ValidationError(
                    _("The field Source of Business is required. Please fill it before confirming."))
            if not record.market_segment:
                raise ValidationError(_("The field Market Segment is required. Please fill it before confirming."))
            if not record.rate_code:
                raise ValidationError(_("The field Rate Code is required. Please fill it before confirming."))
            if not record.meal_pattern:
                raise ValidationError(_("The field Meal Pattern is required. Please fill it before confirming."))

            if not record.parent_booking_name:
                # if not record.availability_results:
                if record.state != "no_show" and not record.availability_results:
                    raise ValidationError(_("Search Room is empty. Please search for available rooms before confirming."))

            if not record.room_line_ids:
                record.action_split_rooms()

            # 4) Check if there is any line in block state
            block_line = record.room_line_ids.filtered(lambda l: l.state_ == 'block')
            # if block_line:
            if record.state == 'block' or block_line:
                return record._open_confirm_wizard(
                    _("Confirm Booking"),
                    _("Room number will be released. Do you want to proceed?"),
                    block_line=block_line
                    
                )
            # 5) If we reached here, there is NO line in block state => we can confirm now
            record.state = "confirmed"

            # 6) Adjust availability
            for search_result in record.availability_results:
                search_result.available_rooms -= search_result.rooms_reserved

        # return True
        return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _("Booking(s) confirmed successfully!"),
                    'next': {'type': 'ir.actions.act_window_close'},
                    # 'dashboard_data': dashboard_data,
                },
            }

    
    def action_waiting(self):
        # today = datetime.now().date()
        today = self.env.company.system_date.date()
        for record in self:
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot sent a booking to Waiting List with a check-in date in the past."))
            if not record.availability_results:
                raise UserError(
                    "You have to Search room first then you can Send to Waiting List.")
            record.state = 'waiting'


    def _log_room_line_status(self, line_ids, status):
        """Helper to insert into room_booking_line_status for each line."""
        cr = self.env.cr
        uid = self.env.uid

        # build a timestamp matching your company date + now()
        today = self.env.company.system_date.date()
        now_time = datetime.now().time()
        change_time = datetime.combine(today, now_time)

        for lid in line_ids:
            cr.execute("""
                INSERT INTO room_booking_line_status (
                    booking_line_id,
                    create_uid, write_uid,
                    status,
                    change_time,
                    create_date, write_date
                ) VALUES (
                    %s,    -- booking_line_id
                    %s,    -- create_uid
                    %s,    -- write_uid
                    %s,    -- status
                    %s,    -- change_time
                    NOW(), -- create_date
                    NOW()  -- write_date
                )
            """, (lid, uid, uid, status, change_time))


    def no_show(self):
        """Mark today’s booking as no-show, clear rooms, adjust availability,
        and record a no_show status in room_booking_line_status."""
        # get today’s date from your company’s timezone setting
        current_date = self.env.company.system_date.date()
        today = self.env.company.system_date.date()
        current_time = datetime.now().time()
        get_sys_date = datetime.combine(today, current_time)

        for booking in self:
            # 1) Only allow if checkin_date is today
            if booking.checkin_date.date() != current_date:
                raise UserError(
                    _("The No Show action can only be performed on the current check-in date."))

            booking_id = booking.id
            parent_id = booking.parent_booking_id.id if booking.parent_booking_id else booking_id

            # 2) Load all lines for this booking
            self.env.cr.execute("""
                SELECT id, room_id
                FROM room_booking_line
                WHERE booking_id = %s
                FOR UPDATE
            """, (booking_id,))
            room_lines = self.env.cr.fetchall()  # [(line_id, room_id), ...]

            # 3) Load availability
            self.env.cr.execute("""
                SELECT id, available_rooms, rooms_reserved
                FROM room_availability_result
                WHERE room_booking_id = %s
                LIMIT 1
                FOR UPDATE
            """, (parent_id,))
            avail = self.env.cr.fetchone()

            # 4) If availability exists, adjust counts
            if avail:
                avail_id, avail_rooms, reserved_rooms = avail
                # count only those lines that had a room assigned
                total = sum(1 for _, room in room_lines if room)
                if total > 0:
                    self.env.cr.execute("""
                        UPDATE room_availability_result
                        SET
                          available_rooms = available_rooms + %s,
                          rooms_reserved   = rooms_reserved - %s
                        WHERE id = %s
                    """, (total, total, avail_id))

            # 5) Clear each line, mark no-show, and insert status history
            for line_id, room in room_lines:
                # clear room_id & state_
                self.env.cr.execute("""
                    UPDATE room_booking_line
                    SET
                      room_id = NULL,
                      state_  = 'no_show'
                    WHERE id = %s
                """, (line_id,))

                # insert a record into your status history table
                self.env.cr.execute(""" 
                    INSERT INTO room_booking_line_status (
                    booking_line_id,
                    create_uid, write_uid,
                    status,
                    change_time,
                    create_date, write_date
                    ) VALUES (
                    %s,    -- booking_line_id
                    %s,    -- create_uid
                    %s,    -- write_uid
                    'no_show',
                    %s,    -- change_time (use get_sys_date)
                    NOW(), -- create_date
                    NOW()  -- write_date
                    )
                """, (line_id, self.env.uid, self.env.uid, get_sys_date))

            # 6) Finally, mark the parent booking itself as no_show
            self.env.cr.execute("""
                UPDATE room_booking
                SET state = 'no_show'
                WHERE id = %s
            """, (booking_id,))


    def action_make_reservation(self):
        """Method called by the button to make a reservation and check its status."""
        for record in self:
            # Ensure that only one record is being processed (optional)
            # record.ensure_one()

            # Get necessary data from the current record
            partner_id = record.partner_id.id
            checkin_date = record.checkin_date
            checkout_date = record.checkout_date
            room_type_id = record.room_type_name.id
            num_rooms = record.room_count
            

            try:
                # Call the make_reservation method
                record.make_reservation(
                    partner_id=partner_id,
                    checkin_date=checkin_date,
                    checkout_date=checkout_date,
                    room_type_id=room_type_id,
                    num_rooms=num_rooms
                )
                # Update state and notify user
                record.state = 'confirmed'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Reservation Confirmed',
                        'message': 'Your reservation has been successfully confirmed.',
                        'sticky': False,
                    }
                }
            except exceptions.UserError as e:
                # Handle reservation failure
                record.state = 'waiting'  # Optionally set state to waiting
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Reservation Failed',
                        'message': str(e),
                        'sticky': False,
                    }
                }

    @api.model
    def make_reservation(self, partner_id, checkin_date, checkout_date, room_type_id, num_rooms):
        checkin_date = fields.Datetime.to_datetime(checkin_date)
        checkout_date = fields.Datetime.to_datetime(checkout_date)

        # Step 1: Check room availability
        available_rooms = self._get_available_rooms(
            checkin_date, checkout_date, room_type_id, num_rooms, False)

        if available_rooms and len(available_rooms) >= num_rooms:
            # Step 2: Create booking lines for each room
            for room in available_rooms[:num_rooms]:
                self.env['room.booking.line'].create({
                    'booking_id': self.id,
                    'room_id': room.id,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                })
            # Set state to 'confirmed'
            self.state = 'confirmed'
            return self
        else:
            # Step 3: Add to waiting list
            self.env['room.waiting.list'].create({
                'partner_id': partner_id,
                'checkin_date': checkin_date,
                'checkout_date': checkout_date,
                'room_type_id': room_type_id,
                'num_rooms': num_rooms,
            })
            # Step 4: Set state to 'waiting' and inform the user
            self.state = 'waiting'
            self.message_post(
                body='No rooms available for the selected dates. The reservation has been added to the waiting list.')
            return self

    def _get_available_rooms(self, checkin_date, checkout_date, room_type_id, num_rooms, is_api):
        # Get all rooms of the specified type
        rooms = self.env['hotel.room'].search([
            ('room_type_name', '=', room_type_id),
        ])

        available_rooms = []
        for room in rooms:
            # Check for overlapping bookings
            overlapping_bookings = self.env['room.booking.line'].search([
                ('room_id', '=', room.id),
                ('booking_id.state', 'in', ['confirmed']),
                ('checkin_date', '<', checkout_date),
                ('checkout_date', '>', checkin_date),
            ])
            if not overlapping_bookings:
                available_rooms.append(room)
                if not is_api:
                    if len(available_rooms) >= num_rooms:
                        break
        return available_rooms

    def get_available_rooms_for_hotel_api(self, checkin_date, checkout_date, room_type_id, num_rooms, is_api, hotel_id):
        # Get all rooms of the specified type
        rooms = self.env['hotel.room'].search([
            ('room_type_name', '=', room_type_id),
            ('company_id', '=', hotel_id),
        ])

        available_rooms = []
        for room in rooms:
            # Check for overlapping bookings
            overlapping_bookings = self.env['room.booking.line'].search([
                ('room_id', '=', room.id),
                ('booking_id.state', 'in', ['confirmed']),
                ('booking_id.company_id', '=', hotel_id),
                ('checkin_date', '<', checkout_date),
                ('checkout_date', '>', checkin_date),
            ])
            if not overlapping_bookings:
                available_rooms.append(room)
                if not is_api:
                    if len(available_rooms) >= num_rooms:
                        break
        return available_rooms

    def get_available_rooms_for_api(self, checkin_date, checkout_date, room_type_id, num_rooms, is_api, pax, hotel_id):
        # Get all rooms of the specified type
        rooms = self.env['hotel.room'].search([
            ('room_type_name', '=', room_type_id),
            # ('num_person', '>=', pax),
            ('num_person', '=', pax),
        ])

        available_rooms = []
        for room in rooms:
            # Check for overlapping bookings
            overlapping_bookings = self.env['room.booking.line'].search([
                ('room_id', '=', room.id),
                ('booking_id.state', 'in', ['confirmed']),
                ('booking_id.company_id', '=', hotel_id),
                ('checkin_date', '<', checkout_date),
                ('checkout_date', '>', checkin_date),
            ])
            if not overlapping_bookings:
                available_rooms.append(room)
                if not is_api:
                    if len(available_rooms) >= num_rooms:
                        break
        return available_rooms

    user_id = fields.Many2one(comodel_name='res.partner',
                              string="Address",
                              compute='_compute_user_id',
                              help="Sets the User automatically",
                              required=True,
                              domain="['|', ('company_id', '=', False), "
                                     "('company_id', '=',"
                                     " company_id)]")

    pricelist_id = fields.Many2one(comodel_name='product.pricelist',
                                   string="Pricelist",
                                   compute='_compute_pricelist_id',
                                   store=True, readonly=False,
                                   tracking=1,
                                   help="If you change the pricelist,"
                                        " only newly added lines"
                                        " will be affected.")

    currency_id = fields.Many2one(
        string="Currency", help="This is the Currency used",
        related='pricelist_id.currency_id',
        depends=['pricelist_id.currency_id'],
        tracking=True
    )

    invoice_count = fields.Integer(compute='_compute_invoice_count',
                                   string="Invoice "
                                          "Count",
                                   help="The number of invoices created", tracking=True)

    account_move = fields.Integer(string='Invoice Id',
                                  help="Id of the invoice created")
    amount_untaxed = fields.Monetary(string="Total Untaxed Amount",
                                     help="This indicates the total untaxed "
                                          "amount", store=True,
                                     compute='_compute_amount_untaxed',
                                     tracking=5)
    amount_tax = fields.Monetary(string="Taxes", help="Total Tax Amount",
                                 store=True, compute='_compute_amount_untaxed')
    amount_total = fields.Monetary(string="Total", store=True,
                                   help="The total Amount including Tax",
                                   compute='_compute_amount_untaxed',
                                   tracking=4)
    amount_untaxed_room = fields.Monetary(string="Room Untaxed",
                                          help="Untaxed Amount for Room",
                                          compute='_compute_amount_untaxed',
                                          tracking=5)
    amount_untaxed_food = fields.Monetary(string="Food Untaxed",
                                          help="Untaxed Amount for Food",
                                          compute='_compute_amount_untaxed',
                                          tracking=5)
    amount_untaxed_event = fields.Monetary(string="Event Untaxed",
                                           help="Untaxed Amount for Event",
                                           compute='_compute_amount_untaxed',
                                           tracking=5)
    amount_untaxed_service = fields.Monetary(
        string="Service Untaxed", help="Untaxed Amount for Service",
        compute='_compute_amount_untaxed', tracking=5)
    amount_untaxed_fleet = fields.Monetary(string="Amount Untaxed",
                                           help="Untaxed amount for Fleet",
                                           compute='_compute_amount_untaxed',
                                           tracking=5)
    amount_taxed_room = fields.Monetary(string="Rom Tax", help="Tax for Room",
                                        compute='_compute_amount_untaxed',
                                        tracking=5)
    amount_taxed_food = fields.Monetary(string="Food Tax", help="Tax for Food",
                                        compute='_compute_amount_untaxed',
                                        tracking=5)
    amount_taxed_event = fields.Monetary(string="Event Tax",
                                         help="Tax for Event",
                                         compute='_compute_amount_untaxed',
                                         tracking=5)
    amount_taxed_service = fields.Monetary(string="Service Tax",
                                           compute='_compute_amount_untaxed',
                                           help="Tax for Service", tracking=5)
    amount_taxed_fleet = fields.Monetary(string="Fleet Tax",
                                         compute='_compute_amount_untaxed',
                                         help="Tax for Fleet", tracking=5)
    amount_total_room = fields.Monetary(string="Total Amount for Room",
                                        compute='_compute_amount_untaxed',
                                        help="This is the Total Amount for "
                                             "Room", tracking=5)
    amount_total_food = fields.Monetary(string="Total Amount for Food",
                                        compute='_compute_amount_untaxed',
                                        help="This is the Total Amount for "
                                             "Food", tracking=5)
    amount_total_event = fields.Monetary(string="Total Amount for Event",
                                         compute='_compute_amount_untaxed',
                                         help="This is the Total Amount for "
                                              "Event", tracking=5)
    amount_total_service = fields.Monetary(string="Total Amount for Service",
                                           compute='_compute_amount_untaxed',
                                           help="This is the Total Amount for "
                                                "Service", tracking=5)
    amount_total_fleet = fields.Monetary(string="Total Amount for Fleet",
                                         compute='_compute_amount_untaxed',
                                         help="This is the Total Amount for "
                                              "Fleet", tracking=5)

    passport = fields.Char(string='Passport', tracking=True)

    nationality = fields.Many2one('res.country', string='Nationality', tracking=True)
    source_of_business = fields.Many2one('source.business', string='Source of Business', 
    domain=lambda self: [
        # ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], tracking=True)
    market_segment = fields.Many2one('market.segment', string='Market Segment', 
    domain=lambda self: [
        # ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], tracking=True)

    rate_details = fields.One2many(
        'room.type.specific.rate', compute="_compute_rate_details", string="Rate Details")
    # rate_details = fields.One2many('rate.detail', compute="_compute_rate_details", string="Rate Details")
    rate_code = fields.Many2one('rate.code', string='Rate Code',  
    domain=lambda self: [
        ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ],tracking=True)
    
    @api.onchange('rate_code')
    def _onchange_rate_code_(self):
        # self._compute_room_taxes()
        self._compute_meal_taxes()
        for record in self:
            if record.rate_code.id:
                rate_details = self.env['rate.detail'].search([
                                ('rate_code_id', '=', record.rate_code.id),
                                ('from_date', '<=', record.checkin_date),
                                ('to_date', '>=', record.checkout_date)
                            ])

                if not rate_details:
                    raise ValidationError(
                        _('The selected rate code %s is expired. Please select another rate code.') % record.rate_code.code
                    )
                if rate_details.price_type != 'room_only' and rate_details.meal_pattern_id and not record.meal_pattern:
                    record.meal_pattern = rate_details.meal_pattern_id


    monday_pax_1 = fields.Float(string="Monday (1 Pax)", tracking=True)

    # Fields for all weekdays and pax counts
    monday_pax_1_rb = fields.Float(string="Monday (1 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    monday_pax_2_rb = fields.Float(string="Monday (2 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    monday_pax_3_rb = fields.Float(string="Monday (3 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    monday_pax_4_rb = fields.Float(string="Monday (4 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    monday_pax_5_rb = fields.Float(string="Monday (5 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    monday_pax_6_rb = fields.Float(string="Monday (6 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    tuesday_pax_1_rb = fields.Float(string="Tuesday (1 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_2_rb = fields.Float(string="Tuesday (2 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_3_rb = fields.Float(string="Tuesday (3 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_4_rb = fields.Float(string="Tuesday (4 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_5_rb = fields.Float(string="Tuesday (5 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    tuesday_pax_6_rb = fields.Float(string="Tuesday (6 Pax)", compute="_compute_rate_details_", store=True,
                                    readonly=False)
    wednesday_pax_1_rb = fields.Float(string="Wednesday (1 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_2_rb = fields.Float(string="Wednesday (2 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_3_rb = fields.Float(string="Wednesday (3 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_4_rb = fields.Float(string="Wednesday (4 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_5_rb = fields.Float(string="Wednesday (5 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    wednesday_pax_6_rb = fields.Float(string="Wednesday (6 Pax)", compute="_compute_rate_details_", store=True,
                                      readonly=False)
    thursday_pax_1_rb = fields.Float(string="Thursday (1 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_2_rb = fields.Float(string="Thursday (2 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_3_rb = fields.Float(string="Thursday (3 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_4_rb = fields.Float(string="Thursday (4 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_5_rb = fields.Float(string="Thursday (5 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    thursday_pax_6_rb = fields.Float(string="Thursday (6 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    friday_pax_1_rb = fields.Float(string="Friday (1 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_2_rb = fields.Float(string="Friday (2 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_3_rb = fields.Float(string="Friday (3 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_4_rb = fields.Float(string="Friday (4 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_5_rb = fields.Float(string="Friday (5 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    friday_pax_6_rb = fields.Float(string="Friday (6 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    saturday_pax_1_rb = fields.Float(string="Saturday (1 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_2_rb = fields.Float(string="Saturday (2 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_3_rb = fields.Float(string="Saturday (3 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_4_rb = fields.Float(string="Saturday (4 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_5_rb = fields.Float(string="Saturday (5 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    saturday_pax_6_rb = fields.Float(string="Saturday (6 Pax)", compute="_compute_rate_details_", store=True,
                                     readonly=False)
    sunday_pax_1_rb = fields.Float(string="Sunday (1 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_2_rb = fields.Float(string="Sunday (2 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_3_rb = fields.Float(string="Sunday (3 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_4_rb = fields.Float(string="Sunday (4 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_5_rb = fields.Float(string="Sunday (5 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)
    sunday_pax_6_rb = fields.Float(string="Sunday (6 Pax)", compute="_compute_rate_details_", store=True,
                                   readonly=False)

    pax_1_rb = fields.Float(string="Default (1 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_2_rb = fields.Float(string="Default (2 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_3_rb = fields.Float(string="Default (3 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_4_rb = fields.Float(string="Default (4 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_5_rb = fields.Float(string="Default (5 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)
    pax_6_rb = fields.Float(string="Default (6 Pax)",
                            compute="_compute_rate_details_", store=True, readonly=False)

    @api.onchange('hotel_room_type')
    def _onchange_hotel_room_type(self):
        for record in self:
            # Define the days variable at the beginning to ensure it is always accessible
            days = ["monday", "tuesday", "wednesday",
                    "thursday", "friday", "saturday", "sunday"]

            # Clear rate code and pax fields if no hotel room type is selected
            if not record.hotel_room_type:
                record.rate_code = False
                for day in days:
                    for pax in range(1, 7):
                        setattr(record, f"{day}_pax_{pax}_rb", 0.0)
                return

            rate_code = self.env['rate.code'].search([
                ('company_id', '=', self.env.company.id),

            ],)
            # Attempt to find rate details in room.type.specific.rate
            specific_rate_detail = self.env['room.type.specific.rate'].search([
                ('room_type_id', '=', record.hotel_room_type.id),
                ('company_id', '=', self.env.company.id),
                ('from_date', '<=', record.checkin_date),
                ('to_date', '>=', record.checkout_date)
            ], limit=1)

            # Check if specific rate detail exists and has non-zero values
            use_specific_rate = False
            if specific_rate_detail:
                # Check if any pax rate for any day is greater than 0.0
                for day in days:
                    for pax in range(1, 7):
                        field_name = f"room_type_{day}_pax_{pax}"
                        if getattr(specific_rate_detail, field_name, 0.0) > 0.0:
                            use_specific_rate = True
                            break
                    if use_specific_rate:
                        break

            if use_specific_rate:
                # Use room.type.specific.rate data if any pax rate is non-zero
                record.rate_code = specific_rate_detail.rate_code_id
                for day in days:
                    for pax in range(1, 7):
                        field_name = f"room_type_{day}_pax_{pax}"
                        rb_field_name = f"{day}_pax_{pax}_rb"
                        value = getattr(specific_rate_detail, field_name, 0.0)
                        setattr(record, rb_field_name, value)

                # Update rate_details field to reflect specific rate detail
                record.update({
                    'rate_details': [(6, 0, specific_rate_detail.ids)]
                })
            else:
                # Fallback to rate.detail if all values in room.type.specific.rate are 0.0
                general_rate_detail = self.env['rate.detail'].search([
                    ('rate_code_id', '=', record.rate_code.id)
                ], limit=1)

                # Set rate code from general rate detail if available
                record.rate_code = general_rate_detail.rate_code_id if general_rate_detail else False

                # Assign values from rate.detail to RoomBooking fields
                if general_rate_detail:
                    for day in days:
                        for pax in range(1, 7):
                            field_name = f"{day}_pax_{pax}"
                            rb_field_name = f"{day}_pax_{pax}_rb"
                            value = getattr(
                                general_rate_detail, field_name, 0.0)
                            setattr(record, rb_field_name, value)

                    # Update rate_details field with the general rate detail data
                    record.update({
                        'rate_details': [(6, 0, general_rate_detail.ids)]
                    })
                else:
                    # If no data is found in either model, clear the fields
                    record.rate_code = False
                    for day in days:
                        for pax in range(1, 7):
                            setattr(record, f"{day}_pax_{pax}_rb", 0.0)

    # @api.onchange('rate_code')
    # def _onchange_rate_code(self):
    #     for record in self:
    #         # Initialize default values for all weekdays and pax counts
    #         weekdays = ["monday", "tuesday", "wednesday",
    #                     "thursday", "friday", "saturday", "sunday"]
    #         for day in weekdays:
    #             for pax in range(1, 7):
    #                 setattr(record, f"{day}_pax_{pax}_rb", 0.0)
    #         for pax in range(1, 7):
    #             setattr(record, f"pax_{pax}_rb", 0.0)

    #         if record.rate_code and record.rate_code.rate_detail_ids:
    #             rate_detail = record.rate_code.rate_detail_ids[0]

    #             # Assign the values from rate_detail to weekday fields
    #             for day in weekdays:
    #                 for pax in range(1, 7):
    #                     field_name = f"{day}_pax_{pax}"
    #                     rb_field_name = f"{day}_pax_{pax}_rb"
    #                     value = getattr(rate_detail, field_name, 0.0) if getattr(
    #                         rate_detail, field_name, 0.0) else 0.0
    #                     setattr(record, rb_field_name, value)

    #             # Assign the values from rate_detail to default pax fields
    #             for pax in range(1, 7):
    #                 field_name = f"pax_{pax}"
    #                 rb_field_name = f"pax_{pax}_rb"
    #                 value = getattr(rate_detail, field_name, 0.0) if getattr(
    #                     rate_detail, field_name, 0.0) else 0.0
    #                 setattr(record, rb_field_name, value)

    
    
    # @api.depends('rate_code')
    # def _compute_rate_details_(self):
    #     _logger.info("Computing rate details for room booking...")
    #     for record in self:
    #         record.monday_pax_1 = 0.0

    #         # Check if rate_code and rate_detail exist
    #         if record.rate_code and record.rate_code.rate_detail_ids:
    #             rate_detail = record.rate_code.rate_detail_ids.filtered(
    #                 lambda r: r.monday_pax_1 is not None)  # Filter rate_details with non-None values
    #             if rate_detail:
    #                 record.monday_pax_1 = rate_detail[0].monday_pax_1

    id_number = fields.Char(string='ID Number')
    house_use = fields.Boolean(string='House Use')

    @api.depends('rate_code')
    def _compute_rate_details_(self):
        pass

    is_customer_company = fields.Boolean(
        string="Filter Company Customers", default=False)  # New helper field

    @api.model
    def name_get(self):
        res = super(RoomBooking, self).name_get()
        for partner in self.env['res.partner'].search([]):
            print(
                f"Partner Name: {partner.name}, is_company: {partner.is_company}")
        return res

    vip = fields.Boolean(string='VIP')
    vip_code = fields.Many2one('vip.code', string="VIP Code", domain=[('obsolete', '=', False)])
    show_vip_code = fields.Boolean(string="Show VIP Code", compute="_compute_show_vip_code", store=True)

    complementary = fields.Boolean(string='Complimentary')
    complementary_codes = fields.Many2one('complimentary.code', string='Complimentary Code', domain=[('obsolete', '=', False)])
    show_complementary_code = fields.Boolean(string="Show Complimentary Code", compute="_compute_show_codes",
                                             store=True)

    house_use = fields.Boolean(string='House Use')
    house_use_codes = fields.Many2one('house.code', string='House Use Code', domain=[('obsolete', '=', False)])
    show_house_use_code = fields.Boolean(string="Show House Code", compute="_compute_show_codes", store=True)

    @api.constrains('vip', 'vip_code', 'complementary', 'complementary_codes', 'house_use', 'house_use_codes')
    def _check_required_codes(self):
        for record in self:
            errors = []
            if record.vip and not record.vip_code:
                errors.append(_("VIP Code is required when VIP is selected."))
            if record.complementary and not record.complementary_codes:
                errors.append(_("Complimentary Code is required when Complimentary is selected."))
            if record.house_use and not record.house_use_codes:
                errors.append(_("House Use Code is required when House Use is selected."))
            if errors:
                raise ValidationError('\n'.join([_("")] + errors))



    

    @api.depends('vip', 'complementary', 'house_use')
    def _compute_show_codes(self):
        for record in self:
            record.show_vip_code = record.vip
            record.show_complementary_code = record.complementary
            record.show_house_use_code = record.house_use

    @api.onchange('vip', 'complementary', 'house_use')
    def _onchange_codes(self):
        if not self.vip:
            self.vip_code = False  # Clear vip_code when VIP is unchecked
        if not self.complementary:
            self.complementary_codes = False
        if not self.house_use:
            self.house_use_codes = False

    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('prepaid_credit', 'Pre-Paid / Credit Limit'),
        ('credit_limit', 'Credit Limit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment')
    ], string='Payment Type')

    @api.constrains('payment_type')
    def _check_payment_type(self):
        for rec in self:
            if not rec.payment_type:
                raise ValidationError(_("You must select a Payment Type before saving."))

    def unlink(self):
        for rec in self:
            if rec.state != 'cancel' and rec.state != 'draft':
                raise ValidationError(
                    'Cannot delete the Booking. Cancel the Booking ')
        return super().unlink()

    rooms_searched = fields.Boolean(
        string="Rooms Searched",
        default=False,
        store=True,
        copy=False,
        help="Indicates whether rooms have been searched for this booking.")

    @api.model
    def create(self, vals_list):
        if not vals_list.get('payment_type'):
            raise ValidationError(_("Cannot save without search for the room available first"))
        
        if not vals_list.get('company_id'):
            vals_list['company_id'] = self.env.company.id

            # Only generate Booking ID if it's still "New"
        if vals_list.get('name', 'New') == 'New':
            company = self.env['res.company'].browse(vals_list['company_id'])
            prefix = company.name + '/' if company else ''
            next_seq = self.env['ir.sequence'].next_by_code('room.booking') or '00001'
            vals_list['name'] = prefix + next_seq
        self.check_room_meal_validation(vals_list, False)
        
        if 'company_id' in vals_list:
            company = self.env['res.company'].browse(vals_list['company_id'])
            if 'checkin_date' not in vals_list:
                vals_list['checkin_date'] = company.system_date

        if 'room_count' in vals_list and vals_list['room_count'] <= 0:
            raise ValidationError(_("Room count cannot be zero or less. Please select at least one room.")
                )

        if 'adult_count' in vals_list and vals_list['adult_count'] <= 0:
            raise ValidationError(
                "Adult count cannot be zero or less. Please select at least one adult.")

        if 'child_count' in vals_list and vals_list['child_count'] < 0:
            raise ValidationError("Child count cannot be less than zero.")

        if 'infant_count' in vals_list and vals_list['infant_count'] < 0:
            raise ValidationError("Infant count cannot be less than zero.")

        if not vals_list.get('checkin_date'):
            raise ValidationError( _("Check-In Date is required and cannot be empty."))

        if not vals_list.get('checkout_date'):
            raise ValidationError( _("Check-Out Date is required and cannot be empty."))

        # Fetch the company_id from vals_list or default to the current user's company
        company_id = vals_list.get('company_id', self.env.company.id)
        company = self.env['res.company'].browse(company_id)
        current_company_name = company.name

        if vals_list.get('name', 'New') == 'New':
            if vals_list.get('parent_booking_id'):
                # Handle child booking
                parent = self.browse(vals_list['parent_booking_id'])
                parent_company_id = parent.company_id.id
                # Ensure child booking inherits parent's company
                vals_list['company_id'] = parent_company_id

                sequence = self.env['ir.sequence'].search(
                    [('code', '=', 'room.booking'),
                     ('company_id', '=', parent_company_id)],
                    limit=1
                )
                if not sequence:
                    raise ValueError(
                        f"No sequence configured for company: {parent.company_id.name}")

                next_sequence = sequence.next_by_id()

                vals_list['name'] = f"{parent.company_id.name}/{next_sequence}"
                vals_list['parent_booking_name'] = parent.name
            else:
                # Handle new parent booking
                sequence = self.env['ir.sequence'].search(
                    [('code', '=', 'room.booking'),
                     ('company_id', '=', company_id)],
                    limit=1
                )
                if not sequence:
                    raise ValueError(
                        f"No sequence configured for company: {current_company_name}")

                next_sequence = sequence.next_by_id()
                vals_list['name'] = f"{current_company_name}/{next_sequence}"

        record = super(RoomBooking, self).create(vals_list)

        # Log the initial state for all room lines
        
        if record.state:
            get_sys_date = self.env.company.system_date.date()
            current_time = datetime.now().time()
            get_sys_date = datetime.combine(get_sys_date, current_time)
            for line in record.room_line_ids:
                if record.state == 'block':
                    self.env['room.booking.line.status'].create({
                        'booking_line_id': line.id,
                        'status': 'confirmed',
                        'change_time': get_sys_date,
                    })

                # Now create the actual status record (e.g., 'block')
                self.env['room.booking.line.status'].create({
                    'booking_line_id': line.id,
                    'status': record.state,
                    'change_time': get_sys_date + timedelta(seconds=1),
                })
        return record
   
    
    @api.depends('partner_id')
    def _compute_user_id(self):
        """Computes the User id"""
        for order in self:
            order.user_id = \
                order.partner_id.address_get(['invoice'])[
                    'invoice'] if order.partner_id else False

    
    def _compute_invoice_count(self):
        """Compute the invoice count"""
        for record in self:
            record.invoice_count = self.env['account.move'].search_count(
                # Use `record.name` instead of `self.name`
                [('ref', '=', record.name)]
            )

    @api.depends('partner_id')
    def _compute_pricelist_id(self):
        """Computes PriceList"""
        for order in self:
            if not order.partner_id:
                order.pricelist_id = False
                continue
            order = order.with_company(order.company_id)
            order.pricelist_id = order.partner_id.property_product_pricelist

    @api.depends('room_line_ids.price_subtotal', 'room_line_ids.price_tax',
                 'room_line_ids.price_total',
                 'food_order_line_ids.price_subtotal',
                 'food_order_line_ids.price_tax',
                 'food_order_line_ids.price_total',
                 'service_line_ids.price_subtotal',
                 'service_line_ids.price_tax', 'service_line_ids.price_total',
                 'vehicle_line_ids.price_subtotal',
                 'vehicle_line_ids.price_tax', 'vehicle_line_ids.price_total',
                 'event_line_ids.price_subtotal', 'event_line_ids.price_tax',
                 'event_line_ids.price_total',
                 )
    @api.depends('food_order_line_ids', 'service_line_ids', 'vehicle_line_ids', 'event_line_ids')
    def _compute_amount_untaxed(self, flag=False):
        for rec in self:
            # Initialize amounts for each record
            amount_untaxed_room = 0.0
            amount_untaxed_food = 0.0
            amount_untaxed_fleet = 0.0
            amount_untaxed_event = 0.0
            amount_untaxed_service = 0.0
            amount_taxed_room = 0.0
            amount_taxed_food = 0.0
            amount_taxed_fleet = 0.0
            amount_taxed_event = 0.0
            amount_taxed_service = 0.0
            amount_total_room = 0.0
            amount_total_food = 0.0
            amount_total_fleet = 0.0
            amount_total_event = 0.0
            amount_total_service = 0.0
            booking_list = []

            # Fetch and filter account move lines for the current record
            account_move_line = self.env['account.move.line'].search_read(
                domain=[('ref', '=', rec.name),
                        ('display_type', '!=', 'payment_term')],
                fields=['name', 'quantity', 'price_unit', 'product_type']
            )

            # Remove the 'id' key from account move lines
            for line in account_move_line:
                del line['id']

            # Calculate amounts for each type of line item
            if rec.room_line_ids:
                amount_untaxed_room += sum(
                    rec.room_line_ids.mapped('price_subtotal'))
                amount_taxed_room += sum(rec.room_line_ids.mapped('price_tax'))
                amount_total_room += sum(rec.room_line_ids.mapped('price_total'))
                for room in rec.room_line_ids:
                    booking_dict = {'name': room.room_id.name, 'quantity': room.uom_qty, 'price_unit': room.price_unit,
                                    'product_type': 'room'}
                    if booking_dict not in account_move_line:
                        if not account_move_line:
                            booking_list.append(booking_dict)
                        else:
                            for move_line in account_move_line:
                                if move_line['product_type'] == 'room' and booking_dict['name'] == move_line['name']:
                                    if booking_dict['price_unit'] == move_line['price_unit'] and booking_dict[
                                        'quantity'] != move_line['quantity']:
                                        booking_list.append({
                                            'name': room.room_id.name,
                                            "quantity": booking_dict['quantity'] - move_line['quantity'],
                                            "price_unit": room.price_unit,
                                            "product_type": 'room'
                                        })
                                    else:
                                        booking_list.append(booking_dict)
                    if flag:
                        room.booking_line_visible = True

            if rec.food_order_line_ids:
                for food in rec.food_order_line_ids:
                    booking_list.append(self.create_list(food))
                amount_untaxed_food += sum(
                    rec.food_order_line_ids.mapped('price_subtotal'))
                amount_taxed_food += sum(
                    rec.food_order_line_ids.mapped('price_tax'))
                amount_total_food += sum(
                    rec.food_order_line_ids.mapped('price_total'))

            if rec.service_line_ids:
                for service in rec.service_line_ids:
                    booking_list.append(self.create_list(service))
                amount_untaxed_service += sum(
                    rec.service_line_ids.mapped('price_subtotal'))
                amount_taxed_service += sum(
                    rec.service_line_ids.mapped('price_tax'))
                amount_total_service += sum(
                    rec.service_line_ids.mapped('price_total'))

            if rec.vehicle_line_ids:
                for fleet in rec.vehicle_line_ids:
                    booking_list.append(self.create_list(fleet))
                amount_untaxed_fleet += sum(
                    rec.vehicle_line_ids.mapped('price_subtotal'))
                amount_taxed_fleet += sum(
                    rec.vehicle_line_ids.mapped('price_tax'))
                amount_total_fleet += sum(
                    rec.vehicle_line_ids.mapped('price_total'))

            if rec.event_line_ids:
                for event in rec.event_line_ids:
                    booking_list.append(self.create_list(event))
                amount_untaxed_event += sum(
                    rec.event_line_ids.mapped('price_subtotal'))
                amount_taxed_event += sum(rec.event_line_ids.mapped('price_tax'))
                amount_total_event += sum(
                    rec.event_line_ids.mapped('price_total'))

            # Assign computed amounts to the current record
            rec.amount_untaxed = amount_untaxed_food + amount_untaxed_room + \
                                 amount_untaxed_fleet + amount_untaxed_event + amount_untaxed_service
            rec.amount_untaxed_food = amount_untaxed_food
            rec.amount_untaxed_room = amount_untaxed_room
            rec.amount_untaxed_fleet = amount_untaxed_fleet
            rec.amount_untaxed_event = amount_untaxed_event
            rec.amount_untaxed_service = amount_untaxed_service
            rec.amount_tax = amount_taxed_food + amount_taxed_room + \
                             amount_taxed_fleet + amount_taxed_event + amount_taxed_service
            rec.amount_taxed_food = amount_taxed_food
            rec.amount_taxed_room = amount_taxed_room
            rec.amount_taxed_fleet = amount_taxed_fleet
            rec.amount_taxed_event = amount_taxed_event
            rec.amount_taxed_service = amount_taxed_service
            rec.amount_total = amount_total_food + amount_total_room + \
                               amount_total_fleet + amount_total_event + amount_total_service
            rec.amount_total_food = amount_total_food
            rec.amount_total_room = amount_total_room
            rec.amount_total_fleet = amount_total_fleet
            rec.amount_total_event = amount_total_event
            rec.amount_total_service = amount_total_service

        return booking_list

    
    @api.onchange('need_food')
    def _onchange_need_food(self):
        """Unlink Food Booking Line if Need Food is false"""
        if not self.need_food and self.food_order_line_ids:
            for food in self.food_order_line_ids:
                food.unlink()

    @api.onchange('need_service')
    def _onchange_need_service(self):
        """Unlink Service Booking Line if Need Service is False"""
        if not self.need_service and self.service_line_ids:
            for serv in self.service_line_ids:
                serv.unlink()

    @api.onchange('need_fleet')
    def _onchange_need_fleet(self):
        """Unlink Fleet Booking Line if Need Fleet is False"""
        if not self.need_fleet:
            if self.vehicle_line_ids:
                for fleet in self.vehicle_line_ids:
                    fleet.unlink()

    @api.onchange('need_event')
    def _onchange_need_event(self):
        """Unlink Event Booking Line if Need Event is False"""
        if not self.need_event:
            if self.event_line_ids:
                for event in self.event_line_ids:
                    event.unlink()

    @api.onchange('food_order_line_ids',
                  'service_line_ids', 'vehicle_line_ids', 'event_line_ids')
    def _onchange_room_line_ids(self):
        """Invokes the Compute amounts function"""
        self._compute_amount_untaxed()
        self.invoice_button_visible = False

    
    def copy(self, default=None):
        restricted_states = ['not_confirmed', 'confirmed', 'block', 'check_in', 'check_out', 'cancel', 'no_show']
        if self.state not in restricted_states:
            raise UserError(_("You cannot duplicate a booking that is in '%s' state.") % self.state.capitalize())

        # Don’t provide 'name' in default, so create() assigns it automatically
        default = dict(default or {})
        
        return super(RoomBooking, self).copy(default)

    def create_list(self, line_ids):
        """Returns a Dictionary containing the Booking line Values"""
        account_move_line = self.env['account.move.line'].search_read(
            domain=[('ref', '=', self.name),
                    ('display_type', '!=', 'payment_term')],
            fields=['name', 'quantity', 'price_unit', 'product_type'], )
        for rec in account_move_line:
            del rec['id']
        booking_dict = {}
        for line in line_ids:
            name = ""
            product_type = ""
            if line_ids._name == 'food.booking.line':
                name = line.food_id.name
                product_type = 'food'
            elif line_ids._name == 'fleet.booking.line':
                name = line.fleet_id.name
                product_type = 'fleet'
            elif line_ids._name == 'service.booking.line':
                name = line.service_id.name
                product_type = 'service'
            elif line_ids._name == 'event.booking.line':
                name = line.event_id.name
                product_type = 'event'
            booking_dict = {'name': name,
                            'quantity': line.uom_qty,
                            'price_unit': line.price_unit,
                            'product_type': product_type}
        return booking_dict

    def action_reserve(self):
        """Button Reserve Function"""
        if self.state == 'reserved':
            message = _("Room Already Reserved.")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': message,
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        if self.room_line_ids:
            for room in self.room_line_ids:
                room.room_id.write({
                    'status': 'reserved',
                })
                room.room_id.is_room_avail = False
            self.write({"state": "reserved"})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': _("Rooms reserved Successfully!"),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        raise ValidationError(_("Please Enter Room Details"))


    def action_cancel(self):
        """Cancel a booking, clear room lines, adjust availability, and record cancel status."""
        for record in self:
            parent_id = record.parent_booking_id.id if record.parent_booking_id else record.id

            # 1) Fetch all room line IDs for this booking
            self.env.cr.execute(
                """
                SELECT id
                FROM room_booking_line
                WHERE booking_id = %s
                """,
                (record.id,)
            )
            room_line_ids = [row[0] for row in self.env.cr.fetchall()]

            if room_line_ids:
                _logger.debug("Cancelling room lines with IDs: %s", room_line_ids)

                # 2) Bulk update room lines to 'cancel'
                self.env.cr.execute(
                    """
                    UPDATE room_booking_line
                    SET state_ = 'cancel',
                        room_id = NULL
                    WHERE id = ANY(%s)
                    """,
                    (room_line_ids,)
                )

                # 3) Adjust availability and insert status history
                self.env.cr.execute(
                    """
                    SELECT id, available_rooms, rooms_reserved
                    FROM room_availability_result
                    WHERE room_booking_id = %s
                    """,
                    (parent_id,)
                )
                availability_results = self.env.cr.fetchall()
                for avail_id, avail_rooms, reserved in availability_results:
                    count = 1
                    if reserved >= count:
                        self.env.cr.execute(
                            """
                            UPDATE room_availability_result
                            SET available_rooms = available_rooms + %s,
                                rooms_reserved   = rooms_reserved - %s
                            WHERE id = %s
                            """,
                            (count, count, avail_id)
                        )
                    else:
                        self.env.cr.execute(
                            """
                            UPDATE room_availability_result
                            SET available_rooms = available_rooms + rooms_reserved,
                                rooms_reserved   = 0
                            WHERE id = %s
                            """,
                            (avail_id,)
                        )

                # 4) Insert a cancel entry for each line
                for line_id in room_line_ids:
                    self.env.cr.execute(
                        """
                        INSERT INTO room_booking_line_status (
                            booking_line_id,
                            create_uid, write_uid,
                            status,
                            change_time,
                            create_date, write_date
                        ) VALUES (%s, %s, %s, 'cancel', NOW(), NOW(), NOW())
                        """,
                        (line_id, self.env.uid, self.env.uid)
                    )

            self.env.cr.execute(
                """
                UPDATE room_booking
                SET state = 'cancel'
                WHERE id = %s
                """,
                (record.id,)
            )
            _logger.debug("Booking ID %s has been canceled.", record.id)



    def action_done(self):
        """Method for creating invoice"""
        if not self.room_line_ids:
            raise ValidationError(_("Please Enter Room Details"))
        booking_list = self._compute_amount_untaxed(True)
        if booking_list:
            account_move = self.env["account.move"].create([{
                'move_type': 'out_invoice',
                'invoice_date': fields.Date.today(),
                'partner_id': self.partner_id.id,
                'ref': self.name,
            }])
            for rec in booking_list:
                account_move.invoice_line_ids.create([{
                    'name': rec['name'],
                    'quantity': rec['quantity'],
                    'price_unit': rec['price_unit'],
                    'move_id': account_move.id,
                    'price_subtotal': rec['quantity'] * rec['price_unit'],
                    'product_type': rec['product_type'],
                }])
            self.write({'invoice_status': "invoiced"})
            self.invoice_button_visible = True
            return {
                'type': 'ir.actions.act_window',
                'name': 'Invoices',
                'view_mode': 'form',
                'view_type': 'form',
                'res_model': 'account.move',
                'view_id': self.env.ref('account.view_move_form').id,
                'res_id': account_move.id,
                'context': "{'create': False}"
            }


    def _create_invoice(self):
        today = self.env.company.system_date.date()
        current_time = datetime.now().time()
        current_datetime = datetime.combine(today, current_time)

        # Get meal and pricing details
        posting_item_meal, _1, _2, _3 = self.get_meal_rates(self.meal_pattern.id)
        record = self  # Assuming the current record is used as 'record'
        meal_price, room_price, package_price, posting_item_value, line_posting_items = self.get_all_prices(record.checkin_date, record)

        _logger.debug(f"Meal Posting Item: {posting_item_meal}")
        _logger.debug(f"Rate Posting Item: {posting_item_value}")

        if not self.room_line_ids:
            raise ValidationError(_("Please Enter Room Details"))

        # Filter forecast rates for today
        filtered_lines = [line for line in self.rate_forecast_ids if line.date == today]

        _logger.debug(f"Number of filtered rate_forecast_ids lines = {len(filtered_lines)}")

        # Create Invoice
        account_move = self.env["account.move"].create({
            'move_type': 'out_invoice',
            'invoice_date': today,
            'partner_id': self.partner_id.id,
            'ref': self.name,
            'hotel_booking_id': self.id,
            'group_booking_name': self.group_booking.name if self.group_booking else '',
            'parent_booking_name': self.parent_booking_name or '',
            'room_numbers': self.room_ids_display or '',
        })

        # Add invoice lines for Rate, Meal, and Package
        for line in filtered_lines:
            line_data = []

            # Add Rate Line if applicable
            if line.rate and line.rate > 0:
                line_data.append({
                    'posting_item_id': posting_item_value,
                    'posting_description': 'Rate',
                    'posting_default_value': line.rate,
                    'move_id': account_move.id,
                })

            # Add Meal Line if applicable
            if line.meals and line.meals > 0:
                line_data.append({
                    'posting_item_id': posting_item_meal,
                    'posting_description': 'Meal',
                    'posting_default_value': line.meals,
                    'move_id': account_move.id,
                })

            # Add Package Line if applicable
            if line.packages and line.packages > 0:
                line_data.append({
                    'posting_item_id': line_posting_items[-1],
                    'posting_description': 'Package',
                    'posting_default_value': line.packages,
                    'move_id': account_move.id,
                })

            # Create invoice lines
            if line_data:
                account_move.invoice_line_ids.create(line_data)

        # Update status
        self.write({'invoice_status': "invoiced"})
        self.write({"state": "check_out"})
        self.room_line_ids.write({"state_": "check_out"})
        self.invoice_button_visible = True

    

    def action_checkout(self):
        today = self.env.company.system_date.date()
        current_time = datetime.now().time()
        current_datetime = datetime.combine(today, current_time)

        if self.env.company.system_date > current_datetime:
            current_datetime = self.env.company.system_date + timedelta(hours=1)
            
            
        if self.checkout_date:
            # Calculate the checkout_date
            get_current_time = datetime.now().time()
            checkout_datetime = datetime.combine(today, get_current_time)
            checkout_date = checkout_datetime

            if self.checkout_date.date() > today:
                return {
                    'name': _('Confirm Early Check-Out'),
                    'type': 'ir.actions.act_window',
                    'res_model': 'confirm.early.checkout.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {'default_booking_ids': self.ids},
                }
            else:
                self._create_invoice()
                self.write({"state": "check_out","checkout_date": current_datetime})
                self.room_line_ids.write({"state_": "check_out"})
                
                self._sql_update_line_dates(
                    self.room_line_ids.ids, self.checkin_date, current_datetime)
                self._log_room_line_status(
                    line_ids=self.room_line_ids.ids,
                    status='check_out'
                )
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'success',
                        'message': _("Booking Checked Out Successfully!"),
                        'next': {'type': 'ir.actions.act_window_close'},
                    }
                }

    
    def action_view_invoices(self):
        """Method for Returning invoice View"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'view_mode': 'tree,form',
            'view_type': 'tree,form',
            'res_model': 'account.move',
            'domain': [('ref', '=', self.name)],
            'context': "{'create': False}"
        }

    def _sql_update_line_dates(self, line_ids, checkin_date, checkout_date):
        if not line_ids:
            _logger.debug("No line IDs to update")
            return
        
        # psycopg2 will expand the tuple into the IN (...) list
        self.env.cr.execute("""
            UPDATE room_booking_line
               SET checkin_date  = %s,
                   checkout_date = %s
             WHERE id IN %s
        """, (checkin_date, checkout_date, tuple(line_ids)))
    
    
    def action_checkin(self):
        today = self.env.company.system_date.date()  # Get today's date from the company configuration

        for record in self:
            # Validate that check-in date is not in the past
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot check-in a booking with a check-in date in the past.")
                )

            # Ensure room details are entered
            if not record.room_line_ids:
                raise ValidationError(_("Please Enter Room Details"))

              # ---- Ensure same room number on same day shouldn't check-in twice ----
        for line in record.room_line_ids:
            overlapping_reservation = self.env['room.booking.line'].search([
                ('room_id', '=', line.room_id.id),
                ('id', '!=', line.id),  # exclude current line
                ('state_', '=', 'check_in'),
                ('checkin_date', '<=', record.checkout_date),
                ('checkout_date', '>=', record.checkin_date),
            ], limit=1)
            if overlapping_reservation:
                raise ValidationError(_(
                    "Selected room number %s is already checked in for this date. Please change the room number to do check-in."
                ) % (line.room_id.name))

   

            # Check if the check-in date is in the future and you are trying to check-in today
            if fields.Date.to_date(record.checkin_date) > today:
                # Perform room availability check for today
                room_availability = record.check_room_availability_all_hotels_split_across_type(
                    checkin_date=today,
                    checkout_date=today + timedelta(days=1),
                    room_count=len(record.room_line_ids),
                    adult_count=sum(record.room_line_ids.mapped('adult_count')),
                    hotel_room_type_id=record.room_line_ids.mapped('hotel_room_type').id if record.room_line_ids else None,
                )
                _logger.debug(f"Room Availability: {room_availability}")

                # Check room availability result
                if not room_availability or isinstance(room_availability, dict):
                    raise ValidationError(_("No rooms are available for today's date. Please select a different date."))

                # Process room availability
                room_availability_list = room_availability[1]
                total_available_rooms = sum(
                    int(res.get('available_rooms', 0)) for res in room_availability_list
                )

                if total_available_rooms <= 0:
                    raise ValidationError(_("No rooms are available for today's date. Please select a different date."))

                # Open the confirmation wizard
                return {
                    'type': 'ir.actions.act_window',
                    'res_model': 'booking.checkin.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_booking_ids': [record.id],
                    }
                }

            # Combine today's date and the current time into a single datetime object for check-in
            get_current_time = datetime.now().time()
            checkin_datetime = datetime.combine(today, get_current_time)
            result = record._perform_checkin()

            line_ids = record.room_line_ids.ids
            record._sql_update_line_dates(self.room_line_ids.ids, checkin_datetime, record.checkout_date)
            record._log_room_line_status(line_ids, status='check_in')
            return result

    
    
    def _perform_checkin(self):
        parent_booking_id = self.parent_booking_id.id if self.parent_booking_id else self.id
        cr = self.env.cr

        room_ids = [room.room_id.id for room in self.room_line_ids]
        room_line_ids = [room.id for room in self.room_line_ids]

        if room_ids:
            cr.execute("""
                UPDATE hotel_room
                SET status = 'occupied', is_room_avail = FALSE
                WHERE id IN %s
            """, (tuple(room_ids),))

        if room_line_ids:
            cr.execute("""
                UPDATE room_booking_line
                SET state_ = 'check_in'
                WHERE id IN %s
            """, (tuple(room_line_ids),))

        cr.execute("""
            UPDATE room_booking
            SET state = 'check_in'
            WHERE id = %s
        """, (self.id,))
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking Checked In Successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
    

    def _early_perform_checkin(self):
        """Helper method to perform check-in and update room availability."""
        try:
            parent_booking_id = self.parent_booking_id.id if self.parent_booking_id else self.id
            today = self.env.company.system_date.date()

            for room in self.room_line_ids:
                # Update room status to 'occupied'
                room.room_id.write({
                    'status': 'occupied',
                })
                room.room_id.is_room_avail = False

            # Fetch room availability
            room_availability = self.check_room_availability_all_hotels_split_across_type(
                checkin_date=today,
                checkout_date=today + timedelta(days=1),
                room_count=len(self.room_line_ids),
                adult_count=sum(self.room_line_ids.mapped('adult_count')),
                hotel_room_type_id=self.room_line_ids.mapped(
                    'hotel_room_type').id if self.room_line_ids else None
            )

            _logger.debug(f"Room Availability: {room_availability}")

            if not room_availability or isinstance(room_availability, dict):
                raise ValidationError(_("No rooms are available for today's date. Please select a different date."))

            room_availability_list = room_availability[1]
            total_available_rooms = sum(
                int(res.get('available_rooms', 0)) for res in room_availability_list)

            if total_available_rooms <= 0:
                raise ValidationError(_("No rooms are available for the selected date. Please select a different date."))

            # Update availability results
            for room in self.room_line_ids:
                if room.room_id:
                    availability_result = self.env['room.availability.result'].search([
                        ('room_booking_id', '=', parent_booking_id)
                    ], limit=1)

                    if availability_result:
                        reserved_rooms = room.room_count if hasattr(room, 'room_count') else 1
                        availability_result.available_rooms -= reserved_rooms
                        availability_result.rooms_reserved += reserved_rooms

            # Update state
            self.write({"state": "check_in"})
            

        except ValidationError as e:
            self.message_post(body=str(e))
            raise

        except Exception as e:
            print(f"Unexpected error: {e}")
            raise ValidationError(_("An unexpected error occurred during check-in. Please contact support."))


    @api.model
    def action_confirm_checkin(self, record_id):
        """ This method is called when the user confirms to change the check-in date """
        record = self.browse(record_id)
        if record.exists():
            # record.checkin_date = datetime.now()
            record.checkin_date = self.env.company.system_date.date()
            return record._perform_checkin()
        return False
    
    def action_block(self):
        # today = datetime.now().date()
        today = self.env.company.system_date.date()
        for record in self:
            if record.checkin_date and record.checkin_date.date() < today:
                raise ValidationError(
                    _("You cannot block  booking with a check-in date in the past."))
            # Check if all room_ids are assigned in room_line_ids
            unassigned_lines = record.room_line_ids.filtered(
                lambda line: not line.room_id)
            if unassigned_lines:
                raise ValidationError(_("All rooms must be assigned in room lines before moving to the 'block' state."))
                 

            # If all rooms are assigned, allow state change
            record.state = "block"

    all_rooms_assigned = fields.Boolean(
        string="All Rooms Assigned",
        compute="_compute_all_rooms_assigned",
        store=True
    )

    @api.depends('room_line_ids.room_id')
    def _compute_all_rooms_assigned(self):
        for record in self:
            if record.room_line_ids:
                record.all_rooms_assigned = all(
                    line.room_id for line in record.room_line_ids)
            else:
                record.all_rooms_assigned = False

            # Call action_reload_page if all rooms are assigned
            if record.all_rooms_assigned:
                record.action_reload_page()

    def action_reload_page(self):
        """Reload the current page when all rooms are assigned."""
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_auto_assign_room(self):
        pass

    def button_split_rooms(self):
        pass

    def get_details(self):
        """ Returns different counts for displaying in dashboard"""
        today = datetime.today()
        tz_name = False
        if self.env.user.tz:
            tz_name = self.env.user.tz
        today_utc = pytz.timezone('UTC').localize(today,
                                                  is_dst=False)
        if tz_name:
            context_today = today_utc.astimezone(pytz.timezone(tz_name))
            total_room = self.env['hotel.room'].search_count([])
            check_in = self.env['room.booking'].search_count(
                [('state', '=', 'check_in')])
            available_room = self.env['hotel.room'].search(
                [('status', '=', 'available')])
            reservation = self.env['room.booking'].search_count(
                [('state', '=', 'reserved')])
            check_outs = self.env['room.booking'].search([])
            check_out = 0
            staff = 0
            for rec in check_outs:
                for room in rec.room_line_ids:
                    if room.checkout_date.date() == context_today.date():
                        check_out += 1
                """staff"""
                staff = self.env['res.users'].search_count(
                    [('groups_id', 'in',
                      [self.env.ref('hotel_management.hotel_group_admin').id,
                       self.env.ref(
                           'hotel_management.cleaning_team_group_head').id,
                       self.env.ref(
                           'hotel_management.cleaning_team_group_user').id,
                       self.env.ref(
                           'hotel_management.hotel_group_reception').id,
                       self.env.ref(
                           'hotel_management.maintenance_team_group_leader').id,
                       self.env.ref(
                           'hotel_management.maintenance_team_group_user').id
                       ])])
            total_vehicle = self.env['fleet.vehicle.model'].search_count([])
            available_vehicle = total_vehicle - self.env[
                'fleet.booking.line'].search_count(
                [('state', '=', 'check_in')])
            total_event = self.env['event.event'].search_count([])
            pending_event = self.env['event.event'].search([])
            pending_events = 0
            today_events = 0
            for pending in pending_event:
                if pending.date_end >= fields.datetime.now():
                    pending_events += 1
                if pending.date_end.date() == fields.date.today():
                    today_events += 1
            food_items = self.env['lunch.product'].search_count([])
            food_order = len(self.env['food.booking.line'].search([]).filtered(
                lambda r: r.booking_id.state not in ['check_out', 'cancel',
                                                     'done']))
            """total Revenue"""
            total_revenue = 0
            today_revenue = 0
            pending_payment = 0
            for rec in self.env['account.move'].search(
                    [('payment_state', '=', 'paid')]):
                if rec.ref:
                    if 'BOOKING' in rec.ref:
                        total_revenue += rec.amount_total
                        if rec.date == fields.date.today():
                            today_revenue += rec.amount_total
            for rec in self.env['account.move'].search(
                    [('payment_state', 'in', ['not_paid', 'partial'])]):
                if rec.ref and 'BOOKING' in rec.ref:
                    if rec.payment_state == 'not_paid':
                        pending_payment += rec.amount_total
                    elif rec.payment_state == 'partial':
                        pending_payment += rec.amount_residual
            return {
                'total_room': total_room,
                'available_room': len(available_room),
                'staff': staff,
                'check_in': check_in,
                'reservation': reservation,
                'check_out': check_out,
                'total_vehicle': total_vehicle,
                'available_vehicle': available_vehicle,
                'total_event': total_event,
                'today_events': today_events,
                'pending_events': pending_events,
                'food_items': food_items,
                'food_order': food_order,
                'total_revenue': round(total_revenue, 2),
                'today_revenue': round(today_revenue, 2),
                'pending_payment': round(pending_payment, 2),
                'currency_symbol': self.env.user.company_id.currency_id.symbol,
                'currency_position': self.env.user.company_id.currency_id.position
            }
        else:
            raise ValidationError(
                _("Please Enter time zone in user settings."))

    room_count = fields.Integer(string='Rooms', tracking=True)


    adult_count = fields.Integer(string='Adults', tracking=True)
    child_count = fields.Integer(string='Children', default=0, tracking=True)
    infant_count = fields.Integer(string='Infant', default=0, tracking=True)
    child_ages = fields.One2many(
        'hotel.child.age', 'booking_id', string='Children Ages')
    total_people = fields.Integer(
        string='Total People', compute='_compute_total_people', store=True, tracking=True)
    rooms_to_add = fields.Integer(
        string='Rooms to Add', default=0, tracking=True)

    room_ids_display = fields.Char(string="Room Names", compute="_compute_room_ids_display",
                                   search="_search_room_ids_display", tracking=True)
    room_type_display = fields.Char(
        string="Room Types", compute="_compute_room_type_display", tracking=True)

    room_price = fields.Float(string="Room Price", default=0, tracking=True)
    
    @api.constrains('use_price', 'room_price', 'use_meal_price', 'meal_price')
    def _check_price_values(self):
        for record in self:
            errors = []

            # Room price validation
            if record.use_price and (record.room_price is None or record.room_price < 0):
                errors.append(_("Room Price must be greater than 0 when Use Price is selected!"))

            # Meal price validation
            if record.use_meal_price and (record.meal_price is None or record.meal_price < 0):
                errors.append(_("Meal Price must be greater than or equal 0 when Use Price is selected!"))

            if errors:
                raise ValidationError('\n'.join([_("Please correct the following:")] + errors))

    
    room_child_price = fields.Float(string="Room Child Price", tracking=True)
    room_infant_price = fields.Float(string="Room Infant Price", tracking=True)
    meal_price = fields.Float(string="Meal Price", default=0, tracking=True)
    meal_child_price = fields.Float(string="Meal Child Price", tracking=True, default=0)
    meal_infant_price = fields.Float(string="Meal Infant Price", tracking=True)
    # Discount Fields
    room_discount = fields.Float(
        string="Room Discount", default=0, digits=(16, 2), tracking=True)
    meal_discount = fields.Float(
        string="Meal Discount", default=0, tracking=True)

    def get_rate_details_on_room_number_specific_rate(self, _day, record, forecast_date):
        room_price = 0
        _day = forecast_date.strftime('%A').lower()
        _var = f"room_number_{_day}_pax_{record.adult_count}"
        _var_child = f"room_number_{_day}_child_pax_1"
        _var_infant = f"room_number_{_day}_infant_pax_1"
        _adult_count = 1
        if record.adult_count > 6:
            _var = f"room_number_{_day}_pax_1"
            _adult_count = record.adult_count

        if record.rate_code.id and not record.use_price:
            _logger.debug("record.rate_code.id: %s", record.rate_code.id)
            # Get the last/selected room from room_line_ids
            room_number_record = ()
            if len(record.room_line_ids) == 1:
                room_number_record = self.env['room.number.store'].search([
                            ('name', '=', record.room_line_ids.room_id.display_name)
                        ], limit=1)
            if room_number_record:
                room_number_specific_rate = self.env['room.number.specific.rate'].search([
                    ('rate_code_id', '=', record.rate_code.id),
                    ('from_date', '<=', forecast_date),
                    ('to_date', '>=', forecast_date),
                    ('room_fsm_location', '=', record.room_line_ids.room_id.fsm_location.id),
                    # ('display_name', '=', room_line.room_id.display_name),
                    ('room_number', '=', room_number_record.id),
                    ('company_id', '=', self.env.company.id)
                    
                ])
                _logger.debug("room_number_specific_rate: %s %s %s %s", room_number_specific_rate,record.room_line_ids.room_id.fsm_location.id,record.room_line_ids.room_id.display_name,room_number_record.id)
                if room_number_specific_rate.id:
                    if record.adult_count > 6:
                        room_price += room_number_specific_rate[_var] * record.adult_count
                    else:
                        room_price += room_number_specific_rate[_var]
                    _logger.debug("room specific rate type room_price: %s", room_price)
                    room_price += room_number_specific_rate[_var_child] * record.child_count
                    room_price += room_number_specific_rate[_var_infant] * record.infant_count
        _logger.debug("room specific rate type room_price: %s", room_price)
        return room_price


    def check_room_meal_validation(self, vals, is_write):
        for record in self:
            if vals.get('use_price', record.use_price):

                if vals.get('room_price', record.room_price) < 0:
                    raise UserError(_("Room Price cannot be less than 0."))

                # Only disallow negative discounts; no minimum % threshold
                discount = vals.get('room_discount', record.room_discount)
                if discount < 0:
                    raise UserError(_("Room Discount cannot be less than 0."))


            # Meal Price validation
            
            if vals.get('use_meal_price', record.use_meal_price):
                if vals.get('meal_price', record.meal_price) < 0:
                    raise UserError(_("Meal Price cannot be less than 0."))

                if vals.get('child_count', record.child_count) > 0:
                    if vals.get('meal_child_price', record.meal_child_price) < 0:
                        raise UserError(
                            "Meal Child Price cannot be less than 0.")

                # Validate meal discount (only non-negative, regardless of percentage flag)
                meal_discount = vals.get('meal_discount', record.meal_discount)
                if meal_discount < 0:
                    raise UserError(_("Meal Discount cannot be less than 0."))

                
    # Discount Type Selection for Room
    room_is_amount = fields.Boolean(string="Room Discount(Amount)", default=True, tracking=True)

    room_is_percentage = fields.Boolean(string="Room Discount(%)", default=False, tracking=True)

    room_discount_display = fields.Char(
        string="Room Discount Display", tracking=True)

    @api.onchange('room_discount', 'room_is_percentage')
    def _onchange_room_discount(self):
        for record in self:
            if record.room_is_percentage and record.room_discount > 100:
                # record.room_discount = 0  # Cap the percentage to 100%
                pass

    @api.onchange('room_is_percentage')
    def _onchange_room_is_percentage(self):
        if self.room_is_percentage:
            if self.room_price == 0:  # Check if room_price is zero
                raise ValidationError(_("Room price is zero. You cannot select percentage."))
            self.room_discount = (self.room_discount / self.room_price)
            self.room_is_amount = False

        else:
            self.room_is_amount = True
        
    # Discount Type Selection for Meal
    meal_is_amount = fields.Boolean(
        string="Meal Discount as Amount", default=True, tracking=True)
    meal_is_percentage = fields.Boolean(
        string="Meal Discount as Percentage", default=False, tracking=True)

    @api.onchange('meal_is_percentage')
    def _onchange_meal_is_percentage(self):
        if self.meal_is_percentage:
            if self.meal_price == 0:  # Check if room_price is zero
                raise ValidationError(_("Meal price is zero. You cannot select percentage."))
            self.meal_discount = (self.meal_discount / self.meal_price)
            self.meal_is_amount = False

        else:
            self.meal_is_amount = True

    @api.onchange('meal_is_amount')
    def _onchange_meal_is_amount(self):
        if self.meal_is_amount:
            self.meal_discount = self.meal_price * self.meal_discount
            self.meal_is_percentage = False

        else:
            self.meal_is_percentage = True

    # Amount Selection for Room and Meal Prices
    room_amount_selection = fields.Selection([
        ('total', 'All Room'),
        ('line_wise', 'Per Room')
    ], string="Discount Type", default='total', tracking=True)

    meal_amount_selection = fields.Selection([
        ('total', 'All Room'),
        ('line_wise', 'Per Room')
    ], string="Discount Type", default='total', tracking=True)

    @api.onchange('room_is_amount')
    def _onchange_room_is_amount(self):
        _logger.debug(
            f"ROOM IS AMOUNT {self.room_is_amount} {self.room_is_percentage}")
        if self.room_is_amount:
            self.room_discount = self.room_price * self.room_discount
            self.room_is_percentage = False

        else:
            self.room_is_percentage = True

    
    use_price = fields.Boolean(string="Use Price", store=True, tracking=True)
    use_meal_price = fields.Boolean(string="Use Meal Price", store=True, tracking=True)

    @api.onchange('use_price')
    def _onchange_use_price(self):
        if not self.use_price:
            # Set room_price to 0 when use_price is unchecked
            self.room_price = 0.00
            self.room_discount = 0.00

    @api.onchange('use_meal_price')
    def _onchange_use_meal_price(self):
        if not self.use_meal_price:
            # Set meal_price to False when use_meal_price is unchecked
            self.meal_price = 0.00
            self.meal_discount = 0.00
            self.meal_child_price = 0.00

    hide_fields = fields.Boolean(string="Hide Fields", default=False)

    @api.depends('room_line_ids')
    def _compute_room_ids_display(self):
        for record in self:
            room_names = record.room_line_ids.mapped('room_id.name')  # Get all room names
            if room_names:
                record.room_ids_display = ", ".join(room_names)
            else:
                record.room_ids_display = _('Room Not Assigned')
            

    def _search_room_ids_display(self, operator, value):
        return [('room_line_ids.room_id.name', operator, value)]

    @api.depends('room_line_ids')
    def _compute_room_type_display(self):
        for record in self:
            room_types = record.room_line_ids.mapped('hotel_room_type.room_type')
            if room_types:
                record.room_type_display = ", ".join(room_types)
            else:
                # Marked for translation:
                record.room_type_display = _('Room Not Assigned')
            
    parent_booking_name = fields.Char(
        string="Parent Booking Name",
        compute="_compute_parent_booking_name",
        store=True,
        readonly=True, tracking=True
    )

    parent_booking_id = fields.Many2one(
        'room.booking',
        string="Parent Booking",
        help="Reference to the parent booking if this is a child booking.", tracking=True
    )

    child_bookings = fields.One2many(
        'room.booking', 'parent_booking_id', string="Child Bookings")

    @api.depends('parent_booking')
    def _compute_child_bookings(self):
        for record in self:
            if record.name:
                record.child_bookings = self.search(
                    [('parent_booking', '=', record.name)])
            else:
                record.child_bookings = self.env['room.booking']


    @api.depends('parent_booking_id')
    def _compute_parent_booking_name(self):
        """Compute the Parent Booking Name based on parent_booking_id."""
        for record in self:
            record.parent_booking_name = record.parent_booking_id.name if record.parent_booking_id else False

    def assign_room(self):
        """Create child booking when room is assigned"""
        self.ensure_one()

        # Create child booking
        child_vals = {
            'parent_booking_id': self.id,
            'room_line_ids': self.room_line_ids.copy_data(),
            'checkin_date': self.checkin_date,
            'checkout_date': self.checkout_date,
            'state': 'block',
            'adult_ids': [(0, 0, vals) for vals in self.adult_ids.copy_data()],
            'is_room_line_readonly': True
        }

        child_booking = self.create(child_vals)
        return child_booking

    def _get_booking_names(self):
        bookings = self.search([])  # Retrieve all room bookings
        return [(str(booking.id), booking.name) for booking in bookings]

    @api.onchange('rooms_to_add')
    def _onchange_rooms_to_add(self):
        for line in self.room_line_ids:
            line.adult_count = self.adult_count
            line.child_count = self.child_count
            line.infant_count = self.infant_count

    @api.depends('adult_count', 'child_count')
    def _compute_total_people(self):
        for rec in self:
            rec.total_people = rec.adult_count + rec.child_count + rec.infant_count

    
    is_button_clicked = fields.Boolean(
        string="Is Button Clicked", default=False, tracking=True)

    
    def button_find_rooms(self):
        if not self.hotel_room_type:
            raise UserError("Please select your Room Type before proceeding.")

        total_people = self.adult_count + self.child_count

        if not self.checkin_date or not self.checkout_date:
            raise UserError(
                'Check-in and Check-out dates must be set before finding rooms.')

        checkin_date = self.checkin_date
        checkout_date = self.checkout_date
        duration = (checkout_date - checkin_date).days + \
                   (checkout_date - checkin_date).seconds / (24 * 3600)

        if duration <= 0:
            raise UserError('Checkout date must be later than Check-in date.')

        total_available = self.env['hotel.room'].search_count([
            ('status', '=', 'available'),
            ('room_type_name', '=', self.hotel_room_type.id)
        ])
        if self.room_count > total_available:
            raise UserError(
                f'Not enough rooms available for the selected room type. Total available rooms: {total_available}')

        new_rooms = self._find_rooms_for_capacity()
        room_lines = []
        if new_rooms:
            for room in new_rooms:
                room_lines.append((0, 0, {
                    'room_id': False,
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'uom_qty': duration,
                    'adult_count': self.adult_count,
                    'child_count': self.child_count
                }))
            self.write({'room_line_ids': room_lines})
        else:
            raise UserError('No rooms found matching the selected criteria.')

    @api.model
    def _find_rooms_for_capacity(self):
        current_room_ids = self.room_line_ids.mapped('room_id.id')
        total_people = self.adult_count + self.child_count
        rooms_to_add = self.room_count

        print(current_room_ids, total_people, rooms_to_add)

        available_rooms = self.env['hotel.room'].search([
            ('status', '=', 'available'),
            ('id', 'not in', current_room_ids),
            ('num_person', '>=', total_people),
            ('room_type_name', '=', self.hotel_room_type.id),
        ], limit=rooms_to_add)

        print("available_rooms", available_rooms)

        return available_rooms

    @api.model
    def check_room_availability_all_hotels_split_across_type(
            self,
            checkin_date,
            checkout_date,
            room_count,
            adult_count,
            hotel_room_type_id=None
    ):
        # Ensure checkin_date and checkout_date are date objects
        checkin_date = self._convert_to_date(checkin_date)
        checkout_date = self._convert_to_date(checkout_date)

        results = []
        total_available_rooms = 0  # Sum of total available rooms

        # Retrieve companies from hotel inventory
        # companies = self.env['hotel.inventory'].read_group([], ['company_id'], ['company_id'])
        company_id = self.env.context.get('company_id', self.env.company.id)
        domain = [('company_id', '=', company_id)] if company_id else []
        companies = self.env['hotel.inventory'].read_group(domain, ['company_id'], ['company_id'])

        # Retrieve all room types and map them by ID
        room_types = self.env['room.type'].search_read(
            [('obsolete', '=', False)], [], order='user_sort ASC')
        # print('room type', room_types)
        room_types_dict = {room_type['id']: room_type for room_type in room_types}

        # Calculate total available rooms
        for company in companies:
            loop_company_id = company['company_id'][0]
            total_available_rooms += self._calculate_available_rooms(
                loop_company_id,
                checkin_date,
                checkout_date,
                adult_count,
                hotel_room_type_id,
                room_types_dict
            )

            if total_available_rooms == 99999:  # Unlimited rooms
                break

        # Handle insufficient rooms
        if total_available_rooms < room_count:
            wizard_result = self._trigger_waiting_list_wizard(
                room_count, total_available_rooms, hotel_room_type_id
            )
            return (total_available_rooms, [wizard_result])

        # Proceed with allocation
        return total_available_rooms, self._allocate_rooms(
            companies,
            room_count,
            checkin_date,
            checkout_date,
            adult_count,
            hotel_room_type_id,
            room_types_dict
        )


    def _convert_to_date(self, date_value):
        """Helper to convert date strings or datetime objects to date."""
        if isinstance(date_value, (datetime, date)):
            return date_value.date() if isinstance(date_value, datetime) else date_value
        elif isinstance(date_value, str):
            return datetime.strptime(date_value, "%Y-%m-%d").date()
        return date_value


    def _allocate_rooms(self, companies, room_count, checkin_date, checkout_date, adult_count, hotel_room_type_id,
                        room_types_dict):
        """Allocate rooms based on availability."""
        results = []
        remaining_rooms = room_count
        # today_date = datetime.today().strftime('%Y-%m-%d')
        today_date = self.env.company.system_date.date().strftime('%Y-%m-%d')

        for company in companies:
            loop_company_id = company['company_id'][0]
            room_availabilities_domain = [
                ('company_id', '=', loop_company_id),
                # ('pax', '>=', adult_count),
            ]

            if hotel_room_type_id:
                room_availabilities_domain.append(
                    ('room_type', '=', hotel_room_type_id))
            else:
                # If no room_type_id is provided, filter by room types in room_types_dict
                room_type_ids = list(room_types_dict.keys())
                if room_type_ids:
                    room_availabilities_domain.append(('room_type', 'in', room_type_ids))

            room_availabilities = self.env['hotel.inventory'].search_read(room_availabilities_domain,
                                                                          ['room_type', 'total_room_count',
                                                                           'overbooking_allowed', 'overbooking_rooms'],
                                                                          order='room_type ASC'
                                                                          )
            grouped_availabilities = {}
            for availability in room_availabilities:
                room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
                    availability['room_type']
                if room_type_id not in grouped_availabilities:
                    grouped_availabilities[room_type_id] = {
                        'total_room_count': 0,
                        'overbooking_allowed': availability['overbooking_allowed'],
                        # 'overbooking_rooms': availability['overbooking_rooms'],
                        'overbooking_rooms': 0,
                        'entries': []
                    }
                grouped_availabilities[room_type_id]['total_room_count'] += availability['total_room_count']
                # Sum overbooking rooms
                grouped_availabilities[room_type_id]['overbooking_rooms'] += availability['overbooking_rooms']
                grouped_availabilities[room_type_id]['entries'].append(
                    availability)

            for room_type_id, availability in grouped_availabilities.items():
                
                #TODO ADD Domain for Out of Order and rooms on hold  
                booked_rooms = self.env['room.booking'].search_count([
                    ('hotel_room_type', '=', room_type_id),
                    # ('booking_id.room_count', '=', 1),
                    # ('adult_count', '=', availability['pax']),
                    ('checkin_date', '<', checkout_date),
                    ('checkout_date', '>', checkin_date),
                    # ('checkout_date', '!=', today_date), 
                    ('checkout_date', 'not like', today_date + '%'),
                    ('state', 'in', ['check_in', 'block','confirmed']),
                    # Exclude allocated lines
                    ('id', 'not in', self.env.context.get('already_allocated', []))
                ])

                rooms_on_hold_count = self.env['rooms.on.hold.management.front.desk'].search_count([
                    ('company_id', '=', self.env.company.id),
                    ('room_type', '=', room_type_id),
                    ('from_date', '<=', checkout_date),
                    ('to_date', '>=', checkin_date)
                ])
                _logger.debug(f"Rooms on hold count: {rooms_on_hold_count}")

                # Count out-of-order rooms for the current company and matching room type
                out_of_order_rooms_count = self.env['out.of.order.management.front.desk'].search_count([
                    ('company_id', '=', self.env.company.id),
                    ('room_type', '=', room_type_id),
                    ('from_date', '<=', checkout_date),
                    ('to_date', '>=', checkin_date)
                ])
                confirmed_bookings = self.env['room.booking'].search([
                    ('hotel_room_type', '=', room_type_id),
                    ('checkin_date', '<', checkout_date),
                    ('checkout_date', '>', checkin_date),
                    ('checkout_date', 'not like', today_date + '%'),
                    ('state', '=', 'confirmed'),
                    ('id', 'not in', self.env.context.get('already_allocated', []))
                ])
                # Get the count of room_line_ids for confirmed bookings
                confirmed_room_lines_count = sum(len(booking.room_line_ids) for booking in confirmed_bookings)
                if sum(len(booking.room_line_ids) for booking in confirmed_bookings) > 0:
                    confirmed_room_lines_count -= 1
                
                booked_rooms = booked_rooms + rooms_on_hold_count + out_of_order_rooms_count+confirmed_room_lines_count

                if availability['overbooking_allowed']:
                    available_rooms = max(
                        availability['total_room_count'] - booked_rooms + availability['overbooking_rooms'], 0)
                else:
                    available_rooms = max(
                        availability['total_room_count'] - booked_rooms, 0)
                # print("line 2582", remaining_rooms, available_rooms)
                current_rooms_reserved = min(remaining_rooms, available_rooms)

                # Track allocated bookings in context
                if current_rooms_reserved > 0:
                    allocated_lines = self.env['room.booking.line'].search([
                        ('hotel_room_type', '=', room_type_id),
                        # ('booking_id.room_count', '=', 1),
                        # ('adult_count', '=', availability['pax']),
                        ('checkin_date', '<', checkout_date),
                        ('checkout_date', '>', checkin_date),
                        ('booking_id.state', 'in', [
                            'confirmed', 'check_in', 'block']),
                    ], limit=current_rooms_reserved)

                    already_allocated_ids = self.env.context.get(
                        'already_allocated', [])
                    already_allocated_ids += allocated_lines.ids
                    self = self.with_context(
                        already_allocated=already_allocated_ids)

                results.append({
                    'company_id': loop_company_id,
                    'room_type': room_type_id,
                    # 'pax': availability['pax'],
                    'rooms_reserved': current_rooms_reserved,
                    'available_rooms': 'Unlimited' if available_rooms == 99999 else str(available_rooms),
                    'description': room_types_dict.get(room_type_id, {}).get('description', ''),
                    'user_sort': room_types_dict.get(room_type_id, {}).get('user_sort', ''),
                    'abbreviation': room_types_dict.get(room_type_id, {}).get('abbreviation', ''),
                })

                remaining_rooms -= current_rooms_reserved
                if remaining_rooms <= 0:
                    break

            if remaining_rooms <= 0:
                break

        return results

    def _trigger_waiting_list_wizard(self, room_count, total_available_rooms, hotel_room_type_id):
        """Trigger a wizard for the waiting list decision."""
        room_type_name = ''
        if hotel_room_type_id:
            room_type_record = self.env['room.type'].browse(hotel_room_type_id)
            room_type_name = room_type_record.description or room_type_record.room_type

    
        message = _(
            '<div style="text-align: center; font-size: 14px; line-height: 1.6; padding: 10px; white-space: nowrap;">'
            '<strong>Room Availability:</strong> You requested <strong>%s</strong> room(s) of type '
            '<strong>%s</strong>, but only <strong>%s</strong> room(s) are available.<br>'
            'Would you like to send this booking to the <strong>Waiting List</strong>?'
            '</div>'
        ) % (
            room_count,
            room_type_name,
            total_available_rooms,
        )

        return {
            'type': 'ir.actions.act_window',
            'name': _('Room Availability'),
            'res_model': 'room.availability.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_room_booking_id': self.id,
                'default_message': message,
                'default_previous_room_count': self.previous_room_count,  
            },
        }

    def _calculate_available_rooms(self, company_id, checkin_date, checkout_date, adult_count, hotel_room_type_id,room_types_dict):
        """Calculate available rooms for a company."""
        _logger.debug(f"Starting room calculation for company_id: {company_id}, checkin_date: {checkin_date}, checkout_date: {checkout_date}, adult_count: {adult_count}, hotel_room_type_id: {hotel_room_type_id}")

        room_availabilities_domain = [
            ('company_id', '=', company_id),
        ]
        _logger.debug(f"Initial room_availabilities_domain: {room_availabilities_domain}")

        # today_date = datetime.today().strftime('%Y-%m-%d')
        today_date = self.env.company.system_date.date().strftime('%Y-%m-%d')
        _logger.debug(f"Today's date: {today_date}")

        if hotel_room_type_id:
            room_availabilities_domain.append(('room_type', '=', hotel_room_type_id))
            _logger.debug(f"Added room_type to domain: {hotel_room_type_id}")
        else:
            room_type_ids = list(room_types_dict.keys())
            if room_type_ids:
                room_availabilities_domain.append(('room_type', 'in', room_type_ids))
                _logger.debug(f"Added multiple room_types to domain: {room_type_ids}")

        _logger.debug(f"Final room_availabilities_domain: {room_availabilities_domain}")

        room_availabilities = self.env['hotel.inventory'].search_read(room_availabilities_domain,
                                                                    ['room_type', 'total_room_count',
                                                                    'overbooking_allowed', 'overbooking_rooms'],
                                                                    order='room_type ASC')

        grouped_availabilities = {}

        for availability in room_availabilities:
            room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else availability['room_type']

            if room_type_id not in grouped_availabilities:
                grouped_availabilities[room_type_id] = {
                    'total_room_count': 0,
                    'overbooking_allowed': availability['overbooking_allowed'],
                    'overbooking_rooms': 0,
                    'entries': []
                }
            grouped_availabilities[room_type_id]['total_room_count'] += availability['total_room_count']
            grouped_availabilities[room_type_id]['overbooking_rooms'] += availability['overbooking_rooms']
            grouped_availabilities[room_type_id]['entries'].append(availability)


        total_available_rooms = 0
        for room_type_id, availability in grouped_availabilities.items():
            _logger.debug(f"Calculating booked rooms for room_type_id: {room_type_id}")

            booked_rooms = self.env['room.booking'].search_count([
                ('hotel_room_type', '=', room_type_id),
                ('checkin_date', '<', checkout_date),
                ('checkout_date', '>', checkin_date),
                ('checkout_date', 'not like', today_date + '%'),
                ('state', 'in', ['check_in', 'block', 'confirmed']),
                ('id', 'not in', self.env.context.get('already_allocated', []))
            ])
            _logger.debug(f"Booked rooms count: {booked_rooms}")

            rooms_on_hold_count = self.env['rooms.on.hold.management.front.desk'].search_count([
                ('company_id', '=', self.env.company.id),
                ('room_type', '=', room_type_id),
                ('from_date', '<=', checkout_date),
                ('to_date', '>=', checkin_date)
            ])
            _logger.debug(f"Rooms on hold count: {rooms_on_hold_count}")

            out_of_order_rooms_count = self.env['out.of.order.management.front.desk'].search_count([
                ('company_id', '=', self.env.company.id),
                ('room_type', '=', room_type_id),
                ('from_date', '<=', checkout_date),
                ('to_date', '>=', checkin_date)
            ])

            confirmed_bookings = self.env['room.booking'].search([
                    ('hotel_room_type', '=', room_type_id),
                    ('checkin_date', '<=', checkout_date),
                    ('checkout_date', '>=', checkin_date),
                    ('checkout_date', 'not like', today_date + '%'),
                    ('state', '=', 'confirmed'),
                    ('id', 'not in', self.env.context.get('already_allocated', []))
                ])

            confirmed_room_lines_count = sum(len(booking.room_line_ids) for booking in confirmed_bookings)
            if sum(len(booking.room_line_ids) for booking in confirmed_bookings) > 0:
                confirmed_room_lines_count -= 1

                
            booked_rooms = booked_rooms + rooms_on_hold_count + out_of_order_rooms_count + confirmed_room_lines_count
                

            # booked_rooms += rooms_on_hold_count + out_of_order_rooms_count

            if availability['overbooking_allowed']:
                available_rooms = max(availability['total_room_count'] - booked_rooms + availability['overbooking_rooms'], 0)
                print(f"Available rooms with overbooking: {available_rooms}")

                if availability['overbooking_rooms'] == 0:
                    print("Overbooking rooms are zero, returning unlimited rooms")
                    return 99999  # Unlimited rooms
            else:
                available_rooms = max(availability['total_room_count'] - booked_rooms, 0)

            total_available_rooms += available_rooms

        return total_available_rooms

    @api.onchange('state')
    def _onchange_state(self):
        if self.state == 'block':
            for line in self.room_line_ids:
                line._update_inventory(
                    line.room_type_name.id, self.company_id.id, increment=False)
        elif self.state == 'confirmed':
            for line in self.room_line_ids:
                line._update_inventory(
                    line.room_type_name.id, self.company_id.id, increment=False)
        else:
            for line in self.room_line_ids:
                line._update_inventory(
                    line.room_type_name.id, self.company_id.id, increment=True)

    # def action_assign_all_rooms(self):
    #     for rec in self:
    #         room_types = {line.hotel_room_type.id for line in rec.room_line_ids if line.hotel_room_type}
    #         if len(room_types) > 1:
    #             raise UserError(_("You cannot auto assign rooms with different Room Types."))
    #     today = self.env.company.system_date.date()
    #     current_time = datetime.now().time()
    #     get_system_date = datetime.combine(today, current_time)

    #     overall_start = datetime.now()
    #     _logger.debug("Starting optimized assign_all_rooms for %s bookings", len(self))

    #     # PERFORMANCE: Pre-compute data for all bookings to avoid N+1 queries
    #     all_companies = self.mapped('company_id')
    #     all_room_types = self.mapped('hotel_room_type')

    #     # PERFORMANCE: Single mega-query for all booked rooms across all companies
    #     if self:
    #         min_checkin = min(self.mapped('checkin_date'))
    #         max_checkout = max(self.mapped('checkout_date'))

    #         # Use raw SQL for better performance
    #         self.env.cr.execute("""
    #             SELECT DISTINCT rbl.room_id, rb.company_id 
    #             FROM room_booking_line rbl
    #             INNER JOIN room_booking rb ON rbl.booking_id = rb.id
    #             WHERE rbl.room_id IS NOT NULL
    #             AND rb.checkin_date < %s
    #             AND rb.checkout_date > %s  
    #             AND rb.state IN ('confirmed', 'block', 'check_in')
    #             AND rb.company_id IN %s
    #         """, (max_checkout, min_checkin, tuple(all_companies.ids)))

    #         booked_rooms_by_company = {}
    #         for room_id, company_id in self.env.cr.fetchall():
    #             if company_id not in booked_rooms_by_company:
    #                 booked_rooms_by_company[company_id] = set()
    #             booked_rooms_by_company[company_id].add(room_id)
    #     else:
    #         booked_rooms_by_company = {}

    #     # PERFORMANCE: Pre-fetch all available rooms using SQL
    #     available_rooms_cache = {}
    #     for company in all_companies:
    #         booked_set = booked_rooms_by_company.get(company.id, set())
    #         for room_type in all_room_types:
    #             if booked_set:
    #                 self.env.cr.execute("""
    #                     SELECT id FROM hotel_room 
    #                     WHERE company_id = %s 
    #                     AND room_type_name = %s 
    #                     AND active = true
    #                     AND id NOT IN %s
    #                     ORDER BY id
    #                 """, (company.id, room_type.id, tuple(booked_set)))
    #             else:
    #                 self.env.cr.execute("""
    #                     SELECT id FROM hotel_room 
    #                     WHERE company_id = %s 
    #                     AND room_type_name = %s 
    #                     AND active = true
    #                     ORDER BY id
    #                 """, (company.id, room_type.id))

    #             available_rooms_cache[(company.id, room_type.id)] = [r[0] for r in self.env.cr.fetchall()]

    #     # OPTIMIZED: Separate single-room and multi-room bookings for different processing
    #     single_room_bookings = []
    #     multi_room_bookings = []

    #     for booking in self:
    #         # Validations first
    #         if booking.state != 'confirmed':
    #             _logger.warning("Booking %s is not confirmed", booking.name)
    #             raise UserError(_("Booking must be Confirmed first."))
    #         if not booking.room_line_ids:
    #             _logger.warning("No room lines found for booking %s", booking.name)
    #             raise UserError("No room lines to assign.")

    #         if len(booking.room_line_ids) == 1:
    #             single_room_bookings.append(booking)
    #         else:
    #             multi_room_bookings.append(booking)

    #     # PERFORMANCE: Batch process all single-room bookings
    #     if single_room_bookings:
    #         _logger.debug("Processing %s single-room bookings in batch", len(single_room_bookings))

    #         # Collect all single-room updates for mega-batch processing
    #         single_room_line_updates = []
    #         single_booking_updates = []
    #         single_history_inserts = []

    #         for booking in single_room_bookings:
    #             available_room_ids = available_rooms_cache.get((booking.company_id.id, booking.hotel_room_type.id), [])
    #             if not available_room_ids:
    #                 raise UserError(_("No available room for type %s") % booking.hotel_room_type)

    #             # Collect for mega-batch SQL operations
    #             single_room_line_updates.append((booking.room_line_ids.ids[0], available_room_ids[0]))
    #             single_booking_updates.append(booking.id)
    #             single_history_inserts.append(
    #                 (booking.room_line_ids.ids[0], self.env.uid, self.env.uid, 'block', get_system_date))

    #         # PERFORMANCE: Execute all single-room updates in mega-batches using SQL
    #         if single_room_line_updates:
    #             # Batch update room assignments
    #             room_line_updates_sql = "UPDATE room_booking_line SET room_id = CASE id "
    #             room_line_params = []
    #             room_line_ids = []

    #             for line_id, room_id in single_room_line_updates:
    #                 room_line_updates_sql += "WHEN %s THEN %s "
    #                 room_line_params.extend([line_id, room_id])
    #                 room_line_ids.append(line_id)

    #             room_line_updates_sql += "END, state_ = 'block' WHERE id IN %s"
    #             room_line_params.append(tuple(room_line_ids))

    #             self.env.cr.execute(room_line_updates_sql, room_line_params)

    #             # Batch update booking states
    #             self.env.cr.execute("""
    #                 UPDATE room_booking 
    #                 SET state = 'block', show_in_tree = true 
    #                 WHERE id IN %s
    #             """, (tuple(single_booking_updates),))

    #             # Batch insert history records
    #             if single_history_inserts:
    #                 self.env.cr.executemany("""
    #                     INSERT INTO room_booking_line_status 
    #                     (booking_line_id, create_uid, write_uid, status, change_time, create_date, write_date)
    #                     VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
    #                 """, single_history_inserts)

    #     # PERFORMANCE: Process multi-room bookings with optimized batching
    #     if multi_room_bookings:
    #         _logger.debug("Processing %s multi-room bookings", len(multi_room_bookings))

    #         # FIXED: Use dictionaries to store temporary data instead of dynamic attributes
    #         temp_booking_data = {}  # booking_id -> {'forecast_data': [...], 'vat_data': (...)}

    #         # Collect all operations for final batch execution
    #         batch_forecast_updates = []
    #         batch_forecast_creates = []
    #         batch_booking_updates = []
    #         batch_history_inserts = []
    #         stored_proc_calls = []
    #         sequence_updates_by_company = {}

    #         for booking in multi_room_bookings:
    #             start_time = datetime.now()
    #             room_count = len(booking.room_line_ids)
    #             # _logger.debug("Processing booking %s with %s rooms", booking.name, room_count)

    #             # Collect forecast updates for batch processing
    #             forecast_data = []
    #             for fc in booking.rate_forecast_ids:
    #                 divided = {
    #                     'date': fc.date,
    #                     'rate': fc.rate / room_count,
    #                     'meals': fc.meals / room_count,
    #                     'packages': fc.packages / room_count,
    #                     'fixed_post': fc.fixed_post / room_count,
    #                     'total': fc.total / room_count,
    #                     'before_discount': fc.before_discount / room_count,
    #                 }
    #                 forecast_data.append(divided)
    #                 batch_forecast_updates.append((fc.id, divided))

    #             # Store VAT/municipality totals for later distribution
    #             total_vat = booking.total_vat or 0.0
    #             total_mun = booking.total_municipality_tax or 0.0
    #             total_unt = booking.total_untaxed or 0.0

    #             # CRITICAL: Call stored procedure (still needs to be individual for business logic)
    #             _logger.debug("Calling stored procedure for booking %s", booking.id)
    #             # self.env.cr.execute("CALL split_confirmed_booking(%s)", (booking.id,))
    #             try:
    #                 self.env.cr.execute("CALL split_confirmed_booking(%s)", (booking.id,))
    #             except psycopg2.Error as e:
    #                 msg = str(e)
    #                 if "No available room for type" in msg:
    #                     raise ValidationError(
    #                         _("No rooms can be allocated for the selected dates."))
    #                 else:
    #                     raise ValidationError(_("Booking assignment failed: %s") % msg)
    #             stored_proc_calls.append(booking.id)

    #             temp_booking_data[booking.id] = {
    #                 'forecast_data': forecast_data,
    #                 'vat_data': (total_vat, total_mun, total_unt)
    #             }

    #             # Collect sequence updates by company (avoid duplicates)
    #             if booking.company_id.id not in sequence_updates_by_company:
    #                 sequence_updates_by_company[booking.company_id.id] = booking.company_id

    #             end_time = datetime.now()
    #             duration = (end_time - start_time).total_seconds()
    #             _logger.debug("Processed booking %s in %.2fs", booking.name, duration)

    #         # PERFORMANCE: Batch process all child bookings after all stored procedures
    #         if stored_proc_calls:
    #             _logger.debug("Processing child bookings for %s parent bookings", len(stored_proc_calls))

    #             # Single query for ALL child bookings
    #             self.env.cr.execute("""
    #                 SELECT id, parent_booking_id FROM room_booking 
    #                 WHERE parent_booking_id IN %s
    #             """, (tuple(stored_proc_calls),))

    #             children_by_parent = {}
    #             for child_id, parent_id in self.env.cr.fetchall():
    #                 if parent_id not in children_by_parent:
    #                     children_by_parent[parent_id] = []
    #                 children_by_parent[parent_id].append(child_id)

    #             # Process all child forecasts and VAT distributions in batch
    #             for booking in multi_room_bookings:
    #                 if booking.id in children_by_parent:
    #                     child_ids = children_by_parent[booking.id]
                        
    #                     # FIXED: Get data from dictionary instead of dynamic attributes
    #                     booking_data = temp_booking_data[booking.id]
    #                     forecast_data = booking_data['forecast_data']
    #                     total_vat, total_mun, total_unt = booking_data['vat_data']
    #                     self.env.cr.execute("""
    #                             DELETE FROM room_rate_forecast 
    #                             WHERE room_booking_id IN %s
    #                         """, (tuple(child_ids),))
    #                     _logger.debug("Deleted existing forecast rates for child bookings %s", child_ids)

    #                     # Create child forecasts
    #                     for child_id in child_ids:
    #                         for data in forecast_data:
    #                             vals = dict(data, room_booking_id=child_id)
    #                             batch_forecast_creates.append(vals)

    #                     all_booking_ids = [booking.id] + child_ids
    #                     per_vat = total_vat / len(all_booking_ids)
    #                     per_mun = total_mun / len(all_booking_ids)
    #                     per_unt = total_unt / len(all_booking_ids)

    #                     for booking_id in all_booking_ids:
    #                         batch_booking_updates.append((booking_id, {
    #                             'total_vat': per_vat,
    #                             'total_municipality_tax': per_mun,
    #                             'total_untaxed': per_unt,
    #                         }))

    #                     # Collect history inserts for all related lines
    #                     self.env.cr.execute("""
    #                         SELECT id FROM room_booking_line 
    #                         WHERE booking_id IN %s
    #                     """, (tuple(all_booking_ids),))

    #                     for (line_id,) in self.env.cr.fetchall():
    #                         batch_history_inserts.append((
    #                             line_id, self.env.uid, self.env.uid, 'block', get_system_date
    #                         ))

    #         # PERFORMANCE: Execute all batch operations for multi-room bookings
    #         _logger.debug("Executing batch operations for multi-room bookings...")

    #         # Batch forecast updates using efficient SQL
    #         if batch_forecast_updates:
    #             _logger.debug("Executing %s forecast updates", len(batch_forecast_updates))
    #             for forecast_id, values in batch_forecast_updates:
    #                 self.env.cr.execute("""
    #                     UPDATE room_rate_forecast 
    #                     SET rate = %s, meals = %s, packages = %s, fixed_post = %s, 
    #                         total = %s, before_discount = %s
    #                     WHERE id = %s
    #                 """, (values['rate'], values['meals'], values['packages'],
    #                       values['fixed_post'], values['total'], values['before_discount'], forecast_id))

    #         # Batch forecast creation
    #         if batch_forecast_creates:
    #             _logger.debug("Creating %s child forecasts", len(batch_forecast_creates))
    #             # self.env['room.rate.forecast'].create(batch_forecast_creates)
    #             _logger.debug("Creating %s child forecasts using bulk SQL", len(batch_forecast_creates))

    #             # PERFORMANCE: Use raw SQL bulk insert instead of ORM create()
    #             # This reduces execution time from ~90s to ~2-5s for large datasets
    #             values_list = []
    #             for vals in batch_forecast_creates:
    #                 values_list.append((
    #                     vals.get('room_booking_id'),
    #                     vals.get('date'),  # Note: field is 'date' not 'report_date'
    #                     vals.get('rate', 0),
    #                     vals.get('meals', 0),
    #                     vals.get('packages', 0),
    #                     vals.get('fixed_post', 0),
    #                     vals.get('total', 0),
    #                     vals.get('before_discount', 0),
    #                     self.env.uid,  # create_uid
    #                     self.env.uid  # write_uid
    #                 ))

    #             # Execute bulk insert - dramatically faster than ORM create()
    #             self.env.cr.executemany("""
    #                 INSERT INTO room_rate_forecast 
    #                 (room_booking_id, date, rate, meals, packages, fixed_post, total, before_discount, 
    #                  create_date, write_date, create_uid, write_uid)
    #                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
    #             """, values_list)

    #         # Batch booking updates using SQL
    #         if batch_booking_updates:
    #             _logger.debug("Executing %s booking updates", len(batch_booking_updates))
    #             for booking_id, values in batch_booking_updates:
    #                 self.env.cr.execute("""
    #                     UPDATE room_booking 
    #                     SET total_vat = %s, total_municipality_tax = %s
    #                     WHERE id = %s
    #                 """, (values['total_vat'], values['total_municipality_tax'], booking_id))

    #         # Batch history inserts
    #         if batch_history_inserts:
    #             _logger.debug("Inserting %s history records", len(batch_history_inserts))
    #             self.env.cr.executemany("""
    #                 INSERT INTO room_booking_line_status 
    #                 (booking_line_id, create_uid, write_uid, status, change_time, create_date, write_date)
    #                 VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
    #             """, batch_history_inserts)

    #     # PERFORMANCE: Single cache invalidation and compute at the very end
    #     self.env.invalidate_all()
    #     # PERFORMANCE: Batch compute operations using SQL where possible
    #     if self.ids:
    #         # Update room line states
    #         self.env.cr.execute("""
    #             UPDATE room_booking_line 
    #             SET state_ = 'block' 
    #             WHERE booking_id IN %s AND room_id IS NOT NULL
    #         """, (tuple(self.ids),))

    #         # Update booking visibility
    #         self.env.cr.execute("""
    #             UPDATE room_booking 
    #             SET show_in_tree = true 
    #             WHERE id IN %s
    #         """, (tuple(self.ids),))

    #     overall_end = datetime.now()
    #     total_duration = (overall_end - overall_start).total_seconds()
    #     _logger.debug("COMPLETED optimized assign_all_rooms for %s bookings in %.2fs",
    #                  len(self), total_duration)

    
    def action_assign_all_rooms(self, available_rooms=None):
        for rec in self:
            room_types = {line.hotel_room_type.id for line in rec.room_line_ids if line.hotel_room_type}
            if len(room_types) > 1:
                raise UserError(_("You cannot auto assign rooms with different Room Types."))
        today = self.env.company.system_date.date()
        current_time = datetime.now().time()
        get_system_date = datetime.combine(today, current_time)

        overall_start = datetime.now()
        _logger.debug("Starting optimized assign_all_rooms for %s bookings", len(self))

        # PERFORMANCE: Pre-compute data for all bookings to avoid N+1 queries
        all_companies = self.mapped('company_id')
        all_room_types = self.mapped('hotel_room_type')

        # PERFORMANCE: Single mega-query for all booked rooms across all companies
        if self:
            min_checkin = min(self.mapped('checkin_date'))
            max_checkout = max(self.mapped('checkout_date'))

            # Use raw SQL for better performance
            self.env.cr.execute("""
                SELECT DISTINCT rbl.room_id, rb.company_id 
                FROM room_booking_line rbl
                INNER JOIN room_booking rb ON rbl.booking_id = rb.id
                WHERE rbl.room_id IS NOT NULL
                AND rb.checkin_date < %s
                AND rb.checkout_date > %s  
                AND rb.state IN ('confirmed', 'block', 'check_in')
                AND rb.company_id IN %s
            """, (max_checkout, min_checkin, tuple(all_companies.ids)))

            booked_rooms_by_company = {}
            for room_id, company_id in self.env.cr.fetchall():
                if company_id not in booked_rooms_by_company:
                    booked_rooms_by_company[company_id] = set()
                booked_rooms_by_company[company_id].add(room_id)
        else:
            booked_rooms_by_company = {}

        # PERFORMANCE: Pre-fetch all available rooms using SQL
        available_rooms_cache = {}

        if available_rooms:
            # Wizard passed explicit available rooms → use them directly
            for booking in self:
                available_rooms_cache[(booking.company_id.id, booking.hotel_room_type.id)] = available_rooms.ids
        else:
            for company in all_companies:
                booked_set = booked_rooms_by_company.get(company.id, set())
                for room_type in all_room_types:
                    if booked_set:
                        self.env.cr.execute("""
                            SELECT id FROM hotel_room 
                            WHERE company_id = %s 
                            AND room_type_name = %s 
                            AND active = true
                            AND id NOT IN %s
                            ORDER BY id
                        """, (company.id, room_type.id, tuple(booked_set)))
                    else:
                        self.env.cr.execute("""
                            SELECT id FROM hotel_room 
                            WHERE company_id = %s 
                            AND room_type_name = %s 
                            AND active = true
                            ORDER BY id
                        """, (company.id, room_type.id))

                    available_rooms_cache[(company.id, room_type.id)] = [r[0] for r in self.env.cr.fetchall()]

        # OPTIMIZED: Separate single-room and multi-room bookings for different processing
        single_room_bookings = []
        multi_room_bookings = []

        for booking in self:
            # Validations first
            if booking.state != 'confirmed':
                _logger.warning("Booking %s is not confirmed", booking.name)
                raise UserError(_("Booking must be Confirmed first."))
            if not booking.room_line_ids:
                _logger.warning("No room lines found for booking %s", booking.name)
                raise UserError("No room lines to assign.")

            if len(booking.room_line_ids) == 1:
                single_room_bookings.append(booking)
            else:
                multi_room_bookings.append(booking)

        # PERFORMANCE: Batch process all single-room bookings
        if single_room_bookings:
            _logger.debug("Processing %s single-room bookings in batch", len(single_room_bookings))

            # Collect all single-room updates for mega-batch processing
            single_room_line_updates = []
            single_booking_updates = []
            single_history_inserts = []

            for booking in single_room_bookings:
                available_room_ids = available_rooms_cache.get((booking.company_id.id, booking.hotel_room_type.id), [])
                if not available_room_ids:
                    raise UserError(_("No available room for type %s") % booking.hotel_room_type)

                # Collect for mega-batch SQL operations
                single_room_line_updates.append((booking.room_line_ids.ids[0], available_room_ids[0]))
                single_booking_updates.append(booking.id)
                single_history_inserts.append(
                    (booking.room_line_ids.ids[0], self.env.uid, self.env.uid, 'block', get_system_date))

            # PERFORMANCE: Execute all single-room updates in mega-batches using SQL
            if single_room_line_updates:
                # Batch update room assignments
                room_line_updates_sql = "UPDATE room_booking_line SET room_id = CASE id "
                room_line_params = []
                room_line_ids = []

                for line_id, room_id in single_room_line_updates:
                    room_line_updates_sql += "WHEN %s THEN %s "
                    room_line_params.extend([line_id, room_id])
                    room_line_ids.append(line_id)

                room_line_updates_sql += "END, state_ = 'block' WHERE id IN %s"
                room_line_params.append(tuple(room_line_ids))

                self.env.cr.execute(room_line_updates_sql, room_line_params)

                # Batch update booking states
                self.env.cr.execute("""
                    UPDATE room_booking 
                    SET state = 'block', show_in_tree = true 
                    WHERE id IN %s
                """, (tuple(single_booking_updates),))

                # Batch insert history records
                if single_history_inserts:
                    self.env.cr.executemany("""
                        INSERT INTO room_booking_line_status 
                        (booking_line_id, create_uid, write_uid, status, change_time, create_date, write_date)
                        VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                    """, single_history_inserts)

        # PERFORMANCE: Process multi-room bookings with optimized batching
        if multi_room_bookings:
            _logger.debug("Processing %s multi-room bookings", len(multi_room_bookings))

            # FIXED: Use dictionaries to store temporary data instead of dynamic attributes
            temp_booking_data = {}  # booking_id -> {'forecast_data': [...], 'vat_data': (...)}

            # Collect all operations for final batch execution
            batch_forecast_updates = []
            batch_forecast_creates = []
            batch_booking_updates = []
            batch_history_inserts = []
            stored_proc_calls = []
            sequence_updates_by_company = {}

            for booking in multi_room_bookings:
                start_time = datetime.now()
                room_count = len(booking.room_line_ids)

                # Collect forecast updates for batch processing
                forecast_data = []
                for fc in booking.rate_forecast_ids:
                    divided = {
                        'date': fc.date,
                        'rate': fc.rate / room_count,
                        'meals': fc.meals / room_count,
                        'packages': fc.packages / room_count,
                        'fixed_post': fc.fixed_post / room_count,
                        'total': fc.total / room_count,
                        'before_discount': fc.before_discount / room_count,
                    }
                    forecast_data.append(divided)
                    batch_forecast_updates.append((fc.id, divided))

                # Store VAT/municipality totals for later distribution
                total_vat = booking.total_vat or 0.0
                total_mun = booking.total_municipality_tax or 0.0
                total_unt = booking.total_untaxed or 0.0

                # CRITICAL: Call stored procedure (still needs to be individual for business logic)
                _logger.debug("Calling stored procedure for booking %s", booking.id)
                try:
                    self.env.cr.execute("CALL split_confirmed_booking(%s)", (booking.id,))
                except psycopg2.Error as e:
                    msg = str(e)
                    if "No available room for type" in msg:
                        raise ValidationError(
                            _("No rooms can be allocated for the selected dates."))
                    else:
                        raise ValidationError(_("Booking assignment failed: %s") % msg)
                stored_proc_calls.append(booking.id)

                temp_booking_data[booking.id] = {
                    'forecast_data': forecast_data,
                    'vat_data': (total_vat, total_mun, total_unt)
                }

                if booking.company_id.id not in sequence_updates_by_company:
                    sequence_updates_by_company[booking.company_id.id] = booking.company_id

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                _logger.debug("Processed booking %s in %.2fs", booking.name, duration)

            if stored_proc_calls:
                _logger.debug("Processing child bookings for %s parent bookings", len(stored_proc_calls))

                self.env.cr.execute("""
                    SELECT id, parent_booking_id FROM room_booking 
                    WHERE parent_booking_id IN %s
                """, (tuple(stored_proc_calls),))

                children_by_parent = {}
                for child_id, parent_id in self.env.cr.fetchall():
                    if parent_id not in children_by_parent:
                        children_by_parent[parent_id] = []
                    children_by_parent[parent_id].append(child_id)

                for booking in multi_room_bookings:
                    if booking.id in children_by_parent:
                        child_ids = children_by_parent[booking.id]
                        
                        booking_data = temp_booking_data[booking.id]
                        forecast_data = booking_data['forecast_data']
                        total_vat, total_mun, total_unt = booking_data['vat_data']
                        self.env.cr.execute("""
                                DELETE FROM room_rate_forecast 
                                WHERE room_booking_id IN %s
                            """, (tuple(child_ids),))
                        _logger.debug("Deleted existing forecast rates for child bookings %s", child_ids)

                        for child_id in child_ids:
                            for data in forecast_data:
                                vals = dict(data, room_booking_id=child_id)
                                batch_forecast_creates.append(vals)

                        all_booking_ids = [booking.id] + child_ids
                        per_vat = total_vat / len(all_booking_ids)
                        per_mun = total_mun / len(all_booking_ids)
                        per_unt = total_unt / len(all_booking_ids)

                        for booking_id in all_booking_ids:
                            batch_booking_updates.append((booking_id, {
                                'total_vat': per_vat,
                                'total_municipality_tax': per_mun,
                                'total_untaxed': per_unt,
                            }))

                        self.env.cr.execute("""
                            SELECT id FROM room_booking_line 
                            WHERE booking_id IN %s
                        """, (tuple(all_booking_ids),))

                        for (line_id,) in self.env.cr.fetchall():
                            batch_history_inserts.append((
                                line_id, self.env.uid, self.env.uid, 'block', get_system_date
                            ))

            _logger.debug("Executing batch operations for multi-room bookings...")

            if batch_forecast_updates:
                _logger.debug("Executing %s forecast updates", len(batch_forecast_updates))
                for forecast_id, values in batch_forecast_updates:
                    self.env.cr.execute("""
                        UPDATE room_rate_forecast 
                        SET rate = %s, meals = %s, packages = %s, fixed_post = %s, 
                            total = %s, before_discount = %s
                        WHERE id = %s
                    """, (values['rate'], values['meals'], values['packages'],
                          values['fixed_post'], values['total'], values['before_discount'], forecast_id))

            if batch_forecast_creates:
                _logger.debug("Creating %s child forecasts", len(batch_forecast_creates))

                values_list = []
                for vals in batch_forecast_creates:
                    values_list.append((
                        vals.get('room_booking_id'),
                        vals.get('date'),
                        vals.get('rate', 0),
                        vals.get('meals', 0),
                        vals.get('packages', 0),
                        vals.get('fixed_post', 0),
                        vals.get('total', 0),
                        vals.get('before_discount', 0),
                        self.env.uid,
                        self.env.uid
                    ))

                self.env.cr.executemany("""
                    INSERT INTO room_rate_forecast 
                    (room_booking_id, date, rate, meals, packages, fixed_post, total, before_discount, 
                     create_date, write_date, create_uid, write_uid)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
                """, values_list)

            if batch_booking_updates:
                _logger.debug("Executing %s booking updates", len(batch_booking_updates))
                for booking_id, values in batch_booking_updates:
                    self.env.cr.execute("""
                        UPDATE room_booking 
                        SET total_vat = %s, total_municipality_tax = %s
                        WHERE id = %s
                    """, (values['total_vat'], values['total_municipality_tax'], booking_id))

            if batch_history_inserts:
                _logger.debug("Inserting %s history records", len(batch_history_inserts))
                self.env.cr.executemany("""
                    INSERT INTO room_booking_line_status 
                    (booking_line_id, create_uid, write_uid, status, change_time, create_date, write_date)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                """, batch_history_inserts)

        self.env.invalidate_all()
        if self.ids:
            self.env.cr.execute("""
                UPDATE room_booking_line 
                SET state_ = 'block' 
                WHERE booking_id IN %s AND room_id IS NOT NULL
            """, (tuple(self.ids),))

            self.env.cr.execute("""
                UPDATE room_booking 
                SET show_in_tree = true 
                WHERE id IN %s
            """, (tuple(self.ids),))

        overall_end = datetime.now()
        total_duration = (overall_end - overall_start).total_seconds()
        _logger.debug("COMPLETED optimized assign_all_rooms for %s bookings in %.2fs",
                     len(self), total_duration)


    def action_clear_rooms(self):
        clear_search_results = self.env.context.get(
            'clear_search_results', False)

        for booking in self:
            # Unlink all room lines associated with this booking
            booking.room_line_ids.unlink()
            booking.adult_ids.unlink()
            booking.child_ids.unlink()
            booking.infant_ids.unlink()
            # booking.rate_forecast_ids.unlink()
            booking.write({'posting_item_ids': [(5, 0, 0)]})
            self.env['room.rate.forecast'].search(
                [('room_booking_id', '=', booking.id)]).unlink()

            # Clear search results only if the flag is True
            # if clear_search_results:
            search_results = self.env['room.availability.result'].search(
                [('room_booking_id', '=', booking.id)])
            if search_results:
                search_results.unlink()
            booking.write({'state': 'not_confirmed'})

    
    def action_split_rooms(self):
        for booking in self:
            if booking.state == "no_show":
                return True
            # Retrieve related room.availability.result records
            availability_results = self.env['room.availability.result'].search(
                [('room_booking_id', '=', booking.id)]
            )


            # Ensure we have availability results to process
            if not availability_results:
                raise UserError(_("You have to Search room first then you can split room"))

            all_split = all(result.split_flag for result in availability_results)
            if all_split:
                raise UserError(_("All rooms have already been split. No new rooms to split."))

            

            room_line_vals = []
            counter = 1
            adult_inserts = []
            child_inserts = []
            infant_inserts = []
            max_counter = max(booking.room_line_ids.mapped('counter') or [0])  # Use 0 if no lines exist
            start_counter = max_counter + 1
            counter = start_counter
            # counter = max_counter + 1  # Start from the next counter value

            partner_name = booking.partner_id.name or ""
            name_parts = partner_name.split()  # Split the name by spaces
            first_name = name_parts[0] if name_parts else ""  # First part as first_name
            last_name = name_parts[-1] if len(name_parts) > 1 else ""  # Last part as last_name

            # Loop through each availability result and process room lines
            for result in availability_results:
                # Check if this record has already been split
                if result.split_flag:
                    continue  # Skip this record if already split

                rooms_reserved_count = int(result.rooms_reserved) if isinstance(result.rooms_reserved, str) else result.rooms_reserved

                # print("Processing result:", result, "Rooms reserved count:", rooms_reserved_count)
                # Create room lines
                for i in range(rooms_reserved_count):
                    new_booking_line = {
                        'room_id': False,  # Room can be assigned later
                        'checkin_date': booking.checkin_date,
                        'checkout_date': booking.checkout_date,
                        'uom_qty': 1,
                        'adult_count': booking.adult_count,
                        'child_count': booking.child_count,
                        'infant_count': booking.infant_count,
                        'hotel_room_type': result.room_type.id,
                        'counter': counter,
                    }
                    counter += 1
                    room_line_vals.append((0, 0, new_booking_line))

                # Append new adult records for this room
                total_adults_needed = rooms_reserved_count * booking.adult_count
                for j in range(total_adults_needed):
                    adult_inserts.append((
                        booking.id,
                        result.room_type.id,
                        first_name, last_name, '', '', '', '', '', '', '', '', '',  # Empty fields
                    ))

                # Append new child records for this room
                total_children_needed = rooms_reserved_count * booking.child_count
                for k in range(total_children_needed):
                    child_inserts.append((
                        booking.id,
                        result.room_type.id,
                        '', '', '', '', '', '', '', '', '', '', '',  # Empty fields
                    ))

                # Append new infant records for this room
                total_infants_needed = rooms_reserved_count * booking.infant_count
                for l in range(total_infants_needed):
                    infant_inserts.append((
                        booking.id,
                        result.room_type.id,
                        '', '', '', '', '', '', '', '', '', '', '',  # Empty fields
                    ))

                # Mark this record as split
                result.split_flag = True

            # Perform bulk insert for adults
            if adult_inserts:
                insert_query_adults = """
                    INSERT INTO reservation_adult (
                        reservation_id, room_type_id, first_name, last_name, profile, nationality,
                        passport_number, id_number, visa_number, id_type, phone_number, relation, create_date
                    ) VALUES %s
                """
                self._bulk_insert(insert_query_adults, adult_inserts)

            # Perform bulk insert for children
            if child_inserts:
                insert_query_children = """
                    INSERT INTO reservation_child (
                        reservation_id, room_type_id, first_name, last_name, profile, nationality,
                        passport_number, id_number, visa_number, id_type, phone_number, relation, create_date
                    ) VALUES %s
                """
                self._bulk_insert(insert_query_children, child_inserts)

            # Perform bulk insert for infants
            if infant_inserts:
                self._bulk_insert("""
                    INSERT INTO reservation_infant (
                        reservation_id, room_type_id, first_name, last_name, profile, nationality,
                        passport_number, id_number, visa_number, id_type, phone_number, relation, create_date
                    ) VALUES %s
                """, infant_inserts)


            if room_line_vals:
                _logger.debug(" Creating %d new room lines", len(room_line_vals))
                booking.write({'room_line_ids': room_line_vals})

                # 7) Immediately SQL‑sync their dates (only the new ones)
                new_lines = booking.room_line_ids.filtered(
                    lambda l: l.counter >= start_counter
                )
                new_ids = new_lines.ids
                if new_ids:
                    # _logger.debug(" SQL‑updating dates on lines %s", new_ids)
                    self.env.cr.execute("""
                        UPDATE room_booking_line
                           SET checkin_date  = %s,
                               checkout_date = %s
                         WHERE id IN %s
                    """, (booking.checkin_date, booking.checkout_date, tuple(new_ids)))
                    _logger.debug(" Date sync complete")
                else:
                    _logger.warning(" No new lines found to SQL‑update!")

            self._update_adults_with_assigned_rooms_split_rooms(
                booking, max_counter)

    
    
    def _update_adults_with_assigned_rooms_split_rooms(self, booking, counter):
        """Update Adults with the assigned rooms from room_line_ids and set room sequence."""
        adult_count = 0
        child_count = 0
        infant_count = 0
        room_sequence_map = {}  # Dictionary to track the sequence for each room type and room
        ctr = counter + 1
        max_counter = counter + 1
        for line in booking.room_line_ids:
            if line.counter < max_counter:
                adult_count += line.adult_count
                child_count += line.child_count
                infant_count += line.infant_count
                continue
            for _ in range(line.adult_count):
                if adult_count < len(booking.adult_ids):
                    # print('4832', adult_count, len(booking.adult_ids))
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the adult
                    booking.adult_ids[adult_count].room_sequence = line.counter
                    booking.adult_ids[adult_count].room_type_id = line.hotel_room_type.id
                    booking.adult_ids[adult_count].room_id = line.room_id.id
                    adult_count += 1

            for _ in range(line.child_count):
                if child_count < len(booking.child_ids):
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.child_ids[child_count].room_sequence = line.counter
                    booking.child_ids[child_count].room_type_id = line.hotel_room_type.id
                    booking.child_ids[child_count].room_id = line.room_id.id
                    child_count += 1

            for _ in range(line.infant_count):
                if infant_count < len(booking.infant_ids):
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.infant_ids[infant_count].room_sequence = line.counter
                    booking.infant_ids[infant_count].room_type_id = line.hotel_room_type.id
                    booking.infant_ids[infant_count].room_id = line.room_id.id
                    infant_count += 1
            ctr += 1

    def _bulk_insert(self, query, values):
        from psycopg2.extras import execute_values
        cleaned_values = []

        # Replace empty strings with NULL for integer fields
        for value in values:
            cleaned_value = tuple(v if v != '' else None for v in value)
            cleaned_values.append(cleaned_value)

        if cleaned_values:
            execute_values(self.env.cr, query, cleaned_values,
                           template=None, page_size=100)
            self.env.cr.commit()

    def _update_adults_with_assigned_rooms(self, booking):
        """Update Adults with the assigned rooms from room_line_ids and set room sequence."""
        adult_count = 0
        child_count = 0
        infant_count = 0
        room_sequence_map = {}  # Dictionary to track the sequence for each room type and room
        ctr = 1

        for line in booking.room_line_ids:
            for _ in range(line.adult_count):
                if adult_count < len(booking.adult_ids):
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the adult
                    booking.adult_ids[adult_count].room_sequence = ctr
                    booking.adult_ids[adult_count].room_type_id = line.hotel_room_type.id
                    booking.adult_ids[adult_count].room_id = line.room_id.id
                    adult_count += 1

            for _ in range(line.child_count):
                if child_count < len(booking.child_ids):
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.child_ids[child_count].room_sequence = ctr
                    booking.child_ids[child_count].room_type_id = line.hotel_room_type.id
                    booking.child_ids[child_count].room_id = line.room_id.id
                    child_count += 1

            for _ in range(line.infant_count):
                if infant_count < len(booking.infant_ids):
                    # Get or initialize the sequence for the room
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.infant_ids[infant_count].room_sequence = ctr
                    booking.infant_ids[infant_count].room_type_id = line.hotel_room_type.id
                    booking.infant_ids[infant_count].room_id = line.room_id.id
                    infant_count += 1

            ctr += 1

    def _get_room_search_query(self):
        return """
        WITH RECURSIVE
    parameters AS (
        SELECT
            %(from_date)s::date AS from_date,
            %(to_date)s::date AS to_date
            ),
    company_ids AS (
        select CAST(%(company_id)s AS INTEGER) as company_id
    ),
    system_date_company AS (
        SELECT
            id AS company_id,
            system_date::date AS system_date,
            create_date::date AS create_date
        FROM res_company rc
        WHERE rc.id IN (SELECT company_id FROM company_ids)
    ),
    date_series AS (
        SELECT generate_series(
            (SELECT MIN(system_date) FROM system_date_company),
            (SELECT to_date FROM parameters),
            INTERVAL '1 day'
        )::date AS report_date
    ),
    base_data AS (
        SELECT
            rb.id AS booking_id,
            rb.parent_booking_id,
            rb.company_id,
            rb.checkin_date::date AS checkin_date,
            rb.checkout_date::date AS checkout_date,
            rbl.id AS booking_line_id,
            rbl.sequence,
            rbl.room_id,
            rbl.hotel_room_type AS room_type_id,
            rbls.status,
            rbls.change_time,
            rb.house_use,
            rb.complementary
        FROM room_booking rb
        JOIN room_booking_line rbl ON rb.id = rbl.booking_id
        LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
        WHERE rb.company_id IN (SELECT company_id FROM company_ids)
          AND rb.active = TRUE
    ),
    latest_line_status AS (
        SELECT DISTINCT ON (bd.booking_line_id, ds.report_date)
            bd.booking_line_id,
            ds.report_date,
            bd.checkin_date,
            bd.checkout_date,
            bd.company_id,
            bd.room_type_id,
            bd.status AS final_status,
            bd.change_time,
            bd.house_use,
            bd.complementary
        FROM base_data bd
        JOIN date_series ds
          ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
        WHERE bd.change_time::date <= ds.report_date
        ORDER BY bd.booking_line_id, ds.report_date DESC, bd.change_time DESC NULLS LAST
    ),
    system_date_in_house AS (
        SELECT
            sdc.system_date AS report_date,
            sdc.company_id,
            lls.room_type_id,
            COUNT(DISTINCT lls.booking_line_id) AS in_house_count
        FROM latest_line_status lls
        JOIN system_date_company sdc ON sdc.company_id = lls.company_id
        WHERE lls.final_status = 'check_in'
          AND sdc.system_date BETWEEN lls.checkin_date AND lls.checkout_date
        GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
    ),
    system_date_expected_arrivals AS (
        SELECT
            sdc.system_date AS report_date,
            sdc.company_id,
            lls.room_type_id,
            COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
        FROM latest_line_status lls
        JOIN system_date_company sdc ON sdc.company_id = lls.company_id
        WHERE lls.checkin_date = sdc.system_date
          AND lls.final_status IN ('confirmed','block')
        GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
    ),
    system_date_expected_departures AS (
        SELECT
            sdc.system_date AS report_date,
            sdc.company_id,
            lls.room_type_id,
            COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
        FROM latest_line_status lls
        JOIN system_date_company sdc ON sdc.company_id = lls.company_id
        WHERE lls.checkout_date = sdc.system_date
          AND lls.final_status IN ('check_in','confirmed','block')
        GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
    ),
    system_date_base AS (
        SELECT
            sdc.system_date AS report_date,
            sdc.company_id,
            rt.id AS room_type_id,
            COALESCE(sdih.in_house_count, 0) AS in_house,
            COALESCE(sdea.expected_arrivals_count, 0) AS expected_arrivals,
            COALESCE(sded.expected_departures_count, 0) AS expected_departures,
            (COALESCE(sdih.in_house_count, 0)
             + COALESCE(sdea.expected_arrivals_count, 0)
             - COALESCE(sded.expected_departures_count, 0)) AS expected_in_house
        FROM system_date_company sdc
        CROSS JOIN room_type rt
        LEFT JOIN system_date_in_house sdih
          ON sdih.company_id = sdc.company_id
         AND sdih.room_type_id = rt.id
         AND sdih.report_date = sdc.system_date
        LEFT JOIN system_date_expected_arrivals sdea
          ON sdea.company_id = sdc.company_id
         AND sdea.room_type_id = rt.id
         AND sdea.report_date = sdc.system_date
        LEFT JOIN system_date_expected_departures sded
          ON sded.company_id = sdc.company_id
         AND sded.room_type_id = rt.id
         AND sded.report_date = sdc.system_date
    ),
    expected_arrivals AS (
        SELECT
            lls.report_date,
            lls.company_id,
            lls.room_type_id,
            COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
        FROM latest_line_status lls
        WHERE lls.checkin_date = lls.report_date
          AND lls.final_status IN ('confirmed','block')
        GROUP BY lls.report_date, lls.company_id, lls.room_type_id
    ),
    expected_departures AS (
        SELECT
            lls.report_date,
            lls.company_id,
            lls.room_type_id,
            COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
        FROM latest_line_status lls
        WHERE lls.checkout_date = lls.report_date
          AND lls.final_status IN ('check_in','confirmed','block')
        GROUP BY lls.report_date, lls.company_id, lls.room_type_id
    ),
    recursive_in_house AS (
        SELECT
            sdb.report_date,
            sdb.company_id,
            sdb.room_type_id,
            sdb.in_house,
            sdb.expected_in_house
        FROM system_date_base sdb
      UNION ALL
        SELECT
            ds.report_date,
            r.company_id,
            r.room_type_id,
            r.expected_in_house AS in_house,
            (r.expected_in_house
             + COALESCE(ea.expected_arrivals_count,0)
             - COALESCE(ed.expected_departures_count,0)) AS expected_in_house
        FROM recursive_in_house r
        JOIN date_series ds
          ON ds.report_date = r.report_date + INTERVAL '1 day'
        LEFT JOIN expected_arrivals ea
          ON ea.report_date = ds.report_date
         AND ea.company_id = r.company_id
         AND ea.room_type_id = r.room_type_id
        LEFT JOIN expected_departures ed
          ON ed.report_date = ds.report_date
         AND ed.company_id = r.company_id
         AND ed.room_type_id = r.room_type_id
    ),
    recursive_in_house_distinct AS (
        SELECT
            report_date,
            company_id,
            room_type_id,
            MAX(in_house) AS in_house,
            MAX(expected_in_house) AS expected_in_house
        FROM recursive_in_house
        GROUP BY report_date, company_id, room_type_id
    ),
    house_use_cte AS (
        SELECT
            lls.report_date,
            lls.company_id,
            lls.room_type_id,
            COUNT(DISTINCT lls.booking_line_id) AS house_use_count
        FROM latest_line_status lls
        WHERE lls.house_use = TRUE
          AND lls.final_status IN ('check_in','check_out')
          AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
        GROUP BY lls.report_date, lls.company_id, lls.room_type_id
    ),
    complementary_use_cte AS (
        SELECT
            lls.report_date,
            lls.company_id,
            lls.room_type_id,
            COUNT(DISTINCT lls.booking_line_id) AS complementary_use_count
        FROM latest_line_status lls
        WHERE lls.complementary = TRUE
          AND lls.final_status IN ('check_in','check_out')
          AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
        GROUP BY lls.report_date, lls.company_id, lls.room_type_id
    ),
    inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        COUNT(DISTINCT hr.id) AS total_room_count,
        SUM(DISTINCT COALESCE(hi.overbooking_rooms,0)) AS overbooking_rooms,
        BOOL_OR(COALESCE(hi.overbooking_allowed,false)) AS overbooking_allowed
        FROM hotel_inventory hi
        JOIN hotel_room hr
        ON hr.company_id = hi.company_id
        AND hr.room_type_name = hi.room_type
        AND hr.active = TRUE
        GROUP BY hi.company_id, hi.room_type
    ),
    out_of_order AS (
        SELECT
            rt.id AS room_type_id,
            hr.company_id,
            ds.report_date,
            COUNT(DISTINCT hr.id) AS out_of_order_count
        FROM date_series ds
        JOIN out_of_order_management_front_desk ooo
          ON ds.report_date BETWEEN ooo.from_date AND ooo.to_date
        JOIN hotel_room hr
          ON hr.id = ooo.room_number
         AND hr.active = TRUE
        JOIN room_type rt
          ON hr.room_type_name = rt.id
        GROUP BY rt.id, hr.company_id, ds.report_date
    ),
    rooms_on_hold AS (
        SELECT
            rt.id AS room_type_id,
            hr.company_id,
            ds.report_date,
            COUNT(DISTINCT hr.id) AS rooms_on_hold_count
        FROM date_series ds
        JOIN rooms_on_hold_management_front_desk roh
          ON ds.report_date BETWEEN roh.from_date AND roh.to_date
        JOIN hotel_room hr
          ON hr.id = roh.room_number
         AND hr.active = TRUE
        JOIN room_type rt
          ON hr.room_type_name = rt.id
        GROUP BY rt.id, hr.company_id, ds.report_date
    ),
    out_of_service AS (
        SELECT
            rt.id AS room_type_id,
            hr.company_id,
            ds.report_date,
            COUNT(DISTINCT hr.id) AS out_of_service_count
        FROM date_series ds
        JOIN housekeeping_management hm
          ON hm.out_of_service = TRUE
         AND (hm.repair_ends_by IS NULL OR ds.report_date <= hm.repair_ends_by)
        JOIN hotel_room hr
          ON hr.room_type_name = hm.room_type
         AND hr.active = TRUE
        JOIN room_type rt
          ON hr.room_type_name = rt.id
        GROUP BY rt.id, hr.company_id, ds.report_date
    ),
    final_report AS (
        SELECT
            ds.report_date,
            rc.id AS company_id,
            rc.name AS company_name,
            rt.id AS room_type_id,
            COALESCE(jsonb_extract_path_text(rt.room_type::jsonb,'en_US'),'N/A') AS room_type_name,
            COALESCE(inv.total_room_count,0) AS total_rooms,
            COALESCE(inv.overbooking_rooms,0) AS overbooking_rooms,
            COALESCE(inv.overbooking_allowed,false) AS overbooking_allowed,
            COALESCE(ooo.out_of_order_count,0) AS out_of_order,
            COALESCE(roh.rooms_on_hold_count,0) AS rooms_on_hold,
            COALESCE(oos.out_of_service_count,0) AS out_of_service,
            COALESCE(ea.expected_arrivals_count,0) AS expected_arrivals,
            COALESCE(ed.expected_departures_count,0) AS expected_departures,
            COALESCE(hc.house_use_count,0) AS house_use_count,
            COALESCE(cc.complementary_use_count,0) AS complementary_use_count,
            (COALESCE(inv.total_room_count,0)
             - COALESCE(ooo.out_of_order_count,0)
             - COALESCE(roh.rooms_on_hold_count,0)) AS available_rooms,
            COALESCE((
                SELECT in_house_count
                FROM system_date_in_house sdi
                WHERE sdi.company_id = rc.id
                  AND sdi.room_type_id = rt.id
                  AND sdi.report_date = ds.report_date
            ),0) AS in_house
        FROM date_series ds
        LEFT JOIN res_company rc
          ON rc.id IN (SELECT company_id FROM company_ids)
        CROSS JOIN room_type rt
        INNER JOIN inventory inv
          ON inv.company_id = rc.id AND inv.room_type_id = rt.id
        LEFT JOIN out_of_order ooo
          ON ooo.company_id = rc.id AND ooo.room_type_id = rt.id AND ooo.report_date = ds.report_date
        LEFT JOIN rooms_on_hold roh
          ON roh.company_id = rc.id AND roh.room_type_id = rt.id AND roh.report_date = ds.report_date
        LEFT JOIN out_of_service oos
          ON oos.company_id = rc.id AND oos.room_type_id = rt.id AND oos.report_date = ds.report_date
        LEFT JOIN expected_arrivals ea
          ON ea.company_id = rc.id AND ea.room_type_id = rt.id AND ea.report_date = ds.report_date
        LEFT JOIN expected_departures ed
          ON ed.company_id = rc.id AND ed.room_type_id = rt.id AND ed.report_date = ds.report_date
        LEFT JOIN house_use_cte hc
          ON hc.company_id = rc.id AND hc.room_type_id = rt.id AND hc.report_date = ds.report_date
        LEFT JOIN complementary_use_cte cc
          ON cc.company_id = rc.id AND cc.room_type_id = rt.id AND cc.report_date = ds.report_date
        LEFT JOIN system_date_company sdc
          ON sdc.company_id = rc.id
        WHERE ds.report_date >= (SELECT from_date FROM parameters)
    ),
    final_output AS (
        SELECT
            fr.report_date,
            fr.company_id,
            fr.company_name,
            fr.room_type_id,
            fr.room_type_name,
            SUM(fr.total_rooms) AS total_rooms,
            BOOL_OR(fr.overbooking_allowed) AS any_overbooking_allowed,
            SUM(fr.overbooking_rooms) AS total_overbooking_rooms,
            SUM(fr.out_of_order) AS out_of_order,
            SUM(fr.rooms_on_hold) AS rooms_on_hold,
            SUM(fr.out_of_service) AS out_of_service,
            SUM(fr.expected_arrivals) AS expected_arrivals,
            SUM(fr.expected_departures) AS expected_departures,
            SUM(fr.house_use_count) AS house_use_count,
            SUM(fr.complementary_use_count) AS complementary_use_count,
            SUM(fr.available_rooms) AS available_rooms,
            rih.in_house AS in_house,
            GREATEST(rih.expected_in_house, 0) AS expected_in_house,
            CASE
                WHEN BOOL_OR(fr.overbooking_allowed) THEN
                    CASE
                        WHEN SUM(fr.available_rooms) < 0
                            OR SUM(fr.overbooking_rooms) < 0
                            OR GREATEST(rih.expected_in_house, 0) < 0 THEN 0
                        ELSE GREATEST(
                            0,
                            SUM(fr.available_rooms)
                            + SUM(fr.overbooking_rooms)
                            - GREATEST(rih.expected_in_house, 0)
                        )
                    END
                ELSE
                    CASE
                        WHEN SUM(fr.available_rooms) < 0 THEN 0
                        ELSE GREATEST(
                            0,
                            SUM(fr.available_rooms)
                            - GREATEST(rih.expected_in_house, 0)
                        )
                    END
            END AS free_to_sell,
            GREATEST(
                0,
                GREATEST(rih.expected_in_house, 0)
                - SUM(fr.available_rooms)
            ) AS over_booked
        FROM final_report fr
        JOIN recursive_in_house_distinct rih
          ON fr.report_date = rih.report_date
         AND fr.company_id = rih.company_id
         AND fr.room_type_id = rih.room_type_id
        WHERE fr.report_date >= (SELECT from_date FROM parameters)
        GROUP BY
            fr.report_date,
            fr.company_id,
            fr.company_name,
            fr.room_type_id,
            fr.room_type_name,
            rih.in_house,
            GREATEST(rih.expected_in_house, 0)
        ORDER BY
            fr.report_date,
            fr.company_name,
            fr.room_type_name
    )

    SELECT
        room_type_id,
        room_type_name,
        company_id,
        company_name,
        min(free_to_sell) AS min_free_to_sell,
        total_rooms,
        any_overbooking_allowed AS has_overbooking,
        total_overbooking_rooms
        FROM final_output
        WHERE (%(room_type_id)s IS NULL OR room_type_id = %(room_type_id)s)
        GROUP BY room_type_id, room_type_name, company_id, company_name, total_rooms, any_overbooking_allowed, total_overbooking_rooms;
            """
        
    search_performed = fields.Boolean(default=False)
    
    def action_search_rooms(self):
        self.ensure_one()
        original_state = self.state

        # ── 1) If we're already confirmed, wipe out the old split so we can re-split ──
        if original_state == 'confirmed':
            # reset split flags so action_split_rooms will run again
            self.availability_results.write({'split_flag': False})
            # drop all existing room lines & passenger records
            self.write({
                'room_line_ids': [(5, 0, 0)],
                'adult_ids':     [(5, 0, 0)],
                'child_ids':     [(5, 0, 0)],
                'infant_ids':    [(5, 0, 0)],
            })

        # ── 2) Clear any old availability and run your forecast & SQL ──
        self.action_clear_rooms()
        self._get_forecast_rates()
        query = self._get_room_search_query()
        params = {
            'company_id':    self.env.company.id,
            'from_date':     self.checkin_date,
            'to_date':       self.checkout_date,
            'room_count':    self.room_count,
            'room_type_id':  self.hotel_room_type.id if self.hotel_room_type else None,
        }
        self.env.cr.execute(query, params)
        results = self.env.cr.dictfetchall()

        # ── 3) Handle “no rooms” exactly as before ──
        if not results:
            wizard = self._trigger_waiting_list_wizard(
                self.room_count, 0,
                self.hotel_room_type.id if self.hotel_room_type else None
            )
            # restore confirmed state before returning
            if original_state == 'confirmed':
                super(self.__class__, self).write({'state': 'confirmed'})
            return (0, [wizard])

        # ── 4) Filter by room_type or pick best ──
        if self.hotel_room_type:
            # only keep rows matching the selected type
            filtered_results = [
                r for r in results
                if r['room_type_id'] == self.hotel_room_type.id
            ]
            # none of that type left?
            if not filtered_results:
                wizard = self._trigger_waiting_list_wizard(
                    self.room_count, 0, self.hotel_room_type.id
                )
                if original_state == 'confirmed':
                    super(self._class_, self).write({'state': 'confirmed'})
                return (0, [wizard])

            # first matching result
            selected = filtered_results[0]
            available = selected['min_free_to_sell']
            # over-booked?
            if self.room_count > available:
                return self._trigger_waiting_list_wizard(
                    self.room_count, int(available), self.hotel_room_type.id
                )
        else:
            # pick the type with max availability
            best = max(results, key=lambda x: x['min_free_to_sell'])
            filtered_results = [best]
        
        # ── 5) Build new availability_results for the current room_count ──
        lines = []
        for r in results:
            if r['min_free_to_sell'] > 0:
                lines.append((0, 0, {
                    'company_id':      r['company_id'],
                    'room_type':       r['room_type_id'],
                    'rooms_reserved':  self.room_count,
                    'available_rooms': r['min_free_to_sell'],
                    'pax':             self.adult_count,
                }))
        self.write({'availability_results': lines})

        # ── 6) If we were originally confirmed, fire off the split again ──
        if original_state == 'confirmed':
            # this will recreate room_line_ids + adult_ids/child_ids/infant_ids
            self.action_split_rooms()
            # and then put us back in confirmed
            super(self.__class__, self).write({'state': 'confirmed'})

        return results


    
    room_count_tree = fields.Integer(
        string="Room Count", store=False)

    room_count_tree_ = fields.Char(
        string="Remaining Room Count", compute="_compute_room_count", store=False)

    @api.depends("room_line_ids")
    def _compute_room_count(self):
        for record in self:
            false_room_count = len(record.room_line_ids.filtered(
                lambda line: not line.room_id))
            record.room_count_tree_ = str(
                false_room_count) if false_room_count > 0 else ''

    @api.onchange('room_line_ids')
    def _onchange_room_id(self):
        if self.env.context.get('skip_code_validation'):
            return
        # Populate available rooms in the dropdown list when user clicks the Room field
        if not self.is_button_clicked:
            return {'domain': {'room_id': [('id', 'in', [])]}}

        new_rooms = self._find_rooms_for_capacity()
        room_ids = new_rooms.mapped('id') if new_rooms else []
        return {'domain': {'room_id': [('id', 'in', room_ids)]}}


    def increase_room_count(self):
        for record in self:
            # Increment room count
            record.room_count += 1

            # Calculate the required number of adults and children
            total_adults_needed = record.room_count * record.adult_count
            total_children_needed = record.room_count * record.child_count

            # Manage adults
            current_adults = len(record.adult_ids)
            if total_adults_needed > current_adults:
                # Add missing adult records
                for _ in range(total_adults_needed - current_adults):
                    self.env['reservation.adult'].create(
                        {'reservation_id': record.id})
            elif total_adults_needed < current_adults:
                # Remove extra adult records
                extra_adults = record.adult_ids[current_adults -
                                                total_adults_needed:]
                extra_adults.unlink()

            # Manage children
            current_children = len(record.child_ids)
            if total_children_needed > current_children:
                # Add missing child records
                for _ in range(total_children_needed - current_children):
                    self.env['reservation.child'].create(
                        {'reservation_id': record.id})
            elif total_children_needed < current_children:
                # Remove extra child records
                extra_children = record.child_ids[current_children -
                                                  total_children_needed:]
                extra_children.unlink()

    def decrease_room_count(self):
        for record in self:
            if record.room_count > 1:
                record.room_count -= 1

    def action_remove_room(self):
        """Remove the last added room from the booking"""
        self.ensure_one()
        if self.room_line_ids:
            last_room = self.room_line_ids[-1]
            # Reset the room status to available
            if last_room.room_id:
                last_room.room_id.write({'status': 'available'})
            # Remove the room line
            last_room.unlink()
            # Update room count
            if self.room_count > len(self.room_line_ids):
                self.room_count = len(self.room_line_ids)
                self.rooms_to_add = 0

    def increase_adult_count(self):
        for record in self:
            record.adult_count += 1
            # Add a new adult when count increases
            self.env['reservation.adult'].create({'reservation_id': record.id})

    def decrease_adult_count(self):
        for record in self:
            if record.adult_count > 1:
                if record.adult_ids:
                    last_adult = record.adult_ids[-1]
                    last_adult.unlink()  # Remove last adult record
                record.adult_count -= 1

    def increase_child_count(self):
        for record in self:
            record.child_count += 1
            self.env['reservation.child'].create({'reservation_id': record.id})

    def decrease_child_count(self):
        for record in self:
            if record.child_count > 0:
                # Archive the last child record instead of deleting it
                if record.child_ids:
                    last_child = record.child_ids[-1]
                    last_child.unlink()  # Archive the last child's record
                record.child_count -= 1


class RoomWaitingList(models.Model):
    _name = 'room.waiting.list'
    _description = 'Room Waiting List'

    partner_id = fields.Many2one('res.partner', string='Customer')
    checkin_date = fields.Datetime(string='Desired Check In', required=True)
    checkout_date = fields.Datetime(string='Desired Check Out', required=True)
    room_type_id = fields.Many2one('room.type', string='Room Type')
    num_rooms = fields.Integer(string='Number of Rooms', required=True)
    state = fields.Selection([
        ('waiting', 'Waiting'),
        ('notified', 'Notified'),
    ], default='waiting')


class HotelChildAge(models.Model):
    _name = 'hotel.child.age'
    _description = 'Children Age'

    age = fields.Selection(
        [(str(i), str(i)) for i in range(1, 18)],  # Ages from 1 to 17
        string='Age'
    )
    booking_id = fields.Many2one('room.booking', string='Booking')

    child_label = fields.Char(string='Child Label',
                              compute='_compute_child_label', store=True)

    @api.depends('booking_id.child_ages')
    def _compute_child_label(self):
        for record in self:
            if record.booking_id:
                # Safely try to get the index
                child_ids = record.booking_id.child_ages.ids
                if record.id in child_ids:
                    index = child_ids.index(record.id) + 1
                    record.child_label = f'Child {index}'
                else:
                    record.child_label = 'Child'


class ReservationAdult(models.Model):
    _name = 'reservation.adult'
    _description = 'Reservation Adult'

    room_sequence = fields.Integer(string="Room Sequence")
    first_name = fields.Char(string='First Name', required=True)
    last_name = fields.Char(string='Last Name')
    profile = fields.Char(string='Profile')
    nationality = fields.Many2one('res.country', string='Nationality')
    birth_date = fields.Date(string='Birth Date')
    passport_number = fields.Char(string='Passport No.')
    id_number = fields.Char(string='ID Number')
    visa_number = fields.Char(string='Visa Number')
    id_type = fields.Char(string='ID Type')
    phone_number = fields.Char(string='Phone Number')
    relation = fields.Char(string='Relation')

    # Link to the main reservation
    reservation_id = fields.Many2one('room.booking', string='Reservation')
    room_type_id = fields.Many2one('room.type', string='Room Type')
    room_id = fields.Many2one(
        'hotel.room', string='Room', help='Room assigned to the adult guest')


class ReservationChild(models.Model):
    _name = 'reservation.child'
    _description = 'Reservation Child'

    room_sequence = fields.Integer(string="Room Sequence")
    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    profile = fields.Char(string='Profile')
    nationality = fields.Many2one('res.country', string='Nationality')
    birth_date = fields.Date(string='Birth Date')
    passport_number = fields.Char(string='Passport No.')
    id_type = fields.Char(string='ID Type')
    id_number = fields.Char(string='ID Number')
    visa_number = fields.Char(string='Visa Number')
    type = fields.Selection(
        [('visitor', 'Visitor'), ('resident', 'Resident')], string='Type')
    phone_number = fields.Char(string='Phone Number')
    relation = fields.Char(string='Relation')

    # Link to the main reservation
    reservation_id = fields.Many2one('room.booking', string='Reservation')
    room_type_id = fields.Many2one('room.type', string='Room Type')
    room_id = fields.Many2one(
        'hotel.room', string='Room', help='Room assigned to the adult guest')


class ReservationInfant(models.Model):
    _name = 'reservation.infant'
    _description = 'Reservation Infant'

    room_sequence = fields.Integer(string="Room Sequence")
    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    profile = fields.Char(string='Profile')
    nationality = fields.Many2one('res.country', string='Nationality')
    birth_date = fields.Date(string='Birth Date')
    passport_number = fields.Char(string='Passport No.')
    id_type = fields.Char(string='ID Type')
    id_number = fields.Char(string='ID Number')
    visa_number = fields.Char(string='Visa Number')
    type = fields.Selection(
        [('visitor', 'Visitor'), ('resident', 'Resident')], string='Type')
    phone_number = fields.Char(string='Phone Number')
    relation = fields.Char(string='Relation')

    # Link to the main reservation
    reservation_id = fields.Many2one('room.booking', string='Reservation')
    room_type_id = fields.Many2one('room.type', string='Room Type')
    room_id = fields.Many2one(
        'hotel.room', string='Room', help='Room assigned to the adult guest')


class ResPartnerDetails(models.Model):
    _name = 'partner.details'
    _description = 'Partner Details'
    _rec_name = 'partner_id' 

    partner_id = fields.Many2one('res.partner', string="Partner", required=False)
    partner_company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company, tracking=True)
    rate_code = fields.Many2one('rate.code', string="Rate Code")
    source_of_business = fields.Many2one('source.business', string="Source of Business")
    market_segments = fields.Many2one('market.segment', string="Market Segment")
    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern")


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create(self, vals):
        
        partner = super(ResPartner, self).create(vals)

        # Create a record in the new model
        self.env['partner.details'].create({
            'partner_id': partner.id,
            'partner_company_id': self.env.company.id,
            'rate_code': vals.get('rate_code'),
            'source_of_business': vals.get('source_of_business'),
            'market_segments': vals.get('market_segments'),
            'meal_pattern': vals.get('meal_pattern'),
        })

        return partner

    is_vip = fields.Boolean(
        string="VIP", help="Mark this contact as a VIP", tracking=True)
    vip_code = fields.Many2one('vip.code', string="VIP Code",
                                domain=[('obsolete', '=', False)],
                                tracking=True
                            )


    @api.onchange('is_vip')
    def _onchange_is_vip(self):
        if not self.is_vip:
            self.vip_code = False
    
    
    meal_rate_ids = fields.One2many('partner.details', 'partner_id', string='Meal and Rate',domain=lambda self: [
        ('partner_company_id', '=', self.env.company.id),
    ],)
    @api.constrains('meal_rate_ids')
    def _check_meal_rate_limit(self):
        for record in self:
            if len(record.meal_rate_ids) > 1:
                raise ValidationError("You can only add one meal and rate code entry.")
    

    
    rate_code = fields.Many2one('rate.code',  domain=lambda self: [
        ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], string="Rate Code", tracking=True)
    
    source_of_business = fields.Many2one(
        'source.business', string="Source of Business", 
        domain=lambda self: [
        ('obsolete', '=', False)
    ],tracking=True)
    nationality = fields.Many2one(
        'res.country', string='Nationality', tracking=True)
    market_segments = fields.Many2one('market.segment', string="Market Segment", 
    domain=lambda self: [
        # ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], tracking=True)
    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern",domain=lambda self: [('company_id', '=', self.env.company.id)], tracking=True)
    max_pax = fields.Integer(string="Max Room", tracking=True)

    hashed_password = fields.Char(string="Hashed Password")

    @api.model
    def set_password(self, password):
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        self.hashed_password = hashed.decode('utf-8')

    def check_password(self, password):
        if self.hashed_password:
            return bcrypt.checkpw(password.encode('utf-8'), self.hashed_password.encode('utf-8'))
        return False

    reservation_count = fields.Integer(
        string="Reservations",
        compute='_compute_reservation_count',
        store=False
    )

    def _compute_reservation_count(self):
        for partner in self:
            partner.reservation_count = self.env['room.booking'].search_count(
                [('partner_id', '=', partner.id)])

    def action_view_reservations(self):
        return {
            'name': 'Reservations',
            'type': 'ir.actions.act_window',
            'res_model': 'room.booking',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'target': 'current',
        }

    group_booking_ids = fields.Many2many('group.booking', string='Group Bookings',
                                         compute='_compute_group_booking_count')
    group_booking_count = fields.Integer(
        string='Group Booking Count', compute='_compute_group_booking_count')

    @api.depends('group_booking_ids')
    def _compute_group_booking_count(self):
        for partner in self:
            group_booking_records = self.env['group.booking'].search([
                ('company', '=', partner.id)
            ])
            partner.group_booking_ids = group_booking_records
            partner.group_booking_count = len(group_booking_records)

    def action_view_group_bookings(self):
        self.ensure_one()
        return {
            'name': 'Group Bookings',
            'type': 'ir.actions.act_window',
            'res_model': 'room.booking',
            'view_mode': 'tree,form',
            'domain': [('group_booking', 'in', self.group_booking_ids.ids)],
            'target': 'current',
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    posting_item_id = fields.Many2one(
        'posting.item', string="Posting Item",
        required=False, help="Select the posting item."
    )
    posting_description = fields.Char(
        string="Description",
        # related='posting_item_id.description',  # Related to posting.item.description
        readonly=True,
    )
    posting_default_value = fields.Float(
        string="Default Value",
        # related='posting_item_id.default_value',  # Related to posting.item.default_value
        readonly=True,
    )


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    rate_code_ids = fields.One2many(
        'rate.code', 'pricelist_id', string="Rate Codes")


class RateCodeInherit(models.Model):
    _inherit = 'rate.code'

    pricelist_id = fields.Many2one(
        'product.pricelist', string='Pricelist', ondelete='cascade')


class SystemDate(models.Model):
    _inherit = 'res.company'

    checkin_time = fields.Char(string="Check-in Time 24hrs", help="Select the check-in time")
    checkout_time = fields.Char(string="Check-out Time 24hrs", help="Select the check-out time")

    @api.model
    def get_system_date(self):
        return self.env.company.system_date
    
    
    @api.constrains('checkin_time', 'checkout_time')
    def _check_time_format(self):
        time_pattern = re.compile(r'^(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d$')  # Regex for HH:MM:SS format
        for record in self:
            if record.checkin_time and not time_pattern.match(record.checkin_time):
                raise ValidationError(f"Invalid check-in time format: {record.checkin_time}. Please use HH:MM:SS.")
            if record.checkout_time and not time_pattern.match(record.checkout_time):
                raise ValidationError(f"Invalid check-out time format: {record.checkout_time}. Please use HH:MM:SS.")


    owner = fields.Char(string='Owner')
    
    system_date = fields.Datetime(
        string="System Date",
        # default=lambda self: fields.Datetime.now(),
        default=lambda self: self._default_system_date(),
        tracking=True,
        required=True,
        help="The current system date and time."
    )

    def action_update_system_date(self):
        """Add 1 day to the system_date for each record in self."""
        for rec in self:
            if rec.system_date:
                rec.system_date = rec.system_date + timedelta(days=1)
            else:
                rec.system_date = fields.Date.context_today(self)

            # Update the cron's nextcall based on system_date
            cron = self.env.ref(
                'hotel_management.cron_move_to_no_show', raise_if_not_found=False)
            if cron:
                cron.nextcall = datetime.combine(
                    rec.system_date, datetime.min.time())

        self.env['room.booking'].move_to_no_show()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    @api.model
    def _default_system_date(self):
        """
        Returns today's date with the time set to 23:30 (11:30 PM) **without timezone info**.
        """
        user_tz = self.env.user.tz or 'UTC'  # Get user timezone or default to UTC
        today_date = fields.Date.context_today(self)  # Today's date in user’s timezone
        default_time = time(7, 00)  # 23:30:00 (11:30 PM)

        # Combine date and time
        user_timezone = pytz.timezone(user_tz)
        local_dt = user_timezone.localize(datetime.combine(today_date, default_time))  # Localized datetime

        # Convert to UTC
        utc_dt = local_dt.astimezone(pytz.utc)

        # **FIX:** Convert to naive datetime (remove timezone info)
        naive_utc_dt = utc_dt.replace(tzinfo=None)

        return naive_utc_dt  # Store as naive datetime


    # @api.constrains('system_date')
    # def _check_system_date(self):
    #     """Ensure that system_date is not earlier than the company's creation date."""
    #     for record in self:
    #         if record.system_date and record.create_date and record.system_date <= record.create_date:
    #             raise ValidationError(f"System Date ({record.system_date.date()}) cannot be earlier than the company's creation date ({record.create_date.date()}).")

    

    inventory_ids = fields.One2many('hotel.inventory', 'company_id', string="Inventory")
    age_threshold = fields.Integer(string="Age Threshold")  #

    # data fields for hotel web
    web_title = fields.Char(string="Title", help="Title of the Hotel")
    web_star_rating = fields.Integer(
        string="Star Rating", help="Star rating of the hotel")
    # web_kaaba_view = fields.Boolean(string="Kaaba view", default=False, help="is Kaaba visible from the hotel")
    web_kaaba_view = fields.Selection(
        selection=[
            ('full_kaaba_view', 'Full Kaaba View'),
            ('partial_kaaba_view', 'Partial Kaaba View'),
            ('no_kaaba_view', 'No Kaaba View')
        ],
        string="Kaaba View",
        default='no_kaaba_view',
        help="Indicates the type of Kaaba view available from the hotel."
    )

    web_hotel_location = fields.Char(
        string="Hotel location", help="Location of the hotel")
    web_description = fields.Text(
        string="Hotel description", help="Description of the hotel")
    web_discount = fields.Float(
        string="Discount", help="General discount given to hotel customers")
    web_review = fields.Float(string="Guest review",
                              help="Guest review of the hotel")
    web_payment = fields.Float(
        string="Payment", help="Payment value", default=0.0)
    rate_code = fields.Many2one('rate.code',   domain=lambda self: [('company_id', '=', self.env.company.id)], string="Rate Codes")
    market_segment = fields.Many2one('market.segment', string='Market Segment')
    starting_price = fields.Float(string="Starting Price")
    
    # source_business = fields.Many2one(
    #     'source.business', domain="[('company_id', '=', 2)]", string="Source of Business")
    source_business = fields.Many2one('source.business', string="Source of Business")

    term_and_condition_rc_en = fields.Html(string="English", domain=lambda self: [('company_id', '=', self.env.company.id)])
    term_and_condition_rc_ar = fields.Html(string="Arabic", domain=lambda self: [('company_id', '=', self.env.company.id)])

    term_and_condition_rcgroup_en = fields.Html(string="English", domain=lambda self: [('company_id', '=', self.env.company.id)])
    term_and_condition_rcgroup_ar = fields.Html(string="Arabic", domain=lambda self: [('company_id', '=', self.env.company.id)])

    @api.constrains('rate_code', 'name')
    def _check_company_name(self):
        """Ensure rate_code is only assigned if the name matches the current company."""
        current_company = self.env.company
        for record in self:
            if record.rate_code and record.name != current_company.name:
                record.rate_code = False  # Forcefully set rate_code to False
                raise ValidationError(
                    _(
                        "You cannot assign a Rate Code because your current hotel is '%s', "
                        "but the hotel name is '%s'. Both must be the same. "
                        "or select blank rate code to create new hotel"

                    ) % (current_company.name, record.name)
                )
    
    @api.constrains('starting_price')
    def _check_starting_price(self):
        for record in self:
            if record.starting_price < 1: 
                raise ValidationError(_("Starting Price Cannot be less than 1"))

    @api.constrains('web_star_rating')
    def _check_star_rating(self):
        for record in self:
            if record.web_star_rating < 1 or record.web_star_rating > 5:
                raise ValidationError(_("Star Rating must be between 1 and 5."))

    @api.constrains('web_discount')
    def _check_discount(self):
        for record in self:
            if record.web_discount < 1 or record.web_discount > 100:
                raise ValidationError("Discount must be between 1 and 100.")

    @api.constrains('web_payment')
    def _check_payment(self):
        for record in self:
            if record.web_payment < 1 or record.web_payment > 100:
                raise ValidationError(_("Payment must be between 1 and 100."))


class HotelInventory(models.Model):
    _name = 'hotel.inventory'
    _description = 'Hotel Inventory'
    _table = 'hotel_inventory'  # This should match the database table name

    _rec_name = 'room_type'
    # image = fields.Image(string="Image", max_width=128, max_height=128)
    image = fields.Binary(string='Image', attachment=True)
    hotel_name = fields.Integer(string="Hotel Name")
    room_type = fields.Many2one('room.type', string="Room Type")
    total_room_count = fields.Integer(string="Total Room Count", readonly=True)
    pax = fields.Integer(string="Pax")
    age_threshold = fields.Integer(string="Age Threshold")
    web_allowed_reservations = fields.Integer(
        string="Web Allowed Reservations")
    overbooking_allowed = fields.Boolean(string="Overbooking Allowed")
    overbooking_rooms = fields.Integer(string="Overbooking Rooms")
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company)
    
    @api.onchange('web_allowed_reservations')
    def _onchange_web_allowed_reservations(self):
        for record in self:
            if record.web_allowed_reservations > record.total_room_count:
                record.web_allowed_reservations = 0  # Resetting the value
                return {
                    'warning': {
                        'title': "Validation Error",
                        'message': "Web Allowed Reservations cannot be greater than Total Room Count.",
                    }
                }

    
    def write(self, vals):
        result = super().write(vals)
        for record in self:
            if 'overbooking_rooms' in vals:
                room_count = vals.get('overbooking_rooms', record.overbooking_rooms)
                self.env.user.notify_info(
                    message=f"Overbooking allowed with {room_count} room(s).",
                    title="Overbooking Info"
                )
        return result


class RoomAvailabilityResult(models.Model):
    _name = 'room.availability.result'
    _description = 'Room Availability Result'

    room_booking_id = fields.Many2one(
        'room.booking', string="Room Booking", ondelete="cascade")
    company_id = fields.Many2one('res.company', string="Company")
    room_type = fields.Many2one('room.type', string="Room Type")
    pax = fields.Integer(string="Adults")
    rooms_reserved = fields.Integer(string="Searched Rooms Count")
    available_rooms = fields.Integer(string="Available Rooms")
    split_flag = fields.Boolean(string='Split Flag', default=False)


    def action_delete_selected(self):
        for record in self:
            # Ensure the availability record is linked to a booking
            if record.room_booking_id:
                # Search for related room lines specific to the availability record
                related_room_lines = self.env['room.booking.line'].search([
                    ('booking_id', '=', record.room_booking_id.id),
                    ('hotel_room_type', '=', record.room_type.id)
                ])

                # Check for conflicts: assigned room_id or state == 'confirmed'
                conflicting_lines = related_room_lines.filtered(
                    lambda line: line.room_id or line.state == 'confirmed'
                )

                if conflicting_lines:
                    # Prepare detailed error message
                    assigned_rooms = conflicting_lines.filtered(
                        lambda line: line.room_id).mapped('room_id.name')
                    assigned_room_names = ', '.join(
                        assigned_rooms) if assigned_rooms else "None"
                    has_confirmed = any(
                        line.state == 'confirmed' for line in conflicting_lines)

                    error_message = "Cannot delete this record because:"
                    if assigned_rooms:
                        error_message += f" the following rooms are already assigned: {assigned_room_names}."
                    if has_confirmed:
                        error_message += " Booking is in the 'confirmed' state."

                    raise ValidationError(error_message)

                # If no conflicts, delete the specific related room lines
                related_room_lines.unlink()

            # Delete the specific availability record
            record.unlink()

    def get_max_counter(self, booking_id):
        # Search for room booking lines related to the given booking ID
        room_lines = self.env['room.booking.line'].search(
            [('booking_id', '=', booking_id)])

        # If no lines are found, return 0
        if not room_lines:
            return 0

        # Get the maximum value of the 'counter' field
        max_counter = max(room_lines.mapped('counter'))
        return max_counter

    def update_counter_res_search(self, booking):
        adult_count = 0
        child_count = 0
        infant_count = 0
        room_sequence_map = {}  # Dictionary to track the sequence for each room type and room
        ctr = 1

        for line in booking.room_booking_id.room_line_ids:
            # Update adults
            for _ in range(line.adult_count):
                if adult_count < len(booking.room_booking_id.adult_ids):
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the adult
                    booking.room_booking_id.adult_ids[adult_count].room_sequence = ctr
                    booking.room_booking_id.adult_ids[adult_count].room_type_id = line.hotel_room_type.id
                    booking.room_booking_id.adult_ids[adult_count].room_id = line.room_id.id
                    adult_count += 1

            # Update children
            for _ in range(line.child_count):
                if child_count < len(booking.room_booking_id.child_ids):
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the child
                    booking.room_booking_id.child_ids[child_count].room_sequence = ctr
                    booking.room_booking_id.child_ids[child_count].room_type_id = line.hotel_room_type.id
                    booking.room_booking_id.child_ids[child_count].room_id = line.room_id.id
                    child_count += 1

            # Update infants
            for _ in range(line.infant_count):
                if infant_count < len(booking.room_booking_id.infant_ids):
                    room_key = f"{line.hotel_room_type.id}-{line.room_id.id}"
                    if room_key not in room_sequence_map:
                        room_sequence_map[room_key] = len(
                            room_sequence_map) + 1  # Increment sequence

                    # Update the room_sequence, room_type, and room_id for the infant
                    booking.room_booking_id.infant_ids[infant_count].room_sequence = ctr
                    booking.room_booking_id.infant_ids[infant_count].room_type_id = line.hotel_room_type.id
                    booking.room_booking_id.infant_ids[infant_count].room_id = line.room_id.id
                    infant_count += 1

            ctr += 1

    def action_split_selected(self):
        for record in self:
            rooms_reserved_count = int(record.rooms_reserved) if isinstance(
                record.rooms_reserved, str) else record.rooms_reserved

            # Ensure we have an existing room.booking record to add lines to
            if not record.room_booking_id:
                raise UserError(
                    "No room booking record found to add lines to.")

            # Check if the record is already split
            if record.split_flag:
                raise UserError("This record has already been split.")

            booking = record.room_booking_id
            room_line_vals = []
            max_counter = self.get_max_counter(booking.id)
            counter = max_counter + 1  # Start from the next counter value
            for _ in range(rooms_reserved_count):
                new_booking_line = {
                    'room_id': False,
                    'checkin_date': booking.checkin_date,
                    'checkout_date': booking.checkout_date,
                    'uom_qty': 1,
                    'adult_count': booking.adult_count,
                    'child_count': booking.child_count,
                    'infant_count': booking.infant_count,
                    'booking_id': record.id,
                    'hotel_room_type': record.room_type.id,
                    'counter': counter,
                }
                counter += 1

                room_line_vals.append((0, 0, new_booking_line))

            # Add room lines to the booking's room_line_ids
            booking.write({'room_line_ids': room_line_vals})

            # Mark the record as split
            record.split_flag = True
            self._update_adults_with_assigned_rooms_split_selected(
                record, max_counter + 1)

    def _update_adults_with_assigned_rooms_split_selected(self, booking, counter):
        """Update Adults and Children with the assigned rooms from room_line_ids and set room sequence."""
        availability_results = self.env['room.availability.result'].search(
            [('id', '=', self.id)]
        )

        if not availability_results:
            raise UserError(_("You have to Search room first then you can split room"))

        room_line_vals = []
        ctr = 1
        partner_name = booking.room_booking_id.partner_id.name or ""
        # partner_name = booking.partner_id.name or ""
        name_parts = partner_name.split()  # Split the name by spaces
        first_name = name_parts[0] if len(name_parts) > 0 else ""
        last_name = name_parts[1] if len(name_parts) > 1 else ""
        

        for result in availability_results:
            rooms_reserved_count = int(result.rooms_reserved) if isinstance(
                result.rooms_reserved, str) else result.rooms_reserved

            # Create room lines
            for _ in range(rooms_reserved_count):
                new_booking_line = {
                    'room_id': False,
                    'checkin_date': booking.room_booking_id.checkin_date,
                    'checkout_date': booking.room_booking_id.checkout_date,
                    'uom_qty': 1,
                    'adult_count': booking.room_booking_id.adult_count,
                    'child_count': booking.room_booking_id.child_count,
                    'infant_count': booking.room_booking_id.infant_count,
                    'hotel_room_type': result.room_type.id,
                    'counter': ctr,
                }
                ctr += 1
                room_line_vals.append((0, 0, new_booking_line))

            # Create new adult records for this room
            for room_idx in range(rooms_reserved_count):
                for _ in range(booking.room_booking_id.adult_count):
                    self.env['reservation.adult'].create({
                        'reservation_id': booking.room_booking_id.id,
                        'room_type_id': result.room_type.id,
                        'room_sequence': room_idx + counter,
                        'first_name': first_name,
                        'last_name': last_name,
                        'profile': '',
                        'nationality': '',
                        'passport_number': '',
                        'id_number': '',
                        'visa_number': '',
                        'id_type': '',
                        'phone_number': '',
                        'relation': '',
                    })

            # Create new child records for this room
            for room_idx in range(rooms_reserved_count):
                for _ in range(booking.room_booking_id.child_count):
                    self.env['reservation.child'].create({
                        'reservation_id': booking.room_booking_id.id,
                        'room_type_id': result.room_type.id,
                        'room_sequence': room_idx + counter,
                        'first_name': '',
                        'last_name': '',
                        'profile': '',
                        'nationality': '',
                        'passport_number': '',
                        'id_number': '',
                        'visa_number': '',
                        'id_type': '',
                        'phone_number': '',
                        'relation': '',
                    })

            # Create new infant records for this room
            for room_idx in range(rooms_reserved_count):
                for _ in range(booking.room_booking_id.infant_count):
                    self.env['reservation.infant'].create({
                        'reservation_id': booking.room_booking_id.id,
                        'room_type_id': result.room_type.id,
                        'room_sequence': room_idx + counter,
                        'first_name': '',
                        'last_name': '',
                        'profile': '',
                        'nationality': '',
                        'passport_number': '',
                        'id_number': '',
                        'visa_number': '',
                        'id_type': '',
                        'phone_number': '',
                        'relation': '',
                    })

            # Mark this record as split
            result.split_flag = True

        self.update_counter_res_search(booking)

    

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    website_name = fields.Char(string="Website Name")
    website_url = fields.Char(string="Website URL")
    max_rooms = fields.Integer(string="Max Rooms")


class RoomAvailabilityWizard(models.TransientModel):
    _name = 'room.availability.wizard'
    _description = 'Room Availability Wizard'

    room_booking_id = fields.Many2one('room.booking', string='Booking')
    message = fields.Html(readonly=True)

    html_message = fields.Html(
        string='Formatted Message', compute='_compute_html_message', sanitize=False)

    previous_room_count = fields.Integer(string="Previous Room Count")

    def action_restore_room_count(self):
        self.ensure_one()
        _logger.debug("[DEBUG] action_restore_room_count TRIGGERED")

        if self.room_booking_id:
            current = self.room_booking_id.room_count
            previous = self.previous_room_count or 0

            if previous == 0:
                # No previous value stored — treat current as correct
                print("[DEBUG] Previous room count is 0, saving current as previous.")
                self.room_booking_id.write({
                    'previous_room_count': current,
                })
            elif current != previous:
                print(f"[DEBUG] Restoring room count from {current} to {previous}")
                self.room_booking_id.write({
                    'room_count': previous,
                    'previous_room_count': False,
                })
            else:
                print("[DEBUG] Room count unchanged. No action taken.")

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'room.booking',
            'res_id': self.room_booking_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('message')
    def _compute_html_message(self):
        for wizard in self:
            wizard.html_message = wizard.message

    def action_send_to_waiting(self):
        """Move the booking to Waiting List state."""
        self.room_booking_id.state = 'waiting'


class BookingCheckinWizard(models.TransientModel):
    _name = 'booking.checkin.wizard'
    _description = 'Check-in Confirmation Wizard'

    booking_ids = fields.Many2many(
        'room.booking', string='Booking', required=True)

    def action_confirm_checkin(self):
        """Batch check-in for eligible bookings with early check-in room availability check"""
        today = self.env.company.system_date.date()
        current_time = datetime.now().time()
        checkin_datetime = datetime.combine(today, current_time)

        # new_checkin_dt

        eligible_bookings = self.booking_ids.filtered(lambda b: len(b.room_line_ids) <= 1)
        _logger.debug("Eligible bookings for check-in: %s", eligible_bookings.mapped('name'))
        all_room_ids = eligible_bookings.mapped('room_line_ids.room_id.id')
        if all_room_ids:
            # Debug before executing
            _logger.debug("DEBUG overlap query params rooms=%s at=%s", all_room_ids, checkin_datetime)

            
            self.env.cr.execute("""
                SELECT DISTINCT rbl.room_id
                FROM room_booking_line rbl
                JOIN room_booking rb ON rbl.booking_id = rb.id
                WHERE rbl.room_id IN %s
                AND rb.state IN ('block','check_in')
                AND rb.checkin_date <= %s
                AND rb.checkout_date >= %s
            """, (tuple(all_room_ids), checkin_datetime, checkin_datetime))

            conflicts = self.env.cr.fetchall()
            # Debug after fetching
            _logger.debug("DEBUG overlap query result: %s", conflicts)

            if conflicts:
                room_ids = [c[0] for c in conflicts]
                self.env.cr.execute("SELECT name FROM hotel_room WHERE id IN %s", (tuple(room_ids),))
                rows = self.env.cr.dictfetchall()   # returns list of dicts: [{'name': '1101'}, {'name': '1102'}]
                # room_names = [str(row['name']) for row in rows] 
                room_names = [
                                str(list(r['name'].values())[0]) if isinstance(r['name'], dict)
                                else str(list(ast.literal_eval(r['name']).values())[0]) if isinstance(r['name'], str) and r['name'].startswith("{")
                                else str(r['name'])
                                for r in rows
                            ]

                raise ValidationError(_(
                    "The following rooms have a conflict with the new check-in date:\n%s"
                ) % ", ".join(room_names))

        # Prepare a template from the first booking's existing forecast lines
        if eligible_bookings:
            _logger.debug("ELIGIBLE BOOKINGS: %s", eligible_bookings.mapped('name'))
            _logger.debug("ELIGIBLE BOOKING---- %s",
                         eligible_bookings.sorted(lambda b: b.checkin_date))
            first = eligible_bookings.sorted(lambda b: b.checkin_date)[:1]
            _logger.debug(f"First booking for template: %s", first)
            # first._get_forecast_rates(from_rate_code=True)
            lines = first.rate_forecast_ids.sorted('date')
            if not lines:
                raise ValidationError(
                    f"No forecast lines on first booking {first.name}")
            tpl = lines[0]
            _logger.debug("Using template from booking with rate %s", tpl.rate)
            tpl_vals = {
                'rate': tpl.rate,
                'meals': tpl.meals,
                'fixed_post': tpl.fixed_post,
                'total': tpl.total,
                'before_discount': tpl.before_discount,
            }
            _logger.debug("Template values: %s", tpl_vals)

        booking_ids = []
        room_line_ids = []
        room_ids = []

        for booking in eligible_bookings:
            # Early check-in room availability check (unchanged)
            _logger.debug("--- Checking Booking: %s ---", booking.name)
            _logger.debug("Original Check-in Date: %s", booking.checkin_date)
            _logger.debug("Today: %s", today)
            _logger.debug("Checkout Date: %s", booking.checkout_date)
            _logger.debug("Room Type ID: %s", booking.hotel_room_type.id if booking.hotel_room_type else None)
            _logger.debug("Room Count: %s", booking.room_count)

            if booking.checkin_date and booking.checkin_date.date() > today:
                early_total = sum(
                    b.room_count for b in eligible_bookings
                    if b.checkin_date and b.checkin_date.date() > today
                )
                _logger.debug("Early Total Rooms Needed: %s", early_total)
                query = booking._get_room_search_query()
                params = {
                    'company_id': booking.env.company.id,
                    'from_date': today,
                    # 'to_date': booking.checkout_date,
                    'to_date': (booking.checkin_date - timedelta(days=1)) if booking.checkin_date else booking.checkout_date,
                    'room_count': early_total,
                    'room_type_id': booking.hotel_room_type.id if booking.hotel_room_type else None,
                }
                _logger.debug("SQL Params: %s", params)
                booking.env.cr.execute(query, params)
                avails = booking.env.cr.dictfetchall()
                _logger.debug("Available Rooms Returned: %s", avails)
                if not avails:
                    raise ValidationError(
                        f"No availability info found for booking: {booking.name}")
                # if avails[0].get('min_free_to_sell', 0.0) < booking.room_count:
                if avails[0].get('min_free_to_sell', 0.0) < early_total:
                    raise ValidationError(
                        f"Only {avails[0]['min_free_to_sell']} rooms are available for early check-in for booking: {booking.name}, but {early_total} required."
                    )

            # Collect IDs for later SQL updates
            booking_ids.append(booking.id)
            for line in booking.room_line_ids:
                room_line_ids.append(line.id)
                room_ids.append(line.room_id.id)

            # ─────────────────────────────────────────────────────────
            # New logic: insert forecast lines for days before the real check-in
            original_date = booking.checkin_date.date()
            days_early = (original_date - today).days
            if days_early > 0:
                rows = []
                for i in range(days_early):
                    day = today + timedelta(days=i)
                    rows.append((
                        booking.id,
                        day,
                        tpl_vals['rate'],
                        tpl_vals['meals'],
                        tpl_vals['fixed_post'],
                        tpl_vals['total'],
                        tpl_vals['before_discount'],
                    ))
                self.env.cr.executemany(
                    """
                    INSERT INTO room_rate_forecast
                        (room_booking_id, date, rate, meals, fixed_post, total, before_discount)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, rows
                )
            # ─────────────────────────────────────────────────────────

            # (The original forecast-reset and recalc lines have been removed)

        # Check for conflicting check-ins
        booking._check_checkin_availability(checkin_datetime)

        cr = self.env.cr
        # Step 1: Update hotel_room
        if room_ids:
            cr.execute(
                """
                UPDATE hotel_room
                SET status = 'occupied', is_room_avail = FALSE
                WHERE id IN %s
                """, (tuple(room_ids),)
            )

        # Step 2: Update room_booking_line
        if room_line_ids:
            cr.execute(
                """
                UPDATE room_booking_line
                SET state_ = 'check_in'
                WHERE id IN %s
                """, (tuple(room_line_ids),)
            )
            self.env['room.booking']._log_room_line_status(
                line_ids=room_line_ids,
                status='check_in'
            )
            self.env['room.booking']._sql_update_line_dates(room_line_ids, 
                                                            checkin_datetime, booking.checkout_date)

        # Step 3: Update room_booking
        if booking_ids:
            cr.execute(
                """
                UPDATE room_booking
                SET state = 'check_in',
                    checkin_date = %s
                WHERE id IN %s
                """, (checkin_datetime, tuple(booking_ids))
            )

        # Final notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking Checked In Successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    @api.model
    def default_get(self, fields_list):
        res = super(BookingCheckinWizard, self).default_get(fields_list)
        booking_ids = self._context.get('default_booking_ids')
        if booking_ids:
            res['booking_ids'] = [(6, 0, booking_ids)]
        return res

    def action_cancel(self):
        """ Action to cancel the check-in """
        return {'type': 'ir.actions.act_window_close'}


class RoomBookingReport(models.AbstractModel):
    _name = 'report.hotel_management.report_consolidated_template'
    _description = 'Consolidated Room Booking Report'

    def _get_record_from_context(self, context):
        room_booking_id = context.get('room_booking_id')
        if not room_booking_id:
            # Fallback to docids
            room_booking_id = self.env.context.get(
                'active_id') or self.env.context.get('active_ids', [])
        if room_booking_id:
            return self.env['room.booking'].browse(room_booking_id)
        return None

    @api.model
    def _calculate_average_rate(self, rate_field, records):
        """
        Helper function to calculate the average of rates in the given records.
        """
        rates = [getattr(record, rate_field, 0)
                 for record in records if getattr(record, rate_field, 0)]
        return sum(rates) / len(rates) if rates else 0

    def _get_report_values(self, docids, data=None):
        context = self.env.context
        _logger.debug("Context received in report: %s", context)
        record = self._get_record_from_context(context)

        if not record:
            raise ValueError(
                "No record found for room_booking_id in the context.")

        # Fetch rates and meals for the room booking
        forecast_records = self.env['room.rate.forecast'].search(
            [('room_booking_id', '=', record.id)])
        if not forecast_records:
            raise ValueError(
                f"No forecast records found for room_booking_id {record.id}")

        # Calculate averages for rates and meals
        rate_avg = self._calculate_average_rate('rate', forecast_records)
        meals_avg = self._calculate_average_rate('meals', forecast_records)

        # Log details for debugging
        _logger.debug("Rate Average: %s", rate_avg)
        _logger.debug("Meals Average: %s", meals_avg)

        # Prepare booking details
        booking_details = [{
            'room_id': record.room_id.id if record.room_id else None,
            'room_number': record.room_id.name if record.room_id else 'N/A',
            'hotel_room_name': record.room_id.name if record.room_id else 'N/A',
            'adults': [{
                'Nationality': adult.nationality.name,
                'Passport NO.': adult.passport_number,
                'Tel no.': adult.phone_number,
                'ID Number': adult.id_number,
            } for adult in record.adult_ids],
            'children': [{
                'Nationality': child.nationality.name,
                'Passport NO.': child.passport_number,
                'Tel no.': child.phone_number,
                'ID Number': child.id_number,
            } for child in record.child_ids],
        }]
        # Log details for debugging
        _logger.debug("Booking Details: %s", booking_details)

        return {
            'doc_ids': docids,
            'doc_model': 'room.booking',
            'docs': record,  # Pass the main record
            'data': data,  # Additional data, if needed
            'booking_details': booking_details,  # Booking details for the template
            'rate_avg': rate_avg,  # Average room rate
            'meals_avg': meals_avg,  # Average meal rate
        }


class ConfirmEarlyCheckoutWizard(models.TransientModel):
    _name = 'confirm.early.checkout.wizard'
    _description = 'Confirm Early Check-Out Wizard'

    booking_ids = fields.Many2many('room.booking', string='Booking')

    @api.model
    def default_get(self, fields_list):
        res = super(ConfirmEarlyCheckoutWizard, self).default_get(fields_list)
        booking_ids = self._context.get('default_booking_ids')
        if booking_ids:
            res['booking_ids'] = [(6, 0, booking_ids)]
        return res

    

    def action_confirm_checkout(self):
        self.ensure_one()
        _logger.debug("Early-checkout start: %d bookings selected", len(self.booking_ids))

        # Prepare timestamps
        today = self.env.company.system_date.date()
        now_dt = datetime.combine(today, datetime.now().time())
        yesterday = today - timedelta(days=1)
    
        if self.env.company.system_date > now_dt:
            now_dt = self.env.company.system_date + timedelta(minutes=3)

        # 1) Gather eligible bookings + their forecast & posting items
        data = []
        for booking in self.booking_ids:
            if len(booking.room_line_ids) > 1:
                _logger.debug("Skipping %s: more than one room_line", booking.name)
                continue
            forecasts = booking.rate_forecast_ids.filtered(lambda l: l.date == today)
            if not forecasts:
                _logger.warning("Skipping %s: no forecast for %s", booking.name, today)
                continue

            meal_item, unused1, unused2, unused3 = booking.get_meal_rates(booking.meal_pattern.id)
            unused4, unused5, unused6, rate_item, package_items = booking.get_all_prices(
                booking.checkin_date, booking
            )
            data.append({
                'booking':      booking,
                'forecasts':    forecasts,
                'meal_item':    meal_item,
                'rate_item':    rate_item,
                'package_item': package_items and package_items[-1] or False,
            })

        if not data:
            _logger.debug("No bookings eligible for early checkout.")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _("No bookings to check out."),
                    'next': {},
                }
            }
        _logger.debug("Will invoice %d bookings", len(data))

        # 2) Bulk create invoice headers
        header_vals = []
        for d in data:
            b = d['booking']
            header_vals.append({
                'move_type':           'out_invoice',
                'invoice_date':        today,
                'partner_id':          b.partner_id.id,
                'ref':                 b.name,
                'hotel_booking_id':    b.id,
                'group_booking_name':  b.group_booking.name or '',
                'parent_booking_name': b.parent_booking_name or '',
                'room_numbers':        b.room_ids_display or '',
            })
        moves = self.env['account.move'].create(header_vals)
        _logger.debug("Created %d invoices", len(moves))

        # 3) Bulk create invoice lines
        line_vals = []
        for d, move in zip(data, moves):
            for f in d['forecasts']:
                if f.rate > 0:
                    line_vals.append({
                        'move_id':               move.id,
                        'posting_item_id':       d['rate_item'],
                        'posting_description':   'Rate',
                        'posting_default_value': f.rate,
                    })
                if f.meals > 0:
                    line_vals.append({
                        'move_id':               move.id,
                        'posting_item_id':       d['meal_item'],
                        'posting_description':   'Meal',
                        'posting_default_value': f.meals,
                    })
                if f.packages > 0 and d['package_item']:
                    line_vals.append({
                        'move_id':               move.id,
                        'posting_item_id':       d['package_item'],
                        'posting_description':   'Package',
                        'posting_default_value': f.packages,
                    })
        if line_vals:
            created_lines = self.env['account.move.line'].create(line_vals)
            _logger.debug("Created %d invoice lines", len(created_lines))

        # 4) Bulk-SQL update room_booking
        booking_ids = [d['booking'].id for d in data]
        self.env.cr.execute("""
            UPDATE room_booking
               SET checkout_date         = %s,
                   state                 = 'check_out',
                   invoice_status        = 'invoiced',
                   invoice_button_visible= TRUE
             WHERE id IN %s
        """, (now_dt, tuple(booking_ids)))
        _logger.debug("SQL updated %d room_booking records", self.env.cr.rowcount)

        # 5) Bulk-SQL update room_booking_line + log
        room_line_ids = sum((d['booking'].room_line_ids.ids for d in data), [])
        if room_line_ids:
            self.env.cr.execute("""
                UPDATE room_booking_line
                   SET state_ = 'check_out'
                 WHERE id IN %s
            """, (tuple(room_line_ids),))
            _logger.debug("SQL updated %d room_booking_line records", self.env.cr.rowcount)

            self.booking_ids._sql_update_line_dates(room_line_ids, 
                                                            booking.checkin_date, now_dt)
            # Use ORM helper to log history
            self.booking_ids._log_room_line_status(
                line_ids=room_line_ids, status='check_out'
            )
            _logger.debug("Logged room line status for %d lines", len(room_line_ids))


        # 6) FAST forecast rebuild via SQL + one recompute call
        forecast_model = self.env['room.rate.forecast']
        table = forecast_model._table
        
        # # Determine date condition based on number of nights
        # # For 1 night bookings: use > (exclude today)
        # # For multi-night bookings: use >= (include today)
        # booking_nights = {}
        # for d in data:
        #     booking = d['booking']
        #     if booking.checkin_date and booking.checkout_date:
        #         nights = (booking.checkout_date.date() - booking.checkin_date.date()).days
        #         print(f"NIGHTS: {nights}")
        #         booking_nights[booking.id] = nights
        
        # # Check if all bookings have 0 or 1 night
        # all_single_night = all(nights <= 1 for nights in booking_nights.values())
        # print(f"All Single Night; {all_single_night} ")
        # date_operator = ">" if all_single_night else ">="
        # print(f" Date Operator: {date_operator}")
            
        # _logger.debug("Booking nights: %s, Using operator: %s", booking_nights, date_operator)

        
            
        # ---- Get today's forecast count before deletion ----
    #     self.env.cr.execute(f"""
    #         SELECT COUNT(*)
    #         FROM {table}
    #         WHERE room_booking_id = ANY(%s)
    #         AND date {date_operator} %s
    # """, (booking_ids, today))
    #     forecast_count = self.env.cr.fetchone()[0]
    #     _logger.debug("Today's forecast count to delete: %d", forecast_count)

        # forecast_model = self.env['room.rate.forecast']
        # table = forecast_model._table

        self.env.cr.execute(f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE room_booking_id = ANY(%s)
            AND date > %s
        """, (booking_ids, today))

        for booking in self.env['room.booking'].browse(booking_ids):
            # if booking.checkout_date == today and booking.no_of_nights == 0:
            if booking.checkout_date == today and (booking.checkout_date - booking.checkin_date).days == 0:
                # Same day check-in/checkout: ensure we have at least 1 record for today
                # First check if today's record exists
                self.env.cr.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE room_booking_id = %s AND date = %s",
                    (booking.id, today)
                )
                today_count = self.env.cr.fetchone()[0]
                
                if today_count > 0:
                    # Keep only today's row (delete all other dates)
                    self.env.cr.execute(
                        f"DELETE FROM {table} WHERE room_booking_id = %s AND date != %s",
                        (booking.id, today)
                    )
                else:
                    # No today record exists, keep the most recent record (likely check-in date)
                    self.env.cr.execute(
                        f"SELECT date FROM {table} WHERE room_booking_id = %s ORDER BY date DESC LIMIT 1",
                        (booking.id,)
                    )
                    latest_record = self.env.cr.fetchone()
                    if latest_record:
                        latest_date = latest_record[0]
                        # Keep the latest record, delete all others
                        self.env.cr.execute(
                            f"DELETE FROM {table} WHERE room_booking_id = %s AND date != %s",
                            (booking.id, latest_date)
                        )
            else:
                # Ensure we always keep at least one record - never make forecast empty
                # First check how many records exist before today
                self.env.cr.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE room_booking_id = %s AND date < %s",
                    (booking.id, today)
                )
                records_before_today = self.env.cr.fetchone()[0]
                
                if records_before_today > 0:
                    # We have records before today, safe to delete from today onwards
                    self.env.cr.execute(
                        f"DELETE FROM {table} WHERE room_booking_id = %s AND date >= %s",
                        (booking.id, today)
                    )
                else:
                    # No records before today, keep at least one record (the earliest available)
                    self.env.cr.execute(
                        f"SELECT date FROM {table} WHERE room_booking_id = %s ORDER BY date ASC LIMIT 1",
                        (booking.id,)
                    )
                    earliest_record = self.env.cr.fetchone()
                    if earliest_record:
                        earliest_date = earliest_record[0]
                        # Keep the earliest record, delete all others after it
                        self.env.cr.execute(
                            f"DELETE FROM {table} WHERE room_booking_id = %s AND date > %s",
                            (booking.id, earliest_date)
                        )
            # else:
            #     # Default: delete all after today
            #     self.env.cr.execute(
            #         f"DELETE FROM {table} WHERE room_booking_id = %s AND date > %s",
            #         (booking.id, today)
            #     )

    #     self.env.cr.execute(f"""
    #         DELETE FROM {table}
    #             WHERE room_booking_id = ANY(%s)
    #             AND date            {date_operator} %s
    # """, (booking_ids, today))
    #     _logger.debug("SQL deleted %d forecast rows", self.env.cr.rowcount)


    #    # 6) FAST forecast rebuild via SQL + one recompute call
    #     forecast_model = self.env['room.rate.forecast']
    #     table = forecast_model._table
    #     # ---- Get today's forecast count before deletion ----
    #     self.env.cr.execute(f"""
    #         SELECT COUNT(*)
    #         FROM {table}
    #         WHERE room_booking_id = ANY(%s)
    #         AND date > %s
    #     """, (booking_ids, today))
    #     forecast_count = self.env.cr.fetchone()[0]
    #     _logger.debug("Today's forecast count to delete: %d", forecast_count)

    #     self.env.cr.execute(f"""
    #         DELETE FROM {table}
    #          WHERE room_booking_id = ANY(%s)
    #            AND date            > %s
    #     """, (booking_ids, today))
    #     _logger.debug("SQL deleted %d forecast rows", self.env.cr.rowcount)

        _logger.debug("Recomputing forecasts for all selected bookings in one batch")
        _logger.debug("Booking IDs: %s", booking_ids)

        self.env.cr.commit()

        return {
        'type': 'ir.actions.client',
        'tag': 'display_notification',
        'params': {
            'type': 'success',
            'message': _("Booking Checked Out Successfully!"),
            'next': {'type': 'ir.actions.act_window_close'},
        }
    }
    
    def action_cancel(self):
        """ Action to cancel the check-in """
        return {'type': 'ir.actions.act_window_close'}


class BookingPostingItem(models.Model):
    _name = 'booking.posting.item'
    _description = 'Booking Posting Item'

    booking_id = fields.Many2one(
        'room.booking', string="Booking", required=True, ondelete='cascade')
    posting_item_id = fields.Many2one('posting.item', string="Posting Item")
    posting_item_selection = fields.Selection(
        [
            ('first_night', 'First Night'),
            ('every_night', 'Every Night'),
        ],
        string="Posting Item Option",
        help="Select whether the posting applies to the first night or every night."
    )
    default_value = fields.Float(
        related='posting_item_id.default_value', string="Default Value", readonly=True)
    item_code = fields.Char(
        related='posting_item_id.item_code', string="Item Code", readonly=True)
    description = fields.Char(
        related='posting_item_id.description', string="Description", readonly=True)


class RoomBookingPostingItem(models.Model):
    _name = 'room.booking.posting.item'

    booking_id = fields.Many2one(
        'room.booking',
        string="Room Booking",
        ondelete='cascade',
        required=True,
        help="Reference to the room booking."
    )
   
    posting_item_id = fields.Many2one(
        'posting.item',
        string="Posting Item",
        required=True,
        domain="""[
            ('main_department', '!=', False),
            '|', '|', '|',
            ('main_department.charge_group', '!=', False),
            ('main_department.payment_group', '!=', False),
            ('main_department.tax_group', '!=', False),
            ('main_department.adjustment', '!=', False)
        ]""",

        
        help="The posting item linked to this booking, filtered by department settings."
    )

    item_code = fields.Char(string="Item Code")
    description = fields.Char(string="Description")
    
    posting_item_selection = fields.Selection(
        [
            ('first_night', 'First Night'),
            ('every_night', 'Every Night'),
            ('custom_date', 'Custom Date')
        ],
        required=True,
        string="Posting Item Option",
        help="Select whether the posting applies to the first night or every night."
    )
    from_date = fields.Datetime(string="From Date")
    to_date = fields.Datetime(string="To Date")

    @api.constrains('posting_item_selection', 'from_date', 'to_date')
    def _check_custom_date_required_fields(self):
        for record in self:
            if record.posting_item_selection == 'custom_date':
                if not record.from_date or not record.to_date:
                    raise exceptions.ValidationError(
                        "Both 'From Date' and 'To Date' are required when 'Custom Date' is selected."
                    )

    default_value = fields.Float(string="Default Value")

    @api.constrains('posting_item_id', 'booking_id')
    def _check_unique_posting_item(self):
        """Ensure the same posting_item_id is not selected twice in the same booking."""
        for record in self:
            duplicates = self.env['room.booking.posting.item'].search([
                ('booking_id', '=', record.booking_id.id),
                ('posting_item_id', '=', record.posting_item_id.id),
                ('id', '!=', record.id)  # Exclude the current record
            ])
            if duplicates:
                raise ValidationError(
                    f"The Posting Item '{record.posting_item_id}' is already selected for this booking. "
                    "Please choose a different Posting Item."
                )

    @api.onchange('from_date', 'to_date')
    def _onchange_dates(self):
        """Validate that from_date and to_date are within the check-in and check-out date range."""
        for record in self:
            if record.to_date and not record.from_date:
                raise ValidationError(
                    "Please select 'From Date' before selecting 'To Date'.")
            if record.booking_id:
                # Convert check-in, check-out, from_date, and to_date to date only
                checkin_date = fields.Date.to_date(
                    record.booking_id.checkin_date)
                checkout_date = fields.Date.to_date(
                    record.booking_id.checkout_date)
                from_date = fields.Date.to_date(
                    record.from_date) if record.from_date else None
                to_date = fields.Date.to_date(
                    record.to_date) if record.to_date else None

                # Debugging: Print normalized dates
               
                # Validate from_date
                if from_date:
                    if not (checkin_date <= from_date <= checkout_date):
                        raise ValidationError(
                            "The 'From Date' must be between the check-in and check-out dates of the booking."
                        )

                # Validate to_date
                if to_date:
                    if not (from_date <= to_date <= checkout_date):
                        raise ValidationError(
                            "The 'To Date' must be greater than or equal to 'From Date' and within the check-out date."
                        )

    @api.onchange('posting_item_id')
    def _onchange_posting_item_id(self):
        """Update related fields when posting_item_id changes."""
        if self.posting_item_id:
            self.item_code = self.posting_item_id.item_code
            self.description = self.posting_item_id.description
            self.default_value = self.posting_item_id.default_value
            


class RoomBookingLineStatus(models.Model):
    _name = 'room.booking.line.status'
    _description = 'Room Booking Line Status'

    booking_line_id = fields.Many2one(
        'room.booking.line', string="Booking Line", ondelete='cascade')
    status = fields.Selection([
        ('not_confirmed', 'Not Confirmed'),
        ('confirmed', 'Confirmed'),
        ('waiting', 'Waiting List'),
        ('no_show', 'No Show'),
        ('block', 'Block'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ('reserved', 'Reserved')
    ], string="Status")
    change_time = fields.Datetime(string="Change Time")


class RoomBookingUpdateWizard(models.TransientModel):
    _name = 'room.booking.update.wizard'
    _description = 'Wizard to Update Check-In and Check-Out Dates'

    checkin_date = fields.Datetime(string='Check-In Date')
    readonly_checkin_date = fields.Boolean(string="Lock Check-In", default=False)

    checkout_date = fields.Datetime(string='Check-Out Date')
    readonly_checkout_date = fields.Boolean(string="Lock Check-Out", default=False)

    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern")
    readonly_meal_pattern = fields.Boolean(string="Lock Meal Pattern", default=False)

    source_of_business = fields.Many2one('source.business', string='Source of Business')
    readonly_source_of_business = fields.Boolean(string="Lock Source of Business", default=False)

    room_type = fields.Many2one(
        'room.type', string="Room Type",
        domain=lambda self: [
        ('obsolete', '=', False),
        ('id', 'in', self.env['hotel.inventory'].search([
            ('company_id', '=', self.env.company.id),
        ]).mapped('room_type.id'))
        ],tracking=True)

    readonly_room_type = fields.Boolean(string="Lock Room Type", default=False)

    market_segment = fields.Many2one('market.segment', string='Market Segment')
    readonly_market_segment = fields.Boolean(string="Lock Market Segment", default=False)

    room_booking_id = fields.Many2one('room.booking', string="Booking")

    rate_code = fields.Many2one('rate.code', string='Rate Code')


    @api.onchange('rate_code', 'checkin_date', 'checkout_date')
    def _onchange_rate_code(self):
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return

        first_booking = self.env['room.booking'].browse(active_ids[0])
        if not first_booking.exists():
            return

        current_state = first_booking.state

        if current_state == 'check_in':
            self.checkin_date = first_booking.checkin_date

        
        if self.rate_code and self.checkin_date and self.checkout_date:
            rate_details = self.env['rate.detail'].search([
                ('rate_code_id', '=', self.rate_code.id),
                ('from_date', '<=', self.checkin_date),
                ('to_date', '>=', self.checkout_date)
            ], limit=1)

            if not rate_details:
                warning = {
                    'warning': {
                        'title': _('Invalid Rate Code'),
                        'message': _('The selected rate code "%s" is expired or not valid for the selected dates. Please choose another rate code.') % self.rate_code.code,
                    }
                }
                # Clear the invalid rate_code
                self.rate_code = False
                return warning

    readonly_rate_code = fields.Boolean(string="Lock Rate Code", default=False)

    nationality = fields.Many2one('res.country', string='Nationality')
    readonly_nationality = fields.Boolean(string="Lock Nationality", default=False)

    blocked_room_action = fields.Selection(
        [
            ('auto_assign', 'Automatically assign rooms of the new type'),
            ('unassign_confirm',
             'Unassign the room and change the booking status to Confirmed')
        ],
        string='Blocked Room Action'
    )

    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company,
        readonly=True
    )
    readonly_company_id = fields.Boolean(string="Lock Company", default=True)  # Typically company shouldn't be changed

    

    @api.constrains('checkin_date', 'checkout_date')
    def _check_dates(self):
        # today = datetime.now()
        today = self.env.company.system_date.date()
        for record in self:
            if record.checkin_date and record.checkin_date.date() < today:
                raise UserError("Check-In Date cannot be earlier than today.")
            if record.checkin_date and record.checkout_date and record.checkout_date <= record.checkin_date:
                raise UserError(
                    "Check-Out Date must be greater than Check-In Date.")

    

    @api.model
    def default_get(self, fields_list):
        res = super(RoomBookingUpdateWizard, self).default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            # Assume all selected bookings must share the same state.
            # We simply check the first booking’s state:
            first_booking = self.env['room.booking'].browse(active_ids[0])
            if first_booking.state in ('no_show', 'check_out'):
                # Mark every field‐readonly flag True
                res.update({
                    'readonly_checkin_date': True,
                    'readonly_checkout_date': True,
                    'readonly_meal_pattern': True,
                    'readonly_rate_code': True,
                    'readonly_nationality': True,
                    'readonly_source_of_business': True,
                    'readonly_room_type': True,
                    'readonly_market_segment': True,
                    'readonly_blocked_room_action': True,
                })
            
            if first_booking.state == 'check_in':
                # Mark check-in date readonly if booking is already checked in
                res.update({
                    'readonly_checkin_date': True,
                })
            if first_booking.state in ('block', 'check_in'):
                # Allow updating check-in and check-out dates only if booking is in 'block' or 'check_in' state
                res.update({
                    'readonly_room_type': True, 
                })
            if first_booking.state == 'not_confirmed':
                # Mark check-in date readonly if booking is already checked in
                res.update({
                    'readonly_room_type': True,
                })
        return res
    

    def action_update_selected_bookings(self):
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return {'type': 'ir.actions.act_window_close'}

        bookings = self.env['room.booking'].browse(active_ids)
        total_room_count = sum(booking.room_count for booking in bookings)
        _logger.debug("Updating %d bookings", len(bookings))
        booking = bookings[0]
        _logger.debug("Booking to update: %s", booking.name)

        # ─── 1) DATE VALIDATIONS ──────────────────────────────────────────────
        old_checkin, old_checkout = booking.checkin_date, booking.checkout_date
        # Only check-in changed
        if self.checkin_date and not self.checkout_date:
            if self.checkin_date > old_checkout:
                raise ValidationError(
                    f"Invalid date: Check-in ({self.checkin_date}) "
                    f"cannot be after existing Check-out ({old_checkout})."
                )
        # Only Check-out changed
        if self.checkout_date and not self.checkin_date:
            if self.checkout_date < old_checkin:
                raise ValidationError(
                    f"Invalid date: Check-out ({self.checkout_date}) "
                    f"cannot be earlier than existing Check-in ({old_checkin})."
                )
        # Both changed -> Check-in > Check-out
        if self.checkin_date and self.checkout_date:
            if self.checkin_date > self.checkout_date:
                raise ValidationError(
                    f"Invalid dates: Check-in ({self.checkin_date}) "
                    f"cannot be after Check-out ({self.checkout_date})."
                )
            if self.checkout_date < self.checkin_date:
                raise ValidationError(
                    f"Invalid dates: Check-out ({self.checkout_date}) "
                    f"cannot be earlier than Check-in ({self.checkin_date})."
                )

        # ─── 2) DETERMINE WHAT REALLY CHANGED ────────────────────────────────
        dates_changed     = bool(self.checkin_date or self.checkout_date)
        room_type_changed = bool(self.room_type)
        # rate_code-only updates will skip availability/overlap
        _logger.debug("dates_changed=%s, room_type_changed=%s, rate_code=%s",
                     dates_changed, room_type_changed, bool(self.rate_code))

        # ─── 3) AVAILABILITY & OVERLAP CHECKS (only on date/type changes) ────
        if dates_changed or room_type_changed:
            # 3a) SQL availability check
            hotel_room_type_id = (
                self.room_type.id
                if self.room_type
                else booking.hotel_room_type.id
            )
            query_template = booking._get_room_search_query()
            
            params = {
                'company_id': self.env.company.id,
                'room_count': booking.room_count,
                'room_type_id': hotel_room_type_id,
            }

            # old_checkin_minus_1_day = old_checkin - timedelta(days=1)
            # Separate params for check-in date changes
            if self.checkin_date:
                params.update({
                    'from_date': self.checkin_date,
                    'to_date': old_checkin,
                })

            # Separate params for check-out date changes
            if self.checkout_date:
                params.update({
                    'from_date': old_checkout,
                    'to_date': self.checkout_date,
                })
            # _logger.debug("Running availability query with %s", params)
            if not self.checkin_date and self.room_type:
                params.update({
                    'from_date': old_checkin,
                })
            if not self.checkout_date and self.room_type:
                params.update({
                    'to_date': old_checkout,
                })
            if (not self.checkin_date or not self.checkout_date) and self.room_type and len(bookings)>1:
                avail_count = 0
                for b in bookings:
                    params.update({
                        'from_date': b.checkin_date,
                        'to_date': b.checkout_date,
                        'room_count': 1,
                    })
                    _logger.debug(" in the multiple booking Running availability query with %s", params)
                    self.env.cr.execute(query_template, params)
                    avail_list = self.env.cr.dictfetchall()
                    _logger.debug("Availability: %s", avail_list)
                    for avail in avail_list:
                        if avail.get('min_free_to_sell', 0):
                            avail_count += 1

                    _logger.debug("avail count ={%s}",avail_count)
                if avail_count < total_room_count:
                    raise ValidationError(
                        _("Only %s room(s) of type '%s' are available. You requested %s.") 
                        % (avail_count, avail['room_type_name'], total_room_count)
                    )

            _logger.debug("Running availability query with %s", params)

            self.env.cr.execute(query_template, params)
            avail_list = self.env.cr.dictfetchall()
            _logger.debug("Availability: %s", avail_list)

            
            for avail in avail_list:
                if avail.get('min_free_to_sell', 0) < total_room_count:
                    raise exceptions.ValidationError(
                        _(
                            "Only %s room(s) of type '%s' are available for %s → %s. "
                            "You requested %s."
                        ) % (
                            avail.get('min_free_to_sell', 0),
                            avail.get('room_type_name'),
                            booking.checkin_date,
                            booking.checkout_date,
                            total_room_count,
                        )
                    )

            for b in bookings:
                all_room_ids = [line.room_id.id for line in b.room_line_ids if line.room_id]
                checkout_date_to_use = self.checkout_date if self.checkout_date else b.checkout_date  # Use old checkout date if not provided
                current_booking_id = b.id   

                for line in b.room_line_ids:
                    room_name = line.room_id.name
                    if not room_name:
                        continue
                    _logger.debug("self.checkin_date: %s %s", self.checkin_date, checkout_date_to_use)
                    checkin_date_to_use = self.checkin_date if self.checkin_date else b.checkout_date
                    _logger.debug("self.checkin_date: %s %s", self.checkin_date, checkout_date_to_use)
                    checkin_date_to_use = self.checkin_date if self.checkin_date else b.checkout_date
                    # Execute the SQL query to find any conflicting bookings for this room
                    self.env.cr.execute("""
                        SELECT DISTINCT rbl.room_id,  rb.checkin_date
                        FROM room_booking_line rbl
                        JOIN room_booking rb ON rbl.booking_id = rb.id
                        WHERE rbl.room_id IN %s
                        AND rb.state IN ('block', 'check_in')
                        AND rb.checkin_date <= %s
                        AND rb.checkout_date >= %s
                        AND rbl.booking_id != %s  -- Exclude the current booking
                        AND NOT (DATE(rb.checkout_date) = DATE(%s))
                    """, (tuple(all_room_ids), checkout_date_to_use, checkin_date_to_use, current_booking_id,checkin_date_to_use))
                
                    conflicts = self.env.cr.fetchall()
                    
                    # Debug after fetching
                    _logger.debug("DEBUG overlap query result: %s", conflicts)

                    if conflicts:
                        # 2. Filter out conflicts where checkin_date == my checkout_date (only dates)
                        my_checkout_date = checkout_date_to_use.date()
                        filtered_conflicts = [c for c in conflicts if c[1] and c[1].date() != my_checkout_date]

                        if filtered_conflicts:
                            room_ids = [c[0] for c in filtered_conflicts]
                            self.env.cr.execute("SELECT name FROM hotel_room WHERE id IN %s", (tuple(room_ids),))
                            rows = self.env.cr.dictfetchall()   # [{'name': '1101'}, {'name': '1102'}]
                            # room_names = [str(r.get('name', '')) for r in rows if r.get('name')]
                            room_names = []
                            for r in rows:
                                name_val = r.get('name')
                                if isinstance(name_val, dict) and name_val:  # handle dict
                                    room_names.append(list(name_val.values())[0])
                                elif isinstance(name_val, str):
                                    room_names.append(name_val)
                                elif name_val is not None:
                                    room_names.append(str(name_val))

                            raise ValidationError(_(
                                "The following rooms have a conflict with the new check-in date:\n%s"
                            ) % ", ".join(room_names))


        # ─── 4) BULK UPDATE BOOKING FIELDS ───────────────────────────────────
        clauses, values = [], []
        if self.checkin_date:
            clauses.append("checkin_date = %s");    values.append(self.checkin_date)
        if self.checkout_date:
            clauses.append("checkout_date = %s");   values.append(self.checkout_date)
        if self.meal_pattern:
            clauses.append("meal_pattern = %s");    values.append(self.meal_pattern.id)
        if self.rate_code:
            clauses.append("rate_code = %s");       values.append(self.rate_code.id)
        if self.nationality:
            clauses.append("nationality = %s");     values.append(self.nationality.id)
        if self.source_of_business:
            clauses.append("source_of_business = %s"); values.append(self.source_of_business.id)
        if self.market_segment:
            clauses.append("market_segment = %s");  values.append(self.market_segment.id)
        if self.room_type:
            clauses.append("hotel_room_type = %s"); values.append(self.room_type.id)

        if clauses:
            booking_ids = tuple(bookings.ids)
            values.append(booking_ids)
            sql = f"""
                UPDATE room_booking
                SET {', '.join(clauses)}
                WHERE id IN %s
            """
            _logger.debug("Executing bulk UPDATE: %s; values=%s", sql, values)
            self.env.cr.execute(sql, tuple(values))
            _logger.debug("Bulk UPDATE executed successfully")
            self.env.cr.commit()
            _logger.debug("Bulk UPDATE committed successfully")

            # 1. build just the date clauses for room_booking_line
            line_clauses, line_vals = [], []
            if self.checkin_date:
                line_clauses.append("checkin_date = %s")
                line_vals.append(self.checkin_date)
            if self.checkout_date:
                line_clauses.append("checkout_date = %s")
                line_vals.append(self.checkout_date)

            # 2. only run if either date was present
            if line_clauses:
                # reuse booking_ids from above
                line_vals.append(booking_ids)
                sql_line = f"""
                    UPDATE room_booking_line
                       SET {', '.join(line_clauses)}
                     WHERE booking_id IN %s
                """
                _logger.debug("Updating booking_line dates: %s; params=%s", sql_line, line_vals)
                self.env.cr.execute(sql_line, tuple(line_vals))
                _logger.debug("room_booking_line date update committed for %s", booking_ids)

        # ─── 5) RE‑FORECAST RATES (when rate, meal or dates change) ────────────
        if self.rate_code or self.meal_pattern or dates_changed:
            _logger.debug("Reforecasting rates for %d bookings", len(bookings))
            # group bookings by (checkin, checkout, adult_count)
            groups = {}
            _logger.debug("Grouping bookings by (checkin, checkout, adult_count)")
            for b in bookings:
                key = (b.checkin_date, b.checkout_date, b.adult_count)
                _logger.debug("Grouping booking %s by %s", b.name, key)
                groups.setdefault(key, []).append(b)
            _logger.debug("Grouped bookings: %s", groups)

            for (chkin, chkout, adults), group in groups.items():
                first = group[0]
                _logger.debug("FIRST: %s ", first)
                ids = [b.id for b in group]
                _logger.debug("IDS: %s ", ids)
                _logger.debug("GROUP: %s ", group)

                # delete old forecasts
                self.env.cr.execute(
                    "DELETE FROM room_rate_forecast WHERE room_booking_id = ANY(%s)",
                    (ids,)
                )

                # regen on first booking
                first._get_forecast_rates(from_rate_code=True)
                _logger.debug("FORECASTS: %s ", first._get_forecast_rates(from_rate_code=True))

                # copy to others
                other_ids = [bid for bid in ids if bid != first.id]
                _logger.debug("OTHER_IDS: %s ", other_ids)
                if other_ids:
                    self.env.cr.execute("""
                        INSERT INTO room_rate_forecast
                            (room_booking_id, date, rate, meals, fixed_post, total, before_discount)
                        SELECT
                            dest.booking_id,
                            src.date,
                            src.rate,
                            src.meals,
                            src.fixed_post,
                            src.total,
                            src.before_discount
                        FROM room_rate_forecast AS src
                        CROSS JOIN UNNEST(%s) AS dest(booking_id)
                        WHERE src.room_booking_id = %s
                    """, (other_ids, first.id))
                    self.env.cr.commit()

        # ─── 6) UPDATE ROOM_LINE STATE & TYPE ────────────────────────────────
        if self.room_type:
            line_ids = bookings.mapped('room_line_ids').ids
            if line_ids:
                self.env.cr.execute("""
                    UPDATE room_booking_line
                    SET hotel_room_type = %s,
                        state_          = %s
                    WHERE id = ANY(%s)
                """, (self.room_type.id, 'confirmed', line_ids))
                _logger.debug("Updated %d room lines", len(line_ids))

        # ─── 7) HANDLE BLOCKED_ROOM_ACTION ───────────────────────────────────
        if self.blocked_room_action in ('unassign_confirm', 'auto_assign'):
            bid_list = tuple(bookings.ids)
            _logger.debug("Applying blocked_room_action '%s' to %s", self.blocked_room_action, bid_list)

            # confirm bookings
            self.env.cr.execute("""
                UPDATE room_booking
                SET state = %s
                WHERE id IN %s
            """, ('confirmed', bid_list))
            self.env.cr.commit()

            # confirm lines
            if line_ids:
                self.env.cr.execute("""
                    UPDATE room_booking_line
                    SET state_ = %s
                    WHERE id = ANY(%s)
                """, ('confirmed', line_ids))

            # auto‑assign if requested
            if self.blocked_room_action == 'auto_assign':
                for b in bookings:
                    b.action_assign_all_rooms()

        return {'type': 'ir.actions.act_window_close'}

class EmailConfigurationSettings(models.Model):
    _inherit = 'res.company'

    cron_name = fields.Char(
        string="Action Name",
        # related='model_id.name',
        # readonly=True,
        help="The name of the action associated with the selected model."
    )

    model_id = fields.Many2one(
        'ir.model',
        string="Model",
        # required=True, #Issue here
        # ondelete='set null',  # This is the default behavior and safe to use
        help="Model on which the server action runs."
    )

    template_id = fields.Many2one(
        'mail.template', string='Confirmation Email Template',
        help="Select the email template for reminder communication."
    )

    pre_template_id = fields.Many2one(
        'mail.template', string='Pre-Arrival Email Template',
        help="Select the email template for pre-arrival communication."
    )

    pre_arrival_days_before = fields.Integer(
        string="Days Before Arrival", default=3,
        help="Number of days before check-in to send the pre-arrival email."
    )

    reminder_days_before = fields.Integer(
        string="Days Before Reminder", default=3,
        help="Number of days before check-in to send the pre-arrival email."
    )

    scheduler_user_id = fields.Many2one(
        'res.users', string="Scheduler User", required=True,
        help="User responsible for executing the scheduled action."
    )
    allowed_groups = fields.Many2many(
        'res.groups', string="Allowed Groups",
        help="Groups allowed to configure this action."
    )
    interval_number = fields.Integer(
        string="Execute Every",
        default=1,
        help="Number of units (minutes, hours, days, etc.) to wait before the next execution."
    )
    execution_frequency_unit = fields.Selection(
        [('minutes', 'Minutes'),
         ('hours', 'Hours'),
         ('days', 'Days'),
         ('weeks', 'Weeks'),
         ('months', 'Months')],
        string="Execution Frequency Unit", default='days',
        help="Unit of time for the execution frequency."
    )
    number_of_calls = fields.Integer(
        string="Number of Calls", default=-1,
        help="Number of times the scheduler should run. Use -1 for unlimited."
    )
    priority = fields.Integer(
        string="Priority", help='Can be 1 - 5', default=5)
    active = fields.Boolean(string="Active", default=True)

    enable_reminder = fields.Boolean(
        string="Enable Reminder",
        help="Enable or disable pre-arrival email reminders."
    )

    @api.onchange('enable_reminder')
    def _onchange_enable_reminder(self):
        scheduled_action = self.env.ref('hotel_management.cron_send_prearrival_emails_company',
                                        raise_if_not_found=False)
        if scheduled_action:
            # Update the active field based on enable_reminder
            scheduled_action.sudo().write({'active': self.enable_reminder})
        if not self.enable_reminder:
            self.pre_template_id = False
            self.pre_arrival_days_before = 0

    @api.model
    def write(self, values):
        if 'enable_reminder' in values:
            scheduled_action = self.env.ref('hotel_management.cron_send_prearrival_emails_company',
                                            raise_if_not_found=False)
            if scheduled_action:
                scheduled_action.sudo().write(
                    {'active': values['enable_reminder']})
        return super(EmailConfigurationSettings, self).write(values)


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model
    def search(self, domain, *args, **kwargs):
        # Append filtering conditions
        domain += [
            ('summary', '=', 'Room Availability Notification'),
            ('res_model', '=', 'room.booking'),
        ]
        _logger.debug("Search domain applied: %s", domain)
        return super(MailActivity, self).search(domain, *args, **kwargs)


class AccountMoveInherit(models.Model):
    _inherit = "account.move"

    hotel_booking_id = fields.Many2one(
        'room.booking',
        string='Booking Reference',
        readonly=True
    )

    group_booking_name = fields.Char(
        string='Group Booking Name',
        store=True,
        readonly=True
    )
    parent_booking_name = fields.Char(
        string='Parent Booking Name',
        store=True,
        readonly=True
    )
    room_numbers = fields.Char(
        string='Room Numbers',
        store=True,
        readonly=True
    )


class ConfirmBookingWizard(models.TransientModel):
    _name = "confirm.booking.wizard"
    _description = "Confirm Booking Wizard"

    message = fields.Char(
        string="Message",
        translate=True,                                  # ← important
        default=lambda self: _(
            "Room number will be released. Do you want to proceed?")
    )
    title   = fields.Char(string="Title", translate=True, default=lambda self: _("Confirm Booking"))

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        res['message'] = _("Room number will be released. Do you want to proceed?")
        res['title'] = _("Confirm Booking")
        return res


    line_id = fields.Many2one(
        'room.booking.line', string="Room Line", readonly=True)
    booking_id = fields.Many2one(
        'room.booking', string="Booking", readonly=True)
    

    def action_confirm(self):
        """YES button: if the line is in 'block' state,
           set room_id to False and change state to 'confirmed'."""
        if self.line_id and self.line_id.state_ == 'block':
            self.line_id.room_id = False
            self.line_id.state_ = 'confirmed'
        
        if self.booking_id and self.booking_id.state == 'block':
            self.booking_id.state = 'confirmed'
            # Also clear room_id for all related room lines
            for line in self.booking_id.room_line_ids:
                line.room_id = False
                line.state_ = 'confirmed'
                
        return {'type': 'ir.actions.act_window_close'}

    def action_block(self):
        # self.line_id.state_ = 'block'
        # self.booking_id.state = 'block'
        return {'type': 'ir.actions.act_window_close'}


class RoomCountConfirmWizard(models.TransientModel):
    _name = "room.count.confirm.wizard"
    _description = "Ask if we should run Search Rooms"

    # Just a read-only label
    message = fields.Html(
        default=lambda self: _(
            "<h3>Room count changed.</h3>"
            "<p>Do you want to search rooms now?</p>"
        ),
        readonly=True,
    )

    # YES  → call the normal button on the booking
    def action_yes(self):
        booking = self.env["room.booking"].browse(self.env.context.get("active_id"))
        booking.action_search_rooms()
        return {"type": "ir.actions.act_window_close"}

    # NO  → simply close the pop-up
    def action_no(self):
        return {"type": "ir.actions.act_window_close"}


class RoomAssignmentWizard(models.TransientModel):
    _name = 'room.assignment.wizard'
    _description = 'Auto Room Assignment Wizard'

    
    building_id = fields.Many2one(
        'fsm.location',
        string="Building",
        required=True,
        domain="[('dynamic_selection_id.name', '=', 'Building')]"
    )
    floor_from = fields.Many2one(
        'fsm.location',
        string="From Floor",
        required=True,
        domain="[('dynamic_selection_id.name', '=', 'Floor'), ('fsm_parent_id', '=', building_id)]")

    floor_to = fields.Many2one(
        'fsm.location',
        string="To Floor",
        required=True,
        domain="[('dynamic_selection_id.name', '=', 'Floor'), ('fsm_parent_id', '=', building_id)]")


    # min_floor = fields.Integer(string="Min Floor", readonly=True)
    # max_floor = fields.Integer(string="Max Floor", readonly=True)
    booking_id = fields.Many2one('room.booking', string="Booking", readonly=True)
    room_type_id = fields.Many2one(
        related="booking_id.hotel_room_type",
        string="Room Type",
        store=False,
        readonly=True
    )
    

    def action_auto_room(self):
        for wizard in self:
            # ✅ Validation using Many2one
            # if wizard.floor_from.id > wizard.floor_to.id:
            #     raise ValidationError(_("'To Floor' cannot be smaller than 'From Floor'."))

            floor_locs = self.env['fsm.location'].search([
                ('dynamic_selection_id.name', '=', 'Floor')
            ])
            valid_floor_ids = []

            for loc in floor_locs:
                location = loc
                while location:
                    if location.id >= wizard.floor_from.id and location.id <= wizard.floor_to.id:
                        valid_floor_ids.append(loc.id)
                        break
                    location = location.fsm_parent_id

            booking = wizard.booking_id
            print(f"BOOKING; {booking}")
            room_type = booking.hotel_room_type

            # ✅ get all booked rooms for this booking but only of the same room_type
            booked_rooms = self.env['room.booking.line'].search([
                ('booking_id.state', 'in', ['confirmed', 'block', 'check_in']),
                ('room_id', '!=', False),
                ('room_id.room_type_name', '=', wizard.room_type_id.id),
                ('booking_id.checkin_date', '<', booking.checkout_date),
                ('booking_id.checkout_date', '>', booking.checkin_date),
                ('booking_id', '!=', booking.id),
            ]).mapped("room_id")
            
            # booked_rooms = self.env['room.booking.line'].search([
            #     ('booking_id.state', 'in', ['confirmed', 'block', 'check_in']),
            #     ('room_id', '!=', False),
            #     ('room_id.room_type_name', '=', self.room_type_id.id),  # ✅ same type only
            #     ('booking_id.checkin_date', '<', self.booking_id.checkout_date),
            #     ('booking_id.checkout_date', '>', self.booking_id.checkin_date),
            #     ('booking_id', '!=', self.booking_id.id),  # ✅ exclude current booking
            # ]).mapped("room_id")

            print("Booked Rooms (same type, same date range):", booked_rooms.mapped("name"))

            # ✅ Step 2: Find all rooms with those floor locations
            rooms = self.env['hotel.room'].search([
                ('fsm_location', 'in', valid_floor_ids),
                ('room_type_name', '=', wizard.room_type_id.id),
                ('active', '=', True),
                ('id', 'not in', booked_rooms.ids),
            ])
            available_count = len(rooms)
            print('11012', available_count)
            print(f"Room COunt: {self.booking_id.room_count}")

            if booking.room_count > available_count:
                raise ValidationError(
                    _(f"Only {available_count} rooms are available for the selected floor(s) "
                    f"and room type, but you requested {booking.room_count}.")
                )

            # if self.booking_id.room_count > available_count:
            #     raise ValidationError(
            #         _(f"Only {available_count} rooms are available for the selected floor(s) "
            #         f"and room type, but you requested {self.booking_id.room_count}.")
            # )

            print("Booked rooms:", booked_rooms.mapped("name"))
            print("Available rooms:", rooms.mapped("name"))

            booking.action_assign_all_rooms(available_rooms=rooms)

    
        