
from odoo import _, fields, models


class HotelAmenity(models.Model):
    """Model that handles all amenities of the hotel"""
    _name = 'hotel.amenity'
    _description = "Hotel Amenity"
    _inherit = 'mail.thread'
    _order = 'id desc'

    name = fields.Char(string=_('Name'), help="Name of the amenity",tracking=True, translate=True)
    icon = fields.Image(string="Icon",
                        help="Image of the amenity")
    description = fields.Html(string="About",
                              help="Specify the amenity description",tracking=True)

    frequency = fields.Selection(
        [
            ('one time', 'One Time'),
            ('daily', 'Daily'),
        ],
        string='Frequency',tracking=True
    )
