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
    abbreviation = fields.Char(string='Abbreviation')
    description = fields.Char(string='Description', required=True)
    reopen = fields.Boolean(string='Open or reopen a group account automatically', default=False, tracking=True)
    auto_payment = fields.Boolean(string='Cash Room – Auto Payment Load', default=False, tracking=True)
    obsolete = fields.Boolean(string='Obsolete', default=False, tracking=True)
    start_date = fields.Datetime(string="Start Date",
                           default=lambda self: self.env.user.company_id.system_date,
                           required=True, tracking=True)

    end_date = fields.Datetime()

    state = fields.Selection([
        ('in', 'In'),
        ('out', 'Out')
    ], string='State', default='in', tracking=True)

    def _create_master_folio(self):
        """
        Create a master folio for the dummy group
        Returns: master folio record
        """
        self.ensure_one()
        master_folio = self.env['tz.master.folio']
        company = self.company_id or self.env.company

        # Create new folio
        folio_name = f"{company.name or ''}/{self.env['ir.sequence'].sudo().with_company(company).next_by_code('tz.master.folio') or 'New'}"
        folio = master_folio.sudo().create({
            'name': folio_name,
            'dummy_id': self.id,
            'rooming_info': self.description,
            'company_id': company.id,
            'currency_id': company.currency_id.id,
        })

        return folio

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            company = self.env.company
            prefix = f"{company.name}/"
            vals['name'] = prefix + (self.env['ir.sequence'].sudo().with_company(company)
                                     .next_by_code('tz.dummy.group'))

        # Create the group first
        group = super().create(vals)
        group._create_master_folio()
        return group

    def copy(self, default=None):
        self.ensure_one()
        company = self.company_id or self.env.company
        prefix = f"{company.name}/"
        name = prefix + (self.env['ir.sequence'].sudo().with_company(company)
                         .next_by_code('tz.dummy.group'))
        default = dict(default or {}, name=name)
        return super().copy(default)
