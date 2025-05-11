from odoo import models, fields, api, _
import logging

from odoo.exceptions import ValidationError

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
                ('state_', 'in', ['confirmed', 'block', 'check_in']),
            ]).mapped('room_id.id')
            booking.unavailable_room_ids = unavailable_rooms

    @api.model
    def default_get(self, fields_list):
        res = super(RoomBooking, self).default_get(fields_list)
        unavailable_rooms = self.env['room.booking.line'].search([
            ('state_', 'in', ['confirmed', 'block', 'check_in']),
        ]).mapped('room_id.id')
        res['unavailable_room_ids'] = [(6, 0, unavailable_rooms)]
        return res

    no_of_nights = fields.Integer(default=1)
    room_count = fields.Integer(default=1)

    nationality = fields.Many2one('res.country', string='Nationality', related='partner_id.nationality', readonly=False, store=True)

    room_type_name = fields.Many2one('room.type', related='room_list.room_type_name', string='Room Type', store=True)
    suite = fields.Boolean(string="Suite", related='room_list.suite')
    no_smoking = fields.Boolean(string="No Smoking", related='room_list.no_smoking')
    extra_beds = fields.Integer(string="Extra Beds", tracking=True)
    companions = fields.Many2many('res.partner')

    price_pax = fields.Float(string="Price/Pax", compute="_compute_price", store=False)
    price_child = fields.Float(string="Price/Child", compute="_compute_price", store=False)

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
            vals.setdefault('state', self.env.context.get('default_state', 'not_confirmed'))
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
                if not vals.get('market_segment') and self.env.company.market_segment:
                    vals['market_segment'] = self.env.company.market_segment.id
                    booking.market_segment = self.env.company.market_segment.id
                if not vals.get('source_of_business') and self.env.company.source_business:
                    vals['source_of_business'] = self.env.company.source_business.id
                    booking.source_of_business = self.env.company.source_business.id

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

                booking.create_booking_lines()
                booking.state = "block"
                booking.action_checkin()

            return booking

        # Default creation if not front_desk context
        return super().create(vals)

    def action_block_wk(self):
        self.create_booking_lines()
        for record in self:
            record.write({'state': 'block'})
        return True

    def action_un_block_wk(self):
        self.delete_booking_lines()
        for record in self:
            record.write({'state': 'not_confirmed'})
        return True

    def action_checkin_wk(self):
        for record in self:
            record.write({'state': 'check_in'})
        return True

    def action_un_checkin_wk(self):
        for record in self:
            record.write({'state': 'block'})
        return True

    def action_checkout_wk(self):
        for record in self:
            record.write({'state': 'check_out'})
        return True

    def action_cancel_wk(self):
        for record in self:
            record.write({'state': 'cancel'})
        return True

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

    def _create_master_folio(self, booking):
        """
        Create or get existing master folio for the booking
        Returns the master folio record
        """
        master_folio = self.env['tz.master.folio']
        checkin_date = fields.Date.to_date(booking.checkin_date)

        # Search criteria
        domain = [
            ('check_in', '=', checkin_date),
            ('company_id', '=', booking.company_id.id),
        ]

        company = self.env.company
        prefix = company.name + '/' if company else ''
        folio_name = prefix + (
                self.env['ir.sequence'].with_company(company).next_by_code('tz.master.folio') or 'New')

        if booking.group_booking:
            domain.append(('group_id', '=', booking.group_booking.id))
            folio = master_folio.sudo().search(domain, limit=1)
            if not folio and not booking.parent_booking_name:
                folio = master_folio.sudo().create({
                    'name': folio_name,
                    'group_id': booking.group_booking.id,
                    'room_id': booking.room_line_ids.room_id.id,
                    'guest_id': booking.partner_id.id,
                    'rooming_info': booking.group_booking.group_name,
                    'check_in': booking.checkin_date,
                    'check_out': booking.checkout_date,
                    'company_id': booking.company_id.id,
                    'currency_id': booking.company_id.currency_id.id,
                })
        else:
            # For individual room bookings
            if booking.room_line_ids:
                room = booking.room_line_ids[0].room_id
                domain.append(('room_id', '=', room.id))
                folio = master_folio.sudo().search(domain, limit=1)
                if not folio:
                    folio = master_folio.sudo().create({
                        'name': folio_name,
                        'room_id': room.id,
                        'guest_id': booking.partner_id.id,
                        'rooming_info': room.name,
                        'check_in': booking.checkin_date,
                        'check_out': booking.checkout_date,
                        'company_id': booking.company_id.id,
                        'currency_id': booking.company_id.currency_id.id,
                    })
            else:
                folio = False

        return folio

    def action_checkin(self):
        result = super(RoomBooking, self).action_checkin()

        # Get all bookings that were checked in (state = 'check_in')
        checked_in_bookings = self.filtered(lambda b: b.state == 'check_in')

        # Create master folios for each checked-in booking
        for booking in checked_in_bookings:
            self._create_master_folio(booking)

        return result

    def action_checkin_booking(self):
        # First call the original method
        result = super(RoomBooking, self).action_checkin_booking()

        # Get all bookings that were checked in (state = 'check_in')
        checked_in_bookings = self.filtered(lambda b: b.state == 'check_in')

        # Create master folios for each checked-in booking
        for booking in checked_in_bookings:
            self._create_master_folio(booking)

        # If the original result was a wizard, return it
        if isinstance(result, dict) and result.get('res_model') == 'booking.checkin.wizard':
            return result

        # Otherwise return the original result or a success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _("Booking checked in and master folio created successfully!"),
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }


class RoomRateForecast(models.Model):
    _inherit = 'room.rate.forecast'

    state = fields.Selection(
        [('draft', 'Draft'),
         ('posted', 'Posted')],
        string='Status',
        default='draft',
        tracking=True
    )

