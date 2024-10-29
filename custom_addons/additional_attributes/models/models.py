# -*- coding: utf-8 -*-

from odoo import models, fields, api

class Additional_Attributes(models.Model):
    _name = 'additional_attributes.additional_attributes'
    _description = 'Additional Attributes'

    attribute_id = fields.Char(string='Attribute ID', readonly=True, copy=False, default='ATT')  # Auto-generated field
    description = fields.Char(string='Description', required=True)
    abbreviation = fields.Char(string='Abbreviation', required=True)
    length = fields.Integer(string='Length', required=True)
    arb_description = fields.Char(string='Arabic Description', required=True)
    arb_abbreviation = fields.Char(string='Arabic Abbreviation', required=True)

    # Adding the "Type" field as radio buttons
    type = fields.Selection(
        [('code', 'Code'), 
         ('string', 'String'), 
         ('number', 'Number'),
         ('money', 'Money'), 
         ('date', 'Date'), 
         ('flag', 'Flag')],
        string='Type', required=True
    )

    # Adding the "Mandatory" field with Yes/No radio buttons
    mandatory = fields.Selection(
        [('yes', 'Yes'), ('no', 'No')],
        string='Mandatory', default='no', required=True
    )

    # Separate checkboxes for Entry Target
    entry_target_profile = fields.Boolean(string='Profile', default=False)
    entry_target_reservation = fields.Boolean(string='Reservation', default=False)

    @api.model
    def create(self, vals):
        # Generate sequence if attribute_id is 'New'
        if vals.get('attribute_id', 'ATT') == 'ATT':
            vals['attribute_id'] = self.env['ir.sequence'].next_by_code('additional_attributes.attribute_id') or 'ATT'
        return super(Additional_Attributes, self).create(vals)
