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
    expected_arrivals = fields.Integer(string='Expected Arrivals', readonly=True,tracking=True)
    expected_departures = fields.Integer(string='Expected Departures', readonly=True,tracking=True)
    expected_inhouse = fields.Integer(string='Expected In House', readonly=True,tracking=True)
    reserved = fields.Integer(string='Reserved', readonly=True,tracking=True)
    expected_occupied_rate = fields.Integer(string='Expected Occupied Rate (%)', readonly=True,tracking=True)
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
        (SELECT MIN(checkin_date::date) FROM room_booking) AS from_date,
        (SELECT MAX(checkout_date::date) FROM room_booking) AS to_date,
        NULL::integer AS selected_room_type
),
date_series AS (
    SELECT generate_series(p.from_date, p.to_date, interval '1 day')::date AS report_date
    FROM parameters p
),
room_types AS (
    SELECT rt.id AS room_type_id,
           rt.room_type,
           rt.description AS room_type_name
    FROM room_type rt
),
line_status_by_day AS (
    SELECT
        ds.report_date,
        rbl.id AS booking_line_id,
        (
            SELECT s.status
            FROM room_booking_line_status s
            WHERE s.booking_line_id = rbl.id
              AND s.change_time::date <= ds.report_date
            ORDER BY s.change_time DESC
            LIMIT 1
        ) AS status
    FROM date_series ds
    JOIN room_booking_line rbl ON rbl.id IS NOT NULL
),
hrb AS (
    SELECT
        ds.report_date,
        rbl.id,
        rb.checkin_date,
        rb.checkout_date,
        lsd.status AS state,
        hr.room_type_name AS room_type_id,
        hr.company_id,
        rc.name AS company_name,
        rb.partner_id AS client_id
    FROM date_series ds
    CROSS JOIN room_types rt
    JOIN room_booking_line rbl ON TRUE
    JOIN room_booking rb ON rb.id = rbl.booking_id
    JOIN hotel_room hr ON rbl.room_id = hr.id
    JOIN res_company rc ON hr.company_id = rc.id
    JOIN line_status_by_day lsd ON lsd.report_date = ds.report_date AND lsd.booking_line_id = rbl.id
    WHERE rb.checkin_date::date <= ds.report_date
      AND rb.checkout_date::date >= ds.report_date
      AND hr.room_type_name = rt.room_type_id
),
expected_in_house AS (
    SELECT
        hrb.report_date,
        hrb.room_type_id,
        hrb.company_id,
        hrb.client_id,
        COUNT(hrb.id) AS expected_in_house_count
    FROM hrb
    WHERE hrb.state IN ('check_in', 'reserved') -- States considered for expected in house
    GROUP BY hrb.report_date, hrb.room_type_id, hrb.company_id, hrb.client_id
),
total_rooms AS (
    SELECT
        ds.report_date,
        rt.room_type_id,
        hr.company_id,
        rc.name AS company_name,
        COUNT(hr.id) AS total_rooms
    FROM date_series ds
    CROSS JOIN room_types rt
    LEFT JOIN hotel_room hr ON hr.room_type_name = rt.room_type_id
    LEFT JOIN res_company rc ON hr.company_id = rc.id
    GROUP BY ds.report_date, rt.room_type_id, hr.company_id, rc.name
)
SELECT
    rc.id AS "Company ID",
    rc.name AS "Company Name",
    rp.id AS "Client ID",
    rp.name AS "Client Name",
    eih.report_date AS "Date",
    COALESCE(rt.room_type_name, 'Total') AS "Room Type",
    SUM(tr.total_rooms) AS "Total Rooms",
    SUM(eih.expected_in_house_count) AS "Expected In House"
FROM expected_in_house eih
LEFT JOIN res_partner rp ON eih.client_id = rp.id
LEFT JOIN total_rooms tr ON eih.report_date = tr.report_date 
    AND eih.room_type_id = tr.room_type_id 
    AND eih.company_id = tr.company_id
LEFT JOIN room_types rt ON eih.room_type_id = rt.room_type_id
LEFT JOIN res_company rc ON eih.company_id = rc.id
GROUP BY rc.id, rc.name, rp.id, rp.name, eih.report_date, rt.room_type_name
ORDER BY rc.id, rp.id, eih.report_date, rt.room_type_name;

        """


        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        records_to_create = []
        for result in results:
            try:
                records_to_create.append({
                    'company_id': result[0],             # Company ID
                    'report_date': result[4],            # Report Date
                    'client_id': result[2],              # Client ID
                    'room_type': result[5],              # Room Type
                    'total_rooms': int(result[6] or 0),# Total Rooms   
                    'expected_inhouse': int(result[7] or 0),# Expected In-House
                    # 'available': int(result[8]),
                    
            # Add other fields if necessary
        })
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")