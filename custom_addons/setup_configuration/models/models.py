from odoo import _, api, models, fields

class HotelDetails(models.Model):
    _name = 'system.configuration'
    _description = 'Hotel Details'

    hotel_name = fields.Char('Hotel Name')
    address = fields.Char(string='Address')
    contact_info = fields.Char(string='Contact Info')


class SystemConfig(models.Model):
    _name = 'system.config'
    _description = 'System Configuration'

    system_configuration_id = fields.Char('System Configuration ID')
    pms_integration_id = fields.Char('PMS Integration ID')
    accounting_integration_id = fields.Char('Accounting Integration ID')
    booking_integration_id = fields.Char('Booking.com Integration ID')


class SystemLanguagesUI(models.Model):
    _name = 'system.languages.ui'
    _description = 'Languages and UI'

    language_id = fields.Many2one('res.lang', string='Language')
    ui_theme = fields.Char('UI Theme')


# class SystemPaymentCurrencies(models.Model):
#     _name = 'system.payment.currencies'
#     _description = 'Payment and Currencies'

#     currency = fields.Char('Currency')
#     payment_gateway = fields.Char('Payment Gateway')

# class SystemCategories(models.Model):
#     _name = 'system.categories'
#     _description = 'Categories'

#     category_name = fields.Char('Category Name')
#     description = fields.Text('Description')

class RateCategory(models.Model):
    _name = 'rate.category'
    _description = 'Rate Category'

    _rec_name = 'category'
    category = fields.Char(string='Category', required=True)
    description = fields.Char(string='Description', required=True)
    abbreviation = fields.Char(string='Abbreviation', required=True)
    user_sort = fields.Integer(string='User Sort', default=0)

class RateCode(models.Model):
    _name = 'rate.code'
    _description = 'Rate Code Management'

    rate_detail_ids = fields.One2many('rate.detail', 'rate_code_id', string="Rate Details")

    _rec_name = 'code'
    code = fields.Char(string='Rate Code', required=True)
    description = fields.Char(string='Description', required=True)
    abbreviation = fields.Char(string='Abbreviation')
    arabic_desc = fields.Char(string='Arabic Description')
    arabic_abbr = fields.Char(string='Arabic Abbreviation')
    rate_code_category_id = fields.Many2one('rate.category', string='Category', required=True)
    rate_posting_item = fields.Many2one('posting.item', string='Rate Posting Item')
    currency_id = fields.Many2one('res.currency', string='Currency')
    include_meals = fields.Boolean(string='Include Meals in Posting Item')
    user_sort = fields.Integer(string='User Sort', default=0)
    obsolete = fields.Boolean(string='Obsolete')

    room_type_id = fields.Many2one('room.type', string="Room Type")
    

    rhythm = fields.Selection([
        ('every_night', 'Every Night'),
        ('after_change_date', 'After Change Date'),
        ('upon_check_out', 'Upon Check Out')
    ], string="Rhythm")

    exchange_rate = fields.Selection([
        ('fixed', 'Fixed (As it was on arrival)'),
        ('variable', 'Variable (Evaluated daily)')
    ], string="Exchange Rate")

    # Date fields for rate details
    rate_details = fields.One2many('rate.detail', 'rate_code_id', string="Rate Details")


        # Method for "Edit Details" button
    def action_rate_code_details(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Rate Details',
            'res_model': 'rate.detail',
            'view_mode': 'tree,form',  # Show the tree view first, and allow form view when a record is selected
            'view_type': 'form',
            'target': 'current',  # Use 'current' instead of 'new' to show the full tree and form view
            'context': {
                'default_rate_code_id': self.id,
            },
            'domain': [('rate_code_id', '=', self.id)]
        }


class RateDetail(models.Model):
    _name = 'rate.detail'
    _description = 'Rate Details'

    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    rate_code_id = fields.Many2one('rate.code', string="Rate Code")

    # Room Prices for different configurations (1 Pax, 2 Pax, etc.)
    default_price = fields.Float(string="Default")
    monday_price = fields.Float(string="Monday")
    tuesday_price = fields.Float(string="Tuesday")
    wednesday_price = fields.Float(string="Wednesday")
    thursday_price = fields.Float(string="Thursday")
    friday_price = fields.Float(string="Friday")
    saturday_price = fields.Float(string="Saturday")
    sunday_price = fields.Float(string="Sunday")

    pax_1 = fields.Float(string="1 Pax")
    pax_2 = fields.Float(string="2 Pax")
    pax_3 = fields.Float(string="3 Pax")
    pax_4 = fields.Float(string="4 Pax")
    pax_5 = fields.Float(string="5 Pax")
    pax_6 = fields.Float(string="6 Pax")
    extra_bed = fields.Float(string="Extra Bed")
    suite_supl = fields.Float(string="Suite Supl")

    # Pax Rates for Default
    # default_pax_1 = fields.Float(string="1 Pax (Default)")
    # default_pax_2 = fields.Float(string="2 Pax (Default)")
    # default_pax_3 = fields.Float(string="3 Pax (Default)")
    # default_pax_4 = fields.Float(string="4 Pax (Default)")
    # default_pax_5 = fields.Float(string="5 Pax (Default)")
    # default_pax_6 = fields.Float(string="6 Pax (Default)")

    # Pax Rates for Monday
    monday_pax_1 = fields.Float(string="1 Pax (Monday)")
    monday_pax_2 = fields.Float(string="2 Pax (Monday)")
    monday_pax_3 = fields.Float(string="3 Pax (Monday)")
    monday_pax_4 = fields.Float(string="4 Pax (Monday)")
    monday_pax_5 = fields.Float(string="5 Pax (Monday)")
    monday_pax_6 = fields.Float(string="6 Pax (Monday)")

    # Pax Rates for Tuesday
    tuesday_pax_1 = fields.Float(string="1 Pax (Tuesday)")
    tuesday_pax_2 = fields.Float(string="2 Pax (Tuesday)")
    tuesday_pax_3 = fields.Float(string="3 Pax (Tuesday)")
    tuesday_pax_4 = fields.Float(string="4 Pax (Tuesday)")
    tuesday_pax_5 = fields.Float(string="5 Pax (Tuesday)")
    tuesday_pax_6 = fields.Float(string="6 Pax (Tuesday)")

    # Pax Rates for Wednesday
    wednesday_pax_1 = fields.Float(string="1 Pax (Wednesday)")
    wednesday_pax_2 = fields.Float(string="2 Pax (Wednesday)")
    wednesday_pax_3 = fields.Float(string="3 Pax (Wednesday)")
    wednesday_pax_4 = fields.Float(string="4 Pax (Wednesday)")
    wednesday_pax_5 = fields.Float(string="5 Pax (Wednesday)")
    wednesday_pax_6 = fields.Float(string="6 Pax (Wednesday)")

    # Pax Rates for Thursday
    thursday_pax_1 = fields.Float(string="1 Pax (Thursday)")
    thursday_pax_2 = fields.Float(string="2 Pax (Thursday)")
    thursday_pax_3 = fields.Float(string="3 Pax (Thursday)")
    thursday_pax_4 = fields.Float(string="4 Pax (Thursday)")
    thursday_pax_5 = fields.Float(string="5 Pax (Thursday)")
    thursday_pax_6 = fields.Float(string="6 Pax (Thursday)")

    # Pax Rates for Friday
    friday_pax_1 = fields.Float(string="1 Pax (Friday)")
    friday_pax_2 = fields.Float(string="2 Pax (Friday)")
    friday_pax_3 = fields.Float(string="3 Pax (Friday)")
    friday_pax_4 = fields.Float(string="4 Pax (Friday)")
    friday_pax_5 = fields.Float(string="5 Pax (Friday)")
    friday_pax_6 = fields.Float(string="6 Pax (Friday)")

    # Pax Rates for Saturday
    saturday_pax_1 = fields.Float(string="1 Pax (Saturday)")
    saturday_pax_2 = fields.Float(string="2 Pax (Saturday)")
    saturday_pax_3 = fields.Float(string="3 Pax (Saturday)")
    saturday_pax_4 = fields.Float(string="4 Pax (Saturday)")
    saturday_pax_5 = fields.Float(string="5 Pax (Saturday)")
    saturday_pax_6 = fields.Float(string="6 Pax (Saturday)")

    # Pax Rates for Sunday
    sunday_pax_1 = fields.Float(string="1 Pax (Sunday)")
    sunday_pax_2 = fields.Float(string="2 Pax (Sunday)")
    sunday_pax_3 = fields.Float(string="3 Pax (Sunday)")
    sunday_pax_4 = fields.Float(string="4 Pax (Sunday)")
    sunday_pax_5 = fields.Float(string="5 Pax (Sunday)")
    sunday_pax_6 = fields.Float(string="6 Pax (Sunday)")

    monday_checkbox = fields.Boolean(string="Apply Default for Monday")
    tuesday_checkbox = fields.Boolean(string="Apply Default for Tuesday")
    wednesday_checkbox = fields.Boolean(string="Apply Default for Wednesday")
    thursday_checkbox = fields.Boolean(string="Apply Default for Thursday")
    friday_checkbox = fields.Boolean(string="Apply Default for Friday")
    saturday_checkbox = fields.Boolean(string="Apply Default for Saturday")
    sunday_checkbox = fields.Boolean(string="Apply Default for Sunday")

    # Onchange methods for each checkbox
    @api.onchange('monday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6')
    def _onchange_monday_checkbox(self):
        if self.monday_checkbox:
            self.monday_pax_1 = self.pax_1
            self.monday_pax_2 = self.pax_2
            self.monday_pax_3 = self.pax_3
            self.monday_pax_4 = self.pax_4
            self.monday_pax_5 = self.pax_5
            self.monday_pax_6 = self.pax_6

    @api.onchange('tuesday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6')
    def _onchange_tuesday_checkbox(self):
        if self.tuesday_checkbox:
            self.tuesday_pax_1 = self.pax_1
            self.tuesday_pax_2 = self.pax_2
            self.tuesday_pax_3 = self.pax_3
            self.tuesday_pax_4 = self.pax_4
            self.tuesday_pax_5 = self.pax_5
            self.tuesday_pax_6 = self.pax_6

    @api.onchange('wednesday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6')
    def _onchange_wednesday_checkbox(self):
        if self.wednesday_checkbox:
            self.wednesday_pax_1 = self.pax_1
            self.wednesday_pax_2 = self.pax_2
            self.wednesday_pax_3 = self.pax_3
            self.wednesday_pax_4 = self.pax_4
            self.wednesday_pax_5 = self.pax_5
            self.wednesday_pax_6 = self.pax_6

    @api.onchange('thursday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6')
    def _onchange_thursday_checkbox(self):
        if self.thursday_checkbox:
            self.thursday_pax_1 = self.pax_1
            self.thursday_pax_2 = self.pax_2
            self.thursday_pax_3 = self.pax_3
            self.thursday_pax_4 = self.pax_4
            self.thursday_pax_5 = self.pax_5
            self.thursday_pax_6 = self.pax_6

    @api.onchange('friday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6')
    def _onchange_friday_checkbox(self):
        if self.friday_checkbox:
            self.friday_pax_1 = self.pax_1
            self.friday_pax_2 = self.pax_2
            self.friday_pax_3 = self.pax_3
            self.friday_pax_4 = self.pax_4
            self.friday_pax_5 = self.pax_5
            self.friday_pax_6 = self.pax_6

    @api.onchange('saturday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6')
    def _onchange_saturday_checkbox(self):
        if self.saturday_checkbox:
            self.saturday_pax_1 = self.pax_1
            self.saturday_pax_2 = self.pax_2
            self.saturday_pax_3 = self.pax_3
            self.saturday_pax_4 = self.pax_4
            self.saturday_pax_5 = self.pax_5
            self.saturday_pax_6 = self.pax_6

    @api.onchange('sunday_checkbox', 'pax_1', 'pax_2', 'pax_3', 'pax_4', 'pax_5', 'pax_6')
    def _onchange_sunday_checkbox(self):
        if self.sunday_checkbox:
            self.sunday_pax_1 = self.pax_1
            self.sunday_pax_2 = self.pax_2
            self.sunday_pax_3 = self.pax_3
            self.sunday_pax_4 = self.pax_4
            self.sunday_pax_5 = self.pax_5
            self.sunday_pax_6 = self.pax_6


    # Price Type and Meal Pattern Fields
    price_type = fields.Selection([
        ('rate_only', 'Rate Only'),
        ('rate_meals', 'Rate and Meals Price'),
        ('room_only', 'Room Only')
    ], string="Price Type")

    meal_pattern_id = fields.Many2one('meal.pattern', string="Meal Pattern")

    def action_set_room_type_rate(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Room Type Specific Rate',
            'res_model': 'room.type.specific.rate',
            'view_mode': 'tree,form',  # Show the tree view first, and allow form view when a record is selected
            'view_type': 'form',
            'target': 'current',  # Use 'current' instead of 'new' to show the full tree and form view
            'context': {
                'default_rate_code_id': self.id,
            },
            'domain': [('rate_code_id', '=', self.id)]
        }

    def action_set_room_number_rate(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Room Number Specific Rate',
            'res_model': 'room.number.specific.rate',
            'view_mode': 'tree,form',  # Show the tree view first, and allow form view when a record is selected
            'view_type': 'form',
            'target': 'current',  # Use 'current' instead of 'new' to show the full tree and form view
            'context': {
                'default_rate_code_id': self.id,
            },
            'domain': [('rate_code_id', '=', self.id)]
        }

class RoomTypeSpecificRate(models.Model):
    _name = 'room.type.specific.rate'
    _description = 'Room Type Specific Rate'

    # Fields for Room Type Specific Rate Model
    rate_code_id = fields.Many2one('rate.code', string="Rate Code", required=True)
    from_date = fields.Date(string="From Date", required=True)
    to_date = fields.Date(string="To Date", required=True)
    room_type_id = fields.Many2one('room.type', string="Room Type", required=True)

    # Fields for Weekday Rates
    room_type_monday_pax_1 = fields.Float(string="Monday 1 Pax")
    room_type_monday_pax_2 = fields.Float(string="Monday 2 Pax")
    room_type_monday_pax_3 = fields.Float(string="Monday 3 Pax")
    room_type_monday_pax_4 = fields.Float(string="Monday 4 Pax")
    room_type_monday_pax_5 = fields.Float(string="Monday 5 Pax")
    room_type_monday_pax_6 = fields.Float(string="Monday 6 Pax")

    room_type_tuesday_pax_1 = fields.Float(string="Tuesday 1 Pax")
    room_type_tuesday_pax_2 = fields.Float(string="Tuesday 2 Pax")
    room_type_tuesday_pax_3 = fields.Float(string="Tuesday 3 Pax")
    room_type_tuesday_pax_4 = fields.Float(string="Tuesday 4 Pax")
    room_type_tuesday_pax_5 = fields.Float(string="Tuesday 5 Pax")
    room_type_tuesday_pax_6 = fields.Float(string="Tuesday 6 Pax")

    room_type_wednesday_pax_1 = fields.Float(string="Wednesday 1 Pax")
    room_type_wednesday_pax_2 = fields.Float(string="Wednesday 2 Pax")
    room_type_wednesday_pax_3 = fields.Float(string="Wednesday 3 Pax")
    room_type_wednesday_pax_4 = fields.Float(string="Wednesday 4 Pax")
    room_type_wednesday_pax_5 = fields.Float(string="Wednesday 5 Pax")
    room_type_wednesday_pax_6 = fields.Float(string="Wednesday 6 Pax")

    room_type_thursday_pax_1 = fields.Float(string="Thursday 1 Pax")
    room_type_thursday_pax_2 = fields.Float(string="Thursday 2 Pax")
    room_type_thursday_pax_3 = fields.Float(string="Thursday 3 Pax")
    room_type_thursday_pax_4 = fields.Float(string="Thursday 4 Pax")
    room_type_thursday_pax_5 = fields.Float(string="Thursday 5 Pax")
    room_type_thursday_pax_6 = fields.Float(string="Thursday 6 Pax")

    room_type_friday_pax_1 = fields.Float(string="Friday 1 Pax")
    room_type_friday_pax_2 = fields.Float(string="Friday 2 Pax")
    room_type_friday_pax_3 = fields.Float(string="Friday 3 Pax")
    room_type_friday_pax_4 = fields.Float(string="Friday 4 Pax")
    room_type_friday_pax_5 = fields.Float(string="Friday 5 Pax")
    room_type_friday_pax_6 = fields.Float(string="Friday 6 Pax")

    room_type_saturday_pax_1 = fields.Float(string="Saturday 1 Pax")
    room_type_saturday_pax_2 = fields.Float(string="Saturday 2 Pax")
    room_type_saturday_pax_3 = fields.Float(string="Saturday 3 Pax")
    room_type_saturday_pax_4 = fields.Float(string="Saturday 4 Pax")
    room_type_saturday_pax_5 = fields.Float(string="Saturday 5 Pax")
    room_type_saturday_pax_6 = fields.Float(string="Saturday 6 Pax")

    room_type_sunday_pax_1 = fields.Float(string="Sunday 1 Pax")
    room_type_sunday_pax_2 = fields.Float(string="Sunday 2 Pax")
    room_type_sunday_pax_3 = fields.Float(string="Sunday 3 Pax")
    room_type_sunday_pax_4 = fields.Float(string="Sunday 4 Pax")
    room_type_sunday_pax_5 = fields.Float(string="Sunday 5 Pax")
    room_type_sunday_pax_6 = fields.Float(string="Sunday 6 Pax")

    monday_checkbox_rt = fields.Boolean(string="Apply Default for Monday")
    tuesday_checkbox_rt = fields.Boolean(string="Apply Default for Tuesday")
    wednesday_checkbox_rt = fields.Boolean(string="Apply Default for Wednesday")
    thursday_checkbox_rt = fields.Boolean(string="Apply Default for Thursday")
    friday_checkbox_rt = fields.Boolean(string="Apply Default for Friday")
    saturday_checkbox_rt = fields.Boolean(string="Apply Default for Saturday")
    sunday_checkbox_rt = fields.Boolean(string="Apply Default for Sunday")

    # Room Prices for different configurations
    pax_1 = fields.Float(string="1 Pax")
    pax_2 = fields.Float(string="2 Pax")
    pax_3 = fields.Float(string="3 Pax")
    pax_4 = fields.Float(string="4 Pax")
    pax_5 = fields.Float(string="5 Pax")
    pax_6 = fields.Float(string="6 Pax")

    # Onchange methods for each checkbox
    @api.onchange('monday_checkbox_rt')
    def _onchange_monday_checkbox_rt(self):
        if self.monday_checkbox_rt:
            self.room_type_monday_pax_1 = self.pax_1
            self.room_type_monday_pax_2 = self.pax_2
            self.room_type_monday_pax_3 = self.pax_3
            self.room_type_monday_pax_4 = self.pax_4
            self.room_type_monday_pax_5 = self.pax_5
            self.room_type_monday_pax_6 = self.pax_6

    @api.onchange('tuesday_checkbox_rt')
    def _onchange_tuesday_checkbox_rt(self):
        if self.tuesday_checkbox_rt:
            self.room_type_tuesday_pax_1 = self.pax_1
            self.room_type_tuesday_pax_2 = self.pax_2
            self.room_type_tuesday_pax_3 = self.pax_3
            self.room_type_tuesday_pax_4 = self.pax_4
            self.room_type_tuesday_pax_5 = self.pax_5
            self.room_type_tuesday_pax_6 = self.pax_6

    @api.onchange('wednesday_checkbox_rt')
    def _onchange_wednesday_checkbox_rt(self):
        if self.wednesday_checkbox_rt:
            self.room_type_wednesday_pax_1 = self.pax_1
            self.room_type_wednesday_pax_2 = self.pax_2
            self.room_type_wednesday_pax_3 = self.pax_3
            self.room_type_wednesday_pax_4 = self.pax_4
            self.room_type_wednesday_pax_5 = self.pax_5
            self.room_type_wednesday_pax_6 = self.pax_6

    @api.onchange('thursday_checkbox_rt')
    def _onchange_thursday_checkbox_rt(self):
        if self.thursday_checkbox_rt:
            self.room_type_thursday_pax_1 = self.pax_1
            self.room_type_thursday_pax_2 = self.pax_2
            self.room_type_thursday_pax_3 = self.pax_3
            self.room_type_thursday_pax_4 = self.pax_4
            self.room_type_thursday_pax_5 = self.pax_5
            self.room_type_thursday_pax_6 = self.pax_6

    @api.onchange('friday_checkbox_rt')
    def _onchange_friday_checkbox_rt(self):
        if self.friday_checkbox_rt:
            self.room_type_friday_pax_1 = self.pax_1
            self.room_type_friday_pax_2 = self.pax_2
            self.room_type_friday_pax_3 = self.pax_3
            self.room_type_friday_pax_4 = self.pax_4
            self.room_type_friday_pax_5 = self.pax_5
            self.room_type_friday_pax_6 = self.pax_6

    @api.onchange('saturday_checkbox_rt')
    def _onchange_saturday_checkbox_rt(self):
        if self.saturday_checkbox_rt:
            self.room_type_saturday_pax_1 = self.pax_1
            self.room_type_saturday_pax_2 = self.pax_2
            self.room_type_saturday_pax_3 = self.pax_3
            self.room_type_saturday_pax_4 = self.pax_4
            self.room_type_saturday_pax_5 = self.pax_5
            self.room_type_saturday_pax_6 = self.pax_6

    @api.onchange('sunday_checkbox_rt')
    def _onchange_sunday_checkbox_rt(self):
        if self.sunday_checkbox_rt:
            self.room_type_sunday_pax_1 = self.pax_1
            self.room_type_sunday_pax_2 = self.pax_2
            self.room_type_sunday_pax_3 = self.pax_3
            self.room_type_sunday_pax_4 = self.pax_4
            self.room_type_sunday_pax_5 = self.pax_5
            self.room_type_sunday_pax_6 = self.pax_6



    extra_bed = fields.Float(string="Extra Bed")
    suite_supl = fields.Float(string="Suite Supplement")
    child = fields.Float(string="Child")
    infant = fields.Float(string="Infant")


class RoomNumberStore(models.Model):
    _name = 'room.number.store'
    _description = 'Room Number Store'

    name = fields.Char(string="Room Name", required=True)
    fsm_location = fields.Many2one('fsm.location', string="Location")

class FSMLocation(models.Model):
    _inherit = 'fsm.location'

    _rec_name = 'description'

class RoomNumberSpecificRate(models.Model):
    _name = 'room.number.specific.rate'
    _description = 'Room Number Specific Rate'

    # Fields for Room Type Specific Rate Model
    rate_code_id = fields.Many2one('rate.code', string="Rate Code", required=True)
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")

    room_fsm_location = fields.Many2one(
        'fsm.location',
        string="Location",
        domain=[('dynamic_selection_id', '=', 4)]
    )

    room_fsm_location_id = fields.Integer(
        string="Location ID",
        compute="_compute_room_fsm_location_id",
        store=True
    )

    room_number = fields.Many2one(
        'room.number.store',
        string="Room Number",
        domain="[('fsm_location', '=', room_fsm_location)]"
    )

    @api.onchange('room_fsm_location')
    def _onchange_room_fsm_location(self):
        """Reset the room number when the location changes"""
        self.room_number = False
        if self.room_fsm_location:
            # Store the rooms in a custom model if they do not already exist
            for room in self.env['hotel.room'].search([('fsm_location', '=', self.room_fsm_location.id)]):
                existing_room = self.env['room.number.store'].search([('name', '=', room.name), ('fsm_location', '=', room.fsm_location.id)], limit=1)
                if not existing_room:
                    self.env['room.number.store'].create({
                        'name': room.name,
                        'fsm_location': room.fsm_location.id,})
                    

     # Fields for Weekday Rates
    room_number_monday_pax_1 = fields.Float(string="Monday 1 Pax")
    room_number_monday_pax_2 = fields.Float(string="Monday 2 Pax")
    room_number_monday_pax_3 = fields.Float(string="Monday 3 Pax")
    room_number_monday_pax_4 = fields.Float(string="Monday 4 Pax")
    room_number_monday_pax_5 = fields.Float(string="Monday 5 Pax")
    room_number_monday_pax_6 = fields.Float(string="Monday 6 Pax")

    room_number_tuesday_pax_1 = fields.Float(string="Tuesday 1 Pax")
    room_number_tuesday_pax_2 = fields.Float(string="Tuesday 2 Pax")
    room_number_tuesday_pax_3 = fields.Float(string="Tuesday 3 Pax")
    room_number_tuesday_pax_4 = fields.Float(string="Tuesday 4 Pax")
    room_number_tuesday_pax_5 = fields.Float(string="Tuesday 5 Pax")
    room_number_tuesday_pax_6 = fields.Float(string="Tuesday 6 Pax")

    room_number_wednesday_pax_1 = fields.Float(string="Wednesday 1 Pax")
    room_number_wednesday_pax_2 = fields.Float(string="Wednesday 2 Pax")
    room_number_wednesday_pax_3 = fields.Float(string="Wednesday 3 Pax")
    room_number_wednesday_pax_4 = fields.Float(string="Wednesday 4 Pax")
    room_number_wednesday_pax_5 = fields.Float(string="Wednesday 5 Pax")
    room_number_wednesday_pax_6 = fields.Float(string="Wednesday 6 Pax")

    room_number_thursday_pax_1 = fields.Float(string="Thursday 1 Pax")
    room_number_thursday_pax_2 = fields.Float(string="Thursday 2 Pax")
    room_number_thursday_pax_3 = fields.Float(string="Thursday 3 Pax")
    room_number_thursday_pax_4 = fields.Float(string="Thursday 4 Pax")
    room_number_thursday_pax_5 = fields.Float(string="Thursday 5 Pax")
    room_number_thursday_pax_6 = fields.Float(string="Thursday 6 Pax")

    room_number_friday_pax_1 = fields.Float(string="Friday 1 Pax")
    room_number_friday_pax_2 = fields.Float(string="Friday 2 Pax")
    room_number_friday_pax_3 = fields.Float(string="Friday 3 Pax")
    room_number_friday_pax_4 = fields.Float(string="Friday 4 Pax")
    room_number_friday_pax_5 = fields.Float(string="Friday 5 Pax")
    room_number_friday_pax_6 = fields.Float(string="Friday 6 Pax")

    room_number_saturday_pax_1 = fields.Float(string="Saturday 1 Pax")
    room_number_saturday_pax_2 = fields.Float(string="Saturday 2 Pax")
    room_number_saturday_pax_3 = fields.Float(string="Saturday 3 Pax")
    room_number_saturday_pax_4 = fields.Float(string="Saturday 4 Pax")
    room_number_saturday_pax_5 = fields.Float(string="Saturday 5 Pax")
    room_number_saturday_pax_6 = fields.Float(string="Saturday 6 Pax")

    room_number_sunday_pax_1 = fields.Float(string="Sunday 1 Pax")
    room_number_sunday_pax_2 = fields.Float(string="Sunday 2 Pax")
    room_number_sunday_pax_3 = fields.Float(string="Sunday 3 Pax")
    room_number_sunday_pax_4 = fields.Float(string="Sunday 4 Pax")
    room_number_sunday_pax_5 = fields.Float(string="Sunday 5 Pax")
    room_number_sunday_pax_6 = fields.Float(string="Sunday 6 Pax")


    # Room Prices for different configurations
    pax_1 = fields.Float(string="1 Pax")
    pax_2 = fields.Float(string="2 Pax")
    pax_3 = fields.Float(string="3 Pax")
    pax_4 = fields.Float(string="4 Pax")
    pax_5 = fields.Float(string="5 Pax")
    pax_6 = fields.Float(string="6 Pax")

    default_checkbox_rn = fields.Boolean(string="Apply Default")
    monday_checkbox_rn = fields.Boolean(string="Apply Default for Monday")
    tuesday_checkbox_rn= fields.Boolean(string="Apply Default for Tuesday")
    wednesday_checkbox_rn = fields.Boolean(string="Apply Default for Wednesday")
    thursday_checkbox_rn = fields.Boolean(string="Apply Default for Thursday")
    friday_checkbox_rn = fields.Boolean(string="Apply Default for Friday")
    saturday_checkbox_rn = fields.Boolean(string="Apply Default for Saturday")
    sunday_checkbox_rn = fields.Boolean(string="Apply Default for Sunday")


    extra_bed = fields.Float(string="Extra Bed")
    suite_supl = fields.Float(string="Suite Supplement")
    child = fields.Float(string="Child")
    infant = fields.Float(string="Infant")




class RatePromotion(models.Model):
    _name = 'rate.promotion'
    _description = 'Rate Promotion'

    promotion_id = fields.Char(string="Promotion ID")
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    buy = fields.Integer(string="Buy")
    get = fields.Integer(string="Get")
    valid_from = fields.Date(string="Validity Period From")
    valid_to = fields.Date(string="Validity Period To")

class MarketCategory(models.Model):
    _name = 'market.category'
    _description = 'Market Category'

    category = fields.Many2one('rate.category', string='Category')
    _rec_name = "market_category"
    market_category = fields.Char(string='Category', required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    user_sort = fields.Integer(string="User Sort")

class MarketSegment(models.Model):
    _name = 'market.segment'
    _description = 'Market Segment'

    _rec_name = 'market_segment'
    market_segment = fields.Char(string="Market Segment", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    category = fields.Many2one('market.category', string='Category', required=True)
    user_sort = fields.Integer(string="User Sort")
    obsolete = fields.Boolean(string="Obsolete", default=False)

class SourceOfBusiness(models.Model):
    _name = 'source.business'
    _description = 'Source of Business'

    _rec_name = 'source'
    source = fields.Char(string="Source", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    user_sort = fields.Integer(string="User Sort")
    obsolete = fields.Boolean(string="Obsolete", default=False)

class CompanyCategory(models.Model):
    _name = 'company.category'
    _description = 'Company Category'

    category = fields.Many2one('rate.category', string='Category', required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)

class CountryRegion(models.Model):
    _name = 'country.region'
    _description = 'Country Region'

    country_id = fields.Many2one('res.country', string="Region", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)

class ReservationStatusCode(models.Model):
    _name = 'reservation.status.code'
    _description = 'Reservation Status Code'

    reservation = fields.Char(string="Reservation Type", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

    count_as = fields.Selection([
        ('not_confirmed', 'Not Confirmed'),
        ('confirmed', 'Confirmed'),
        ('wait_list', 'Wait List'),
        ('tentative', 'Tentative'),
        ('release', 'Release'),
        ('cancelled', 'Cancelled'),
        ('other', 'Other')
    ], string="Count As")

class AllotmentCode(models.Model):
    _name = 'allotment.code'
    _description = 'Allotment Code'

    allotment_code = fields.Char(string="Allotment Code", required=True)
    description = fields.Char(string="Description")
    arabic_description = fields.Char(string="Arabic Description")
    company = fields.Char(string="Company")
    active = fields.Boolean(string="Active", default=True)
    committed_reservations = fields.Boolean(string="Committed Reservations")
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    release_date = fields.Date(string="Release Date")
    release_period = fields.Integer(string="Release Period")
    room_type_ids = fields.One2many('allotment.room.type', 'allotment_id', string="Room Types")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)

    def action_edit_details(self):
        # Logic for the "Edit Details" button
        return {
            'type': 'ir.actions.act_window',
            'name': 'Edit Allotment Details',
            'view_mode': 'form',
            'res_model': 'allotment.code',
            'target': 'new',
            'res_id': self.id,
        }

class AllotmentRoomType(models.Model):
    _name = 'allotment.room.type'
    _description = 'Allotment Room Type'

    room_type = fields.Char(string="Room Type")
    short_name = fields.Char(string="Short Name")
    no_of_rooms = fields.Integer(string="Number of Rooms")
    no_of_pax = fields.Integer(string="Number of Pax")
    allotment_id = fields.Many2one('allotment.code', string="Allotment Code")
class CancellationCode(models.Model):
    _name = 'cancellation.code'
    _description = 'Cancellation Code'

    code = fields.Char(string="Code", required=True)
    description = fields.Char(string="Description")
    abbreviation = fields.Char(string="Abbreviation")
    user_sort = fields.Integer(string="User Sort", default=0)
    obsolete = fields.Boolean(string="Obsolete", default=False)
                              
class CountryCode(models.Model):
    _name = 'country.code'
    _description = 'Country Code'

    country_id = fields.Many2one('res.country', string="Country", required=True)
    country_code = fields.Char(string="Country Code", compute="_compute_country_code", store=True)
    phone_code = fields.Char(string="Phone Code", compute="_compute_country_code", store=True)

    @api.depends('country_id')
    def _compute_country_code(self):
        for record in self:
            record.country_code = record.country_id.code if record.country_id else ''
            record.phone_code = record.country_id.phone_code if record.country_id else ''
    
