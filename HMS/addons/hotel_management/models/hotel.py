from odoo import models, fields

class Hotel(models.Model):
    _name = 'hotel.hotel'
    _description = 'Hotel'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Hotel Name", required=True, help="Name of the Hotel",tracking=True)
    image = fields.Binary(string="Hotel Image", help="Image of the Hotel",tracking=True)
    location = fields.Char(string="Location", help="Location of the Hotel",tracking=True)
    description = fields.Text(string="Description", help="Brief description of the hotel",tracking=True)
    room_ids = fields.One2many('room.booking', 'hotel_id', string="Room Bookings",
                               help="Bookings associated with this hotel") #
    company_id = fields.Many2one('res.company', string="Company", required=True, default=lambda self: self.env.company,
                                 help="Company associated with this hotel",tracking=True)


