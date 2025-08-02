from odoo import models, fields, api, _
import logging
from datetime import timedelta
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class RoomBooking(models.Model):
    _inherit = 'room.booking'

    partner_id = fields.Many2one('res.partner', string='Guest Name')

    room_list = fields.Many2one(
        'hotel.room',
        string="Select Room",
        domain="[('id', 'not in', unavailable_room_ids)]"
    )

    unavailable_room_ids = fields.Many2many(
        comodel_name='hotel.room',
        compute='_compute_unavailable_rooms',
        store=False,
    )

    @api.depends('room_id.state_', 'room_id.room_id')
    def _compute_unavailable_rooms(self):
        for booking in self:
            unavailable_rooms = self.env['room.booking.line'].search([
                ('current_company_id', '=', booking.company_id.id),
                ('state_', 'in', ['confirmed', 'block', 'check_in']),
            ]).mapped('room_id.id')
            booking.unavailable_room_ids = unavailable_rooms

    @api.model
    def default_get(self, fields_list):
        res = super(RoomBooking, self).default_get(fields_list)
        current_company = self.env.company
        unavailable_rooms = self.env['room.booking.line'].search([
            ('current_company_id', '=', current_company.id),
            ('state_', 'in', ['confirmed', 'block', 'check_in']),
        ]).mapped('room_id.id')
        res['unavailable_room_ids'] = [(6, 0, unavailable_rooms)]
        return res

    no_of_nights = fields.Integer(
        string='Number of Nights',
        compute='_compute_no_of_nights_custom',
        inverse='_inverse_no_of_nights_custom',
        store=True,
        default=1
    )

    room_count = fields.Integer(default=1)

    nationality = fields.Many2one('res.country', string='Nationality', related='partner_id.nationality', readonly=False,
                                  store=True)

    room_type_name = fields.Many2one('room.type', related='room_list.room_type_name', string='Room Type', store=True)
    suite = fields.Boolean(string="Suite", related='room_list.suite')
    no_smoking = fields.Boolean(string="No Smoking", related='room_list.no_smoking')
    extra_beds = fields.Integer(string="Extra Beds", tracking=True)
    companions = fields.Many2many('res.partner')

    price_pax = fields.Float(string="Price/Pax", compute="_compute_price", store=False)
    price_child = fields.Float(string="Price/Child", compute="_compute_price", store=False)

    def _default_checkout_date(self):
        company = self.company_id or self.env.company
        system_date = company.system_date.date()
        next_day = system_date + timedelta(days=1)
        # raise UserError(fields.Datetime.to_datetime(next_day))
        return fields.Datetime.to_datetime(next_day)

    checkout_date = fields.Datetime(
        string="Check Out",
        help="Date of Checkout",
        required=True,
        tracking=True,
        default=lambda self: self._default_checkout_date()
    )

    group_booking = fields.Many2one(
        'group.booking',
        string="Group Booking",
        index=True  # Important for performance
    )

    @api.depends('meal_pattern.meals_list_ids.meal_code.price_pax',
                 'meal_pattern.meals_list_ids.meal_code.price_child')
    def _compute_price(self):
        for booking in self:
            total_price_pax = 0.0
            total_price_child = 0.0

            # If a meal pattern is selected, sum the prices
            if booking.meal_pattern:
                for meal in booking.meal_pattern.meals_list_ids:
                    if meal.meal_code:
                        total_price_pax += meal.meal_code.price_pax
                        total_price_child += meal.meal_code.price_child

            booking.price_pax = total_price_pax
            booking.price_child = total_price_child

    @api.model
    def create(self, vals):
        if self.env.context.get('front_desk'):
            # raise UserError(self.env.company.system_date.date())
            vals['is_offline_search'] = False

            if not vals.get('partner_id'):
                raise ValidationError(_("Guest Name is required and cannot be empty."))

            if vals.get('room_list'):
                room = self.env['hotel.room'].browse(vals['room_list'])
                if room.room_type_name:
                    inventory = self.env['hotel.inventory'].search([
                        ('room_type', '=', room.room_type_name.id),
                        ('company_id', '=', self.env.company.id),
                        ('room_type.obsolete', '=', False),
                    ], limit=1)

                    if not inventory:
                        raise ValidationError('No room type')

                    vals['hotel_room_type'] = inventory.id

            # Now create the record first before using it
            booking = super().create(vals)

            # Proceed only if front_desk and room_list were used
            if vals.get('room_list') and booking.hotel_room_type:
                # Handle Rate Code
                if not vals.get('rate_code'):
                    if self.env.company.rate_code:
                        vals['rate_code'] = self.env.company.rate_code.id
                        booking.rate_code = self.env.company.rate_code.id
                    else:
                        raise UserError(
                            _("Rate Code is required. Please a Rate Code or configure a default Rate Code in Company Settings"))

                # Handle market segment
                if not vals.get('market_segment'):
                    if self.env.company.market_segment:
                        vals['market_segment'] = self.env.company.market_segment.id
                        booking.market_segment = self.env.company.market_segment.id
                    else:
                        raise UserError(
                            _("Market Segment is required. Please configure a default Market Segment in Company Settings."))

                # Handle source of business
                if not vals.get('source_of_business'):
                    if self.env.company.source_business:
                        vals['source_of_business'] = self.env.company.source_business.id
                        booking.source_of_business = self.env.company.source_business.id
                    else:
                        raise UserError(
                            _("Source of Business is required. Please configure a default Source of Business in Company Settings."))

                if not vals.get('partner_id'):
                    raise ValidationError(_("Guest Name is required and cannot be empty."))
                last_availability = self.env['room.availability.result'].search(
                    [('room_type', '=', booking.hotel_room_type.id)],
                    order='id desc',
                    limit=1
                )

                available_rooms = last_availability.available_rooms - 1 if last_availability else 0

                self.env['room.availability.result'].create({
                    'room_booking_id': booking.id,
                    'company_id': booking.company_id.id,
                    'room_type': booking.hotel_room_type.id,
                    'pax': booking.adult_count or 1,
                    'rooms_reserved': 1,
                    'available_rooms': available_rooms,
                    'split_flag': True
                })

                booking._get_or_create_master_folio(booking)
                booking.create_booking_lines()
                booking.state = "block"
                booking.action_checkin()

            return booking

        # Default creation if not front_desk context
        return super().create(vals)

    def write(self, vals):
        # Call super() first to perform the write operation
        res = super().write(vals)

        # Only update folio rooms if write was successful (res is True)
        if res and any(field in vals for field in ['room_line_ids', 'group_booking', 'state']):
            for booking in self:
                self._update_folio_room(booking)

        return res

    def create_booking_lines(self):
        for booking in self:
            if not booking.room_list:
                raise ValidationError("Room must be selected before creating a booking line.")

            line_vals = {
                'booking_id': booking.id,
                'room_id': booking.room_list.id,
                'hotel_room_type': booking.room_list.room_type_name.id,
                'checkin_date': booking.checkin_date,
                'checkout_date': booking.checkout_date,
                'adult_count': booking.adult_count,
                'state_': 'block',
                'counter': 1,
                'uom_qty': (booking.checkout_date - booking.checkin_date).days or 1,
                'is_unassigned': True,
            }

            self.env['room.booking.line'].create(line_vals)

    def delete_booking_lines(self):
        """Delete all booking lines linked to the current booking"""
        for booking in self:
            booking_lines = self.env['room.booking.line'].search([('booking_id', '=', booking.id)])
            booking_lines.unlink()
        return True

    def _update_folio_room(self, booking):
        """Update room_id in folio based on booking type"""
        folio = self.env['tz.master.folio'].sudo().search(
            domain=[
                ('company_id', '=', booking.company_id.id),
                ('booking_ids', 'in', booking.id),
                ('state', '=', 'draft'),
            ]
            , limit=1)
        if not booking.group_booking:
            # Individual booking - take first room
            if booking.room_line_ids:
                folio.sudo().write({'room_id': booking.room_line_ids[0].room_id.id})
        else:
            non_parent_booking = self.env['room.booking'].sudo().search([
                ('group_booking', '=', booking.group_booking.id),
                ('parent_booking_name', '=', False)
            ], limit=1)
            if non_parent_booking and non_parent_booking.room_line_ids:
                folio.sudo().write({'room_id': non_parent_booking.room_line_ids[0].room_id.id})

    def _get_or_create_master_folio(self, booking):
        """
        Create or get existing master folio for the booking
        Rules:
        - Group bookings: One folio per group (uses group_id as identifier)
        - Individual bookings: One folio per booking
        Returns: master folio record
        """
        master_folio = self.env['tz.master.folio']
        company = booking.company_id or self.env.company

        # Base domain
        domain = [
            ('company_id', '=', company.id),
            ('state', '=', 'draft'),
        ]

        # Group booking logic
        if booking.group_booking:
            domain.append(('group_id', '=', booking.group_booking.id))
            folio = master_folio.sudo().search(domain, limit=1)

            if not folio:
                # Create new group folio
                folio_name = f"{company.name or ''}/{self.env['ir.sequence'].sudo().with_company(company).next_by_code('tz.master.folio') or 'New'}"
                folio = master_folio.sudo().create({
                    'name': folio_name,
                    'group_id': booking.group_booking.id,
                    'guest_id': booking.partner_id.id,
                    'rooming_info': booking.group_booking.group_name,
                    'check_in': booking.checkin_date,
                    'check_out': booking.checkout_date,
                    'company_id': company.id,
                    'currency_id': company.currency_id.id,
                })

                # Set has_master_folio = True on the related group booking
                booking.group_booking.sudo().write({'has_master_folio': True})

            # Always link the current booking to the folio
            folio.write({'booking_ids': [(4, booking.id)]})
            return folio

        # Individual booking logic
        else:
            domain.append(('booking_ids', 'in', booking.id))
            folio = master_folio.sudo().search(domain, limit=1)

            if not folio:
                folio_name = f"{company.name or ''}/{self.env['ir.sequence'].sudo().with_company(company).next_by_code('tz.master.folio') or 'New'}"
                folio = master_folio.sudo().create({
                    'name': folio_name,
                    'guest_id': booking.partner_id.id,
                    'rooming_info': booking.name,
                    'check_in': booking.checkin_date,
                    'check_out': booking.checkout_date,
                    'company_id': company.id,
                    'currency_id': company.currency_id.id,
                    'booking_ids': [(4, booking.id)],
                })
            return folio

    def _notify_booking_confirmation(self, original_result=None):
        """Helper function to show booking confirmation notification"""
        if original_result and isinstance(original_result, dict) and original_result.get(
                'res_model') == 'booking.checkin.wizard':
            return original_result

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Master folio successfully created."),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def action_confirm(self):
        result = super(RoomBooking, self).action_confirm()
        checked_in_bookings = self.filtered(lambda b: b.state == 'confirmed')

        for booking in checked_in_bookings:
            self._get_or_create_master_folio(booking)
        # self.env['tz.manual.posting.type'].generate_manual_postings()
        return self._notify_booking_confirmation(result)

    def action_confirm_booking(self):
        result = super(RoomBooking, self).action_confirm_booking()
        checked_in_bookings = self.filtered(lambda b: b.state == 'confirmed')

        for booking in checked_in_bookings:
            self._get_or_create_master_folio(booking)
        # self.env['tz.manual.posting.type'].generate_manual_postings()
        return self._notify_booking_confirmation(result)

    @api.depends('checkin_date', 'checkout_date')
    def _compute_no_of_nights_custom(self):
        for rec in self:
            if rec.checkin_date and rec.checkout_date:
                in_date = fields.Date.to_date(rec.checkin_date)
                out_date = fields.Date.to_date(rec.checkout_date)
                diff_days = (out_date - in_date).days
                rec.no_of_nights = max(diff_days, 1)  # Enforce at least 1 night
            else:
                rec.no_of_nights = 1

    def _inverse_no_of_nights_custom(self):
        for rec in self:
            if rec.checkin_date:
                # Enforce minimum of 1 night
                nights = max(rec.no_of_nights, 1)
                rec.checkout_date = rec.checkin_date + timedelta(days=nights)

    def action_block(self):
        result = super(RoomBooking, self).action_block()
        # self.env['tz.manual.posting.type'].generate_manual_postings()
        return result

    def action_checkin(self):
        # Call the parent method first
        result = super(RoomBooking, self).action_checkin()

        # Refresh the SQL View and Sync data
        # self.env['tz.manual.posting.type'].generate_manual_postings()
        hotel_check_out = self.env['tz.hotel.checkout']
        hotel_check_out.generate_data()
        hotel_check_out.sync_from_view()

        return result

    def action_checkin_booking(self):
        # Call the parent method first
        result = super(RoomBooking, self).action_checkin_booking()
        # self.env['tz.manual.posting.type'].generate_manual_postings()
        # Refresh the SQL View and Sync data
        hotel_check_out = self.env['tz.hotel.checkout']
        hotel_check_out.generate_data()
        hotel_check_out.sync_from_view()

        return result







class RoomRateForecast(models.Model):
    _inherit = 'room.rate.forecast'

    state = fields.Selection(
        [('draft', 'Draft'),
         ('posted', 'Posted')],
        string='Status',
        default='draft',
        tracking=True
    )
