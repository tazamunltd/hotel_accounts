from odoo import models, fields

# class ResPartnerAgent(models.Model):
#     _inherit = 'res.partner'
#
#     agent_name = fields.Char(string="Agent Name", required=True)
#     agent_street = fields.Char(string="Street")
#     agent_street2 = fields.Char(string="Street2")
#     agent_city = fields.Char(string="City")
#     agent_state_id = fields.Many2one('res.country.state', string="State")
#     agent_zip = fields.Char(string="Zip")
#     agent_country_id = fields.Many2one('res.country', string="Country")
#     agent_image = fields.Binary(string="Agent Image")
#
#     def create(self, vals):
#         if 'agent_name' in vals:
#             vals['name'] = vals['agent_name']
#         return super(ResPartnerAgent, self).create(vals)
#
#     def write(self, vals):
#         if 'agent_name' in vals:
#             vals['name'] = vals['agent_name']
#         return super(ResPartnerAgent, self).write(vals)



class Agent(models.Model):
    _name = 'agent.agent'
    _description = 'Agent'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    name = fields.Char(string="Agent Name", required=True, help="Name of the Agent",tracking=True)
    address = fields.Char(string="Address", help="Address of the Agent",tracking=True)
    image = fields.Binary(string="Agent Image", help="Image of the Agent",tracking=True)

