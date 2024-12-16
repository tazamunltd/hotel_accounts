
from odoo import models, fields, api


class FSMLocation(models.Model):
    _inherit = 'fsm.location'
    _rec_name = 'description'

class OutOfOrderManagement(models.Model):
    _name = 'out.of.order.management.fron.desk'
    _description = 'Out of Order Management'

    room_fsm_location = fields.Many2one(
        'fsm.location',
        string="Location",
        domain=[('dynamic_selection_id', '=', 4)]
    )

    room_number = fields.Many2one('hotel.room', string="Room Number", domain="[('fsm_location', '=', room_fsm_location)]")

    @api.onchange('room_fsm_location')
    def _onchange_room_fsm_location(self):
        """Reset the room number when the location changes."""
        self.room_number = False

            
    # Room Information
    # room_number = fields.Char(string="Room Number", required=True)
    from_date = fields.Date(string="From Date", required=True)
    to_date = fields.Date(string="To Date", required=True)

    # Codes and Comments
    out_of_order_code = fields.Char(string="Out of Order Code")
    authorization_code = fields.Char(string="Authorization Code")
    comments = fields.Text(string="Comments")

class RoomsOnHoldManagement(models.Model):
    _name = 'rooms.on.hold.management.front.desk'
    _description = 'Rooms On Hold Management'

    room_fsm_location = fields.Many2one(
        'fsm.location',
        string="Location",
        domain=[('dynamic_selection_id', '=', 4)]
    )

    room_number = fields.Many2one('hotel.room', string="Room Number", domain="[('fsm_location', '=', room_fsm_location)]")

    @api.onchange('room_fsm_location')
    def _onchange_room_fsm_location(self):
        """Reset the room number when the location changes."""
        self.room_number = False


    # Room Information
    # room_number = fields.Char(string="Room Number", required=True)
    from_date = fields.Date(string="From Date", required=True)
    to_date = fields.Date(string="To Date", required=True)

    # Codes and Comments
    roh_code = fields.Char(string="ROH Code")
    authorization_code = fields.Char(string="Authorization Code")
    comments = fields.Text(string="Comments")

    

