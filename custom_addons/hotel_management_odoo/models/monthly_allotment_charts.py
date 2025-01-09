from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class MonthlyAllotmentCharts(models.Model):
    _name = 'monthly.allotment.charts'
    _description = 'Monthly Allotment Charts'
    _inherit = ['mail.thread', 'mail.activity.mixin']



    report_date = fields.Date(string='Report Date', required=True,tracking=True)
    company_id = fields.Many2one('res.company',string='company', required = True,tracking=True)
    client_id = fields.Many2one('res.partner', string='Client',tracking=True)  
    region = fields.Char(string='Region',tracking=True)  
    nationality = fields.Char(string='Nationality',tracking=True)  
    room_type = fields.Char(string='Room Type', required=True,tracking=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True,tracking=True)
    available = fields.Integer(string='Available', readonly=True,tracking=True)
    inhouse = fields.Integer(string='In-House', readonly=True,tracking=True)
    expected_arrivals = fields.Integer(string='Exp.Arrivals', readonly=True,tracking=True)
    expected_departures = fields.Integer(string='Exp.Departures', readonly=True,tracking=True)
    expected_inhouse = fields.Integer(string='Exp.Inhouse', readonly=True,tracking=True)
    reserved = fields.Integer(string='Reserved', readonly=True,tracking=True)
    expected_occupied_rate = fields.Float(string='Exp.Occupied Rate (%)', readonly=True,tracking=True)  
    out_of_order = fields.Integer(string='Out of Order', readonly=True,tracking=True)
    overbook = fields.Integer(string='Overbook', readonly=True,tracking=True)
    free_to_sell = fields.Integer(string='Free to sell', readonly=True,tracking=True)
    sort_order = fields.Integer(string='Sort Order', readonly=True,tracking=True)
    source_of_business = fields.Char(string='Source of Business',tracking=True)
    

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        print("line 34")
        try:
            # Call the run_process method to execute the query and process results
            self.run_process_by_monthly_allotment()

        except Exception as e:
            _logger.error(f"Error generating room results: {str(e)}")
            raise ValueError(f"Error generating room results: {str(e)}")

    def run_process_by_monthly_allotment(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_monthly_allotment")
        
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
   Incorporate source_of_business.
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
           sb.description           AS source_of_business
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb        ON rb.id = rbl.booking_id
    JOIN hotel_room hr          ON hr.id = rbl.room_id
    JOIN room_type rt           ON rt.id = hr.room_type_name  -- Ensure hr.room_type_name is the ID
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
           AND rbls.change_time::date <= ds.report_date
    JOIN source_business sb      ON rb.source_of_business = sb.id
    ORDER BY
       rbl.id,
       ds.report_date,
       rbls.change_time DESC NULLS LAST
),

/* ----------------------------------------------------------------------------
   2) IN-HOUSE:
   Count bookings with status 'check_in' for each group.
---------------------------------------------------------------------------- */
in_house AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.source_of_business,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.checkin_date <= lls.report_date
      AND lls.checkout_date >= lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.source_of_business
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
        lls.source_of_business,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.source_of_business
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
        lls.source_of_business,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.source_of_business
),

/* ----------------------------------------------------------------------------
   5) FINAL REPORT:
   Combine in_house, expected_arrivals, and expected_departures to calculate expected_in_house.
---------------------------------------------------------------------------- */
final_report AS (
    SELECT
        COALESCE(ih.report_date, ea.report_date, ed.report_date) AS report_date,
        COALESCE(ih.company_id, ea.company_id, ed.company_id)   AS company_id,
        COALESCE(ih.room_type_id, ea.room_type_id, ed.room_type_id) AS room_type_id,
        COALESCE(ih.source_of_business, ea.source_of_business, ed.source_of_business) AS source_of_business,
        (COALESCE(ih.in_house_count, 0)
         + COALESCE(ea.expected_arrivals_count, 0)
         - COALESCE(ed.expected_departures_count, 0)) AS expected_in_house
    FROM in_house ih
    FULL OUTER JOIN expected_arrivals ea
        ON ih.report_date = ea.report_date
        AND ih.company_id = ea.company_id
        AND ih.room_type_id = ea.room_type_id
        AND ih.source_of_business = ea.source_of_business
    FULL OUTER JOIN expected_departures ed
        ON COALESCE(ih.report_date, ea.report_date) = ed.report_date
        AND COALESCE(ih.company_id, ea.company_id) = ed.company_id
        AND COALESCE(ih.room_type_id, ea.room_type_id) = ed.room_type_id
        AND COALESCE(ih.source_of_business, ea.source_of_business) = ed.source_of_business
)

SELECT
    fr.report_date,
    fr.company_id,
    rc.name AS company_name,
    fr.room_type_id,
    rt.room_type AS room_type_name,
    fr.source_of_business,
    fr.expected_in_house
FROM final_report fr
JOIN res_company rc ON fr.company_id = rc.id
JOIN room_type rt ON fr.room_type_id = rt.id
ORDER BY
    fr.report_date,
    rc.name,
    rt.room_type,
    fr.source_of_business;

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
                # Unpack the result tuple
                (
                    report_date,
                    company_id,
                    company_name,
                    room_type_id,
                    room_type_name,
                    source_of_business,
                    expected_in_house
                ) = result

                record = {
                    'company_id': company_id,                     # Integer
                    'report_date': report_date,                   # Date
                    'source_of_business': source_of_business,     # String
                    'room_type': room_type_name,                  # String
                    'expected_inhouse': int(expected_in_house or 0),  # Integer
                }
                _logger.debug(f"Creating record: {record}")
                records_to_create.append(record)
            except ValueError as ve:
                _logger.error(f"ValueError processing record: {ve}, Data: {result}")
                continue
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            try:
                self.create(records_to_create)
                _logger.info(f"{len(records_to_create)} records created")
            except Exception as e:
                _logger.error(f"Error creating records: {str(e)}")
                raise
        else:
            _logger.info("No records to create")
        _logger.info("Completed run_process_by_monthly_allotment")