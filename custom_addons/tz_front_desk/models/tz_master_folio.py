from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import json
import base64
import logging

_logger = logging.getLogger(__name__)


class TzMasterFolio(models.Model):
    _name = 'tz.master.folio'
    _description = 'Master Folio'
    _order = 'create_date desc'

    name = fields.Char(string="Folio Number", required=True, index=True, default="New")

    room_id = fields.Many2one('hotel.room', string="Room")
    room_type_id = fields.Many2one('room.type', string="Room Type", related='room_id.room_type_name', store=True)
    guest_id = fields.Many2one('res.partner', string="Guest")
    company_id = fields.Many2one('res.company', string="Hotel",
                                 index=True,
                                 default=lambda self: self.env.company,
                                 readonly=True)
    company_vat = fields.Char(string="Company VAT", related='company_id.vat', store=True)
    group_id = fields.Many2one('group.booking', string="Group")
    dummy_id = fields.Many2one('tz.dummy.group', string="Dummy")
    rooming_info = fields.Char(string="Rooming Info")
    check_in = fields.Datetime(string="Check-in")
    check_out = fields.Datetime(string="Check-out")
    bill_number = fields.Char(string="Bill Number")
    total_debit = fields.Float(string="Total Debit")
    total_credit = fields.Float(string="Total Credit")
    balance = fields.Float(string="Balance", compute='_compute_balance', store=True)

    value_added_tax = fields.Float(string="Value Added Tax")
    municipality_tax = fields.Float(string="Municipality Tax")

    state = fields.Selection(
        [('draft', 'Draft'), ('posted', 'Posted')],
        string="State",
        default='draft'
    )

    booking_ids = fields.Many2many(
        'room.booking',
        string="Linked Bookings",
        help="All bookings associated with this Master Folio"
    )

    display_info = fields.Char(string="Room/Group", compute="_compute_display_info", store=True)

    tax_totals = fields.Binary(
        string="Tax Totals",
        compute='_compute_tax_totals',
        exportable=False,
        help="JSON-formatted tax summary"
    )

    manual_posting_ids = fields.One2many(
        'tz.manual.posting',
        'folio_id',
        string="Manual Postings"
    )

    amount_untaxed = fields.Monetary(
        string="Untaxed Amount", compute='_compute_amounts', store=True)
    amount_tax = fields.Monetary(
        string="Taxes", compute='_compute_amounts', store=True)
    amount_total = fields.Monetary(
        string="Total", compute='_compute_amounts', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('manual_posting_ids.total', 'manual_posting_ids.tax_amount')
    def _compute_amounts(self):
        for folio in self:
            lines = folio.manual_posting_ids
            folio.amount_untaxed = sum(l.price_subtotal for l in lines)
            folio.amount_tax = sum(l.tax_amount for l in lines)
            folio.amount_total = folio.amount_untaxed + folio.amount_tax

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            company = self.env['res.company'].browse(vals['company_id'])
            prefix = company.name + '/' if company else ''
            next_seq = self.env['ir.sequence'].with_company(company).next_by_code('tz.master.folio') or '00001'
            vals['name'] = prefix + next_seq

        # Handle group booking folio creation
        if vals.get('is_group_booking'):
            # Find the master booking for this group
            master_booking = self.env['room.booking'].search([
                ('group_booking_id', '=', vals.get('group_booking_id')),
                ('parent_booking_name', '=', False)
            ], limit=1)

            if master_booking and master_booking.room_booking_line_ids:
                vals['room_id'] = master_booking.room_booking_line_ids[0].room_id.id

        return super(TzMasterFolio, self).create(vals)

    def action_generate_and_show_report(self):
        for folio in self:
            report_lines = self.env['tz.master.folio.report'].generate_folio_report(folio_id=folio.id)
            return self.env.ref('tz_front_desk.action_report_tz_master_folio').report_action(report_lines)

    @api.depends('room_id', 'group_id', 'dummy_id')
    def _compute_display_info(self):
        for rec in self:
            values = []
            if rec.room_id:
                values.append(f"Room: {rec.room_id.name}")
            if rec.group_id:
                values.append(f"Group: {rec.group_id.name}")
            if rec.dummy_id:
                values.append(f"Dummy: {rec.dummy_id.name}")
            rec.display_info = " | ".join(values)

    @api.depends('total_debit', 'total_credit')
    def _compute_balance(self):
        for record in self:
            record.balance = record.total_debit - record.total_credit

    @api.depends_context('lang')
    @api.depends('manual_posting_ids.taxes', 'manual_posting_ids.total', 'amount_total', 'amount_untaxed')
    def _compute_tax_totals(self):
        for folio in self:
            lines = folio.manual_posting_ids.filtered(lambda l: not l.display_type)
            folio.tax_totals = self.env['account.tax']._prepare_tax_totals(
                [l._convert_to_tax_base_line_dict() for l in lines],
                folio.currency_id or folio.company_id.currency_id,
            )
