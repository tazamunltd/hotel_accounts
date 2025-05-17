from odoo import models, fields, api, _
from odoo.tools.misc import formatLang, format_date
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)
# from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as DTF

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
    company_id = fields.Many2one('res.company', string='Hotel')
    company_vat = fields.Char(string='Company VAT')
    check_in = fields.Datetime(string='Check-in')
    check_out = fields.Datetime(string='Check-out')
    bill_number = fields.Char(string='Bill Number')
    rooming_info = fields.Char(string="Rooming Info")
    currency_id = fields.Many2one('res.currency', string='Currency')

    # Fields from posting items
    item_id = fields.Many2one('posting.item', string='Posting Item')
    item_name = fields.Char(string='Item Code')
    item_description = fields.Char(string='Description')
    first_date = fields.Date(string='First Date')
    first_time = fields.Char(string='First Time')
    total_debit = fields.Float(string='Total Debit')
    total_credit = fields.Float(string='Total Credit')
    total_balance = fields.Float(string='Total Balance')

    # Computed fields from folio (might want to recalculate these)
    folio_total_debit = fields.Float(string='Folio Total Debit')
    folio_total_credit = fields.Float(string='Folio Total Credit')
    folio_balance = fields.Float(string='Folio Balance')
    value_added_tax = fields.Float(string='VAT')
    municipality_tax = fields.Float(string='Municipality Tax')
    grand_total = fields.Float(string='Grand Total')

    # Indexes for better performance
    _sql_constraints = [
        ('unique_item_folio', 'UNIQUE(item_id, folio_id)', 'Item per folio must be unique!'),
    ]

    # @api.model
    def generate_folio_report(self, folio_id=None):
        """ Generate or refresh the report data """
        if folio_id:
            self.search([('folio_id', '=', folio_id)]).unlink()

        lang = self.env.context.get('lang') or 'en_US'

        query = """
            SELECT
                pi.id AS item_id,
                COALESCE(pi.item_code ->> %s, pi.item_code ->> 'en_US') AS item_name,
                COALESCE(pi.description ->> %s, pi.description ->> 'en_US') AS item_description,
                MIN(mp.date) AS first_date,
                MIN(mp.time) AS first_time,
                SUM(mp.debit_amount) AS total_debit,
                SUM(mp.credit_amount) AS total_credit,
                SUM(mp.balance) AS total_balance,
                mf.id AS folio_id,
                mf.name AS folio_number,
                mf.room_id AS room_id,
                mf.group_id AS group_id,
                mf.room_type_id AS room_type_id,
                mf.guest_id AS guest_id,
                mf.company_id AS company_id,
                mf.company_vat AS company_vat,
                mf.check_in AS check_in,
                mf.check_out AS check_out,
                mf.bill_number AS bill_number,
                mf.rooming_info AS rooming_info,
                mf.value_added_tax AS value_added_tax,
                mf.municipality_tax AS municipality_tax,
                mf.grand_total AS grand_total,
                mf.currency_id AS currency_id,
                mf.total_debit AS folio_total_debit,
                mf.total_credit AS folio_total_credit,
                mf.balance AS folio_balance
            FROM
                tz_manual_posting mp
            JOIN
                posting_item pi ON mp.item_id = pi.id
            JOIN
                tz_master_folio mf ON mp.folio_id = mf.id
            WHERE
                {where_clause}
            GROUP BY
                pi.id, pi.item_code, pi.description, mf.id, mf.name, 
                mf.room_id, mf.room_type_id, mf.guest_id, mf.company_id, 
                mf.company_vat, mf.check_in, mf.check_out, mf.bill_number,
                mf.value_added_tax, mf.municipality_tax, mf.grand_total,
                mf.currency_id, mf.total_debit, mf.total_credit, mf.balance
            ORDER BY
                pi.item_code
        """

        if folio_id:
            where_clause = "mp.folio_id = %s"
            params = (lang, lang, folio_id)
        else:
            where_clause = "1=1"
            params = (lang, lang)

        # Final formatted query
        final_query = query.format(where_clause=where_clause)

        try:
            self.env.cr.execute(final_query, params)
            results = self.env.cr.dictfetchall()
        except Exception as e:
            _logger.error("Error executing SQL query: %s", e)
            raise UserError("An error occurred while fetching report data.")

        if results:
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


# SELECT
#                 pi.id AS item_id,
#                 COALESCE(pi.item_code ->> 'ar', pi.item_code ->> 'en_US') AS item_name,
#                 COALESCE(pi.description ->>'ar', pi.description ->> 'en_US') AS item_description,
#                 MIN(mp.date) AS first_date,
#                 MIN(mp.time) AS first_time,
#                 SUM(mp.debit_amount) AS total_debit,
#                 SUM(mp.credit_amount) AS total_credit,
#                 SUM(mp.balance) AS total_balance,
#                 mf.id AS folio_id,
#                 mf.name AS folio_number,
#                 mf.room_id AS room_id,
#                 mf.group_id AS group_id,
#                 mf.room_type_id AS room_type_id,
#                 mf.guest_id AS guest_id,
#                 mf.company_id AS company_id,
#                 mf.company_vat AS company_vat,
#                 mf.check_in AS check_in,
#                 mf.check_out AS check_out,
#                 mf.bill_number AS bill_number,
# 				mf.rooming_info AS rooming_info,
#                 mf.value_added_tax AS value_added_tax,
#                 mf.municipality_tax AS municipality_tax,
#                 mf.grand_total AS grand_total,
#                 mf.currency_id AS currency_id,
#                 mf.total_debit AS folio_total_debit,
#                 mf.total_credit AS folio_total_credit,
#                 mf.balance AS folio_balance
#             FROM
#                 tz_manual_posting mp
#             JOIN
#                 posting_item pi ON mp.item_id = pi.id
#             JOIN
#                 tz_master_folio mf ON mp.folio_id = mf.id
#             WHERE
#                 mp.folio_id = 1
#             GROUP BY
#                 pi.id, pi.item_code, pi.description, mf.id, mf.name,
#                 mf.room_id, mf.room_type_id, mf.guest_id, mf.company_id,
#                 mf.company_vat, mf.check_in, mf.check_out, mf.bill_number,
#                 mf.value_added_tax, mf.municipality_tax, mf.grand_total,
#                 mf.currency_id, mf.total_debit, mf.total_credit, mf.balance
#             ORDER BY
#                 pi.item_code