from datetime import timedelta, datetime
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError
from odoo.models import NewId
import logging

_logger = logging.getLogger(__name__)

class RoomBookingLine(models.Model):
    """Model that handles the room booking form"""
    _name = "room.booking.line"
    _description = "Hotel Folio Line"
    _rec_name = 'room_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    sequence = fields.Integer(
        string='Sequence', compute='_compute_sequence', store=True,tracking=True)

    

    @api.depends("booking_id.room_line_ids")
    def _compute_sequence(self):
        """Bulk assign sequence numbers – one DB write per booking."""
        for booking in self.mapped("booking_id"):
            lines = booking.room_line_ids.sorted("create_date")
            for i, line in enumerate(lines, start=1):
                line.sequence = i

    counter = fields.Integer(string="Counter", default=0,tracking=True)

    housekeeping_status = fields.Many2one(
        'housekeeping.status', string="Housekeeping Status", compute="_compute_room_statuses", store=False
    ,tracking=True)
    maintenance_status = fields.Many2one(
        'maintenance.status', string="Maintenance Status", compute="_compute_room_statuses", store=False
    ,tracking=True)
    housekeeping_staff_status = fields.Many2one(
        'housekeeping.staff.status', string="Housekeeping Staff Status", compute="_compute_room_statuses", store=False
    ,tracking=True)

    

    @api.depends("room_id")
    def _compute_room_statuses(self):
        for rec in self:
            room = rec.room_id
            rec.housekeeping_status = room.housekeeping_status.id if room else False
            rec.maintenance_status = room.maintenance_status.id if room else False
            rec.housekeeping_staff_status = (
                room.housekeeping_staff_status.id if room else False
            )

    hide_fields = fields.Boolean(string="Hide Fields", default=False,tracking=True)

    @tools.ormcache()
    def _set_default_uom_id(self):
        return self.env.ref('uom.product_uom_day')

    booking_id = fields.Many2one("room.booking", string="Booking",
                                 help="Indicates the Room",
                                 ondelete="cascade",tracking=True)

    state_ = fields.Selection([
        ('not_confirmed', 'Not Confirmed'),
        ('block', 'Block'),
        ('no_show', 'No Show'),
        ('confirmed', 'Confirmed'),
        ('check_in', 'Check In'),
        ('check_out', 'Check Out'),
        ('done', 'done'),
        ('cancel', 'Cancel'),
    ], default='not_confirmed', string="Status", compute='_compute_state', store=True,tracking=True)

    
    #Working Code 12/12/2024
    @api.depends('booking_id', 'booking_id.state', 'sequence')
    def _compute_state(self):
        for record in self:
            if record.booking_id.state == 'not_confirmed':
                record.state_ = 'not_confirmed'
                continue
            if not record.room_id:
                record.state_ = 'confirmed'
                continue
            if record.booking_id.state == 'block':
                record.state_ = 'block'
                continue
            # Search for a child booking with parent_booking_id matching the current booking

            # Step 1: Get all child bookings for the current booking_id
            child_bookings_ = self.env['room.booking'].search([
                ('parent_booking_id', '=', record.booking_id.id)
            ])
            if child_bookings_:
                # Step 2: Find a matching booking line under any of the child bookings
                matching_line = self.env['room.booking.line'].search([
                    ('booking_id', 'in', child_bookings_.ids),
                    ('counter', '=', record.counter)
                ], limit=1)
                # print('matching_',matching_line,matching_line.booking_id)

                child_bookings = self.env['room.booking'].search([
                    ('id', '=', matching_line.booking_id.id)
                ], limit=1)

                # print("compute called",child_bookings)
                # Assign the state of the child booking if found, else use the parent's state
                if child_bookings:
                    record.state_ = child_bookings.state
                    # print(child_bookings.id, child_bookings.state, "child")
                # else:
                #     record.state_ = 'not_confirmed'
                #     # print(child_booking.id, child_booking.state, "not child")
            else:
                if len(record.booking_id.room_line_ids) == 1:
                    if record.booking_id.state == 'block':
                        record.state_ = 'block'
                    
    
    
    hide_room_id = fields.Boolean(
        string='Hide Room Field', compute='_compute_hide_room_id',tracking=True)

    @api.depends('booking_id.state')
    def _compute_hide_room_id(self):
        for record in self:
            record.hide_room_id = record.booking_id.state == 'block'

    room_availability_result_id = fields.Many2one(
        'room.availability.result', string="Room Availability Result",
        readonly=True
    ,tracking=True)

    checkin_date = fields.Datetime(string="Check In",
                                   help="You can choose the date,"
                                        " Otherwise sets to current Date",
                                   required=True,tracking=True)
    checkout_date = fields.Datetime(string="Check Out",
                                    help="You can choose the date,"
                                         " Otherwise sets to current Date",
                                    required=True,tracking=True)

    related_hotel_room_type = fields.Many2one(
        related='booking_id.hotel_room_type',
        string="Related Room Type",
        store=True
    ,tracking=True)



    room_id = fields.Many2one(
        'hotel.room',
        string="Room",
        domain="[('room_type_name', '=', hotel_room_type), "
        "('id', 'not in', booked_room_ids), ('company_id', '=', current_company_id)]",
        help="Indicates the Room",tracking=True)

    @api.model
    def default_get(self, fields_list):
        defaults = super(RoomBookingLine, self).default_get(fields_list)
        defaults['current_company_id'] = self.env.company.id
        return defaults

    current_company_id = fields.Many2one('res.company', default=lambda self: self.env.company,tracking=True)

    @api.onchange('hotel_room_type', 'adult_count')
    def _onchange_room_type_or_pax(self):
        for line in self:
            print("102", line.hotel_room_type, line.adult_count)

    booked_room_ids = fields.Many2many(
        'hotel.room',
        compute='_compute_booked_room_ids',
        string='Booked Rooms',
        store=False
    ,tracking=True)

    

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
                    ('booking_id.state', 'in', ['confirmed','block','check_in']),
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
    ,tracking=True)

    

    @api.onchange('hotel_room_type')
    def _onchange_hotel_room_type(self):
        """Automatically filter room_id based on hotel_room_type."""
        parent_booking_id = self.booking_id.id
        # print(parent_booking_id, type(parent_booking_id))
        # numeric_parent_id = parent_booking_id.split('=')[-1].strip('>')
        if isinstance(parent_booking_id, NewId):
            parent_booking_id_str = str(parent_booking_id)
            if '_' in parent_booking_id_str:
                numeric_parent_id = int(parent_booking_id_str.split('_')[-1])
                parent_booking_ids = self.env['room.booking'].search(
                    [('parent_booking_id', '=', numeric_parent_id)]).mapped('id')
                room_booking_line_ids = self.env['room.booking.line'].search(
                    [('booking_id', 'in', parent_booking_ids),
                     ('counter', '=', self.counter)],
                    order='id asc'  # Sort in ascending order
                ).ids
                room_ids_count = len(room_booking_line_ids)
                # print(f"Room Booking Line IDs for room type: {room_booking_line_ids}")
        # Find the affected room booking line
        affected_line = self.booking_id.room_line_ids.filtered(
            lambda line: line.id == self.id)

        if affected_line:
            affected_line_str = str(affected_line.id)

            # Extract only the numeric part
            numeric_id = affected_line_str.split('=')[-1].strip('>')
            numeric_id = int(numeric_id.split('_')[-1])
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
                # Update all records with the new room_id
                recordset.write({
                    'hotel_room_type': self.hotel_room_type.id,
                    'related_hotel_room_type': self.hotel_room_type.id,
                })

            
        return {
            'domain': {
                'room_id': [
                    # ('status', '=', 'available'),
                    ('company_id', '=',self.env.company.id),
                    ('room_type_name', '=', self.hotel_room_type.id)
                ] if self.hotel_room_type else [('company_id', '=',self.env.company.id)]
            }
        }

    def _get_dynamic_room_domain(self):
        """Get dynamic domain for room_id based on hotel_room_type."""
        domain = [('status', '=', 'available')]
        if self.hotel_room_type:
            domain.append(('room_type_name', '=', self.hotel_room_type.id))
        return domain

    room_type = fields.Many2one('hotel.room', string="Room Type",tracking=True)

    room_type_name = fields.Many2one(
        'room.type', string="Room Type", related="room_id.room_type_name", readonly=True,tracking=True)

    adult_count = fields.Integer(string="Adults", readonly=True,tracking=True)
    child_count = fields.Integer(string="Children", related="booking_id.child_count", readonly=True,tracking=True)
    infant_count = fields.Integer(string="Infant", related="booking_id.infant_count", readonly=True,tracking=True)

    uom_qty = fields.Float(string="Duration",
                           compute='_compute_uom_qty',
                           inverse='_inverse_uom_qty',
                           help="The quantity converted into the UoM used by "
                                "the product",tracking=True)

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

    uom_id = fields.Many2one('uom.uom',
                             default=_set_default_uom_id,
                             string="Unit of Measure",
                             help="This will set the unit of measure used",
                             readonly=True,tracking=True)
    price_unit = fields.Float(related='room_id.list_price', string='Rent',
                              digits='Product Price',
                              help="The rent price of the selected room.",tracking=True)
    tax_ids = fields.Many2many('account.tax',
                               'hotel_room_order_line_taxes_rel',
                               'room_id', 'tax_id',
                               related='room_id.taxes_ids',
                               string='Taxes',
                               help="Default taxes used when selling the room.", domain=[('type_tax_use', '=', 'sale')],tracking=True)
    currency_id = fields.Many2one(string='Currency',
                                  related='booking_id.pricelist_id.currency_id', help='The currency used',tracking=True)
    price_subtotal = fields.Float(string="Subtotal",
                                  compute='_compute_price_subtotal',
                                  help="Total Price excluding Tax",
                                  store=True,tracking=True)
    price_tax = fields.Float(string="Total Tax",
                             compute='_compute_price_subtotal',
                             help="Tax Amount",
                             store=True,tracking=True)
    price_total = fields.Float(string="Total",
                               compute='_compute_price_subtotal',
                               help="Total Price including Tax",
                               store=True,tracking=True)
    state = fields.Selection(related='booking_id.state',
                             string="Order Status",
                             help=" Status of the Order",
                             copy=False,tracking=True)
    booking_line_visible = fields.Boolean(default=False,
                                          string="Booking Line Visible",
                                          help="If True, then Booking Line "
                                               "will be visible",tracking=True)

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
                                   help="Indicates if the room line is unassigned.",tracking=True)

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
                child_bookings.unlink()

        # Call the original unlink method to delete the current record
        return super(RoomBookingLine, self).unlink()

    def assign_room_manual(self, room_id):
        """Method to handle manual room assignments with proper context"""
        return self.with_context(skip_code_validation=True).write({
            'room_id': room_id,
        })

    @api.constrains('room_id')
    def _check_duplicate_room(self):
        for rec in self:
            if rec.booking_id:
                existing_room_ids = rec.booking_id.room_line_ids.filtered(
                    lambda line: line.id != rec.id).mapped('room_id.id')
                if rec.room_id.id in existing_room_ids:
                    raise ValidationError("This room is already assigned to the current booking. Please select a different room.")

    @api.onchange('room_id')
    def _onchange_room_id(self):
        """Update booking state based on room_id value and log changes."""
        # if not self.id:
        #     return
        if self.booking_id:
            existing_room_ids = self.booking_id.room_line_ids.filtered(lambda line: line.id != self.id).mapped('room_id.id')
            if self.room_id.id in existing_room_ids:
                raise ValidationError("This room is already assigned to the current booking. Please select a different room.") 
        if isinstance(self.id, NewId):
            id_str_room = str(self.id)
            if '_' in id_str_room:
                current_id = int(id_str_room.split('_')[-1])

            # # current_id = None  # Exclude current record from the search
            # current_id = int(self.id.split('_')[-1])
        else:
            current_id = self.id
        if not self.id or not self.room_id:
            return
        if current_id is not None:
            # checkin_date = self.checkin_date
            checkin_date = self.booking_id.checkin_date
            checkout_date = self.booking_id.checkout_date

            # Convert to datetime if they are strings
            if isinstance(checkin_date, str):
                checkin_date = datetime.strptime(checkin_date, "%Y-%m-%d %H:%M:%S")
            if isinstance(checkout_date, str):
                checkout_date = datetime.strptime(checkout_date, "%Y-%m-%d %H:%M:%S")

            conflicting_bookings = self.env['room.booking.line'].search([
                ('room_id', '=', self.room_id.id),
                ('booking_id.state', 'in', ['block', 'check_in']),
                # ('checkin_date', '<=', checkout_date),
                # ('checkout_date', '>=', checkin_date),
                '|', '|',
                '&', ('checkin_date', '<', checkout_date), ('checkout_date', '>', checkin_date),
                '&', ('checkin_date', '<=', checkin_date), ('checkout_date', '>=', checkout_date),
                '&', ('checkin_date', '>=', checkin_date), ('checkout_date', '<=', checkout_date),
                ('id', '!=', current_id)
            ])
            _logger.info(f"Conflicting Bookings {len(conflicting_bookings)} {conflicting_bookings}")

            if conflicting_bookings:
                raise ValidationError("This room is already assigned to another booking. Please select a different room.")
                return
        if self.booking_id:
            existing_room_ids = self.booking_id.room_line_ids.filtered(lambda line: line.id != self.id).mapped('room_id.id')
            _logger.info(f"EXISTING ROOM IDS {existing_room_ids}")
            if self.room_id.id in existing_room_ids:
                raise ValidationError("This room is already assigned to the current booking. Please select a different room.")

            if self.room_id is None:
                self.booking_id.state = 'confirmed'
                print(f"Room ID cleared. Booking state updated to 'not_confirmed' for booking ID {self.booking_id.id}.")
            else:
                # print("395", self.room_id, self.booking_id.room_line_ids,self.booking_id.id, self.counter, self.sequence)
                parent_booking_id = self.booking_id.id
                # print(parent_booking_id, type(parent_booking_id))
                # numeric_parent_id = parent_booking_id.split('=')[-1].strip('>')
                if isinstance(parent_booking_id, NewId):
                    parent_booking_id_str = str(parent_booking_id)
                    if '_' in parent_booking_id_str:
                        numeric_parent_id = int(parent_booking_id_str.split('_')[-1])
                        parent_booking_ids = self.env['room.booking'].search([('parent_booking_id', '=', numeric_parent_id)]).mapped('id')
                        room_booking_line_ids = self.env['room.booking.line'].search(
                            [('booking_id', 'in', parent_booking_ids),
                             ('counter', '=', self.counter)
                             ],
                            order='id asc'  # Sort in ascending order
                        ).ids
                        room_ids_count = len(room_booking_line_ids)
                        print(room_ids_count)
                        print(f"Room Booking Line IDs: {room_booking_line_ids}")
                # Find the affected room booking line
                affected_line = self.booking_id.room_line_ids.filtered(
                    lambda line: line.id == self.id)
                # print('459', affected_line)

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
                        print(f"Updating Room Booking Lines with IDs: {recordset.ids}, {self.sequence} ,{self.counter}")

                        # Update all records with the new room_id

                        recordset.write({
                            'room_id': self.room_id.id,
                            'sequence': self.sequence
                        })
                    # Step 2: Update records with a condition on 'room_id'
                    print("611",parent_booking_ids, self.room_id.id)
                    bookings = self.env['room.booking'].browse(parent_booking_ids)
                    # bookings = self.env['room.booking'].search([
                    #     ('parent_booking_id', 'in', parent_booking_ids),
                    #     # ('counter', '=', self.counter)
                    # ])
                    matching_line = self.env['room.booking.line'].search([
                        ('booking_id', 'in', parent_booking_ids),
                        ('counter', '=', self.counter)
                    ], limit=1)
                    # print('matching_',matching_line,matching_line.booking_id)

                    bookings = self.env['room.booking'].search([
                        ('id', '=', matching_line.booking_id.id)
                    ], limit=1)

                    # Step 2: Update the 'state' based on the condition
                    for booking in bookings:
                        if not self.room_id.id:
                            booking.write({'state': 'not_confirmed'})
                else:
                    print(
                        f"New room_line created with Room ID {self.room_id.id}.")

            # self.booking_id.state = 'confirmed'
            print(f"Room ID assigned. Booking state updated to 'confirmed' for booking ID {self.booking_id.id}.")
        

    @api.onchange('room_line_ids')
    def _onchange_room_lines(self):
        """Triggered when room lines are changed to adjust booking state."""
        for line in self.room_line_ids:
            if line.room_id is None:
                self.state = 'not_confirmed'
            else:
                child_booking = self.env['room.booking'].search([
                    ('parent_booking_id', '=', line.booking_id.id),
                    ('sequence', '=', line.sequence)
                ], limit=1)
                # Assign the state of the child booking if found, else use the parent's state
                if child_booking:
                    line.state_ = child_booking.state
                else:
                    line.state_ = 'not_confirmed'
                self.state_ = 'confirmed'
                # self.state = 'confirmed'
                # break

    
    # def update_adult_record(self,parent_booking,counter):
    #     # Update existing adult and child records with new room_id
    #     adults_to_update = self.env['reservation.adult'].search([
    #         ('reservation_id', '=', parent_booking),
    #         # ('room_sequence', '=', counter)
    #     ])
    #     adults_to_update.write({'room_id': self.room_id.id, 'room_sequence':counter})

    #     children_to_update = self.env['reservation.child'].search([
    #         ('reservation_id', '=', parent_booking),
    #         # ('room_sequence', '=', counter)
    #     ])
    #     children_to_update.write({'room_id': self.room_id.id, 'room_sequence':counter})

    #     infants_to_update = self.env['reservation.infant'].search([
    #         ('reservation_id', '=', parent_booking),
    #         # ('room_sequence', '=', counter)
    #     ])
    #     infants_to_update.write({'room_id': self.room_id.id,'room_sequence':counter})

    def update_adult_record(self, parent_booking, counter):
        [self.env[model].search([('reservation_id', '=', parent_booking)]).write({
            'room_id': self.room_id.id,
            'room_sequence': counter
        }) for model in ['reservation.adult', 'reservation.child', 'reservation.infant']]


    # def update_adult_record(self, parent_booking, counter):
    #     for model in ['reservation.adult', 'reservation.child', 'reservation.infant']:
    #         self.env[model].search([('reservation_id', '=', parent_booking)]).write({
    #             'room_id': self.room_id.id,
    #             'room_sequence': counter
    #         })

    def create_adult_record(self, parent_booking, new_booking, counter):
        ModelMap = {
            'reservation.adult': parent_booking.adult_count,
            'reservation.child': parent_booking.child_count,
            'reservation.infant': parent_booking.infant_count,
        }

        # Update room_id for matching sequence records under the parent booking
        for model in ModelMap:
            self.env[model].search([
                ('reservation_id', '=', parent_booking.id),
                ('room_sequence', '=', counter)
            ]).write({'room_id': self.room_id.id})

        # Create new records in new_booking based on parent_booking
        for model_name, count in ModelMap.items():
            parent_records = self.env[model_name].search([
                ('reservation_id', '=', parent_booking.id),
                ('room_sequence', '=', counter)
            ])
            for record in parent_records:
                existing = self.env[model_name].search([
                    ('reservation_id', '=', new_booking.id),
                    ('room_sequence', '=', counter),
                    ('first_name', '=', record.first_name),
                    ('last_name', '=', record.last_name)
                ])
                if not existing:
                    for _ in range(count):
                        self.env[model_name].sudo().create({
                            'reservation_id': new_booking.id,
                            'room_sequence': counter,
                            'first_name': record.first_name,
                            'last_name': record.last_name,
                            'profile': record.profile,
                            'nationality': record.nationality.id if record.nationality else False,
                            'birth_date': record.birth_date,
                            'passport_number': record.passport_number,
                            'id_number': record.id_number,
                            'visa_number': record.visa_number,
                            'id_type': record.id_type,
                            'phone_number': record.phone_number,
                            'relation': record.relation,
                            'room_type_id': self.hotel_room_type.id,
                            'room_id': self.room_id.id,
                        })
                else:
                    existing.write({'room_id': self.room_id.id})



    # def create_adult_record(self, parent_booking, new_booking, counter):
    #     # Fetch child bookings associated with the parent booking
    #     child_bookings = self.env['room.booking'].search(
    #         [('parent_booking_id', '=', parent_booking.id)], order='id')

    #     # Update existing adult and child records with new room_id
    #     adults_to_update = self.env['reservation.adult'].search([
    #         ('reservation_id', '=', parent_booking.id),
    #         ('room_sequence', '=', counter)
    #     ])
    #     adults_to_update.write({'room_id': self.room_id.id})

    #     children_to_update = self.env['reservation.child'].search([
    #         ('reservation_id', '=', parent_booking.id),
    #         ('room_sequence', '=', counter)
    #     ])
    #     children_to_update.write({'room_id': self.room_id.id})

    #     infants_to_update = self.env['reservation.infant'].search([
    #     ('reservation_id', '=', parent_booking.id),
    #     ('room_sequence', '=', counter)
    #     ])
    #     infants_to_update.write({'room_id': self.room_id.id})


    #     # Fetch adults from the parent booking with the same room sequence
    #     parent_adults = self.env['reservation.adult'].search([
    #         ('reservation_id', '=', parent_booking.id),
    #         ('room_sequence', '=', counter)
    #     ])
    #     # Fetch children from the parent booking with the same room sequence
    #     parent_children = self.env['reservation.child'].search([
    #         ('reservation_id', '=', parent_booking.id),
    #         ('room_sequence', '=', counter)
    #     ])

    #     parent_infants = self.env['reservation.infant'].search([
    #     ('reservation_id', '=', parent_booking.id),
    #     ('room_sequence', '=', counter)])


    #     # Handle adults
    #     for adult in parent_adults:
    #         # existing_adult = None
    #         # if len(child_bookings) > 0:
    #             # Ensure we only create unique records
    #         existing_adult = self.env['reservation.adult'].search([
    #             ('reservation_id', '=', new_booking.id),
    #             ('room_sequence', '=', counter),
    #             ('first_name', '=', adult.first_name),
    #             ('last_name', '=', adult.last_name)
    #         ])
            
    #         if not existing_adult:
    #             # adult_line_vals = []
    #             for i in range(parent_booking.adult_count):
    #             # Prepare adult record values
    #                 adult_line_vals = {
    #                     'reservation_id': new_booking.id,
    #                     'room_sequence': counter,
    #                     'first_name': adult.first_name,
    #                     'last_name': adult.last_name,
    #                     'last_name': adult.last_name,
    #                     'profile': adult.profile,
    #                     'nationality': adult.nationality.id if adult.nationality else False,
    #                     'birth_date': adult.birth_date,
    #                     'passport_number': adult.passport_number,
    #                     'id_number': adult.id_number,
    #                     'visa_number': adult.visa_number,
    #                     'id_type': adult.id_type,
    #                     'phone_number': adult.phone_number,
    #                     'relation': adult.relation,
    #                     'room_type_id': self.hotel_room_type.id,
    #                     'room_id': self.room_id.id,
    #                 }

    #                 # Create the adult record
    #                 self.env['reservation.adult'].sudo().create(adult_line_vals)
    #         else:
    #             existing_adult.write({'room_id': self.room_id.id})

    #     # Handle children
    #     for child in parent_children:
            
    #         existing_child = self.env['reservation.child'].search([
    #             ('reservation_id', '=', new_booking.id),
    #             ('room_sequence', '=', counter),
    #             ('first_name', '=', child.first_name),
    #             ('last_name', '=', child.last_name)
    #         ])

    #         if not existing_child:
    #             # Prepare child record values
    #             for i in range(parent_booking.child_count):
    #                 child_line_vals = {
    #                     'reservation_id': new_booking.id,
    #                     'room_sequence': counter,
    #                     'first_name': child.first_name,
    #                     'last_name': child.last_name,
    #                     'profile': adult.profile,
    #                     'nationality': adult.nationality.id if adult.nationality else False,
    #                     'birth_date': adult.birth_date,
    #                     'passport_number': adult.passport_number,
    #                     'id_number': adult.id_number,
    #                     'visa_number': adult.visa_number,
    #                     'id_type': adult.id_type,
    #                     'phone_number': adult.phone_number,
    #                     'relation': adult.relation,
    #                     'room_type_id': self.hotel_room_type.id,
    #                     'room_id': self.room_id.id,
    #                 }

    #                 # Create the child record
    #                 self.env['reservation.child'].sudo().create(child_line_vals)
    #                 # print(f"Created new child record for booking: {new_booking.id}, Room Sequence: {counter}")
    #         else:
    #             existing_child.write({'room_id': self.room_id.id})

    #     # Handle infants
    #     for infant in parent_infants:
    #         # existing_infant = None
    #         # if len(child_bookings>0):
    #         existing_infant = self.env['reservation.infant'].search([
    #             ('reservation_id', '=', new_booking.id),
    #             ('room_sequence', '=', counter),
    #             ('first_name', '=', infant.first_name),
    #             ('last_name', '=', infant.last_name)
    #         ])

    #         if not existing_infant:
    #             for i in range(parent_booking.infant_count):
    #                 infant_line_vals = {
    #                     'reservation_id': new_booking.id,
    #                     'room_sequence': counter,
    #                     'first_name': infant.first_name,
    #                     'last_name': infant.last_name,
    #                     'profile': infant.profile,
    #                     'nationality': infant.nationality.id if infant.nationality else False,
    #                     'birth_date': infant.birth_date,
    #                     'passport_number': infant.passport_number,
    #                     'id_number': infant.id_number,
    #                     'visa_number': infant.visa_number,
    #                     'id_type': infant.id_type,
    #                     'phone_number': infant.phone_number,
    #                     'relation': infant.relation,
    #                     'room_type_id': self.hotel_room_type.id,
    #                     'room_id': self.room_id.id,
    #                 }
    #                 self.env['reservation.infant'].sudo().create(infant_line_vals)
    #                 print(f"Created new infant record for booking: {parent_booking.id}, Room Sequence: {counter}")
    #         else:
    #             existing_infant.write({'room_id': self.room_id.id})
    



    # def write(self, vals):
    #     record_to_delete, records_to_update, parent_bookings_to_update = [], [], []
    #     processed_parent_bookings = set()
    #     for record in self:
    #         if record.booking_id:
    #             # Fetch the booking record to get the parent_booking_id
    #             booking_record = self.env['room.booking'].browse(record.booking_id.id)
    #             parent_booking_id = booking_record.parent_booking_id
    #             counter_write = 0
    #             if parent_booking_id:
    #                 # Fetch the room_id from the updated vals or fallback to the current record
    #                 room_id = vals.get('room_id') or record.room_id.id
    #                 if room_id:
    #                     # Ensure parent_booking_id is an integer and not a recordset
    #                     parent_booking_id_int = parent_booking_id.id
    #                     # Search for matching room.booking.line records
    #                     booking_line_records = self.env['room.booking.line'].search([
    #                         ('booking_id', '=', parent_booking_id_int),
    #                         ('room_id', '=', room_id)
    #                     ])

    #                     # Process the counter values if matching lines are found
    #                     if booking_line_records:
    #                         # print(f"Found {len(booking_line_records)} records matching the criteria.")
    #                         for line in booking_line_records:
    #                             counter_write = line.counter
    #                             # print(f"Room Booking Line ID: {line.id}, Counter: {line.counter}")
    #         parent_booking = record.booking_id
    #         # Retrieve room bookings associated with the parent_booking_id
    #         room_bookings = self.env['room.booking'].search([('parent_booking_id', '=', parent_booking.id)])
    #         # print(f"Room bookings for parent_booking_id {parent_booking.id}: {room_bookings}")
    #         if 'room_id' in vals and 'id' in vals:
    #             room_id = vals.get("room_id")
    #             record_id = vals.get("id")

    #             # Ensure the record has a valid database ID
    #             if isinstance(record_id, list):
    #                 child_booking = self.env['room.booking.line'].search([
    #                     # Search for records with IDs in the list
    #                     ('id', 'in', record_id),
    #                     # ('counter', '=', counter)  # Include the counter in the search criteria
    #                 ])
    #                 if child_booking.exists():
    #                     [super(RoomBookingLine, child).write({'room_id': room_id}) for child in child_booking]
    #                     return
    #                 else:
    #                     print(f"No Room Booking Line found with ID: {record_id}")

    #                 # if child_booking.exists():
    #                 #     for child in child_booking:
    #                 #         # print(f"Updating Room ID for Room Booking Line ID: {child}")
    #                 #         super(RoomBookingLine, child).write(
    #                 #             {'room_id': room_id})
    #                 #     return
    #                 # else:
    #                 #     print(f"No Room Booking Line found with ID: {record_id}")
    #             else:
    #                 print(f"Skipping write operation for non-integer ID: {record_id}")

    #         if 'hotel_room_type' in vals:
    #             room_type = vals.get("hotel_room_type")
    #             # print('536', room_type)
    #             related_room_type = vals.get("related_hotel_room_type")
    #             super(RoomBookingLine, record).write({'hotel_room_type': room_type, 'related_hotel_room_type': room_type, 'room_id': False})

    #         if 'room_id' in vals and 'id' not in vals:
    #             room_id = vals.get('room_id')
    #             new_room_id = vals['room_id']
    #             counter = vals.get('counter')
    #             old_room_id = record.room_id
    #             # print("477",old_room_id.id)
    #             if room_id:
    #                 super(RoomBookingLine, record).write({'room_id': new_room_id, 'state': 'block'})
    #                 # print(f"Updating room_id for record {record.id} to {room_id}")

    #             if new_room_id:
    #                 counter = vals.get('counter')

    #                 # Update current record's room_id
    #                 # print('running super write ethod', counter)
    #                 super(RoomBookingLine, record).write({'room_id': new_room_id, 'state': 'block'})

    #                 # Check and update child bookings
    #                 for child_booking in room_bookings:
    #                     if not child_booking.room_line_ids:
    #                         child_booking.sudo().write({
    #                             'state': 'block',  # Update state to block for reassigned room
    #                             'room_line_ids': [(0, 0, {
    #                                 'room_id': new_room_id,
    #                                 # 'checkin_date': record.checkin_date,
    #                                 'checkin_date': parent_booking.checkin_date,
    #                                 # 'checkout_date': record.checkout_date,
    #                                 'checkout_date': parent_booking.checkout_date,
    #                                 'uom_qty': 1,
    #                                 'adult_count': record.adult_count,
    #                                 'child_count': record.child_count,
    #                                 'infant_count': record.infant_count,
    #                                 'hotel_room_type': record.hotel_room_type.id,
    #                                 'counter': counter
    #                             })]
    #                         })
                            

    #             # If room_id is not provided, move to 'not_confirmed' state
    #             if not room_id:
    #                 new_booking_vals = {
    #                     'parent_booking_id': parent_booking.id,
    #                     'parent_booking_name': parent_booking.name,
    #                     'partner_id': parent_booking.partner_id.id,
    #                     'reference_contact_': parent_booking.reference_contact_,
    #                     'hotel_room_type': parent_booking.hotel_room_type.id,
    #                     'group_booking': parent_booking.group_booking.id,
    #                     'room_line_ids': [],  # No room_line_ids since room_id is unlinked
    #                     # 'checkin_date': record.checkin_date,
    #                     'checkin_date': parent_booking.checkin_date,
    #                     # 'checkout_date': record.checkout_date,
    #                     'checkout_date': parent_booking.checkout_date,
    #                     'state': 'not_confirmed',  # Ensure state is set to 'not_confirmed'
    #                     'is_room_line_readonly': False,
    #                     'is_offline_search': False
    #                 }

    #                 parent_bookings_to_update.append((parent_booking, {'state': 'confirmed'}))
    #                 # record.write({'state_': 'confirmed'})
    #                 continue

    #             # Ensure the booking is confirmed before assigning a room
    #             if parent_booking.state != 'confirmed' and len(parent_booking.room_line_ids) > 1:
    #                 raise UserError(
    #                     "Please confirm the booking before assigning a room.")

    #             # Move to 'block' state if only one entry exists
    #             if len(parent_booking.room_line_ids) == 1:
    #                 parent_bookings_to_update.append((parent_booking, {
    #                     'state': 'block',
    #                     'hotel_room_type': record.hotel_room_type.id,
    #                 }))
    #                 # print(f"Booking {parent_booking.id} moved to 'block' state as it has only one room line.")
    #             else:
    #                 counter = vals.get('counter')
    #                 booking_record = self.env['room.booking'].browse(record.booking_id.id)
    #                 parent_booking_id = booking_record.parent_booking_id

    #                 if parent_booking_id:
    #                     # Fetch the room_id from the updated vals or fallback to the current record
    #                     room_id = vals.get('room_id') or record.room_id.id
    #                     if room_id:
    #                         # Ensure parent_booking_id is an integer and not a recordset
    #                         parent_booking_id_int = parent_booking_id.id
    #                         # Search for matching room.booking.line records
    #                         booking_line_records = self.env['room.booking.line'].search([
    #                             ('booking_id', '=', parent_booking_id_int),
    #                             ('room_id', '=', room_id)
    #                         ])

    #                         # Process the counter values if matching lines are found
    #                         if booking_line_records:
    #                             print(
    #                                 f"Found {len(booking_line_records)} records matching the criteria.")
    #                             for line in booking_line_records:
    #                                 counter = line.counter
    #                                 # print(f"Room Booking Line ID: {line.id}, Counter: {line.counter}")
    #                 # Handle unassigned lines and create a new child booking if needed
    #                 if record.is_unassigned and parent_booking.state == 'confirmed':
    #                     if parent_booking.id in processed_parent_bookings:
    #                         continue  # Skip if this parent booking is already processed

    #                     unassigned_lines = parent_booking.room_line_ids.filtered(lambda line: line.is_unassigned)
    #                     if len(unassigned_lines) == 1:
    #                         # Only one room left to assign, update the existing record
    #                         last_unassigned_line = unassigned_lines[0]
    #                         room_id = vals.get('room_id') or last_unassigned_line.room_id.id

    #                         # Update the last unassigned line with the room_id and mark as assigned
    #                         records_to_update.append((last_unassigned_line, {
    #                             'is_unassigned': False,
    #                             'room_id': room_id
    #                         }))

    #                         # Update the parent booking state to 'block'
    #                         parent_bookings_to_update.append((parent_booking, {
    #                             'state': 'block',
    #                             'parent_booking_id': parent_booking.id,
    #                             'parent_booking_name': parent_booking.name,
    #                         }))

                            
    #                         print(f"Updated parent booking {parent_booking.id}, {self.counter} with the last pending room assignment.")
    #                         self.update_adult_record(parent_booking.id,self.counter)
    #                     else:

    #                         # print("this creates the final booking here", len(booking_line_records), record.is_unassigned)
    #                         new_booking_vals = {
    #                             'parent_booking_id': parent_booking.id,
    #                             'parent_booking_name': parent_booking.name,
    #                             'partner_id': parent_booking.partner_id.id,
    #                             'nationality': parent_booking.nationality.id,
    #                             'source_of_business': parent_booking.source_of_business.id,
    #                             'meal_pattern': parent_booking.meal_pattern.id,
    #                             'market_segment': parent_booking.market_segment.id,
    #                             'rate_code': parent_booking.rate_code.id,
    #                             'reference_contact_': parent_booking.reference_contact_,
    #                             # 'hotel_room_type': parent_booking.hotel_room_type.id,
    #                             'hotel_room_type': record.hotel_room_type.id,
    #                             'group_booking': parent_booking.group_booking.id,
    #                             'house_use': parent_booking.house_use,
    #                             'complementary': parent_booking.complementary,
    #                             'vip': parent_booking.vip,
    #                             'room_count':1,
    #                             'adult_count':parent_booking.adult_count,
    #                             'child_count': parent_booking.child_count,
    #                             'infant_count': parent_booking.infant_count,
    #                             'complementary_codes': parent_booking.complementary_codes.id,
    #                             'house_use_codes': parent_booking.house_use_codes.id,
    #                             'vip_code': parent_booking.vip_code.id,
    #                             'notes': parent_booking.notes,
    #                             # 'show_in_tree':True,
    #                             'room_line_ids': [(0, 0, {
    #                                 # 'sequence': record.sequence,
    #                                 'sequence': counter,
    #                                 'room_id': room_id,
    #                                 'checkin_date': parent_booking.checkin_date,
    #                                 'checkout_date': parent_booking.checkout_date,
    #                                 'uom_qty': 1,
    #                                 'adult_count': record.adult_count,
    #                                 'child_count': record.child_count,
    #                                 'infant_count': record.infant_count,
    #                                 'is_unassigned': False,
    #                                 'hotel_room_type': record.hotel_room_type.id,
    #                                 'counter': counter,
    #                             })],
    #                             'posting_item_ids': [(0, 0, {
    #                                 'posting_item_id': posting_item.posting_item_id.id,
    #                                 'item_code': posting_item.item_code,
    #                                 'description': posting_item.description,
    #                                 'posting_item_selection': posting_item.posting_item_selection,
    #                                 'from_date': posting_item.from_date,
    #                                 'to_date': posting_item.to_date,
    #                                 'default_value': posting_item.default_value,
    #                             }) for posting_item in parent_booking.posting_item_ids],
    #                             # 'posting_item_ids': [(6, 0, parent_booking.posting_item_ids.ids)],
    #                             'checkin_date': parent_booking.checkin_date,
    #                             'checkout_date': parent_booking.checkout_date,
    #                             'state': 'block',
    #                             'group_booking': parent_booking.group_booking.id,
    #                             'is_offline_search': False,
    #                             # 'is_grp_company': parent_booking.is_grp_company,
    #                             'is_agent': parent_booking.is_agent,
    #                             'no_of_nights': parent_booking.no_of_nights,
    #                             'room_price': parent_booking.room_price,
    #                             'use_price': parent_booking.use_price,
    #                             'room_discount':parent_booking.room_discount,
    #                             'room_is_amount':parent_booking.room_is_amount,
    #                             'room_amount_selection':parent_booking.room_amount_selection,
    #                             'room_is_percentage':parent_booking.room_is_percentage,
    #                             'use_meal_price': parent_booking.use_meal_price,
    #                             'meal_price': parent_booking.meal_price,
    #                             'meal_child_price': parent_booking.meal_child_price,
    #                             'meal_discount':parent_booking.meal_discount,
    #                             'meal_amount_selection': parent_booking.meal_amount_selection,
    #                             'meal_is_amount':parent_booking.meal_is_amount,
    #                             'meal_is_percentage':parent_booking.meal_is_percentage,
    #                             'payment_type': parent_booking.payment_type,
    #                             # 'is_room_line_readonly': True,
    #                         }

    #                         # # new_booking_vals['adult_ids'] = adult_lines + child_lines
    #                         # new_booking_vals['adult_ids'] = adult_lines

    #                         # Create the new child booking
    #                         new_id_booking =self.env['room.booking'].create(new_booking_vals)
                            
    #                           # Ensure 'counter' field exists in 'room.booking'

    #                         # Search for room.booking.line records with the same counter
    #                         lines_to_delete = self.env['room.booking.line'].search([('counter', '=', self.counter),  ('booking_id', '=', parent_booking.id)])
    #                         record_to_delete.append(lines_to_delete)
    #                         # Delete the records
                            
    #                         # if counter is None:
    #                         #     counter = 1  # or some default fallback
    #                         self.create_adult_record(parent_booking,new_id_booking, self.counter)

    #                     # Mark the unassigned line as processed
    #                     records_to_update.append(
    #                         (record, {'is_unassigned': False, 'room_id': room_id}))
    #                     processed_parent_bookings.add(parent_booking.id)
    #         else:
    #             if 'checkout_date' in vals and counter_write != 0:
    #                 super(RoomBookingLine, record).write(
    #                     {'counter': counter_write})

    #             # No room_id provided; leave the line unchanged
    #             # print(f"No room_id provided for line {record.id}. Keeping it unchanged.")

    #     # Perform all pending updates
    #     for record, record_vals in records_to_update:
    #         # print(f"Updating record: {record}, values: {record_vals}")
    #         super(RoomBookingLine, record).write(record_vals)

    #     for booking, booking_vals in parent_bookings_to_update:
    #         # print(f"Updating parent booking: {booking}, values: {booking_vals}")
    #         booking.write(booking_vals)
        
        
    #     # Call super to finalize other updates
    #     result = super(RoomBookingLine, self).write(vals)
            
    #     lines_to_update = None
    #     counter_line = 0
    #     booking_id_check = 0
    #     if 'room_id' in vals:
    #         for line in self:
    #             counter_line = line.counter
    #             booking_id_check = line.booking_id.id

    #             # Ensure we have a booking and a sequence
    #             if line.booking_id and line.counter and line.room_id:
    #                 # Update Adults
    #                 adults_to_update = self.env['reservation.adult'].search([
    #                     ('reservation_id', '=', line.booking_id.id),
    #                     ('room_sequence', '=', line.counter)
    #                 ])
    #                 if adults_to_update:
    #                     adults_to_update.write({'room_id': line.room_id.id})

    #                 # Update Children
    #                 children_to_update = self.env['reservation.child'].search([
    #                     ('reservation_id', '=', line.booking_id.id),
    #                     ('room_sequence', '=', line.counter)
    #                 ])
    #                 if children_to_update:
    #                     children_to_update.write({'room_id': line.room_id.id})

    #                 # Update Children
    #                 infants_to_update = self.env['reservation.infant'].search([
    #                         ('reservation_id', '=', line.booking_id.id),
    #                         ('room_sequence', '=', line.counter)
    #                 ])
    #                 if infants_to_update:
    #                     infants_to_update.write({'room_id': line.room_id.id})


    #     # print("1203 ",counter_line,len(self.ids))
    #     if counter_line != 0 and booking_id_check !=0:
    #         lines_to_check = self.env['room.booking.line'].search([
    #             ('booking_id', '=', booking_id_check),

    #         ])
    #         if counter_line < len(lines_to_check):
    #             # update child records using room_id-
    #             child_booking_ids = self.env['room.booking'].search([('parent_booking_id', '=', booking_id_check)]).ids
    #             lines_to_update = self.env['room.booking.line'].search([
    #                 ('booking_id', 'in', child_booking_ids),
    #                 ('counter', '=', counter_line)
    #             ])
    #             # super(RoomBookingLine, self).write(vals)
    #             result = lines_to_update.write({'room_id': line.room_id.id})
        
    #     for line in record_to_delete:
    #         line_booking_obj = line.booking_id
    #         line_booking = line.booking_id.id
    #         line_counter = line.counter
    #         super(RoomBookingLine, line).unlink()
    #         adult_lines = self.env['reservation.adult'].search([
    #                 # Match parent booking ID
    #                 ('reservation_id', '=', line_booking),
    #                 ('room_sequence', '=', line_counter)  # Exclude matching counter value
    #             ], order='room_sequence asc')
    #         adult_lines.unlink()
    #         child_lines = self.env['reservation.child'].search([
    #                 # Match parent booking ID
    #                 ('reservation_id', '=', line_booking),
    #                 ('room_sequence', '=', line_counter)  # Exclude matching counter value
    #             ], order='room_sequence asc')
    #         child_lines.unlink()
    #         infant_lines = self.env['reservation.infant'].search([
    #                 # Match parent booking ID
    #                 ('reservation_id', '=', line_booking),
    #                 ('room_sequence', '=', line_counter)  # Exclude matching counter value
    #             ], order='room_sequence asc')
    #         infant_lines.unlink()

    #         if len(line_booking_obj.room_line_ids) > 0:
    #                 line_booking_obj.write({'room_count': len(line_booking_obj.room_line_ids)})
            
            
    #     return result

    


    def write(self, vals):
        _logger.info("Starting write method for RoomBookingLine with vals: %s", vals)
        
        record_to_delete, records_to_update, parent_bookings_to_update = [], [], []
        processed_parent_bookings = set()
        record_counter = 0
        for record in self:
            record_counter += 1
            if_start_time = datetime.now().time()
            _logger.info("---Processing record ID: %s", record)
            _logger.info("Processing record ID: %s", record.id)
            
            if record.booking_id:
                _logger.info("Record has booking_id: %s", record.booking_id.id)
                
                # Fetch the booking record to get the parent_booking_id
                booking_record = self.env['room.booking'].browse(record.booking_id.id)
                parent_booking_id = booking_record.parent_booking_id
                counter_write = 0
                
                if parent_booking_id:
                    _logger.info("Found parent_booking_id: %s", parent_booking_id.id)
                    
                    room_id = vals.get('room_id') or record.room_id.id
                    if room_id:
                        parent_booking_id_int = parent_booking_id.id
                        booking_line_records = self.env['room.booking.line'].search([
                            ('booking_id', '=', parent_booking_id_int),
                            ('room_id', '=', room_id)
                        ])

                        if booking_line_records:
                            _logger.info("Found %d booking_line_records matching criteria", len(booking_line_records))
                            for line in booking_line_records:
                                counter_write = line.counter
                                _logger.info("Room Booking Line ID: %s, Counter: %s", line.id, line.counter)

            parent_booking = record.booking_id
            room_bookings = self.env['room.booking'].search([('parent_booking_id', '=', parent_booking.id)])
            _logger.info("Found %d room_bookings for parent_booking_id %s", len(room_bookings), parent_booking.id)

            if 'room_id' in vals and 'id' in vals:
                room_id = vals.get("room_id")
                record_id = vals.get("id")
                _logger.info("Processing room_id and id in vals - room_id: %s, record_id: %s", room_id, record_id)

                if isinstance(record_id, list):
                    child_booking = self.env['room.booking.line'].search([
                        ('id', 'in', record_id),
                    ])
                    
                    if child_booking.exists():
                        _logger.info("Found %d child bookings to update", len(child_booking))
                        [super(RoomBookingLine, child).write({'room_id': room_id}) for child in child_booking]
                        return
                    else:
                        _logger.warning("No Room Booking Line found with ID: %s", record_id)
                else:
                    _logger.warning("Skipping write operation for non-integer ID: %s", record_id)

            if 'hotel_room_type' in vals:
                room_type = vals.get("hotel_room_type")
                _logger.info("Updating hotel_room_type to: %s", room_type)
                super(RoomBookingLine, record).write({'hotel_room_type': room_type, 'related_hotel_room_type': room_type, 'room_id': False})

            if 'room_id' in vals and 'id' not in vals:
                room_id = vals.get('room_id')
                new_room_id = vals['room_id']
                counter = vals.get('counter')
                old_room_id = record.room_id
                _logger.info("Processing room_id update - new_room_id: %s, counter: %s, old_room_id: %s", new_room_id, counter, old_room_id.id if old_room_id else None)

                if room_id:
                    super(RoomBookingLine, record).write({'room_id': new_room_id, 'state': 'block'})
                    _logger.info("Updated room_id for record %s to %s", record.id, room_id)

                if new_room_id:
                    counter = vals.get('counter')
                    super(RoomBookingLine, record).write({'room_id': new_room_id, 'state': 'block'})
                    _logger.info("Running super write method with counter: %s", counter)

                    for child_booking in room_bookings:
                        if not child_booking.room_line_ids:
                            _logger.info("Creating new room_line_ids for child_booking %s", child_booking.id)
                            child_booking.sudo().write({
                                'state': 'block',
                                'room_line_ids': [(0, 0, {
                                    'room_id': new_room_id,
                                    'checkin_date': parent_booking.checkin_date,
                                    'checkout_date': parent_booking.checkout_date,
                                    'uom_qty': 1,
                                    'adult_count': record.adult_count,
                                    'child_count': record.child_count,
                                    'infant_count': record.infant_count,
                                    'hotel_room_type': record.hotel_room_type.id,
                                    'counter': counter
                                })]
                            })

                if not room_id:
                    _logger.info("No room_id provided, moving to 'not_confirmed' state")
                    new_booking_vals = {
                        'parent_booking_id': parent_booking.id,
                        'parent_booking_name': parent_booking.name,
                        'partner_id': parent_booking.partner_id.id,
                        'reference_contact_': parent_booking.reference_contact_,
                        'hotel_room_type': parent_booking.hotel_room_type.id,
                        'group_booking': parent_booking.group_booking.id,
                        'room_line_ids': [],
                        'checkin_date': parent_booking.checkin_date,
                        'checkout_date': parent_booking.checkout_date,
                        'state': 'not_confirmed',
                        'is_room_line_readonly': False,
                        'is_offline_search': False
                    }

                    parent_bookings_to_update.append((parent_booking, {'state': 'confirmed'}))
                    continue

                if parent_booking.state != 'confirmed' and len(parent_booking.room_line_ids) > 1:
                    _logger.error("Booking not confirmed before assigning room")
                    raise UserError("Please confirm the booking before assigning a room.")

                if len(parent_booking.room_line_ids) == 1:
                    _logger.info("Booking %s has only one room line, moving to 'block' state", parent_booking.id)
                    parent_bookings_to_update.append((parent_booking, {
                        'state': 'block',
                        'hotel_room_type': record.hotel_room_type.id,
                    }))
                else:
                    counter = vals.get('counter')
                    booking_record = self.env['room.booking'].browse(record.booking_id.id)
                    parent_booking_id = booking_record.parent_booking_id

                    if parent_booking_id:
                        room_id = vals.get('room_id') or record.room_id.id
                        if room_id:
                            parent_booking_id_int = parent_booking_id.id
                            booking_line_records = self.env['room.booking.line'].search([
                                ('booking_id', '=', parent_booking_id_int),
                                ('room_id', '=', room_id)
                            ])

                            if booking_line_records:
                                _logger.info("Found %d booking_line_records matching criteria", len(booking_line_records))
                                for line in booking_line_records:
                                    counter = line.counter
                                    _logger.info("Room Booking Line ID: %s, Counter: %s", line.id, line.counter)

                    if record.is_unassigned and parent_booking.state == 'confirmed':
                        if parent_booking.id in processed_parent_bookings:
                            continue

                        unassigned_lines = parent_booking.room_line_ids.filtered(lambda line: line.is_unassigned)
                        if len(unassigned_lines) == 1:
                            _logger.info("Only one unassigned line left for booking %s", parent_booking.id)
                            last_unassigned_line = unassigned_lines[0]
                            room_id = vals.get('room_id') or last_unassigned_line.room_id.id

                            records_to_update.append((last_unassigned_line, {
                                'is_unassigned': False,
                                'room_id': room_id
                            }))

                            parent_bookings_to_update.append((parent_booking, {
                                'state': 'block',
                                'parent_booking_id': parent_booking.id,
                                'parent_booking_name': parent_booking.name,
                            }))

                            _logger.info("Updated parent booking %s with last pending room assignment", parent_booking.id)
                            self.update_adult_record(parent_booking.id, self.counter)
                        else:
                            else_start_time = datetime.now().time()
                            print("In ELse Start Time", else_start_time, f"Record Counter: {record_counter}")
                            _logger.info("Creating new child booking for parent_booking %s", parent_booking.id)
                            new_booking_vals = {
                                'parent_booking_id': parent_booking.id,
                                'parent_booking_name': parent_booking.name,
                                'partner_id': parent_booking.partner_id.id,
                                'nationality': parent_booking.nationality.id,
                                'source_of_business': parent_booking.source_of_business.id,
                                'meal_pattern': parent_booking.meal_pattern.id,
                                'market_segment': parent_booking.market_segment.id,
                                'rate_code': parent_booking.rate_code.id,
                                'reference_contact_': parent_booking.reference_contact_,
                                'hotel_room_type': record.hotel_room_type.id,
                                'group_booking': parent_booking.group_booking.id,
                                'house_use': parent_booking.house_use,
                                'complementary': parent_booking.complementary,
                                'vip': parent_booking.vip,
                                'room_count': 1,
                                'adult_count': parent_booking.adult_count,
                                'child_count': parent_booking.child_count,
                                'infant_count': parent_booking.infant_count,
                                'complementary_codes': parent_booking.complementary_codes.id,
                                'house_use_codes': parent_booking.house_use_codes.id,
                                'vip_code': parent_booking.vip_code.id,
                                'notes': parent_booking.notes,
                                'room_line_ids': [(0, 0, {
                                    'sequence': counter,
                                    'room_id': room_id,
                                    'checkin_date': parent_booking.checkin_date,
                                    'checkout_date': parent_booking.checkout_date,
                                    'uom_qty': 1,
                                    'adult_count': record.adult_count,
                                    'child_count': record.child_count,
                                    'infant_count': record.infant_count,
                                    'is_unassigned': False,
                                    'hotel_room_type': record.hotel_room_type.id,
                                    'counter': counter,
                                })],
                                'posting_item_ids': [(0, 0, {
                                    'posting_item_id': posting_item.posting_item_id.id,
                                    'item_code': posting_item.item_code,
                                    'description': posting_item.description,
                                    'posting_item_selection': posting_item.posting_item_selection,
                                    'from_date': posting_item.from_date,
                                    'to_date': posting_item.to_date,
                                    'default_value': posting_item.default_value,
                                }) for posting_item in parent_booking.posting_item_ids],
                                'checkin_date': parent_booking.checkin_date,
                                'checkout_date': parent_booking.checkout_date,
                                'state': 'block',
                                'group_booking': parent_booking.group_booking.id,
                                'is_offline_search': False,
                                'is_agent': parent_booking.is_agent,
                                'no_of_nights': parent_booking.no_of_nights,
                                'room_price': parent_booking.room_price,
                                'use_price': parent_booking.use_price,
                                'room_discount': parent_booking.room_discount,
                                'room_is_amount': parent_booking.room_is_amount,
                                'room_amount_selection': parent_booking.room_amount_selection,
                                'room_is_percentage': parent_booking.room_is_percentage,
                                'use_meal_price': parent_booking.use_meal_price,
                                'meal_price': parent_booking.meal_price,
                                'meal_child_price': parent_booking.meal_child_price,
                                'meal_discount': parent_booking.meal_discount,
                                'meal_amount_selection': parent_booking.meal_amount_selection,
                                'meal_is_amount': parent_booking.meal_is_amount,
                                'meal_is_percentage': parent_booking.meal_is_percentage,
                                'payment_type': parent_booking.payment_type,
                            }

                            new_id_booking = self.env['room.booking'].create(new_booking_vals)
                            _logger.info("Created new booking with ID: %s", new_id_booking.id)
                            
                            lines_to_delete = self.env['room.booking.line'].search([
                                ('counter', '=', self.counter),
                                ('booking_id', '=', parent_booking.id)
                            ])
                            record_to_delete.append(lines_to_delete)
                            self.create_adult_record(parent_booking, new_id_booking, self.counter)
                            else_end_time = datetime.now().time()
                            # print("In ELse Time Taken", else_end_time - else_start_time)
                        records_to_update.append((record, {'is_unassigned': False, 'room_id': room_id}))
                        processed_parent_bookings.add(parent_booking.id)
            else:
                if 'checkout_date' in vals and counter_write != 0:
                    _logger.info("Updating checkout_date with counter_write: %s", counter_write)
                    super(RoomBookingLine, record).write({'counter': counter_write})

        # Perform all pending updates
        for record, record_vals in records_to_update:
            _logger.info("Updating record %s with values: %s", record.id, record_vals)
            super(RoomBookingLine, record).write(record_vals)

        for booking, booking_vals in parent_bookings_to_update:
            _logger.info("Updating parent booking %s with values: %s", booking.id, booking_vals)
            booking.write(booking_vals)

        # Call super to finalize other updates
        result = super(RoomBookingLine, self).write(vals)
        _logger.info("Super write method completed with result: %s", result)

        lines_to_update = None
        counter_line = 0
        booking_id_check = 0
        
        if 'room_id' in vals:
            for line in self:
                counter_line = line.counter
                booking_id_check = line.booking_id.id
                _logger.info("Processing room_id update for line - counter_line: %s, booking_id_check: %s", counter_line, booking_id_check)

                if line.booking_id and line.counter and line.room_id:
                    adults_to_update = self.env['reservation.adult'].search([
                        ('reservation_id', '=', line.booking_id.id),
                        ('room_sequence', '=', line.counter)
                    ])
                    if adults_to_update:
                        _logger.info("Updating %d adult records", len(adults_to_update))
                        adults_to_update.write({'room_id': line.room_id.id})

                    children_to_update = self.env['reservation.child'].search([
                        ('reservation_id', '=', line.booking_id.id),
                        ('room_sequence', '=', line.counter)
                    ])
                    if children_to_update:
                        _logger.info("Updating %d child records", len(children_to_update))
                        children_to_update.write({'room_id': line.room_id.id})

                    infants_to_update = self.env['reservation.infant'].search([
                        ('reservation_id', '=', line.booking_id.id),
                        ('room_sequence', '=', line.counter)
                    ])
                    if infants_to_update:
                        _logger.info("Updating %d infant records", len(infants_to_update))
                        infants_to_update.write({'room_id': line.room_id.id})

        if counter_line != 0 and booking_id_check != 0:
            _logger.info("Checking for lines to update - counter_line: %s, booking_id_check: %s", counter_line, booking_id_check)
            lines_to_check = self.env['room.booking.line'].search([
                ('booking_id', '=', booking_id_check),
            ])
            
            if counter_line < len(lines_to_check):
                _logger.info("Updating child records with room_id")
                child_booking_ids = self.env['room.booking'].search([('parent_booking_id', '=', booking_id_check)]).ids
                lines_to_update = self.env['room.booking.line'].search([
                    ('booking_id', 'in', child_booking_ids),
                    ('counter', '=', counter_line)
                ])
                result = lines_to_update.write({'room_id': line.room_id.id})

        for line in record_to_delete:
            _logger.info("Processing record deletion for line: %s", line)
            line_booking_obj = line.booking_id
            line_booking = line.booking_id.id
            line_counter = line.counter
            
            super(RoomBookingLine, line).unlink()
            _logger.info("Deleted room booking line %s", line.id)

            adult_lines = self.env['reservation.adult'].search([
                ('reservation_id', '=', line_booking),
                ('room_sequence', '=', line_counter)
            ], order='room_sequence asc')
            adult_lines.unlink()
            _logger.info("Deleted %d adult records", len(adult_lines))

            child_lines = self.env['reservation.child'].search([
                ('reservation_id', '=', line_booking),
                ('room_sequence', '=', line_counter)
            ], order='room_sequence asc')
            child_lines.unlink()
            _logger.info("Deleted %d child records", len(child_lines))

            infant_lines = self.env['reservation.infant'].search([
                ('reservation_id', '=', line_booking),
                ('room_sequence', '=', line_counter)
            ], order='room_sequence asc')
            infant_lines.unlink()
            _logger.info("Deleted %d infant records", len(infant_lines))

            if len(line_booking_obj.room_line_ids) > 0:
                _logger.info("Updating room_count for booking %s to %d", line_booking_obj.id, len(line_booking_obj.room_line_ids))
                line_booking_obj.write({'room_count': len(line_booking_obj.room_line_ids)})

        _logger.info("Write method completed successfully")
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

    room_forecast_ids = fields.Many2many(
        'room.rate.forecast',
        'room_forecast_booking_line_rel',  # Relational table name
        'booking_line_id',  # Column for room.booking.line ID
        'forecast_id',  # Column for room.rate.forecast ID
        string="Forecasts",
        help="Forecast records associated with this room line."
    )