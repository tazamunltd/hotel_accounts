# -*- coding: utf-8 -*-
# from odoo import http


# class Templates(http.Controller):
#     @http.route('/templates/templates', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/templates/templates/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('templates.listing', {
#             'root': '/templates/templates',
#             'objects': http.request.env['templates.templates'].search([]),
#         })

#     @http.route('/templates/templates/objects/<model("templates.templates"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('templates.object', {
#             'object': obj
#         })

