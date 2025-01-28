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
        COALESCE((SELECT MIN(rb.checkin_date::date) FROM room_booking rb), CURRENT_DATE) AS from_date,
        COALESCE((SELECT MAX(rb.checkout_date::date) FROM room_booking rb), CURRENT_DATE) AS to_date
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
           rb.house_use            AS house_use,
           rb.complementary        AS complementary,
           rb.nationality          AS nationality_id
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb    ON rb.id = rbl.booking_id
    JOIN hotel_room hr      ON hr.id = rbl.room_id
    JOIN room_type rt       ON rt.id = hr.room_type_name
    JOIN group_booking gb       ON rb.group_booking = gb.id 
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
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        sub.nationality_id,
        COUNT(DISTINCT sub.booking_line_number) AS in_house_count
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type   rt

    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number,
               qry.nationality_id
             
        FROM (
            SELECT 
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rbl.checkin_date,
                rbl.checkout_date,
                rbl.id              AS booking_line_number,
                rbls.status,
                rbls.change_time,
                rb.nationality          AS nationality_id
            FROM room_booking rb
            JOIN room_booking_line rbl
                  ON rbl.booking_id = rb.id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
            JOIN res_partner rp
                  ON rb.partner_id = rp.id
			JOIN group_booking gb       ON rb.group_booking = gb.id 
        ) AS qry
        WHERE qry.company_id     = rc.id
          AND qry.room_type_id   = rt.id
          AND qry.checkin_date::date <= ds.report_date
          AND qry.checkout_date::date > ds.report_date
          AND qry.status = 'check_in'
          AND qry.change_time::date <= ds.report_date
        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE

    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id,
        sub.nationality_id
),
expected_arrivals AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        sub.nationality_id,
        COUNT(DISTINCT sub.booking_line_number) AS expected_arrivals_count
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type   rt

    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number,
               qry.nationality_id
        FROM (
            SELECT 
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rbl.checkin_date    AS checkin_dt,
                rb.name,
                rbls.status,
                rbl.id              AS booking_line_number,
                rbls.change_time,
                rb.nationality          AS nationality_id
            FROM room_booking rb
            JOIN room_booking_line rbl 
                  ON rbl.booking_id = rb.id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
            JOIN res_partner rp
                  ON rb.partner_id = rp.id
		
        ) AS qry
        WHERE qry.company_id    = rc.id
          AND qry.room_type_id  = rt.id
          AND qry.status        IN ('confirmed','block')
          AND qry.change_time::date <= ds.report_date
          AND qry.checkin_dt::date   = ds.report_date
        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE
    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id,
        sub.nationality_id
),
expected_departures AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        sub.nationality_id,
        COUNT(DISTINCT sub.booking_line_number) AS expected_departures_count
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type   rt

    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number,
               qry.nationality_id
        FROM (
            SELECT 
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rbl.checkin_date,
                rbl.checkout_date,
                rbl.id              AS booking_line_number,
                rbls.status,
                rbls.change_time,
                rb.nationality          AS nationality_id
            FROM room_booking rb
            JOIN room_booking_line rbl
                  ON rbl.booking_id = rb.id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
            JOIN res_partner rp
                  ON rb.partner_id = rp.id
			JOIN group_booking gb       ON rb.group_booking = gb.id 
        ) AS qry
        WHERE qry.company_id    = rc.id
          AND qry.room_type_id  = rt.id
          AND qry.checkout_date::date = ds.report_date
          AND qry.status = 'check_in'
          AND qry.change_time::date <= ds.report_date
        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE
    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id,
        sub.nationality_id
),
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
final_report AS (
    SELECT
        mk.report_date,
        mk.company_id,
        mk.room_type_id,
        mk.nationality_id,
        COALESCE(ih.in_house_count, 0) AS in_house_count,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures_count,
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
       AND mk.nationality_id= ed.nationality_id
)
SELECT
    fr.report_date,
    fr.company_id,
    rc.name AS company_name,
    fr.room_type_id,
    COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
    jsonb_extract_path_text(cr."Region"::jsonb, 'en_US') AS "Region",
    jsonb_extract_path_text(rc_country.name::jsonb, 'en_US') AS "Country",
    fr.expected_in_house
FROM final_report fr

LEFT JOIN res_company rc ON fr.company_id = rc.id
LEFT JOIN res_country rc_country ON fr.nationality_id = rc_country.id
LEFT JOIN country_region_res_country_rel crrc ON rc_country.id = crrc.res_country_id
LEFT JOIN country_region cr ON crrc.country_region_id = cr.id
LEFT JOIN room_type rt ON fr.room_type_id = rt.id	

WHERE cr."Region" IS NOT NULL
   OR rc_country.name IS NOT NULL
ORDER BY
    fr.report_date,
    rc.name,
    rt.room_type,
    cr."Region", 
    jsonb_extract_path_text(rc_country.name::jsonb, 'en_US');

	
        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
        records_to_create = []

        current_company_id = self.env.company.id

        for result in results:
            try:
                record_company_id = result[1]
                if record_company_id != current_company_id:
                    continue  # Skip records not belonging to the current company
                
                records_to_create.append({
                    'company_id': record_company_id,               # Company ID
                    'report_date': result[0],                      # Report Date
                    'region': result[5],                           # Region
                    'nationality': result[6],                      # Country (Nationality)
                    'room_type': result[4],                        # Room Type
                    'expected_inhouse': float(result[7] or 0),      # Expected In House
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