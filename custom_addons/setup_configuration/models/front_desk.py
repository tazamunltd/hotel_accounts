from odoo import _, models, fields,api
from odoo.exceptions import ValidationError

class ApplicationRoomType(models.Model):
    _name = 'application.room.type'

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True
    
    name = fields.Char(string="Application Room Type", required=True, tracking=True)
    description = fields.Char(string=_("Description"),tracking=True, translate=True)
    # company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, tracking=True)

class RoomType(models.Model):
    _name = 'room.type'
    _description = 'Room Type'
    _rec_name = 'room_type'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True

    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True, readonly=True)
    room_type = fields.Char(string=_("Hotel Room Type"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"),tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    generic_type = fields.Char(string=_("Generic Type"),tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)
    image_ids = fields.One2many('room.type.image', 'room_type_id', string="Images")
    application_room_type = fields.Many2one('application.room.type',string='Application Room Type')

class RoomTypeImage(models.Model):
    _name = 'room.type.image'
    _description = 'Room Type Images'

    room_type_id = fields.Many2one('room.type', string="Room Type", required=True, ondelete='cascade')
    image = fields.Binary(string="Image", attachment=True, help="Upload images for this room type")


class RoomSpecification(models.Model):
    _name = 'room.specification'
    _description = 'Room Specification'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Existing fields
    room_number = fields.Char(string=_("Room Number"), required=True,tracking=True, translate=True)
    door_sign = fields.Char(string=_("Door Sign"),tracking=True, translate=True)
    room_type = fields.Many2one('room.type', string='Room Type', required=True,tracking=True, translate=True)
    suite = fields.Boolean(string="Suite",tracking=True, translate=True)
    connected_room = fields.Char(string=_("Connected Room"),tracking=True, translate=True)
    type_of_bed = fields.Char(string=_("Type of Bed"),tracking=True, translate=True)
    type_of_bath = fields.Char(string=_("Type of Bath"),tracking=True, translate=True)
    floor = fields.Integer(string="Floor #",tracking=True)
    block = fields.Integer(string="Block",tracking=True)
    building = fields.Char(string=_("Building"),tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)

    # New fields for the Information tab
    pending_repairs = fields.Char(string=_("Pending Repairs"),tracking=True, translate=True)
    last_repairs = fields.Date(string="Last Repairs",tracking=True)
    room_description = fields.Text(string="Room Description",tracking=True)
    notes = fields.Text(string="Notes",tracking=True)

    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)
    no_smoking = fields.Boolean(string="No Smoking", default=False,tracking=True)
    max_pax = fields.Integer(string="Max Pax",tracking=True)
    section_hk = fields.Char(string=_("Section (H.K.)"),tracking=True, translate=True)
    telephone_ext = fields.Char(string=_("Telephone Ext."),tracking=True, translate=True)
    disability_features = fields.Char(string=_("Disability Features"),tracking=True, translate=True)
    extra_features = fields.Char(string=_("Extra Features"),tracking=True, translate=True)
    rate_code = fields.Char(string=_("Rate Code"),tracking=True, translate=True)
    rate_posting_item = fields.Char(string=_("Rate Posting Item"),tracking=True, translate=True)

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

class MealSubType(models.Model):
    _name = 'meal.code.sub.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True
    name = fields.Char(string="Main Meal Code", required=True, translate = True, tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, tracking=True)

class MealCode(models.Model):

    _name = 'meal.code'
    _description = 'Meal Code'
    _rec_name = 'meal_code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True


    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True)
    meal_code = fields.Char(string=_("Meal Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    # posting_item = fields.Char(string=_("Posting Item"),tracking=True)
    posting_item = fields.Many2one('posting.item',string="Posting Item", ondelete="cascade",tracking=True)
    price_pax = fields.Float(string="Price/Pax",tracking=True)
    price_child = fields.Float(string="Price/Child",tracking=True)
    @api.constrains('price_pax', 'price_child')
    def _check_prices(self):
        for record in self:
            if record.price_pax < 0:
                raise ValidationError("The Price cannot be less than 0.")
            if record.price_child < 0:
                raise ValidationError("The Child Price cannot be less than 0.")
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

    meal_code_sub_type = fields.Many2one('meal.code.sub.type', string="Main Meal Code", required=True,)
    # domain=lambda self: [
    #     ('company_id', '=', self.env.company.id)],)
    
    
class MealPatternSubType(models.Model):
    _name = 'meal.pattern.sub.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True
    name = fields.Char(string="Main Meal Pattern", required=True, tracking=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company, tracking=True)

class MealPattern(models.Model):
    _name = 'meal.pattern'
    _description = 'Meal Pattern'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    _rec_name = 'meal_pattern'

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        RoomBooking = self.env['room.booking']
        for record in self:
            # Search for room bookings linked to this meal pattern and check if they are in 'block' or 'check_in' state
            booking = RoomBooking.search([
                ('meal_pattern', '=', record.id),
                ('state', 'in', ['block', 'check_in'])
            ], limit=1) 
            
            if booking:
                raise ValidationError(
                    "You cannot delete the Meal Pattern '%s' because it is associated with bookings: '%s' in the following states: '%s'." %
                    (record.meal_pattern, booking.name, booking.state)
                )
            else:
                # If no conflicting bookings, archive the meal pattern (deactivate it)
                record.active = False



    # def action_delete_record(self):
    #     for record in self:
    #         record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True
    company_id = fields.Many2one('res.company', string="Hotel", default=lambda self: self.env.company, tracking=True)
    meal_pattern = fields.Char(string=_("Meal Pattern"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    # meal_posting_item = fields.Char(string=_("Meal Posting Item",tracking=True)
    meal_posting_item = fields.Many2one('posting.item',string="Meal Posting Item",ondelete="cascade", required=True, tracking=True)
    user_sort = fields.Integer(string="User Sort",tracking=True)
    meals_list_ids = fields.One2many('meal.list', 'meal_pattern_id', string="Meals List") #
    taxes = fields.Many2one('account.tax', string="Taxes",tracking=True)
    meal_pattern_sub_type = fields.Many2one('meal.pattern.sub.type', string="Main Meal Pattern ", required=True )
    # domain=lambda self: [
    #     ('company_id', '=', self.env.company.id)],)

class MealList(models.Model):
    _name = 'meal.list'
    _description = 'Meal List'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    line = fields.Integer(string="Line", required=True,tracking=True)
    meal_code = fields.Many2one('meal.code', string="Meal Code", required=True,tracking=True)
    name = fields.Char(string=_("Name"),tracking=True)
    quantity = fields.Integer(string="Quantity", default=1,tracking=True)
    apply_on_arrival = fields.Boolean(string="Apply on Arrival", default=False,tracking=True)
    apply_on_departure = fields.Boolean(string="Apply on Departure", default=False,tracking=True)
    apply_during_stay = fields.Boolean(string="Apply During Stay", default=False,tracking=True)
    meal_pattern_id = fields.Many2one('meal.pattern', string="Meal Pattern", ondelete='cascade',tracking=True)
    price = fields.Float(string="Price/Pax", related='meal_code.price_pax', store=True,  tracking=True)  # Add a field to store the price of the meal_code
    price_child = fields.Float(string="Price/Child",  related='meal_code.price_child', store=True,tracking=True)

    @api.model
    def create(self, vals):
        """Ensure price values are set on creation"""
        if 'meal_code' in vals:
            meal = self.env['meal.code'].browse(vals['meal_code'])
            vals['price'] = meal.price_pax or 0.0
            vals['price_child'] = meal.price_child or 0.0
        return super(MealList, self).create(vals)

    def write(self, vals):
        """Ensure price values are updated on write"""
        if 'meal_code' in vals:
            for record in self:
                meal = self.env['meal.code'].browse(vals['meal_code'])
                vals['price'] = meal.price_pax or 0.0
                vals['price_child'] = meal.price_child or 0.0
        return super(MealList, self).write(vals)

    @api.onchange('meal_code')
    def _onchange_meal_code(self):
        for record in self:
            if record.meal_code:
                # Fetch the price from the selected meal_code
                record.price = record.meal_code.price_pax  # Assuming `price_pax` is the field in `meal.code` that stores the price
                record.price_child = record.meal_code.price_child  # Assuming `price_child` exists in `meal.code`

class AuthorizedCode(models.Model):
    _name = 'authorized.code'
    _description = 'Authorized Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string=_("Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
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

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True

    _rec_name = 'code'
    code = fields.Char(string=_("Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
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
    _rec_name = 'code'

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True

    code = fields.Char(string=_("Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)

class RoomOnHoldCode(models.Model):
    _name = 'room.on.hold.code'
    _description = 'Room on Hold Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'code'

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True

    code = fields.Char(string=_("Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)


class VipCode(models.Model):
    _name = 'vip.code'
    _description = 'VIP Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True

    _rec_name = 'code'
    code = fields.Char(string=_("Code"), required=True, tracking=True)
    description = fields.Char(string=_("Description"),  translate=True, required=True, tracking=True)
    abbreviation = fields.Char(string=_("Abbreviation"), translate=True, tracking=True)
    level = fields.Integer(string="Level", default=0, tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False, tracking=True)

class HouseCode(models.Model):
    _name = 'house.code'
    _description = 'House Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True

    _rec_name = 'code'
    code = fields.Char(string=_("Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    level = fields.Integer(string="Level", default=0,tracking=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)


class SafeDepositCode(models.Model):
    _name = 'safe.deposit.code'
    _description = 'Safe Deposit Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string=_("Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    user_sort = fields.Integer(string="User Sort", default=0,tracking=True)
    obsolete = fields.Boolean(string="Obsolete", default=False,tracking=True)


class HotelCode(models.Model):
    _name = 'hotel.code'
    _description = 'Hotel Code'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string=_("Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
    number_of_rooms = fields.Integer(string="Number of Rooms",tracking=True)
    number_of_stars = fields.Integer(string="Number of Stars",tracking=True)
    notes = fields.Text(string="Notes",tracking=True)

class RentableAsset(models.Model):
    _name = 'rentable.asset'
    _description = 'Rentable Asset'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string=_("Code"), required=True,tracking=True, translate=True)
    description = fields.Char(string=_("Description"), required=True,tracking=True, translate=True)
    abbreviation = fields.Char(string=_("Abbreviation"),tracking=True, translate=True)
    arabic_description = fields.Char(string=_("Arabic Description"),tracking=True, translate=True)
    arabic_abbreviation = fields.Char(string=_("Arabic Abbreviation"),tracking=True, translate=True)
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
    posting_item = fields.Char(string=_("Posting Item"),tracking=True)
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

    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True

    extension_number = fields.Char(string=_("Telephone Extension"), required=True,tracking=True, translate=True)
    room_number = fields.Char(string=_("Room Number"), required=True,tracking=True, translate=True)
    comments = fields.Text(string="Comments",tracking=True)