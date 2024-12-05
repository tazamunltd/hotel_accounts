from odoo import models, fields, api

class GroupBooking(models.Model):
    _name = 'group.booking'
    _description = 'Group Booking'

    reservation_ids = fields.One2many(
        'room.booking',  # The target model (e.g., reservations)
        'group_booking_id',  # The inverse field in 'hotel.reservation' model
        string='Reservations'
    )

    room_booking_ids = fields.One2many('room.booking', 'group_booking', string='Room Bookings', compute='_compute_room_booking_ids', store=False)

    @api.depends('reservation_ids')
    def _compute_room_booking_ids(self):
        for record in self:
            all_bookings = self.env['room.booking'].search([
                '|', ('group_booking', '=', record.id), ('parent_booking_id.group_booking', '=', record.id)
            ])
            record.room_booking_ids = all_bookings



    # @api.depends()
    # def _compute_room_bookings(self):
    #     for record in self:
    #         record.room_booking_ids = self.env['room.booking'].search([('state', '=', 'reserved')])

    @api.model
    def default_get(self, fields_list):
        defaults = super(GroupBooking, self).default_get(fields_list)
        # Get all reserved room bookings
        reserved_bookings = self.env['room.booking'].search([('state', '=', 'reserved')])
        defaults['room_booking_ids'] = [(6, 0, reserved_bookings.ids)]
        return defaults


    partner_id = fields.Many2one('res.partner', string='Contact')

    name = fields.Char(string='Booking Reference', required=True)
    address = fields.Char(string="Address", help="Address of the Agent")
    image = fields.Binary(string="Document", help="Document of the Person")
    person_ids = fields.One2many('group.booking.person', 'group_booking_id', string="Persons")

    # Main fields
    profile_id = fields.Char(string='Profile ID')
    group_name = fields.Char(string='Group Name')
    is_grp_company = fields.Boolean(string='Is Company')

    company = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True
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

    nationality = fields.Many2one('res.country', string='Nationality')
    source_of_business = fields.Many2one('source.business',string='Source of Business')
    status_code = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('pending', 'Pending'),
        ('canceled', 'Canceled'),
    ], string='Status Code')

    
    complimentary = fields.Boolean(string='Complimentary')
    complimentary_codes = fields.Many2one('complimentary.code', string='Complimentary')
    show_complementary_code = fields.Boolean(string="Show Complementary Code", compute="_compute_show_codes", store=True)

    house_use = fields.Boolean(string='House Use')
    house_use_codes_ = fields.Many2one('house.code', string='House Use Code')
    show_house_use_code = fields.Boolean(
        string="Show House Code", compute="_compute_show_house_codes", store=True)

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
    ], string='Payment Type')

    master_folio_limit = fields.Float(string='Master Folio C. Limit')

    # Rate and Market details
    rate_code = fields.Many2one('rate.code',string='Rate Code')
    meal_pattern = fields.Selection([
        ('ro', 'Room Only'),
        ('bb', 'Bed & Breakfast'),
        ('hb', 'Half Board'),
        ('fb', 'Full Board'),
    ], string='Meal Pattern')

    group_meal_pattern = fields.Many2one('meal.pattern', string='Meal Pattern')
    market_segment = fields.Many2one('market.segment',string='Market Segment')

    # Reference details
    reference = fields.Char(string='Reference')
    allotment = fields.Char(string='Allotment')

    # Additional fields
    allow_profile_change = fields.Boolean(string='Allow changing profile data in the reservation form?')
    country_id = fields.Many2one('res.country', string='Country')
    street = fields.Char(string='Street')
    city = fields.Char(string='City')
    zip_code = fields.Char(string='Zip Code')
    billing_address = fields.Char(string='Billing Address')
    
    contact_leader = fields.Many2one('res.partner', string='Contact / Leader')
    phone_1 = fields.Char(string='Phone 1')
    phone_2 = fields.Char(string='Phone 2')
    mobile = fields.Char(string='Mobile')
    email_address = fields.Char(string='E-Mail Address')


    expected_rooms = fields.Integer(string='Expected Rooms')
    user_sort = fields.Char(string='User Sort')
    comments = fields.Text(string='Comments')

    # Statistics fields
    first_visit = fields.Date(string='First Visit')
    last_visit = fields.Date(string='Last Visit')
    last_rate = fields.Float(string='Last Rate')
    total_stays = fields.Integer(string='Total Stays')
    total_nights = fields.Integer(string='Total Nights')
    total_cancellations = fields.Integer(string='Total Cancellations')
    total_no_shows = fields.Integer(string='Total No Shows')
    total_revenue = fields.Float(string='Total Revenue')

class GroupBookingPerson(models.Model):
    _name = 'group.booking.person'
    _description = 'Group Booking Person'

    name = fields.Char(string='Name', required=True)
    age = fields.Integer(string='Age', required=True)
    address = fields.Char(string='Address', required=True)
    image = fields.Binary(string="Document", help="Document of the Person")
    group_booking_id = fields.Many2one('group.booking', string='Group Booking', required=True, ondelete='cascade')
