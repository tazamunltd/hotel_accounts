from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import defaultdict
import base64

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
    total_debit = fields.Float(string="Total Debit", compute='_compute_totals', store=True)
    total_credit = fields.Float(string="Total Credit", compute='_compute_totals', store=True)
    balance = fields.Float(string="Balance", compute='_compute_totals', store=True)
    value_added_tax = fields.Float(string="Value Added Tax")
    municipality_tax = fields.Float(string="Municipality Tax")
    grand_total = fields.Float(string="Grand Total", compute='_compute_totals', store=True)
    manual_posting_ids = fields.One2many(
        'tz.manual.posting',
        'folio_id',
        string="Posting Lines",
        order='create_date asc'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency'
    )

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

    @api.depends('manual_posting_ids.debit_amount', 'manual_posting_ids.credit_amount', 'value_added_tax',
                 'municipality_tax')
    def _compute_totals(self):
        for folio in self:
            total_debit = sum(line.debit_amount for line in folio.manual_posting_ids)
            total_credit = sum(line.credit_amount for line in folio.manual_posting_ids)
            folio.total_debit = total_debit
            folio.total_credit = total_credit
            folio.balance = total_debit - total_credit
            folio.grand_total = total_debit + folio.value_added_tax + folio.municipality_tax

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

    def action_folio_report_pdf(self):
        self.ensure_one()
        data = {
            'doc_ids': [self.id],
            'doc_model': 'tz.master.folio',
            'docs': self,
            'postings_grouped': self._prepare_postings_grouped_data(),
        }
        raise UserError(data)
        return self.env.ref('tz_front_desk.action_report_master_folio').report_action(self, data=data)

    def _prepare_postings_grouped_data(self):
        query = """
                            SELECT
                                pi.id AS item_id,
                                pi.item_code AS item_name,
                                pi.description AS item_description,
                                MIN(mp.date) AS first_date,
                                MIN(mp.time) AS first_time,
                                SUM(mp.debit_amount) AS total_debit,
                                SUM(mp.credit_amount) AS total_credit,
                                SUM(mp.balance) AS total_balance
                            FROM
                                tz_manual_posting mp
                            JOIN
                                posting_item pi ON mp.item_id = pi.id
                            WHERE
                                mp.folio_id = %s
                            GROUP BY
                                pi.id, pi.item_code, pi.description
                            ORDER BY
                                pi.item_code
                        """
        self.env.cr.execute(query, (self.id,))
        return self.env.cr.dictfetchall()

    def action_generate_and_show_report(self):
        for folio in self:
            report_lines = self.env['tz.master.folio.report'].generate_folio_report(folio_id=folio.id)
            return self.env.ref('tz_front_desk.action_report_tz_master_folio').report_action(report_lines)

    @api.model
    def action_generate_pdf_report(self):
        """ Generate and return the PDF report """
        self.ensure_one()

        self.generate_folio_report(self.folio_id.id)

        if not self.exists():
            raise UserError("No data available for this report.")

        report_action = self.env.ref('tz_front_desk.action_report_tz_master_folio')
        return report_action.report_action(self)

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

