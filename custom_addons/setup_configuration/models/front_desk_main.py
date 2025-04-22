from odoo import models, fields

class FrontDeskWalkinMain(models.Model):
    _name = 'frontdesk.walkin.main'
    _description = 'Front Desk Walk-in Main'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    guest_id = fields.Char(string="Guest ID",tracking=True)
    ref = fields.Char(string="Reference",tracking=True)
    last_name = fields.Char(string="Last Name",tracking=True)
    first_name = fields.Char(string="First Name",tracking=True)
    room_number = fields.Char(string="Room Number",tracking=True)
    room_type = fields.Selection([
        ('suite', 'Suite'),
        ('regular', 'Regular')
    ], string="Room Type",tracking=True)
    pax_room = fields.Integer(string="Pax/Room",tracking=True)
    smoking = fields.Boolean(string="Smoking",tracking=True)
    nights = fields.Integer(string="Nights",tracking=True)
    departure_date = fields.Datetime(string="Departure Date",tracking=True)
    rate_code = fields.Char(string="Rate Code",tracking=True)
    meal_pattern = fields.Char(string="Meal Pattern",tracking=True)
    profile_id = fields.Many2one('reservation.profile.main', string="Default Profile",tracking=True)
    nationality = fields.Char(string="Nationality",tracking=True)
    total_children = fields.Integer(string="Total Children",tracking=True)
    total_infants = fields.Integer(string="Total Infants",tracking=True)
    extra_beds = fields.Integer(string="Extra Beds",tracking=True)
    companions = fields.Integer(string="Companions",tracking=True)
    rate_value = fields.Float(string="Rate Value",tracking=True)
    meals_value = fields.Float(string="Meals Value",tracking=True)
    discount_rate = fields.Float(string="Discount on Rate (%,tracking=True)",tracking=True)
    discount_meals = fields.Float(string="Discount on Meals (%)",tracking=True)
    
    # Adult Information
    adult_ids = fields.One2many('reservation.adults', 'reservation_id') #
    child_ids = fields.One2many('reservation.childs', 'reservation_id')#
    infant_ids = fields.One2many('reservation.infants', 'reservation_id')#

    # Optional/Children Fields
    company = fields.Char(string="Company",tracking=True)
    source_of_business = fields.Char(string="Source of Business",tracking=True)
    vip_code = fields.Boolean(string="VIP Code",tracking=True)
    travel_method = fields.Selection([
        ('air', 'Air'),
        ('road', 'Road'),
        ('sea', 'Sea')
    ], string="Travel Method",tracking=True)
    visit_reason = fields.Selection([
        ('business', 'Business'),
        ('leisure', 'Leisure'),
    ], string="Visit Reason",tracking=True)
    sponsor = fields.Char(string="Sponsor",tracking=True)
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('credit', 'Credit (C/L)'),
        ('prepaid', 'Pre-Paid / Credit Limit'),
        ('other', 'Other Payment')
    ], string="Payment Type",tracking=True)
    credit_limit_value = fields.Float(string="Credit Limit Value",tracking=True)
    comments = fields.Text(string="Comments",tracking=True)
    
    # Children Information
    # children_ids = fields.One2many('frontdesk.walkin.child', 'walkin_id', string="Children")

    # Profiles/Infants Fields
    profile_ids = fields.One2many('reservation.reservations.profile', 'profile_reservation_id', string="Profiles")#
    linked_profile_id = fields.Many2one('reservation.profile', string="Linked Profile",tracking=True)
    description = fields.Text(string="Description",tracking=True)
    
    # Infants Information
    infant_ids = fields.One2many('reservation.infants', 'reservation_id', string="Infants",tracking=True)#

    front_desk_html = fields.Html(string="HTML",tracking=True)

class FrontDeskInHouseGuest(models.Model):
    _name = 'frontdesk.inhouse.guest.main'
    _description = 'In-House Guest'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    guest_id = fields.Char(string="Guest ID",tracking=True)
    ref = fields.Char(string="Reference",tracking=True)
    last_name = fields.Char(string="Last Name",tracking=True)
    first_name = fields.Char(string="First Name",tracking=True)
    room_number = fields.Char(string="Room Number",tracking=True)
    pax_room = fields.Integer(string="Pax/Room",tracking=True)
    no_of_rooms = fields.Integer(string="No. of Rooms",tracking=True)
    room_type = fields.Selection([
        ('suite', 'Suite'),
        ('regular', 'Regular')
    ], string="Room Type",tracking=True)
    smoking = fields.Boolean(string="No Smoking",tracking=True)
    rate_code = fields.Char(string="Rate Code",tracking=True)
    meal_pattern = fields.Char(string="Meal Pattern",tracking=True)
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
    ], string="Status Code", default='default',tracking=True)
    company = fields.Char(string="Company",tracking=True)
    nationality = fields.Char(string="Nationality",tracking=True)
    arrival_date = fields.Datetime(string="Arrival Date",tracking=True)
    departure_date = fields.Datetime(string="Departure Date",tracking=True)
    total_children = fields.Integer(string="Total Children",tracking=True)
    total_infants = fields.Integer(string="Total Infants",tracking=True)
    extra_beds = fields.Integer(string="Extra Beds",tracking=True)
    companions = fields.Integer(string="Companions",tracking=True)
    rate_value = fields.Float(string="Rate Value",tracking=True)
    meals_value = fields.Float(string="Meals Value",tracking=True)
    allotment = fields.Char(string="Allotment",tracking=True)
    discount_rate = fields.Float(string="Discount on Rate (%)",tracking=True)
    discount_meals = fields.Float(string="Discount on Meals (%)",tracking=True)
    remarks = fields.Text(string="Remark",tracking=True)
    source_of_business = fields.Char(string="Source of Business",tracking=True)
    market_segment = fields.Char(string="Market Segment",tracking=True)


    # Fields for "Optional" Page
    how_taken = fields.Selection([
        ('normal', 'Normal'),
        ('house_use', 'House Use')
    ], string="How Taken",tracking=True)
    travel_method = fields.Selection([
        ('air', 'Air'),
        ('road', 'Road'),
        ('sea', 'Sea')
    ], string="Travel Method")
    visit_reason = fields.Selection([
        ('business', 'Business'),
        ('leisure', 'Leisure'),
    ], string="Visit Reason",tracking=True)
    house_use = fields.Boolean(string="House Use",tracking=True)
    complimentary = fields.Boolean(string="Complimentary",tracking=True)
    vip_stay = fields.Boolean(string="Stay as VIP",tracking=True)

    # Payment Information
    payment_type = fields.Selection([
        ('cash', 'Cash Payment'),
        ('credit', 'Credit (C/L)'),
        ('prepaid', 'Pre-Paid / Credit Limit'),
        ('other', 'Other Payment')
    ], string="Payment Type",tracking=True)
    credit_limit_value = fields.Float(string="Credit Limit Value",tracking=True)
    comments = fields.Text(string="Comments",tracking=True)

    # Safe Box and Sponsor Information
    safe_box_code = fields.Char(string="Safe Box Code",tracking=True)
    voucher_received = fields.Boolean(string="Voucher Received?",tracking=True)
    deposit = fields.Float(string="Deposit",tracking=True)
    sponsor = fields.Char(string="Sponsor",tracking=True)
    reserved_by = fields.Char(string="Reserved By",tracking=True)

    adult_ids = fields.One2many('reservation.adults', 'reservation_id', string='Adults')#
    child_ids = fields.One2many('reservation.childs', 'reservation_id', string='Children')#
    infant_ids = fields.One2many('reservation.infants', 'reservation_id', string='Infants')#
    # profile_ids = fields.One2many('reservation.reservation.profile', 'profile_reservation_id', string='Profile ID')

    # Relation to Profiles (using the existing profile model)
    profile_ids = fields.One2many('reservation.reservations.profile', 'profile_reservation_id', string="Profiles")#
    linked_profile_id = fields.Many2one('reservation.reservations.profile', string="Linked Profile ID",tracking=True)
    description = fields.Text(string="Description",tracking=True)

    inhouse_attributes = fields.Text(string="Attributes",tracking=True)


class Guest_Comments(models.Model):
    _name = 'guest_comments.guest_comments'
    _description = 'guest_comments.guest_comments'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    comment_id = fields.Char(string='Comment ID', readonly=True, copy=False, default='GC',tracking=True)  # Auto-generated field
    comment_category = fields.Char(string='Comment Category',tracking=True)
    room_number = fields.Integer(string= 'Room Number',tracking=True)
    description = fields.Text(string='Description',tracking=True)
    created_by = fields.Char(readonly=True,tracking=True)
    status = fields.Char(readonly=True,tracking=True)
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
    _inherit = ['mail.thread', 'mail.activity.mixin']

    id = fields.Integer(string='ID',tracking=True)
    room_number = fields.Integer(string='Room Number', required=True,tracking=True)
    frm_date = fields.Datetime(string='From Date', default=fields.Datetime.now, required=True,tracking=True)
    to_date = fields.Datetime(string='To Date', required=True,tracking=True)
    user_text = fields.Text(string="Message",tracking=True)
    location = fields.Text(string='Location',tracking=True)
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
    ,tracking=True)
    occurs_daily = fields.Boolean(string='Occurs Daily', default=False,tracking=True)

class TraceRecord(models.Model):
    _name = 'trace.record'
    _description = 'Trace Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    trace_id = fields.Char(string='ID#', required=True,tracking=True)
    from_department = fields.Selection([('maintenance', 'Maintenance'), ('front_desk', 'Front Desk')], string='From',tracking=True)
    target = fields.Selection([('front_desk', 'Front Desk'), ('reservation', 'Reservation')], string='Target',tracking=True)
    room_number = fields.Char(string='Room Number',tracking=True)
    guest = fields.Many2one('res.partner', string='Guest',tracking=True)
    message = fields.Text(string='Message',tracking=True)
    due_date = fields.Datetime(string='Due Date',tracking=True)
    end_date = fields.Datetime(string='End Date',tracking=True)
    recurring_daily = fields.Boolean(string='Recurring Daily',tracking=True)
    end_of_day = fields.Boolean(string='End of Day',tracking=True)
    status = fields.Selection([('in_process', 'In Process'), ('resolved', 'Resolved'), ('cancelled', 'Cancelled')], default='in_process', string='Status',tracking=True)
    user_id = fields.Many2one('res.users', string='User ID',tracking=True)
    opened_on = fields.Datetime(string='Opened On', default=fields.Datetime.now,tracking=True)

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
    _inherit = ['mail.thread', 'mail.activity.mixin']

    room_id = fields.Char(string='Room Number', required=True,tracking=True)
    from_person = fields.Char(string='From', required=True,tracking=True)
    contact_info = fields.Char(string='Contact Info',tracking=True)
    message = fields.Text(string='Message', required=True,tracking=True)
    user_text = fields.Text(string='User Text',tracking=True)
    status = fields.Selection([
        ('new', 'New'),
        ('open', 'Open'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='new', required=True,tracking=True)

    # Fixed default for Datetime field
    message_date = fields.Datetime(string='Message Date', default=lambda self: fields.Datetime.now(), required=True,tracking=True)

class HotelCompetitionEntry(models.Model):
    _name = 'hotel.competition.entry'
    _description = 'Hotel Competition Entry'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    entry_date = fields.Date(string='Date', required=True,tracking=True)

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