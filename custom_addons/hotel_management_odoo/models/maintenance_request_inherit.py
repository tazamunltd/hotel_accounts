from odoo import api, fields, models, SUPERUSER_ID, _

class DynamicSelection(models.Model):
    _name = 'dynamic.selection'
    _description = 'Dynamic Selection for Floor, Hotel, Block'

    name = fields.Char(string='Value', required=True)

class MaintenanceRequest(models.Model):

    _inherit = "maintenance.request"
    _rec_names_search = ["code"]

    dynamic_selection_id = fields.Many2one(
        'dynamic.selection', string='Location Type')

    maintenance_fsm_location = fields.Many2one('fsm.location', string="Location")

    activity_type = fields.Selection(
        selection=[
            ('maintenance', 'Maintenance'),
        ],
        string="Activity Type",
    )

    activity_type_id_ = fields.Many2one(
        'activity.type.list',
        string="Activity Type",
        help="Select an activity type from the available list"
    )

    # One2many field to display items based on the selected activity_type
    activity_item_ids = fields.One2many(
        'activity.item', 'activity_type_list_id', string="Activity Items", compute="_compute_activity_item_ids"
    )

    @api.depends('activity_type_id_')
    def _compute_activity_item_ids(self):
        for record in self:
            if record.activity_type_id_:
                # Assign related activity items to activity_item_ids
                record.activity_item_ids = record.activity_type_id_.activity_items_ids
            else:
                record.activity_item_ids = [(5, 0, 0)]  # Clear the One2many relation

    # @api.onchange('activity_type')
    # def _onchange_activity_type(self):
    #     self.activity_item_ids = [(5, 0, 0)]  # Clear existing records
    #     if self.activity_type:
    #         # Search for template items
    #         template_items = self.env['activity.item'].search([
    #             ('activity_type', '=', self.activity_type),
    #             ('maintenance_request_id', '=', False)  # Only get template items
    #         ])
    #         # Create new records based on templates
    #         new_items = []
    #         for template in template_items:
    #             new_items.append((0, 0, {
    #                 'name': template.name,
    #                 'activity_type': template.activity_type,
    #                 'status': 'new',
    #             }))
    #         self.activity_item_ids = new_items

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

    # Link to Activity Type List (Many2one)
    activity_type_list_id = fields.Many2one(
        'activity.type.list',
        string="Activity Type List",
        help="The activity type list that this item belongs to."
    )


class ActivityItem(models.Model):
    _name = "activity.type.list"
    _description = "Maintenance Activity Type List"

    name = fields.Char(string="List", required=True)

    # One2many field to link multiple activity items
    activity_items_ids = fields.Many2many(
        'activity.item',
        string="Activity Items",
        help="Select multiple activity items for this activity type list"
    )


class MaintenanceHousekeepingRequest(models.Model):
    _inherit = "maintenance_housekeeping.request"

    hk_activity_type = fields.Selection(
        selection=[
            ('housekeeping', 'HouseKeeping'),
        ],
        string="Activity Type",
    )

    hk_activity_type_id = fields.Many2one(
        'hk.activity.type.list',
        string="Activity Type",
        help="Select an activity type from the available list"
    )

    # One2many field to display items based on the selected activity_type
    activity_item_ids = fields.One2many(
        'hk.activity.item', 'hk_activity_type_list_id', string="Activity Items", compute="_compute_activity_item_ids"
    )

    @api.depends('hk_activity_type_id')
    def _compute_activity_item_ids(self):
        for record in self:
            if record.hk_activity_type_id:
                # Assign related activity items to activity_item_ids
                record.activity_item_ids = record.hk_activity_type_id.hk_activity_items_ids
            else:
                record.activity_item_ids = [(5, 0, 0)]  # Clear the One2many relation


class HKActivityTypeList(models.Model):
    _name = "hk.activity.type.list"
    _description = "Maintenance Activity Type List"

    name = fields.Char(string="List", required=True)

    # One2many field to link multiple activity items
    hk_activity_items_ids = fields.Many2many(
        'hk.activity.item',
        string="Activity Items",
        help="Select multiple activity items for this activity type list"
    )

class HKActivityItem(models.Model):
    _name = "hk.activity.item"
    _description = "Item List for Housekeeping and Maintenance"

    name = fields.Char(string="Item Name", required=True)
    # Link the item to the Maintenance Request model
    hk_maintenance_request_id = fields.Many2one(
        'maintenance_housekeeping.request', string="Maintenance Request"
    )

    # Activity type field
    hk_activity_type = fields.Selection(
        selection=[
            ('housekeeping', 'Housekeeping')
        ],
        string="Activity Type",
        required=True,
    )

    # Status field
    hk_status = fields.Selection(
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
    hk_reason = fields.Text(string="Reason")

    hk_activity_type_list_id = fields.Many2one(
        'hk.activity.type.list',
        string="Activity Type List",
        help="The activity type list that this item belongs to."
    )


