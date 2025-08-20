# -*- coding: utf-8 -*-
# from odoo import http


# class SetupConfiguration(http.Controller):
#     @http.route('/hotel_configuration/hotel_configuration', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hotel_configuration/hotel_configuration/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('hotel_configuration.listing', {
#             'root': '/hotel_configuration/hotel_configuration',
#             'objects': http.request.env['hotel_configuration.hotel_configuration'].search([]),
#         })

#     @http.route('/hotel_configuration/hotel_configuration/objects/<model("hotel_configuration.hotel_configuration"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hotel_configuration.object', {
#             'object': obj
#         })

