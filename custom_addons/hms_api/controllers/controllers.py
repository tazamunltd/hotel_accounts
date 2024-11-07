# -*- coding: utf-8 -*-
# from odoo import http


# class HmsApi(http.Controller):
#     @http.route('/hms_api/hms_api', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/hms_api/hms_api/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('hms_api.listing', {
#             'root': '/hms_api/hms_api',
#             'objects': http.request.env['hms_api.hms_api'].search([]),
#         })

#     @http.route('/hms_api/hms_api/objects/<model("hms_api.hms_api"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('hms_api.object', {
#             'object': obj
#         })

