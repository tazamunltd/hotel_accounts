# -*- coding: utf-8 -*-
# from odoo import http


# class WebCors(http.Controller):
#     @http.route('/web_cors/web_cors', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/web_cors/web_cors/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('web_cors.listing', {
#             'root': '/web_cors/web_cors',
#             'objects': http.request.env['web_cors.web_cors'].search([]),
#         })

#     @http.route('/web_cors/web_cors/objects/<model("web_cors.web_cors"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('web_cors.object', {
#             'object': obj
#         })

