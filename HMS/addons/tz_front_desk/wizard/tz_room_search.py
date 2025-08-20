# -*- coding: utf-8 -*-
from odoo import models, fields, api
from datetime import timedelta, datetime, date
from odoo.exceptions import ValidationError


class TzRoomSearch(models.TransientModel):
    _name = 'tz.room.search'
    _description = 'Transient model for searching hotel rooms'
    _rec_name = 'checkin_date'

    guest_id = fields.Many2one('res.partner', string="Guest", required=True)
    nationality = fields.Many2one('res.country', string='Nationality', related='guest_id.country_id', required=True)

    checkin_date = fields.Datetime(
        string="Check In Date",
        default=lambda self: self.env.company.system_date.replace(hour=0, minute=0, second=0, microsecond=0),
        help="Date of Check-in",
        required=True
    )

    checkout_date = fields.Datetime(
        string="Check Out Date",
        help="Date of Checkout",
        required=True
    )

    room_count = fields.Integer(string='Rooms', default=1, required=True)
    adult_count = fields.Integer(string='Adults', default=1, required=True)
    child_count = fields.Integer(string='Children', default=0)
    infant_count = fields.Integer(string='Infant', default=0)

    no_of_nights = fields.Integer(
        string="Number of Nights",
        required=True,
        default=1
    )

    hotel_room_type = fields.Many2one('room.type', string="Room Type")
    availability_results = fields.Many2many('tz.room.availability', compute="action_search_rooms",
                                            string='Available Rooms')

    @api.onchange('checkin_date')
    def _onchange_checkin_date(self):
        """ Updates checkout_date only if no_of_nights is greater than 1 """
        for record in self:
            if record.checkin_date and record.no_of_nights > 1:
                record.checkout_date = record.checkin_date + timedelta(days=record.no_of_nights)

    @api.onchange('no_of_nights')
    def _onchange_no_of_nights(self):
        """ Updates checkout_date when no_of_nights is changed """
        for record in self:
            if record.checkin_date and record.no_of_nights > 0:
                record.checkout_date = record.checkin_date + timedelta(days=record.no_of_nights)

    @api.onchange('checkout_date')
    def _onchange_checkout_date(self):
        """ Updates no_of_nights when checkout_date is manually selected """
        for record in self:
            if record.checkin_date and record.checkout_date:
                delta = (record.checkout_date - record.checkin_date).days
                record.no_of_nights = max(delta, 1)  # Ensure at least 1 night

    @api.depends('room_count', 'adult_count', 'hotel_room_type', 'checkin_date', 'checkout_date')
    def action_search_rooms(self):
        """ Searches rooms but prevents overwriting user-selected checkout_date """
        for record in self:
            # Store the original checkout_date before executing function
            original_checkout = record.checkout_date

            # Perform room search logic
            record.availability_results = [(5, 0, 0)]
            if record.room_count <= 0 or record.adult_count <= 0:
                raise ValidationError(
                    "Room count and adult count cannot be zero or less. Please select at least one room and one adult.")

            result = record.check_room_availability_all_hotels_split_across_type(
                record.checkin_date, record.checkout_date, record.room_count, record.adult_count,
                record.hotel_room_type.id if record.hotel_room_type else None
            )

            if isinstance(result, tuple) and len(result) == 2:
                total_available_rooms, results = result
            else:
                raise ValueError("Expected a tuple with 2 elements, but got:", result)

            if isinstance(results, list) and len(results) == 1 and isinstance(results[0], dict) and results[0].get(
                    'type') == 'ir.actions.act_window':
                return results[0]

            if not isinstance(results, list):
                raise ValueError("Expected a list of dictionaries, but got:", results)

            result_lines = []
            for res in results:
                if not isinstance(res, dict):
                    raise ValueError(f"Expected a dictionary, but got: {res}")

                availability_record = self.env['tz.room.availability'].create({
                    'company_id': res['company_id'],
                    'room_type': res['room_type'],
                    'rooms_reserved': res['rooms_reserved'],
                    'available_rooms': res['available_rooms'],
                })

                record.availability_results = [(4, availability_record.id)]

            # Restore the original checkout_date if it was changed inside other functions
            if original_checkout and record.checkout_date != original_checkout:
                record.checkout_date = original_checkout

    @api.model
    def check_room_availability_all_hotels_split_across_type(
            self, checkin_date, checkout_date, room_count, adult_count, hotel_room_type_id=None):
        """ Checks room availability while preserving original checkout_date """
        checkin_date = self._convert_to_date(checkin_date)
        checkout_date = self._convert_to_date(checkout_date)

        original_checkout = checkout_date  # Save the original checkout_date

        total_available_rooms = 0
        companies = self.env['hotel.inventory'].read_group([], ['company_id'], ['company_id'])
        room_types_dict = {room_type['id']: room_type for room_type in
                           self.env['room.type'].search_read([], [], order='user_sort ASC')}

        for company in companies:
            loop_company_id = company['company_id'][0]
            total_available_rooms += self._calculate_available_rooms(
                loop_company_id, checkin_date, checkout_date, adult_count, hotel_room_type_id, room_types_dict
            )

            if total_available_rooms == 99999:
                break

        results = self._allocate_rooms(companies, room_count, checkin_date, checkout_date, adult_count,
                                       hotel_room_type_id, room_types_dict)

        return total_available_rooms, results

    def _convert_to_date(self, date_value):
        """Helper to convert date strings or datetime objects to date."""
        if isinstance(date_value, (datetime, date)):
            return date_value.date() if isinstance(date_value, datetime) else date_value
        elif isinstance(date_value, str):
            return datetime.strptime(date_value, "%Y-%m-%d").date()
        return date_value

    def _calculate_available_rooms(self, company_id, checkin_date, checkout_date, adult_count, hotel_room_type_id,
                                   room_types_dict):
        """Calculate available rooms for a company."""
        room_availabilities_domain = [
            ('company_id', '=', company_id),
            ('pax', '>=', adult_count),
        ]

        if hotel_room_type_id:
            room_availabilities_domain.append(('room_type', '=', hotel_room_type_id))

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
                    'overbooking_rooms': availability['overbooking_rooms'],
                    'entries': []
                }
            grouped_availabilities[room_type_id]['total_room_count'] += availability['total_room_count']
            grouped_availabilities[room_type_id]['entries'].append(availability)

        total_available_rooms = 0
        for room_type_id, availability in grouped_availabilities.items():
            # room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
            #     availability['room_type']
            # Exclude already allocated bookings from search
            booked_rooms = self.env['room.booking.line'].search_count([
                ('hotel_room_type', '=', room_type_id),
                ('fd_booking_id.room_count', '=', 1),  # Include only bookings with room_count = 1
                # ('adult_count', '=', availability['pax']),
                ('checkin_date', '<=', checkout_date),  # Check-in date filter
                ('checkout_date', '>=', checkin_date),  # Check-out date filter
                ('fd_booking_id.state', 'in', ['confirmed', 'block', 'check_in']),  # Booking state filter
                ('id', 'not in', self.env.context.get('already_allocated', []))
                # ('hotel_room_type', '=', room_type_id),
                # ('adult_count', '=', availability['pax']),
                # ('checkin_date', '<', checkout_date),
                # ('checkout_date', '>', checkin_date),
                # ('state', 'in', ['confirmed', 'block', 'check_in']),
                # ('id', 'not in', self.env.context.get('already_allocated', []))  # Exclude allocated lines
            ])

            if availability['overbooking_allowed']:
                available_rooms = max(
                    availability['total_room_count'] - booked_rooms + availability['overbooking_rooms'], 0
                )
                if availability['overbooking_rooms'] == 0:
                    return 99999  # Unlimited rooms
            else:
                available_rooms = max(availability['total_room_count'] - booked_rooms, 0)

            total_available_rooms += available_rooms

        return total_available_rooms

    def _allocate_rooms(self, companies, room_count, checkin_date, checkout_date, adult_count, hotel_room_type_id,
                        room_types_dict):
        """Allocate rooms based on availability."""
        results = []
        remaining_rooms = room_count

        for company in companies:
            loop_company_id = company['company_id'][0]
            room_availabilities_domain = [
                ('company_id', '=', loop_company_id),
                ('pax', '>=', adult_count),
            ]

            if hotel_room_type_id:
                room_availabilities_domain.append(('room_type', '=', hotel_room_type_id))

            # room_availabilities = self.env['hotel.inventory'].search_read(room_availabilities_domain,
            #     ['room_type', 'pax', 'total_room_count', 'overbooking_allowed', 'overbooking_rooms'],
            #     order='pax ASC'
            # )

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
                        'overbooking_rooms': availability['overbooking_rooms'],
                        'entries': []
                    }
                grouped_availabilities[room_type_id]['total_room_count'] += availability['total_room_count']
                grouped_availabilities[room_type_id]['entries'].append(availability)

            for room_type_id, availability in grouped_availabilities.items():
                # room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
                #     availability['room_type']

                # Exclude already allocated bookings from search
                booked_rooms = self.env['room.booking.line'].search_count([
                    ('hotel_room_type', '=', room_type_id),
                    ('fd_booking_id.room_count', '=', 1),
                    # ('adult_count', '=', availability['pax']),
                    ('checkin_date', '<=', checkout_date),
                    ('checkout_date', '>=', checkin_date),
                    ('fd_booking_id.state', 'in', ['confirmed', 'check_in', 'block']),
                    ('id', 'not in', self.env.context.get('already_allocated', []))  # Exclude allocated lines
                ])

                if availability['overbooking_allowed']:
                    available_rooms = max(
                        availability['total_room_count'] - booked_rooms + availability['overbooking_rooms'], 0)
                else:
                    available_rooms = max(availability['total_room_count'] - booked_rooms, 0)
                current_rooms_reserved = min(remaining_rooms, available_rooms)

                # Track allocated bookings in context
                if current_rooms_reserved > 0:
                    allocated_lines = self.env['room.booking.line'].search([
                        ('hotel_room_type', '=', room_type_id),
                        # ('fd_booking_id.room_count', '=', 1),
                        # ('adult_count', '=', availability['pax']),
                        ('checkin_date', '<=', checkout_date),
                        ('checkout_date', '>=', checkin_date),
                        ('fd_booking_id.state', 'in', ['confirmed', 'check_in', 'block']),
                    ], limit=current_rooms_reserved)

                    already_allocated_ids = self.env.context.get('already_allocated', [])
                    already_allocated_ids += allocated_lines.ids
                    self = self.with_context(already_allocated=already_allocated_ids)

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

    def action_open_room_booking(self):
        self.ensure_one()  # Ensure that the method is called for a single record

        # Step 1: Create a new booking record in `tz.frontdesk.booking`
        booking_vals = {
            'guest_id': self.guest_id.id,
            'nationality': self.nationality.id,
            'checkin_date': self.checkin_date,
            'checkout_date': self.checkout_date,
            'room_count': self.room_count,
            'adult_count': self.adult_count,
            'child_count': self.child_count,
            'infant_count': self.infant_count,
            'no_of_nights': self.no_of_nights,
            'hotel_room_type': self.hotel_room_type.id,
        }
        booking = self.env['tz.frontdesk.booking'].create(booking_vals)

        # Step 2: Fetch available room data and create `room.availability.result` records
        availability_results = []
        for availability in self.availability_results:
            result_vals = {
                'fd_booking_id': booking.id,
                'company_id': booking.company_id.id,
                'room_type': self.hotel_room_type.id,
                'pax': self.adult_count,
                'rooms_reserved': availability.rooms_reserved,
                'available_rooms': availability.available_rooms if availability.available_rooms.isdigit() else 0,
                'split_flag': False,  # Set based on any logic needed
            }
            availability_results.append((0, 0, result_vals))

        # Step 3: Update the booking with availability results
        if availability_results:
            booking.write({'availability_results': availability_results})
            booking.action_split_rooms()

        # Step 4: Return an action to open the created booking form
        return {
            'type': 'ir.actions.act_window',
            'name': 'Booking Details',
            'res_model': 'tz.frontdesk.booking',
            'res_id': booking.id,
            'view_mode': 'form',
            'view_id': self.env.ref('tz_front_desk.tz_view_room_booking_form').id,
            'target': 'current',
        }


class TzRoomAvailability(models.TransientModel):
    _name = 'tz.room.availability'
    _description = 'Room Availability Results'

    company_id = fields.Many2one('res.company', string='Hotel')
    room_type = fields.Many2one('room.type', string='Room Type')
    rooms_reserved = fields.Integer(string='Rooms Reserved')
    available_rooms = fields.Char(string='Available Rooms')  # String to handle "Unlimited" availability

    def action_open_room_booking(self):
        ctx = {
            'default_room_count': self.room_count,
            'default_adult_count': self.adult_count,
            'default_child_count': self.child_count,
            'default_checkin_date': self.checkin_date,
            'default_checkout_date': self.checkout_date,
            'default_hotel_room_type': self.hotel_room_type.id,
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tz.frontdesk.booking',
            'res_id': self.id,
            'view_mode': 'new',
            'view_id': self.env.ref('tz_front_desk.view_room_booking_form').id,
            'context': ctx,
        }
