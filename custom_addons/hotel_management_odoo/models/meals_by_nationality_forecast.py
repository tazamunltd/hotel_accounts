from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class MealsByNationalityForecast(models.Model):
    _name = 'meals.by.nationality.forecast'
    _description = 'Meals By Nationality Forecast'

    company_id = fields.Many2one('res.company', string='Company', required=True)
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
    def search_available_rooms(self, from_date, to_date):
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

    def run_process_by_meals_by_nationality_forecast(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_meals_by_nationality_forecast")

        # Scoped deletion to current company
        self.search([]).unlink()
        _logger.info("Existing records for the current company deleted")
        
        system_date = self.env.company.system_date.date()
        from_date = system_date - datetime.timedelta(days=7)
        to_date = system_date + datetime.timedelta(days=7)
        get_company = self.env.company.id


        query = """
WITH parameters AS (
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
    SELECT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
    FROM parameters p
),

base_data AS (
    SELECT
        rb.id AS booking_id,
        rb.company_id,
        rb.partner_id AS customer_id,
        rp.name AS customer_name,
--         rb.nationality AS nationality_id,
		rcountry.name AS nationality_name,
        mp.meal_pattern AS meal_pattern,  
        rb.checkin_date::date AS checkin_date,
        rb.checkout_date::date AS checkout_date,
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
	LEFT JOIN res_country rcountry ON rb.nationality = rcountry.id
),

in_house AS (
    SELECT
        bd.checkin_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.meal_pattern,
        bd.nationality_name,
        COUNT(DISTINCT bd.booking_line_id) AS in_house_count,
        SUM(bd.adult_count) AS in_house_adults,
        SUM(bd.child_count) AS in_house_children,
        SUM(bd.infant_count) AS in_house_infants
    FROM base_data bd
    WHERE bd.status = 'check_in'
    GROUP BY bd.checkin_date, bd.company_id, bd.room_type_id, bd.meal_pattern, bd.nationality_name
),

expected_arrivals AS (
    SELECT
        bd.checkin_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.meal_pattern,
        bd.nationality_name,
        COUNT(DISTINCT bd.booking_line_id) AS expected_arrivals_count,
        SUM(bd.adult_count) AS expected_arrivals_adults,
        SUM(bd.child_count) AS expected_arrivals_children,
        SUM(bd.infant_count) AS expected_arrivals_infants
    FROM base_data bd
    WHERE bd.status IN ('confirmed', 'block')
    GROUP BY bd.checkin_date, bd.company_id, bd.room_type_id, bd.meal_pattern, bd.nationality_name
),

expected_departures AS (
    SELECT
        bd.checkout_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.meal_pattern,
        bd.nationality_name,
        COUNT(DISTINCT bd.booking_line_id) AS expected_departures_count,
        SUM(bd.adult_count) AS expected_departures_adults,
        SUM(bd.child_count) AS expected_departures_children,
        SUM(bd.infant_count) AS expected_departures_infants
    FROM base_data bd
    WHERE bd.status = 'check_in'
    GROUP BY bd.checkout_date, bd.company_id, bd.room_type_id, bd.meal_pattern, bd.nationality_name
),

inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count
    FROM hotel_inventory hi
    GROUP BY hi.company_id, hi.room_type
),

final_report AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rc.name AS company_name,
        rt.id AS room_type_id,
        COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
        mp.id AS meal_pattern_id,
        COALESCE(jsonb_extract_path_text(mp.meal_pattern::jsonb, 'en_US'),'N/A') AS meal_pattern,
--         bd.nationality_id,
		bd.nationality_name,
        COALESCE(inv.total_room_count, 0) AS total_rooms,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals,
        COALESCE(ea.expected_arrivals_adults, 0) AS expected_arrivals_adults,
        COALESCE(ea.expected_arrivals_children, 0) AS expected_arrivals_children,
        COALESCE(ea.expected_arrivals_infants, 0) AS expected_arrivals_infants,
        (COALESCE(ea.expected_arrivals_adults, 0) + COALESCE(ea.expected_arrivals_children, 0) + COALESCE(ea.expected_arrivals_infants, 0)) AS expected_arrivals_total,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures,
        COALESCE(ed.expected_departures_adults, 0) AS expected_departures_adults,
        COALESCE(ed.expected_departures_children, 0) AS expected_departures_children,
        COALESCE(ed.expected_departures_infants, 0) AS expected_departures_infants,
        (COALESCE(ed.expected_departures_adults, 0) + COALESCE(ed.expected_departures_children, 0) + COALESCE(ed.expected_departures_infants, 0)) AS expected_departures_total,
        COALESCE(ih.in_house_count, 0) AS in_house,
        COALESCE(ih.in_house_adults, 0) AS in_house_adults,
        COALESCE(ih.in_house_children, 0) AS in_house_children,
        COALESCE(ih.in_house_infants, 0) AS in_house_infants,
        (COALESCE(ih.in_house_adults, 0) + COALESCE(ih.in_house_children, 0) + COALESCE(ih.in_house_infants, 0)) AS in_house_total
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type rt
    CROSS JOIN public.meal_pattern mp
    LEFT JOIN inventory inv ON inv.company_id = rc.id AND inv.room_type_id = rt.id
    LEFT JOIN expected_arrivals ea ON ea.company_id = rc.id AND ea.room_type_id = rt.id AND ea.meal_pattern = mp.meal_pattern AND ea.report_date = ds.report_date
    LEFT JOIN expected_departures ed ON ed.company_id = rc.id AND ed.room_type_id = rt.id AND ed.meal_pattern = mp.meal_pattern AND ed.report_date = ds.report_date
    LEFT JOIN in_house ih ON ih.company_id = rc.id AND ih.room_type_id = rt.id AND ih.meal_pattern = mp.meal_pattern AND ih.report_date = ds.report_date
    LEFT JOIN base_data bd ON bd.company_id = rc.id AND bd.room_type_id = rt.id AND bd.meal_pattern = mp.meal_pattern AND bd.checkin_date <= ds.report_date AND bd.checkout_date >= ds.report_date
)

SELECT
    fr.report_date,
    fr.company_id,
	fr.company_name,
    fr.room_type_name,
    fr.meal_pattern,
    COALESCE(jsonb_extract_path_text(fr.nationality_name::jsonb, 'en_US'), 'N/A') AS nationality_name,
    
    
	
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
	
    SUM(fr.in_house) AS in_house,
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
WHERE (COALESCE(fr.expected_arrivals, 0) + COALESCE(fr.expected_departures, 0) + COALESCE(fr.in_house, 0)) > 0
GROUP BY fr.report_date, fr.company_name, fr.company_id, fr.room_type_name, fr.meal_pattern, fr.nationality_name
ORDER BY fr.report_date, fr.company_id, fr.room_type_name, fr.meal_pattern, fr.nationality_name;
        """

        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        self.env.cr.execute(query, (get_company, get_company, get_company))
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
                    meal_pattern,
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

                if company_id:
                    if company_id != self.env.company.id:  # Ensure the record belongs to the current company
                        continue
                else:
                    continue

                total_adults = expected_arrivals_adults + expected_departures_adults + in_house_adults

                records_to_create.append({
                    'report_date': report_date,
                    'company_id': company_id,  # Assign the company_id correctly
                    'company_name': company_name,
                    'room_type_name': room_type_name,
                    'meal_pattern': meal_pattern,
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
