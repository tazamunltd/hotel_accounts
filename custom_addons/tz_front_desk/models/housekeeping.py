from odoo import fields, models, api, _


class HouseKeeping(models.Model):
    _name = 'tz.house.keeping'
    _description = 'HouseKeeping'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    # _check_company_auto = True

    name = fields.Char(
        string="Reference",
        readonly=True,
        index=True,
        default=lambda self: _('New'),
        copy=False
    )

    company_id = fields.Many2one('res.company', string="Hotel",
                                 index=True,
                                 default=lambda self: self.env.company)
    room_id = fields.Many2one('hotel.room', string='Room')
    room_type_id = fields.Many2one('room.type', string='Room Type')
    fsm_location = fields.Many2one(
        'fsm.location', string='Location', required=True, tracking=True, domain=[('active', '=', True)])

    block = fields.Char()
    building = fields.Char()
    partner_id = fields.Many2one(
        'res.partner',
        string='HK Section',
    )
    is_clean = fields.Boolean(string="Clean", default=False)
    out_of_service = fields.Boolean(string="Out of Service", default=False)
    repair_ends_by = fields.Date(string="Repair Ends By")
    reason = fields.Char()

    room_status = fields.Selection(selection=[
        ('vacant', 'Vacant'),
        ('slept_out', 'Slept Out'),
        ('occupied', 'Occupied'),
        ('ooo', 'OOO'),
    ], string='State')

    pending_repairs = fields.Text()
    adult_count = fields.Integer(string='Adults')
    child_count = fields.Integer(string='Children')
    infant_count = fields.Integer(string='Infants')

    @api.model
    def create(self, vals):
        if not vals.get('name') or vals['name'] == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('tz.house.keeping') or _('New')
        return super(HouseKeeping, self).create(vals)

    def action_mark_clean(self):
        self.write({'is_clean': True})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_mark_out_of_service(self):
        self.write({'out_of_service': True})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }




