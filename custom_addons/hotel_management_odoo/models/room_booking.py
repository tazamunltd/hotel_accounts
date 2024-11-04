from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo import exceptions
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import pytz
from itertools import combinations

from odoo.exceptions import UserError


class RoomBooking(models.Model):
    """Model that handles the hotel room booking and all operations related
     to booking"""
    _name = "room.booking"
    _order = 'create_date desc'
    _description = "Hotel Room Reservation"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def get_today_checkin_domain(self):
        today = fields.Date.context_today(self)
        return [
            ('checkin_date', '>=', today), 
            ('checkin_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_in')
        ]

    @api.model
    def get_today_checkout_domain(self):
        today = fields.Date.context_today(self)
        return [
            ('checkout_date', '>=', today), 
            ('checkout_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_out')
        ]

    @api.model
    def retrieve_dashboard(self):
        self.delete_zero_room_count_records()
        self.env.cr.commit()
        # Today's check-in and check-out counts
        today = fields.Date.context_today(self)
        today_checkin_count = self.search_count([
            ('checkin_date', '>=', today),
            ('checkin_date', '<', today + timedelta(days=1)),
            ('state', '=', 'block')
        ])
        today_checkout_count = self.search_count([
            ('checkout_date', '>=', today),
            ('checkout_date', '<', today + timedelta(days=1)),
            ('state', '=', 'check_out')
        ])

        # Counts for each specific booking state
        not_confirm_count = self.env['room.booking'].search_count([('state', '=', 'not_confirmed')])
        confirmed_count = self.env['room.booking'].search_count([('state', '=', 'confirmed')])
        waiting_count = self.env['room.booking'].search_count([('state', '=', 'waiting')])
        blocked_count = self.env['room.booking'].search_count([('state', '=', 'block')])
        cancelled_count = self.env['room.booking'].search_count([('state', '=', 'cancel')])
        checkin_count = self.search_count([('state', '=', 'check_in')])
        checkout_count = self.search_count([('state', '=', 'check_out')])

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
        }
        return result

    # @api.model
    # def retrieve_dashboard(self):
    #     result = {
    #         'all_to_send': 0,
    #         'today_checkin': self.search_count(self.get_today_checkin_domain()),
    #     }
    #     return result


    adult_ids = fields.One2many('reservation.adult', 'reservation_id', string='Adults')
    child_ids = fields.One2many('reservation.child', 'reservation_id', string='Children')

    meal_pattern = fields.Many2one('meal.pattern', string="Meal Pattern")
    group_booking_id = fields.Many2one(
        'group.booking',  # The source model (group bookings)
        string='Group Booking',
        ondelete='cascade'
    )

    name = fields.Char(string="Folio Number", readonly=True, index=True,
                       default="New", help="Name of Folio")
    hotel_id = fields.Many2one('hotel.hotel', string="Hotel", help="Hotel associated with this booking")
    group_booking = fields.Many2one('group.booking', string="Group Booking", help="Group associated with this booking")

    @api.onchange('group_booking')
    def _onchange_group_booking(self):
        if self.group_booking:
            print(f"Nationality: {self.group_booking.nationality.name}")
            self.nationality = self.group_booking.nationality.id if self.group_booking.nationality else False
            self.partner_id = self.group_booking.contact_leader.id if self.group_booking.contact_leader else False
            self.source_of_business = self.group_booking.source_of_business.id if self.group_booking.source_of_business else False
            self.rate_code = self.group_booking.rate_code.id if self.group_booking.rate_code else False
            self.meal_pattern = self.group_booking.group_meal_pattern.id if self.group_booking.group_meal_pattern else False
            self.market_segment = self.group_booking.market_segment.id if self.group_booking.market_segment else False

    agent = fields.Many2one('agent.agent', string="Agent", help="Agent associated with this booking")
    is_vip = fields.Boolean(related='partner_id.is_vip', string="VIP", store=True)
    allow_profile_change = fields.Boolean(related='group_booking.allow_profile_change',
                                          string='Allow changing profile data in the reservation form?', readonly=True)
    company_id = fields.Many2one('res.company', string="Hotel",
                                 help="Choose the Hotel",
                                 index=True,
                                 default=lambda self: self.env.company)
    # partner_id = fields.Many2one('res.partner', string="Customer",
    #                              help="Customers of hotel",
    #                              required=True, index=True, tracking=1,
    #                              domain="[('type', '!=', 'private'),"
    #                                     " ('company_id', 'in', "
    #                                     "(False, company_id))]")
    is_agent = fields.Boolean(string='Is Company')
    partner_id = fields.Many2one(
        'res.partner',
        string='Contact'
        
    )

    reference_contact = fields.Many2one(
        'res.partner',
        string='Contact Reference'
        
    )
    


    # @api.onchange('partner_id')
    # def _onchange_customer(self):
    #     if self.partner_id:
    #         self.nationality = self.partner_id.nationality.id
    #         self.source_of_business = self.partner_id.source_of_business.id
    #         self.rate_code = self.partner_id.rate_code.id

    @api.onchange('partner_id')
    def _onchange_customer(self):
        if self.group_booking:
            # If group_booking is selected, skip this onchange
            return
        if self.partner_id:
            self.nationality = self.partner_id.nationality.id
            self.source_of_business = self.partner_id.source_of_business.id
            self.rate_code = self.partner_id.rate_code.id

    @api.onchange('is_agent')
    def _onchange_is_agent(self):
        self.partner_id = False
        return {
            'domain': {
                'partner_id': [('is_company', '=', self.is_agent)]
            }
        }
    
    date_order = fields.Datetime(string="Order Date",
                                 required=True, copy=False,
                                 help="Creation date of draft/sent orders,"
                                      " Confirmation date of confirmed orders",
                                 default=fields.Datetime.now)
    is_checkin = fields.Boolean(default=False, string="Is Checkin",
                                help="sets to True if the room is occupied")
    maintenance_request_sent = fields.Boolean(default=False,
                                              string="Maintenance Request sent"
                                                     "or Not",
                                              help="sets to True if the "
                                                   "maintenance request send "
                                                   "once")
    checkin_date = fields.Datetime(string="Check In",
                                   help="Date of Checkin")
                                   # default=fields.Datetime.now()
    checkout_date = fields.Datetime(string="Check Out",
                                    help="Date of Checkout")
                                    # default=fields.Datetime.now() + timedelta(
                                    #     hours=23, minutes=59, seconds=59)

    @api.onchange('checkin_date')
    def _onchange_checkin_date(self):
        if self.checkin_date:
            # Set checkout_date to the end of the checkin_date
            self.checkout_date = self.checkin_date + timedelta(hours=23, minutes=59, seconds=59)

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
                                            "the main Invoice.")
    event_line_ids = fields.One2many("event.booking.line",
                                     'booking_id',
                                     string="Event",
                                     help="Hotel event reservation detail.")
    vehicle_line_ids = fields.One2many("fleet.booking.line",
                                       "booking_id",
                                       string="Vehicle",
                                       help="Hotel fleet reservation detail.")
    room_line_ids = fields.One2many("room.booking.line",
                                    "booking_id", string="Room",
                                    help="Hotel room reservation detail.")
    food_order_line_ids = fields.One2many("food.booking.line",
                                          "booking_id",
                                          string='Food',
                                          help="Food details provided"
                                               " to Customer and"
                                               " it will included in the "
                                               "main invoice.", )
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

    show_confirm_button = fields.Boolean(string = "Confirm Button")
    show_cancel_button = fields.Boolean(string = "Cancel Button")
    
    hotel_room_type = fields.Many2one('room.type', string="Room Type")

    def action_confirm_booking(self):

        print("Selected records before filtering: %s", self.ids)
        print("Selected records' states: %s", self.mapped('state'))
        # Ensure all selected records have the same state
        states = self.mapped('state')
        if len(set(states)) > 1:
            raise ValidationError("Please select records with the same state.")

        # Ensure the state of all selected records is 'not_confirm'
        # if states[0] != 'not_confirmed':
        #     raise ValidationError("Please select records in the 'Not Confirm' state only.")
        if any(record.state != 'not_confirmed' for record in self):
            raise ValidationError("Please select only records in the 'Not Confirmed' state to confirm.")

        # Filter records to only those in the 'not_confirm' state
        # selected_records = self.filtered(lambda r: r.state == 'not_confirm')
        for record in self.sudo():  # Elevated permissions to avoid access issues
            record.state = 'confirmed'
            print("State changed to 'confirmed' for record ID: %s", record.id)

        # if not selected_records:
        #     raise ValidationError("No records found in the 'Not Confirm' state to confirm.")

            # Update state to 'confirmed' for each valid record
        # for record in selected_records.sudo():
        #     record.state = 'confirmed'
        #     print("State changed to confirmed for record ID: %s", record.id)

        self.env.cr.commit()

        dashboard_data = self.retrieve_dashboard()
        print("dashboard_data",dashboard_data)

        # confirmed_count = self.env['room.booking'].search_count([('state', '=', 'confirmed')])
        # not_confirm_count = self.env['room.booking'].search_count([('state', '=', 'not_confirmed')])
        # print("Confirmed Count:", confirmed_count)
        # print("Not Confirm Count:", not_confirm_count)

        # Return an action to reload the view to reflect the count changes
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {'dashboard_data': dashboard_data},
        }

    def action_cancel_booking(self):
        # Ensure all selected records have the same state
        states = self.mapped('state')
        if len(set(states)) > 1:
            raise ValidationError("Please select records with the same state.")

        # Define allowed states for cancellation
        allowed_states = ['not_confirmed', 'confirmed', 'block']

        # Explicitly check if any record is in 'check_in' state and raise an error
        if any(record.state == 'check_in' for record in self):
            raise ValidationError("You cannot cancel records that are in the 'Checkin' state.")

        # Validate that all selected records are in one of the allowed states
        for record in self:
            if record.state not in allowed_states:
                raise ValidationError(
                    "You can only cancel records that are in 'Not Confirmed', 'Confirmed', or 'Block' states. Record ID %s is in state '%s'." % (
                        record.id, record.state))

        # Update each valid record to 'cancel' and update room availability
        for record in self.sudo():  # Elevated permissions to avoid access issues
            record.state = 'cancel'
            print("State changed to 'cancel' for record ID: %s", record.id)

            # Set each room's status to 'available' and mark it as available if room_line_ids exist
            if record.room_line_ids:
                for room in record.room_line_ids:
                    room.room_id.write({
                        'status': 'available',
                    })
                    room.room_id.is_room_avail = True
                    print("Room ID %s set to available.", room.room_id.id)

        # Commit the transaction to ensure changes are saved immediately
        self.env.cr.commit()

        # Retrieve updated dashboard counts
        dashboard_data = self.retrieve_dashboard()
        print("Updated dashboard data after cancel action: %s", dashboard_data)

        # Verify count changes directly after the commit
        cancelled_count = self.env['room.booking'].search_count([('state', '=', 'cancel')])
        print("Cancelled Count: %s", cancelled_count)

        # Return an action to reload the view to reflect the count changes
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {'dashboard_data': dashboard_data},
        }

    def action_checkin_booking(self):
        today = fields.Date.context_today(self)
        dashboard_data = None  # Initialize to update once after all records are processed

        for booking in self:
            # Ensure the booking is in the 'block' state
            if booking.state != 'block':
                raise ValidationError(_("Check-in can only be done when the booking is in the 'Block' state."))

            # Ensure check-in date is today (handles both date and datetime fields)
            if fields.Date.to_date(booking.checkin_date) != today:
                raise ValidationError(
                    _("You can only check in on the reservation's check-in date, which should be today."))

            # Validate that room details are provided
            if not booking.room_line_ids:
                raise ValidationError(_("Please Enter Room Details"))

            # Set each room's status to 'occupied' and mark it as unavailable
            for room in booking.room_line_ids:
                room.room_id.write({
                    'status': 'occupied',
                })
                room.room_id.is_room_avail = False

            # Update the booking state to 'check_in'
            booking.write({"state": "check_in"})
            print("Booking ID %s checked in and rooms updated to occupied.", booking.id)

        # Retrieve updated dashboard counts only once after all records are processed
        dashboard_data = self.retrieve_dashboard()
        print("Updated dashboard data after check-in action: %s", dashboard_data)

        # Display success notification with updated dashboard data
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': "Booking Checked In Successfully!",
                'next': {'type': 'ir.actions.act_window_close'},
                'dashboard_data': dashboard_data,  # Pass updated dashboard data for frontend refresh
            }
        }

    def action_checkout_booking(self):
        # Ensure the method can handle multiple records
        today = fields.Date.context_today(self)
        dashboard_data = None  # Initialize to update once after all records are processed

        for booking in self:
            # Ensure the booking is in the 'check_in' state
            if booking.state != 'check_in':
                raise ValidationError(_("Check-out can only be done when the booking is in the 'Check-in' state."))

            # Ensure check-out date is today (handles both date and datetime fields)
            if fields.Date.to_date(booking.checkout_date) != today:
                raise ValidationError(
                    _("You can only check out on the reservation's check-out date, which should be today.")
                )

            # Update booking state to 'check_out'
            booking.write({"state": "check_out"})

            # Set each room's status to 'available' and mark it as available
            for room in booking.room_line_ids:
                room.room_id.write({
                    'status': 'available',
                    'is_room_avail': True
                })
                # Update the checkout date to today's date for each room
                room.write({'checkout_date': datetime.today()})

            print("Booking ID %s checked out and rooms updated to available.", booking.id)

        # Retrieve updated dashboard counts only once after all records are processed
        dashboard_data = self.retrieve_dashboard()
        print("Updated dashboard data after check-out action: %s", dashboard_data)

        # Display success notification with updated dashboard data
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': "Booking Checked Out Successfully!",
                'next': {'type': 'ir.actions.act_window_close'},
                'dashboard_data': dashboard_data,  # Pass updated dashboard data for frontend refresh
            }
        }

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

    room_type_name = fields.Many2one('room.type', string='Room Type')

    def action_confirm(self):
        self.state = 'confirmed'

    def action_waiting(self):
        self.state = 'waiting'

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
            print(partner_id, checkin_date, checkout_date, room_type_id, num_rooms)


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
        available_rooms = self._get_available_rooms(checkin_date, checkout_date, room_type_id, num_rooms)

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
            self.message_post(body='No rooms available for the selected dates. The reservation has been added to the waiting list.')
            return self


    def _get_available_rooms(self, checkin_date, checkout_date, room_type_id, num_rooms):
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
    )
    
    invoice_count = fields.Integer(compute='_compute_invoice_count',
                                   string="Invoice "
                                          "Count",
                                   help="The number of invoices created")
    
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
    
    
    

    passport = fields.Char(string='Passport')
    nationality = fields.Many2one('res.country', string='Nationality')
    source_of_business = fields.Many2one('source.business', string='Source of Business')
    market_segment = fields.Many2one('market.segment', string='Market Segment')

    rate_details = fields.One2many('room.type.specific.rate', compute="_compute_rate_details", string="Rate Details")
    # rate_details = fields.One2many('rate.detail', compute="_compute_rate_details", string="Rate Details")
    rate_code = fields.Many2one('rate.code',string='Rate Code')

    monday_pax_1 = fields.Float(string="Monday (1 Pax)")

    # Fields for all weekdays and pax counts
    monday_pax_1_rb = fields.Float(string="Monday (1 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    monday_pax_2_rb = fields.Float(string="Monday (2 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    monday_pax_3_rb = fields.Float(string="Monday (3 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    monday_pax_4_rb = fields.Float(string="Monday (4 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    monday_pax_5_rb = fields.Float(string="Monday (5 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    monday_pax_6_rb = fields.Float(string="Monday (6 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    tuesday_pax_1_rb = fields.Float(string="Tuesday (1 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    tuesday_pax_2_rb = fields.Float(string="Tuesday (2 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    tuesday_pax_3_rb = fields.Float(string="Tuesday (3 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    tuesday_pax_4_rb = fields.Float(string="Tuesday (4 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    tuesday_pax_5_rb = fields.Float(string="Tuesday (5 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    tuesday_pax_6_rb = fields.Float(string="Tuesday (6 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    wednesday_pax_1_rb = fields.Float(string="Wednesday (1 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    wednesday_pax_2_rb = fields.Float(string="Wednesday (2 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    wednesday_pax_3_rb = fields.Float(string="Wednesday (3 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    wednesday_pax_4_rb = fields.Float(string="Wednesday (4 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    wednesday_pax_5_rb = fields.Float(string="Wednesday (5 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    wednesday_pax_6_rb = fields.Float(string="Wednesday (6 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    thursday_pax_1_rb = fields.Float(string="Thursday (1 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    thursday_pax_2_rb = fields.Float(string="Thursday (2 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    thursday_pax_3_rb = fields.Float(string="Thursday (3 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    thursday_pax_4_rb = fields.Float(string="Thursday (4 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    thursday_pax_5_rb = fields.Float(string="Thursday (5 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    thursday_pax_6_rb = fields.Float(string="Thursday (6 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    friday_pax_1_rb = fields.Float(string="Friday (1 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    friday_pax_2_rb = fields.Float(string="Friday (2 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    friday_pax_3_rb = fields.Float(string="Friday (3 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    friday_pax_4_rb = fields.Float(string="Friday (4 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    friday_pax_5_rb = fields.Float(string="Friday (5 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    friday_pax_6_rb = fields.Float(string="Friday (6 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    saturday_pax_1_rb = fields.Float(string="Saturday (1 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    saturday_pax_2_rb = fields.Float(string="Saturday (2 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    saturday_pax_3_rb = fields.Float(string="Saturday (3 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    saturday_pax_4_rb = fields.Float(string="Saturday (4 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    saturday_pax_5_rb = fields.Float(string="Saturday (5 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    saturday_pax_6_rb = fields.Float(string="Saturday (6 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    sunday_pax_1_rb = fields.Float(string="Sunday (1 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    sunday_pax_2_rb = fields.Float(string="Sunday (2 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    sunday_pax_3_rb = fields.Float(string="Sunday (3 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    sunday_pax_4_rb = fields.Float(string="Sunday (4 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    sunday_pax_5_rb = fields.Float(string="Sunday (5 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    sunday_pax_6_rb = fields.Float(string="Sunday (6 Pax)", compute="_compute_rate_details_", store=True, readonly=False)

    pax_1_rb = fields.Float(string="Default (1 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    pax_2_rb = fields.Float(string="Default (2 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    pax_3_rb = fields.Float(string="Default (3 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    pax_4_rb = fields.Float(string="Default (4 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    pax_5_rb = fields.Float(string="Default (5 Pax)", compute="_compute_rate_details_", store=True, readonly=False)
    pax_6_rb = fields.Float(string="Default (6 Pax)", compute="_compute_rate_details_", store=True, readonly=False)

    @api.onchange('hotel_room_type')
    def _onchange_hotel_room_type(self):
        for record in self:
            # Define the days variable at the beginning to ensure it is always accessible
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

            # Clear rate code and pax fields if no hotel room type is selected
            if not record.hotel_room_type:
                record.rate_code = False
                for day in days:
                    for pax in range(1, 7):
                        setattr(record, f"{day}_pax_{pax}_rb", 0.0)
                return

            # Attempt to find rate details in room.type.specific.rate
            specific_rate_detail = self.env['room.type.specific.rate'].search([
                ('room_type_id', '=', record.hotel_room_type.id)
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
                            value = getattr(general_rate_detail, field_name, 0.0)
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





   
    # @api.onchange('hotel_room_type')
    # def _onchange_hotel_room_type(self):
    #     for record in self:
    #         # Clear rate code and pax fields if no hotel room type is selected
    #         if not record.hotel_room_type:
    #             record.rate_code = False
    #             for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
    #                 for pax in range(1, 7):
    #                     setattr(record, f"{day}_pax_{pax}_rb", 0.0)
    #             return

    #         # Find the related rate detail for the selected room type
    #         rate_detail = self.env['room.type.specific.rate'].search([
    #             ('room_type_id', '=', record.hotel_room_type.id)
    #         ], limit=1)
            
    #         # Set the rate code if found
    #         record.rate_code = rate_detail.rate_code_id if rate_detail else False

    #         # Assign the specific pax values from the rate detail to the fields in RoomBooking
    #         if rate_detail:
    #             days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    #             for day in days:
    #                 for pax in range(1, 7):
    #                     field_name = f"room_type_{day}_pax_{pax}"
    #                     rb_field_name = f"{day}_pax_{pax}_rb"
    #                     value = getattr(rate_detail, field_name, 0.0)
    #                     setattr(record, rb_field_name, value)

    @api.onchange('rate_code')
    def _onchange_rate_code(self):
        for record in self:
            # Initialize default values for all weekdays and pax counts
            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for day in weekdays:
                for pax in range(1, 7):
                    setattr(record, f"{day}_pax_{pax}_rb", 0.0)
            for pax in range(1, 7):
                setattr(record, f"pax_{pax}_rb", 0.0)

            print(f"Debug: rate_code selected - {record.rate_code}")

            # Check if rate_code and rate_detail exist
            if record.rate_code and record.rate_code.rate_detail_ids:
                print(f"Debug: rate_detail_ids before filtering - {record.rate_code.rate_detail_ids}")

                # Assign the value from the first rate_detail in rate_detail_ids
                rate_detail = record.rate_code.rate_detail_ids[0]  # Get the first rate_detail if it exists

                print(f"Debug: rate_detail found - {rate_detail}")

                # Assign the values from rate_detail to weekday fields
                for day in weekdays:
                    for pax in range(1, 7):
                        field_name = f"{day}_pax_{pax}"
                        rb_field_name = f"{day}_pax_{pax}_rb"
                        value = getattr(rate_detail, field_name, 0.0) if getattr(rate_detail, field_name, 0.0) else 0.0
                        setattr(record, rb_field_name, value)
                        print(f"Debug: {rb_field_name} value assigned - {value}")

                # Assign the values from rate_detail to default pax fields
                for pax in range(1, 7):
                    field_name = f"pax_{pax}"
                    rb_field_name = f"pax_{pax}_rb"
                    value = getattr(rate_detail, field_name, 0.0) if getattr(rate_detail, field_name, 0.0) else 0.0
                    setattr(record, rb_field_name, value)
                    print(f"Debug: {rb_field_name} value assigned - {value}")

    @api.depends('rate_code')
    def _compute_rate_details_(self):
        for record in self:
            # Initialize default value for monday_pax_1 field
            record.monday_pax_1 = 0.0
            
            # Check if rate_code and rate_detail exist
            if record.rate_code and record.rate_code.rate_detail_ids:
                rate_detail = record.rate_code.rate_detail_ids.filtered(lambda r: r.monday_pax_1 is not None)  # Filter rate_details with non-None values
                if rate_detail:
                    record.monday_pax_1 = rate_detail[0].monday_pax_1

    
    id_number = fields.Char(string='ID Number')
    house_use = fields.Boolean(string='House Use')

    @api.depends('rate_code')
    def _compute_rate_details_(self):
        pass

    

    is_customer_company = fields.Boolean(string="Filter Company Customers", default=False)  # New helper field

           
    @api.model
    def name_get(self):
        res = super(RoomBooking, self).name_get()
        for partner in self.env['res.partner'].search([]):
            print(f"Partner Name: {partner.name}, is_company: {partner.is_company}")
        return res 
                
    vip = fields.Boolean(string='VIP')
    vip_code = fields.Many2one('vip.code', string="VIP Code")

     
     # Adding a computed boolean field that controls if the vip_code should be visible
    show_vip_code = fields.Boolean(string="Show VIP Code", compute="_compute_show_vip_code", store=True)

    @api.depends('vip')
    def _compute_show_vip_code(self):
        for record in self:
            record.show_vip_code = record.vip

    @api.onchange('vip')
    def _onchange_vip(self):
        print('VIP Changed')
        if not self.vip:
            self.vip_code = False  # Clear vip_code when VIP is unchecked

    complementary = fields.Boolean(string='Complementary')
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('credit_limit', 'Credit Limit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment')
    ], string='Payment Type')

    def unlink(self):
        for rec in self:
            if rec.state != 'cancel' and rec.state != 'draft':
                raise ValidationError('Cannot delete the Booking. Cancel the Booking ')
        return super().unlink()

    @api.model
    def create(self, vals_list):
        """Sequence Generation"""
        if vals_list.get('name', 'New') == 'New':
            vals_list['name'] = self.env['ir.sequence'].next_by_code(
                'room.booking')
        return super().create(vals_list)

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
                [('ref', '=', self.name)])

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
    
    @api.depends('room_line_ids', 'food_order_line_ids', 'service_line_ids', 'vehicle_line_ids', 'event_line_ids')
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
                domain=[('ref', '=', rec.name), ('display_type', '!=', 'payment_term')],
                fields=['name', 'quantity', 'price_unit', 'product_type']
            )

            # Remove the 'id' key from account move lines
            for line in account_move_line:
                del line['id']

            # Calculate amounts for each type of line item
            if rec.room_line_ids:
                amount_untaxed_room += sum(rec.room_line_ids.mapped('price_subtotal'))
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
                amount_untaxed_food += sum(rec.food_order_line_ids.mapped('price_subtotal'))
                amount_taxed_food += sum(rec.food_order_line_ids.mapped('price_tax'))
                amount_total_food += sum(rec.food_order_line_ids.mapped('price_total'))

            if rec.service_line_ids:
                for service in rec.service_line_ids:
                    booking_list.append(self.create_list(service))
                amount_untaxed_service += sum(rec.service_line_ids.mapped('price_subtotal'))
                amount_taxed_service += sum(rec.service_line_ids.mapped('price_tax'))
                amount_total_service += sum(rec.service_line_ids.mapped('price_total'))

            if rec.vehicle_line_ids:
                for fleet in rec.vehicle_line_ids:
                    booking_list.append(self.create_list(fleet))
                amount_untaxed_fleet += sum(rec.vehicle_line_ids.mapped('price_subtotal'))
                amount_taxed_fleet += sum(rec.vehicle_line_ids.mapped('price_tax'))
                amount_total_fleet += sum(rec.vehicle_line_ids.mapped('price_total'))

            if rec.event_line_ids:
                for event in rec.event_line_ids:
                    booking_list.append(self.create_list(event))
                amount_untaxed_event += sum(rec.event_line_ids.mapped('price_subtotal'))
                amount_taxed_event += sum(rec.event_line_ids.mapped('price_tax'))
                amount_total_event += sum(rec.event_line_ids.mapped('price_total'))

            # Assign computed amounts to the current record
            rec.amount_untaxed = amount_untaxed_food + amount_untaxed_room + amount_untaxed_fleet + amount_untaxed_event + amount_untaxed_service
            rec.amount_untaxed_food = amount_untaxed_food
            rec.amount_untaxed_room = amount_untaxed_room
            rec.amount_untaxed_fleet = amount_untaxed_fleet
            rec.amount_untaxed_event = amount_untaxed_event
            rec.amount_untaxed_service = amount_untaxed_service
            rec.amount_tax = amount_taxed_food + amount_taxed_room + amount_taxed_fleet + amount_taxed_event + amount_taxed_service
            rec.amount_taxed_food = amount_taxed_food
            rec.amount_taxed_room = amount_taxed_room
            rec.amount_taxed_fleet = amount_taxed_fleet
            rec.amount_taxed_event = amount_taxed_event
            rec.amount_taxed_service = amount_taxed_service
            rec.amount_total = amount_total_food + amount_total_room + amount_total_fleet + amount_total_event + amount_total_service
            rec.amount_total_food = amount_total_food
            rec.amount_total_room = amount_total_room
            rec.amount_total_fleet = amount_total_fleet
            rec.amount_total_event = amount_total_event
            rec.amount_total_service = amount_total_service

        return booking_list
    
    # def _compute_amount_untaxed(self, flag=False):
    #     """Compute the total amounts of the Sale Order"""
    #     amount_untaxed_room = 0.0
    #     amount_untaxed_food = 0.0
    #     amount_untaxed_fleet = 0.0
    #     amount_untaxed_event = 0.0
    #     amount_untaxed_service = 0.0
    #     amount_taxed_room = 0.0
    #     amount_taxed_food = 0.0
    #     amount_taxed_fleet = 0.0
    #     amount_taxed_event = 0.0
    #     amount_taxed_service = 0.0
    #     amount_total_room = 0.0
    #     amount_total_food = 0.0
    #     amount_total_fleet = 0.0
    #     amount_total_event = 0.0
    #     amount_total_service = 0.0
    #     room_lines = self.room_line_ids
    #     food_lines = self.food_order_line_ids
    #     service_lines = self.service_line_ids
    #     fleet_lines = self.vehicle_line_ids
    #     event_lines = self.event_line_ids
    #     booking_list = []
    #     account_move_line = self.env['account.move.line'].search_read(
    #         domain=[('ref', '=', self.name),
    #                 ('display_type', '!=', 'payment_term')],
    #         fields=['name', 'quantity', 'price_unit', 'product_type'], )
    #     for rec in account_move_line:
    #         del rec['id']
    #     if room_lines:
    #         amount_untaxed_room += sum(room_lines.mapped('price_subtotal'))
    #         amount_taxed_room += sum(room_lines.mapped('price_tax'))
    #         amount_total_room += sum(room_lines.mapped('price_total'))
    #         for room in room_lines:
    #             booking_dict = {'name': room.room_id.name,
    #                             'quantity': room.uom_qty,
    #                             'price_unit': room.price_unit,
    #                             'product_type': 'room'}
    #             if booking_dict not in account_move_line:
    #                 if not account_move_line:
    #                     booking_list.append(booking_dict)
    #                 else:
    #                     for rec in account_move_line:
    #                         if rec['product_type'] == 'room':
    #                             if booking_dict['name'] == rec['name'] and \
    #                                     booking_dict['price_unit'] == rec[
    #                                 'price_unit'] and booking_dict['quantity']\
    #                                     != rec['quantity']:
    #                                 booking_list.append(
    #                                     {'name': room.room_id.name,
    #                                      "quantity": booking_dict[
    #                                                      'quantity'] - rec[
    #                                                      'quantity'],
    #                                      "price_unit": room.price_unit,
    #                                      "product_type": 'room'})
    #                             else:
    #                                 booking_list.append(booking_dict)
    #                 if flag:
    #                     room.booking_line_visible = True
    #     if food_lines:
    #         for food in food_lines:
    #             booking_list.append(self.create_list(food))
    #         amount_untaxed_food += sum(food_lines.mapped('price_subtotal'))
    #         amount_taxed_food += sum(food_lines.mapped('price_tax'))
    #         amount_total_food += sum(food_lines.mapped('price_total'))
    #     if service_lines:
    #         for service in service_lines:
    #             booking_list.append(self.create_list(service))
    #         amount_untaxed_service += sum(
    #             service_lines.mapped('price_subtotal'))
    #         amount_taxed_service += sum(service_lines.mapped('price_tax'))
    #         amount_total_service += sum(service_lines.mapped('price_total'))
    #     if fleet_lines:
    #         for fleet in fleet_lines:
    #             booking_list.append(self.create_list(fleet))
    #         amount_untaxed_fleet += sum(fleet_lines.mapped('price_subtotal'))
    #         amount_taxed_fleet += sum(fleet_lines.mapped('price_tax'))
    #         amount_total_fleet += sum(fleet_lines.mapped('price_total'))
    #     if event_lines:
    #         for event in event_lines:
    #             booking_list.append(self.create_list(event))
    #         amount_untaxed_event += sum(event_lines.mapped('price_subtotal'))
    #         amount_taxed_event += sum(event_lines.mapped('price_tax'))
    #         amount_total_event += sum(event_lines.mapped('price_total'))
    #     for rec in self:
    #         rec.amount_untaxed = amount_untaxed_food + amount_untaxed_room + \
    #                              amount_untaxed_fleet + \
    #                              amount_untaxed_event + amount_untaxed_service
    #         rec.amount_untaxed_food = amount_untaxed_food
    #         rec.amount_untaxed_room = amount_untaxed_room
    #         rec.amount_untaxed_fleet = amount_untaxed_fleet
    #         rec.amount_untaxed_event = amount_untaxed_event
    #         rec.amount_untaxed_service = amount_untaxed_service
    #         rec.amount_tax = (amount_taxed_food + amount_taxed_room
    #                           + amount_taxed_fleet
    #                           + amount_taxed_event + amount_taxed_service)
    #         rec.amount_taxed_food = amount_taxed_food
    #         rec.amount_taxed_room = amount_taxed_room
    #         rec.amount_taxed_fleet = amount_taxed_fleet
    #         rec.amount_taxed_event = amount_taxed_event
    #         rec.amount_taxed_service = amount_taxed_service
    #         rec.amount_total = (amount_total_food + amount_total_room
    #                             + amount_total_fleet + amount_total_event
    #                             + amount_total_service)
    #         rec.amount_total_food = amount_total_food
    #         rec.amount_total_room = amount_total_room
    #         rec.amount_total_fleet = amount_total_fleet
    #         rec.amount_total_event = amount_total_event
    #         rec.amount_total_service = amount_total_service
    #     return booking_list

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

    @api.onchange('food_order_line_ids', 'room_line_ids',
                  'service_line_ids', 'vehicle_line_ids', 'event_line_ids')
    def _onchange_room_line_ids(self):
        """Invokes the Compute amounts function"""
        self._compute_amount_untaxed()
        self.invoice_button_visible = False

    # @api.constrains("room_line_ids")
    # def _check_duplicate_folio_room_line(self):
    #     """
    #     This method is used to validate the room_lines.
    #     ------------------------------------------------
    #     @param self: object pointer
    #     @return: raise warning depending on the validation
    #     """
    #     for record in self:
    #         # Create a set of unique ids
    #         ids = set()
    #         for line in record.room_line_ids:
    #             if line.room_id.id in ids:
    #                 raise ValidationError(
    #                     _(
    #                         """Room Entry Duplicates Found!, """
    #                         """You Cannot Book "%s" Room More Than Once!"""
    #                     )
    #                     % line.room_id.name
    #                 )
    #             ids.add(line.room_id.id)

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
                    'message': "Rooms reserved Successfully!",
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }
        raise ValidationError(_("Please Enter Room Details"))

    def action_cancel(self):
        """
        @param self: object pointer
        """
        if self.room_line_ids:
            for room in self.room_line_ids:
                room.room_id.write({
                    'status': 'available',
                })
                room.room_id.is_room_avail = True
        self.write({"state": "cancel"})

    # def action_maintenance_request(self):
    #     """
    #     Function that handles the maintenance request
    #     """
    #     room_list = []
    #     for rec in self.room_line_ids.room_id.ids:
    #         room_list.append(rec)
    #     if room_list:
    #         room_id = self.env['hotel.room'].search([
    #             ('id', 'in', room_list)])
    #         self.env['maintenance.request'].sudo().create({
    #             'date': fields.Date.today(),
    #             'state': 'draft',
    #             'type': 'room',
    #             'room_maintenance_ids': room_id.ids,
    #         })
    #         self.maintenance_request_sent = True
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'type': 'success',
    #                 'message': "Maintenance Request Sent Successfully",
    #                 'next': {'type': 'ir.actions.act_window_close'},
    #             }
    #         }
    #     raise ValidationError(_("Please Enter Room Details"))

    def action_done(self):
        """Button action_confirm function"""
        for rec in self.env['account.move'].search(
                [('ref', '=', self.name)]):
            if rec.payment_state != 'not_paid':
                self.write({"state": "done"})
                self.is_checkin = False
                if self.room_line_ids:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'type': 'success',
                            'message': "Booking Checked Out Successfully!",
                            'next': {'type': 'ir.actions.act_window_close'},
                        }
                    }
            raise ValidationError(_('Your Invoice is Due for Payment.'))
        self.write({"state": "done"})

    def action_checkout(self):
        today = fields.Date.context_today(self)
        if fields.Date.to_date(self.checkout_date) != today:
            raise ValidationError(
                _("You can only check out on the reservation's check-out date, which should be today."))
        """Button action_heck_out function"""
        self.write({"state": "check_out"})
        for room in self.room_line_ids:
            room.room_id.write({
                'status': 'available',
                'is_room_avail': True
            })
            room.write({'checkout_date': datetime.today()})

    def action_invoice(self):
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

    def action_checkin(self):

        today = fields.Date.context_today(self)
        if fields.Date.to_date(self.checkout_date) != today:
            raise ValidationError(
                _("You can only check in on the reservation's check-in date, which should be today."))
        """
        @param self: object pointer
        """
        if not self.room_line_ids:
            raise ValidationError(_("Please Enter Room Details"))
        else:
            for room in self.room_line_ids:
                room.room_id.write({
                    'status': 'occupied',
                })
                room.room_id.is_room_avail = False
            self.write({"state": "check_in"})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'success',
                    'message': "Booking Checked In Successfully!",
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

    def action_block(self):
        pass

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
                      [self.env.ref('hotel_management_odoo.hotel_group_admin').id,
                       self.env.ref(
                           'hotel_management_odoo.cleaning_team_group_head').id,
                       self.env.ref(
                           'hotel_management_odoo.cleaning_team_group_user').id,
                       self.env.ref(
                           'hotel_management_odoo.hotel_group_reception').id,
                       self.env.ref(
                           'hotel_management_odoo.maintenance_team_group_leader').id,
                       self.env.ref(
                           'hotel_management_odoo.maintenance_team_group_user').id
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
            raise ValidationError(_("Please Enter time zone in user settings."))

    room_count = fields.Integer(string='Rooms', default=1)
    adult_count = fields.Integer(string='Adults', default=1)
    child_count = fields.Integer(string='Children', default=0)
    child_ages = fields.One2many('hotel.child.age', 'booking_id', string='Children Ages')
    total_people = fields.Integer(string='Total People', compute='_compute_total_people', store=True)
    rooms_to_add = fields.Integer(string='Rooms to Add', default=0)

    room_ids_display = fields.Char(string="Room Names", compute="_compute_room_ids_display")
    room_type_display = fields.Char(string="Room Types", compute="_compute_room_type_display")

    room_price = fields.Float(string="Price")
    meal_price = fields.Float(string="Meal Price")

    hide_fields = fields.Boolean(string="Hide Fields", default=False)

    @api.depends('room_line_ids')
    def _compute_room_ids_display(self):
        for record in self:
            room_names = record.room_line_ids.mapped('room_id.name')  # Get all room names
            record.room_ids_display = ", ".join(room_names) if room_names else "No records"

    @api.depends('room_line_ids')
    def _compute_room_type_display(self):
        for record in self:
            # Correctly map the room type name from the room_line_ids
            room_types = record.room_line_ids.mapped('room_id.room_type_name.room_type')  # Get all room type names
            record.room_type_display = ", ".join(room_types) if room_types else "No records"

    parent_booking = fields.Selection(
        selection=lambda self: self._get_booking_names(),
        string="Parent Booking",
        store=True,
    )

    parent_booking_name = fields.Char(
        string="Parent Booking Name",
        compute="_compute_parent_booking_name",
        store=True
    )

    @api.depends('parent_booking')
    def _compute_parent_booking_name(self):
        for record in self:
            if record.parent_booking:
                # Get the name of the parent booking based on the selection
                booking = self.env['room.booking'].search([('id', '=', int(record.parent_booking))], limit=1)
                record.parent_booking_name = booking.name if booking else ''

    def _get_booking_names(self):
        bookings = self.search([])  # Retrieve all room bookings
        return [(str(booking.id), booking.name) for booking in bookings]

    @api.onchange('rooms_to_add')
    def _onchange_rooms_to_add(self):
        for line in self.room_line_ids:
            line.adult_count = self.adult_count
            line.child_count = self.child_count

    @api.depends('adult_count', 'child_count')
    def _compute_total_people(self):
        for rec in self:
            rec.total_people = rec.adult_count + rec.child_count

    # @api.onchange('room_id')
    # def _find_rooms_for_capacity(self):
    #     # Get currently selected room IDs
    #     current_room_ids = self.room_line_ids.mapped('room_id.id')

    #     # Calculate the total number of people (adults + children)
    #     total_people = self.adult_count + self.child_count

    #     # Calculate how many rooms we should add in this batch
    #     rooms_to_add = self.rooms_to_add if self.rooms_to_add else self.room_count

    #     # Fetch available rooms that can accommodate the total number of people and are not already used in this booking
    #     available_rooms = self.env['hotel.room'].search([
    #     ('status', '=', 'available'),
    #     ('id', 'not in', current_room_ids),
    #     ('num_person', '>=', total_people),
    #     ('id', 'not in', self.env['room.booking.line'].search([
    #         ('checkin_date', '<', self.checkout_date),
    #         ('checkout_date', '>', self.checkin_date),
    #         ('room_id', '!=', False)
    #     ]).mapped('room_id.id'))  # Exclude rooms with conflicting bookings
    # ], limit=rooms_to_add)

    #     # if not available_rooms:
    #     #     raise UserError('No more rooms available for booking that can accommodate the specified number of people.')

    #     # if len(available_rooms) < rooms_to_add:
    #     #     raise UserError(
    #     #         f'Only {len(available_rooms)} rooms are available that can accommodate the specified number of people. You requested {rooms_to_add} rooms.')

    #     return available_rooms
    
    is_button_clicked = fields.Boolean(string="Is Button Clicked", default=False)


    # def button_find_rooms(self):
    #     if not self.hotel_room_type:
    #         raise UserError("Please select your Room Type before proceeding.")
    #     # if self.is_button_clicked:
    #     #     raise UserError("Rooms have already been added. You cannot add them again.")
        
    #     total_people = self.adult_count + self.child_count
        
    #     # Validate check-in and check-out dates
    #     if not self.checkin_date or not self.checkout_date:
    #         raise UserError('Check-in and Check-out dates must be set before finding rooms.')
            
    #     checkin_date = self.checkin_date
    #     checkout_date = self.checkout_date
    #     duration = (checkout_date - checkin_date).days + (checkout_date - checkin_date).seconds / (24 * 3600)
        
    #     if duration <= 0:
    #         raise UserError('Checkout date must be later than Check-in date.')
        
            
    #     # Calculate remaining available rooms
    #     total_available = self.env['hotel.room'].search_count([('status', '=', 'available')])
    #     currently_booked = len(self.room_line_ids)
        
    #     # Validate if enough rooms are available
    #     if self.room_count > (total_available + currently_booked):
    #         raise UserError(f'Not enough rooms available. Total available rooms: {total_available}')
            
    #     # Check for overlapping bookings with the same date range
    #     overlapping_bookings = self.env['room.booking'].search([
    #         ('id', '!=', self.id),
    #         ('checkin_date', '<', checkout_date),
    #         ('checkout_date', '>', checkin_date),
    #     ])
        
    #     # if overlapping_bookings:
    #     #     raise UserError('Date conflict found with existing booking. Please change the Check-in and Check-out dates.')
        
    #     # Find valid rooms based on criteria
    #     new_rooms = self._find_rooms_for_capacity()
    #     # print('new_rooms', new_rooms)
    #     # if new_rooms:
    #         # Prepare room lines
    #     room_lines = []
    #     if new_rooms:
    #         for room in new_rooms:
    #             room_lines.append((0, 0, {
    #                 'room_id': False,
    #                 'checkin_date': checkin_date,
    #                 'checkout_date': checkout_date,
    #                 'uom_qty': duration,
    #                 'adult_count': self.adult_count,
    #                 'child_count': self.child_count
    #             }))
    #             # room.write({'status': 'reserved'})
    #     else:
    #         # Add an unassigned room line if no suitable rooms are found
    #         room_lines.append((0, 0, {
    #             'room_id': False,
    #             'checkin_date': checkin_date,
    #             'checkout_date': checkout_date,
    #             'uom_qty': duration,
    #             'adult_count': self.adult_count,
    #             'child_count': self.child_count,
    #             'is_unassigned': True  # Custom field to mark as unassigned
    #         }))

    #         self.state = 'waiting'
    #         # raise UserError('No rooms are currently available. Your booking has been assigned to the Waiting List.')

    #     # Append new room lines to existing room lines
    #     self.write({
    #         'room_line_ids': room_lines
    #     })

    #     # Reset rooms_to_add after successful addition
    #     self.rooms_to_add = 0 
            

    def button_find_rooms(self):
        if not self.hotel_room_type:
            raise UserError("Please select your Room Type before proceeding.")
        
        total_people = self.adult_count + self.child_count
        
        if not self.checkin_date or not self.checkout_date:
            raise UserError('Check-in and Check-out dates must be set before finding rooms.')
            
        checkin_date = self.checkin_date
        checkout_date = self.checkout_date
        duration = (checkout_date - checkin_date).days + (checkout_date - checkin_date).seconds / (24 * 3600)
        
        if duration <= 0:
            raise UserError('Checkout date must be later than Check-in date.')
        
        total_available = self.env['hotel.room'].search_count([
            ('status', '=', 'available'),
            ('room_type_name', '=', self.hotel_room_type.id)
        ])
        if self.room_count > total_available:
            raise UserError(f'Not enough rooms available for the selected room type. Total available rooms: {total_available}')
        
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
            # ('id', 'not in', self.env['room.booking.line'].search([
            #     ('checkin_date', '<', self.checkout_date),
            #     ('checkout_date', '>', self.checkin_date),
            #     ('room_id', '!=', False)
            # ]).mapped('room_id.id'))
        ], limit=rooms_to_add)

        print("available_rooms", available_rooms)

        return available_rooms


    room_count_tree = fields.Integer(string="Room Count", compute="_compute_room_count", store=False)

    @api.depends("room_line_ids")
    def _compute_room_count(self):
        for record in self:
            record.room_count_tree = len(record.room_line_ids)

            if record.room_count_tree == 0 and not record._context.get("unlinking"):
                record.state = 'cancel'
                # record.unlink()

    @api.model
    def delete_zero_room_count_records(self):
        # Search for records where room_count_tree is zero and state is 'cancel'
        records_to_delete = self.search([
            ('room_count_tree', '=', 0),
            ('state', '=', 'cancel')
        ])
        # Delete the found records
        if records_to_delete:
            records_to_delete.unlink()

    @api.onchange('room_line_ids')
    def _onchange_room_id(self):
        # Populate available rooms in the dropdown list when user clicks the Room field
        if not self.is_button_clicked:
            return {'domain': {'room_id': [('id', 'in', [])]}}

        new_rooms = self._find_rooms_for_capacity()
        room_ids = new_rooms.mapped('id') if new_rooms else []
        return {'domain': {'room_id': [('id', 'in', room_ids)]}}
    
    # def button_find_rooms(self):
    #     total_people = self.adult_count + self.child_count

    #     # Check if an unassigned room already exists for this booking
    #     existing_placeholder_room = self.env['hotel.room'].search([
    #         ('name', '=', f'Unassigned {self.id}'),
    #         ('status', '=', 'available')
    #     ], limit=1)

    #     # Create a placeholder room if one does not already exist
    #     if not existing_placeholder_room:
    #         placeholder_room = self.env['hotel.room'].create({
    #             'name': f'Unassigned {self.id}',
    #             'status': 'available',
    #             'num_person': total_people,
    #         })
    #     else:
    #         placeholder_room = existing_placeholder_room

    #     # Calculate remaining available rooms
    #     total_available = self.env['hotel.room'].search_count([('status', '=', 'available')])
    #     currently_booked = len(self.room_line_ids)

    #     # Validate if enough rooms are available
    #     if self.room_count > (total_available + currently_booked):
    #         raise UserError(f'Not enough rooms available. Total available rooms: {total_available}')

    #     # Find valid rooms based on criteria
    #     new_rooms = self._find_rooms_for_capacity()

    #     if new_rooms:
    #         if not self.checkin_date or not self.checkout_date:
    #             raise UserError('Check-in and Check-out dates must be set before finding rooms.')

    #         checkin_date = self.checkin_date
    #         checkout_date = self.checkout_date
    #         duration = (checkout_date - checkin_date).days + (checkout_date - checkin_date).seconds / (24 * 3600)

    #         if duration <= 0:
    #             raise UserError('Checkout date must be later than Check-in date.')

    #         room_lines = []
    #         for room in new_rooms:
    #             # Check if the room is already booked for the given date range
    #             overlapping_bookings = self.env['room.booking'].search([
    #                 ('id', '!=', self.id),
    #                 ('room_line_ids.room_id', '=', room.id),
    #                 ('checkin_date', '<', checkout_date),
    #                 ('checkout_date', '>', checkin_date),
    #             ])

    #             if overlapping_bookings:
    #                 continue  # Skip this room if there is a date conflict

    #             # Add the room to the booking
    #             room_lines.append((0, 0, {
    #                 'room_id': room.id,
    #                 'checkin_date': checkin_date,
    #                 'checkout_date': checkout_date,
    #                 'uom_qty': duration,
    #                 'adult_count': self.adult_count,
    #                 'child_count': self.child_count
    #             }))

    #         if room_lines:
    #             # Append new room lines to existing room lines
    #             self.write({
    #                 'room_line_ids': room_lines
    #             })

    #             # Reset rooms_to_add after successful addition
    #             self.rooms_to_add = 0
    #         else:
    #             raise UserError('No suitable rooms found that are not already used.')
    #     else:
    #         raise UserError('No suitable rooms found that are not already used.')

    
    
    # def button_find_rooms(self):
    #     if self.is_button_clicked:
    #         raise UserError("Rooms have already been added. You cannot add them again.")
        
    #     """Find and add requested number of rooms to the booking"""
    #     # Calculate remaining available rooms
    #     total_available = self.env['hotel.room'].search_count([('status', '=', 'available')])
    #     currently_booked = len(self.room_line_ids)
        
    #     # Validate if we have enough rooms available
    #     if self.room_count > (total_available + currently_booked):
    #         raise UserError(f'Not enough rooms available. Total available rooms: {total_available}')

    #     # Find valid room(s) based on the selected criteria
    #     new_rooms = self._find_rooms_for_capacity()

    #     if new_rooms:
    #         # Ensure check-in and check-out dates are set
    #         if not self.checkin_date or not self.checkout_date:
    #             raise UserError('Check-in and Check-out dates must be set before finding rooms.')
            

    #         checkin_date = self.checkin_date
    #         checkout_date = self.checkout_date

    #         adult_count = self.adult_count
    #         child_count = self.child_count

    #         # Calculate duration (in days)
    #         duration = (checkout_date - checkin_date).days + (checkout_date - checkin_date).seconds / (24 * 3600)
    #         if duration <= 0:
    #             raise UserError('Checkout date must be later than Check-in date.')

    #         # Prepare room lines to add to existing ones
    #         room_lines = []
    #         for room in new_rooms:
    #             room_lines.append((0, 0, {
    #                 'room_id': False,
    #                 'checkin_date': self.checkin_date,
    #                 'checkout_date': self.checkout_date,
    #                 'uom_qty': duration,
    #                 'adult_count': adult_count,
    #                 'child_count': child_count
    #             }))
    #             # Mark the room as reserved
    #             # room.write({'status': 'reserved'})

    #         # Append new rooms to existing room lines
    #         self.write({
    #             'room_line_ids': room_lines
    #         })

    #         self.is_button_clicked = True
            
    #         # Reset rooms_to_add after successful addition
    #         self.rooms_to_add = 0
    #     else:
    #         raise UserError('No suitable rooms found that are not already used.')

    # @api.onchange('room_count')
    # def _onchange_room_count(self):
    #     """Handle room count changes"""
    #     if self.room_count < len(self.room_line_ids):
    #         raise UserError('Cannot decrease room count below number of selected rooms.')
        
    #     # Calculate how many new rooms to add
    #     self.rooms_to_add = self.room_count - len(self.room_line_ids)


    # @api.onchange('child_count')
    # def _onchange_child_count(self):
    #     self.child_ids = [(5, 0, 0)]  # Clear existing children records
    #     for _ in range(self.child_count):
    #         self.env['reservation.child'].create({'reservation_id': self.id})

    @api.onchange('child_count')
    def _onchange_child_count(self):
        # Clear existing adult records
        self.child_ids = [(5, 0, 0)]  # Removes all current related records

        # Prepare a list to add new adult records
        new_child_records = []

        # Add new adult records based on the adult_count
        for _ in range(self.child_count):
            new_child_records.append((0, 0, {
                'first_name': '',  # You can define other default fields here
                'last_name': '',
                'nationality': False,
                'birth_date': False,
                'passport_number': '',
                'id_number': '',
                'visa_number': '',
                'id_type': '',
                'phone_number': '',
                'relation': ''
            }))

        # Update the adult_ids field with the new records
        self.child_ids = new_child_records


    @api.onchange('adult_count')
    def _onchange_adult_count(self):
        # Clear existing adult records
        self.adult_ids = [(5, 0, 0)]  # Removes all current related records

        # Prepare a list to add new adult records
        new_adult_records = []

        # Add new adult records based on the adult_count
        for _ in range(self.adult_count):
            new_adult_records.append((0, 0, {
                'first_name': '',  # You can define other default fields here
                'last_name': '',
                'nationality': False,
                'birth_date': False,
                'passport_number': '',
                'id_number': '',
                'visa_number': '',
                'id_type': '',
                'phone_number': '',
                'relation': ''
            }))

        # Update the adult_ids field with the new records
        self.adult_ids = new_adult_records


    def increase_room_count(self):
        for record in self:
            record.room_count += 1

    def decrease_room_count(self):
        for record in self:
            if record.room_count > 0:
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
            if record.adult_count > 0:
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

    child_label = fields.Char(string='Child Label', compute='_compute_child_label', store=True)


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

    first_name = fields.Char(string='First Name')
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

class ReservationChild(models.Model):
    _name = 'reservation.child'
    _description = 'Reservation Child'


    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    profile = fields.Char(string='Profile')
    nationality = fields.Many2one('res.country', string='Nationality')
    birth_date = fields.Date(string='Birth Date')
    passport_number = fields.Char(string='Passport No.')
    id_type = fields.Char(string='ID Type')
    id_number = fields.Char(string='ID Number')
    visa_number = fields.Char(string='Visa Number')
    type = fields.Selection([('visitor', 'Visitor'), ('resident', 'Resident')], string='Type')
    phone_number = fields.Char(string='Phone Number')
    relation = fields.Char(string='Relation')

    # Link to the main reservation
    reservation_id = fields.Many2one('room.booking', string='Reservation')

class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_vip = fields.Boolean(string="VIP", help="Mark this contact as a VIP")

    rate_code = fields.Many2one('rate.code', string="Rate Code")
    source_of_business = fields.Many2one('source.business', string="Source of Business")
    nationality = fields.Many2one('res.country', string='Nationality')

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    rate_code_ids = fields.One2many('rate.code', 'pricelist_id', string="Rate Codes")

class RateCodeInherit(models.Model):
    _inherit = 'rate.code'

    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', ondelete='cascade')

class SystemDate(models.Model):
    _inherit = 'res.company'

    system_date = fields.Datetime(string="System Date")
    inventory_ids = fields.One2many('hotel.inventory', 'company_id', string="Inventory")
    age_threshold = fields.Integer(string="Age Threshold")


class HotelInventory(models.Model):
    _name = 'hotel.inventory'
    _description = 'Hotel Inventory'
    _table = 'hotel_inventory'  # This should match the database table name

    hotel_name = fields.Integer(string="Hotel Name")
    room_type = fields.Many2one('room.type', string="Room Type")
    total_room_count = fields.Integer(string="Total Room Count")
    pax = fields.Integer(string="Pax")
    age_threshold = fields.Integer(string="Age Threshold")
    web_allowed_reservations = fields.Integer(string="Web Allowed Reservations")
    overbooking_allowed = fields.Boolean(string="Overbooking Allowed")
    overbooking_rooms = fields.Integer(string="Overbooking Rooms")
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)

