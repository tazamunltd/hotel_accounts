# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class YearlyGeographicalChart(models.Model):
    _name = 'yearly.geographical.chart'
    _description = 'Yearly Geographical Chart'

    report_date = fields.Date(string='Report Date', required=True)
    company_id = fields.Many2one('res.company',string='company', required = True)
    client_id = fields.Many2one('res.partner', string='Client')  
    region = fields.Char(string='Region')  
    nationality = fields.Char(string='Nationality')  
    room_type = fields.Char(string='Room Type', required=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True)
    available = fields.Integer(string='Available', readonly=True)
    inhouse = fields.Integer(string='In-House', readonly=True)
    expected_arrivals = fields.Integer(string='Exp.Arrivals', readonly=True)
    expected_departures = fields.Integer(string='Exp.Departures', readonly=True)
    expected_inhouse = fields.Integer(string='Exp.Inhouse', readonly=True)
    reserved = fields.Integer(string='Reserved', readonly=True)
    expected_occupied_rate = fields.Float(string='Exp.Occupied Rate (%)', readonly=True)  
    out_of_order = fields.Integer(string='Out of Order', readonly=True)
    overbook = fields.Integer(string='Overbook', readonly=True)
    free_to_sell = fields.Integer(string='Free to sell', readonly=True)
    sort_order = fields.Integer(string='Sort Order', readonly=True)
    

    def action_generate_results(self):
        """Generate and update room results by nationality."""
        # Fetch the region record
        region_record = self.env['region.model'].search([('name', '=', 'American Samoa')], limit=1)
        if not region_record:
            raise ValueError("No region found for 'American Samoa'")
        
        # Update the region field for the current record(s)
        self.write({'region': region_record.id})

        try:
            # Run the process to generate results
            self.run_process_by_Region()
        except Exception as e:
            # Log the error and raise a user-friendly error
            _logger.error(f"Error generating room results: {str(e)}")
            raise ValueError(f"Error generating room results: {str(e)}")


    def run_process_by_Region(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_Region")
        
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
   Incorporate nationality.
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
           rb.nationality          AS nationality_id
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb        ON rb.id = rbl.booking_id
    JOIN hotel_room hr          ON hr.id = rbl.room_id
    JOIN room_type rt           ON rt.id = hr.room_type_name
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
           AND rbls.change_time::date <= ds.report_date
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
        lls.nationality_id,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.checkin_date <= lls.report_date
      AND lls.checkout_date >= lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.nationality_id
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
        lls.nationality_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.nationality_id
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
        lls.nationality_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.nationality_id
),

/* ----------------------------------------------------------------------------
   5) MASTER_KEYS:
   Create a master list of all relevant keys from in_house, expected_arrivals, and expected_departures.
---------------------------------------------------------------------------- */
master_keys AS (
    SELECT report_date, company_id, room_type_id, nationality_id
    FROM in_house
    UNION
    SELECT report_date, company_id, room_type_id, nationality_id
    FROM expected_arrivals
    UNION
    SELECT report_date, company_id, room_type_id, nationality_id
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
        mk.nationality_id,
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
       AND mk.nationality_id = ih.nationality_id
    LEFT JOIN expected_arrivals ea
        ON mk.report_date = ea.report_date
       AND mk.company_id = ea.company_id
       AND mk.room_type_id = ea.room_type_id
       AND mk.nationality_id = ea.nationality_id
    LEFT JOIN expected_departures ed
        ON mk.report_date = ed.report_date
       AND mk.company_id = ed.company_id
       AND mk.room_type_id = ed.room_type_id
       AND mk.nationality_id = ed.nationality_id
)

SELECT
    rc.id AS "Company ID",
    rc.name AS "Company Name",
    cr."Region" AS "Region",
    jsonb_extract_path_text(rc_country.name::jsonb, 'en_US') AS "Country",  -- Extract English value
    fr.report_date AS "Date",
    rt.room_type AS "Room Type",
    SUM(COALESCE(fr.expected_in_house, 0)) AS "Expected In House"
FROM final_report fr
LEFT JOIN res_company rc ON fr.company_id = rc.id
LEFT JOIN res_country rc_country ON fr.nationality_id = rc_country.id
LEFT JOIN country_region_res_country_rel crrc ON rc_country.id = crrc.res_country_id
LEFT JOIN country_region cr ON crrc.country_region_id = cr.id
LEFT JOIN room_type rt ON fr.room_type_id = rt.id
GROUP BY 
    rc.id, 
    rc.name, 
    cr."Region", 
    jsonb_extract_path_text(rc_country.name::jsonb, 'en_US'),  -- Must match the SELECT
    fr.report_date, 
    rt.room_type
ORDER BY 
    rc.id, 
    rc.name, 
    cr."Region", 
    jsonb_extract_path_text(rc_country.name::jsonb, 'en_US'), 
    fr.report_date, 
    rt.room_type;
        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
        records_to_create = []

        for result in results:
            try:
                if result[1]:
                    company_id = result[0]
                    if company_id != self.env.company.id:
                        continue  
                    # print(result[1])  
                else:
                    continue
                records_to_create.append({
                    'company_id': result[0],              # Company ID
                    'report_date': result[4],             # Date
                    'region': result[2],                  # Region
                    'nationality': result[3],             # Country (Nationality)
                    'room_type': result[5],               # Room Type
                    'expected_inhouse': float(result[6] or 0),  # Expected In House
                })
                            # 'total_rooms': int(result[6] or 0),        # Total Rooms
                    # 'available': int(result[7] or 0),          # Available Rooms
                    # 'inhouse': int(result[8] or 0),            # In House
                    # 'expected_arrivals': int(result[9] or 0),  # Expected Arrivals
                    # 'expected_departures': int(result[10] or 0), # Expected Departures
                    #    # Expected In House
                    # 'reserved': int(result[12] or 0),           # Reserved
                    # 'expected_occupied_rate': float(result[13] or 0.0), # Expected Occupied Rate
                    # 'out_of_order': int(result[14] or 0),      # Out of Order Count
                    # 'overbook': int(result[15] or 0),          # Overbooked Count
                    # 'free_to_sell': int(result[16] or 0),      # Free to Sell
                    # 'sort_order': int(result[17] or 0),        # Sort Order
                
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
        _logger.info("Completed run_process_by_Region")