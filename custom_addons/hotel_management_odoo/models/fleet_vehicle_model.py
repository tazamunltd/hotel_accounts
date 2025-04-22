
from odoo import fields, models, tools


class FleetVehicleModel(models.Model):
    """Inherits Fleet Model for Booking vehicles for hotel Customers"""
    _inherit = 'fleet.vehicle.model'

    @tools.ormcache()
    def _set_default_uom_id(self):
        """Method for getting the default uom id"""
        return self.env.ref('uom.product_uom_km')

    price_per_km = fields.Float(string="Price/KM", default=1.0,
                                help="Rent for Vehicle")
    uom_id = fields.Many2one('uom.uom',
                             string='Reference Uom',
                             help="UOM of the product",
                             default=_set_default_uom_id, required=True)
