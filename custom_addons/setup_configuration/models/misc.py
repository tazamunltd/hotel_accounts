from odoo import models, fields, api


class HousekeepingManagement(models.Model):
    _name = 'housekeeping.management'
    _description = 'Housekeeping Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Room Information
    # room_number = fields.Char(string="Room Number")
    room_fsm_location = fields.Many2one(
        'fsm.location',
        string="Location",
        domain=[('dynamic_selection_id', '=', 4)]
    ,tracking=True)

    room_type = fields.Many2one('room.type', string="Room Type",tracking=True)

    room_number = fields.Many2one('room.number.store', string="Room Number", 
                                  domain="[('fsm_location', '=', room_fsm_location)]",tracking=True)

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
                    


    floor_number = fields.Char(string="Floor #",tracking=True)
    section_hk = fields.Char(string="Section (H.K)",tracking=True)
    block = fields.Char(string="Block",tracking=True)
    building = fields.Char(string="Building",tracking=True)

    # Housekeeping Information
    clean = fields.Boolean(string="Clean",tracking=True)
    out_of_service = fields.Boolean(string="Out of Service",tracking=True)
    repair_ends_by = fields.Date(string="Repair Ends By",tracking=True)
    changed_linen = fields.Integer(string="Changed Linen",tracking=True)
    changed_towels = fields.Integer(string="Changed Towels",tracking=True)
    pending_repairs = fields.Text(string="Pending Repairs",tracking=True)

    # Room Status (Housekeeping)
    room_status = fields.Selection([
        ('vacant', 'Vacant'),
        ('slept_out', 'Slept Out'),
        ('occupied', 'Occupied'),
    ], string="Room Status (H.K)",tracking=True)

    pax = fields.Integer(string="Pax",tracking=True)
    child = fields.Integer(string="Child",tracking=True)
    infant = fields.Integer(string="Infant",tracking=True)

    # Reason for housekeeping status
    reason = fields.Selection([
        ('not_finished', 'Not finished'),
        ('do_not_disturb', 'Do Not Disturb'),
        ('room_locked', 'Room Locked'),
        ('refused_service', 'Refused Service')
    ], string="Reason",tracking=True)

    # New Selection Field (Instead of the buttons in the image)
    housekeeping_status = fields.Selection([
        ('default', '[Default]'),
        ('dirty_rooms', 'Dirty Rooms'),
        ('expected_arr', 'Expected Arrival'),
        ('exp_arr_clean', 'Exp Arrival Clean'),
        ('exp_arr_dirty', 'Exp Arrival Dirty'),
        ('expected_dep', 'Expected Departure'),
        ('dirty_co', 'Dirty Check-out'),
        ('changed_rooms', 'Changed Rooms'),
        ('arrival_queue', 'Arrival Queue'),
        ('dirty_occupied', 'Dirty Occupied'),
        ('dirty_vacant', 'Dirty Vacant'),
    ], string="Housekeeping Status", default='default',tracking=True)

    # Methods for Room Status Updates
    def action_change_to_unclean(self):
        self.clean = False

    def action_change_to_clean(self):
        self.clean = True

    def action_change_to_vacant(self):
        self.room_status = 'vacant'

    def action_change_to_occupied(self):
        self.room_status = 'occupied'

    def action_change_to_out_of_service(self):
        self.out_of_service = True

    def action_change_to_in_service(self):
        self.out_of_service = False


class OutOfOrderManagement(models.Model):
    _name = 'out.of.order.management'
    _description = 'Out of Order Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    room_fsm_location = fields.Many2one(
        'fsm.location',
        string="Location",
        domain=[('dynamic_selection_id', '=', 4)]
    ,tracking=True)

    room_number = fields.Many2one('room.number.store', string="Room Number", domain="[('fsm_location', '=', room_fsm_location)]",tracking=True)

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

    # Room Information
    # room_number = fields.Char(string="Room Number", required=True)
    from_date = fields.Date(string="From Date", required=True,tracking=True)
    to_date = fields.Date(string="To Date", required=True,tracking=True)

    # Codes and Comments
    out_of_order_code = fields.Char(string="Out of Order Code",tracking=True)
    authorization_code = fields.Char(string="Authorization Code",tracking=True)
    comments = fields.Text(string="Comments",tracking=True)

    # Action Methods
    def action_end_list_today(self):
        # Logic to end the list for today
        self.to_date = fields.Date.today()

    def action_change_all_list(self):
        # Logic to change all list details
        pass


class RoomsOnHoldManagement(models.Model):
    _name = 'rooms.on.hold.management'
    _description = 'Rooms On Hold Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    room_fsm_location = fields.Many2one(
        'fsm.location',
        string="Location",
        domain=[('dynamic_selection_id', '=', 4)]
    ,tracking=True)

    room_number = fields.Many2one('room.number.store', string="Room Number", domain="[('fsm_location', '=', room_fsm_location)]",tracking=True)

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

    # Room Information
    # room_number = fields.Char(string="Room Number", required=True)
    from_date = fields.Date(string="From Date", required=True,tracking=True)
    to_date = fields.Date(string="To Date", required=True,tracking=True)

    # Codes and Comments
    roh_code = fields.Char(string="ROH Code",tracking=True)
    authorization_code = fields.Char(string="Authorization Code",tracking=True)
    comments = fields.Text(string="Comments",tracking=True)

    # Action Methods
    def action_end_list_today(self):
        # Logic to end the list for today by setting the to_date to today's date
        self.to_date = fields.Date.today()

    def action_change_all_list(self):
        # Logic to change all list details (can be customized)
        pass


class HousekeepingTraces(models.Model):
    _name = 'housekeeping.traces'
    _description = 'Housekeeping Traces'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    

    # Removed name field, keeping ID and other fields
    id = fields.Char(string="ID", required=True,tracking=True)
    date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now,tracking=True)
    status = fields.Selection([
        ('new', 'New'),
        ('in_process', 'In Process'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='new', required=True,tracking=True)

    target = fields.Selection([
        ('all_sources', 'All Sources'),
        ('front_desk', 'Front Desk'),
        ('reservation', 'Reservation'),
        ('cashier', 'Cashier'),
        ('housekeeping', 'Housekeeping'),
        ('concierge', 'Concierge'),
        ('fnb', 'F & B'),
        ('maintenance', 'Maintenance'),
        ('it', 'IT'),
        ('hr', 'HR'),
        ('security', 'Security'),
        ('management', 'Management')
    ], string='Target',tracking=True)
    room_number = fields.Char(string='Room Number',tracking=True)
    due_date = fields.Datetime(string='Due Date',tracking=True)
    end_date = fields.Datetime(string='End Date',tracking=True)
    message = fields.Text(string='Message',tracking=True)

    user_text = fields.Selection([
        ('Please king size bed', 'Please king size bed'),
        ('Please add baby cot', 'Please add baby cot'),
        ('Please add extra bed', 'Please add extra bed'),
        ('Please note very regular guests', 'Please note very regular guests'),
        ('Please free upgrade to nile view', 'Please free upgrade to nile view'),
        ('Please note birthday', 'Please note birthday')
    ], string='User Text',tracking=True)

    user_id = fields.Many2one('res.users', string='User ID',tracking=True)
    recurring = fields.Boolean(string="Recurring Task",tracking=True)
    from_department = fields.Selection([
        ('fnb', 'F & B'),
        ('front_desk', 'Front Desk'),
        ('housekeeping', 'Housekeeping'),
        ('concierge', 'Concierge'),
        ('maintenance', 'Maintenance'),
        ('it', 'IT'),
        ('hr', 'HR'),
        ('security', 'Security'),
        ('management', 'Management')
    ], string="From", default='housekeeping',tracking=True)

class ConciergeTraces(models.Model):
    _name = 'concierge.traces'
    _inherit = 'housekeeping.traces'  # Inherit fields from housekeeping.traces
    _description = 'Concierge Traces'


class MaintenanceTraces(models.Model):
    _name = 'maintenance.traces'
    _inherit = 'housekeeping.traces'  # Inherit fields from housekeeping.traces
    _description = 'Maintenanace Traces'

class FNBTraces(models.Model):
    _name = 'fnb.traces'
    _inherit = 'housekeeping.traces'  # Inherit fields from housekeeping.traces
    _description = 'F&B Traces'

class ITTraces(models.Model):
    _name = 'it.traces'
    _inherit = 'housekeeping.traces'  # Inherit fields from housekeeping.traces
    _description = 'IT Traces'