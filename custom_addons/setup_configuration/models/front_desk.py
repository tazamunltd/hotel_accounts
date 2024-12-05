from odoo import models, fields


class RoomType(models.Model):
    _name = 'room.type'
    _description = 'Room Type'
    _rec_name = 'room_type'
    room_type = fields.Char(string="Room Type", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    generic_type = fields.Char(string="Generic Type")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

class RoomSpecification(models.Model):
    _name = 'room.specification'
    _description = 'Room Specification'

    # Existing fields
    room_number = fields.Char(string="Room Number", required=True)
    door_sign = fields.Char(string="Door Sign")
    room_type = fields.Many2one('room.type', string='Room Type', required=True)
    suite = fields.Boolean(string="Suite")
    connected_room = fields.Char(string="Connected Room")
    type_of_bed = fields.Char(string="Type of Bed")
    type_of_bath = fields.Char(string="Type of Bath")
    floor = fields.Integer(string="Floor #")
    block = fields.Integer(string="Block")
    building = fields.Char(string="Building")
    user_sort = fields.Integer(string="User Sort", default=0)

    # New fields for the Information tab
    pending_repairs = fields.Char(string="Pending Repairs")
    last_repairs = fields.Date(string="Last Repairs")
    room_description = fields.Text(string="Room Description")
    notes = fields.Text(string="Notes")

    obsolete = fields.Boolean(string="Obsolete", default=False)
    no_smoking = fields.Boolean(string="No Smoking", default=False)
    max_pax = fields.Integer(string="Max Pax")
    section_hk = fields.Char(string="Section (H.K.)")
    telephone_ext = fields.Char(string="Telephone Ext.")
    disability_features = fields.Char(string="Disability Features")
    extra_features = fields.Char(string="Extra Features")
    rate_code = fields.Char(string="Rate Code")
    rate_posting_item = fields.Char(string="Rate Posting Item")

    # Radio button fields
    count_in_statistics = fields.Selection([
        ('always', 'Always'),
        ('when_occupied', 'In Total & Occupied (When Occupied)'),
        ('only_occupied', 'Only Occupied'),
        ('never', 'Never')
    ], string="Count in Statistics", default="always")

    count_in_availability = fields.Selection([
        ('always', 'Always'),
        ('when_occupied', 'In Total & Occupied (When Occupied)'),
        ('only_occupied', 'Only Occupied'),
        ('never', 'Never')
    ], string="Count in Availability", default="always")

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

    meal_code = fields.Char(string="Meal Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    # posting_item = fields.Char(string="Posting Item")
    posting_item = fields.Many2one('posting.item',string="Posting Item", ondelete="cascade")
    price_pax = fields.Float(string="Price/Pax")
    price_child = fields.Float(string="Price/Child")
    price_infant = fields.Float(string="Price/Infant")
    user_sort = fields.Integer(string="User Sort")
    notes = fields.Text(string="Notes")
    
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
    ], string="Type", default="unspecified")
    


class MealPattern(models.Model):
    _name = 'meal.pattern'
    _description = 'Meal Pattern'

    _rec_name = 'meal_pattern'
    meal_pattern = fields.Char(string="Meal Pattern", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    # meal_posting_item = fields.Char(string="Meal Posting Item")
    meal_posting_item = fields.Many2one('posting.item',string="Meal Posting Item",ondelete="cascade")
    user_sort = fields.Integer(string="User Sort")
    meals_list_ids = fields.One2many('meal.list', 'meal_pattern_id', string="Meals List")
    taxes = fields.Many2one('account.tax', string="Taxes")

class MealList(models.Model):
    _name = 'meal.list'
    _description = 'Meal List'

    line = fields.Integer(string="Line", required=True)
    meal_code = fields.Many2one('meal.code', string="Meal Code", required=True)
    name = fields.Char(string="Name")
    quantity = fields.Integer(string="Quantity", default=1)
    apply_on_arrival = fields.Boolean(string="Apply on Arrival", default=False)
    apply_on_departure = fields.Boolean(string="Apply on Departure", default=False)
    apply_during_stay = fields.Boolean(string="Apply During Stay", default=False)
    meal_pattern_id = fields.Many2one('meal.pattern', string="Meal Pattern", ondelete='cascade')

class AuthorizedCode(models.Model):
    _name = 'authorized.code'
    _description = 'Authorized Code'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort")
    obsolete = fields.Boolean(string="Obsolete", default=False)

    # Checkboxes for authorization
    can_authorize_complimentary = fields.Boolean(string="Complimentary", default=False)
    can_authorize_vip = fields.Boolean(string="VIP", default=False)
    can_authorize_house_use = fields.Boolean(string="House Use", default=False)
    can_authorize_out_of_order = fields.Boolean(string="Out of Order", default=False)
    can_authorize_room_on_hold = fields.Boolean(string="Room on Hold", default=False)

class ComplimentaryCode(models.Model):
    _name = 'complimentary.code'
    _description = 'Complimentary Code'

    _rec_name = 'code'
    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)
    
    # Type Selection (Room, F&B, Both)
    type = fields.Selection([
        ('room', 'Room'),
        ('fb', 'F & B'),
        ('both', 'Both')
    ], string="Type", required=True, default="room")

class OutOfOrderCode(models.Model):
    _name = 'out.of.order.code'
    _description = 'Out of Order Code'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

class RoomOnHoldCode(models.Model):
    _name = 'room.on.hold.code'
    _description = 'Room on Hold Code'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)


class VipCode(models.Model):
    _name = 'vip.code'
    _description = 'VIP Code'

    _rec_name = 'code'
    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    level = fields.Integer(string="Level", default=0)
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

class HouseCode(models.Model):
    _name = 'house.code'
    _description = 'House Code'

    _rec_name = 'code'
    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    level = fields.Integer(string="Level", default=0)
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

class SafeDepositCode(models.Model):
    _name = 'safe.deposit.code'
    _description = 'Safe Deposit Code'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)


class HotelCode(models.Model):
    _name = 'hotel.code'
    _description = 'Hotel Code'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    number_of_rooms = fields.Integer(string="Number of Rooms")
    number_of_stars = fields.Integer(string="Number of Stars")
    notes = fields.Text(string="Notes")

class RentableAsset(models.Model):
    _name = 'rentable.asset'
    _description = 'Rentable Asset'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description", required=True)
    abbreviation = fields.Char(string="Abbreviation")
    arabic_description = fields.Char(string="Arabic Description")
    arabic_abbreviation = fields.Char(string="Arabic Abbreviation")
    obsolete = fields.Boolean(string="Obsolete", default=False)
    
    # Default Type options
    default_type = fields.Selection([
        ('unspecified', 'Unspecified'),
        ('outside_light', 'Outside Room - Light (e.g. Towel Cards)'),
        ('outside_managed', 'Outside Room - Managed (e.g. Boats)'),
        ('inside_room', 'Inside Room - Managed by HK (e.g. VCR)'),
        ('fixed_rent', 'Fixed/Rent Time (e.g. Ballroom)')
    ], string="Default Type", default="unspecified")

    rhythm = fields.Selection([
        ('manual', 'Manual'),
        ('auto_check_in', 'Automatically Activated by Check In')
    ], string="Rhythm", default="manual")
    
    create_as_with_guest = fields.Boolean(string="Create as (With Guest)", default=False)
    use_as_default_rent_notes = fields.Boolean(string="Use As Default Rent Notes", default=False)
    
    # Quantity and pricing information
    quantity_type = fields.Selection([
        ('none', 'None'),
        ('one_value', 'One Value'),
        ('per_room', 'Per Room'),
        ('per_person', 'Per Person')
    ], string="Quantity")
    
    default_quantity = fields.Integer(string="Def. Quantity", default=0)
    price = fields.Float(string="Price", default=0.0)
    posting_item = fields.Char(string="Posting Item")
    free = fields.Boolean(string="Free", default=False)
    
    # Return Check options
    return_check = fields.Selection([
        ('no_check', 'No Check'),
        ('before_cashier', 'Before Cashier Check Out'),
        ('before_room', 'Before Room Check Out'),
        ('upon_check_in', 'Upon Check In')
    ], string="Return Check", default="no_check")
    
    # Extra options
    per_pax = fields.Boolean(string="Pax", default=False)
    per_child = fields.Boolean(string="Child", default=False)
    per_infant = fields.Boolean(string="Infant", default=False)
    extra_bed = fields.Boolean(string="Extra Bed", default=False)
    notes = fields.Text(string="Notes")


class TelephoneExtension(models.Model):
    _name = 'telephone.extension'
    _description = 'Telephone Extension'

    extension_number = fields.Char(string="Telephone Extension", required=True)
    room_number = fields.Char(string="Room Number", required=True)
    comments = fields.Text(string="Comments")