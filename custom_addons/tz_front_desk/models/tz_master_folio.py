from odoo import models, fields, api, _
from odoo.exceptions import UserError

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
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        tracking=True
    )

    invoice_ids = fields.One2many(
        'account.move',
        'folio_id',
        string='Invoices',
        readonly=True
    )

    invoice_status = fields.Selection([
        ('no', 'Nothing to Invoice'),
        ('to_invoice', 'To Invoice'),
        ('invoiced', 'Fully Invoiced')
    ], string='Invoice Status', default='no', readonly=True, copy=False)

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

    def create_invoice(self):
        """
        Create an invoice (account.move) from the folio and its lines
        Returns the created invoice
        """
        self.ensure_one()

        # Validate before creating invoice
        if not self.folio_line_ids:
            raise UserError(_("Cannot create invoice from an empty folio"))

        if not self.guest_id:
            raise UserError(_("Please set a customer/guest for this folio"))

        # Prepare invoice values
        invoice_vals = {
            'move_type': 'out_invoice',  # Customer invoice
            'invoice_date': fields.Date.context_today(self),
            'partner_id': self.guest_id.id,
            'currency_id': self.currency_id.id or self.company_id.currency_id.id,
            'invoice_origin': self.name,
            'company_id': self.company_id.id,
            'no_account_entry': True,
            'invoice_line_ids': []
        }

        # Prepare invoice lines from folio lines
        for line in self.folio_line_ids:
            # Skip zero amount lines
            amount = line.debit_amount or -line.credit_amount
            if not amount:
                continue

            line_vals = {
                'name': line.description or _("Folio Charge"),
                'quantity': 1,
                'price_unit': amount,
                # 'account_id': self._get_invoice_line_account(line).id,
                # 'tax_ids': [(6, 0, self._get_invoice_line_taxes(line).ids)],
            }
            invoice_vals['invoice_line_ids'].append((0, 0, line_vals))

        # Create the invoice
        invoice = self.env['account.move'].create(invoice_vals)

        # Link the invoice back to the folio
        invoice.write({'folio_id': self.id})

        # Post the invoice automatically
        try:
            invoice.action_post()
        except Exception as e:
            raise UserError(_("Invoice created but posting failed: %s") % str(e))

        # Update folio status
        self.sudo().write({'invoice_status': 'invoiced'})

        return invoice

    def _get_invoice_line_taxes(self, folio_line):
        """Determine taxes for invoice line"""
        # Use taxes from product if available
        if folio_line.product_id and folio_line.product_id.taxes_id:
            return folio_line.product_id.taxes_id.filtered(lambda t: t.company_id == self.company_id)

        # Fallback to no taxes
        return self.env['account.tax']


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