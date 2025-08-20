from odoo import models, fields, api, _
from odoo.tools import formatLang
from odoo.exceptions import UserError
import logging
import json
import base64
_logger = logging.getLogger(__name__)


class TzMasterFolio(models.Model):
    _name = 'tz.master.folio'
    _description = 'Master Folio'
    _order = 'room_id, group_id, dummy_id' #create_date desc,

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
            if rec.room_id:
                rec.display_info = rec.room_id.name
            elif rec.group_id:
                rec.display_info = rec.group_id.group_name
            elif rec.dummy_id:
                rec.display_info = rec.dummy_id.description
            else:
                rec.display_info = ""

    @api.depends('manual_posting_ids.balance')
    def _compute_balance(self):
        for folio in self:
            last_posting = folio.manual_posting_ids.sorted(
                key=lambda p: p.create_date or p.id, reverse=True
            )[:1]
            folio.balance = last_posting.balance if last_posting else 0.0

    @api.depends_context('lang')
    @api.depends('manual_posting_ids.taxes', 'manual_posting_ids.total', 'amount_total', 'amount_untaxed')
    def _compute_tax_totalsX(self):
        for folio in self:
            # Filter out:
            # 1. Display-type lines
            # 2. Credit-only lines (credit_amount > 0 and debit_amount = 0)
            # 3. From specific payment/charge groups
            lines = folio.manual_posting_ids.filtered(
                lambda l: not l.display_type
                          and not (l.credit_amount > 0 and l.debit_amount == 0
                                   and (l.payment_group or l.charge_group)))

            folio.tax_totals = self.env['account.tax']._prepare_tax_totals(
                [l._convert_to_tax_base_line_dict() for l in lines],
                folio.currency_id or folio.company_id.currency_id,
            )

    def _compute_tax_totals(self):
        for folio in self:
            # Filter out:
            # - Display-type lines
            # - Lines with a payment_group (e.g., Cash)
            lines = folio.manual_posting_ids.filtered(
                lambda l: not l.display_type and not l.payment_group
            )

            base_lines = []
            currency = folio.currency_id or folio.company_id.currency_id

            for line in lines:
                price_unit = line.debit_amount - line.credit_amount
                base_line = self.env['account.tax']._convert_to_tax_base_line_dict(
                    line,
                    partner=folio.guest_id,
                    currency=currency,
                    product=None,
                    taxes=line.taxes,
                    price_unit=price_unit,
                    quantity=1.0,
                    discount=0.0,
                    price_subtotal=price_unit,
                )
                base_lines.append(base_line)

            folio.tax_totals = self.env['account.tax']._prepare_tax_totals(
                base_lines,
                currency,
            )

    def print_master_folio_report(self):
        return self.env.ref('tz_front_desk.action_report_tz_master_folio_new').report_action(self)

    def _get_tax_totals_display(self):
        self.ensure_one()
        if not self.tax_totals:
            return {}

        try:
            tax_totals = json.loads(self.tax_totals.decode('utf-8')) if isinstance(self.tax_totals,
                                                                                   bytes) else self.tax_totals
            if isinstance(tax_totals, str):
                tax_totals = json.loads(tax_totals)

            # Ensure we have a proper dictionary structure
            if not isinstance(tax_totals, dict):
                return {}

            return {
                'amount_untaxed': tax_totals.get('amount_untaxed', 0),
                'amount_tax': tax_totals.get('amount_tax', 0),
                'amount_total': tax_totals.get('amount_total', 0),
                'groups_by_subtotal': tax_totals.get('groups_by_subtotal', {}),
                'subtotals': tax_totals.get('subtotals', []),
            }
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            _logger.error("Error parsing tax totals: %s", str(e))
            return {}

    def generate_folio_report(self, folio_id=None):
        """ Generate or refresh the report data """
        if folio_id:
            self.search([('folio_id', '=', folio_id)]).unlink()

        lang = self.env.context.get('lang') or 'en_US'

        query = """
               WITH auto_items_summary AS (
                   SELECT 
                       mp.folio_id,
                       pi.id AS item_id,
                       COALESCE(pi.item_code ->> %s, pi.item_code ->> 'en_US') AS item_name,
                       COALESCE(pi.description ->> %s, pi.description ->> 'en_US') AS item_description,
                       mp.date,
                       MIN(mp.time) AS report_time,
                       SUM(mp.debit_without_vat) AS total_debit,
                       SUM(mp.credit_without_vat) AS total_credit
                   FROM tz_manual_posting mp
                   JOIN posting_item pi ON mp.item_id = pi.id
                   WHERE mp.source_type = 'auto'
                   GROUP BY mp.folio_id, mp.date, pi.id, pi.item_code, pi.description
               ),
               manual_items_raw AS (
                   SELECT 
                       mp.folio_id,
                       pi.id AS item_id,
                       COALESCE(pi.item_code ->> %s, pi.item_code ->> 'en_US') AS item_name,
                       COALESCE(pi.description ->> %s, pi.description ->> 'en_US') AS item_description,
                       mp.date,
                       mp.time AS report_time,
                       mp.debit_without_vat AS total_debit,
                       mp.credit_without_vat AS total_credit
                   FROM tz_manual_posting mp
                   JOIN posting_item pi ON mp.item_id = pi.id
                   WHERE mp.source_type = 'manual'
               ),
               all_items AS (
                   SELECT * FROM auto_items_summary
                   UNION ALL
                   SELECT * FROM manual_items_raw
               )
               SELECT  
                   mf.id AS folio_id,
                   mf.name AS folio_number,
                   mf.room_id,
                   mf.group_id,
                   mf.room_type_id,
                   mf.guest_id,
                   mf.company_id,
                   mf.company_vat,
                   mf.check_in,
                   mf.check_out,
                   mf.bill_number,
                   mf.rooming_info,
                   mf.value_added_tax,
                   mf.municipality_tax,
                   mf.amount_total,
                   mf.currency_id,
                   mf.total_debit AS folio_total_debit,
                   mf.total_credit AS folio_total_credit,
                   mf.balance AS folio_balance,
                   ai.date,
                   ai.report_time,
                   ai.total_debit,
                   ai.total_credit,
                   ai.item_id,
                   ai.item_name,
                   ai.item_description
               FROM tz_master_folio mf
               LEFT JOIN all_items ai ON ai.folio_id = mf.id
               WHERE {where_clause}
               ORDER BY ai.date, ai.report_time, ai.item_name;
           """

        if folio_id:
            where_clause = "mf.id = %s"
            params = (lang, lang, lang, lang, folio_id)
        else:
            where_clause = "1=1"
            params = (lang, lang, lang, lang)

        final_query = query.format(where_clause=where_clause)

        try:
            self.env.cr.execute(final_query, params)
            results = self.env.cr.dictfetchall()
        except Exception as e:
            _logger.error("Error executing SQL query: %s", e)
            raise UserError("An error occurred while fetching report data.")

        if results:
            # Sort by folio_id + date + time + item name for running balance
            results.sort(key=lambda r: (
                r['folio_id'],
                r['date'] or '',
                r['report_time'] or '',
                r['item_name'] or ''
            ))

            # Compute running total_balance
            running_balances = {}
            for row in results:
                folio_id = row['folio_id']
                debit = row['total_debit'] or 0.0
                credit = row['total_credit'] or 0.0
                previous_balance = running_balances.get(folio_id, 0.0)
                current_balance = previous_balance + (debit - credit)
                row['total_balance'] = round(current_balance, 2)
                running_balances[folio_id] = round(current_balance, 2)

            created_records = self.create(results)
            _logger.info("Created records: %s", created_records)
            return created_records
        else:
            _logger.warning("No data found for folio_id: %s", folio_id)
            return self

    @api.model
    def auto_refresh_reports(self):
        """ Scheduled action to refresh all reports """
        self.search([]).unlink()  # Clear all existing data
        return self.generate_folio_report()

    def get_report_dataX(self):
        """ Prepare data for the report """
        return {
            'doc_ids': self.ids,
            'doc_model': 'tz.master.folio.report',
            'docs': self.env['tz.master.folio.report'].browse(self.ids),
            'format_datetime': lambda dt: dt and fields.Datetime.context_timestamp(self, fields.Datetime.from_string(
                dt)).strftime('%Y-%m-%d %H:%M') or '',
            'format_amount': lambda amount, currency: currency and formatLang(self.env, amount,
                                                                              currency_obj=currency) or formatLang(
                self.env, amount),
        }

    def get_report_data(self):
        decoded_tax_totals = {}
        for folio in self:
            if folio.tax_totals:
                try:
                    decoded = base64.b64decode(folio.tax_totals)
                    decoded_tax_totals[folio.id] = json.loads(decoded)
                except Exception as e:
                    _logger.warning("Failed to decode tax_totals for folio %s: %s", folio.id, e)

        return {
            'doc_ids': self.ids,
            'doc_model': 'tz.master.folio',
            'docs': self,
            'tax_totals': decoded_tax_totals,
            'format_datetime': lambda dt: dt and fields.Datetime.context_timestamp(self, fields.Datetime.from_string(
                dt)).strftime('%Y-%m-%d %H:%M') or '',
            'format_amount': lambda amount, currency: currency and formatLang(self.env, amount,
                                                                              currency_obj=currency) or formatLang(
                self.env, amount),
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        records = self.browse(docids)
        decoded_tax_totals = {}
        for folio in records:
            if folio.tax_totals:
                try:
                    decoded = base64.b64decode(folio.tax_totals)
                    decoded_tax_totals[folio.id] = json.loads(decoded)
                except Exception as e:
                    _logger.warning("Failed to decode tax_totals for folio %s: %s", folio.id, e)

        return {
            'doc_ids': docids,
            'doc_model': 'tz.master.folio',
            'docs': records,
            'tax_totals': decoded_tax_totals,
            'format_datetime': lambda dt: dt and fields.Datetime.context_timestamp(self, fields.Datetime.from_string(
                dt)).strftime('%Y-%m-%d %H:%M') or '',
            'format_amount': lambda amount, currency: currency and formatLang(self.env, amount,
                                                                              currency_obj=currency) or formatLang(
                self.env, amount),
        }


class OdooPayment(models.Model):
    _inherit = 'account.payment'

    folio_id = fields.Many2one('tz.master.folio', string="Folio", index=True, store=True)



