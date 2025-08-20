# -*- coding: utf-8 -*-
# from odoo import http


# class FrontDesk(http.Controller):
#     @http.route('/front_desk/front_desk', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/front_desk/front_desk/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('front_desk.listing', {
#             'root': '/front_desk/front_desk',
#             'objects': http.request.env['front_desk.front_desk'].search([]),
#         })

#     @http.route('/front_desk/front_desk/objects/<model("front_desk.front_desk"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('front_desk.object', {
#             'object': obj
#         })

