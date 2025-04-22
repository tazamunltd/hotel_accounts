# -*- coding: utf-8 -*-
# from odoo import http


# class SetupConfiguration(http.Controller):
#     @http.route('/setup_configuration/setup_configuration', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/setup_configuration/setup_configuration/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('setup_configuration.listing', {
#             'root': '/setup_configuration/setup_configuration',
#             'objects': http.request.env['setup_configuration.setup_configuration'].search([]),
#         })

#     @http.route('/setup_configuration/setup_configuration/objects/<model("setup_configuration.setup_configuration"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('setup_configuration.object', {
#             'object': obj
#         })

