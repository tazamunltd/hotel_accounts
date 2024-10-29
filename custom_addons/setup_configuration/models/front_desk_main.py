from odoo import models, fields

class FrontDeskWalkinMain(models.Model):
    _name = 'frontdesk.walkin.main'
    _description = 'Front Desk Walk-in Main'

    guest_id = fields.Char(string="Guest ID")
    ref = fields.Char(string="Reference")
    last_name = fields.Char(string="Last Name")
    first_name = fields.Char(string="First Name")
    room_number = fields.Char(string="Room Number")
    room_type = fields.Selection([
        ('suite', 'Suite'),
        ('regular', 'Regular')
    ], string="Room Type")
    pax_room = fields.Integer(string="Pax/Room")
    smoking = fields.Boolean(string="Smoking")
    nights = fields.Integer(string="Nights")
    departure_date = fields.Datetime(string="Departure Date")
    rate_code = fields.Char(string="Rate Code")
    meal_pattern = fields.Char(string="Meal Pattern")
    profile_id = fields.Many2one('reservation.profile.main', string="Default Profile")
    nationality = fields.Char(string="Nationality")
    total_children = fields.Integer(string="Total Children")
    total_infants = fields.Integer(string="Total Infants")
    extra_beds = fields.Integer(string="Extra Beds")
    companions = fields.Integer(string="Companions")
    rate_value = fields.Float(string="Rate Value")
    meals_value = fields.Float(string="Meals Value")
    discount_rate = fields.Float(string="Discount on Rate (%)")
    discount_meals = fields.Float(string="Discount on Meals (%)")
    
    # Adult Information
    adult_ids = fields.One2many('reservation.adults', 'reservation_id')
    child_ids = fields.One2many('reservation.childs', 'reservation_id')
    infant_ids = fields.One2many('reservation.infants', 'reservation_id')

    # Optional/Children Fields
    company = fields.Char(string="Company")
    source_of_business = fields.Char(string="Source of Business")
    vip_code = fields.Boolean(string="VIP Code")
    travel_method = fields.Selection([
        ('air', 'Air'),
        ('road', 'Road'),
        ('sea', 'Sea')
    ], string="Travel Method")
    visit_reason = fields.Selection([
        ('business', 'Business'),
        ('leisure', 'Leisure'),
    ], string="Visit Reason")
    sponsor = fields.Char(string="Sponsor")
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('credit', 'Credit (C/L)'),
        ('prepaid', 'Pre-Paid / Credit Limit'),
        ('other', 'Other Payment')
    ], string="Payment Type")
    credit_limit_value = fields.Float(string="Credit Limit Value")
    comments = fields.Text(string="Comments")
    
    # Children Information
    # children_ids = fields.One2many('frontdesk.walkin.child', 'walkin_id', string="Children")

    # Profiles/Infants Fields
    profile_ids = fields.One2many('reservation.reservations.profile', 'profile_reservation_id', string="Profiles")
    linked_profile_id = fields.Many2one('reservation.profile', string="Linked Profile")
    description = fields.Text(string="Description")
    
    # Infants Information
    infant_ids = fields.One2many('reservation.infants', 'reservation_id', string="Infants")

    front_desk_html = fields.Html(string="HTML")

class FrontDeskInHouseGuest(models.Model):
    _name = 'frontdesk.inhouse.guest.main'
    _description = 'In-House Guest'

    guest_id = fields.Char(string="Guest ID")
    ref = fields.Char(string="Reference")
    last_name = fields.Char(string="Last Name")
    first_name = fields.Char(string="First Name")
    room_number = fields.Char(string="Room Number")
    pax_room = fields.Integer(string="Pax/Room")
    no_of_rooms = fields.Integer(string="No. of Rooms")
    room_type = fields.Selection([
        ('suite', 'Suite'),
        ('regular', 'Regular')
    ], string="Room Type")
    smoking = fields.Boolean(string="No Smoking")
    rate_code = fields.Char(string="Rate Code")
    meal_pattern = fields.Char(string="Meal Pattern")
    status_code = fields.Selection([
        ('default', 'Default'),
        ('inhouse', 'In-house'),
        ('arrivals', 'Arrivals'),
        ('expected', 'Expected'),
        ('departures', 'Departures'),
        ('confirmed', 'Confirmed'),
        ('shares', 'Shares'),
        ('queue', 'Queue'),
        ('filter', 'Filter')
    ], string="Status Code", default='default')
    company = fields.Char(string="Company")
    nationality = fields.Char(string="Nationality")
    arrival_date = fields.Datetime(string="Arrival Date")
    departure_date = fields.Datetime(string="Departure Date")
    total_children = fields.Integer(string="Total Children")
    total_infants = fields.Integer(string="Total Infants")
    extra_beds = fields.Integer(string="Extra Beds")
    companions = fields.Integer(string="Companions")
    rate_value = fields.Float(string="Rate Value")
    meals_value = fields.Float(string="Meals Value")
    allotment = fields.Char(string="Allotment")
    discount_rate = fields.Float(string="Discount on Rate (%)")
    discount_meals = fields.Float(string="Discount on Meals (%)")
    remarks = fields.Text(string="Remark")
    source_of_business = fields.Char(string="Source of Business")
    market_segment = fields.Char(string="Market Segment")


    # Fields for "Optional" Page
    how_taken = fields.Selection([
        ('normal', 'Normal'),
        ('house_use', 'House Use')
    ], string="How Taken")
    travel_method = fields.Selection([
        ('air', 'Air'),
        ('road', 'Road'),
        ('sea', 'Sea')
    ], string="Travel Method")
    visit_reason = fields.Selection([
        ('business', 'Business'),
        ('leisure', 'Leisure'),
    ], string="Visit Reason")
    house_use = fields.Boolean(string="House Use")
    complimentary = fields.Boolean(string="Complimentary")
    vip_stay = fields.Boolean(string="Stay as VIP")

    # Payment Information
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('credit', 'Credit (C/L)'),
        ('prepaid', 'Pre-Paid / Credit Limit'),
        ('other', 'Other Payment')
    ], string="Payment Type")
    credit_limit_value = fields.Float(string="Credit Limit Value")
    comments = fields.Text(string="Comments")

    # Safe Box and Sponsor Information
    safe_box_code = fields.Char(string="Safe Box Code")
    voucher_received = fields.Boolean(string="Voucher Received?")
    deposit = fields.Float(string="Deposit")
    sponsor = fields.Char(string="Sponsor")
    reserved_by = fields.Char(string="Reserved By")

    adult_ids = fields.One2many('reservation.adults', 'reservation_id', string='Adults')
    child_ids = fields.One2many('reservation.childs', 'reservation_id', string='Children')
    infant_ids = fields.One2many('reservation.infants', 'reservation_id', string='Infants')
    # profile_ids = fields.One2many('reservation.reservation.profile', 'profile_reservation_id', string='Profile ID')

    # Relation to Profiles (using the existing profile model)
    profile_ids = fields.One2many('reservation.reservations.profile', 'profile_reservation_id', string="Profiles")
    linked_profile_id = fields.Many2one('reservation.reservations.profile', string="Linked Profile ID")
    description = fields.Text(string="Description")

    inhouse_attributes = fields.Text(string="Attributes")


class Guest_Comments(models.Model):
    _name = 'guest_comments.guest_comments'
    _description = 'guest_comments.guest_comments'

    comment_id = fields.Char(string='Comment ID', readonly=True, copy=False, default='GC')  # Auto-generated field
    comment_category = fields.Char(string='Comment Category')
    room_number = fields.Integer(string= 'Room Number')
    description = fields.Text(string='Description')
    created_by = fields.Char(readonly=True)
    status = fields.Char(readonly=True)
    # user_text = fields.Text()
    # status_button  = fields.Char()

    # @api.model
    # def create(self, vals):
    #     # Generate sequence if attribute_id is 'New'
    #     if vals.get('comment_id', 'GC') == 'GC':
    #         vals['comment_id'] = self.env['ir.sequence'].next_by_code('guest_comments.comment_id') or 'GC'
    #     return super(Guest_Comments, self).create(vals)


class guest_locator(models.Model):
    _name = 'guest.locator'
    _description = 'Guest Locator'

    id = fields.Integer(string='ID')
    room_number = fields.Integer(string='Room Number', required=True)
    frm_date = fields.Datetime(string='From Date', default=fields.Datetime.now, required=True)
    to_date = fields.Datetime(string='To Date', required=True)
    user_text = fields.Text(string="Message")
    location = fields.Text(string='Location')
    status = fields.Selection(
        selection=[
            ('new', 'New'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('canceled', 'Canceled'),
        ],
        string="Status",
        readonly=True,
        default='new'
    )
    occurs_daily = fields.Boolean(string='Occurs Daily', default=False)

class TraceRecord(models.Model):
    _name = 'trace.record'
    _description = 'Trace Record'

    trace_id = fields.Char(string='ID#', required=True)
    from_department = fields.Selection([('maintenance', 'Maintenance'), ('front_desk', 'Front Desk')], string='From')
    target = fields.Selection([('front_desk', 'Front Desk'), ('reservation', 'Reservation')], string='Target')
    room_number = fields.Char(string='Room Number')
    guest = fields.Many2one('res.partner', string='Guest')
    message = fields.Text(string='Message')
    due_date = fields.Datetime(string='Due Date')
    end_date = fields.Datetime(string='End Date')
    recurring_daily = fields.Boolean(string='Recurring Daily')
    end_of_day = fields.Boolean(string='End of Day')
    status = fields.Selection([('in_process', 'In Process'), ('resolved', 'Resolved'), ('cancelled', 'Cancelled')], default='in_process', string='Status')
    user_id = fields.Many2one('res.users', string='User ID')
    opened_on = fields.Datetime(string='Opened On', default=fields.Datetime.now)

    # Define the button actions
    def action_resolved(self):
        self.status = 'resolved'

    def action_cancelled(self):
        self.status = 'cancelled'

    def action_amend(self):
        # Logic to amend the record, placeholder
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'trace.record',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }
    
class GuestMessage(models.Model):
    _name = 'guest.message'
    _description = 'Guest Messages'

    room_id = fields.Char(string='Room Number', required=True)
    from_person = fields.Char(string='From', required=True)
    contact_info = fields.Char(string='Contact Info')
    message = fields.Text(string='Message', required=True)
    user_text = fields.Text(string='User Text')
    status = fields.Selection([
        ('new', 'New'),
        ('open', 'Open'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='new', required=True)

    # Fixed default for Datetime field
    message_date = fields.Datetime(string='Message Date', default=lambda self: fields.Datetime.now(), required=True)

class HotelCompetitionEntry(models.Model):
    _name = 'hotel.competition.entry'
    _description = 'Hotel Competition Entry'

    entry_date = fields.Date(string='Date', required=True)

    def confirm_entry(self):
        # Define what should happen when the 'Ok' button is clicked
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def exit_entry(self):
        # Define what should happen when the 'Exit' button is clicked
        # This will close the form view
        return {'type': 'ir.actions.act_window_close'}