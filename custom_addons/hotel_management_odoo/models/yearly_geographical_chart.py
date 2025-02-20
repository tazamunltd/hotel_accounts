# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)

class YearlyGeographicalChart(models.Model):
    _name = 'yearly.geographical.chart'
    _description = 'Yearly Geographical Chart'

    report_date = fields.Date(string='Report Date', required=True)
    company_id = fields.Many2one('res.company',string='Hotel', required = True)
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
    def action_run_process_by_region(self):
        """Runs the yearly geographical process based on context and returns the action."""
        if self.env.context.get('filtered_date_range'):
            self.env["yearly.geographical.chart"].run_process_by_region()

            return {
                'name': _('Yearly Geographical Chart'),
                'type': 'ir.actions.act_window',
                'res_model': 'yearly.geographical.chart',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref(
                        'hotel_management_odoo.yearly_geographical_chart_tree_view').id, 'tree'),
                    (self.env.ref(
                        'hotel_management_odoo.yearly_geographical_chart_graph_view').id, 'graph'),
                    (self.env.ref(
                        'hotel_management_odoo.yearly_geographical_chart_pivot_view').id, 'pivot'),
                ],
                'target': 'current',
            }
        else:
            return {
                'name': _('Yearly Geographical Chart'),
                'type': 'ir.actions.act_window',
                'res_model': 'yearly.geographical.chart',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref(
                        'hotel_management_odoo.yearly_geographical_chart_tree_view').id, 'tree'),
                    (self.env.ref(
                        'hotel_management_odoo.yearly_geographical_chart_graph_view').id, 'graph'),
                    (self.env.ref(
                        'hotel_management_odoo.yearly_geographical_chart_pivot_view').id, 'pivot'),
                ],
                'domain': [('id', '=', False)],  # Ensures no data is displayed
                'target': 'current',
            }

    @api.model
    def search_available_rooms_geographical(self, from_date, to_date):  # Fix typo here
        """
        Search for available rooms based on the provided criteria.
        """
        self.run_process_by_Region(from_date, to_date)
        company_ids = [company.id for company in self.env.companies]
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
            ('company_id', 'in', company_ids)
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

    def run_process_by_Region(self,from_date = None, to_date = None):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_Region")
        
        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")
        # system_date = self.env.company.system_date.date()
        # from_date = system_date - timedelta(days=7)
        # to_date = system_date + timedelta(days=7)
        # get_company = self.env.company.id
        company_ids = [company.id for company in self.env.companies]
        
        query = f"""WITH parameters AS (
     SELECT
        '{from_date}'::date AS from_date,
        '{to_date}'::date AS to_date
),
company_ids AS (
    SELECT unnest(ARRAY{company_ids}::int[]) AS company_id
),
date_series AS (
    SELECT DISTINCT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
    FROM parameters p
),
system_date_company AS (
    SELECT 
        rc.id AS company_id, 
        rc.system_date::date AS system_date
    FROM res_company rc
    WHERE rc.id IN (SELECT company_id FROM company_ids)
),
room_type_data AS (
    SELECT
        rt.id AS room_type_id,
        COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'), 'N/A') AS room_type_name
    FROM room_type rt
),
base_data AS (
    SELECT
          rb.id AS booking_id
        , rb.company_id
        , sdc.system_date::date AS system_date
        , rb.nationality AS nationality_id
        , rb.checkin_date::date AS checkin_date
        , rb.checkout_date::date AS checkout_date
        , rbl.id AS booking_line_id
        , rbl.room_id
        , rbl.hotel_room_type AS room_type_id
        , rbls.status
        , rbls.change_time
        , rb.house_use
        , rb.complementary
    FROM room_booking rb
    JOIN room_booking_line rbl 
          ON rb.id = rbl.booking_id
    LEFT JOIN room_booking_line_status rbls 
          ON rbl.id = rbls.booking_line_id
    LEFT JOIN res_partner rp 
          ON rb.partner_id = rp.id
    LEFT JOIN system_date_company sdc
          ON sdc.company_id = rb.company_id
    WHERE rb.company_id IN (SELECT company_id FROM company_ids)
),
inventory AS (
    SELECT
          hi.company_id
        , hi.room_type AS room_type_id
        , SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count
        , SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms
        , BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    GROUP BY hi.company_id, hi.room_type
),
latest_line_status AS (
    SELECT
          bd.booking_line_id
        , ds.report_date
        , bd.system_date
        , bd.checkin_date
        , bd.checkout_date
        , bd.company_id
        , bd.room_type_id
        , bd.nationality_id
        , bd.status AS final_status
        , bd.change_time
        , bd.house_use
        , bd.complementary
    FROM base_data bd
    JOIN date_series ds 
          ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
),
in_house AS (
    SELECT
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.nationality_id
        , COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
      AND lls.checkin_date = lls.report_date
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.nationality_id
),
yesterday_in_house AS (
    SELECT
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.nationality_id
        , COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
      AND (lls.report_date - INTERVAL '1 day')
          BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.nationality_id
),
expected_arrivals AS (
    SELECT 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.nationality_id
        , COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.nationality_id
),
expected_departures AS (
    SELECT
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.nationality_id
        , COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY 
          lls.report_date
        , lls.system_date
        , lls.company_id
        , lls.room_type_id
        , lls.nationality_id
),
master_keys AS (
    SELECT report_date, company_id, system_date, room_type_id, nationality_id
      FROM in_house
    UNION
    SELECT report_date, company_id, system_date, room_type_id, nationality_id
      FROM expected_arrivals
    UNION
    SELECT report_date, company_id, system_date, room_type_id, nationality_id
      FROM expected_departures
    UNION
    SELECT report_date, company_id, system_date, room_type_id, nationality_id
      FROM yesterday_in_house
),
final_report AS (
    SELECT
          mk.report_date
        , mk.system_date
        , mk.company_id
        , mk.room_type_id
        , mk.nationality_id
        , CASE WHEN mk.report_date <= mk.system_date THEN
            ih.in_house_count
          ELSE
            GREATEST(
                COALESCE(yh.in_house_count, 0)
                + COALESCE(ea.expected_arrivals_count, 0)
                - COALESCE(ed.expected_departures_count, 0),
                0
            )
          END AS in_house_count
        , COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count
        , COALESCE(ed.expected_departures_count, 0) AS expected_departures_count
        , GREATEST(
            COALESCE(yh.in_house_count, 0)
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
)
SELECT
      fr.report_date
    , fr.company_id 
    , rc.name AS company_name
    , rtd.room_type_name AS room_type
    , jsonb_extract_path_text(cr."Region"::jsonb, 'en_US') AS "region"
    , jsonb_extract_path_text(rc_country.name::jsonb, 'en_US') AS "nationality"
    , SUM(fr.expected_in_house) AS expected_in_house
FROM final_report fr
LEFT JOIN res_company rc 
       ON rc.id = fr.company_id
LEFT JOIN room_type_data rtd
       ON rtd.room_type_id = fr.room_type_id
LEFT JOIN res_country rc_country
       ON rc_country.id = fr.nationality_id
LEFT JOIN country_region_res_country_rel crrc
       ON rc_country.id = crrc.res_country_id
LEFT JOIN country_region cr
       ON crrc.country_region_id = cr.id
WHERE (cr."Region" IS NOT NULL
   OR rc_country.name IS NOT NULL) 
GROUP BY
      fr.report_date
    , fr.company_id
    , rc.name
    , rtd.room_type_name
    , cr."Region"
    , rc_country.name
ORDER BY
      fr.report_date
    , rc.name
    , rtd.room_type_name
    , cr."Region"
    , jsonb_extract_path_text(rc_country.name::jsonb, 'en_US');
"""
        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        # params = (from_date, to_date, get_company)
        # print('query', query)
        self.env.cr.execute(query)
        # self.env.cr.execute(query, (get_company, get_company, get_company))
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        # Initialize records_to_create as an empty list
        records_to_create = []

        current_company_id = self.env.company.id

        for result in results:
            try:
                # record_company_id = result[1]
                # if record_company_id != current_company_id:
                #     continue  # Skip records not belonging to the current company
                
                records_to_create.append({
                    'company_id': result[1],               # Company ID
                    'report_date': result[0],                      # Report Date
                    'region': result[4],                           # Region
                    'nationality': result[5],                      # Country (Nationality)
                    'room_type': result[3],                        # Room Type
                    'expected_inhouse': float(result[6] or 0),      # Expected In House
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