
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError


class HotelRoom(models.Model):
    """Model that holds all details regarding hotel room"""
    _name = 'hotel.room'
    _description = 'Rooms'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    housekeeping_status = fields.Many2one(
        'housekeeping.status', string="HouseKeeping Status", tracking=True)
    maintenance_status = fields.Many2one(
        'maintenance.status', string="Maintenance Status", tracking=True)
    housekeeping_staff_status = fields.Many2one(
        'housekeeping.staff.status', string="HouseKeeping Staff Status", tracking=True)

    door_sign = fields.Char(string=_("Door Sign"), tracking=True, translate=True)
    suite = fields.Boolean(string="Suite", tracking=True)
    connected_room = fields.Char(string=_("Connected Room"), tracking=True, translate=True)
    type_of_bed = fields.Char(string=_("Type of Bed"), tracking=True, translate=True)
    type_of_bath = fields.Char(string=_("Type of Bath"), tracking=True, translate=True)
    block = fields.Integer(string="Block", tracking=True)
    building = fields.Char(string=_("Building"), tracking=True, translate=True)
    user_sort = fields.Integer(
        string="User Sort", compute="_compute_user_sort", tracking=True)

    # New fields for the Information tab
    pending_repairs = fields.Char(string=_("Pending Repairs"), tracking=True, translate=True)
    last_repairs = fields.Date(string="Last Repairs", tracking=True)
    room_description = fields.Text(string="Room Description", tracking=True)
    notes = fields.Text(string="Notes", tracking=True)

    obsolete = fields.Boolean(string="Obsolete", default=False, tracking=True)
    no_smoking = fields.Boolean(
        string="No Smoking", default=False, tracking=True)
    # max_pax = fields.Integer(string="Max Pax", tracking=True)
    section_hk = fields.Char(
        string=_("Section (H.K.)"), tracking=True, translate=True)
    telephone_ext = fields.Char(string=_("Telephone Ext."), tracking=True, translate=True)
    disability_features = fields.Char(
        string=_("Disability Features"), tracking=True, translate=True)
    extra_features = fields.Char(string=_("Extra Features"), tracking=True, translate=True)
    rate_code = fields.Many2one('rate.code', string="Rate Code", tracking=True)
    rate_posting_item = fields.Char(string=_("Rate Posting Item"), tracking=True, translate=True)

    @tools.ormcache()
    def _get_default_uom_id(self):
        """Method for getting the default uom id"""
        return self.env.ref('uom.product_uom_unit')

    name = fields.Char(string="Name", index='trigram', required=True, translate=True)

    # @api.onchange('name')
    # def _check_name_validity(self):
    #     for record in self:
    #         if record.name:
    #             name_value = int(record.name)
    #             if name_value <= 0:
    #                 raise ValidationError(_("Room name cannot be a negative number or zero. Please enter a valid name."))

    # @api.constrains('name')
    # @api.onchange('name')
    # def _check_name_validity(self):
    #     for record in self:
    #         if record.name and record.name.lstrip('-').isdigit():
    #             if int(record.name) < 1:
    #                 raise ValidationError(_("Room name cannot be a negative number. Please enter a valid name."))

    room_type_name = fields.Many2one('room.type', string='Room Type')

    @api.depends('room_type_name')
    def _compute_user_sort(self):
        """Compute the user_sort value from the related room type."""
        for room in self:
            room.user_sort = room.room_type_name.user_sort if room.room_type_name else 0

    hotel_id = fields.Many2one('hotel.hotel', string="Hotel",
                               help="Hotel associated with this booking", tracking=True)
    status = fields.Selection([("available", "Available"),
                               ("reserved", "Reserved"),
                               ("occupied", "Occupied")],
                              default="available", string="Status",
                              help="Status of The Room",
                              tracking=True)
    is_room_avail = fields.Boolean(default=True, string="Available",
                                   help="Check if the room is available", tracking=True)
    list_price = fields.Float(string='Rent', digits='Product Price',
                              help="The rent of the room.", tracking=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure',
                             default=_get_default_uom_id, required=True,
                             help="Default unit of measure used for all stock"
                                  " operations.", tracking=True)
    room_image = fields.Image(string="Room Image", max_width=1920,
                              max_height=1920, help='Image of the room')
    taxes_ids = fields.Many2many('account.tax',
                                 'hotel_room_taxes_rel',
                                 'room_id', 'tax_id',
                                 help="Default taxes used when selling the"
                                      " room.", string='Customer Taxes',
                                 domain=[('type_tax_use', '=', 'sale')],
                                 default=lambda self: self.env.company.
                                 account_sale_tax_id, tracking=True)
    room_amenities_ids = fields.Many2many("hotel.amenity",
                                          string="Room Amenities",
                                          help="List of room amenities.", tracking=True)
    # floor_id = fields.Many2one('hotel.floor', string='Floor',
    #                            help="Automatically selects the Floor",
    #                            tracking=True)
    floor_id = fields.Many2one(
        'fsm.location',
        string="Floor",
        domain=[('dynamic_selection_id', '=', 4)], tracking=True)


    user_id = fields.Many2one('res.users', string="User",
                              
                              help="Automatically selects the manager",
                              tracking=True)
    # room_type = fields.Selection([('single', 'Single'),
    #                               ('double', 'Double'),
    #                               ('dormitory', 'Dormitory')],
    #                              required=True, string="Room Type",
    #                              help="Automatically selects the Room Type",
    #                              tracking=True,
    #                              default="single")
    num_person = fields.Integer(string='Max Pax',
                                required=True,
                                help="Automatically chooses the No. of Persons",
                                tracking=True)
    description = fields.Html(string='Description', help="Add description",
                              translate=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 default=lambda self: self.env.company, required=True, tracking=True)

    fsm_location = fields.Many2one(
        'fsm.location', string='Location', tracking=True)
    # @api.onchange('fsm_location')
    # def _onchange_fsm_location(self):
    #     if self.fsm_location:
    #         print(f"Selected Location: {self.fsm_location.complete_name}")
    #     else:
    #         print("No location selected.")

    is_room_avail = fields.Boolean(
        string='Is Available', default=True, tracking=True)

    @api.model
    def create(self, vals):
        # Automatically set the company of the logged-in user if not provided
        if not vals.get('company_id'):
            vals['company_id'] = self.env.company.id
        return super(HotelRoom, self).create(vals)

    @api.constrains("num_person")
    def _check_capacity(self):
        """Check capacity function"""
        for room in self:
            if room.num_person <= 0:
                raise ValidationError(_("Room capacity must be more than 0"))

    # @api.onchange("room_type_name")
    # def _onchange_room_type(self):
    #     """Based on selected room type, number of person will be updated.
    #     ----------------------------------------
    #     @param self: object pointer"""
    #     if self.room_type_name == "DELX":
    #         self.num_person = 1
    #     elif self.room_type_name == "DUBL":
    #         self.num_person = 2
    #     else:
    #         self.num_person = 4

    @api.onchange('room_type_name')
    def _onchange_room_type(self):
        """Based on selected room type, number of persons will be updated."""
        if self.room_type_name and self.room_type_name.room_type == "DELX":
            self.num_person = 1
        elif self.room_type_name and self.room_type_name.room_type == "DUBL":
            self.num_person = 2
        elif self.room_type_name and self.room_type_name.room_type == "FAMS":
            self.num_person = 6
        else:
            self.num_person = 8

    checkin_date = fields.Datetime(string='Check-In Date')
    checkout_date = fields.Datetime(string='Check-Out Date')


class HouseKeepingStatus(models.Model):
    _name = 'housekeeping.status'
    _description = 'Housekeeping Status'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'house_keeping_status'
    house_keeping_status = fields.Char(
        string="HouseKeeping Status", tracking=True)


class MaintenanceStatus(models.Model):
    _name = 'maintenance.status'
    _description = 'Housekeeping Status'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'maintenance_status'
    maintenance_status = fields.Char(
        string="Maintenance Status", tracking=True)


class HouseKeepingStaffStatus(models.Model):
    _name = 'housekeeping.staff.status'
    _description = 'Housekeeping Staff Status'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'housekeeping_staff_status'
    housekeeping_staff_status = fields.Char(
        string="HouseKeeping Staff Status", tracking=True)
