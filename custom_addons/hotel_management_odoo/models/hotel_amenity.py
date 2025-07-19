
from odoo import _, fields, models


class HotelAmenity(models.Model):
    """Model that handles all amenities of the hotel"""
    _name = 'hotel.amenity'
    _description = "Hotel Amenity"
    _inherit = 'mail.thread'
    _order = 'id desc'


    active = fields.Boolean(default=True, tracking=True)

    def action_delete_record(self):
        for record in self:
            record.active = False
    
    def action_unarchieve_record(self):
        for record in self:
            record.active = True

    company_id = fields.Many2one('res.company', string="Hotel",
                                 help="Choose the Hotel",
                                 index=True,
                                 default=lambda self: self.env.company,
                                 readonly=True)
    
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
