
from odoo import models, fields, api


class FSMLocation(models.Model):
    _inherit = 'fsm.location'
    _rec_name = 'description'

class OutOfOrderManagement(models.Model):
    _name = 'out.of.order.management.fron.desk'
    _description = 'Out of Order Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'room_number'

    room_fsm_location = fields.Many2one(
        'fsm.location',
        string="Location",
        domain=[('dynamic_selection_id', '=', 4)]
    ,tracking=True)

    room_number = fields.Many2one('hotel.room', string="Room Number", domain="[('fsm_location', '=', room_fsm_location)]",tracking=True)

    room_type = fields.Many2one(
        'room.type',
        string="Room Type",
        compute="_compute_room_type",
        store=True,
        readonly=True
    )

    @api.depends('room_number')
    def _compute_room_type(self):
        for record in self:
            record.room_type = record.room_number.room_type_name if record.room_number else False

    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company, required=True)

    @api.onchange('room_fsm_location')
    def _onchange_room_fsm_location(self):
        """Reset the room number when the location changes."""
        self.room_number = False

            
    # Room Information
    # room_number = fields.Char(string="Room Number", required=True)
    from_date = fields.Date(string="From Date", required=True,tracking=True)
    to_date = fields.Date(string="To Date", required=True,tracking=True)

    # Codes and Comments
    out_of_order_code = fields.Char(string="Out of Order Code",tracking=True)
    authorization_code = fields.Char(string="Authorization Code",tracking=True)
    comments = fields.Text(string="Comments",tracking=True)

class RoomsOnHoldManagement(models.Model):
    _name = 'rooms.on.hold.management.front.desk'
    _description = 'Rooms On Hold Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _rec_name = 'room_number'

    room_fsm_location = fields.Many2one(
        'fsm.location',
        string="Location",
        domain=[('dynamic_selection_id', '=', 4)]
    ,tracking=True)

    room_number = fields.Many2one('hotel.room', string="Room Number", domain="[('fsm_location', '=', room_fsm_location)]",tracking=True)

    room_type = fields.Many2one(
        'room.type',
        string="Room Type",
        compute="_compute_room_type",
        store=True,
        readonly=True
    )

    @api.depends('room_number')
    def _compute_room_type(self):
        for record in self:
            record.room_type = record.room_number.room_type_name if record.room_number else False

    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company, required=True)

    @api.onchange('room_fsm_location')
    def _onchange_room_fsm_location(self):
        """Reset the room number when the location changes."""
        self.room_number = False


    # Room Information
    # room_number = fields.Char(string="Room Number", required=True)
    from_date = fields.Date(string="From Date", required=True,tracking=True)
    to_date = fields.Date(string="To Date", required=True,tracking=True)

    # Codes and Comments
    roh_code = fields.Char(string="ROH Code",tracking=True)
    authorization_code = fields.Char(string="Authorization Code",tracking=True)
    comments = fields.Text(string="Comments",tracking=True)



class PackageHandling(models.Model):
    _name = 'hotel.package_handling'
    _description = 'Package and Mail Handling'

    name = fields.Char(string="Package Name", required=True)
    room_contact_email = fields.Char(string="Room Contact Email", required=True)
    package_details = fields.Text(string="Package Details")
    received_date = fields.Datetime(string="Received Date", default=fields.Datetime.now)
    signature = fields.Binary(string="Signature")
    status = fields.Selection([
        ('pending', 'Pending'),
        ('ready_for_pickup', 'Ready for Pickup'),
        ('delivered', 'Delivered'),
        ('unclaimed', 'Unclaimed')
    ], string="Status", default='pending', required=True)
    confirmed = fields.Boolean(string="Confirmed", default=False)
    booking_id = fields.Many2one('room.booking', string="Booking Reference", required=False)

    @api.model
    def create(self, vals):
        record = super(PackageHandling, self).create(vals)
        if vals.get('room_contact_email'):
            template = self.env.ref('front_desk.package_received_email_template')
            self.env['mail.template'].browse(template.id).send_mail(record.id, force_send=True)
        return record

    def set_ready_for_pickup(self):
        for record in self:
            record.status = 'ready_for_pickup'

    def set_delivered(self):
        for record in self:
            record.status = 'delivered'
            record.confirmed = True
            record.received_date = fields.Datetime.now()

    def mark_unclaimed(self):
        for record in self:
            if record.status == 'pending':
                record.status = 'unclaimed'

    @api.model
    def daily_unclaimed_packages(self):
        unclaimed_packages = self.search([('status', '=', 'pending')])
        for package in unclaimed_packages:
            package.mark_unclaimed()

    def send_notification(self):
        for record in self:
            if record.room_contact_email:
                template = self.env.ref('front_desk.package_update_email_template')
                self.env['mail.template'].browse(template.id).send_mail(record.id, force_send=True)


