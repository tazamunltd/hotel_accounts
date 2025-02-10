from datetime import timedelta
from odoo import models, fields, api
import logging


_logger = logging.getLogger(__name__)

class RoomResultByClient(models.Model):
    _name = 'room.result.by.client'
    _description = 'Room Result By Client'
    _inherit = ['mail.thread', 'mail.activity.mixin']


    report_date = fields.Date(string='Report Date', required=True,tracking=True)
    company_id = fields.Many2one('res.company',string='company', required = True,tracking=True)
    client_id = fields.Many2one('res.partner', string='Client', required=True,tracking=True)
    room_type = fields.Char(string='Room Type', required=True,tracking=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True,tracking=True)
    available = fields.Integer(string='Available', readonly=True,tracking=True)
    inhouse = fields.Integer(string='In-House', readonly=True,tracking=True)
    expected_arrivals = fields.Integer(string='Exp.Arrivals', readonly=True,tracking=True)
    expected_departures = fields.Integer(string='Exp.Departures', readonly=True,tracking=True)
    expected_inhouse = fields.Integer(string='Exp.Inhouse', readonly=True,tracking=True)
    reserved = fields.Integer(string='Reserved', readonly=True,tracking=True)
    expected_occupied_rate = fields.Integer(string='Exp.Occupied Rate (%)', readonly=True,tracking=True)
    out_of_order = fields.Integer(string='Out of Order', readonly=True,tracking=True)
    overbook = fields.Integer(string='Overbook', readonly=True,tracking=True)
    free_to_sell = fields.Integer(string='Free to sell', readonly=True,tracking=True)
    sort_order = fields.Integer(string='Sort Order', readonly=True,tracking=True)

    

    @api.model
    def search_available_rooms(self, from_date, to_date):
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
        ]
        results = self.search(domain)
        return results.read([
            'report_date', 'room_type', 'client_id', 'expected_inhouse', 'company_id'
        ])

    

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        # print("line 34")
        try:
            # Call the run_process method to execute the query and process results
            self.run_process()

        except Exception as e:
            _logger.error(f"Error generating room results: {str(e)}")
            raise ValueError(f"Error generating room results: {str(e)}")

    def run_process(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process")
        # SQL Query (modified)
        self.env.cr.execute("DELETE FROM room_result_by_client")
        _logger.info("Existing records deleted")
        system_date = self.env.company.system_date.date()
        from_date = system_date - timedelta(days=7)
        to_date = system_date + timedelta(days=7)
        print(f"From Date: {from_date}, To Date: {to_date}")
        get_company = self.env.company.id
#         query = """
#             WITH parameters AS (
#     SELECT
#         COALESCE((SELECT MIN(rb.checkin_date::date) FROM room_booking rb), CURRENT_DATE) AS from_date,
#         COALESCE((SELECT MAX(rb.checkout_date::date) FROM room_booking rb), CURRENT_DATE) AS to_date
# ),
#         query = """
#         WITH parameters AS (
#             SELECT
#                 %s::date AS from_date,
#                 %s::date AS to_date
#         ),
# date_series AS (
#     SELECT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
#     FROM parameters p
# ),
# latest_line_status AS (
#     SELECT DISTINCT ON (rbl.id, ds.report_date)
#            rbl.id AS booking_line_id,
#            ds.report_date,
#            rb.checkin_date::date   AS checkin_date,
#            rb.checkout_date::date  AS checkout_date,
#            hr.company_id,
#            rt.id                   AS room_type_id,
#            rbls.status             AS final_status,
#            rbls.change_time,
#            rb.house_use            AS house_use,
#            rb.complementary        AS complementary,
#            rp.id                   AS customer_id,
#            rp.name                 AS customer_name
#     FROM room_booking_line rbl
#     CROSS JOIN date_series ds
#     JOIN room_booking rb    ON rb.id = rbl.booking_id
#     JOIN hotel_room hr      ON hr.id = rbl.room_id
#     JOIN room_type rt       ON rt.id = hr.room_type_name
#     JOIN res_partner rp     ON rb.partner_id = rp.id
#     LEFT JOIN room_booking_line_status rbls
#            ON rbls.booking_line_id = rbl.id
#            AND rbls.change_time::date <= ds.report_date
#     ORDER BY
#        rbl.id,
#        ds.report_date,
#        rbls.change_time DESC NULLS LAST
# ),
# in_house AS (
#     SELECT
#         ds.report_date,
#         rc.id AS company_id,
#         rt.id AS room_type_id,
#         sub.customer_id,
#         sub.customer_name,
#         COUNT(DISTINCT sub.booking_line_number) AS in_house_count
#     FROM date_series ds
#     CROSS JOIN res_company rc
#     CROSS JOIN room_type   rt

#     LEFT JOIN LATERAL (
#         SELECT DISTINCT ON (qry.booking_line_number)
#                qry.booking_line_number,
#                qry.customer_id,
#                qry.customer_name
#         FROM (
#             SELECT 
#                 rb.company_id,
#                 rbl.hotel_room_type AS room_type_id,
#                 rbl.checkin_date,
#                 rbl.checkout_date,
#                 rbl.id              AS booking_line_number,
#                 rbls.status,
#                 rbls.change_time,
#                 rp.id               AS customer_id,
#                 rp.name             AS customer_name
#             FROM room_booking rb
#             JOIN room_booking_line rbl
#                   ON rbl.booking_id = rb.id
#             JOIN room_booking_line_status rbls
#                   ON rbls.booking_line_id = rbl.id
#             JOIN res_partner rp
#                   ON rb.partner_id = rp.id
#         ) AS qry
#         WHERE qry.company_id     = rc.id
#           AND qry.room_type_id   = rt.id
#           AND qry.checkin_date::date <= ds.report_date
#           AND qry.checkout_date::date > ds.report_date
#           AND qry.status = 'check_in'
#           AND qry.change_time::date <= ds.report_date
#         ORDER BY qry.booking_line_number, qry.change_time DESC
#     ) AS sub ON TRUE

#     GROUP BY 
#         ds.report_date,
#         rc.id,
#         rt.id,
#         sub.customer_id,
#         sub.customer_name
# ),
# expected_arrivals AS (
#     SELECT
#         ds.report_date,
#         rc.id AS company_id,
#         rt.id AS room_type_id,
#         sub.customer_id,
#         sub.customer_name,
#         COUNT(DISTINCT sub.booking_line_number) AS expected_arrivals_count
#     FROM date_series ds
#     CROSS JOIN res_company rc
#     CROSS JOIN room_type   rt

#     LEFT JOIN LATERAL (
#         SELECT DISTINCT ON (qry.booking_line_number)
#                qry.booking_line_number,
#                qry.customer_id,
#                qry.customer_name
#         FROM (
#             SELECT 
#                 rb.company_id,
#                 rbl.hotel_room_type AS room_type_id,
#                 rbl.checkin_date    AS checkin_dt,
#                 rb.name,
#                 rbls.status,
#                 rbl.id              AS booking_line_number,
#                 rbls.change_time,
#                 rp.id               AS customer_id,
#                 rp.name             AS customer_name
#             FROM room_booking rb
#             JOIN room_booking_line rbl 
#                   ON rbl.booking_id = rb.id
#             JOIN room_booking_line_status rbls
#                   ON rbls.booking_line_id = rbl.id
#             JOIN res_partner rp
#                   ON rb.partner_id = rp.id
#         ) AS qry
#         WHERE qry.company_id    = rc.id
#           AND qry.room_type_id  = rt.id
#           AND qry.status        IN ('confirmed','block')
#           AND qry.change_time::date <= ds.report_date
#           AND qry.checkin_dt::date   = ds.report_date
#         ORDER BY qry.booking_line_number, qry.change_time DESC
#     ) AS sub ON TRUE
#     GROUP BY 
#         ds.report_date,
#         rc.id,
#         rt.id,
#         sub.customer_id,
#         sub.customer_name
# ),
# expected_departures AS (
#     SELECT
#         ds.report_date,
#         rc.id AS company_id,
#         rt.id AS room_type_id,
#         sub.customer_id,
#         sub.customer_name,
#         COUNT(DISTINCT sub.booking_line_number) AS expected_departures_count
#     FROM date_series ds
#     CROSS JOIN res_company rc
#     CROSS JOIN room_type   rt

#     LEFT JOIN LATERAL (
#         SELECT DISTINCT ON (qry.booking_line_number)
#                qry.booking_line_number,
#                qry.customer_id,
#                qry.customer_name
#         FROM (
#             SELECT 
#                 rb.company_id,
#                 rbl.hotel_room_type AS room_type_id,
#                 rbl.checkin_date,
#                 rbl.checkout_date,
#                 rbl.id              AS booking_line_number,
#                 rbls.status,
#                 rbls.change_time,
#                 rp.id               AS customer_id,
#                 rp.name             AS customer_name
#             FROM room_booking rb
#             JOIN room_booking_line rbl
#                   ON rbl.booking_id = rb.id
#             JOIN room_booking_line_status rbls
#                   ON rbls.booking_line_id = rbl.id
#             JOIN res_partner rp
#                   ON rb.partner_id = rp.id
#         ) AS qry
#         WHERE qry.company_id    = rc.id
#           AND qry.room_type_id  = rt.id
#           AND qry.checkout_date::date = ds.report_date
#           AND qry.status = 'check_in'
#           AND qry.change_time::date <= ds.report_date
#         ORDER BY qry.booking_line_number, qry.change_time DESC
#     ) AS sub ON TRUE
#     GROUP BY 
#         ds.report_date,
#         rc.id,
#         rt.id,
#         sub.customer_id,
#         sub.customer_name
# ),
# master_keys AS (
#     SELECT report_date, company_id, room_type_id, customer_id, customer_name
#     FROM in_house
#     UNION
#     SELECT report_date, company_id, room_type_id, customer_id, customer_name
#     FROM expected_arrivals
#     UNION
#     SELECT report_date, company_id, room_type_id, customer_id, customer_name
#     FROM expected_departures
# ),
# final_report AS (
#     SELECT
#         mk.report_date,
#         mk.company_id,
#         mk.room_type_id,
#         mk.customer_id,
#         mk.customer_name,
#         COALESCE(ih.in_house_count, 0) AS in_house_count,
#         COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count,
#         COALESCE(ed.expected_departures_count, 0) AS expected_departures_count,
#         GREATEST(
#             COALESCE(ih.in_house_count, 0)
#             + COALESCE(ea.expected_arrivals_count, 0)
#             - COALESCE(ed.expected_departures_count, 0),
#             0
#         ) AS expected_in_house
#     FROM master_keys mk
#     LEFT JOIN in_house ih
#         ON mk.report_date = ih.report_date
#        AND mk.company_id = ih.company_id
#        AND mk.room_type_id = ih.room_type_id
#        AND mk.customer_id = ih.customer_id
#        AND mk.customer_name = ih.customer_name
#     LEFT JOIN expected_arrivals ea
#         ON mk.report_date = ea.report_date
#        AND mk.company_id = ea.company_id
#        AND mk.room_type_id = ea.room_type_id
#        AND mk.customer_id = ea.customer_id
#        AND mk.customer_name = ea.customer_name
#     LEFT JOIN expected_departures ed
#         ON mk.report_date = ed.report_date
#        AND mk.company_id = ed.company_id
#        AND mk.room_type_id = ed.room_type_id
#        AND mk.customer_id = ed.customer_id
#        AND mk.customer_name = ed.customer_name
# )
# SELECT
#     fr.report_date,
#     fr.company_id,
#     rc.name AS company_name,
#     fr.room_type_id,
#     COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
#     fr.customer_id,
#     fr.customer_name,
#     fr.expected_in_house
# FROM final_report fr
# JOIN res_company rc ON fr.company_id = rc.id
# JOIN room_type rt ON fr.room_type_id = rt.id
# WHERE fr.customer_id IS NOT NULL
# ORDER BY
#     fr.report_date,
#     rc.name,
#     rt.room_type,
#     fr.customer_name;
#         """

#         # self.env.cr.execute(query)
        query = """WITH parameters AS (
    SELECT
        COALESCE(
          (SELECT MIN(rb.checkin_date::date) 
           FROM room_booking rb 
           WHERE rb.company_id = %s), 
          CURRENT_DATE
        ) AS from_date,
        COALESCE(
          (SELECT MAX(rb.checkout_date::date) 
           FROM room_booking rb 
           WHERE rb.company_id = %s), 
          CURRENT_DATE
        ) AS to_date,
        %s AS company_id
),

date_series AS (
    SELECT DISTINCT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
    FROM parameters p
),
room_type_data AS (
    SELECT
        id AS room_type_id,
        COALESCE(jsonb_extract_path_text(room_type::jsonb, 'en_US'),'N/A') AS room_type_name
    FROM room_type
),
base_data AS (
    SELECT
        rb.id AS booking_id,
        rb.company_id,
        rb.partner_id AS customer_id,
        rp.name AS customer_name,
        rb.checkin_date::date AS checkin_date,
        rb.checkout_date::date AS checkout_date,
        rbl.id AS booking_line_id,
        rbl.room_id,
        rbl.hotel_room_type AS room_type_id,
        rbls.status,
        rbls.change_time,
        rb.house_use,
        rb.complementary
    FROM room_booking rb
    JOIN room_booking_line rbl ON rb.id = rbl.booking_id
    LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
    LEFT JOIN res_partner rp ON rb.partner_id = rp.id
),
inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count,
        SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms,
        BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    GROUP BY hi.company_id, hi.room_type
),
latest_line_status AS (
    SELECT
        bd.booking_line_id,
        ds.report_date,
        bd.checkin_date,
        bd.checkout_date,
        bd.company_id,
        bd.room_type_id,
        bd.customer_id,
        bd.customer_name,
        bd.status AS final_status,
        bd.change_time,
        bd.house_use,
        bd.complementary
    FROM base_data bd
    JOIN date_series ds ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
),
in_house AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.customer_id,
        lls.customer_name,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.customer_id, lls.customer_name
),
yesterday_in_house AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.customer_id,
        lls.customer_name,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
      AND lls.report_date - interval '1 day' BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.customer_id, lls.customer_name
),
final_report AS (
    SELECT
        ds.report_date,
        bd.company_id,
        rc.name AS company_name,
        rtd.room_type_name,
        bd.customer_id,
        bd.customer_name,
        COALESCE(yh.in_house_count, 0) AS expected_in_house
    FROM date_series ds
    JOIN base_data bd ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    JOIN res_company rc ON bd.company_id = rc.id
    JOIN room_type_data rtd ON bd.room_type_id = rtd.room_type_id
    LEFT JOIN yesterday_in_house yh ON yh.company_id = rc.id AND yh.room_type_id = rtd.room_type_id AND yh.report_date = ds.report_date
)
SELECT
    fr.report_date,
    fr.company_id,
    fr.company_name,
    fr.room_type_name,
    fr.customer_id,
    fr.customer_name,
    SUM(fr.expected_in_house) AS expected_in_house
FROM final_report fr
WHERE fr.customer_id IS NOT NULL OR fr.customer_name IS NOT NULL
GROUP BY fr.report_date, fr.company_id, fr.company_name, fr.room_type_name, fr.customer_id, fr.customer_name
ORDER BY fr.report_date, fr.company_name, fr.customer_name;"""
        
        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        self.env.cr.execute(query, (get_company, get_company, get_company))
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        records_to_create = []
        for result in results:
            try:
                if result[1]:
                    company_id = result[1]
                    if company_id != self.env.company.id:
                        continue  
                    # print(result[1])  
                else:
                    continue
            # Unpack each row for clarity:
                (
                    report_date,
                    company_id,
                    company_name,   # not used? up to you
                    # room_type_id,
                    room_type_name,
                    customer_id,
                    customer_name,
                    expected_in_house,
                ) = result

                # Example: total_rooms is not in the query, so let's set it to 0 or something:
                total_rooms = 0

            # Build a dictionary that matches your model fields:
                record_dict = {
                    'report_date': report_date,       # fields.Date
                    'company_id': company_id,         # Many2one to res.company (int)
                    'client_id': customer_id,         # Many2one to res.partner (int)
                    'room_type': room_type_name,      # Char field
                    'total_rooms': total_rooms,       # Integer
                    'inhouse': 0,                    # Or derive from the query if needed
                    'expected_arrivals': 0,
                    'expected_departures': 0,
                    'expected_inhouse': expected_in_house,
                    # ... etc. fill in more fields if you want
                }
                records_to_create.append(record_dict)
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
