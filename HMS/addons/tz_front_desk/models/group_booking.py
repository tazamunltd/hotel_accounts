from odoo import models, fields, api, _

class GroupBooking(models.Model):
    _inherit = 'group.booking'

    has_master_folio = fields.Boolean(default=False)

    state = fields.Selection([
        ('in', 'In'),
        ('out', 'Out')
    ], string='State', default='in')

    first_visit = fields.Date(
        string='First Arrive',
        compute='_compute_first_and_last_visit',
        store=True,
        tracking=True,
    )

    last_visit = fields.Date(
        string='Last Departure',
        compute='_compute_first_and_last_visit',
        store=True,
        tracking=True,
    )

    total_adult_count = fields.Integer(
        string='Adults',
        compute='_compute_pax_and_room_count',
        tracking=True,
        store=True
    )

    total_child_count = fields.Integer(
        string='Children',
        compute='_compute_pax_and_room_count',
        tracking=True,
        store=True
    )

    total_infant_count = fields.Integer(
        string='Infants',
        compute='_compute_pax_and_room_count',
        tracking=True,
        store=True
    )

    total_room_count = fields.Integer(
        string='Rooms',
        compute='_compute_pax_and_room_count',
        tracking=True,
        store=True
    )

    @api.model
    def create(self, vals):
        """Override create to refresh materialized view after creation"""
        record = super(GroupBooking, self).create(vals)
        self.env['tz.manual.posting.room'].create_or_replace_view()
        self.env['tz.manual.posting.type'].update_data_from_sql_view()
        return record

    def write(self, vals):
        """Override write to refresh materialized view when relevant fields change"""
        result = super(GroupBooking, self).write(vals)
        self.env['tz.manual.posting.room'].create_or_replace_view()
        self.env['tz.manual.posting.type'].update_data_from_sql_view()
        return result


