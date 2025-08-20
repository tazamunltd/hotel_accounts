# -*- coding: utf-8 -*-
# from odoo import http


# class TzFrontDesk(http.Controller):
#     @http.route('/tz_front_desk/tz_front_desk', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/tz_front_desk/tz_front_desk/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('tz_front_desk.listing', {
#             'root': '/tz_front_desk/tz_front_desk',
#             'objects': http.request.env['tz_front_desk.tz_front_desk'].search([]),
#         })

#     @http.route('/tz_front_desk/tz_front_desk/objects/<model("tz_front_desk.tz_front_desk"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('tz_front_desk.object', {
#             'object': obj
#         })

