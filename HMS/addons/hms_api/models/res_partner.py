from odoo import models, fields, api
import bcrypt

class ResPartner(models.Model):
    _inherit = 'res.partner'

    hashed_password = fields.Char(string="Hashed Password")

    @api.model
    def set_password(self, password):
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        self.hashed_password = hashed.decode('utf-8')

    def check_password(self, password):
        if self.hashed_password:
            return bcrypt.checkpw(password.encode('utf-8'), self.hashed_password.encode('utf-8'))
        return False
