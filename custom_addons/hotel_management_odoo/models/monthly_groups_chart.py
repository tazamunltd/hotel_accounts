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
    expected_inhouse = fields.Integer(string='Exp.In House', readonly=True)
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

/* ----------------------------------------------------------------------------
   1) LATEST_LINE_STATUS:
   Determine the latest booking line status for each date and booking line.
   Incorporate Group Booking.
---------------------------------------------------------------------------- */
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
           gb.name                 AS group_booking_name
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb        ON rb.id = rbl.booking_id
    JOIN hotel_room hr          ON hr.id = rbl.room_id
    JOIN room_type rt           ON rt.id = hr.room_type_name  -- Ensure hr.room_type_name is the ID
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
           AND rbls.change_time::date <= ds.report_date
    JOIN group_booking gb       ON rb.group_booking = gb.id  -- Joining Group Booking
    ORDER BY
       rbl.id,
       ds.report_date,
       rbls.change_time DESC NULLS LAST
),

/* ----------------------------------------------------------------------------
   2) IN-HOUSE:
   Count bookings with status 'check_in' for each Group Booking.
---------------------------------------------------------------------------- */
in_house AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.group_booking_name,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.checkin_date <= lls.report_date
      AND lls.checkout_date > lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.group_booking_name
),

/* ----------------------------------------------------------------------------
   3) EXPECTED ARRIVALS:
   Count bookings arriving on the report_date.
---------------------------------------------------------------------------- */
expected_arrivals AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.group_booking_name,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.group_booking_name
),

/* ----------------------------------------------------------------------------
   4) EXPECTED DEPARTURES:
   Count bookings departing on the report_date.
---------------------------------------------------------------------------- */
expected_departures AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.group_booking_name,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.group_booking_name
),

/* ----------------------------------------------------------------------------
   5) MASTER_KEYS:
   Create a master list of all relevant keys from in_house, expected_arrivals, and expected_departures.
---------------------------------------------------------------------------- */
master_keys AS (
    SELECT report_date, company_id, room_type_id, group_booking_name
    FROM in_house
    UNION
    SELECT report_date, company_id, room_type_id, group_booking_name
    FROM expected_arrivals
    UNION
    SELECT report_date, company_id, room_type_id, group_booking_name
    FROM expected_departures
),

/* ----------------------------------------------------------------------------
   6) FINAL REPORT:
   Combine in_house, expected_arrivals, and expected_departures to calculate expected_in_house.
---------------------------------------------------------------------------- */
final_report AS (
    SELECT
        mk.report_date,
        mk.company_id,
        mk.room_type_id,
        mk.group_booking_name,
        COALESCE(ih.in_house_count, 0) AS in_house_count,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures_count,
        -- Prevent negative values
        GREATEST(
            (COALESCE(ih.in_house_count, 0)
             + COALESCE(ea.expected_arrivals_count, 0)
             - COALESCE(ed.expected_departures_count, 0)),
            0
        ) AS expected_in_house
    FROM master_keys mk
    LEFT JOIN in_house ih
        ON mk.report_date = ih.report_date
       AND mk.company_id = ih.company_id
       AND mk.room_type_id = ih.room_type_id
       AND mk.group_booking_name = ih.group_booking_name
    LEFT JOIN expected_arrivals ea
        ON mk.report_date = ea.report_date
       AND mk.company_id = ea.company_id
       AND mk.room_type_id = ea.room_type_id
       AND mk.group_booking_name = ea.group_booking_name
    LEFT JOIN expected_departures ed
        ON mk.report_date = ed.report_date
       AND mk.company_id = ed.company_id
       AND mk.room_type_id = ed.room_type_id
       AND mk.group_booking_name = ed.group_booking_name
)

SELECT
    fr.report_date,
    fr.company_id,
    rc.name AS company_name,
    fr.room_type_id,
    rt.room_type AS room_type_name,
    fr.group_booking_name,
    fr.expected_in_house
FROM final_report fr
JOIN res_company rc ON fr.company_id = rc.id
JOIN room_type rt ON fr.room_type_id = rt.id
ORDER BY
    fr.report_date,
    rc.name,
    rt.room_type,
    fr.group_booking_name;
        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
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
                records_to_create.append({
                    'company_id': company_id,
                    'report_date': result[0],               # Date
                    'group_booking': result[5],             # group_booking_name
                    'room_type': result[4],                 # room_type_name
                    'expected_inhouse': int(result[6] or 0),# expected_in_house
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
