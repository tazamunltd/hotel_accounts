from odoo import models, fields, api
import logging


class GroupBooking(models.Model):
    _name = 'group.booking'
    _description = 'Group Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _logger = logging.getLogger(__name__)

    reservation_ids = fields.One2many(
        'room.booking',  # The target model (e.g., reservations)
        'group_booking_id',  # The inverse field in 'hotel.reservation' model
        string='Reservations'
    )

    room_booking_ids = fields.One2many(
        'room.booking', 'group_booking', string='Room Bookings', compute='_compute_room_booking_ids', store=False)

    total_no_shows = fields.Integer(
        string='Total No Shows', compute='_compute_no_show_count', tracking=True, store=True)
    total_cancellations = fields.Integer(
        string='Total Cancellations', compute='_compute_cancel_count', tracking=True, store=True)

    @api.depends('reservation_ids')
    def _compute_room_booking_ids(self):
        for record in self:
            all_bookings = self.env['room.booking'].search([
                '|', ('group_booking', '=',
                      record.id), ('parent_booking_id.group_booking', '=', record.id)
            ])
            # print('All Bookings:', all_bookings)
            record.room_booking_ids = all_bookings
            # print('Room Bookings:', record.room_booking_ids)

    @api.depends('room_booking_ids', 'room_booking_ids.state')
    def _compute_no_show_count(self):
        for record in self:
            # Filter bookings with state 'no_show'
            no_show_bookings = record.room_booking_ids.filtered(
                lambda b: b.state == 'no_show')
            record.total_no_shows = len(no_show_bookings)
            print('Total No Shows:', record.total_no_shows)

            record.total_stays = len(record.room_booking_ids)
            # print('Total Stays:', record.total_stays)

    @api.depends('room_booking_ids.state')
    def _compute_cancel_count(self):
        for record in self:
            # Filter bookings with state 'no_show'
            cancelled_bookings = record.room_booking_ids.filtered(
                lambda b: b.state == 'cancel')
            record.total_cancellations = len(cancelled_bookings)

            # record.total_nights = sum(
            #     record.room_booking_ids.mapped('no_of_nights') or [0])

    total_stays = fields.Integer(
        string='Total Stays',
        compute='_compute_total_stays',
        store=True,
        tracking=True
    )

    @api.depends('room_booking_ids', 'room_booking_ids.state', 'room_booking_ids.create_date')
    def _compute_total_stays(self):
        for record in self:
            # Filter bookings with state 'check_in'
            checked_in_bookings = record.room_booking_ids.filtered(
                lambda b: b.state == 'check_in')
            record.total_stays = len(checked_in_bookings)

            # Get all create_date values from `room_booking_ids`
            create_dates = record.room_booking_ids.mapped('create_date')

            if create_dates:
                # Set the earliest date in `first_visit`
                record.first_visit = min(create_dates)

                # Set the latest date in `last_visit`
                record.last_visit = max(create_dates)
            else:
                # If no bookings, set both `first_visit` and `last_visit` to False
                record.first_visit = False
                record.last_visit = False

            # Debugging output (Optional, useful for testing)
            print(f"Group Booking {record.id}: Total Stays: {record.total_stays}, "
                         f"First Visit: {record.first_visit}, Last Visit: {record.last_visit}")

    # @api.depends('room_booking_ids', 'room_booking_ids.state')
    # def _compute_total_stays(self):
    #     for record in self:
    #         # Count all bookings associated with this group booking
    #         # Including both direct bookings and those through parent bookings
    #         checked_in_bookings = record.room_booking_ids.filtered(lambda b: b.state == 'check_in')
    #         record.total_stays = len(checked_in_bookings)

    #         create_dates = record.room_booking_ids.mapped('create_date')
    #         # print(f"Group Booking {record.id}: Create Dates: {create_dates}")
    #         record.first_visit = min(create_dates)
    #         # print(f"Group Booking {record.id}: First Visit: {record.first_visit}")

    #         # Set the latest date in `last_visit`
    #         record.last_visit = max(create_dates)
    #         # print(f"Group Booking {record.id}: Last Visit: {record.last_visit}")

    #         # For debugging
    #         # bookings = record.room_booking_ids
    #         # print(f"Group Booking ID {record.id}:")
    #         # print(f"Total bookings found: {record.total_stays}")
    #         # print(f"Booking IDs: {bookings.ids}")
    #         # print(f"Booking states: {bookings.mapped('state')}")

    #         # record.total_stays = total_stays_count

    total_nights = fields.Integer(
        string='Total Nights',
        store=True,
        compute='_compute_total_nights',
        tracking=True
    )

    @api.depends('room_booking_ids')
    def _compute_total_nights(self):
        for record in self:
            record.total_nights = sum(
                record.room_booking_ids.mapped('no_of_nights') or [0])

    first_visit = fields.Datetime(
        string='First Visit',
        compute='_compute_first_and_last_visit',
        store=True,
        tracking=True,
    )

    last_visit = fields.Datetime(
        string='Last Visit',
        compute='_compute_first_and_last_visit',
        store=True,
        tracking=True,
    )

    @api.depends('room_booking_ids.create_date')
    def _compute_first_and_last_visit(self):
        for record in self:
            # Filter reservations linked to this particular group_booking
            if record.room_booking_ids:
                # Extract all create_date values from related reservations
                create_dates = record.room_booking_ids.mapped('create_date')
                # print(f"Group Booking {record.id}: Create Dates: {create_dates}")

                # Set the earliest date in `first_visit`
                record.first_visit = min(create_dates)
                # print(f"Group Booking {record.id}: First Visit: {record.first_visit}")

                # Set the latest date in `last_visit`
                record.last_visit = max(create_dates)
                # print(f"Group Booking {record.id}: Last Visit: {record.last_visit}")

                # Debugging
                # print(f"Group Booking {record.id}: First Visit: {record.first_visit}, Last Visit: {record.last_visit}")
            else:
                # If no reservations exist for the group booking, clear the values
                record.first_visit = False
                record.last_visit = False

    total_revenue = fields.Float(
        string='Total Revenue',
        compute='_compute_total_revenue',
        store=True,
        tracking=True
    )

    @api.depends('room_booking_ids.total_total_forecast')
    def _compute_total_revenue(self):
        for record in self:
            # Calculate total revenue as the sum of `total_total_forecast` for all linked reservations
            record.total_revenue = sum(
                record.room_booking_ids.mapped('total_total_forecast'))

            # Debugging output
            # print(f"Group Booking {record.id}: Total Revenue: {record.total_revenue}")

    # @api.depends()
    # def _compute_room_bookings(self):
    #     for record in self:
    #         record.room_booking_ids = self.env['room.booking'].search([('state', '=', 'reserved')])

    @api.model
    def default_get(self, fields_list):
        defaults = super(GroupBooking, self).default_get(fields_list)
        # Get all reserved room bookings
        reserved_bookings = self.env['room.booking'].search(
            [('state', '=', 'reserved')])
        defaults['room_booking_ids'] = [(6, 0, reserved_bookings.ids)]
        return defaults

    partner_id = fields.Many2one(
        'res.partner', string='Contact', tracking=True)

    name = fields.Char(string='Booking Reference',
                       required=True, tracking=True)
    address = fields.Char(
        string="Address", help="Address of the Agent", tracking=True)
    image = fields.Binary(string="Document", help="Document of the Person")
    document_name = fields.Char(string="Document Name", tracking=True)
    person_ids = fields.One2many(
        'group.booking.person', 'group_booking_id', string="Persons", tracking=True)

    # Main fields
    profile_id = fields.Char(string='Profile ID', tracking=True)
    group_name = fields.Char(string='Group Name', tracking=True)
    is_grp_company = fields.Boolean(string='Is Company', tracking=True)

    company = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        tracking=True
    )

    @api.onchange('company')
    def _onchange_customer(self):
        if self.company:
            self.nationality = self.company.nationality.id
            self.source_of_business = self.company.source_of_business.id
            self.rate_code = self.company.rate_code.id
            self.market_segment = self.company.market_segments.id
            self.group_meal_pattern = self.company.meal_pattern.id
            # self.house_use = self.company.house_use.id
            # self.complementary = self.company.meal_pattern.id

    # company = fields.Char(string='Contact')

    @api.onchange('is_grp_company')
    def _onchange_is_agent(self):
        self.partner_id = False
        return {
            'domain': {
                'company': [('is_company', '=', self.is_grp_company)]
            }
        }

    nationality = fields.Many2one(
        'res.country', string='Nationality', tracking=True)
    source_of_business = fields.Many2one(
        'source.business', string='Source of Business', tracking=True)
    status_code = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('pending', 'Pending'),
        ('canceled', 'Canceled'),
    ], string='Status Code', tracking=True)

    complimentary = fields.Boolean(string='Complimentary', tracking=True)
    complimentary_codes = fields.Many2one(
        'complimentary.code', string='Complimentary', required=True, tracking=True)
    show_complementary_code = fields.Boolean(
        string="Show Complementary Code", compute="_compute_show_codes", store=True, tracking=True)

    house_use = fields.Boolean(string='House Use', tracking=True)
    house_use_codes_ = fields.Many2one(
        'house.code', string='House Use Code', tracking=True, required=True)
    show_house_use_code = fields.Boolean(
        string="Show House Code", compute="_compute_show_house_codes", store=True, tracking=True)

    @api.depends('complimentary')
    def _compute_show_codes(self):
        for record in self:
            record.show_complementary_code = record.complimentary

    @api.onchange('complimentary')
    def _onchange_codes(self):
        if not self.complimentary:
            self.complimentary_codes = False

    @api.depends('house_use')
    def _compute_show_house_codes(self):
        for record in self:
            record.show_house_use_code = record.house_use

    @api.onchange('house_use')
    def _onchange_codes(self):
        if not self.house_use:
            self.house_use_codes_ = False

    # Payment details
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('prepaid_credit', 'Pre-Paid / Credit Limit'),
        ('credit_limit', 'Credit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment'),
    ], string='Payment Type', tracking=True)

    master_folio_limit = fields.Float(
        string='Master Folio C. Limit', tracking=True)

    # Rate and Market details
    rate_code = fields.Many2one('rate.code', string='Rate Code', tracking=True)
    meal_pattern = fields.Selection([
        ('ro', 'Room Only'),
        ('bb', 'Bed & Breakfast'),
        ('hb', 'Half Board'),
        ('fb', 'Full Board'),
    ], string='Meal Pattern', tracking=True)

    group_meal_pattern = fields.Many2one(
        'meal.pattern', string='Meal Pattern', tracking=True)
    market_segment = fields.Many2one(
        'market.segment', string='Market Segment', tracking=True)

    # Reference details
    reference = fields.Char(string='Reference', tracking=True)
    allotment = fields.Char(string='Allotment', tracking=True)

    # Additional fields
    allow_profile_change = fields.Boolean(
        string='Allow changing profile data in the reservation form?', tracking=True)
    country_id = fields.Many2one(
        'res.country', string='Country', tracking=True)
    street = fields.Char(string='Street', tracking=True)
    city = fields.Char(string='City', tracking=True)
    zip_code = fields.Char(string='Zip Code', tracking=True)
    billing_address = fields.Char(string='Billing Address', tracking=True)

    contact_leader = fields.Many2one(
        'res.partner', string='Contact / Leader', tracking=True)
    phone_1 = fields.Char(string='Phone 1', tracking=True)
    phone_2 = fields.Char(string='Phone 2', tracking=True)
    mobile = fields.Char(string='Mobile', tracking=True)
    email_address = fields.Char(string='E-Mail Address', tracking=True)

    expected_rooms = fields.Integer(string='Expected Rooms', tracking=True)
    user_sort = fields.Char(string='User Sort', tracking=True)
    comments = fields.Text(string='Comments', tracking=True)

    # Statistics fields
    # first_visit = fields.Date(string='First Visit',tracking=True)
    # last_visit = fields.Date(string='Last Visit',tracking=True)

    last_rate = fields.Float(string='Last Rate', tracking=True)


class GroupBookingPerson(models.Model):
    _name = 'group.booking.person'
    _description = 'Group Booking Person'

    name = fields.Char(string='Name', required=True, tracking=True)
    age = fields.Integer(string='Age', required=True)
    address = fields.Char(string='Address', required=True, tracking=True)
    image = fields.Binary(
        string="Document", help="Document of the Person", tracking=True)
    document_name = fields.Char(string="Document Name", tracking=True)
    group_booking_id = fields.Many2one(
        'group.booking', string='Group Booking', required=True, ondelete='cascade', tracking=True)
