# -*- coding: utf-8 -*-
# from odoo import http


# class AdditionalAttributes(http.Controller):
#     @http.route('/additional_attributes/additional_attributes', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/additional_attributes/additional_attributes/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('additional_attributes.listing', {
#             'root': '/additional_attributes/additional_attributes',
#             'objects': http.request.env['additional_attributes.additional_attributes'].search([]),
#         })

#     @http.route('/additional_attributes/additional_attributes/objects/<model("additional_attributes.additional_attributes"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('additional_attributes.object', {
#             'object': obj
#         })

