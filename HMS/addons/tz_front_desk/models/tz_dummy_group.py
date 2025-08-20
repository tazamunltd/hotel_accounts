from odoo import fields, models, api, _


class DummyGroup(models.Model):
    _name = 'tz.dummy.group'
    _description = 'Dummy Group'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _check_company_auto = True
    # _rec_name = 'description'

    name = fields.Char(
        string="Group ID",
        readonly=True,
        index=True,
        tracking=True
    )
    company_id = fields.Many2one('res.company', string="Hotel",
                                 index=True,
                                 default=lambda self: self.env.company)
    partner_id = fields.Many2one(
        'res.partner',
        string='Guest',
        domain="[('is_dummy', '=', True)]", required=True
    )
    abbreviation = fields.Char(string='Abbreviation')
    description = fields.Char(string='Description', required=True)
    reopen = fields.Boolean(string='Open or reopen a group account automatically', default=False, tracking=True)
    auto_payment = fields.Boolean(string='Cash Room – Auto Payment Load', default=False, tracking=True)
    obsolete = fields.Boolean(string='Obsolete', default=False, tracking=True)
    start_date = fields.Datetime(string="Start Date",
                           default=lambda self: self.env.company.system_date.replace(hour=0, minute=0, second=0, microsecond=0),
                           required=True, tracking=True)

    end_date = fields.Datetime()

    state = fields.Selection([
        ('in', 'In'),
        ('out', 'Out')
    ], string='State', default='in')

    def _get_or_create_master_folio(self):
        """
        Get or create a master folio for the dummy group
        Returns: master folio record
        """
        self.ensure_one()
        master_folio = self.env['tz.master.folio']
        company = self.company_id or self.env.company

        # Check if a folio already exists for this dummy group
        existing_folio = master_folio.sudo().search([
            ('dummy_id', '=', self.id),
            ('company_id', '=', company.id)
        ], limit=1)

        # Check conditions to determine if we should create new folio or use existing one
        is_reopen = self.reopen
        is_state_in = self.state == 'in'
        has_end_date = bool(self.end_date)

        # If all conditions are met or no existing folio found
        if (is_reopen and is_state_in and not has_end_date) or not existing_folio:
            # Create new folio
            folio_name = f"{company.name or ''}/{self.env['ir.sequence'].sudo().with_company(company).next_by_code('tz.master.folio') or 'New'}"
            folio = master_folio.sudo().create({
                'name': folio_name,
                'dummy_id': self.id,
                'guest_id': self.partner_id.id,
                'rooming_info': self.description,
                'company_id': company.id,
                'currency_id': company.currency_id.id,
            })
            return folio
        else:
            # Update existing folio if needed
            update_vals = {}
            if existing_folio.guest_id.id != self.partner_id.id:
                update_vals['guest_id'] = self.partner_id.id
            if existing_folio.rooming_info != self.description:
                update_vals['rooming_info'] = self.description
            if update_vals:
                existing_folio.sudo().write(update_vals)
            return existing_folio

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            company = self.env.company
            prefix = f"{company.name}/"
            vals['name'] = prefix + (self.env['ir.sequence'].sudo().with_company(company)
                                     .next_by_code('tz.dummy.group'))

        # Create the group first
        group = super().create(vals)
        group._get_or_create_master_folio()
        # Refresh the SQL View and Sync data
        self.env['tz.manual.posting.room'].create_or_replace_view()
        self.env['tz.manual.posting.type'].sync_with_materialized_view()

        self.env['tz.checkout'].create_or_replace_view()
        self.env['tz.hotel.checkout'].sync_with_materialized_view()
        return group

    def write(self, vals):
        result = super().write(vals)

        for record in self:
            # Evaluate final values after write
            is_reopen = vals.get('reopen', record.reopen)
            is_state_in = vals.get('state', record.state) == 'in'
            has_end_date = 'end_date' in vals or record.end_date
            record._get_or_create_master_folio()
            self.env['tz.manual.posting.room'].create_or_replace_view()
            self.env['tz.manual.posting.type'].sync_with_materialized_view()

            if is_reopen and is_state_in and has_end_date:
                record._get_or_create_master_folio()

        return result

    def copy(self, default=None):
        self.ensure_one()
        company = self.company_id or self.env.company
        prefix = f"{company.name}/"
        name = prefix + (self.env['ir.sequence'].sudo().with_company(company)
                         .next_by_code('tz.dummy.group'))
        default = dict(default or {}, name=name)
        self._get_or_create_master_folio()
        self.env['tz.manual.posting.room'].create_or_replace_view()
        self.env['tz.manual.posting.type'].sync_with_materialized_view()
        return super().copy(default)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_dummy = fields.Boolean()