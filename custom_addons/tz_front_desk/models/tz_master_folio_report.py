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
    grand_total = fields.Float(string='Grand Total')
    currency_id = fields.Many2one('res.currency', string='Currency')

    # Fields from posting items
    item_id = fields.Many2one('posting.item', string='Posting Item')
    item_name = fields.Char(string='Item Code')
    item_description = fields.Char(string='Description')
    date = fields.Date(string='Date')
    report_time = fields.Char(string='Time')
    total_debit = fields.Float(string='Total Debit')
    total_credit = fields.Float(string='Total Credit')
    total_balance = fields.Float(string='Total Balance')  # Will be calculated in Python

    # Computed fields from folio
    folio_total_debit = fields.Float(string='Folio Total Debit')
    folio_total_credit = fields.Float(string='Folio Total Credit')
    folio_balance = fields.Float(string='Folio Balance')

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
                mf.grand_total,
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

    def get_report_data(self):
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
