from odoo import fields, models, api


class HotelService(models.Model):
    """Model that holds the all hotel services"""
    _name = 'hotel.service'
    _description = "Hotel Service"
    _inherit = 'mail.thread'
    _order = 'id desc'

    name = fields.Char(string="Service", help="Name of the service",
                       required=True)
    unit_price = fields.Float(string="Price", help="Price of the service",
                              default=0.0)
    taxes_ids = fields.Many2many('account.tax',
                                 'hotel_service_taxes_rel',
                                 'service_id', 'tax_id',
                                 string='Customer Taxes',
                                 help="Default taxes used when selling the"
                                      " service product.",
                                 domain=[('type_tax_use', '=', 'sale')],
                                 default=lambda self:
                                 self.env.company.account_sale_tax_id)

    frequency = fields.Selection(
        [
            ('one time', 'One Time'),
            ('daily', 'Daily'),
        ],
        string='Frequency',
    )

    @api.model
    def create(self, vals):
        """Override create to reflect changes in hotel.configuration"""
        record = super(HotelService, self).create(vals)
        self.env['hotel.configuration']._sync_with_service(record)
        return record

    def write(self, vals):
        """Override write to reflect changes in hotel.configuration"""
        result = super(HotelService, self).write(vals)
        for record in self:
            self.env['hotel.configuration']._sync_with_service(record)
        return result

    def unlink(self):
        """Override unlink to remove corresponding records in hotel.configuration"""
        for record in self:
            # Find corresponding hotel.configuration record
            config = self.env['hotel.configuration'].search([('service_name', '=', record.name)])
            # Remove the hotel.configuration record if it exists
            config.unlink()
        return super(HotelService, self).unlink()

    def sync_existing_services(self):
        """Synchronize existing services with hotel.configuration"""
        for record in self.search([]):  # Fetch all hotel.service records
            self.env['hotel.configuration']._sync_with_service(record)