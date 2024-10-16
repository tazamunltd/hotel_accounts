from odoo import models, fields

class ReservationProfile(models.Model):
    _name = 'reservation.profile'
    _description = 'Reservation Profile'

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

    profile_id = fields.Char(string='Profile ID', required=True)
    profile_category = fields.Char(string='Profile Category')
    last_name = fields.Char(string='Last Name')
    first_name = fields.Char(string='First Name')
    passport_number = fields.Char(string='Passport')
    id_number = fields.Char(string='ID Number')
    house_use = fields.Boolean(string='House Use')
    vip = fields.Boolean(string='VIP')
    complementary = fields.Boolean(string='Complementary')
    
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('credit_limit', 'Credit Limit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment')
    ], string='Payment Type')

    nationality = fields.Many2one('res.country', string='Nationality')
    source_of_business = fields.Many2one('source.business', string='Source of Business')
    market_segment = fields.Char(string='Market Segment')
    meal_pattern = fields.Selection([
        ('ro', 'Room Only'),
        ('bb', 'Bed & Breakfast'),
        ('hb', 'Half Board'),
        ('fb', 'Full Board')
    ], string='Meal Pattern')
    
    rate_code = fields.Char(string='Rate Code')

    status = fields.Selection([
        ('active', 'Active'),
        ('black_list', 'Black List'),
        ('obsolete', 'Obsolete')
    ], string='Status', default='active')

    # Related buttons for additional actions
    documents = fields.Binary(string='Documents')
    guest_comments = fields.Text(string='Guest Comments')
    job_title = fields.Char(string='Job Title')
    employer_company = fields.Char(string='Employer/Company')
    position = fields.Char(string='Position')
    salutation = fields.Char(string='Salutation')
    currency = fields.Many2one('res.currency', string='Currency')
    spouse_name = fields.Char(string='Spouse Name')
    language = fields.Many2one('res.lang', string='Language')
    rank = fields.Char(string='Rank')
    birthday = fields.Date(string='Birthday')
    birth_place = fields.Char(string='Birth Place')
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')], string='Gender')
    spouse_birthday = fields.Date(string='Spouse Birthday')
    documents = fields.Binary(string='Documents')
    guest_comments = fields.Text(string='Guest Comments')

    # Fields for the Information page
    special_rate = fields.Char(string='Special Rate')
    extra_features = fields.Char(string='Extra Features')
    preferred_room_type = fields.Char(string='Preferred Room Type')
    preferred_room = fields.Char(string='Preferred Room')
    expected_room = fields.Char(string='Expected Room')
    comments = fields.Text(string='Comments')
    total_points = fields.Integer(string='Total Points')
    user_sort = fields.Char(string='User Sort')

    first_visit = fields.Date(string='First Visit')
    last_visit = fields.Date(string='Last Visit')
    last_rate = fields.Char(string='Last Rate')
    last_room = fields.Char(string='Last Room')
    booking_rate = fields.Char(string='Booking Rate')
    total_stays = fields.Integer(string='Total Stays')
    total_nights = fields.Integer(string='Total Nights')
    total_cancellations = fields.Integer(string='Total Cancellations')
    total_no_shows = fields.Integer(string='Total No Shows')
    total_revenue = fields.Float(string='Total Revenue')

    # Address Information from res.company
    address_ids = fields.One2many('res.partner', 'company_id', string='Profile Address')
    country_id = fields.Many2one('res.country', string='Country', related='address_ids.country_id', readonly=False)
    state_id = fields.Many2one('res.country.state', string='State', related='address_ids.state_id', readonly=False)
    city = fields.Char(related='address_ids.city', string='City', readonly=False)
    zip_code = fields.Char(related='address_ids.zip', string='Zip Code', readonly=False)
    street = fields.Char(related='address_ids.street', string='Street', readonly=False)
    address_type = fields.Char(string='Address Type')
    user_sort = fields.Char(string='User Sort')
    is_obsolete = fields.Boolean(string='Obsolete')
    is_primary = fields.Boolean(string='Primary')
    comments = fields.Text(string='Comments')

    _rec_name = 'profile_id'
    profile_id = fields.Char(string='Profile ID', required=True)
    method_type = fields.Char(string='Method Type')
    description = fields.Text(string='Description')
    user_sort = fields.Char(string='User Sort')
    is_primary = fields.Boolean(string='Primary')
    is_obsolete = fields.Boolean(string='Obsolete')

    contact_method_type = fields.Char(string='Method Type')
    contact_method_description = fields.Text(string='Description')
    contact_method_user_sort = fields.Char(string='User Sort')
    contact_method_is_primary = fields.Boolean(string='Primary')
    contact_method_is_obsolete = fields.Boolean(string='Obsolete')

    # Image field for the "Image" page
    image = fields.Binary(string="Profile Picture")

    # Credit Card fields
    card_type = fields.Char(string='Card Type')
    card_number = fields.Char(string='Card Number')
    card_holder_name = fields.Char(string='Holder Name')
    card_expiry_date = fields.Date(string='Expiry Date')

    # Linked Profiles fields
    linked_profile_id = fields.Char(string='Linked Profile ID')
    linked_profile_description = fields.Text(string='Description')

    # Membership Card fields
    membership_type = fields.Char(string='Membership Type')
    membership_card_number = fields.Char(string='Card Number')
    membership_description = fields.Text(string='Description')
    membership_expiry_date = fields.Date(string='Expiry Date')

    # Notes fields
    note_category = fields.Char(string='Note Category')
    note_description = fields.Text(string='Description')
    note_expiry_date = fields.Datetime(string='Expiry Date')
    note_created_by = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user.id)
    note_not_for_guest = fields.Boolean(string='Not For Guest')

    # Profile Tree field
    profile_tree_description = fields.Text(string='Profile Tree')

    # Add Attributes field
    additional_attributes = fields.Text(string='Additional Attributes')

    # HTML Content field
    html_content = fields.Html(string='HTML Content')

    def export_html(self):
        """Placeholder for export HTML action."""
        pass
    

    # reservation_ids = fields.One2many('reservation.line', 'profile_id', string='Reservations')

class ReservationGroupProfile(models.Model):
    _name = 'reservation.group.profile'
    _description = 'Reservation Group Profile'

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
    profile_id = fields.Char(string='Profile ID', required=True)
    group_name = fields.Char(string='Group Name')
    company = fields.Char(string='Company')
    nationality = fields.Many2one('res.country', string='Nationality')
    source_of_business = fields.Char(string='Source of Business')
    status_code = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('pending', 'Pending'),
        ('canceled', 'Canceled'),
    ], string='Status Code')

    house_use = fields.Boolean(string='House Use')
    complimentary = fields.Boolean(string='Complimentary')

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
    rate_code = fields.Char(string='Rate Code')
    meal_pattern = fields.Selection([
        ('ro', 'Room Only'),
        ('bb', 'Bed & Breakfast'),
        ('hb', 'Half Board'),
        ('fb', 'Full Board'),
    ], string='Meal Pattern')
    market_segment = fields.Char(string='Market Segment')

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
    
    contact_leader = fields.Char(string='Contact / Leader')
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

    # reservation_ids = fields.One2many('reservation.group.line', 'profile_id', string='Reservations')


class ReservationReservationMain(models.Model):
    _name = 'reservation.reservation.main'
    _description = 'Reservation Reservation Main'

    # One2many relation for Adults
    adult_ids = fields.One2many('reservation.adult', 'reservation_id', string='Adults')
    child_ids = fields.One2many('reservation.child', 'reservation_id', string='Children')
    infant_ids = fields.One2many('reservation.infant', 'reservation_id', string='Infants')

    linked_profile_id = fields.Many2one('reservation.profile.main', string='Linked Profile ID')

    # One2many relation for Profiles
    profile_ids = fields.One2many('reservation.reservations.profile', 'profile_reservation_id', string='Profiles')

    # Guest details
    guest_id = fields.Char(string='Guest ID', required=True)
    last_name = fields.Char(string='Last Name')
    first_name = fields.Char(string='First Name')
    room_number = fields.Char(string='Room Number')
    no_of_rooms = fields.Integer(string='No. of Rooms')
    pax_per_room = fields.Integer(string='Pax/Room')
    suite = fields.Boolean(string='Suite')
    no_smoking = fields.Boolean(string='No Smoking')

    # Date fields
    arrival_date = fields.Datetime(string='Arrival Date')
    nights = fields.Integer(string='Nights')
    departure_date = fields.Datetime(string='Departure Date')

    # Reservation details
    rate_code = fields.Char(string='Rate Code')
    meal_pattern = fields.Selection([
        ('ro', 'Room Only'),
        ('bb', 'Bed & Breakfast'),
        ('hb', 'Half Board'),
        ('fb', 'Full Board'),
    ], string='Meal Pattern')
    status_code = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('pending', 'Pending'),
        ('canceled', 'Canceled'),
    ], string='Status Code')
    company = fields.Char(string='Company')
    nationality = fields.Many2one('res.country', string='Nationality')

    # Group information and room allocation
    group_profile_id = fields.Many2one('reservation.group.profile', string='Group Profile ID')
    default_profile_id = fields.Many2one('reservation.profile.main', string='Default Profile ID')
    room_type = fields.Selection([
        ('single', 'Single'),
        ('double', 'Double'),
        ('suite', 'Suite'),
        ('quad', 'Quadruple'),
    ], string='Room Type')
    total_children = fields.Integer(string='Total Children')
    total_infants = fields.Integer(string='Total Infants')
    total_extra_beds = fields.Integer(string='Extra Beds')
    companions = fields.Char(string='Companions')

    # Allotment and financials
    allotment_value = fields.Float(string='Allotment Value')
    rate_value = fields.Float(string='Rate Value')
    meal_value = fields.Float(string='Meal Value')
    release_date = fields.Date(string='Release Date')
    discount_rate = fields.Float(string='Discount % of Rate')
    discount_meals = fields.Float(string='Discount % of Meals')

    # Source and segment
    source_of_business = fields.Char(string='Source of Business')
    market_segment = fields.Char(string='Market Segment')

    # Additional remarks
    remarks = fields.Text(string='Remarks')
    group_comments = fields.Text(string='Group Comments')


    # Fields for Optionals Page
    how_taken = fields.Char(string='How Taken')
    travel_method = fields.Selection([
        ('air', 'Air'),
        ('train', 'Train'),
        ('car', 'Car'),
        ('bus', 'Bus'),
    ], string='Travel Method')
    visit_reason = fields.Selection([
        ('business', 'Business'),
        ('leisure', 'Leisure'),
        ('medical', 'Medical'),
    ], string='Visit Reason')
    house_use = fields.Boolean(string='House Use')
    complimentary = fields.Boolean(string='Complimentary')
    stay_as_vip = fields.Boolean(string='Stay as VIP')

    # Payment details
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('prepaid_credit', 'Pre-Paid / Credit Limit'),
        ('credit_limit', 'Credit (C/L)'),
        ('credit_card', 'Credit Card'),
        ('other', 'Other Payment'),
    ], string='Payment Type')
    credit_limit_value = fields.Float(string='Credit Limit Value')

    # Safe Box Information
    safe_box_code = fields.Char(string='Safe Box Code')
    police_bill_number = fields.Char(string='Police # (Bill #)')
    voucher_received = fields.Boolean(string='Voucher Received?')
    deposit = fields.Float(string='Deposit')
    sponsor = fields.Char(string='Sponsor')
    reserved_by = fields.Char(string='Reserved By')

    # Additional comments
    comments = fields.Text(string='Comments')

    reservation_attributes = fields.Text(string='Attributes')

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
    reservation_id = fields.Many2one('reservation.reservation.main', string='Reservation')

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
    reservation_id = fields.Many2one('reservation.reservation.main', string='Reservation')
    

class ReservationInfant(models.Model):
    _name = 'reservation.infant'
    _description = 'Reservation Infant'

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
    reservation_id = fields.Many2one('reservation.reservation.main', string='Reservation')



class ReservationProfile(models.Model):
    _name = 'reservation.reservations.profile'
    _description = 'Reservation Profile'

    profile_id = fields.Char(string='Profile ID')
    name = fields.Char(string='Name')
    description = fields.Text(string='Description')
    

    # Link to the main reservation
    profile_reservation_id = fields.Many2one('reservation.reservation.main', string='Reservation')


class ReservationTrace(models.Model):
    _name = 'reservation.trace'
    _description = 'Reservation Trace'

    trace_id = fields.Char(string='ID', required=True)
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
    ], string='Target', required=True)

    room_number = fields.Char(string='Room Number')
    user_text = fields.Text(string='User Text')
    user_id = fields.Many2one('res.users', string='User ID')
    message = fields.Text(string='Message')

    # Date fields
    due_date = fields.Datetime(string='Due Date')
    end_date = fields.Datetime(string='End Date')
    start_of_day = fields.Boolean(string='Start of Day')
    end_of_day = fields.Boolean(string='End of Day')
    recurring_daily = fields.Boolean(string='Recurring Daily')

    # Status
    status = fields.Selection([
        ('new', 'New'),
        ('in_process', 'In Process'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='new')


class ReservationTraceLog(models.Model):
    _name = 'reservation.trace.log'
    _description = 'Reservation Trace Log'

    trace_id = fields.Many2one('reservation.trace', string='Trace')
    message = fields.Text(string='Message')
    date = fields.Datetime(string='Date')
