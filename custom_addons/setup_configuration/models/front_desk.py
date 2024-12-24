from odoo import models, fields


class RoomType(models.Model):
    _name = 'room.type'
    _description = 'Room Type'
    _rec_name = 'room_type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    

    room_type = fields.Char(string="Room Type", required=True,tracking=True)
    description = fields.Char(string="Description",tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    generic_type = fields.Char(string="Generic Type",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

class RoomSpecification(models.Model):
    _name = 'room.specification'
    _description = 'Room Specification'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Existing fields
    room_number = fields.Char(string="Room Number", required=True,tracking=True)
    door_sign = fields.Char(string="Door Sign",tracking=True)
    room_type = fields.Many2one('room.type', string='Room Type', required=True,tracking=True)
    suite = fields.Boolean(string="Suite",tracking=True)
    connected_room = fields.Char(string="Connected Room",tracking=True)
    type_of_bed = fields.Char(string="Type of Bed",tracking=True)
    type_of_bath = fields.Char(string="Type of Bath",tracking=True)
    floor = fields.Integer(string="Floor #",tracking=True)
    block = fields.Integer(string="Block",tracking=True)
    building = fields.Char(string="Building",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)

    # New fields for the Information tab
    pending_repairs = fields.Char(string="Pending Repairs",tracking=True)
    last_repairs = fields.Date(string="Last Repairs",tracking=True)
    room_description = fields.Text(string="Room Description",tracking=True)
    notes = fields.Text(string="Notes",tracking=True)

    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)
    no_smoking = fields.Boolean(string="No Smoking", default=False,tracking=True)
    max_pax = fields.Integer(string="Max Pax",tracking=True)
    section_hk = fields.Char(string="Section (H.K.,tracking=True)",tracking=True)
    telephone_ext = fields.Char(string="Telephone Ext.",tracking=True)
    disability_features = fields.Char(string="Disability Features",tracking=True)
    extra_features = fields.Char(string="Extra Features",tracking=True)
    rate_code = fields.Char(string="Rate Code",tracking=True)
    rate_posting_item = fields.Char(string="Rate Posting Item",tracking=True)

    # Radio button fields
    count_in_statistics = fields.Selection([
        ('always', 'Always'),
        ('when_occupied', 'In Total & Occupied (When Occupied)'),
        ('only_occupied', 'Only Occupied'),
        ('never', 'Never')
    ], string="Count in Statistics", default="always",tracking=True)

    count_in_availability = fields.Selection([
        ('always', 'Always'),
        ('when_occupied', 'In Total & Occupied (When Occupied)'),
        ('only_occupied', 'Only Occupied'),
        ('never', 'Never')
    ], string="Count in Availability", default="always",tracking=True)

    # Placeholder for floor plan action
    def action_view_floor_plan(self):
        # Logic for viewing floor plan
        return {
            'type': 'ir.actions.act_url',
            'url': '/web#action=floor_plan_action',  # Example link to a floor plan view
            'target': 'new'
        }
    
class MealCode(models.Model):

    _name = 'meal.code'
    _description = 'Meal Code'
    _rec_name = 'meal_code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    meal_code = fields.Char(string="Meal Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    # posting_item = fields.Char(string="Posting Item",tracking=True)
    posting_item = fields.Many2one('posting.item',string="Posting Item", ondelete="cascade",tracking=True)
    price_pax = fields.Float(string="Price/Pax",tracking=True)
    price_child = fields.Float(string="Price/Child",tracking=True)
    price_infant = fields.Float(string="Price/Infant",tracking=True)
    user_sort = fields.Integer(string="User Sort",tracking=True)
    notes = fields.Text(string="Notes",tracking=True)
    
    type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('breakfast', 'Breakfast'),
        ('brunch', 'Brunch'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
        ('supper', 'Supper'),
        ('snack', 'Snack'),
        ('iftar', 'Iftar'),
        ('sohor', 'Sohor'),
    ], string="Type", default="unspecified",tracking=True)
    


class MealPattern(models.Model):
    _name = 'meal.pattern'
    _description = 'Meal Pattern'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'meal_pattern'
    meal_pattern = fields.Char(string="Meal Pattern", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    # meal_posting_item = fields.Char(string="Meal Posting Item",tracking=True)
    meal_posting_item = fields.Many2one('posting.item',string="Meal Posting Item",ondelete="cascade",tracking=True)
    user_sort = fields.Integer(string="User Sort",tracking=True)
    meals_list_ids = fields.One2many('meal.list', 'meal_pattern_id', string="Meals List") #
    taxes = fields.Many2one('account.tax', string="Taxes",tracking=True)

class MealList(models.Model):
    _name = 'meal.list'
    _description = 'Meal List'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    line = fields.Integer(string="Line", required=True,tracking=True)
    meal_code = fields.Many2one('meal.code', string="Meal Code", required=True,tracking=True)
    name = fields.Char(string="Name",tracking=True)
    quantity = fields.Integer(string="Quantity", default=1,tracking=True)
    apply_on_arrival = fields.Boolean(string="Apply on Arrival", default=False,tracking=True)
    apply_on_departure = fields.Boolean(string="Apply on Departure", default=False,tracking=True)
    apply_during_stay = fields.Boolean(string="Apply During Stay", default=False,tracking=True)
    meal_pattern_id = fields.Many2one('meal.pattern', string="Meal Pattern", ondelete='cascade',tracking=True)

class AuthorizedCode(models.Model):
    _name = 'authorized.code'
    _description = 'Authorized Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort",tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

    # Checkboxes for authorization
    can_authorize_complimentary = fields.Boolean(string="Complimentary", default=False,tracking=True)
    can_authorize_vip = fields.Boolean(string="VIP", default=False,tracking=True)
    can_authorize_house_use = fields.Boolean(string="House Use", default=False,tracking=True)
    can_authorize_out_of_order = fields.Boolean(string="Out of Order", default=False,tracking=True)
    can_authorize_room_on_hold = fields.Boolean(string="Room on Hold", default=False,tracking=True)

class ComplimentaryCode(models.Model):
    _name = 'complimentary.code'
    _description = 'Complimentary Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'code'
    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)
    
    # Type Selection (Room, F&B, Both,tracking=True)
    type = fields.Selection([
        ('room', 'Room'),
        ('fb', 'F & B'),
        ('both', 'Both')
    ], string="Type", required=True, default="room",tracking=True)

class OutOfOrderCode(models.Model):
    _name = 'out.of.order.code'
    _description = 'Out of Order Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

class RoomOnHoldCode(models.Model):
    _name = 'room.on.hold.code'
    _description = 'Room on Hold Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)


class VipCode(models.Model):
    _name = 'vip.code'
    _description = 'VIP Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'code'
    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    level = fields.Integer(string="Level", default=0,tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

class HouseCode(models.Model):
    _name = 'house.code'
    _description = 'House Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'code'
    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    level = fields.Integer(string="Level", default=0,tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

class SafeDepositCode(models.Model):
    _name = 'safe.deposit.code'
    _description = 'Safe Deposit Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)


class HotelCode(models.Model):
    _name = 'hotel.code'
    _description = 'Hotel Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    number_of_rooms = fields.Integer(string="Number of Rooms",tracking=True)
    number_of_stars = fields.Integer(string="Number of Stars",tracking=True)
    notes = fields.Text(string="Notes",tracking=True)

class RentableAsset(models.Model):
    _name = 'rentable.asset'
    _description = 'Rentable Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string="Code", required=True,tracking=True)
    description = fields.Char(string="Description", required=True,tracking=True)
    abbreviation = fields.Char(string="Abbreviation",tracking=True)
    arabic_description = fields.Char(string="Arabic Description",tracking=True)
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation",tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)
    
    # Default Type options
    default_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('outside_light', 'Outside Room - Light (e.g. Towel Cards)'),
        ('outside_managed', 'Outside Room - Managed (e.g. Boats)'),
        ('inside_room', 'Inside Room - Managed by HK (e.g. VCR)'),
        ('fixed_rent', 'Fixed/Rent Time (e.g. Ballroom)')
    ], string="Default Type", default="unspecified",tracking=True)

    rhythm = fields.Selection([
        ('manual', 'Manual'),
        ('auto_check_in', 'Automatically Activated by Check In')
    ], string="Rhythm", default="manual",tracking=True)
    
    create_as_with_guest = fields.Boolean(string="Create as (With Guest)", default=False,tracking=True)
    use_as_default_rent_notes = fields.Boolean(string="Use As Default Rent Notes", default=False,tracking=True)
    
    # Quantity and pricing information
    quantity_type = fields.Selection([
        ('none', 'None'),
        ('one_value', 'One Value'),
        ('per_room', 'Per Room'),
        ('per_person', 'Per Person')
    ], string="Quantity",tracking=True)
    
    default_quantity = fields.Integer(string="Def. Quantity", default=0,tracking=True)
    price = fields.Float(string="Price", default=0.0,tracking=True)
    posting_item = fields.Char(string="Posting Item",tracking=True)
    free = fields.Boolean(string="Free", default=False,tracking=True)
    
    # Return Check options
    return_check = fields.Selection([
        ('no_check', 'No Check'),
        ('before_cashier', 'Before Cashier Check Out'),
        ('before_room', 'Before Room Check Out'),
        ('upon_check_in', 'Upon Check In')
    ], string="Return Check", default="no_check",tracking=True)
    
    # Extra options
    per_pax = fields.Boolean(string="Pax", default=False,tracking=True)
    per_child = fields.Boolean(string="Child", default=False,tracking=True)
    per_infant = fields.Boolean(string="Infant", default=False,tracking=True)
    extra_bed = fields.Boolean(string="Extra Bed", default=False,tracking=True)
    notes = fields.Text(string="Notes",tracking=True)


class TelephoneExtension(models.Model):
    _name = 'telephone.extension'
    _description = 'Telephone Extension'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    extension_number = fields.Char(string="Telephone Extension", required=True,tracking=True)
    room_number = fields.Char(string="Room Number", required=True,tracking=True)
    comments = fields.Text(string="Comments",tracking=True)