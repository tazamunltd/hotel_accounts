from odoo import models, fields, api

class TzMasterFolio(models.Model):
    _name = 'tz.master.folio'
    _description = 'Master Folio'
    _order = 'create_date desc'

    name = fields.Char(string="Folio Number", required=True, index=True, default="New")
    system_date = fields.Datetime(
        string="System Date"
    )
    room_id = fields.Many2one('hotel.room', string="Room", required=True)
    room_type_id = fields.Many2one('room.type', string="Room Type", related='room_id.room_type_name', store=True)
    guest_id = fields.Many2one('res.partner', string="Guest")
    company_id = fields.Many2one('res.company', string="Hotel", index=True)
    company_vat = fields.Char(string="Company VAT", related='company_id.vat', store=True)
    group_id = fields.Many2one('group.booking', string="Group")
    rooming_info = fields.Char(string="Rooming Info")
    check_in = fields.Datetime(string="Check-in")
    check_out = fields.Datetime(string="Check-out")
    bill_number = fields.Char(string="Bill Number")
    total_debit = fields.Float(string="Total Debit", compute='_compute_totals', store=True)
    total_credit = fields.Float(string="Total Credit", compute='_compute_totals', store=True)
    balance = fields.Float(string="Balance", compute='_compute_totals', store=True)
    value_added_tax = fields.Float(string="Value Added Tax")
    municipality_tax = fields.Float(string="Municipality Tax")
    grand_total = fields.Float(string="Grand Total", compute='_compute_totals', store=True)
    folio_line_ids = fields.One2many('tz.master.folio.line', 'folio_id', string="Folio Lines")

    @api.depends('folio_line_ids.debit_amount', 'folio_line_ids.credit_amount', 'value_added_tax', 'municipality_tax')
    def _compute_totals(self):
        for folio in self:
            total_debit = sum(line.debit_amount for line in folio.folio_line_ids)
            total_credit = sum(line.credit_amount for line in folio.folio_line_ids)
            folio.total_debit = total_debit
            folio.total_credit = total_credit
            folio.balance = total_debit - total_credit
            folio.grand_total = total_debit + folio.value_added_tax + folio.municipality_tax

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('tz.master.folio') or 'New'
        return super(TzMasterFolio, self).create(vals)


class TzMasterFolioLine(models.Model):
    _name = 'tz.master.folio.line'
    _description = 'Master Folio Line'
    _order = 'date, id'

    folio_id = fields.Many2one('tz.master.folio', string="Folio", required=True, ondelete='cascade')
    date = fields.Date(string="Date", required=True)
    time = fields.Char(string="Time")
    description = fields.Char(string="Description", required=True)
    voucher_number = fields.Char(string="Voucher #")
    debit_amount = fields.Float(string="Debit", default=0)
    credit_amount = fields.Float(string="Credit", default=0)
    balance = fields.Float(string="Balance", compute='_compute_balance', store=True)
    # product_id = fields.Many2one('product.product', string="Product")
    # tax_ids = fields.Many2many('account.tax', string="Taxes")

    @api.depends('folio_id', 'debit_amount', 'credit_amount', 'date')
    def _compute_balance(self):
        for folio in self.mapped('folio_id'):
            lines = folio.folio_line_ids.sorted(key=lambda r: (r.date, r.id))
            running_balance = 0
            for line in lines:
                running_balance += line.debit_amount - line.credit_amount
                line.balance = running_balance