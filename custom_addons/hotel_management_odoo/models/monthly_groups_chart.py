from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class MonthlyGroupsCharts(models.Model):
    _name = 'monthly.groups.charts'
    _description = 'Monthly Groups Charts'

    report_date = fields.Date(string='Report Date', required=True)
    company_id = fields.Many2one('res.company',string='company', required = True)
    room_type = fields.Char(string='Room Type', required=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True)
    available = fields.Integer(string='Available', readonly=True)
    expected_inhouse = fields.Integer(string='Expected In House', readonly=True)
    group_booking = fields.Char(string='Group Booking',readonly=True)
    inhouse = fields.Integer(string='In-House', readonly=True)

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        print("line 34")
        try:
            # Call the run_process method to execute the query and process results
            self.run_process_by_monthly_groups_charts()

        except Exception as e:
            _logger.error(f"Error generating room results: {str(e)}")
            raise ValueError(f"Error generating room results: {str(e)}")

    def run_process_by_monthly_groups_charts(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_monthly_groups_charts")
        
        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")

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
        gb.name AS group_booking_name, -- Added Group Booking Name
        lsd.status AS state,
        hr.room_type_name AS room_type_id,
        hr.company_id,
        rc.name AS company_name
    FROM date_series ds
    CROSS JOIN room_types rt
    JOIN room_booking_line rbl ON TRUE
    JOIN room_booking rb ON rb.id = rbl.booking_id
    JOIN group_booking gb ON rb.group_booking = gb.id -- Joining Group Booking
    JOIN hotel_room hr ON rbl.room_id = hr.id
    JOIN res_company rc ON hr.company_id = rc.id
    JOIN line_status_by_day lsd ON lsd.report_date = ds.report_date AND lsd.booking_line_id = rbl.id
    WHERE rb.checkin_date::date <= ds.report_date
      AND rb.checkout_date::date >= ds.report_date
      AND hr.room_type_name = rt.room_type_id
),
daily_data AS (
    SELECT
        hrb.report_date,
        hrb.group_booking_name, -- Grouping by Group Booking
        hrb.room_type_id,
        hrb.company_id,
        hrb.company_name,
        COUNT(CASE WHEN hrb.state = 'check_in' THEN 1 END) AS in_house,
        COUNT(CASE WHEN hrb.state IN ('confirmed', 'block') AND hrb.checkin_date::date <= hrb.report_date AND hrb.checkout_date::date >= hrb.report_date THEN 1 END) AS expected_inhouse
    FROM hrb
    GROUP BY hrb.report_date, hrb.group_booking_name, hrb.room_type_id, hrb.company_id, hrb.company_name
)
SELECT
    dd.company_id AS "Company ID",
    dd.company_name AS "Company Name",
    dd.report_date AS "Date",
    dd.group_booking_name AS "Group Booking Name", -- Added Group Booking Name
    COALESCE(rt.room_type_name, 'Total') AS "Room Type",
    SUM(dd.in_house) AS "In House",
    SUM(dd.expected_inhouse) AS "Expected In-House"
FROM daily_data dd
LEFT JOIN room_types rt ON dd.room_type_id = rt.room_type_id
GROUP BY dd.company_id, dd.company_name, dd.report_date, dd.group_booking_name, rt.room_type_name
ORDER BY dd.company_id, dd.report_date, dd.group_booking_name, rt.room_type_name;

        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
        records_to_create = []

        for result in results:
            try:
                if result[0] is not None:
                    company_id = result[0]
                    records_to_create.append({
                        'company_id': company_id,
                        'report_date': result[2],  # Date
                        'group_booking': result[3],  # Source of Business
                        'room_type': result[4],    # Room Type
                        'inhouse': int(result[5] or 0),
                        'expected_inhouse': int(result[6] or 0),
                        # 'total_rooms': int(result[6] or 0),        # Total Rooms
                        # 'available': int(result[7] or 0),          # Available Rooms
                         
                        # 'inhouse': int(result[8] or 0),            # In House
                        # 'expected_arrivals': int(result[9] or 0),  # Expected Arrivals
                        # 'expected_departures': int(result[10] or 0), # Expected Departures
                        # Expected In House
                        # 'reserved': int(result[12] or 0),           # Reserved
                        # 'expected_occupied_rate': float(result[13] or 0.0), # Expected Occupied Rate
                        # 'out_of_order': int(result[14] or 0),      # Out of Order Count
                        # 'overbook': int(result[15] or 0),          # Overbooked Count
                        # 'free_to_sell': int(result[16] or 0),      # Free to Sell
                        # 'sort_order': int(result[17] or 0),        # Sort Order
                    })
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
        _logger.info("Completed run_process_by_monthly_groups_charts")
