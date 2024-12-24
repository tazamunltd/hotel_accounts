
from odoo import api, fields, models


class EventBookingLine(models.Model):
    """Model that handles the event booking form"""
    _name = "event.booking.line"
    _description = "Hotel Event Line"
    _rec_name = 'event_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    booking_id = fields.Many2one("room.booking", string="Booking",
                                 help="Choose room booking reference",
                                 ondelete="cascade",tracking=True)
    event_id = fields.Many2one('event.event', string="Event",
                               help="Choose the Event",tracking=True)
    ticket_id = fields.Many2one('product.product', string="Ticket",
                                help="Choose the Ticket Type",
                                domain=[('detailed_type', '=', 'event')],tracking=True)
    description = fields.Char(string='Description', help="Detailed "
                                                         "description of the "
                                                         "event",
                              related='event_id.display_name',tracking=True)
    uom_qty = fields.Float(string="Quantity", default=1,
                           help="The quantity converted into the UoM used by "
                                "the product",tracking=True)
    uom_id = fields.Many2one('uom.uom', readonly=True,
                             string="Unit of Measure",
                             related='ticket_id.uom_id', help="This will set "
                                                              "the unit of"
                                                              " measure used",tracking=True)
    price_unit = fields.Float(related='ticket_id.lst_price', string='Price',
                              digits='Product Price',
                              help="The selling price of the selected ticket.",tracking=True)
    tax_ids = fields.Many2many('account.tax',
                               'hotel_event_order_line_taxes_rel',
                               'event_id',
                               'tax_id', related='ticket_id.taxes_id',
                               string='Taxes',
                               help="Default taxes used when selling the event"
                                    "tickets.",
                               domain=[('type_tax_use', '=', 'sale')],tracking=True)
    currency_id = fields.Many2one(
        related='booking_id.pricelist_id.currency_id', string='Currency',
        help='The currency used', store=True, precompute=True,tracking=True)
    price_subtotal = fields.Float(string="Subtotal",
                                  compute='_compute_price_subtotal',
                                  help="Total Price Excluding Tax", store=True,tracking=True)
    price_tax = fields.Float(string="Total Tax",
                             compute='_compute_price_subtotal',
                             help="Tax Amount", store=True,tracking=True)
    price_total = fields.Float(string="Total",
                               compute='_compute_price_subtotal',
                               help="Total Price Including Tax", store=True,tracking=True)
    state = fields.Selection(related='booking_id.state',
                             string="Order Status",
                             help="State of Room Booking", copy=False,tracking=True)

    @api.depends('uom_qty', 'price_unit', 'tax_ids')
    def _compute_price_subtotal(self):
        """Compute the amounts of the Event booking line."""
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes(
                [line._convert_to_tax_base_line_dict()])
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']
            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })
            if self.env.context.get('import_file',
                                    False) and not self.env.user. \
                    user_has_groups('account.group_account_manager'):
                line.tax_id.invalidate_recordset(
                    ['invoice_repartition_line_ids'])

    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the
        generic taxes computation method
        defined on account.tax.
        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.booking_id.partner_id,
            currency=self.currency_id,
            taxes=self.tax_ids,
            price_unit=self.price_unit,
            quantity=self.uom_qty,
            price_subtotal=self.price_subtotal,
        )
