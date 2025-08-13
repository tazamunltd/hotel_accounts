from collections import defaultdict
import json
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import formatLang
import logging

_logger = logging.getLogger(__name__)

class TzMasterFolioReport(models.Model):
    _name = 'tz.master.folio.report'
    _description = 'Master Folio Report'

    # Fields from folio
    folio_id = fields.Many2one('tz.master.folio', string='Folio')
    folio_number = fields.Char(string='Folio Number')
    room_id = fields.Many2one('hotel.room', string='Room')
    group_id = fields.Many2one('group.booking', string="Group")
    room_type_id = fields.Many2one('room.type', string='Room Type')
    guest_id = fields.Many2one('res.partner', string='Guest')
    company_id = fields.Many2one(
        'res.company',
        string="Hotel",
        index=True,
        default=lambda self: self.env.company,
        readonly=True
    )
    company_vat = fields.Char(string='Company VAT')
    check_in = fields.Datetime(string='Check-in')
    check_out = fields.Datetime(string='Check-out')
    bill_number = fields.Char(string='Bill Number')
    rooming_info = fields.Char(string="Rooming Info")
    value_added_tax = fields.Float(string='VAT')
    municipality_tax = fields.Float(string='Municipality Tax')
    amount_total = fields.Float(string='Grand Total')
    currency_id = fields.Many2one('res.currency', string='Currency')

    # Fields from posting items
    item_id = fields.Many2one('posting.item', string='Posting Item')
    item_name = fields.Char(string='Item Code')
    item_description = fields.Char(string='Description')
    tax_descriptions = fields.Char(string='Tax Descriptions')
    date = fields.Date(string='Date')
    report_time = fields.Char(string='Time')
    total_debit = fields.Float(string='Total Debit')
    total_credit = fields.Float(string='Total Credit')
    total_balance = fields.Float(string='Total Balance')  # Will be calculated in Python

    # Computed fields from folio
    folio_total_debit = fields.Float(string='Folio Total Debit')
    folio_total_credit = fields.Float(string='Folio Total Credit')
    folio_balance = fields.Float(string='Folio Balance')
    tax_totals_json = fields.Text(string="Tax Totals JSON")

    # Computed field to get the dict back
    tax_totals = fields.Binary(
        string="Tax Totals",
        compute='_compute_tax_totals',
        store=False
    )

    taxes_info = fields.Json(string="Taxes", compute="_compute_taxes_info", store=False)

    @api.depends('tax_totals_json')
    def _compute_tax_totals(self):
        for record in self:
            try:
                record.tax_totals = json.loads(record.tax_totals_json or '{}')
            except json.JSONDecodeError:
                record.tax_totals = {}

    def _compute_taxes_info(self):
        for rec in self:
            tax_lines = self.env['tz.manual.posting.tax'].search([
                ('posting_id.folio_id', '=', rec.folio_id.id)
            ])
            tax_summary = defaultdict(float)

            for tax in tax_lines:
                if tax.description:
                    label = tax.description.strip()
                elif tax.type == 'vat':
                    label = "VAT"
                elif tax.type == 'municipality':
                    label = "Municipality Tax"
                else:
                    label = "Other Tax"

                tax_summary[label] += tax.price or 0.0

            rec.taxes_info = [
                {'label': label, 'amount': round(amount, 2)}
                for label, amount in tax_summary.items() if amount > 0
            ]

    def generate_folio_reportX(self, folio_id=None):
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

    def generate_folio_report(self, folio_id=None):
        """ Generate or refresh the report data with all fields including computed tax_totals """
        # Clear existing data if folio_id is provided
        if folio_id:
            self.search([('folio_id', '=', folio_id)]).unlink()

        lang = self.env.context.get('lang') or 'en_US'

        # Base SQL query
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

        # Prepare query parameters
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
            raise UserError(_("An error occurred while fetching report data."))

        if not results:
            _logger.warning("No data found for folio_id: %s", folio_id)
            return self.env['tz.master.folio.report']

        # Prepare folio data with computed fields
        folio_dict = {}
        for row in results:
            folio_id = row['folio_id']
            if folio_id not in folio_dict:
                folio = self.env['tz.master.folio'].browse(folio_id)
                # Convert tax_totals dict to JSON string for storage
                tax_totals = folio.tax_totals or {}
                folio_dict[folio_id] = {
                    'folio': folio,
                    'tax_totals_json': json.dumps(tax_totals),  # Store as JSON string
                    'currency': folio.currency_id,
                    'lines': []
                }
            folio_dict[folio_id]['lines'].append(row)

        # Calculate running balances per folio and prepare report data
        report_data = []
        for folio_id, data in folio_dict.items():
            running_balance = 0.0
            currency = data['currency']

            for line in data['lines']:
                debit = line.get('total_debit', 0.0) or 0.0
                credit = line.get('total_credit', 0.0) or 0.0
                running_balance += (debit - credit)

                report_line = {
                    'folio_id': folio_id,
                    'folio_number': line.get('folio_number'),
                    'room_id': line.get('room_id'),
                    'group_id': line.get('group_id'),
                    'room_type_id': line.get('room_type_id'),
                    'guest_id': line.get('guest_id'),
                    'company_id': line.get('company_id'),
                    'company_vat': line.get('company_vat'),
                    'check_in': line.get('check_in'),
                    'check_out': line.get('check_out'),
                    'bill_number': line.get('bill_number'),
                    'rooming_info': line.get('rooming_info'),
                    'value_added_tax': line.get('value_added_tax'),
                    'municipality_tax': line.get('municipality_tax'),
                    'amount_total': line.get('amount_total'),
                    'currency_id': currency.id if currency else False,
                    'folio_total_debit': line.get('folio_total_debit'),
                    'folio_total_credit': line.get('folio_total_credit'),
                    'folio_balance': line.get('folio_balance'),
                    'date': line.get('date'),
                    'report_time': line.get('report_time'),
                    'total_debit': debit,
                    'total_credit': credit,
                    'total_balance': running_balance,
                    'item_id': line.get('item_id'),
                    'item_name': line.get('item_name'),
                    'item_description': line.get('item_description'),
                    'tax_totals_json': data['tax_totals_json'],  # Store as JSON string
                }
                report_data.append(report_line)

        # Create report records
        return self.env['tz.master.folio.report'].create(report_data)

    @api.model
    def auto_refresh_reports(self):
        """ Scheduled action to refresh all reports """
        self.search([]).unlink()  # Clear all existing data
        return self.generate_folio_report()

    def get_report_data(self):
        """ Prepare data for the report with proper formatting functions """
        return {
            'doc_ids': self.ids,
            'doc_model': 'tz.master.folio.report',
            'docs': self.env['tz.master.folio.report'].browse(self.ids),
            'format_datetime': lambda dt: dt and fields.Datetime.context_timestamp(
                self, fields.Datetime.from_string(dt)).strftime('%Y-%m-%d %H:%M') or '',
            'format_amount': self._format_amount,  # Use the method below
        }

    def _format_amount(self, amount, currency=None):
        """ Safe amount formatting method """
        try:
            return formatLang(self.env, amount, currency_obj=currency or self.currency_id)
        except:
            return str(amount)

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

    def get_tax_totals_dict(self):
        try:
            return json.loads(self.tax_totals or '{}')
        except Exception:
            return {}
