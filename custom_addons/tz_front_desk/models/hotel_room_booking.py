# -*- coding: utf-8 -*-
import logging
from datetime import timedelta, datetime, date
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
from odoo.models import NewId

_logger = logging.getLogger(__name__)


class TzHotelRoomBooking(models.Model):
    """Model that handles the hotel room booking and all operations related
        to booking"""
    _name = 'tz.frontdesk.booking'
    _order = 'create_date desc'
    _description = 'Hotel Room Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Booking ID", readonly=True, index=True,
                       default="New", help="Name or Reference of Booking", tracking=True)

    company_id = fields.Many2one('res.company', string="Hotel",
                                 index=True,
                                 default=lambda self: self.env.company,
                                 readonly=True)
    # Guest Details
    date_order = fields.Datetime(string='Order Date', required=True, default=lambda self: self.env.company.system_date)
    guest_id = fields.Many2one('res.partner', string="Guest", required=True, tracking=True)
    nationality = fields.Many2one('res.country', string='Nationality', related='guest_id.country_id', required=True,
                                  tracking=True, store=True)

    rate_code = fields.Many2one('rate.code', string='Rate Code',
                                domain=lambda self: [
                                    ('company_id', '=', self.env.company.id),
                                    ('obsolete', '=', False)
                                ], tracking=True)

    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern",
                                   domain=lambda self: [('company_id', '=', self.env.company.id)], tracking=True)

    # Room Details
    checkin_date = fields.Datetime(
        string="Check In Date",
        default=lambda self: self.env.user.company_id.system_date.replace(hour=0, minute=0, second=0, microsecond=0),
        help="Date of Check-in",
        required=True
    )

    checkout_date = fields.Datetime(
        string="Check Out Date",
        help="Date of Checkout",
        required=True
    )
    room_count = fields.Integer(string='Rooms', tracking=True)
    adult_count = fields.Integer(string='Adults', tracking=True)
    child_count = fields.Integer(string='Children', default=0, tracking=True)
    infant_count = fields.Integer(string='Infant', default=0, tracking=True)
    no_of_nights = fields.Integer(
        string="Number of Nights",
        compute="_compute_no_of_nights",
        store=True,
        help="Computed field to calculate the number of nights based on check-in and check-out dates.",
        tracking=True
    )

    hotel_room_type = fields.Many2one('room.type', string="Room Type")

    ref_id_bk = fields.Char(string="Ref. ID(booking.com)", tracking=True)

    adult_ids = fields.One2many(
        'reservation.adult', 'fd_booking_id', string="Adults")

    child_ids = fields.One2many(
        'reservation.child', 'fd_booking_id', string='Children')

    infant_ids = fields.One2many(
        'reservation.infant', 'fd_booking_id', string='Infant')

    availability_results = fields.One2many(
        'room.availability.result', 'fd_booking_id', string="Availability Results", readonly=True
    )

    room_line_ids = fields.One2many("room.booking.line",
                                    "fd_booking_id", string="Room",
                                    help="Hotel room reservation detail.")

    parent_booking_id = fields.Many2one(
        'tz.frontdesk.booking',
        string="Parent Booking",
        tracking=True
    )

    state = fields.Selection(selection=[
        ('confirmed', 'Confirmed'),
        ('block', 'Block'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('cancel', 'Cancelled'),
    ], string='State', help="State of the Booking", default='confirmed', tracking=True)

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
            # print('3245', grouped_availabilities)

        total_available_rooms = 0
        for room_type_id, availability in grouped_availabilities.items():
            # room_type_id = availability['room_type'][0] if isinstance(availability['room_type'], tuple) else \
            #     availability['room_type']
            # print('2666', room_type_id, availability['pax'], checkout_date, checkin_date)
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
                # ('fd_state', 'in', ['confirmed', 'block', 'check_in']),
                # ('id', 'not in', self.env.context.get('already_allocated', []))  # Exclude allocated lines
            ])
            # print("line 2676",booked_rooms)

            if availability['overbooking_allowed']:
                available_rooms = max(
                    availability['total_room_count'] - booked_rooms + availability['overbooking_rooms'], 0
                )
                if availability['overbooking_rooms'] == 0:
                    return 99999  # Unlimited rooms
            else:
                # print("2693",availability['total_room_count'], booked_rooms,max(availability['total_room_count'] - booked_rooms, 0))
                available_rooms = max(availability['total_room_count'] - booked_rooms, 0)

            total_available_rooms += available_rooms
            # print('line 2697',total_available_rooms)

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
                # print("line 2582", remaining_rooms, available_rooms)
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
                # print('3174', results)

                remaining_rooms -= current_rooms_reserved
                # print('3172', remaining_rooms)
                if remaining_rooms <= 0:
                    break

            if remaining_rooms <= 0:
                break

        return results

    @api.model
    def create(self, vals):
        # self.check_room_meal_validation(vals, False)
        if 'company_id' in vals:
            company = self.env['res.company'].browse(vals['company_id'])
            if 'checkin_date' not in vals:
                vals['checkin_date'] = company.system_date

        if 'room_count' in vals and vals['room_count'] <= 0:
            raise ValidationError(
                "Room count cannot be zero or less. Please select at least one room.")

        if 'adult_count' in vals and vals['adult_count'] <= 0:
            raise ValidationError(
                "Adult count cannot be zero or less. Please select at least one adult.")

        if 'child_count' in vals and vals['child_count'] < 0:
            raise ValidationError("Child count cannot be less than zero.")

        if 'infant_count' in vals and vals['infant_count'] < 0:
            raise ValidationError("Infant count cannot be less than zero.")

        if not vals.get('checkin_date'):
            raise ValidationError(
                _("Check-In Date is required and cannot be empty."))
        # Fetch the company_id from vals or default to the current user's company
        company_id = vals.get('company_id', self.env.company.id)
        company = self.env['res.company'].browse(company_id)
        current_company_name = company.name

        if vals.get('name', 'New') == 'New':
            if vals.get('parent_booking_id'):
                # Handle child booking
                parent = self.browse(vals['parent_booking_id'])
                parent_company_id = parent.company_id.id
                # Ensure child booking inherits parent's company
                vals['company_id'] = parent_company_id

                sequence = self.env['ir.sequence'].search(
                    [('code', '=', 'tz.frontdesk.booking'),
                     ('company_id', '=', parent_company_id)],
                    limit=1
                )
                if not sequence:
                    raise ValueError(
                        f"No sequence configured for company: {parent.company_id.name}")

                next_sequence = sequence.next_by_id()

                vals['name'] = f"{parent.company_id.name}/{next_sequence}"
                vals['parent_booking_name'] = parent.name
            else:
                sequence = self.env['ir.sequence'].search(
                    [('code', '=', 'room.booking'),
                     ('company_id', '=', company_id)],
                    limit=1
                )
                if not sequence:
                    raise ValueError(
                        f"No sequence configured for company: {current_company_name}")

                next_sequence = sequence.next_by_id()
                vals['name'] = f"{current_company_name}/{next_sequence}"

        return super(TzHotelRoomBooking, self).create(vals)

    def check_room_meal_validation(self, vals, is_write):
        _logger.info(f"VALIDATION STARTED: {vals}, IS_WRITE: {is_write}")

        for record in self:
            if vals.get('use_price', record.use_price):
                _logger.info(
                    f"USE ROOM PRICE {vals.get('use_price', record.use_price)}")

                if vals.get('room_price', record.room_price) < 0:
                    raise UserError("Room Price cannot be less than 0.")

                # if vals.get('child_count', record.child_count) > 0:
                #     if vals.get('room_child_price', record.room_child_price) < 1:
                #         raise UserError(
                #             "Room Child Price cannot be less than 1.")

                # if vals.get('infant_count', record.infant_count) > 0:
                #     if vals.get('room_infant_price', record.room_infant_price) < 1:
                #         raise UserError(
                #             "Room Infant Price cannot be less than 1.")

                # _logger.info(f"TEST {vals.get('room_discount', record.room_discount) * 100}")
                if vals.get('room_is_percentage', record.room_is_percentage):
                    if vals.get('room_discount', record.room_discount) * 100 < 1:
                        raise UserError("Room Discount cannot be less than 1.")
                else:
                    if vals.get('room_discount', record.room_discount) < 0:
                        raise UserError("Room Discount cannot be less than 0.")

            # Meal Price validation

            if vals.get('use_meal_price', record.use_meal_price):
                if vals.get('meal_price', record.meal_price) < 0:
                    raise UserError("Meal Price cannot be less than 0.")

                if vals.get('child_count', record.child_count) > 0:
                    if vals.get('meal_child_price', record.meal_child_price) < 0:
                        raise UserError(
                            "Meal Child Price cannot be less than 0.")

                # if vals.get('infant_count', record.infant_count) > 0:
                #     if vals.get('meal_infant_price', record.meal_infant_price) < 1:
                #         raise UserError(
                #             "Meal Infant Price cannot be less than 1.")

                if vals.get('meal_is_percentage', record.meal_is_percentage):
                    if vals.get('meal_discount', record.meal_discount) * 100 < 1:
                        raise UserError("Meal Discount cannot be less than 1.")
                else:
                    if vals.get('meal_discount', record.meal_discount) < 0:
                        raise UserError("Meal Discount cannot be less than 0.")

        _logger.info("VALIDATION COMPLETED")

    def action_split_rooms(self):
        for booking in self:
            availability_results = self.env['room.availability.result'].search(
                [('fd_booking_id', '=', booking.id)]
            )

            room_line_vals = []
            counter = 1
            adult_inserts = []
            child_inserts = []
            infant_inserts = []
            max_counter = max(booking.room_line_ids.mapped('counter') or [0])
            counter = max_counter + 1

            partner_name = booking.guest_id.name or ""
            name_parts = partner_name.split()
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[-1] if len(name_parts) > 1 else ""

            for result in availability_results:
                if result.split_flag:
                    continue

                room_type_id = result.room_type.id if result.room_type else None  # Ensure None instead of False

                rooms_reserved_count = int(result.rooms_reserved) if isinstance(
                    result.rooms_reserved, str) else result.rooms_reserved

                for _ in range(rooms_reserved_count):
                    new_booking_line = {
                        'room_id': False,
                        'checkin_date': booking.checkin_date,
                        'checkout_date': booking.checkout_date,
                        'uom_qty': 1,
                        'adult_count': booking.adult_count,
                        'child_count': booking.child_count,
                        'infant_count': booking.infant_count,
                        'hotel_room_type': room_type_id,  # Safe to use now
                        'counter': counter,
                    }
                    counter += 1
                    room_line_vals.append((0, 0, new_booking_line))

                # Append new adult records
                for _ in range(rooms_reserved_count * booking.adult_count):
                    adult_inserts.append((
                        booking.id,
                        room_type_id,  # Ensure integer or NULL
                        first_name, last_name, '', '', '', '', '', '', '', '', '',  # Empty fields
                    ))

                # Append new child records
                for _ in range(rooms_reserved_count * booking.child_count):
                    child_inserts.append((
                        booking.id,
                        room_type_id,  # Ensure integer or NULL
                        '', '', '', '', '', '', '', '', '', '', '',  # Empty fields
                    ))

                # Append new infant records
                for _ in range(rooms_reserved_count * booking.infant_count):
                    infant_inserts.append((
                        booking.id,
                        room_type_id,  # Ensure integer or NULL
                        '', '', '', '', '', '', '', '', '', '', '',  # Empty fields
                    ))

                result.split_flag = True

            if adult_inserts:
                self._bulk_insert("""
                    INSERT INTO reservation_adult (
                        fd_booking_id, room_type_id, first_name, last_name, profile, nationality,
                        passport_number, id_number, visa_number, id_type, phone_number, relation, create_date
                    ) VALUES %s
                """, adult_inserts)

            if child_inserts:
                self._bulk_insert("""
                    INSERT INTO reservation_child (
                        fd_booking_id, room_type_id, first_name, last_name, profile, nationality,
                        passport_number, id_number, visa_number, id_type, phone_number, relation, create_date
                    ) VALUES %s
                """, child_inserts)

            if infant_inserts:
                self._bulk_insert("""
                    INSERT INTO reservation_infant (
                        fd_booking_id, room_type_id, first_name, last_name, profile, nationality,
                        passport_number, id_number, visa_number, id_type, phone_number, relation, create_date
                    ) VALUES %s
                """, infant_inserts)

            if room_line_vals:
                booking.write({'room_line_ids': room_line_vals})

            self._update_adults_with_assigned_rooms_split_rooms(booking, max_counter)

    def _bulk_insert(self, query, values):
        from psycopg2.extras import execute_values
        cleaned_values = []

        for value in values:
            cleaned_value = tuple(None if v in ['', False] else v for v in value)  # Convert '' or False to NULL
            cleaned_values.append(cleaned_value)

        if cleaned_values:
            execute_values(self.env.cr, query, cleaned_values, template=None, page_size=100)
            self.env.cr.commit()

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


class RoomAvailabilityResultInherit(models.Model):
    _inherit = 'room.availability.result'

    fd_booking_id = fields.Many2one(
        "tz.frontdesk.booking",
        string="Booking",
        ondelete="cascade",
        tracking=True
    )


class RoomBookingLineInherit(models.Model):
    _inherit = 'room.booking.line'

    fd_booking_id = fields.Many2one(
        "tz.frontdesk.booking",
        string="Booking",
        ondelete="cascade",
        tracking=True
    )

    # fd_state = fields.Selection(related='fd_booking_id.state',
    #                          string="Order Status",
    #                          copy=False, tracking=True)

    fd_state = fields.Selection(selection=[
        ('confirmed', 'Confirmed'),
        ('block', 'Block'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
    ], string='State', help="State of the Booking", default='confirmed', tracking=True)

    @api.onchange('room_id')
    def _onchange_room_id(self):
        """Extended onchange method that works with both booking systems"""
        super(RoomBookingLineInherit, self)._onchange_room_id()
        if self.fd_booking_id:
            # Check for duplicate rooms in current booking
            existing_room_ids = self.fd_booking_id.room_line_ids.filtered(
                lambda line: line.id != self.id
            ).mapped('room_id.id')

            if self.room_id.id in existing_room_ids:
                raise ValidationError(
                    "This room is already assigned to the current booking. "
                    "Please select a different room."
                )

            # Check for conflicting bookings
            if self.id and self.room_id:
                # Handle both NewId and regular IDs
                current_id = self.id
                if isinstance(current_id, NewId):
                    current_id = int(str(current_id).split('_')[-1])

                # Get dates from parent booking
                checkin_date = self.fd_booking_id.checkin_date
                checkout_date = self.fd_booking_id.checkout_date

                # Convert string dates if needed
                if isinstance(checkin_date, str):
                    checkin_date = datetime.strptime(checkin_date, "%Y-%m-%d %H:%M:%S")
                if isinstance(checkout_date, str):
                    checkout_date = datetime.strptime(checkout_date, "%Y-%m-%d %H:%M:%S")

                # Search for conflicts across both booking systems
                conflicts = self.env['room.booking.line'].search([
                    ('room_id', '=', self.room_id.id),
                    ('id', '!=', current_id),
                    '|',
                    ('fd_booking_id.state', 'in', ['block', 'check_in']),
                    '|', '|',
                    '&', ('checkin_date', '<', checkout_date),
                    ('checkout_date', '>', checkin_date),
                    '&', ('checkin_date', '<=', checkin_date),
                    ('checkout_date', '>=', checkout_date),
                    '&', ('checkin_date', '>=', checkin_date),
                    ('checkout_date', '<=', checkout_date)
                ])

                if conflicts:
                    raise ValidationError(
                        "This room is already assigned to another booking. "
                        "Please select a different room."
                    )

            # Update booking state
            if not self.room_id:
                # raise ValidationError('if not self.room_id:')
                self.fd_booking_id.state = 'block'
            else:
                # raise ValidationError('else:')
                # Handle child bookings for frontdesk system
                parent_booking_id = self.fd_booking_id.id
                child_bookings = self.env['tz.frontdesk.booking'].search([
                    ('parent_booking_id', '=', parent_booking_id)
                ])

                # Find matching lines in child bookings
                matching_lines = self.env['room.booking.line'].search([
                    ('fd_booking_id', 'in', child_bookings.ids),
                    ('counter', '=', self.counter)
                ])

                # Update all matching lines
                if matching_lines:
                    matching_lines.write({
                        'room_id': self.room_id.id,
                        'sequence': self.sequence
                    })

                # Update child booking states
                for booking in child_bookings:
                    if not self.room_id.id:
                        booking.state = 'block'

    def write(self, vals):
        # Separate records by booking type
        fd_records = self.filtered(lambda r: r.fd_booking_id)
        regular_records = self - fd_records

        # Process regular records first (original functionality)
        if regular_records:
            super(RoomBookingLineInherit, regular_records).write(vals)

        # Process frontdesk records with custom logic
        if fd_records:
            # Initialize tracking variables
            record_to_delete = []
            records_to_update = []
            parent_bookings_to_update = []
            processed_parent_bookings = set()

            for record in fd_records:
                parent_booking = record.fd_booking_id
                counter = record.counter

                # Handle room_id changes
                if 'room_id' in vals:
                    room_id = vals['room_id']

                    # Update the current record
                    super(RoomBookingLineInherit, record).write({
                        'room_id': room_id,
                        'fd_state': 'block'
                    })

                    # Update child bookings in tz.frontdesk.booking
                    child_bookings = self.env['tz.frontdesk.booking'].search([
                        ('parent_booking_id', '=', parent_booking.id)
                    ])

                    for child in child_bookings:
                        # Find or create matching line in child booking
                        child_line = self.search([
                            ('fd_booking_id', '=', child.id),
                            ('counter', '=', counter)
                        ], limit=1)

                        if not child_line:
                            child.write({
                                'room_line_ids': [(0, 0, {
                                    'room_id': room_id,
                                    'checkin_date': parent_booking.checkin_date,
                                    'checkout_date': parent_booking.checkout_date,
                                    'uom_qty': 1,
                                    'adult_count': record.adult_count,
                                    'child_count': record.child_count,
                                    'infant_count': record.infant_count,
                                    'hotel_room_type': record.hotel_room_type.id,
                                    'counter': counter,
                                    'fd_booking_id': child.id
                                })]
                            })
                        else:
                            child_line.write({'room_id': room_id})

                    # Update guest records
                    self._update_guest_records(
                        booking_id=parent_booking.id,
                        counter=counter,
                        room_id=room_id,
                        use_fd_booking=True
                    )

                # Handle hotel_room_type changes
                if 'hotel_room_type' in vals:
                    room_type = vals['hotel_room_type']
                    super(RoomBookingLineInherit, record).write({
                        'hotel_room_type': room_type,
                        'related_hotel_room_type': room_type,
                        'room_id': False
                    })

                # Handle counter updates
                if 'counter' in vals:
                    new_counter = vals['counter']

                    # Update matching lines in child bookings
                    for child in child_bookings:
                        child_lines = self.search([
                            ('fd_booking_id', '=', child.id),
                            ('counter', '=', counter)
                        ])
                        if child_lines:
                            child_lines.write({'counter': new_counter})

                    # Update guest records with new counter
                    if 'room_id' in vals:
                        self._update_guest_records(
                            booking_id=parent_booking.id,
                            counter=new_counter,
                            room_id=vals['room_id'],
                            use_fd_booking=True
                        )

                # Handle unassigned rooms
                if not vals.get('room_id') and 'room_id' in vals:
                    parent_bookings_to_update.append((parent_booking, {
                        'fd_state': 'confirmed'
                    }))

            # Process pending updates
            for booking, booking_vals in parent_bookings_to_update:
                booking.write(booking_vals)

        return True

    def _update_guest_records(self, booking_id, counter, room_id, use_fd_booking=False):
        """
        Update guest records (adults, children, infants) when room assignments change

        Args:
            booking_id: ID of the parent booking
            counter: The counter value to match guest records
            room_id: The room ID to assign to guests
            use_fd_booking: Boolean indicating if using fd_booking_id (True) or booking_id (False)
        """
        # Base domain for all guest types
        domain = [('room_sequence', '=', counter)]

        # Add booking reference based on system used
        if use_fd_booking:
            domain.append(('fd_booking_id', '=', booking_id))

        # Update adults
        adults = self.env['reservation.adult'].search(domain)
        if adults:
            adults.write({'room_id': room_id})

        # Update children
        children = self.env['reservation.child'].search(domain)
        if children:
            children.write({'room_id': room_id})

        # Update infants
        infants = self.env['reservation.infant'].search(domain)
        if infants:
            infants.write({'room_id': room_id})


class ReservationAdultInherit(models.Model):
    _inherit = 'reservation.adult'

    fd_booking_id = fields.Many2one(
        "tz.frontdesk.booking",
        string="Booking",
        ondelete="cascade",
        tracking=True
    )


class ReservationChildInherit(models.Model):
    _inherit = 'reservation.child'

    fd_booking_id = fields.Many2one(
        "tz.frontdesk.booking",
        string="Booking",
        ondelete="cascade",
        tracking=True
    )


class ReservationInfantInherit(models.Model):
    _inherit = 'reservation.infant'

    fd_booking_id = fields.Many2one(
        "tz.frontdesk.booking",
        string="Booking",
        ondelete="cascade",
        tracking=True
    )
