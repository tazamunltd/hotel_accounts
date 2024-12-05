# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class YearlyGeographicalChart(models.Model):
    _name = 'yearly.geographical.chart'
    _description = 'Yearly Geographical Chart'

    report_date = fields.Date(string='Report Date', required=True)
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
    SELECT generate_series(p.from_date, p.to_date, interval '1 day') AS report_date
    FROM parameters p
),
room_types AS (
    SELECT rt.id AS room_type_id,
           rt.room_type AS room_type_code, 
           rt.description AS room_type_name
    FROM room_type rt
),
hrb AS (
    SELECT
        rb.id,
        rb.checkin_date,
        rb.checkout_date,
        rb.state,
        rc.name->>'en_US' AS nationality,  
        rbl.room_id,
        hr.room_type_name AS room_type_id,
        cr."Region" AS region
    FROM room_booking rb
    JOIN room_booking_line rbl ON rbl.booking_id = rb.id
    JOIN hotel_room hr ON rbl.room_id = hr.id
    LEFT JOIN res_country rc ON rb.nationality = rc.id  
    LEFT JOIN country_region_res_country_rel crr ON rc.id = crr.res_country_id
    LEFT JOIN country_region cr ON crr.country_region_id = cr.id
),
partner_dates AS (
    SELECT DISTINCT
        ds.report_date,
        rt.room_type_id,
        hrb.nationality,
        hrb.region
    FROM date_series ds
    CROSS JOIN room_types rt
    JOIN hrb ON hrb.room_type_id = rt.room_type_id
              AND (
                  (hrb.checkin_date::date <= ds.report_date AND hrb.checkout_date::date > ds.report_date)
                  OR hrb.checkin_date::date = ds.report_date
                  OR hrb.checkout_date::date = ds.report_date
              )
),
in_house AS (
    SELECT
        ds.report_date,
        rt.room_type_id,
        hrb.nationality,
        hrb.region,
        COUNT(DISTINCT hrb.id) AS in_house
    FROM date_series ds
    CROSS JOIN room_types rt
    JOIN hrb ON hrb.checkin_date::date <= ds.report_date
              AND hrb.checkout_date::date > ds.report_date
              AND hrb.state = 'check_in'
              AND hrb.room_type_id = rt.room_type_id
    GROUP BY ds.report_date, rt.room_type_id, hrb.nationality, hrb.region
),
expected_arrivals AS (
    SELECT
        ds.report_date,
        rt.room_type_id,
        hrb.nationality,
        hrb.region,
        COUNT(DISTINCT hrb.id) AS expected_arrivals
    FROM date_series ds
    CROSS JOIN room_types rt
    JOIN hrb ON hrb.checkin_date::date = ds.report_date
              AND hrb.state IN ('confirmed', 'block')
              AND hrb.room_type_id = rt.room_type_id
    GROUP BY ds.report_date, rt.room_type_id, hrb.nationality, hrb.region
),
expected_departures AS (
    SELECT
        ds.report_date,
        rt.room_type_id,
        hrb.nationality,
        hrb.region,
        COUNT(DISTINCT hrb.id) AS expected_departures
    FROM date_series ds
    CROSS JOIN room_types rt
    JOIN hrb ON hrb.checkout_date::date = ds.report_date
              AND hrb.state = 'check_in'
              AND hrb.room_type_id = rt.room_type_id
    GROUP BY ds.report_date, rt.room_type_id, hrb.nationality, hrb.region
),
daily_data AS (
    SELECT
        pd.report_date,
        pd.room_type_id,
        pd.nationality,
        pd.region,
        COALESCE(ih.in_house, 0) AS in_house,
        COALESCE(ea.expected_arrivals, 0) AS expected_arrivals,
        COALESCE(ed.expected_departures, 0) AS expected_departures
    FROM partner_dates pd
    LEFT JOIN in_house ih ON pd.report_date = ih.report_date AND pd.room_type_id = ih.room_type_id AND pd.nationality = ih.nationality AND pd.region = ih.region
    LEFT JOIN expected_arrivals ea ON pd.report_date = ea.report_date AND pd.room_type_id = ea.room_type_id AND pd.nationality = ea.nationality AND pd.region = ea.region
    LEFT JOIN expected_departures ed ON pd.report_date = ed.report_date AND pd.room_type_id = ed.room_type_id AND pd.nationality = ed.nationality AND pd.region = ed.region
),
expected_in_house_data AS (
    SELECT
        dd.*,
        SUM(dd.expected_arrivals - dd.expected_departures) OVER (
            PARTITION BY dd.room_type_id, dd.nationality, dd.region ORDER BY dd.report_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) + dd.in_house AS expected_in_house
    FROM daily_data dd
),
total_rooms AS (
    SELECT
        tr.report_date,
        rt.room_type_id,
        rt.room_type_name,
        COUNT(hr.id) AS total_rooms
    FROM date_series tr
    CROSS JOIN room_types rt
    LEFT JOIN hotel_room hr ON hr.room_type_name = rt.room_type_id
    GROUP BY tr.report_date, rt.room_type_id, rt.room_type_name
)
SELECT
    eih.report_date AS "Date",
    COALESCE(rt.room_type_name, 'Total') AS "Room Type",
    eih.region AS "Region",
    eih.nationality AS "Nationality",  
    SUM(tr.total_rooms) AS "Total Rooms",
    SUM(eih.in_house) AS "In House",
    SUM(eih.expected_arrivals) AS "Expected Arrivals",
    SUM(eih.expected_departures) AS "Expected Departures",
    SUM(eih.expected_in_house) AS "Expected In House",
    ROUND((SUM(eih.expected_in_house::numeric) / NULLIF(SUM(tr.total_rooms::numeric), 0)) * 100, 2) AS "Expected Occupied Rate (%)"
FROM expected_in_house_data eih
LEFT JOIN room_types rt ON eih.room_type_id = rt.room_type_id
LEFT JOIN total_rooms tr ON eih.report_date = tr.report_date AND eih.room_type_id = tr.room_type_id
GROUP BY eih.report_date, rt.room_type_name, eih.region, eih.nationality
ORDER BY eih.report_date, rt.room_type_name, eih.region, eih.nationality;
        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
        records_to_create = []

        for result in results:
            records_to_create.append({
                'report_date': result[0],
                'room_type': result[1],
                'region': result[2],
                'nationality': result[3],
                'total_rooms': result[4] or 0,
                'inhouse': result[5] or 0,
                'expected_arrivals': result[6] or 0,
                'expected_departures': result[7] or 0,
                'expected_inhouse': result[8] or 0,
                'expected_occupied_rate': result[9] or 0.0,
            })
        
        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
        _logger.info("Completed run_process_by_Region")
