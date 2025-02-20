
from odoo import _, fields, models,api


class HotelFloor(models.Model):
    """Model that holds the Hotel Floors."""
    _name = "hotel.floor"
    _description = "Floor"
    _order = 'id desc'
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string=_("Name"), help="Name of the floor", required=True, translate=True)
    user_id = fields.Many2one('res.users', string='Manager',
                              help="Manager of the Floor",
                              required=True)
    
class FSMLocationInherit(models.Model):
    _inherit = 'fsm.location'
    _rec_name = 'complete_name'

    owner_id = fields.Many2one('res.partner', string='Related Owner', required=False)    

    description = fields.Char(string=_('Description'), translate=True)
  
    
    @api.onchange('name', 'company_id', 'fsm_parent_id', 'dynamic_selection_id')
    def _onchange_generate_description(self):
        for record in self:
            hotel_name = record.company_id.name if record.company_id else ''
            parent_name = record.fsm_parent_id.name if record.fsm_parent_id else ''
            location_type = record.dynamic_selection_id.name if record.dynamic_selection_id else ''
            name = record.name or ''
            
            description_parts = [part for part in [hotel_name, parent_name, location_type, name] if part]
            record.description = '\\'.join(description_parts)
    partner_id = fields.Many2one(required=False)

    dynamic_selection_id = fields.Many2one(
        'dynamic.selection',
        string="Location Type"
    )
    description = fields.Char(string=_("Description"), required=True, translate=True)

    # company_id = fields.Many2one('res.company', string="Hotel", )
    company_id = fields.Many2one(
        'res.company', 
        string="Hotel", 
        default=lambda self: self.env.company
    )
    dynamic_selection_id = fields.Many2one(
        'dynamic.selection',
        string="Location Type",
        required=True  # This makes the field mandatory
    )

    