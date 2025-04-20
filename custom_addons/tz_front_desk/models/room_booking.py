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
                # Set market_segment and source_business from company if not provided
                # Get default values from config settings
                # config = self.env['res.config.settings'].sudo().get_values()

                # if 'source_of_business' not in vals and config.get('source_of_business'):
                #     vals['source_of_business'] = config['source_of_business']
                #
                # if 'market_segment' not in vals and config.get('market_segment'):
                #     vals['market_segment'] = config['market_segment']
                # raise ValidationError(company.source_of_business.id)
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

    def save_to_master_folio(self):
        """
        Save manual posting to master folio with the following logic:
        1. Search for existing folio matching company, guest, room/group and system date
        2. If found: create only folio line
        3. If not found: create both folio header and line
        """
        self.ensure_one()

        # Prepare search domain
        domain = [
            ('company_id', '=', self.company_id.id),
            ('system_date', '=', self.checkin_date)
        ]

        # Add room or group to domain based on posting type
        if self.room_list:
            domain.append(('room_id', '=', self.room_id.room_id.id))
        elif self.type == 'group' and self.group_list:
            domain.append(('group_id', '=', self.group_booking.id))

        # Add guest to domain if available
        if self.partner_id:
            domain.append(('guest_id', '=', self.partner_id.id))

        # Search for existing folio
        folio = self.env['tz.master.folio'].sudo().search(domain, limit=1)

        # Create folio if not found
        if not folio:
            folio_vals = {
                'name': self.env['ir.sequence'].next_by_code('tz.master.folio') or 'New',
                'company_id': self.company_id.id,
                'system_date': self.date_shift,
                'room_id': self.room_list.id if self.type == 'room' else False,
                'group_id': self.group_list.id if self.type == 'group' else False,
                'guest_id': self.partner_id.id if self.partner_id else False,
                'check_in': self.date_shift
            }
            folio = self.env['tz.master.folio'].sudo().create(folio_vals)

        # Prepare folio line values
        line_vals = {
            'folio_id': folio.id,
            'date': fields.Date.context_today(self),
            'time': fields.Datetime.now().strftime('%H:%M %p'),
            'description': self.description or self.item_id.name,
            'voucher_number': self.voucher,
            'debit_amount': self.total if self.sign == 'debit' else 0.0,
            'credit_amount': self.total if self.sign == 'credit' else 0.0,
        }

        # Create folio line
        folio_line = self.env['tz.master.folio.line'].sudo().create(line_vals)

        # Return results
        return {
            'folio_id': folio.id,
            'folio_line_id': folio_line.id,
            'message': _("Posted to %s") % folio.name
        }

