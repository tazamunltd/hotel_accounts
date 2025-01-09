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


    # @api.model
    # def default_get(self, fields_list):
    #     res = super(RoomResultByClient, self).default_get(fields_list)
    #     print('line21')
    #
    #     return res

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        print("line 34")
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
        print("line 47")
        query = """
            WITH parameters AS (
    SELECT
        COALESCE(
          (SELECT MIN(rb.checkin_date::date) FROM room_booking rb), 
          CURRENT_DATE
        ) AS from_date,
        COALESCE(
          (SELECT MAX(rb.checkout_date::date) FROM room_booking rb), 
          CURRENT_DATE
        ) AS to_date
),
date_series AS (
    SELECT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
    FROM parameters p
),

latest_line_status AS (
    SELECT DISTINCT ON (rbl.id, ds.report_date)
           rbl.id AS booking_line_id,
           ds.report_date,
           rb.checkin_date::date   AS checkin_date,
           rb.checkout_date::date  AS checkout_date,
           hr.company_id,
           rt.id                   AS room_type_id,
           rbls.status             AS final_status,
           rbls.change_time,
           rp.id                   AS customer_id,
           rp.name                 AS customer_name,
           rp.is_company           AS is_company
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb        ON rb.id = rbl.booking_id
    JOIN hotel_room hr          ON hr.id = rbl.room_id
    JOIN room_type rt           ON rt.id = hr.room_type_name
    JOIN res_partner rp         ON rb.partner_id = rp.id
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
           AND rbls.change_time::date <= ds.report_date
    ORDER BY
       rbl.id,
       ds.report_date,
       rbls.change_time DESC NULLS LAST
),

in_house AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.is_company,
        lls.customer_id,
        lls.customer_name,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.checkin_date <= lls.report_date
      AND lls.checkout_date > lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.is_company, lls.customer_id, lls.customer_name
),

expected_arrivals AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.is_company,
        lls.customer_id,
        lls.customer_name,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.is_company, lls.customer_id, lls.customer_name
),

expected_departures AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.is_company,
        lls.customer_id,
        lls.customer_name,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.is_company, lls.customer_id, lls.customer_name
),

-- Create a master list of all relevant keys
master_keys AS (
    SELECT report_date, company_id, room_type_id, is_company, customer_id, customer_name
    FROM in_house
    UNION
    SELECT report_date, company_id, room_type_id, is_company, customer_id, customer_name
    FROM expected_arrivals
    UNION
    SELECT report_date, company_id, room_type_id, is_company, customer_id, customer_name
    FROM expected_departures
),

final_report AS (
    SELECT
        mk.report_date,
        mk.company_id,
        mk.room_type_id,
        mk.is_company,
        mk.customer_id,
        mk.customer_name,
        COALESCE(ih.in_house_count, 0) AS in_house_count,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures_count,
        -- Ensure expected_in_house does not go negative
        GREATEST(
            COALESCE(ih.in_house_count, 0)
            + COALESCE(ea.expected_arrivals_count, 0)
            - COALESCE(ed.expected_departures_count, 0),
            0
        ) AS expected_in_house
    FROM master_keys mk
    LEFT JOIN in_house ih
        ON mk.report_date = ih.report_date
       AND mk.company_id = ih.company_id
       AND mk.room_type_id = ih.room_type_id
       AND mk.is_company = ih.is_company
       AND mk.customer_id = ih.customer_id
       AND mk.customer_name = ih.customer_name
    LEFT JOIN expected_arrivals ea
        ON mk.report_date = ea.report_date
       AND mk.company_id = ea.company_id
       AND mk.room_type_id = ea.room_type_id
       AND mk.is_company = ea.is_company
       AND mk.customer_id = ea.customer_id
       AND mk.customer_name = ea.customer_name
    LEFT JOIN expected_departures ed
        ON mk.report_date = ed.report_date
       AND mk.company_id = ed.company_id
       AND mk.room_type_id = ed.room_type_id
       AND mk.is_company = ed.is_company
       AND mk.customer_id = ed.customer_id
       AND mk.customer_name = ed.customer_name
)

SELECT
    fr.report_date,
    fr.company_id,
    rc.name AS company_name,
    fr.room_type_id,
    rt.room_type AS room_type_name,
    fr.is_company,
    fr.customer_id,
    fr.customer_name,
    fr.expected_in_house
FROM final_report fr
JOIN res_company rc ON fr.company_id = rc.id
JOIN room_type rt ON fr.room_type_id = rt.id
ORDER BY
    fr.report_date,
    rc.name,
    rt.room_type,
    fr.is_company,
    fr.customer_name;


        """


        self.env.cr.execute(query)
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
                    room_type_id,
                    room_type_name,
                    is_company,
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
