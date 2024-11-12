# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Vishnu K P (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from datetime import timedelta
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError


class RoomBookingLine(models.Model):
    """Model that handles the room booking form"""
    _name = "room.booking.line"
    _description = "Hotel Folio Line"
    _rec_name = 'room_id'

    hide_fields = fields.Boolean(string="Hide Fields", default=False)

    @tools.ormcache()
    def _set_default_uom_id(self):
        return self.env.ref('uom.product_uom_day')



    booking_id = fields.Many2one("room.booking", string="Booking",
                                 help="Indicates the Room",
                                 ondelete="cascade")
    
    state = fields.Selection([
        ('block', 'Block'),
        ('no_show', 'No Show'),
        ('confirmed', 'Confirmed'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
    ], default='block', string="Status")
    
    room_availability_result_id = fields.Many2one(
        'room.availability.result', string="Room Availability Result",
        readonly=True
    )

    checkin_date = fields.Datetime(string="Check In",
                                   help="You can choose the date,"
                                        " Otherwise sets to current Date",
                                   required=True)
    checkout_date = fields.Datetime(string="Check Out",
                                    help="You can choose the date,"
                                         " Otherwise sets to current Date",
                                    required=True)
    # room_id = fields.Many2one('hotel.room', string="Room",
    #                           help="Indicates the Room",
    #                           required=False,
    #                           domain="[('num_person', '>=', parent.total_people)]"
    #                           )
    related_hotel_room_type = fields.Many2one(
        related='booking_id.hotel_room_type', 
        string="Related Room Type", 
        store=True
    )

    room_id = fields.Many2one(
        'hotel.room',
        string="Room",
        domain="[('status', '=', 'available'), ('num_person', '>=', adult_count), ('room_type_name', '=', hotel_room_type)] if hotel_room_type else [('status', '=', 'available')]",
        # domain="[('status', '=', 'available'), ('room_type_name', '=', related_hotel_room_type)] if related_hotel_room_type else [('status', '=', 'available')]",
        # required=True,
        help="Indicates the Room"
    )

    hotel_room_type = fields.Many2one(
        'room.type',
        string="Room Type",
        help="Select a room type to filter available rooms."
    )

    # @api.onchange('room_id')
    # def _onchange_room_id(self):
    #     """Update Room Type when room is selected."""
    #     if self.room_id:
    #         self.hotel_room_type = self.room_id.room_type_name

    # @api.onchange('related_hotel_room_type')
    # def _onchange_related_hotel_room_type(self):
    #     """Update the domain for room_id and sort by user_sort."""
    #     domain = [('status', '=', 'available')]
    #     if self.related_hotel_room_type:
    #         domain.append(('room_type_name', '=', self.related_hotel_room_type.id))
    #     return {
    #         'domain': {
    #             'room_id': domain,
    #         },
    #         'context': {
    #             'order': 'user_sort ASC'  # Ensure rooms are sorted by user_sort
    #         },
    #     }

    @api.onchange('hotel_room_type')
    def _onchange_hotel_room_type(self):
        """Automatically filter room_id based on hotel_room_type."""
        return {
            'domain': {
                'room_id': [
                    ('status', '=', 'available'),
                    ('room_type_name', '=', self.hotel_room_type.id)
                ] if self.hotel_room_type else [('status', '=', 'available')]
            }
        }

    # @api.onchange('hotel_room_type')
    # def _onchange_hotel_room_type(self):
    #     """Dynamically update the room_id domain based on hotel_room_type."""
    #     if self.hotel_room_type:
    #         return {
    #             'domain': {
    #                 'room_id': [
    #                     ('room_type_name', '=', self.hotel_room_type.id),
    #                     ('status', '=', 'available')
    #                 ]
    #             }
    #         }
    #     else:
    #         return {
    #             'domain': {
    #                 'room_id': [('status', '=', 'available')]
    #             }
    #         }

    def _get_dynamic_room_domain(self):
        """Get dynamic domain for room_id based on hotel_room_type."""
        domain = [('status', '=', 'available')]
        if self.hotel_room_type:
            domain.append(('room_type_name', '=', self.hotel_room_type.id))
        return domain
    
    room_type = fields.Many2one('hotel.room', string="Room Type")

    room_type_name = fields.Many2one('room.type', string="Room Type", related="room_id.room_type_name", readonly=True)

    adult_count = fields.Integer(string="Adults", readonly=True)
    child_count = fields.Integer(string="Children", related="booking_id.child_count", readonly=True)

    # adult_count = fields.Integer(string="Adults")
    # child_count = fields.Integer(string="Children")

    # @api.onchange('room_id')
    # def _onchange_room_id(self):
    #     for line in self:
    #         if line.room_id:
    #             line.room_type_name = line.room_id.room_type_name.id
    

    uom_qty = fields.Float(string="Duration",
                           compute='_compute_uom_qty',
                            inverse='_inverse_uom_qty',
                           help="The quantity converted into the UoM used by "
                                "the product")
    
    @api.depends('checkin_date', 'checkout_date')
    def _compute_uom_qty(self):
        for record in self:
            if record.checkin_date and record.checkout_date:
                duration = (record.checkout_date - record.checkin_date).days + ((record.checkout_date - record.checkin_date).seconds / 86400)
                record.uom_qty = duration

    @api.onchange('uom_qty')
    def _inverse_uom_qty(self):
        for record in self:
            if record.checkin_date and record.uom_qty:
                record.checkout_date = record.checkin_date + timedelta(days=record.uom_qty)

    @api.onchange('checkin_date', 'checkout_date')
    def _onchange_dates(self):
        for record in self:
            if record.checkin_date and record.checkout_date:
                record.uom_qty = (record.checkout_date - record.checkin_date).days + ((record.checkout_date - record.checkin_date).seconds / 86400)
            elif record.checkin_date and record.uom_qty:
                record.checkout_date = record.checkin_date + timedelta(days=record.uom_qty)



    uom_id = fields.Many2one('uom.uom',
                             default=_set_default_uom_id,
                             string="Unit of Measure",
                             help="This will set the unit of measure used",
                             readonly=True)
    price_unit = fields.Float(related='room_id.list_price', string='Rent',
                              digits='Product Price',
                              help="The rent price of the selected room.")
    tax_ids = fields.Many2many('account.tax',
                               'hotel_room_order_line_taxes_rel',
                               'room_id', 'tax_id',
                               related='room_id.taxes_ids',
                               string='Taxes',
                               help="Default taxes used when selling the room."
                               , domain=[('type_tax_use', '=', 'sale')])
    currency_id = fields.Many2one(string='Currency',
                                  related='booking_id.pricelist_id.currency_id'
                                  , help='The currency used')
    price_subtotal = fields.Float(string="Subtotal",
                                  compute='_compute_price_subtotal',
                                  help="Total Price excluding Tax",
                                  store=True)
    price_tax = fields.Float(string="Total Tax",
                             compute='_compute_price_subtotal',
                             help="Tax Amount",
                             store=True)
    price_total = fields.Float(string="Total",
                               compute='_compute_price_subtotal',
                               help="Total Price including Tax",
                               store=True)
    state = fields.Selection(related='booking_id.state',
                             string="Order Status",
                             help=" Status of the Order",
                             copy=False)
    booking_line_visible = fields.Boolean(default=False,
                                          string="Booking Line Visible",
                                          help="If True, then Booking Line "
                                               "will be visible")

    @api.onchange("checkin_date", "checkout_date")
    def _onchange_checkin_date(self):
        """When you change checkin_date or checkout_date it will check
        and update the qty of hotel service line
        -----------------------------------------------------------------
        @param self: object pointer"""
        if self.checkout_date < self.checkin_date:
            raise ValidationError(
                _("Checkout must be greater or equal checkin date"))
        if self.checkin_date and self.checkout_date:
            diffdate = self.checkout_date - self.checkin_date
            qty = diffdate.days
            if diffdate.total_seconds() > 0:
                qty = qty + 1
            self.uom_qty = qty

    @api.depends('uom_qty', 'price_unit', 'tax_ids')
    def _compute_price_subtotal(self):
        """Compute the amounts of the room booking line."""
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes(
                [line._convert_to_tax_base_line_dict()])
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']
            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })
            if self.env.context.get('import_file',
                                    False) and not self.env.user. \
                    user_has_groups('account.group_account_manager'):
                line.tax_id.invalidate_recordset(
                    ['invoice_repartition_line_ids'])

    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the
        generic taxes computation method
        defined on account.tax.
        :return: A python dictionary."""
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.booking_id.partner_id,
            currency=self.currency_id,
            taxes=self.tax_ids,
            price_unit=self.price_unit,
            quantity=self.uom_qty,
            price_subtotal=self.price_subtotal,
        )

    
    is_unassigned = fields.Boolean(string="Is Unassigned", default=True,
                                   help="Indicates if the room line is unassigned.")
    
    @api.onchange('room_id')
    def _onchange_room_id(self):
        if self.booking_id.state != 'confirmed':
            raise UserError("Please confirm booking first.")
        
    @api.model
    def _update_inventory(self, room_type_id, company_id, increment=True):
        """Update available rooms in hotel.inventory."""
        inventory = self.env['hotel.inventory'].search([
            ('room_type', '=', room_type_id),
            ('company_id', '=', company_id)
        ], limit=1)
        
        if inventory:
            if increment:
                inventory.available_rooms += 1
            else:
                inventory.available_rooms -= 1

    @api.model
    def assign_room(self, parent_booking, room_vals):
        """Assign a room from a parent booking, creating a child booking."""
        new_booking_vals = {
            'parent_booking_id': parent_booking.id,  # Link parent booking
            'room_line_ids': [(0, 0, room_vals)],
            'state': 'block',  # New state for child booking
        }

        # Create child booking with reference to parent
        return self.env['room.booking'].create(new_booking_vals)

    def write(self, vals):
        for record in self:
            # Handle room assignment change
            if 'room_id' in vals and record.room_id:
                # Increment the inventory count for the previous room type (unassigning room)
                self._update_inventory(record.room_type_name.id, record.booking_id.company_id.id, increment=True)
                # Decrement the inventory count for the new room type (assigning room)
                self._update_inventory(vals['room_id'], record.booking_id.company_id.id, increment=False)

            # Original logic for handling room assignment
            if 'room_id' in vals and record.is_unassigned:
                if record.booking_id and record.booking_id.state == 'confirmed':
                    parent_booking = record.booking_id
                    
                    # Prepare values for the new booking line
                    new_booking_vals = {
                        'room_id': vals['room_id'],
                        'checkin_date': record.checkin_date,
                        'checkout_date': record.checkout_date,
                        'uom_qty': record.uom_qty,
                        'adult_count': record.adult_count,
                        'child_count': record.child_count,
                    }

                    # Prepare the adult lines based on the adult_count
                    adult_lines = [(0, 0, {
                        'first_name': '',
                        'last_name': '',
                        'profile': '',  # Set default values or keep empty
                        'nationality': '',
                        'birth_date': False,
                        'passport_number': '',
                        'id_number': '',
                        'visa_number': '',
                        'id_type': '',
                        'phone_number': '',
                        'relation': ''
                    }) for _ in range(record.adult_count)]

                    # Prepare the child lines based on the child_count
                    child_lines = [(0, 0, {
                        'first_name': '',
                        'last_name': '',
                        'profile': '',
                        'nationality': '',
                        'birth_date': False,
                        'passport_number': '',
                        'id_number': '',
                        'visa_number': '',
                        'id_type': '',
                        'phone_number': '',
                        'relation': ''
                    }) for _ in range(record.child_count)]

                    # Create the new booking with adult_ids based on adult count
                    self.env['room.booking'].create({
                        'parent_booking_id': parent_booking.id,
                        'room_line_ids': [(0, 0, new_booking_vals)],
                        'checkin_date': record.checkin_date,
                        'checkout_date': record.checkout_date,
                        'state': 'block',  # Set state to block
                        'adult_ids': adult_lines,  # Add the adult lines here
                        'is_room_line_readonly': False,
                    })

                    # Update the original record to unassign and hide fields
                    record.write({
                        'booking_id': False,
                        'hide_fields': True  # Set the flag to hide fields
                    })
                    vals['is_unassigned'] = False

        return super(RoomBookingLine, self).write(vals)

    # def unlink(self):
    #     """Override unlink to restore inventory when a line is deleted."""
    #     for line in self:
    #         self._update_inventory(line.room_type_name.id, line.booking_id.company_id.id, increment=True)
    #     return super(RoomBookingLine, self).unlink()
    def unlink(self):
        """Override unlink to restore inventory when a line is deleted."""
        # for line in self:
        #     self._update_inventory(line.room_type_name.id, line.booking_id.company_id.id, increment=True)
        return super(RoomBookingLine, self).unlink()


    # @api.onchange('checkin_date', 'checkout_date', 'room_id')
    # def onchange_checkin_date(self):
    #     records = self.env['room.booking'].search(
    #         [('state', 'in', ['reserved', 'check_in'])])
    #     for rec in records:
    #         rec_room_id = rec.room_line_ids.room_id
    #         rec_checkin_date = rec.room_line_ids.checkin_date
    #         rec_checkout_date = rec.room_line_ids.checkout_date

    #         if rec_room_id and rec_checkin_date and rec_checkout_date:
    #             # Check for conflicts with existing room lines
    #             for line in self:
    #                 if line.id != rec.id and line.room_id == rec_room_id:
    #                     # Check if the dates overlap
    #                     if (rec_checkin_date <= line.checkin_date <= rec_checkout_date or
    #                             rec_checkin_date <= line.checkout_date <= rec_checkout_date):
    #                         raise ValidationError(
    #                             _("Sorry, You cannot create a reservation for "
    #                               "this date since it overlaps with another "
    #                               "reservation..!!"))
    #                     if rec_checkout_date <= line.checkout_date and rec_checkin_date >= line.checkin_date:
    #                         raise ValidationError(
    #                             "Sorry You cannot create a reservation for this"
    #                             "date due to an existing reservation between "
    #                             "this date")
