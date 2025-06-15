from odoo import models, fields, api


class MkSaleOrder(models.Model):
    _name = 'mk.sale.order'
    _description = 'Custom Sale Order'
    _check_company_auto = True

    # Basic fields
    name = fields.Char(string="Reference", required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('mk.sale.order'))
    partner_id = fields.Many2one('res.partner', string="Customer", required=True)
    date_order = fields.Datetime(string="Order Date", default=fields.Datetime.now)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id)

    # Amount fields
    amount_untaxed = fields.Monetary(string="Untaxed Amount", store=True, compute='_compute_amounts')
    amount_tax = fields.Monetary(string="Taxes", store=True, compute='_compute_amounts')
    amount_total = fields.Monetary(string="Total", store=True, compute='_compute_amounts')

    # Tax related fields
    tax_totals = fields.Binary(compute='_compute_tax_totals')
    tax_country_id = fields.Many2one('res.country', compute='_compute_tax_country_id')

    # Lines
    order_line = fields.One2many('mk.sale.order.line', 'order_id', string="Order Lines")

    # Computation methods
    @api.depends('order_line.price_subtotal', 'order_line.price_tax', 'order_line.price_total')
    def _compute_amounts(self):
        for order in self:
            order_lines = order.order_line.filtered(lambda line: not line.display_type)

            if order.company_id.tax_calculation_rounding_method == 'round_globally':
                tax_results = self.env['account.tax']._compute_taxes([
                    line._convert_to_tax_base_line_dict()
                    for line in order_lines
                ])
                totals = tax_results['totals']
                amount_untaxed = totals.get(order.currency_id, {}).get('amount_untaxed', 0.0)
                amount_tax = totals.get(order.currency_id, {}).get('amount_tax', 0.0)
            else:
                amount_untaxed = sum(order_lines.mapped('price_subtotal'))
                amount_tax = sum(order_lines.mapped('price_tax'))

            order.amount_untaxed = amount_untaxed
            order.amount_tax = amount_tax
            order.amount_total = order.amount_untaxed + order.amount_tax

    @api.depends('partner_id')
    def _compute_tax_country_id(self):
        for order in self:
            order.tax_country_id = order.partner_id.country_id

    @api.depends('order_line.tax_id', 'order_line.price_unit', 'amount_total', 'amount_untaxed')
    def _compute_tax_totals(self):
        for order in self:
            order_lines = order.order_line.filtered(lambda line: not line.display_type)
            order.tax_totals = self.env['account.tax']._prepare_tax_totals(
                [line._convert_to_tax_base_line_dict() for line in order_lines],
                order.currency_id or order.company_id.currency_id,
            )


class MkSaleOrderLine(models.Model):
    _name = 'mk.sale.order.line'
    _description = 'Custom Sale Order Line'
    _check_company_auto = True

    # Basic fields
    order_id = fields.Many2one('mk.sale.order', string="Order Reference", required=True, ondelete='cascade')

    product_id = fields.Many2one('product.product', string="Product")
    name = fields.Text(string="Description")
    product_uom_qty = fields.Float(string="Quantity", digits='Product Unit of Measure', default=1.0)
    product_uom = fields.Many2one('uom.uom', string="Unit of Measure")
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note")], string="Display Type")

    # Price fields
    price_unit = fields.Float(string="Unit Price", digits='Product Price')
    discount = fields.Float(string="Discount (%)", digits='Discount')

    # Tax fields
    tax_id = fields.Many2many(
        comodel_name='account.tax',
        string="Taxes")

    company_id = fields.Many2one(related='order_id.company_id', store=True)

    # Amount fields
    price_subtotal = fields.Monetary(compute='_compute_amount', store=True)
    price_tax = fields.Float(compute='_compute_amount', store=True)
    price_total = fields.Monetary(compute='_compute_amount', store=True)
    price_reduce_taxexcl = fields.Monetary(compute='_compute_price_reduce', store=True)
    price_reduce_taxinc = fields.Monetary(compute='_compute_price_reduce', store=True)

    # Related fields
    currency_id = fields.Many2one(related='order_id.currency_id', store=True)

    # Computation methods
    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id')
    def _compute_amount(self):
        for line in self:
            if line.display_type:
                line.update({
                    'price_subtotal': 0,
                    'price_tax': 0,
                    'price_total': 0,
                })
                continue

            tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
            totals = list(tax_results['totals'].values())[0]

            line.update({
                'price_subtotal': totals['amount_untaxed'],
                'price_tax': totals['amount_tax'],
                'price_total': totals['amount_untaxed'] + totals['amount_tax'],
            })

    @api.depends('price_unit', 'discount', 'tax_id')
    def _compute_price_reduce(self):
        for line in self:
            price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            taxes = line.tax_id.compute_all(price, line.currency_id, 1.0, line.product_id, line.order_id.partner_id)
            line.update({
                'price_reduce_taxexcl': taxes['total_excluded'],
                'price_reduce_taxinc': taxes['total_included'],
            })

    def _convert_to_tax_base_line_dict(self):
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.order_id.partner_id,
            currency=self.order_id.currency_id,
            product=self.product_id,
            taxes=self.tax_id,
            price_unit=self.price_unit,
            quantity=self.product_uom_qty,
            discount=self.discount,
            price_subtotal=self.price_subtotal,
        )