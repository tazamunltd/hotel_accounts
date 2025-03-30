from odoo import models, fields, api, _
import logging

from odoo.exceptions import ValidationError


class GroupBooking(models.Model):
    _name = 'group.booking'
    _description = 'Group Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    def name_get(self):
        result = []
        for rec in self:
            name = f"{rec.group_name or 'Group'} ({rec.name})"
            result.append((rec.id, name))
        return result

    def generateRcPDF(self):
        # Redirect to the controller to generate the PDFs
        booking_ids = ','.join(map(str, self.ids))
        return {
            'type': 'ir.actions.act_url',
            'url': f'/generate_rc/bookings_pdf?booking_ids={booking_ids}',
            'target': 'self',
        }

    # @api.model
    # def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
    #     args = args or []
    #     domain = []

    #     if name:
    #         domain = [('group_name', operator, name)]
    #     return self._search(domain + args, limit=limit, order=order, access_rights_uid=name_get_uid)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None, order=None):
        args = args or []
        domain = ['|', ('group_name', operator, name), ('name', operator, name)]
        return self._search(domain + args, limit=limit, order=order, access_rights_uid=name_get_uid)


    _logger = logging.getLogger(__name__)

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
                '|', ('group_booking', '=',
                      record.id), ('parent_booking_id.group_booking', '=', record.id)
            ])
            record.room_booking_ids = all_bookings


    total_no_shows = fields.Integer(string='No Shows', compute='_compute_no_show_count', tracking=True, store=True)
    total_confirmed = fields.Integer(string='Confirmed', compute='_compute_no_show_count', tracking=True, store=True)
    total_not_confirmed = fields.Integer(string='Not Confirmed', compute='_compute_no_show_count', tracking=True, store=True)
    total_block = fields.Integer(string='Blocks', compute='_compute_no_show_count', tracking=True, store=True)
    total_checkin = fields.Integer(string='Check-Ins', compute='_compute_no_show_count', tracking=True, store=True)
    total_checkout = fields.Integer(string='Check-Outs', compute='_compute_no_show_count', tracking=True, store=True)
    total_cancellations = fields.Integer(string=' Cancellations', compute='_compute_cancel_count', tracking=True, store=True)

    
    @api.depends('room_booking_ids', 'room_booking_ids.state')
    def _compute_no_show_count(self):
        for record in self:
            # Filter bookings with state 'no_show'
            no_show_bookings = record.room_booking_ids.filtered(lambda b: b.state == 'no_show')
            confirmed_bookings = record.room_booking_ids.filtered(lambda b: b.state == 'confirmed')
            not_confirmed_bookings = record.room_booking_ids.filtered(lambda b: b.state == 'not_confirmed')
            block_bookings = record.room_booking_ids.filtered(lambda b: b.state == 'block')
            checkin_bookings = record.room_booking_ids.filtered(lambda b: b.state == 'check_in')
            checkout_bookings = record.room_booking_ids.filtered(lambda b: b.state == 'check_out')
            cancelled_bookings = record.room_booking_ids.filtered(lambda b: b.state == 'cancel')

            record.total_cancellations = len(cancelled_bookings)
            record.total_no_shows = len(no_show_bookings)
            record.total_confirmed = len(confirmed_bookings)
            record.total_not_confirmed = len(not_confirmed_bookings)
            record.total_block = len(block_bookings)
            record.total_checkin = len(checkin_bookings)
            record.total_checkout = len(checkout_bookings)
            record.total_stays = len(record.room_booking_ids)


    total_adult_count = fields.Integer(string='Adults', compute='_compute_pax_and_room_count', tracking=True, store=True)
    total_child_count = fields.Integer(string='Children', compute='_compute_pax_and_room_count', tracking=True, store=True)
    total_infant_count = fields.Integer(string='Infants', compute='_compute_pax_and_room_count', tracking=True, store=True)
    total_room_count = fields.Integer(string='Rooms', compute='_compute_pax_and_room_count', tracking=True, store=True)

    @api.depends(
        'room_booking_ids',
        'room_booking_ids.adult_count',
        'room_booking_ids.child_count',
        'room_booking_ids.infant_count',
        'room_booking_ids.room_count'
    )
    def _compute_pax_and_room_count(self):
        for record in self:
            adult_counts = record.room_booking_ids.mapped('adult_count')
            print("Group Booking %s - Adult Counts from Room Bookings: %s", record.id, adult_counts)
            record.total_adult_count = sum(adult_counts or [0])
            # record.total_adult_count = sum(record.room_booking_ids.mapped('adult_count') or [0])
            child_counts = record.room_booking_ids.mapped('child_count')
            print("Group Booking %s - Child Counts from Room Bookings: %s" % (record.id, child_counts))
            record.total_child_count = sum(child_counts or [0])
            
            # Get and log infant counts
            infant_counts = record.room_booking_ids.mapped('infant_count')
            print("Group Booking %s - Infant Counts from Room Bookings: %s" % (record.id, infant_counts))
            record.total_infant_count = sum(infant_counts or [0])
            
            record.total_room_count = sum(record.room_booking_ids.mapped('room_count') or [0])



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
        string='Stays',
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


    total_nights = fields.Integer(
        string='Total Nights',
        store=True,
        compute='_compute_total_nights',
        tracking=True
    )

    @api.depends('first_visit', 'last_visit')
    def _compute_total_nights(self):
        for record in self:
            # Check if both first_visit and last_visit are set
            if record.first_visit and record.last_visit:
                # Ensure the dates are in the correct format (date object)
                first_visit = fields.Date.from_string(record.first_visit)
                last_visit = fields.Date.from_string(record.last_visit)

                # Calculate the difference between the dates
                total_nights = (last_visit - first_visit).days
                record.total_nights = total_nights
            else:
                record.total_nights = 0

    # @api.depends('room_booking_ids')
    # def _compute_total_nights(self):
    #     for record in self:
    #         record.total_nights = sum(
    #             record.room_booking_ids.mapped('no_of_nights') or [0])

    first_visit = fields.Date(
        string='First Visit',
        compute='_compute_first_and_last_visit',
        store=True,
        tracking=True,
    )

    last_visit = fields.Date(
        string='Last Visit',
        compute='_compute_first_and_last_visit',
        store=True,
        tracking=True,
    )

    @api.depends('room_booking_ids.checkin_date', 'room_booking_ids.checkout_date', 'room_booking_ids.state')
    def _compute_first_and_last_visit(self):
        for record in self:
            # Earliest check-in (you can leave this logic as is if you still want
            # to display the earliest planned checkin_date).
            checkin_dates = record.room_booking_ids.mapped('checkin_date')
            if checkin_dates:
                record.first_visit = min(checkin_dates)
            else:
                record.first_visit = False

            # For last_visit, consider only bookings that have state = 'check_out'.
            checked_out_bookings = record.room_booking_ids.filtered(lambda b: b.state == 'check_out' and b.checkout_date)
            if checked_out_bookings:
                checkout_dates = checked_out_bookings.mapped('checkout_date')
                record.last_visit = max(checkout_dates)
            else:
                record.last_visit = False



    # @api.depends('room_booking_ids.checkin_date', 'room_booking_ids.checkout_date')
    # def _compute_first_and_last_visit(self):
    #     for record in self:
    #         if record.room_booking_ids:
    #             # Extract all check-in dates
    #             checkin_dates = record.room_booking_ids.mapped('checkin_date')
    #             checkout_dates = record.room_booking_ids.mapped('checkout_date')

    #             # Earliest check-in
    #             if checkin_dates:
    #                 earliest_checkin = min(checkin_dates)
    #                 record.first_visit = earliest_checkin
    #             else:
    #                 record.first_visit = False

    #             # Latest check-out
    #             if checkout_dates:
    #                 latest_checkout = max(checkout_dates)
    #                 record.last_visit = latest_checkout
    #             else:
    #                 record.last_visit = False
    #         else:
    #             # No bookings
    #             record.first_visit = False
    #             record.last_visit = False
    
    
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

    # partner_id = fields.Many2one('res.partner', string='Contact', tracking=True)

    # name = fields.Char(string='Booking Reference',
    #                    required=True, tracking=True)
    # address = fields.Char(
    #     string="Address", help="Address of the Agent", tracking=True)
    
    address = fields.Text(string="Address", help="Address of the Agent", tracking=True)

    image = fields.Binary(string="Document", help="Document of the Person")
    document_name = fields.Char(string=_("Document Name"), tracking=True, translate=True)
    person_ids = fields.One2many(
        'group.booking.person', 'group_booking_id', string="Persons", tracking=True)

    # Main fields
    profile_id = fields.Char(string=_('Profile ID'), tracking=True, translate=True)
    group_name = fields.Char(string=_('Group Name'), tracking=True, required=True, translate=True)
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
        # self.partner_id = False
        self.company = False
        return {
            'domain': {
                'company': [('is_company', '=', self.is_grp_company)]
            }
        }

    nationality = fields.Many2one(
        'res.country', string='Nationality', tracking=True, required=True)
    source_of_business = fields.Many2one(
        'source.business', string='Source of Business', domain=lambda self: [
        # ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], required = True, tracking=True)
    status_code = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('pending', 'Pending'),
        ('canceled', 'Canceled'),
    ], string='Status Code', tracking=True)

    complimentary = fields.Boolean(string='Complimentary', tracking=True)
    complimentary_codes = fields.Many2one('complimentary.code', string='Complimentary Codes', tracking=True)
    show_complementary_code = fields.Boolean(
        string="Show Complementary Code", compute="_compute_show_codes", store=True, tracking=True)

    house_use = fields.Boolean(string='House Use', tracking=True)
    house_use_codes_ = fields.Many2one('house.code', string='House Use Code', tracking=True)
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
    rate_code = fields.Many2one('rate.code', string='Rate Code', 
    domain=lambda self: [
        ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], tracking=True, required=True)
    # meal_pattern = fields.Selection([
    #     ('ro', 'Room Only'),
    #     ('bb', 'Bed & Breakfast'),
    #     ('hb', 'Half Board'),
    #     ('fb', 'Full Board'),
    # ], string='Meal Pattern', tracking=True)

    group_meal_pattern = fields.Many2one(
        'meal.pattern', string='Meal Pattern',  
        domain=lambda self: [
        ('company_id', '=', self.env.company.id),
    ], tracking=True, required=True)
    market_segment = fields.Many2one(
        'market.segment', string='Market Segment',  domain=lambda self: [
        # ('company_id', '=', self.env.company.id),
        ('obsolete', '=', False)
    ], tracking=True, required=True)

    # Reference details
    reference = fields.Char(string=_('Reference'), tracking=True, translate=True)
    allotment = fields.Char(string=_('Allotment'), tracking=True, translate=True)

    # Additional fields
    allow_profile_change = fields.Boolean(
        string='Allow changing profile data in the reservation form?', tracking=True)
    country_id = fields.Many2one(
        'res.country', string='Country', tracking=True)
    street = fields.Char(string=_('Street'), tracking=True, translate=True)
    city = fields.Char(string=_('City'), tracking=True, translate=True)
    zip_code = fields.Char(string=_('Zip Code'), tracking=True, translate=True)
    billing_address = fields.Char(string=('Billing Address'), tracking=True)

    contact_leader = fields.Many2one(
        'res.partner', string='Contact / Leader', tracking=True)
    phone_1 = fields.Char(string=_('Phone 1'), tracking=True)
    phone_2 = fields.Char(string=_('Phone 2'), tracking=True)
    mobile = fields.Char(string=_('Mobile'), tracking=True)
    email_address = fields.Char(string=('E-Mail Address'), tracking=True)

    expected_rooms = fields.Integer(string='Expected Rooms', tracking=True)
    user_sort = fields.Char(string=_('User Sort'), tracking=True, translate=True)
    comments = fields.Text(string='Comments', tracking=True)

    # Statistics fields
    # first_visit = fields.Date(string='First Visit',tracking=True)
    # last_visit = fields.Date(string='Last Visit',tracking=True)

    last_rate = fields.Float(string='Last Rate', tracking=True)

    name = fields.Char(string=_("Group ID"), required=True,copy=False, readonly=True, default='New', translate=True)
    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, required=True)

    group_booking_id = fields.Many2one('group.booking', string='Parent Booking', tracking=True)

    @api.model
    def create(self, vals):
        # Fetch the company_id from vals or use the current user's company
        # company_id = vals.get('company_id', self.env.user.company_id.id)
        company_id = vals.get('company_id', self.env.company.id)
        print(f"Company ID: {company_id}")
        company = self.env['res.company'].browse(company_id)
        print(f"Company: {company}")
        company_name = company.name
        print(f"Company Name: {company_name}")

        # Ensure sequence exists for the company
        sequence = self.env['ir.sequence'].search(
            [('code', '=', 'group.booking'), ('company_id', '=', company_id)],
            limit=1
        )
        print(f"Sequence: {sequence}")
        if not sequence:
            # Automatically create the sequence if not found
            sequence = self.env['ir.sequence'].create({
                'name': f"Group Booking Sequence ({company_name})",
                'code': 'group.booking',
                'prefix': f"GRP_",
                'padding': 4,  # Padding for sequence number (e.g., 0002)
                'company_id': company_id,
            })

        # Generate the name based on the sequence
        if vals.get('name', 'New') == 'New':
            sequence_number = sequence.next_by_id()
            vals['name'] = f"{company_name}/{sequence_number}"

        return super(GroupBooking, self).create(vals)


class GroupBookingPerson(models.Model):
    _name = 'group.booking.person'
    _description = 'Group Booking Person'

    name = fields.Char(string=_('Name'), required=True, tracking=True, translate=True)
    age = fields.Integer(string=_('Age'), required=True)
    address = fields.Char(string=_('Address'), required=True, tracking=True, translate=True)
    image = fields.Binary(
        string="Document", help="Document of the Person", tracking=True)
    document_name = fields.Char(string=_("Document Name"), tracking=True, translate=True)
    group_booking_id = fields.Many2one(
        'group.booking', string='Group Booking', required=True, ondelete='cascade', tracking=True)
