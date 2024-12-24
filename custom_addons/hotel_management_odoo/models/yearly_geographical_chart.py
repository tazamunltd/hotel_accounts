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
    expected_arrivals = fields.Integer(string='Expected Arrivals', readonly=True)
    expected_departures = fields.Integer(string='Expected Departures', readonly=True)
    expected_inhouse = fields.Integer(string='Expected In House', readonly=True)
    reserved = fields.Integer(string='Reserved', readonly=True)
    expected_occupied_rate = fields.Float(string='Expected Occupied Rate (%)', readonly=True)  
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
        rb.nationality AS nationality_id,
        rc.name AS company_name
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
expected_in_house_data AS (
    SELECT
        hrb.report_date,
        hrb.room_type_id,
        hrb.company_id,
        hrb.nationality_id,
        COUNT(DISTINCT hrb.id) AS expected_in_house_count
    FROM hrb
    WHERE hrb.state IN ('check_in', 'reserved')
    GROUP BY hrb.report_date, hrb.room_type_id, hrb.company_id, hrb.nationality_id
)
SELECT
    rc.id AS "Company ID",
    rc.name AS "Company Name",
    cr."Region" AS "Region",
    jsonb_extract_path_text(rc_country.name::jsonb, 'en_US') AS "Country",  -- Extract English value
    eih.report_date AS "Date",
    rt.room_type_name AS "Room Type",
    SUM(tr.total_rooms) AS "Total Rooms",
    SUM(COALESCE(eih.expected_in_house_count, 0)) AS "Expected In House"
FROM expected_in_house_data eih
LEFT JOIN room_types rt ON eih.room_type_id = rt.room_type_id
LEFT JOIN res_company rc ON eih.company_id = rc.id
LEFT JOIN res_country rc_country ON eih.nationality_id = rc_country.id
LEFT JOIN country_region_res_country_rel crrc ON rc_country.id = crrc.res_country_id
LEFT JOIN country_region cr ON crrc.country_region_id = cr.id
LEFT JOIN (
    SELECT
        tr.report_date,
        rt.room_type_id,
        hr.company_id,
        COUNT(hr.id) AS total_rooms
    FROM date_series tr
    CROSS JOIN room_types rt
    LEFT JOIN hotel_room hr ON hr.room_type_name = rt.room_type_id
    GROUP BY tr.report_date, rt.room_type_id, hr.company_id
) tr ON eih.report_date = tr.report_date
   AND eih.room_type_id = tr.room_type_id
   AND eih.company_id = tr.company_id
GROUP BY rc.id, rc.name, cr."Region", jsonb_extract_path_text(rc_country.name::jsonb, 'en_US'), eih.report_date, rt.room_type_name
ORDER BY rc.id, rc.name, cr."Region", jsonb_extract_path_text(rc_country.name::jsonb, 'en_US'), eih.report_date, rt.room_type_name;


        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
        records_to_create = []

        for result in results:
            try:
                records_to_create.append({
                    'company_id': result[0],              # Company ID
                    'report_date': result[4],             # Date
                    'region': result[2],                  # Region
                    'nationality': result[3],             # Country (Nationality)
                    'room_type': result[5],               # Room Type
                    'total_rooms': int(result[6] or 0),   # Total Rooms
                    'expected_inhouse': int(result[7] or 0),  # Expected In House
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