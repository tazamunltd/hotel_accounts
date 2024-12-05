# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


# class ResConfigSettings(models.TransientModel):
#     _inherit = 'res.config.settings'

#     module_maintenance_worksheet = fields.Boolean(string="Custom Maintenance Worksheets")
#     website_description = fields.Char(string="Website Description")
#     max_room = fields.Integer(string="Max Rooms")

# class ResConfigSettings(models.TransientModel):
#     _inherit = 'res.config.settings'

#     module_maintenance_worksheet = fields.Boolean(string="Custom Maintenance Worksheets")
#     website_description = fields.Char(
#         string="Website Description",
#         config_parameter="website.description"  # Key in ir.config_parameter
#     )
#     max_room = fields.Integer(
#         string="Max Rooms",
#         config_parameter="website.max_room"  # Key in ir.config_parameter
#     )
#     market_segment = fields.Many2one('market.segment', string="Market Segments", config_parameter="website.market_segment")
#     source_of_business = fields.Many2one('source.business', string="Market Segments", config_parameter="website.source_of_business")
