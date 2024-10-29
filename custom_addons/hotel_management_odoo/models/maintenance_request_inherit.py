from odoo import api, fields, models, SUPERUSER_ID, _

class DynamicSelection(models.Model):
    _name = 'dynamic.selection'
    _description = 'Dynamic Selection for Floor, Hotel, Block'

    name = fields.Char(string='Value', required=True)

class MaintenanceRequest(models.Model):

    _inherit = "maintenance.request"
    _rec_names_search = ["code"]

    dynamic_selection_id = fields.Many2one(
        'dynamic.selection', string='Location Type',
        domain=lambda self: [('name', 'in', ['Floor', 'Hotel', 'Block'])]
    )

    maintenance_fsm_location = fields.Many2one('fsm.location', string="Location")

    activity_type = fields.Selection(
        selection=[
            ('maintenance', 'Maintenance'),
            ('housekeeping', 'Housekeeping')
        ],
        string="Activity Type",
    )

   # One2many field to display items based on the selected activity_type
    activity_item_ids = fields.One2many(
        'activity.item', 'maintenance_request_id', string="Activity Items"
    )

    @api.onchange('activity_type')
    def _onchange_activity_type(self):
        self.activity_item_ids = [(5, 0, 0)]  # Clear existing records
        if self.activity_type:
            # Search for template items
            template_items = self.env['activity.item'].search([
                ('activity_type', '=', self.activity_type),
                ('maintenance_request_id', '=', False)  # Only get template items
            ])
            # Create new records based on templates
            new_items = []
            for template in template_items:
                new_items.append((0, 0, {
                    'name': template.name,
                    'activity_type': template.activity_type,
                    'status': 'new',
                }))
            self.activity_item_ids = new_items

class ActivityItem(models.Model):
    _name = "activity.item"
    _description = "Item List for Housekeeping and Maintenance"

    name = fields.Char(string="Item Name", required=True)
    # Link the item to the Maintenance Request model
    maintenance_request_id = fields.Many2one(
        'maintenance.request', string="Maintenance Request"
    )

    # Activity type field
    activity_type = fields.Selection(
        selection=[
            ('maintenance', 'Maintenance'),
            ('housekeeping', 'Housekeeping')
        ],
        string="Activity Type",
        required=True,
    )

    # Status field
    status = fields.Selection(
        selection=[
            ('new', 'New'),
            ('assign', 'Assign'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancel', 'Cancel')
        ],
        string="Status",
        default='new',
    )

    # Reason text field
    reason = fields.Text(string="Reason")
