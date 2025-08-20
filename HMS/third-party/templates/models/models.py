# -*- coding: utf-8 -*-

from odoo import models, fields, api

class templates(models.Model):
    _name = 'templates.templates'
    _description = 'templates.templates'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    template_id = fields.Char(string='Template ID', readonly=True, copy=False, default='TMP',tracking=True) 
    description = fields.Char(string='Description', required=True,tracking=True)
    user_sort = fields.Integer(string='User Sort', default=0,tracking=True)

    @api.model
    def create(self, vals):
        # Generate sequence if id is 'TMP'
        if vals.get('template_id', 'TMP') == 'TMP':
            vals['template_id'] = self.env['ir.sequence'].next_by_code('templates.id') or 'TMP'
        return super(templates, self).create(vals)



