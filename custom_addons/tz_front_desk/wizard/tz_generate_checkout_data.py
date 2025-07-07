from odoo import models, fields, tools, api, _
import logging
_logger = logging.getLogger(__name__)

class GenerateCheckoutWizard(models.TransientModel):
    _name = 'tz.checkout.data'
    _description = 'Wizard for Generating Checkout Data'

    filter_data = fields.Selection([("in_house", "In House"),
                               ("expected_dep", "Expected Dep."),
                               ("depp_w_balance", "Deep with Balance"),
                               ("depp_z_balance", "Deep zero Balance"),
                               ("in_w_balance", "In with Balance"),
                               ("in_co_today", "In & C/D Toady"),
                                    ],
                              default="in_house")

    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    def action_generate_checkout(self):
        self.ensure_one()

        # 1. Fetch all checkout records for the company
        existing_records = self.env['tz.hotel.checkout'].search([
            ('company_id', '=', self.company_id.id)
        ])

        # 2. Get all current booking IDs from the materialized view or table
        self.env.cr.execute("SELECT booking_id FROM tz_checkout WHERE booking_id IS NOT NULL")
        current_booking_ids = {r[0] for r in self.env.cr.fetchall()}

        # 3. Filter existing records to those NOT in current booking_ids
        records_to_remove = existing_records.filtered(
            lambda r: r.booking_id not in current_booking_ids
        )

        # 4. Delete these unmatched records
        records_to_remove.unlink()

        # Step 2: Rebuild the SQL view with filters
        self.generate_data(
            date_from=self.date_from,
            date_to=self.date_to,
            company_id=self.company_id.id,
        )

        # Step 3: Sync from view to hotel checkout table
        self.env['tz.hotel.checkout'].sync_from_view()

        # Step 4: Redirect to the hotel checkout view
        return self.env.ref('tz_front_desk.action_hotel_checkout').read()[0]

    def generate_data(self, date_from=None, date_to=None, company_id=None):
        where_clauses = []
        if date_from:
            where_clauses.append(f"rb.checkin_date >= '{date_from}'")
        if date_to:
            where_clauses.append(f"rb.checkout_date <= '{date_to}'")
        if company_id:
            where_clauses.append(f"rb.company_id = {company_id}")

        where_filter = ' AND '.join(where_clauses) or 'TRUE'

        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
                CREATE OR REPLACE VIEW tz_checkout AS (
                    SELECT
                        ROW_NUMBER() OVER () AS id,
                        booking_id,
                        room_id,
                        group_booking_id,
                        dummy_id,
                        partner_id,
                        checkin_date,
                        checkout_date,
                        adult_count,
                        child_count,
                        infant_count,
                        rate_code,
                        meal_pattern,
                        state,
                        company_id,
                        name
                    FROM (
                        SELECT
                            rb.id AS booking_id,
                            hr.id AS room_id,
                            rb.group_booking_id,
                            NULL::integer AS dummy_id,
                            rb.partner_id,
                            rb.checkin_date,
                            rb.checkout_date,
                            rb.adult_count::integer,
                            rb.child_count::integer,
                            rb.infant_count::integer,
                            rb.rate_code,
                            rb.meal_pattern,
                            rb.state,
                            rb.company_id,
                            COALESCE(hr.name ->> 'en_US', 'Unnamed') AS name
                        FROM room_booking rb
                        JOIN room_booking_line rbl ON rbl.booking_id = rb.id
                        JOIN hotel_room hr ON rbl.room_id = hr.id
                        WHERE rb.state = 'check_in' AND rb.group_booking IS NULL
                
                        UNION ALL
                
                        SELECT
                            NULL AS booking_id,
                            NULL AS room_id,
                            gb.id AS group_booking_id,
                            NULL::integer AS dummy_id,
                            gb.company,
                            gb.first_visit,
                            gb.last_visit,
                            gb.total_adult_count::integer,
                            gb.total_child_count::integer,
                            gb.total_infant_count::integer,
                            gb.rate_code,
                            gb.group_meal_pattern,
                            gb.status_code::varchar,
                            gb.company_id,
                            COALESCE(gb.group_name ->> 'en_US', 'Unnamed')
                        FROM group_booking gb
                        WHERE gb.status_code = 'confirmed'
                          AND gb.id in (SELECT rb.group_booking from room_booking rb WHERE rb.state = 'check_in')
                
                        UNION ALL
                
                        SELECT
                            NULL AS booking_id,
                            NULL AS room_id,
                            NULL AS group_booking_id,
                            dg.id AS dummy_id,
                            NULL,
                            dg.start_date,
                            dg.end_date,
                            NULL,
                            NULL,
                            NULL,
                            NULL,
                            NULL,
                            dg.state,
                            dg.company_id,
                            dg.description::text
                        FROM tz_dummy_group dg
                        WHERE dg.obsolete = FALSE
                    ) AS unified
                );
        """)







