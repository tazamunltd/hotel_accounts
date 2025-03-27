from odoo import models, fields, api, _
import logging
import datetime
from datetime import timedelta

_logger = logging.getLogger(__name__)

class MealsByNationalityForecast(models.Model):
    _name = 'meals.by.nationality.forecast'
    _description = 'Meals By Nationality Forecast'

    company_id = fields.Many2one('res.company', string='Hotel', required=True)
    report_date = fields.Date(string='Report Date', required=True)
    room_type_name = fields.Char(string='Room Type')
    meal_pattern = fields.Char(string='Meal Pattern')
    country_name = fields.Char(string='Nationality')
    expected_arrivals = fields.Integer(string='Expected Arrivals')
    expected_departures = fields.Integer(string='Expected Departures')
    in_house = fields.Integer(string='In House')
    expected_arrivals_adults = fields.Integer(string='Expected Arrivals Adults')
    expected_arrivals_children = fields.Integer(string='Expected Arrivals Children')
    expected_arrivals_infants = fields.Integer(string='Expected Arrivals Infants')
    expected_arrivals_total = fields.Integer(string='Expected Arrivals Total')
    expected_departures_adults = fields.Integer(string='Expected Departures Adults')
    expected_departures_children = fields.Integer(string='Expected Departures Children')
    expected_departures_infants = fields.Integer(string='Expected Departures Infants')
    expected_departures_total = fields.Integer(string='Expected Departures Total')
    in_house_adults = fields.Integer(string='In House Adults')
    in_house_children = fields.Integer(string='In House Children')
    in_house_infants = fields.Integer(string='In House Infants')
    in_house_total = fields.Integer(string='In House Total')
    company_name = fields.Char(string='Company Name')
    total_adults = fields.Integer(string='Total Adults')
    total_children = fields.Integer(string='Total Children')
    total_infants = fields.Integer(string='Total Infants')
    total_of_all = fields.Integer(string='Total of All')

    @api.model
    def action_run_process_by_meals_by_nationality_forecast(self):
        """Runs the meals by nationality forecast process based on context and returns the action."""
        system_date = self.env.company.system_date.date()  # or fields.Date.today() if needed
        default_from_date = system_date
        default_to_date = system_date + timedelta(days=30)

        if self.env.context.get('filtered_date_range'):
            self.env["meals.by.nationality.forecast"].run_process_by_meals_by_nationality_forecast()

            return {
                'name': _('Meals by Nationality Forecast Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'meals.by.nationality.forecast',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref('hotel_management_odoo.view_meals_by_nationality_forecast_tree').id, 'tree'),
                    (self.env.ref('hotel_management_odoo.view_meals_by_nationality_forecast_graph').id, 'graph'),
                    (self.env.ref('hotel_management_odoo.view_meals_by_nationality_forecast_pivot').id, 'pivot'),
                ],
                'target': 'current',
            }
        else:
            self.env["meals.by.nationality.forecast"].run_process_by_meals_by_nationality_forecast(
                from_date=default_from_date,
                to_date=default_to_date
            )

            # 3) Show only records for that 30-day window by specifying a domain
            domain = [
                ('report_date', '>=', default_from_date),
                ('report_date', '<=', default_to_date),
            ]
            return {
                'name': _('Meals by Nationality Forecast Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'meals.by.nationality.forecast',
                'view_mode': 'tree,graph,pivot',
                'views': [
                    (self.env.ref('hotel_management_odoo.view_meals_by_nationality_forecast_tree').id, 'tree'),
                    (self.env.ref('hotel_management_odoo.view_meals_by_nationality_forecast_graph').id, 'graph'),
                    (self.env.ref('hotel_management_odoo.view_meals_by_nationality_forecast_pivot').id, 'pivot'),
                ],
                'domain': domain,  # Ensures no data is displayed
                'target': 'current',
            }

    @api.model
    def search_available_rooms(self, from_date, to_date):
        """
        Search for available rooms based on the provided criteria.
        """
        self.run_process_by_meals_by_nationality_forecast(from_date, to_date)
        company_ids = [company.id for company in self.env.companies]
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
            ('company_id', 'in', company_ids)
        ]

        results = self.search(domain)

        return results.read([
            'report_date',
            'company_id',
            'room_type_name',
            'meal_pattern',
            'country_name',
            'expected_arrivals',
            'expected_departures',
            'in_house',
            'expected_arrivals_adults',
            'expected_arrivals_children',
            'expected_arrivals_infants',
            'expected_arrivals_total',
            'expected_departures_adults',
            'expected_departures_children',
            'expected_departures_infants',
            'expected_departures_total',
            'in_house_adults',
            'in_house_children',
            'in_house_infants',
            'in_house_total',
            'company_name',
            'total_adults',
            'total_children',
            'total_infants',
            'total_of_all'
        ])

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_meals_by_nationality_forecast()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")
        
#             query = """
#         WITH parameters AS (
#     SELECT
#         COALESCE(
#             (SELECT MIN(rb.checkin_date::date) FROM room_booking rb), 
#             CURRENT_DATE
#         ) AS from_date,
#         COALESCE(
#             (SELECT MAX(rb.checkout_date::date) FROM room_booking rb), 
#             CURRENT_DATE
#         ) AS to_date
# ),

    def run_process_by_meals_by_nationality_forecast(self,from_date = None, to_date = None):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_meals_by_nationality_forecast")

        # Scoped deletion to current company
        self.search([]).unlink()

        if not from_date or not to_date:
            # Fallback if the method is called without parameters
            system_date = self.env.company.system_date.date()
            from_date = system_date
            to_date = system_date + timedelta(days=30)
        _logger.info("Existing records for the current company deleted")
        
        # system_date = self.env.company.system_date.date()
        # from_date = system_date - datetime.timedelta(days=7)
        # to_date = system_date + datetime.timedelta(days=7)
        # get_company = self.env.company.id
        company_ids = [company.id for company in self.env.companies]

        query = f"""
WITH parameters AS (
    SELECT
        '{from_date}'::date AS from_date,
        '{to_date}'::date AS to_date
),
company_ids AS (
    SELECT unnest(ARRAY{company_ids}::int[]) AS company_id
),
system_date_company AS (
    SELECT 
        id AS company_id, 
        system_date::date AS system_date,
        create_date::date AS create_date
    FROM res_company rc 
    WHERE rc.id IN (SELECT company_id FROM company_ids)
),

date_series AS (
    SELECT generate_series(
        GREATEST(p.from_date, c.create_date), 
        p.to_date, 
        INTERVAL '1 day'
    )::date AS report_date
    FROM parameters p
    CROSS JOIN system_date_company c
),

inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count,
        SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms,
        BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    GROUP BY hi.company_id, hi.room_type
),
room_type_data AS (
    SELECT
        rt.id AS room_type_id,
        COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'), 'N/A') AS room_type_name
    FROM room_type rt
),
base_data AS (
    SELECT
        rb.id AS booking_id,
        rb.company_id,
        rb.partner_id AS customer_id,
        rp.name AS customer_name,
        rb.nationality AS nationality_id,
		rcs.name as company_name,
		rtd.room_type_name,
		COALESCE(jsonb_extract_path_text(rc.name::jsonb, 'en_US'),'N/A') AS nationality_name,
        rb.meal_pattern AS meal_pattern_id,
        COALESCE(jsonb_extract_path_text(mp.abbreviation::jsonb, 'en_US'),'N/A') AS meal_pattern_name,
        rb.checkin_date::date AS checkin_date,
        rb.checkout_date::date AS checkout_date,
		sdc.system_date ::date as system_date,
        rbl.id AS booking_line_id,
        rbl.room_id,
        rbl.hotel_room_type AS room_type_id,
        rbl.adult_count,
        rb.child_count,
        rb.infant_count,
        rbls.status,
        rbls.change_time,
        rb.house_use,
        rb.complementary
    FROM room_booking rb
    JOIN room_booking_line rbl ON rb.id = rbl.booking_id
    LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
    LEFT JOIN res_partner rp ON rb.partner_id = rp.id
    LEFT JOIN public.meal_pattern mp ON rb.meal_pattern = mp.id
	LEFT JOIN res_country as rc ON rb.nationality = rc.id
	LEFT JOIN system_date_company sdc
        ON sdc.company_id = rb.company_id
	LEFT JOIN res_company rcs 
       ON rcs.id = rb.company_id
	LEFT JOIN room_type_data rtd
       ON rtd.room_type_id = rbl.hotel_room_type
    WHERE rb.company_id in (SELECT company_id FROM company_ids)
),
latest_line_status AS (
    SELECT 
    -- 	DISTINCT ON (bd.booking_line_id, ds.report_date)
		ds.report_date,
        bd.system_date,
        bd.checkin_date,
        bd.checkout_date,
        bd.booking_id,
        bd.company_id,
		bd.company_name,
        bd.nationality_id,
		bd.nationality_name,
        bd.meal_pattern_id,  
		bd.meal_pattern_name,
        bd.booking_line_id,
        bd.room_id,
        bd.room_type_id,
		bd.room_type_name,
        bd.adult_count,
        bd.child_count,
        bd.infant_count,
     	bd.status as final_status,   
		bd.change_time,
        bd.house_use,
        bd.complementary
       
    FROM base_data bd
    JOIN date_series ds 
        ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
	ORDER BY bd.booking_line_id, ds.report_date, bd.change_time DESC
	
)
,
in_house AS (
    SELECT
        lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_name,
        lls.room_type_id,
		lls.nationality_id,
		lls.nationality_name,
		lls.meal_pattern_id,
		lls.meal_pattern_name,
	 	COUNT(DISTINCT lls.booking_line_id) AS in_house_count,
        SUM(lls.adult_count) AS in_house_adults,
        SUM(lls.child_count) AS in_house_children,
        SUM(lls.infant_count) AS in_house_infants
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
	and lls.checkin_date = lls.report_date 
    GROUP BY 
        lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_name,
        lls.room_type_id,
	 	lls.nationality_id,
		lls.nationality_name,
		lls.meal_pattern_id,
		lls.meal_pattern_name
),
yesterday_in_house AS (
    SELECT
         lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_name,
        lls.room_type_id,
	 	lls.nationality_id,
		lls.nationality_name,
		lls.meal_pattern_id,
		lls.meal_pattern_name,
	 	COUNT(DISTINCT lls.booking_line_id) AS yin_house_count,
        SUM(lls.adult_count) AS yin_house_adults,
        SUM(lls.child_count) AS yin_house_children,
        SUM(lls.infant_count) AS yin_house_infants
    FROM latest_line_status lls
    WHERE lls.final_status = 'check_in'
      AND (lls.report_date - INTERVAL '1 day')
          BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY 
          lls.report_date,
        lls.system_date,
        lls.company_id,
    	lls.company_name,
		lls.room_type_name,    
		lls.room_type_id,
	 	lls.nationality_id,
		lls.nationality_name,
		lls.meal_pattern_id,
		lls.meal_pattern_name
),   
  
expected_arrivals AS (
    SELECT 
           lls.report_date,
        lls.system_date,
        lls.company_id,
    	lls.company_name,
		lls.room_type_name,    
		lls.room_type_id,
	 	lls.nationality_id,
		lls.nationality_name,
		lls.meal_pattern_id,
		lls.meal_pattern_name,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count,
	    SUM(lls.adult_count)/2 AS ea_adults_count,
        SUM(lls.child_count)/2 AS ea_children_count,
        SUM(lls.infant_count)/2 AS ea_infants_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY 
         lls.report_date,
        lls.system_date,
        lls.company_id,
        lls.company_name,
		lls.room_type_name,
		lls.room_type_id,
	 	lls.nationality_id,
		lls.nationality_name,
		lls.meal_pattern_id,
		lls.meal_pattern_name
	),
expected_departures AS (
    SELECT
        lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_name,
        lls.room_type_id,
		 	lls.nationality_id,
		lls.nationality_name,
		lls.meal_pattern_id,
		lls.meal_pattern_name,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count,
	 SUM(lls.adult_count) AS ed_adults_count,
        SUM(lls.child_count) AS ed_children_count,
        SUM(lls.infant_count) AS ed_infants_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY 
        lls.report_date,
        lls.system_date,
        lls.company_id,
    	lls.company_name,
		lls.room_type_name,    
		lls.room_type_id,
		lls.nationality_id,
		lls.nationality_name,
		lls.meal_pattern_id,
		lls.meal_pattern_name
),
master_keys AS (
    SELECT report_date, company_id, system_date, company_name,
		room_type_name, room_type_id, nationality_id,
		nationality_name, meal_pattern_id, meal_pattern_name
    FROM in_house
    UNION
 	SELECT report_date, company_id, system_date, company_name,
		room_type_name, room_type_id, nationality_id,
		nationality_name, meal_pattern_id, meal_pattern_name
	FROM expected_arrivals
    UNION
 	SELECT report_date, company_id, system_date, company_name,
		room_type_name, room_type_id, nationality_id,
		nationality_name, meal_pattern_id, meal_pattern_name
	FROM expected_departures
    UNION
 	SELECT report_date, company_id, system_date, company_name,
		room_type_name, room_type_id, nationality_id,
		nationality_name, meal_pattern_id, meal_pattern_name
	FROM yesterday_in_house
),
final_report AS (
    SELECT
        mk.report_date,
        mk.company_id,
        mk.company_name,
        mk.room_type_id,
        mk.room_type_name,
        mk.meal_pattern_id,
        mk.meal_pattern_name,
--         bd.nationality_id,
		mk.nationality_name,
        COALESCE(inv.total_room_count, 0) AS total_rooms,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals,
        COALESCE(ea.ea_adults_count, 0) AS expected_arrivals_adults,
        COALESCE(ea.ea_children_count, 0) AS expected_arrivals_children,
        COALESCE(ea.ea_infants_count, 0) AS expected_arrivals_infants,
        (COALESCE(ea.ea_adults_count, 0) + COALESCE(ea.ea_children_count, 0) + COALESCE(ea.ea_infants_count, 0)) AS expected_arrivals_total,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures,
        COALESCE(ed.ed_adults_count, 0) AS expected_departures_adults,
        COALESCE(ed.ed_children_count, 0) AS expected_departures_children,
        COALESCE(ed.ed_infants_count, 0) AS expected_departures_infants,
        (COALESCE(ed.ed_adults_count, 0) + COALESCE(ed.ed_children_count, 0) + COALESCE(ed.ed_infants_count, 0)) AS expected_departures_total,
	
		 CASE WHEN mk.report_date <= mk.system_date THEN
            ih.in_house_count
        ELSE
            GREATEST(
                COALESCE(yh.yin_house_count, 0)
                + COALESCE(ea.expected_arrivals_count, 0)
                - COALESCE(ed.expected_departures_count, 0),
                0
            )
        END AS in_house_count,
        --COALESCE(ih.in_house_count, 0) AS in_house,
		CASE WHEN mk.report_date <= mk.system_date THEN
            ih.in_house_adults
        ELSE
            GREATEST(
                COALESCE(yh.yin_house_adults, 0)
                + COALESCE(ea.ea_adults_count, 0)
                - COALESCE(ed.ed_adults_count, 0),
                0
            )
        END AS in_house_adults,
        --COALESCE(ih.in_house_adults, 0) AS in_house_adults,
		CASE WHEN mk.report_date <= mk.system_date THEN
            ih.in_house_children
        ELSE
            GREATEST(
                COALESCE(yh.yin_house_children, 0)
                + COALESCE(ea.ea_children_count, 0)
                - COALESCE(ed.ed_children_count, 0),
                0
            )
        END AS in_house_children,
		CASE WHEN mk.report_date <= mk.system_date THEN
            ih.in_house_infants
        ELSE
            GREATEST(
                COALESCE(yh.yin_house_infants, 0)
                + COALESCE(ea.ea_infants_count, 0)
                - COALESCE(ed.ed_infants_count, 0),
                0
            )
        END AS in_house_infants,
       CASE WHEN mk.report_date <= mk.system_date THEN
            (COALESCE(ih.in_house_adults, 0) + COALESCE(ih.in_house_children, 0) + COALESCE(ih.in_house_infants, 0)) 
        ELSE
            GREATEST(
                COALESCE(yh.yin_house_adults, 0) + COALESCE(yh.yin_house_children, 0) + COALESCE(yh.yin_house_infants, 0)
                + COALESCE(ea.ea_adults_count, 0) + COALESCE(ea.ea_children_count, 0) + COALESCE(ea.ea_infants_count, 0)
                - COALESCE(ed.ed_adults_count, 0) - COALESCE(ed.ed_children_count, 0) - COALESCE(ed.ed_infants_count, 0),
                0
            )
        END AS in_house_total,
        
        
        
	

        
        /* 
           We still keep the pieces for reference:
        */
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures_count,
        GREATEST(
            COALESCE(yh.yin_house_count, 0)
            + COALESCE(ea.expected_arrivals_count, 0)
            - COALESCE(ed.expected_departures_count, 0),
            0
        ) AS expected_in_house
	
	FROM master_keys mk
    LEFT JOIN in_house ih
        ON  mk.report_date   = ih.report_date
        AND mk.company_id    = ih.company_id
		AND mk.nationality_id = ih.nationality_id	
        AND mk.room_type_id  = ih.room_type_id
	    AND mk.meal_pattern_id   = ih.meal_pattern_id
        AND mk.meal_pattern_name = ih.meal_pattern_name

        
    LEFT JOIN yesterday_in_house yh
        ON  mk.report_date   = yh.report_date
        AND mk.company_id    = yh.company_id
		AND mk.nationality_id = yh.nationality_id
        AND mk.room_type_id  = yh.room_type_id
	    AND mk.meal_pattern_id   = yh.meal_pattern_id
        AND mk.meal_pattern_name = yh.meal_pattern_name

        
    LEFT JOIN expected_arrivals ea
        ON  mk.report_date   = ea.report_date
        AND mk.company_id    = ea.company_id
        AND mk.room_type_id  = ea.room_type_id
 		AND mk.nationality_id = ea.nationality_id    
		AND mk.meal_pattern_id   = ea.meal_pattern_id
        AND mk.meal_pattern_name = ea.meal_pattern_name

    LEFT JOIN expected_departures ed
        ON  mk.report_date   = ed.report_date
        AND mk.company_id    = ed.company_id
        AND mk.room_type_id  = ed.room_type_id
		AND mk.nationality_id = ed.nationality_id	
		AND mk.meal_pattern_id   = ed.meal_pattern_id
        AND mk.meal_pattern_name = ed.meal_pattern_name
	LEFT JOIN inventory inv ON inv.company_id = mk.company_id AND inv.room_type_id = mk.room_type_id
--     FROM date_series ds
--     CROSS JOIN res_company rc
--     CROSS JOIN room_type rt
--     CROSS JOIN public.meal_pattern mp
--     LEFT JOIN inventory inv ON inv.company_id = rc.id AND inv.room_type_id = rt.id
--     LEFT JOIN expected_arrivals ea ON ea.company_id = rc.id AND ea.room_type_id = rt.id AND ea.meal_pattern = mp.meal_pattern AND ea.report_date = ds.report_date
--     LEFT JOIN expected_departures ed ON ed.company_id = rc.id AND ed.room_type_id = rt.id AND ed.meal_pattern = mp.meal_pattern AND ed.report_date = ds.report_date
--     LEFT JOIN in_house ih ON ih.company_id = rc.id AND ih.room_type_id = rt.id AND ih.meal_pattern = mp.meal_pattern AND ih.report_date = ds.report_date
--     LEFT JOIN latest_line_status as lls ON bd.company_id = rc.id AND bd.room_type_id = rt.id AND bd.meal_pattern = mp.meal_pattern AND bd.checkin_date <= ds.report_date AND bd.checkout_date >= ds.report_date
--     WHERE fr.company_id IN (SELECT company_id FROM company_ids)
    
)

SELECT
    fr.report_date,
    fr.company_id,
	fr.company_name,
    fr.room_type_name,
    fr.meal_pattern_name,
    fr.nationality_name,
    SUM(fr.expected_arrivals) AS expected_arrivals,
    SUM(fr.expected_arrivals_adults) AS expected_arrivals_adults,
    SUM(fr.expected_arrivals_children) AS expected_arrivals_children,
    SUM(fr.expected_arrivals_infants) AS expected_arrivals_infants,
    SUM(fr.expected_arrivals_total) AS expected_arrivals_total,
	
    SUM(fr.expected_departures) AS expected_departures,
    SUM(fr.expected_departures_adults) AS expected_departures_adults,
    SUM(fr.expected_departures_children) AS expected_departures_children,
    SUM(fr.expected_departures_infants) AS expected_departures_infants,
    SUM(fr.expected_departures_total) AS expected_departures_total,
	
    SUM(fr.in_house_count) AS in_house,
    SUM(fr.in_house_adults) AS in_house_adults,
    SUM(fr.in_house_children) AS in_house_children,
    SUM(fr.in_house_infants) AS in_house_infants,
    SUM(fr.in_house_total) AS in_house_total,
	
    (SUM(fr.expected_arrivals_adults) + SUM(fr.expected_departures_adults) + SUM(fr.in_house_adults)) AS total_adults,
    (SUM(fr.expected_arrivals_children) + SUM(fr.expected_departures_children) + SUM(fr.in_house_children)) AS total_children,
    (SUM(fr.expected_arrivals_infants) + SUM(fr.expected_departures_infants) + SUM(fr.in_house_infants)) AS total_infants,
	
	(
    (SUM(fr.expected_arrivals_adults) + SUM(fr.expected_departures_adults) + SUM(fr.in_house_adults)) +
    (SUM(fr.expected_arrivals_children) + SUM(fr.expected_departures_children) + SUM(fr.in_house_children)) +
    (SUM(fr.expected_arrivals_infants) + SUM(fr.expected_departures_infants) + SUM(fr.in_house_infants))
) AS total_of_all
	
--     (SUM(fr.expected_arrivals) + SUM(fr.expected_departures) + SUM(fr.in_house)) AS total_overall_arrivals_departures_inhouse,
--     (SUM(fr.expected_arrivals_adults) + SUM(fr.expected_departures_adults) + SUM(fr.in_house_adults)) AS total_overall_adults,
--     (SUM(fr.expected_arrivals_children) + SUM(fr.expected_departures_children) + SUM(fr.in_house_children)) AS total_overall_children,
--     (SUM(fr.expected_arrivals_infants) + SUM(fr.expected_departures_infants) + SUM(fr.in_house_infants)) AS total_overall_infants
FROM final_report fr

WHERE fr.company_id IN (SELECT company_id FROM company_ids)  -- ✅ Fix: Apply WHERE condition here
  AND (COALESCE(fr.expected_arrivals, 0) + COALESCE(fr.expected_departures, 0) + COALESCE(fr.in_house_count, 0)) > 0
  AND (fr.meal_pattern_id IS NOT NULL AND fr.meal_pattern_name IS NOT NULL)
  AND (fr.nationality_name IS NOT NULL)
GROUP BY fr.report_date, fr.company_name, fr.company_id, fr.room_type_name, fr.meal_pattern_name, fr.nationality_name
ORDER BY fr.report_date, fr.company_id, fr.room_type_name, fr.meal_pattern_name, fr.nationality_name;
        """

        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        # params = (from_date, to_date, get_company)
        self.env.cr.execute(query)
        # self.env.cr.execute(query, (get_company, get_company, get_company))
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        records_to_create = []

        for result in results:
            try:
                # Adjust indices based on the updated SELECT statement
                (
                    report_date,
                    company_id,      # result[1]
                    company_name,
                    room_type_name,
                    meal_pattern_name,
                    country_name,
                    expected_arrivals,
                    expected_arrivals_adults,
                    expected_arrivals_children,
                    expected_arrivals_infants,
                    expected_arrivals_total,
                    expected_departures,
                    expected_departures_adults,
                    expected_departures_children,
                    expected_departures_infants,
                    expected_departures_total,
                    in_house,
                    in_house_adults,
                    in_house_children,
                    in_house_infants,
                    in_house_total,
                    total_adults,
                    total_children,
                    total_infants,
                    total_of_all
                ) = result

                # if company_id:
                #     if company_id != self.env.company.id:  # Ensure the record belongs to the current company
                #         continue
                # else:
                #     continue

                total_adults = expected_arrivals_adults + expected_departures_adults + in_house_adults

                records_to_create.append({
                    'report_date': report_date,
                    'company_id': company_id,  # Assign the company_id correctly
                    'company_name': company_name,
                    'room_type_name': room_type_name,
                    'meal_pattern': meal_pattern_name,
                    'country_name': country_name,
                    'expected_arrivals': expected_arrivals,
                    'expected_arrivals_adults': expected_arrivals_adults,
                    'expected_arrivals_children': expected_arrivals_children,
                    'expected_arrivals_infants': expected_arrivals_infants,
                    'expected_arrivals_total': expected_arrivals_total,
                    'expected_departures': expected_departures,
                    'expected_departures_adults': expected_departures_adults,
                    'expected_departures_children': expected_departures_children,
                    'expected_departures_infants': expected_departures_infants,
                    'expected_departures_total': expected_departures_total,
                    'in_house': in_house,
                    'in_house_adults': in_house_adults,
                    'in_house_children': in_house_children,
                    'in_house_infants': in_house_infants,
                    'in_house_total': in_house_total,
                    'total_adults': total_adults,
                    'total_children': total_children,
                    'total_infants': total_infants,
                    'total_of_all': total_of_all,
                })

            except Exception as e:
                _logger.error(f"Error processing record {result}: {e}", exc_info=True)
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
