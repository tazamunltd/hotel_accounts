
from odoo import fields, models


class CleaningTeam(models.Model):
    """ Model for creating Cleaning team and assigns Cleaning requests to
    each team"""
    _name = "cleaning.team"
    _description = "Cleaning Team"


    name = fields.Char(string="Team Name", help="Name of the Team")
    team_head_id = fields.Many2one('res.users', string="Team Head",
                                   help="Choose the Team Head",
                                   domain=lambda self: [
                                       ('groups_id', 'in', self.env.ref(
                                           'hotel_management_odoo.'
                                           'cleaning_team_group_head').id)])
    member_ids = fields.Many2many('res.users', string="Member",
                                  domain=lambda self: [
                                      ('groups_id', 'in', self.env.ref(
                                          'hotel_management_odoo.'
                                          'cleaning_team_group_user').id)],
                                  help="Team Members")
