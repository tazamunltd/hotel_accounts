from odoo import models, fields

class ReservationProfile(models.Model):
    _name = 'reservation.profile'
    _description = 'Reservation Profile'
    # _inherit = ['mail.thread', 'mail.activity.mixin']

    # Button Methods to trigger actions
    # def action_main_info(self):
        # return {
        #     'type': 'ir.actions.act_window',
        #     'name': 'Main Information',
        #     'res_model': 'reservation.profile.main',
        #     'view_mode': 'form,tree',
        #     'view_type': 'tree',
        #     'target': 'new',
        #     'context': {'default_profile_id': self.id}
        # }
    
    def action_main_info(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Main Information',
            'res_model': 'reservation.profile',
            'view_mode': 'tree,form',  # Show the tree view first, and allow form view when a record is selected
            'view_type': 'form',
            'target': 'current'  # Use 'current' instead of 'new' to show the full tree and form view
            # 'context': {
            #     'default_rate_code_id': self.id,
            # },
            # 'domain': [('rate_code_id', '=', self.id)]
        }

    def action_optional_info(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Optional Information',
            'res_model': 'reservation.profile.main',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_information(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Information',
            'res_model': 'reservation.profile.main',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_address(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Address',
            'res_model': 'reservation.profile.main',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_contact_method(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contact Method',
            'res_model': 'reservation.profile.main',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_image(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Image',
            'res_model': 'reservation.profile',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_credit_cards(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Cards',
            'res_model': 'reservation.profile',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_linked_profiles(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Linked Profiles',
            'res_model': 'reservation.profile',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_membership(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Membership',
            'res_model': 'reservation.profile',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_notes(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Notes',
            'res_model': 'reservation.profile',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_profile_tree(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Profile Tree',
            'res_model': 'reservation.profile',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }

    def action_add_attributes(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Attributes',
            'res_model': 'reservation.profile',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
            'context': {'default_profile_id': self.id}
        }
    

class ReservationProfileMain(models.Model):
    _name = 'reservation.profile.main'
    _description = 'Reservation Profile Main'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    profile_id = fields.Char(string='Profile ID', required=True,tracking=True)
    profile_category = fields.Many2one('profile.category',string='Profile Category',tracking=True)
    last_name = fields.Char(string='Last Name',tracking=True)
    first_name = fields.Char(string='First Name',tracking=True)
    passport_number = fields.Char(string='Passport',tracking=True)
    id_number = fields.Char(string='ID Number',tracking=True)
    house_use = fields.Boolean(string='House Use',tracking=True)
    vip = fields.Boolean(string='VIP',tracking=True)
    complementary = fields.Boolean(string='Complementary',tracking=True)
    
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('credit_limit', 'Credit Limit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment')
    ], string='Payment Type',tracking=True)

    nationality = fields.Many2one('res.country', string='Nationality',tracking=True)
    source_of_business = fields.Many2one('source.business', string='Source of Business',tracking=True)
    market_segment = fields.Many2one('market.segment', string='Market Segment',tracking=True)
    meal_pattern = fields.Selection([
        ('ro', 'Room Only'),
        ('bb', 'Bed & Breakfast'),
        ('hb', 'Half Board'),
        ('fb', 'Full Board')
    ], string='Meal Pattern',tracking=True)
    reservation_meal_pattern = fields.Many2one('meal.pattern', string='Meal Pattern',tracking=True)
    
    rate_code = fields.Many2one('rate.code',string='Rate Code',tracking=True)

    status = fields.Selection([
        ('active', 'Active'),
        ('black_list', 'Black List'),
        ('obsolete', 'Obsolete')
    ], string='Status', default='active',tracking=True)

    # Related buttons for additional actions
    documents = fields.Binary(string='Documents',tracking=True)
    guest_comments = fields.Text(string='Guest Comments',tracking=True)
    job_title = fields.Char(string='Job Title',tracking=True)
    employer_company = fields.Many2one('res.company', string='Employer/Company',tracking=True)
    position = fields.Char(string='Position',tracking=True)
    salutation = fields.Char(string='Salutation',tracking=True)
    currency = fields.Many2one('res.currency', string='Currency',tracking=True)
    spouse_name = fields.Char(string='Spouse Name',tracking=True)
    language = fields.Many2one('res.lang', string='Language',tracking=True)
    rank = fields.Char(string='Rank',tracking=True)
    birthday = fields.Date(string='Birthday',tracking=True)
    birth_place = fields.Char(string='Birth Place',tracking=True)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')], string='Gender',tracking=True)
    spouse_birthday = fields.Date(string='Spouse Birthday',tracking=True)
    documents = fields.Binary(string='Documents',tracking=True)
    guest_comments = fields.Text(string='Guest Comments',tracking=True)

    # Fields for the Information page
    special_rate = fields.Char(string='Special Rate',tracking=True)
    extra_features = fields.Char(string='Extra Features',tracking=True)
    preferred_room_type = fields.Char(string='Preferred Room Type',tracking=True)
    preferred_room = fields.Char(string='Preferred Room',tracking=True)
    expected_room = fields.Char(string='Expected Room',tracking=True)
    comments = fields.Text(string='Comments',tracking=True)
    total_points = fields.Integer(string='Total Points',tracking=True)
    user_sort = fields.Char(string='User Sort',tracking=True)

    first_visit = fields.Date(string='First Visit',tracking=True)
    last_visit = fields.Date(string='Last Visit',tracking=True)
    last_rate = fields.Char(string='Last Rate',tracking=True)
    last_room = fields.Char(string='Last Room',tracking=True)
    booking_rate = fields.Char(string='Booking Rate',tracking=True)
    total_stays = fields.Integer(string='Total Stays',tracking=True)
    total_nights = fields.Integer(string='Total Nights',tracking=True)
    total_cancellations = fields.Integer(string='Total Cancellations',tracking=True)
    total_no_shows = fields.Integer(string='Total No Shows',tracking=True)
    total_revenue = fields.Float(string='Total Revenue',tracking=True)

    # Address Information from res.company
    address_ids = fields.One2many('res.partner', 'company_id', string='Profile Address') #
    country_id = fields.Many2one('res.country', string='Country', related='address_ids.country_id', readonly=False,tracking=True)
    state_id = fields.Many2one('res.country.state', string='State', related='address_ids.state_id', readonly=False,tracking=True)
    city = fields.Char(related='address_ids.city', string='City', readonly=False,tracking=True)
    zip_code = fields.Char(related='address_ids.zip', string='Zip Code', readonly=False,tracking=True)
    street = fields.Char(related='address_ids.street', string='Street', readonly=False,tracking=True)
    address_type = fields.Char(string='Address Type',tracking=True)
    user_sort = fields.Char(string='User Sort',tracking=True)
    is_obsolete = fields.Boolean(string='Obsolete',tracking=True)
    is_primary = fields.Boolean(string='Primary',tracking=True)
    comments = fields.Text(string='Comments',tracking=True)

    _rec_name = 'profile_id'
    profile_id = fields.Char(string='Profile ID', required=True,tracking=True)
    method_type = fields.Char(string='Method Type',tracking=True)
    description = fields.Text(string='Description',tracking=True)
    user_sort = fields.Char(string='User Sort',tracking=True)
    is_primary = fields.Boolean(string='Primary',tracking=True)
    is_obsolete = fields.Boolean(string='Obsolete',tracking=True)

    contact_method_type = fields.Char(string='Method Type',tracking=True)
    contact_method_description = fields.Text(string='Description',tracking=True)
    contact_method_user_sort = fields.Char(string='User Sort',tracking=True)
    contact_method_is_primary = fields.Boolean(string='Primary',tracking=True)
    contact_method_is_obsolete = fields.Boolean(string='Obsolete',tracking=True)

    # Image field for the "Image" page
    image = fields.Binary(string="Profile Picture",tracking=True)

    # Credit Card fields
    card_type = fields.Char(string='Card Type',tracking=True)
    card_number = fields.Char(string='Card Number',tracking=True)
    card_holder_name = fields.Char(string='Holder Name',tracking=True)
    card_expiry_date = fields.Date(string='Expiry Date',tracking=True)

    # Linked Profiles fields
    linked_profile_id = fields.Char(string='Linked Profile ID',tracking=True)
    linked_profile_description = fields.Text(string='Description',tracking=True)

    # Membership Card fields
    membership_type = fields.Char(string='Membership Type',tracking=True)
    membership_card_number = fields.Char(string='Card Number',tracking=True)
    membership_description = fields.Text(string='Description',tracking=True)
    membership_expiry_date = fields.Date(string='Expiry Date',tracking=True)

    # Notes fields
    note_category = fields.Char(string='Note Category',tracking=True)
    note_description = fields.Text(string='Description',tracking=True)
    note_expiry_date = fields.Datetime(string='Expiry Date',tracking=True)
    note_created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user.id,tracking=True)
    note_not_for_guest = fields.Boolean(string='Not For Guest',tracking=True)

    # Profile Tree field
    profile_tree_description = fields.Text(string='Profile Tree',tracking=True)

    # Add Attributes field
    additional_attributes = fields.Text(string='Additional Attributes',tracking=True)

    # HTML Content field
    html_content = fields.Html(string='HTML Content',tracking=True)

    def export_html(self):
        """Placeholder for export HTML action."""
        pass
    

    # reservation_ids = fields.One2many('reservation.line', 'profile_id', string='Reservations')

class ReservationGroupProfile(models.Model):
    _name = 'reservation.group.profile'
    _description = 'Reservation Group Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']



    def action_print_rooming_list(self):
        """Placeholder for Print Rooming List action."""
        pass

    def action_serie_fixed_arrivals(self):
        """Placeholder for Serie (Fixed Arrivals) action."""
        pass

    def action_rate_forecast(self):
        """Placeholder for Rate Forecast action."""
        pass

    # Main fields
    profile_id = fields.Char(string='Profile ID', required=True,tracking=True)
    group_name = fields.Char(string='Group Name',tracking=True)
    company = fields.Char(string='Company',tracking=True)
    nationality = fields.Many2one('res.country', string='Nationality',tracking=True)
    source_of_business = fields.Char(string='Source of Business',tracking=True)
    status_code = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('pending', 'Pending'),
        ('canceled', 'Canceled'),
    ], string='Status Code',tracking=True)

    house_use = fields.Boolean(string='House Use',tracking=True)
    complimentary = fields.Boolean(string='Complimentary',tracking=True)

    # Payment details
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('prepaid_credit', 'Pre-Paid / Credit Limit'),
        ('credit_limit', 'Credit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment'),
    ], string='Payment Type',tracking=True)

    master_folio_limit = fields.Float(string='Master Folio C. Limit',tracking=True)

    # Rate and Market details
    rate_code = fields.Char(string='Rate Code',tracking=True)
    meal_pattern = fields.Selection([
        ('ro', 'Room Only'),
        ('bb', 'Bed & Breakfast'),
        ('hb', 'Half Board'),
        ('fb', 'Full Board'),
    ], string='Meal Pattern',tracking=True)
    market_segment = fields.Char(string='Market Segment',tracking=True)

    # Reference details
    reference = fields.Char(string='Reference',tracking=True)
    allotment = fields.Char(string='Allotment',tracking=True)

    # Additional fields
    allow_profile_change = fields.Boolean(string='Allow changing profile data in the reservation form?',tracking=True)
    country_id = fields.Many2one('res.country', string='Country',tracking=True)
    street = fields.Char(string='Street',tracking=True)
    city = fields.Char(string='City',tracking=True)
    zip_code = fields.Char(string='Zip Code',tracking=True)
    billing_address = fields.Char(string='Billing Address',tracking=True)
    
    contact_leader = fields.Char(string='Contact / Leader',tracking=True)
    phone_1 = fields.Char(string='Phone 1',tracking=True)
    phone_2 = fields.Char(string='Phone 2',tracking=True)
    mobile = fields.Char(string='Mobile',tracking=True)
    email_address = fields.Char(string='E-Mail Address',tracking=True)


    expected_rooms = fields.Integer(string='Expected Rooms',tracking=True)
    user_sort = fields.Char(string='User Sort',tracking=True)
    comments = fields.Text(string='Comments',tracking=True)

    # Statistics fields
    first_visit = fields.Date(string='First Visit',tracking=True)
    last_visit = fields.Date(string='Last Visit',tracking=True)
    last_rate = fields.Float(string='Last Rate',tracking=True)
    total_stays = fields.Integer(string='Total Stays',tracking=True)
    total_nights = fields.Integer(string='Total Nights',tracking=True)
    total_cancellations = fields.Integer(string='Total Cancellations',tracking=True)
    total_no_shows = fields.Integer(string='Total No Shows',tracking=True)
    total_revenue = fields.Float(string='Total Revenue',tracking=True)

    # reservation_ids = fields.One2many('reservation.group.line', 'profile_id', string='Reservations')


class ReservationReservationMain(models.Model):
    _name = 'reservation.reservation.main'
    _description = 'Reservation Reservation Main'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # One2many relation for Adults
    adult_ids = fields.One2many('reservation.adults', 'reservation_id', string='Adults')#
    child_ids = fields.One2many('reservation.childs', 'reservation_id', string='Children')#
    infant_ids = fields.One2many('reservation.infants', 'reservation_id', string='Infants')#

    linked_profile_id = fields.Many2one('reservation.profile.main', string='Linked Profile ID',tracking=True)

    # One2many relation for Profiles
    profile_ids = fields.One2many('reservation.reservations.profile', 'profile_reservation_id', string='Profiles')#

    # Guest details
    guest_id = fields.Char(string='Guest ID', required=True,tracking=True)
    last_name = fields.Char(string='Last Name',tracking=True)
    first_name = fields.Char(string='First Name',tracking=True)
    room_number = fields.Char(string='Room Number',tracking=True)
    no_of_rooms = fields.Integer(string='No. of Rooms',tracking=True)
    pax_per_room = fields.Integer(string='Pax/Room',tracking=True)
    suite = fields.Boolean(string='Suite',tracking=True)
    no_smoking = fields.Boolean(string='No Smoking',tracking=True)

    # Date fields
    arrival_date = fields.Datetime(string='Arrival Date',tracking=True)
    nights = fields.Integer(string='Nights',tracking=True)
    departure_date = fields.Datetime(string='Departure Date',tracking=True)

    # Reservation details
    rate_code = fields.Char(string='Rate Code',tracking=True)
    meal_pattern = fields.Selection([
        ('ro', 'Room Only'),
        ('bb', 'Bed & Breakfast'),
        ('hb', 'Half Board'),
        ('fb', 'Full Board'),
    ], string='Meal Pattern',tracking=True)
    status_code = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('pending', 'Pending'),
        ('canceled', 'Canceled'),
    ], string='Status Code',tracking=True)
    company = fields.Char(string='Company',tracking=True)
    nationality = fields.Many2one('res.country', string='Nationality',tracking=True)

    # Group information and room allocation
    group_profile_id = fields.Many2one('reservation.group.profile', string='Group Profile ID',tracking=True)
    default_profile_id = fields.Many2one('reservation.profile.main', string='Default Profile ID',tracking=True)
    room_type = fields.Selection([
        ('single', 'Single'),
        ('double', 'Double'),
        ('suite', 'Suite'),
        ('quad', 'Quadruple'),
    ], string='Room Type',tracking=True)
    total_children = fields.Integer(string='Total Children',tracking=True)
    total_infants = fields.Integer(string='Total Infants',tracking=True)
    total_extra_beds = fields.Integer(string='Extra Beds',tracking=True)
    companions = fields.Char(string='Companions',tracking=True)

    # Allotment and financials
    allotment_value = fields.Float(string='Allotment Value',tracking=True)
    rate_value = fields.Float(string='Rate Value',tracking=True)
    meal_value = fields.Float(string='Meal Value',tracking=True)
    release_date = fields.Date(string='Release Date',tracking=True)
    discount_rate = fields.Float(string='Discount % of Rate',tracking=True)
    discount_meals = fields.Float(string='Discount % of Meals',tracking=True)

    # Source and segment
    source_of_business = fields.Char(string='Source of Business',tracking=True)
    market_segment = fields.Char(string='Market Segment',tracking=True)

    # Additional remarks
    remarks = fields.Text(string='Remarks',tracking=True)
    group_comments = fields.Text(string='Group Comments',tracking=True)


    # Fields for Optionals Page
    how_taken = fields.Char(string='How Taken',tracking=True)
    travel_method = fields.Selection([
        ('air', 'Air'),
        ('train', 'Train'),
        ('car', 'Car'),
        ('bus', 'Bus'),
    ], string='Travel Method',tracking=True)
    visit_reason = fields.Selection([
        ('business', 'Business'),
        ('leisure', 'Leisure'),
        ('medical', 'Medical'),
    ], string='Visit Reason',tracking=True)
    house_use = fields.Boolean(string='House Use',tracking=True)
    complimentary = fields.Boolean(string='Complimentary',tracking=True)
    stay_as_vip = fields.Boolean(string='Stay as VIP',tracking=True)

    # Payment details
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('prepaid_credit', 'Pre-Paid / Credit Limit'),
        ('credit_limit', 'Credit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment'),
    ], string='Payment Type',tracking=True)
    credit_limit_value = fields.Float(string='Credit Limit Value',tracking=True)

    # Safe Box Information
    safe_box_code = fields.Char(string='Safe Box Code',tracking=True)
    police_bill_number = fields.Char(string='Police # (Bill #)',tracking=True)
    voucher_received = fields.Boolean(string='Voucher Received?',tracking=True)
    deposit = fields.Float(string='Deposit',tracking=True)
    sponsor = fields.Char(string='Sponsor',tracking=True)
    reserved_by = fields.Char(string='Reserved By',tracking=True)

    # Additional comments
    comments = fields.Text(string='Comments',tracking=True)

    reservation_attributes = fields.Text(string='Attributes',tracking=True)

    # profile = fields.One2many('reservation.profile.main', string='Adults')

    def action_view_changes(self):
        """Placeholder action for View Changes."""
        pass

    def action_get_passport_info(self):
        """Placeholder action for Get Passport Info."""
        pass

    def action_show_passport(self):
        """Placeholder action for Show Passport."""
        pass

class ReservationAdult(models.Model):
    _name = 'reservation.adults'
    _description = 'Reservation Adult'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    first_name = fields.Char(string='First Name',tracking=True)
    last_name = fields.Char(string='Last Name',tracking=True)
    profile = fields.Char(string='Profile',tracking=True)
    nationality = fields.Many2one('res.country', string='Nationality',tracking=True)
    birth_date = fields.Date(string='Birth Date',tracking=True)
    passport_number = fields.Char(string='Passport No.',tracking=True)
    id_number = fields.Char(string='ID Number',tracking=True)
    visa_number = fields.Char(string='Visa Number',tracking=True)
    id_type = fields.Char(string='ID Type',tracking=True)
    phone_number = fields.Char(string='Phone Number',tracking=True)
    relation = fields.Char(string='Relation',tracking=True)

    # Link to the main reservation
    reservation_id = fields.Many2one('reservation.reservation.main', string='Reservation',tracking=True)

class ReservationChild(models.Model):
    _name = 'reservation.childs'
    _description = 'Reservation Child'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    first_name = fields.Char(string='First Name',tracking=True)
    last_name = fields.Char(string='Last Name',tracking=True)
    profile = fields.Char(string='Profile',tracking=True)
    nationality = fields.Many2one('res.country', string='Nationality',tracking=True)
    birth_date = fields.Date(string='Birth Date',tracking=True)
    passport_number = fields.Char(string='Passport No.',tracking=True)
    id_type = fields.Char(string='ID Type',tracking=True)
    id_number = fields.Char(string='ID Number',tracking=True)
    visa_number = fields.Char(string='Visa Number',tracking=True)
    type = fields.Selection([('visitor', 'Visitor'), ('resident', 'Resident')], string='Type',tracking=True)
    phone_number = fields.Char(string='Phone Number',tracking=True)
    relation = fields.Char(string='Relation',tracking=True)

    # Link to the main reservation
    reservation_id = fields.Many2one('reservation.reservation.main', string='Reservation',tracking=True)
    

class ReservationInfant(models.Model):
    _name = 'reservation.infants'
    _description = 'Reservation Infant'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    first_name = fields.Char(string='First Name',tracking=True)
    last_name = fields.Char(string='Last Name',tracking=True)
    profile = fields.Char(string='Profile',tracking=True)
    nationality = fields.Many2one('res.country', string='Nationality',tracking=True)
    birth_date = fields.Date(string='Birth Date',tracking=True)
    passport_number = fields.Char(string='Passport No.',tracking=True)
    id_type = fields.Char(string='ID Type',tracking=True)
    id_number = fields.Char(string='ID Number',tracking=True)
    visa_number = fields.Char(string='Visa Number',tracking=True)
    type = fields.Selection([('visitor', 'Visitor'), ('resident', 'Resident')], string='Type',tracking=True)
    phone_number = fields.Char(string='Phone Number',tracking=True)
    relation = fields.Char(string='Relation',tracking=True)

    # Link to the main reservation
    reservation_id = fields.Many2one('reservation.reservation.main', string='Reservation',tracking=True)

class ReservationInfant(models.Model):
    _name = 'reservation.infant'



class ReservationProfile(models.Model):
    _name = 'reservation.reservations.profile'
    _description = 'Reservation Profile'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    profile_id = fields.Char(string='Profile ID',tracking=True)
    name = fields.Char(string='Name',tracking=True)
    description = fields.Text(string='Description',tracking=True)
    

    # Link to the main reservation
    profile_reservation_id = fields.Many2one('reservation.reservation.main', string='Reservation',tracking=True)


class ReservationTrace(models.Model):
    _name = 'reservation.trace'
    _description = 'Reservation Trace'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    trace_id = fields.Char(string='ID', required=True,tracking=True)
    target = fields.Selection([
        ('front_desk', 'Front Desk'),
        ('reservation', 'Reservation'),
        ('cashier', 'Cashier'),
        ('house_keeping', 'House Keeping'),
        ('concierge', 'Concierge'),
        ('f_b', 'F & B'),
        ('maintenance', 'Maintenance'),
        ('it', 'IT'),
        ('hr', 'HR'),
        ('security', 'Security'),
        ('management', 'Management'),
    ], string='Target', required=True,tracking=True)

    room_number = fields.Char(string='Room Number',tracking=True)
    user_text = fields.Text(string='User Text',tracking=True)
    user_id = fields.Many2one('res.users', string='User ID',tracking=True)
    message = fields.Text(string='Message',tracking=True)

    # Date fields
    due_date = fields.Datetime(string='Due Date',tracking=True)
    end_date = fields.Datetime(string='End Date',tracking=True)
    start_of_day = fields.Boolean(string='Start of Day',tracking=True)
    end_of_day = fields.Boolean(string='End of Day',tracking=True)
    recurring_daily = fields.Boolean(string='Recurring Daily',tracking=True)

    # Status
    status = fields.Selection([
        ('new', 'New'),
        ('in_process', 'In Process'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new',tracking=True)


class ReservationTraceLog(models.Model):
    _name = 'reservation.trace.log'
    _description = 'Reservation Trace Log'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    trace_id = fields.Many2one('reservation.trace', string='Trace',tracking=True)
    message = fields.Text(string='Message',tracking=True)
    date = fields.Datetime(string='Date',tracking=True)
