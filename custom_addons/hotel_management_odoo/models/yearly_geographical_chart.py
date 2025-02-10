# -*- coding: utf-8 -*-
from datetime import timedelta
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

    @api.model
    def search_available_rooms_geographical(self, from_date, to_date):  # Fix typo here
        """
        Search for available rooms based on the provided criteria.
        """
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
        ]

        results = self.search(domain)

        return results.read([
            'report_date',
            'room_type',
            'company_id',
            'nationality',
            'region',
            'expected_inhouse'
        ])



    def action_generate_results(self):
        """Generate and update room results by nationality."""
        # Fetch the region record
        region_record = self.env['region.model'].search([], limit=1)
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


#         WITH parameters AS (
#     SELECT
#         COALESCE((SELECT MIN(rb.checkin_date::date) FROM room_booking rb), CURRENT_DATE) AS from_date,
#         COALESCE((SELECT MAX(rb.checkout_date::date) FROM room_booking rb), CURRENT_DATE) AS to_date
# ),

    def run_process_by_Region(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_Region")
        
        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")
        system_date = self.env.company.system_date.date()
        from_date = system_date - timedelta(days=7)
        to_date = system_date + timedelta(days=7)
        get_company = self.env.company.id

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
system_date_company AS (
	select id as company_id 
	, system_date::date	from res_company rc where  rc.id = (SELECT company_id FROM parameters)
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
        rb.nationality as nationality_id,
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
latest_line_status AS (
    SELECT DISTINCT ON (bd.booking_line_id, ds.report_date)
           bd.booking_line_id,
           ds.report_date,
           bd.checkin_date,
           bd.checkout_date,
           bd.company_id,
           bd.room_type_id,
           bd.nationality_id,
           bd.status AS final_status,
           bd.change_time,
           bd.house_use,
           bd.complementary
    FROM base_data bd
    JOIN date_series ds 
      ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
    ORDER BY
       bd.booking_line_id,
       ds.report_date,
       bd.change_time DESC NULLS LAST
),
in_house AS (
    SELECT 
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.nationality_id,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
      AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.nationality_id
),
yesterday_in_house AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.nationality_id,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
      AND lls.report_date - interval '1 day' BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.nationality_id
),
expected_arrivals AS (
    SELECT
        bd.checkin_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.nationality_id,
        COUNT(DISTINCT bd.booking_line_id) AS expected_arrivals_count
    FROM base_data bd
    WHERE bd.status IN ('confirmed', 'block')
    GROUP BY bd.checkin_date, bd.company_id, bd.room_type_id, bd.nationality_id
),
expected_departures AS (
    SELECT
        bd.checkout_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.nationality_id,
        COUNT(DISTINCT bd.booking_line_id) AS expected_departures_count
    FROM base_data bd
    WHERE bd.status = 'check_in'
    GROUP BY bd.checkout_date, bd.company_id, bd.room_type_id, bd.nationality_id
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
        GREATEST(0, 
      -- Use ih.in_house_count when system_date is today, otherwise use yh.in_house_count
      COALESCE(
          CASE 
              WHEN sdc.system_date = mk.report_date THEN ih.in_house_count 
              ELSE yh.in_house_count 
          END, 0
      ) 
      + COALESCE(ea.expected_arrivals_count, 0)
      - LEAST(COALESCE(ed.expected_departures_count, 0), 
              COALESCE(
                  CASE 
                      WHEN sdc.system_date = mk.report_date THEN ih.in_house_count 
                      ELSE yh.in_house_count 
                  END, 0
              )
      )
    ) AS expected_in_house
    FROM master_keys mk
    LEFT JOIN in_house ih
        ON mk.report_date = ih.report_date
       AND mk.company_id = ih.company_id
       AND mk.room_type_id = ih.room_type_id
       AND mk.nationality_id = ih.nationality_id
    LEFT JOIN yesterday_in_house yh
        ON mk.report_date = yh.report_date
       AND mk.company_id = yh.company_id
       AND mk.room_type_id = yh.room_type_id
       AND mk.nationality_id = yh.nationality_id
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
    
       LEFT JOIN system_date_company sdc on sdc.company_id = mk.company_id
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
JOIN res_company rc ON fr.company_id = rc.id
JOIN room_type rt ON fr.room_type_id = rt.id
LEFT JOIN res_country rc_country ON rc_country.id = fr.nationality_id
LEFT JOIN country_region_res_country_rel crrc ON rc_country.id = crrc.res_country_id
LEFT JOIN country_region cr ON crrc.country_region_id = cr.id
WHERE cr."Region" IS NOT NULL
   OR rc_country.name IS NOT NULL
ORDER BY
    fr.report_date,
    rc.name,
    rt.room_type,
    cr."Region",
    jsonb_extract_path_text(rc_country.name::jsonb, 'en_US');"""
        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        self.env.cr.execute(query, (get_company, get_company, get_company))
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