from odoo import models, fields


class HousekeepingManagement(models.Model):
    _name = 'housekeeping.management'
    _description = 'Housekeeping Management'

    # Room Information
    room_number = fields.Char(string="Room Number")
    # room_type = fields.Selection([
    #     ('single', 'Single Room'),
    #     ('double', 'Double Room'),
    #     ('triple', 'Triple Room'),
    #     ('suite', 'Suite Room'),
    # ], string="Room Type")

    room_type = fields.Many2one('room.type', string="Room Type")



    floor_number = fields.Char(string="Floor #")
    section_hk = fields.Char(string="Section (H.K)")
    block = fields.Char(string="Block")
    building = fields.Char(string="Building")

    # Housekeeping Information
    clean = fields.Boolean(string="Clean")
    out_of_service = fields.Boolean(string="Out of Service")
    repair_ends_by = fields.Date(string="Repair Ends By")
    changed_linen = fields.Integer(string="Changed Linen")
    changed_towels = fields.Integer(string="Changed Towels")
    pending_repairs = fields.Text(string="Pending Repairs")

    # Room Status (Housekeeping)
    room_status = fields.Selection([
        ('vacant', 'Vacant'),
        ('slept_out', 'Slept Out'),
        ('occupied', 'Occupied'),
    ], string="Room Status (H.K)")

    pax = fields.Integer(string="Pax")
    child = fields.Integer(string="Child")
    infant = fields.Integer(string="Infant")

    # Reason for housekeeping status
    reason = fields.Selection([
        ('not_finished', 'Not finished'),
        ('do_not_disturb', 'Do Not Disturb'),
        ('room_locked', 'Room Locked'),
        ('refused_service', 'Refused Service')
    ], string="Reason")

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
    ], string="Housekeeping Status", default='default')

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

    # Room Information
    room_number = fields.Char(string="Room Number", required=True)
    from_date = fields.Date(string="From Date", required=True)
    to_date = fields.Date(string="To Date", required=True)

    # Codes and Comments
    out_of_order_code = fields.Char(string="Out of Order Code", required=True)
    authorization_code = fields.Char(string="Authorization Code", required=True)
    comments = fields.Text(string="Comments")

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

    # Room Information
    room_number = fields.Char(string="Room Number", required=True)
    from_date = fields.Date(string="From Date", required=True)
    to_date = fields.Date(string="To Date", required=True)

    # Codes and Comments
    roh_code = fields.Char(string="ROH Code", required=True)
    authorization_code = fields.Char(string="Authorization Code", required=True)
    comments = fields.Text(string="Comments")

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

    # Removed name field, keeping ID and other fields
    id = fields.Char(string="ID", required=True)
    date = fields.Datetime(string='Date', required=True, default=fields.Datetime.now)
    status = fields.Selection([
        ('new', 'New'),
        ('in_process', 'In Process'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='new', required=True)

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
    ], string='Target')
    room_number = fields.Char(string='Room Number')
    due_date = fields.Datetime(string='Due Date')
    end_date = fields.Datetime(string='End Date')
    message = fields.Text(string='Message')

    user_text = fields.Selection([
        ('Please king size bed', 'Please king size bed'),
        ('Please add baby cot', 'Please add baby cot'),
        ('Please add extra bed', 'Please add extra bed'),
        ('Please note very regular guests', 'Please note very regular guests'),
        ('Please free upgrade to nile view', 'Please free upgrade to nile view'),
        ('Please note birthday', 'Please note birthday')
    ], string='User Text')

    user_id = fields.Many2one('res.users', string='User ID')
    recurring = fields.Boolean(string="Recurring Task")
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
    ], string="From", default='housekeeping')

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