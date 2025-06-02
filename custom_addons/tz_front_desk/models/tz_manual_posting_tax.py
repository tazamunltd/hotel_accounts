from odoo import fields, models, api


class TzHotelManualPostingTax(models.Model):
    _name = 'tz.manual.posting.tax'
    _description = 'Hotel Manual Posting Tax'

    posting_id = fields.Many2one('tz.manual.posting', string="Manual Posting", required=True, index=True, ondelete='cascade')
    date = fields.Date()
    time = fields.Char()
    description = fields.Char(string='Description')
    debit_amount = fields.Float(string="Debit")
    credit_amount = fields.Float(string="Credit")
    balance = fields.Float(string="Balance", store=True)

    company_id = fields.Many2one('res.company', string="Hotel",
                                 index=True,
                                 default=lambda self: self.env.company,
                                 readonly=True)

    price = fields.Float(string="Price", compute="_compute_price", store=True)

    type = fields.Selection([
        ('amount', 'Amount'),
        ('vat', 'VAT'),
        ('municipality', 'Municipality'),
        ('other', 'Other'),
    ], string='Type')

    @api.depends('debit_amount', 'credit_amount')
    def _compute_price(self):
        for rec in self:
            rec.price = rec.debit_amount or rec.credit_amount

    @api.depends('tax_id')
    def _compute_tax_type(self):
        for record in self:
            name = (record.tax_id.name or '').lower()
            if 'vat' in name:
                record.tax_type = 'vat'
            elif 'municipality' in name or 'municipal' in name:
                record.tax_type = 'municipality'
            else:
                record.tax_type = 'other'






