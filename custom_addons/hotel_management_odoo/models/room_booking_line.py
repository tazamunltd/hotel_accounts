from datetime import timedelta
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.models import NewId


class RoomBookingLine(models.Model):
    """Model that handles the room booking form"""
    _name = "room.booking.line"
    _description = "Hotel Folio Line"
    _rec_name = 'room_id'

    sequence = fields.Integer(
        string='Sequence', compute='_compute_sequence', store=True)

    # Depends on the field that relates to the records
    @api.depends('booking_id.room_line_ids')
    def _compute_sequence(self):
        # Iterate through all related bookings
        for record in self.mapped('booking_id'):
            sequence = 1
            for line in record.room_line_ids.sorted('create_date'):
                line.sequence = sequence
                sequence += 1

    counter = fields.Integer(string="Counter", default=0)

    housekeeping_status = fields.Many2one(
        'housekeeping.status', string="Housekeeping Status", compute="_compute_room_statuses", store=False
    )
    maintenance_status = fields.Many2one(
        'maintenance.status', string="Maintenance Status", compute="_compute_room_statuses", store=False
    )
    housekeeping_staff_status = fields.Many2one(
        'housekeeping.staff.status', string="Housekeeping Staff Status", compute="_compute_room_statuses", store=False
    )

    @api.depends('room_id')
    def _compute_room_statuses(self):
        for record in self:
            if record.room_id:
                record.housekeeping_status = record.room_id.housekeeping_status.id
                record.maintenance_status = record.room_id.maintenance_status.id
                record.housekeeping_staff_status = record.room_id.housekeeping_staff_status.id
            else:
                record.housekeeping_status = False
                record.maintenance_status = False
                record.housekeeping_staff_status = False

    hide_fields = fields.Boolean(string="Hide Fields", default=False)

    @tools.ormcache()
    def _set_default_uom_id(self):
        return self.env.ref('uom.product_uom_day')

    booking_id = fields.Many2one("room.booking", string="Booking",
                                 help="Indicates the Room",
                                 ondelete="cascade")

    state = fields.Selection([
        ('not_confirmed', 'Not Confirmed'),
        ('block', 'Block'),
        ('no_show', 'No Show'),
        ('confirmed', 'Confirmed'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
    ], default='block', string="Status", compute='_compute_state', store=True)

    @api.depends('booking_id.state')
    def _compute_state(self):
        for record in self:
            record.state = record.booking_id.state

    hide_room_id = fields.Boolean(
        string='Hide Room Field', compute='_compute_hide_room_id')

    @api.depends('booking_id.state')
    def _compute_hide_room_id(self):
        for record in self:
            record.hide_room_id = record.booking_id.state == 'block'

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

    related_hotel_room_type = fields.Many2one(
        related='booking_id.hotel_room_type',
        string="Related Room Type",
        store=True
    )

    room_id = fields.Many2one(
        'hotel.room',
        string="Room",
        domain="[('status', '=', 'available'), ('room_type_name', '=', hotel_room_type), "
        "('id', 'not in', booked_room_ids)] if hotel_room_type else [('status', '=', 'available'), "
        "('id', 'not in', booked_room_ids)]",
        help="Indicates the Room")

    @api.onchange('hotel_room_type', 'adult_count')
    def _onchange_room_type_or_pax(self):
        for line in self:
            print("102", line.hotel_room_type, line.adult_count)

    booked_room_ids = fields.Many2many(
        'hotel.room',
        compute='_compute_booked_room_ids',
        string='Booked Rooms',
        store=False
    )

    # @api.depends('checkin_date', 'checkout_date', 'room_id')
    # def _compute_booked_room_ids(self):
    #     print("Inside _compute_booked_room_ids")
    #     for record in self:
    #         if not record.id or isinstance(record.id, str):
    #             # Skip unsaved records
    #             record.booked_room_ids = False
    #             continue

    #         # Perform the search only for saved records
    #         overlapping_bookings = self.env['room.booking.line'].search([
    #             ('room_id', '=', record.room_id.id),
    #             ('id', '!=', record.id),  # Exclude current record
    #             ('checkin_date', '<=', record.checkout_date),
    #             ('checkout_date', '>=', record.checkin_date),
    #         ])

    #         print("overlapping_bookings", overlapping_bookings)

    #         record.booked_room_ids = overlapping_bookings.mapped('room_id')

    @api.depends('checkin_date', 'checkout_date')
    def _compute_booked_room_ids(self):
        for record in self:
            if isinstance(record.id, NewId):
                # Skip unsaved records, as they do not have a valid database ID
                record.booked_room_ids = []
                continue

            if record.checkin_date and record.checkout_date:
                # Search for all bookings overlapping the current booking's date range
                overlapping_bookings = self.env['room.booking.line'].search([
                    ('checkin_date', '<', record.checkout_date),
                    ('checkout_date', '>', record.checkin_date),
                    ('room_id', '!=', False),
                    ('id', '!=', record.id)  # Exclude current record
                ])
                # Collect room IDs that are already booked
                record.booked_room_ids = overlapping_bookings.mapped(
                    'room_id.id')
            else:
                record.booked_room_ids = []

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
        # print("192", self.room_id.status)
        # print("193", self.hotel_room_type)
        print("196", self.room_id, self.booking_id.room_line_ids, self.booking_id.id)
        parent_booking_id = self.booking_id.id
        print(parent_booking_id, type(parent_booking_id))
        # numeric_parent_id = parent_booking_id.split('=')[-1].strip('>')
        if isinstance(parent_booking_id, NewId):
            parent_booking_id_str = str(parent_booking_id)
            if '_' in parent_booking_id_str:
                numeric_parent_id = int(parent_booking_id_str.split('_')[-1])
                print('204', numeric_parent_id)
                parent_booking_ids = self.env['room.booking'].search(
                    [('parent_booking_id', '=', numeric_parent_id)]).mapped('id')
                room_booking_line_ids = self.env['room.booking.line'].search(
                    [('booking_id', 'in', parent_booking_ids),
                     ('counter', '=', self.counter)],
                    order='id asc'  # Sort in ascending order
                ).ids
                room_ids_count = len(room_booking_line_ids)
                print(room_ids_count)
                print(
                    f"Room Booking Line IDs for room type: {room_booking_line_ids}")
        # Find the affected room booking line
        affected_line = self.booking_id.room_line_ids.filtered(
            lambda line: line.id == self.id)

        if affected_line:
            affected_line_str = str(affected_line.id)

            # Extract only the numeric part
            numeric_id = affected_line_str.split('=')[-1].strip('>')
            numeric_id = int(numeric_id.split('_')[-1])
            print(
                f"Updating roo type for room_line_id {numeric_id}. New Room ID: {self.room_id.id}")
            if len(room_booking_line_ids) > 0:
                recordset = self.env['room.booking.line'].search([
                    ('id', 'in', [numeric_id, room_booking_line_ids[0]])
                ])
            else:
                recordset = self.env['room.booking.line'].search([
                    ('id', 'in', [numeric_id])
                ])

            # Check if records exist
            if recordset:
                print(f"Updating Room : {recordset.ids}")

                # Update all records with the new room_id
                recordset.write({
                    'hotel_room_type': self.hotel_room_type.id,
                    'related_hotel_room_type': self.hotel_room_type.id,
                })

            # record = self.env['room.booking.line'].browse(numeric_id)
            #
            # # Check if the record exists
            # if record.exists():
            #     # Retrieve the value of the 'counter' column
            #     counter_value = record.counter
            #     print(f"The value of the 'counter' column for ID 6162 is: {counter_value}")
            # affected_line.write({
            #     'hotel_room_type': self.hotel_room_type,
            #     'related_hotel_room_type': self.related_hotel_room_type,
            #     'id': numeric_id,  # Pass the affected_line_id in the write operation
            #     'counter': counter_value
            # })
        return {
            'domain': {
                'room_id': [
                    ('status', '=', 'available'),
                    ('room_type_name', '=', self.hotel_room_type.id)
                ] if self.hotel_room_type else [('status', '=', 'available')]
            }
        }

    def _get_dynamic_room_domain(self):
        """Get dynamic domain for room_id based on hotel_room_type."""
        domain = [('status', '=', 'available')]
        if self.hotel_room_type:
            domain.append(('room_type_name', '=', self.hotel_room_type.id))
        return domain

    room_type = fields.Many2one('hotel.room', string="Room Type")

    room_type_name = fields.Many2one(
        'room.type', string="Room Type", related="room_id.room_type_name", readonly=True)

    adult_count = fields.Integer(string="Adults", readonly=True)
    child_count = fields.Integer(
        string="Children", related="booking_id.child_count", readonly=True)

    uom_qty = fields.Float(string="Duration",
                           compute='_compute_uom_qty',
                           inverse='_inverse_uom_qty',
                           help="The quantity converted into the UoM used by "
                                "the product")

    @api.depends('checkin_date', 'checkout_date')
    def _compute_uom_qty(self):
        for record in self:
            if record.checkin_date and record.checkout_date:
                duration = (record.checkout_date - record.checkin_date).days + \
                    ((record.checkout_date - record.checkin_date).seconds / 86400)
                record.uom_qty = duration

    @api.onchange('uom_qty')
    def _inverse_uom_qty(self):
        for record in self:
            if record.checkin_date and record.uom_qty:
                record.checkout_date = record.checkin_date + \
                    timedelta(days=record.uom_qty)

    # @api.onchange('checkin_date', 'checkout_date')
    # def _onchange_dates(self):
    #     for record in self:
    #         if record.checkin_date and record.checkout_date:
    #             record.uom_qty = (record.checkout_date - record.checkin_date).days + (
    #                 (record.checkout_date - record.checkin_date).seconds / 86400)
    #         elif record.checkin_date and record.uom_qty:
    #             record.checkout_date = record.checkin_date + \
    #                 timedelta(days=record.uom_qty)

    #         # Adjust visibility based on booking state
    #         if record.booking_id.state == 'block':
    #             record.hide_room_id = True
    #             record.room_id = False  # Optionally clear the room_id field
    #         else:
    #             record.hide_room_id = False

    # @api.onchange('checkin_date', 'checkout_date', 'hotel_room_type')
    # def _onchange_dates(self):
    #     if self.checkin_date and self.checkout_date:
    #         overlapping_bookings = self.env['room.booking.line'].search([
    #             ('room_id', '!=', False),
    #             ('checkin_date', '<', self.checkout_date),
    #             ('checkout_date', '>', self.checkin_date),
    #             ('booking_id.state', 'in', ['confirmed', 'block', 'check_in']),
    #             ('id', '!=', self.id),
    #         ])
    #         self.booked_room_ids = overlapping_bookings.mapped('room_id.id')
    #         print("Booked Room IDs:", self.booked_room_ids)  # Debugging line
    #     else:
    #         self.booked_room_ids = []

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
                               help="Default taxes used when selling the room.", domain=[('type_tax_use', '=', 'sale')])
    currency_id = fields.Many2one(string='Currency',
                                  related='booking_id.pricelist_id.currency_id', help='The currency used')
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

    # @api.onchange('room_id')
    # def _onchange_room_id(self):
    #     if self.booking_id.state != 'confirmed':
    #         raise UserError("Please confirm booking first.")

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

    # @api.onchange('room_id')
    # def _onchange_room_id(self):
    #     """When the room_id changes, set the state to confirmed."""
    #     if self.room_id:
    #         self.state = 'confirmed'

    def unlink(self):
        """Override unlink to handle cascading deletion of related child records."""
        for record in self:
            if record.booking_id:
                # Find the corresponding child bookings based on sequence or counter
                child_bookings = self.env['room.booking'].search([
                    ('parent_booking_id', '=', record.booking_id.id),
                    # Assuming counter identifies related lines
                    ('room_line_ids.counter', '=', record.counter)
                ])

                # Log details for debugging
                print(
                    f"Deleting related child bookings: {child_bookings.ids} for record {record.id}")

                # Delete related child bookings
                child_bookings.unlink()

        # Call the original unlink method to delete the current record
        return super(RoomBookingLine, self).unlink()

    def assign_room_manual(self, room_id):
        """Method to handle manual room assignments with proper context"""
        return self.with_context(skip_code_validation=True).write({
            'room_id': room_id,
        })

    @api.onchange('room_id')
    def _onchange_room_id(self):
        """Update booking state based on room_id value and log changes."""
        if self.booking_id:
            existing_room_ids = self.booking_id.room_line_ids.filtered(
                lambda line: line.id != self.id).mapped('room_id.id')
            # existing_room_ids.write({'state':'block'})
            print("393", existing_room_ids)
            if self.room_id.id in existing_room_ids:
                # Reset the field and raise a warning
                raise ValidationError(
                    "This room is already assigned to the current booking. Please select a different room.")

            if self.room_id is None:
                # self.booking_id.state = 'not_confirmed'
                print(
                    f"Room ID cleared. Booking state updated to 'not_confirmed' for booking ID {self.booking_id.id}.")
            else:
                print("395", self.room_id, self.booking_id.room_line_ids,
                      self.booking_id.id, self.counter)
                parent_booking_id = self.booking_id.id
                print(parent_booking_id, type(parent_booking_id))
                # numeric_parent_id = parent_booking_id.split('=')[-1].strip('>')
                if isinstance(parent_booking_id, NewId):
                    parent_booking_id_str = str(parent_booking_id)
                    if '_' in parent_booking_id_str:
                        numeric_parent_id = int(
                            parent_booking_id_str.split('_')[-1])
                        print('404', numeric_parent_id)
                        parent_booking_ids = self.env['room.booking'].search(
                            [('parent_booking_id', '=', numeric_parent_id)]).mapped('id')
                        print('457', parent_booking_ids)
                        room_booking_line_ids = self.env['room.booking.line'].search(
                            [('booking_id', 'in', parent_booking_ids),
                             ('counter', '=', self.counter)
                             ],
                            order='id asc'  # Sort in ascending order
                        ).ids
                        print('454', room_booking_line_ids)
                        room_ids_count = len(room_booking_line_ids)
                        print(room_ids_count)
                        print(
                            f"Room Booking Line IDs: {room_booking_line_ids}")
                # Find the affected room booking line
                affected_line = self.booking_id.room_line_ids.filtered(
                    lambda line: line.id == self.id)
                print('459', affected_line)

                if affected_line:
                    affected_line_str = str(affected_line.id)

                    # Extract only the numeric part
                    numeric_id = affected_line_str.split('=')[-1].strip('>')
                    numeric_id = int(numeric_id.split('_')[-1])
                    print(
                        f"Updating room ID for room_line_id {numeric_id}. New Room ID: {self.room_id.id}")
                    if len(room_booking_line_ids) > 0:
                        recordset = self.env['room.booking.line'].search([
                            ('id', 'in', [numeric_id,
                             room_booking_line_ids[0]])
                        ])
                    else:
                        recordset = self.env['room.booking.line'].search([
                            ('id', 'in', [numeric_id])
                        ])

                    # Check if records exist
                    if recordset:
                        print(
                            f"Updating Room Booking Lines with IDs: {recordset.ids}")

                        # Update all records with the new room_id
                        recordset.write({
                            'room_id': self.room_id.id
                        })

                    # record_tx = self.env['room.booking.line'].search([("id","in",[numeric_id,room_booking_line_ids[0]])])
                    # print('481', record_tx, numeric_id,room_booking_line_ids[0])
                    #
                    # # Check if the record exists
                    # if record_tx.exists():
                    #     for rec in  record_tx:
                    #
                    #     # Retrieve the value of the 'counter' column
                    #         counter_value = rec.counter
                    #         print(f"The value of the 'counter' column for ID 6162 is: {counter_value}")

                        # super(RoomBookingLine, affected_line).write({'room_id': self.room_id.id, 'counter': counter_value, 'id':numeric_id})
                else:
                    print(
                        f"New room_line created with Room ID {self.room_id.id}.")

            self.booking_id.state = 'confirmed'
            print(
                f"Room ID assigned. Booking state updated to 'confirmed' for booking ID {self.booking_id.id}.")
        if not self.room_id and not self.booking_id.parent_booking_id:
            print("Line 498")
            self._delete_child_booking_records(self.counter, self.booking_id)
            self.booking_id.write({'state': 'not_confirmed'})
            return

    @api.onchange('room_line_ids')
    def _onchange_room_lines(self):
        """Triggered when room lines are changed to adjust booking state."""
        for line in self.room_line_ids:
            if line.room_id is None:
                self.state = 'not_confirmed'
            else:
                self.state = 'confirmed'
                break

    

    def create_adult_record(self, parent_booking):
        # Fetch child bookings associated with the parent booking
        child_bookings = self.env['room.booking'].search(
            [('parent_booking_id', '=', parent_booking.id)], order='id')
        print("Child bookings for parent booking:", child_bookings)

        # Update existing adult and child records with new room_id
        adults_to_update = self.env['reservation.adult'].search([
            ('reservation_id', '=', parent_booking.id),
            ('room_sequence', '=', self.sequence)
        ])
        adults_to_update.write({'room_id': self.room_id.id})

        children_to_update = self.env['reservation.child'].search([
            ('reservation_id', '=', parent_booking.id),
            ('room_sequence', '=', self.sequence)
        ])
        children_to_update.write({'room_id': self.room_id.id})

        # Fetch adults from the parent booking with the same room sequence
        parent_adults = self.env['reservation.adult'].search([
            ('reservation_id', '=', parent_booking.id),
            ('room_sequence', '=', self.sequence)
        ])

        # Fetch children from the parent booking with the same room sequence
        parent_children = self.env['reservation.child'].search([
            ('reservation_id', '=', parent_booking.id),
            ('room_sequence', '=', self.sequence)
        ])

        ctr_sequence = self.sequence
        if len(child_bookings) < (ctr_sequence - 1):
            ctr_sequence = ctr_sequence - 1
        else:
            ctr_sequence = len(child_bookings) - 1

        # Handle adults
        for adult in parent_adults:
            # Ensure we only create unique records
            existing_adult = self.env['reservation.adult'].search([
                ('reservation_id', '=', child_bookings[ctr_sequence].id),
                ('room_sequence', '=', adult.room_sequence),
                ('first_name', '=', adult.first_name),
                ('last_name', '=', adult.last_name)
            ])

            if not existing_adult:
                # Prepare adult record values
                adult_line_vals = {
                    'reservation_id': child_bookings[ctr_sequence].id,
                    'room_sequence': self.sequence,
                    'first_name': adult.first_name,
                    'last_name': adult.last_name,
                    'profile': adult.profile,
                    'nationality': adult.nationality.id if adult.nationality else False,
                    'birth_date': adult.birth_date,
                    'passport_number': adult.passport_number,
                    'id_number': adult.id_number,
                    'visa_number': adult.visa_number,
                    'id_type': adult.id_type,
                    'phone_number': adult.phone_number,
                    'relation': adult.relation,
                    'room_type_id': self.hotel_room_type.id,
                    'room_id': self.room_id.id,
                }

                # Create the adult record
                self.env['reservation.adult'].sudo().create(adult_line_vals)
                print(
                    f"Created new adult record for booking: {child_bookings[ctr_sequence].id}, Room Sequence: {ctr_sequence}")

        # Handle children
        for child in parent_children:
            # Ensure we only create unique records
            existing_child = self.env['reservation.child'].search([
                ('reservation_id', '=', child_bookings[ctr_sequence].id),
                ('room_sequence', '=', child.room_sequence),
                ('first_name', '=', child.first_name),
                ('last_name', '=', child.last_name)
            ])

            if not existing_child:
                # Prepare child record values
                child_line_vals = {
                    'reservation_id': child_bookings[ctr_sequence].id,
                    'room_sequence': self.sequence,
                    'first_name': child.first_name,
                    'last_name': child.last_name,
                    'profile': adult.profile,
                    'nationality': adult.nationality.id if adult.nationality else False,
                    'birth_date': adult.birth_date,
                    'passport_number': adult.passport_number,
                    'id_number': adult.id_number,
                    'visa_number': adult.visa_number,
                    'id_type': adult.id_type,
                    'phone_number': adult.phone_number,
                    'relation': adult.relation,
                    'room_type_id': self.hotel_room_type.id,
                    'room_id': self.room_id.id,
                }

                # Create the child record
                self.env['reservation.child'].sudo().create(child_line_vals)
                print(
                    f"Created new child record for booking: {child_bookings[ctr_sequence].id}, Room Sequence: {ctr_sequence}")

    def write(self, vals):
        records_to_update = []
        records_to_delete = []
        parent_bookings_to_update = []
        processed_parent_bookings = set()
        for record in self:
            if record.booking_id:
                # Fetch the booking record to get the parent_booking_id
                booking_record = self.env['room.booking'].browse(
                    record.booking_id.id)
                parent_booking_id = booking_record.parent_booking_id
                counter_write = 0
                if parent_booking_id:
                    # Fetch the room_id from the updated vals or fallback to the current record
                    room_id = vals.get('room_id') or record.room_id.id
                    if room_id:
                        # Ensure parent_booking_id is an integer and not a recordset
                        parent_booking_id_int = parent_booking_id.id
                        # Search for matching room.booking.line records
                        booking_line_records = self.env['room.booking.line'].search([
                            ('booking_id', '=', parent_booking_id_int),
                            ('room_id', '=', room_id)
                        ])

                        # Process the counter values if matching lines are found
                        if booking_line_records:
                            # print(f"Found {len(booking_line_records)} records matching the criteria.")
                            for line in booking_line_records:
                                counter_write = line.counter
                                # print(f"Room Booking Line ID: {line.id}, Counter: {line.counter}")
            parent_booking = record.booking_id
            # Retrieve room bookings associated with the parent_booking_id
            room_bookings = self.env['room.booking'].search(
                [('parent_booking_id', '=', parent_booking.id)])
            # print(f"Room bookings for parent_booking_id {parent_booking.id}: {room_bookings}")
            if 'room_id' in vals and 'id' in vals:
                room_id = vals.get("room_id")
                record_id = vals.get("id")

                # Ensure the record has a valid database ID
                if isinstance(record_id, list):
                    child_booking = self.env['room.booking.line'].search([
                        # Search for records with IDs in the list
                        ('id', 'in', record_id),
                        # ('counter', '=', counter)  # Include the counter in the search criteria
                    ])
                    if child_booking.exists():
                        for child in child_booking:
                            # print(f"Updating Room ID for Room Booking Line ID: {child}")
                            super(RoomBookingLine, child).write(
                                {'room_id': room_id})
                        return
                    else:
                        print(
                            f"No Room Booking Line found with ID: {record_id}")
                else:
                    print(
                        f"Skipping write operation for non-integer ID: {record_id}")

            if 'hotel_room_type' in vals:
                room_type = vals.get("hotel_room_type")
                # print('536', room_type)
                related_room_type = vals.get("related_hotel_room_type")
                super(RoomBookingLine, record).write(
                    {'hotel_room_type': room_type, 'related_hotel_room_type': room_type, 'room_id': False})

            if 'room_id' in vals and 'id' not in vals:
                # print('588', vals)
                room_id = vals.get('room_id')
                new_room_id = vals['room_id']
                counter = vals.get('counter')
                old_room_id = record.room_id
                # print("477",old_room_id.id)
                if room_id:
                    super(RoomBookingLine, record).write(
                        {'room_id': new_room_id, 'state': 'block'})
                    # print(f"Updating room_id for record {record.id} to {room_id}")

                if new_room_id:
                    counter = vals.get('counter')

                    # Update current record's room_id
                    # print('running super write ethod', counter)
                    super(RoomBookingLine, record).write(
                        {'room_id': new_room_id, 'state': 'block'})

                    # Check and update child bookings
                    for child_booking in room_bookings:
                        print(room_id == new_room_id)
                        if not child_booking.room_line_ids:
                            child_booking.sudo().write({
                                'state': 'block',  # Update state to block for reassigned room
                                'room_line_ids': [(0, 0, {
                                    'room_id': new_room_id,
                                    'checkin_date': record.checkin_date,
                                    'checkout_date': record.checkout_date,
                                    'uom_qty': 1,
                                    'adult_count': record.adult_count,
                                    'child_count': record.child_count,
                                    'hotel_room_type': record.hotel_room_type.id,
                                    'counter': counter
                                })]
                            })
                            # print(f"Reassigned room_id {new_room_id} for child booking {child_booking.id}.")

                    # Check if all rooms are assigned in the parent booking
                    # all_rooms_assigned = all(line.room_id for line in parent_booking.room_line_ids)
                    # if all_rooms_assigned:
                    #     parent_bookings_to_update.append((parent_booking, {
                    #         'is_room_line_readonly': True
                    #     }))

                # If room_id is not provided, move to 'not_confirmed' state
                if not room_id:
                    new_booking_vals = {
                        'parent_booking_id': parent_booking.id,
                        'parent_booking_name': parent_booking.name,
                        'partner_id': parent_booking.partner_id.id,
                        'reference_contact_': parent_booking.reference_contact.id,
                        'hotel_room_type': parent_booking.hotel_room_type.id,
                        'group_booking': parent_booking.group_booking.id,
                        'room_line_ids': [],  # No room_line_ids since room_id is unlinked
                        'checkin_date': record.checkin_date,
                        'checkout_date': record.checkout_date,
                        'state': 'not_confirmed',  # Ensure state is set to 'not_confirmed'
                        'is_room_line_readonly': False,
                    }
                    # print(f"New booking created with state 'not_confirmed' due to missing room_id.")

                    # print(f"Room_id removed for record {record.id}. Moving booking to 'not_confirmed' state.")

                    parent_bookings_to_update.append(
                        (parent_booking, {'state': 'confirmed'}))
                    continue

                # Ensure the booking is confirmed before assigning a room
                if parent_booking.state != 'confirmed' and len(parent_booking.room_line_ids) > 1:
                    raise UserError(
                        "Please confirm the booking before assigning a room.")

                # Move to 'block' state if only one entry exists
                if len(parent_booking.room_line_ids) == 1:
                    parent_bookings_to_update.append((parent_booking, {
                        'state': 'block'
                    }))
                    # print(f"Booking {parent_booking.id} moved to 'block' state as it has only one room line.")
                else:
                    # print('685', vals)
                    counter = vals.get('counter')
                    booking_record = self.env['room.booking'].browse(
                        record.booking_id.id)
                    # print('736', booking_record)
                    parent_booking_id = booking_record.parent_booking_id

                    if parent_booking_id:
                        # Fetch the room_id from the updated vals or fallback to the current record
                        room_id = vals.get('room_id') or record.room_id.id
                        if room_id:
                            # Ensure parent_booking_id is an integer and not a recordset
                            parent_booking_id_int = parent_booking_id.id
                            # Search for matching room.booking.line records
                            booking_line_records = self.env['room.booking.line'].search([
                                ('booking_id', '=', parent_booking_id_int),
                                ('room_id', '=', room_id)
                            ])

                            # Process the counter values if matching lines are found
                            if booking_line_records:
                                print(
                                    f"Found {len(booking_line_records)} records matching the criteria.")
                                for line in booking_line_records:
                                    counter = line.counter
                                    # print(f"Room Booking Line ID: {line.id}, Counter: {line.counter}")
                    # Handle unassigned lines and create a new child booking if needed
                    if record.is_unassigned and parent_booking.state == 'confirmed':
                        if parent_booking.id in processed_parent_bookings:
                            continue  # Skip if this parent booking is already processed

                        new_booking_vals = {
                            'parent_booking_id': parent_booking.id,
                            'parent_booking_name': parent_booking.name,
                            'partner_id': parent_booking.partner_id.id,
                            'nationality': parent_booking.nationality.id,
                            'source_of_business': parent_booking.source_of_business.id,
                            'meal_pattern': parent_booking.meal_pattern.id,
                            'market_segment': parent_booking.market_segment.id,
                            'rate_code': parent_booking.rate_code.id,
                            'reference_contact_': parent_booking.reference_contact.id,
                            'hotel_room_type': parent_booking.hotel_room_type.id,
                            'group_booking': parent_booking.group_booking.id,
                            'house_use': True,
                            # 'show_in_tree':True,
                            'complementary': True,
                            'room_line_ids': [(0, 0, {
                                'sequence': record.sequence,
                                'room_id': room_id,
                                'checkin_date': parent_booking.checkin_date,
                                'checkout_date': parent_booking.checkout_date,
                                'uom_qty': 1,
                                'adult_count': record.adult_count,
                                'child_count': record.child_count,
                                'is_unassigned': False,
                                'hotel_room_type': record.hotel_room_type.id,
                                'counter': counter
                            })],
                            'posting_item_ids': [(6, 0, parent_booking.posting_item_ids.ids)],
                            'checkin_date': parent_booking.checkin_date,
                            'checkout_date': parent_booking.checkout_date,
                            'state': 'block',
                            'group_booking': parent_booking.group_booking.id,
                            # 'is_room_line_readonly': True,
                        }

                        # # new_booking_vals['adult_ids'] = adult_lines + child_lines
                        # new_booking_vals['adult_ids'] = adult_lines

                        # Create the new child booking
                        self.env['room.booking'].create(new_booking_vals)
                        self.create_adult_record(parent_booking)

                        # Mark the unassigned line as processed
                        records_to_update.append(
                            (record, {'is_unassigned': False, 'room_id': room_id}))
                        processed_parent_bookings.add(parent_booking.id)
            else:
                if 'checkout_date' in vals and counter_write != 0:
                    super(RoomBookingLine, record).write(
                        {'counter': counter_write})

                # No room_id provided; leave the line unchanged
                # print(f"No room_id provided for line {record.id}. Keeping it unchanged.")

        # Perform all pending updates
        for record, record_vals in records_to_update:
            # print(f"Updating record: {record}, values: {record_vals}")
            super(RoomBookingLine, record).write(record_vals)

        for booking, booking_vals in parent_bookings_to_update:
            # print(f"Updating parent booking: {booking}, values: {booking_vals}")
            booking.write(booking_vals)

        # Call super to finalize other updates
        result = super(RoomBookingLine, self).write(vals)

        if 'room_id' in vals:
            for line in self:
                # Ensure we have a booking and a sequence
                if line.booking_id and line.sequence and line.room_id:
                    # Update Adults
                    adults_to_update = self.env['reservation.adult'].search([
                        ('reservation_id', '=', line.booking_id.id),
                        ('room_sequence', '=', line.sequence)
                    ])
                    if adults_to_update:
                        adults_to_update.write({'room_id': line.room_id.id})

                    # Update Children
                    children_to_update = self.env['reservation.child'].search([
                        ('reservation_id', '=', line.booking_id.id),
                        ('room_sequence', '=', line.sequence)
                    ])
                    if children_to_update:
                        children_to_update.write({'room_id': line.room_id.id})
        
        return result

    def _delete_child_booking_records(self, counter, parent_booking):
        """Helper function to delete child booking records."""
        # Find all child bookings related to this parent booking
        child_bookings = self.env['room.booking'].search([
            ('parent_booking_id', '=', parent_booking.id)
        ])

        for child_booking in child_bookings:
            # Find matching room lines in child booking based on counter
            matching_lines = child_booking.room_line_ids.filtered(
                lambda line: line.counter == counter
            )

            if matching_lines:
                # Set state to cancel before deletion
                matching_lines.sudo().write({'state': 'cancel'})
                # Delete matching lines
                matching_lines.sudo().unlink()

                # If no room lines left, set booking to cancel and delete
                if not child_booking.room_line_ids:
                    child_booking.sudo().write({
                        'show_in_tree': False,
                        'state': 'cancel'
                    })
                    child_booking.sudo().unlink()

    def unlink(self):
        """Handle deletion of room booking lines."""
        for record in self:
            if record.booking_id and not record.booking_id.parent_booking_id:
                # Set state to cancel before deletion
                record.write({'state': 'cancel'})
                self._delete_child_booking_records(
                    record.counter, record.booking_id)

                # Update parent booking state if needed
                remaining_lines = record.booking_id.room_line_ids - record
                if not remaining_lines:
                    record.booking_id.write({
                        'state': 'cancel'
                    })

        return super(RoomBookingLine, self).unlink()
