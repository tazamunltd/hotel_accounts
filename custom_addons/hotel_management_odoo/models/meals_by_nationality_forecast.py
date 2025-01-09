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
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_meals_by_nationality_forecast()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_meals_by_nationality_forecast(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_meals_by_nationality_forecast")

        # Scoped deletion to current company
        self.search([('company_id', '=', self.env.company.id)]).unlink()
        _logger.info("Existing records for the current company deleted")

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

latest_line_status AS (
    SELECT DISTINCT ON (rbl.id, ds.report_date)
           rbl.id AS booking_line_id,
           ds.report_date,
           rb.checkin_date::date AS checkin_date,
           rb.checkout_date::date AS checkout_date,
           hr.company_id,
           rt.id AS room_type_id,
           rbls.status AS final_status,
           rbls.change_time,
           rb.house_use,
           rb.complementary,
           rbl.adult_count,
           rb.child_count,
           rb.infant_count,
           rb.nationality,
           rb.meal_pattern,
           mp.meal_pattern AS meal_pattern_name,
           rb.nationality AS nationality_id
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb ON rb.id = rbl.booking_id
    JOIN hotel_room hr ON hr.id = rbl.room_id
    JOIN room_type rt ON rt.id = hr.room_type_name
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
           AND rbls.change_time::date <= ds.report_date
    LEFT JOIN public.meal_pattern mp ON mp.id = rb.meal_pattern
    ORDER BY rbl.id, ds.report_date, rbls.change_time DESC NULLS LAST
),

expected_arrivals AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.meal_pattern_name,
        lls.nationality_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count,
        SUM(lls.adult_count) AS expected_arrivals_adults,
        SUM(lls.child_count) AS expected_arrivals_children,
        SUM(lls.infant_count) AS expected_arrivals_infants,
        SUM(lls.adult_count + lls.child_count + lls.infant_count) AS expected_arrivals_total
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.meal_pattern_name, lls.nationality_id
),

expected_departures AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.meal_pattern_name,
        lls.nationality_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count,
        SUM(lls.adult_count) AS expected_departures_adults,
        SUM(lls.child_count) AS expected_departures_children,
        SUM(lls.infant_count) AS expected_departures_infants,
        SUM(lls.adult_count + lls.child_count + lls.infant_count) AS expected_departures_total
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.meal_pattern_name, lls.nationality_id
),

in_house AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.meal_pattern_name,
        lls.nationality_id,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count,
        SUM(lls.adult_count) AS in_house_adults,
        SUM(lls.child_count) AS in_house_children,
        SUM(lls.infant_count) AS in_house_infants,
        SUM(lls.adult_count + lls.child_count + lls.infant_count) AS in_house_total
    FROM latest_line_status lls
    WHERE lls.checkin_date <= lls.report_date
      AND lls.checkout_date > lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.meal_pattern_name, lls.nationality_id
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
        rt.room_type AS room_type_name,
        ea.meal_pattern_name AS meal_pattern,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals,
        COALESCE(ea.expected_arrivals_adults, 0) AS expected_arrivals_adults,
        COALESCE(ea.expected_arrivals_children, 0) AS expected_arrivals_children,
        COALESCE(ea.expected_arrivals_infants, 0) AS expected_arrivals_infants,
        COALESCE(ea.expected_arrivals_total, 0) AS expected_arrivals_total,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures,
        COALESCE(ed.expected_departures_adults, 0) AS expected_departures_adults,
        COALESCE(ed.expected_departures_children, 0) AS expected_departures_children,
        COALESCE(ed.expected_departures_infants, 0) AS expected_departures_infants,
        COALESCE(ed.expected_departures_total, 0) AS expected_departures_total,
        COALESCE(ih.in_house_count, 0) AS in_house,
        COALESCE(ih.in_house_adults, 0) AS in_house_adults,
        COALESCE(ih.in_house_children, 0) AS in_house_children,
        COALESCE(ih.in_house_infants, 0) AS in_house_infants,
        COALESCE(ih.in_house_total, 0) AS in_house_total,
        COALESCE(ih.nationality_id, ea.nationality_id, ed.nationality_id) AS nationality_id
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type rt
    LEFT JOIN inventory inv ON inv.company_id = rc.id AND inv.room_type_id = rt.id
    LEFT JOIN expected_arrivals ea ON ea.company_id = rc.id AND ea.room_type_id = rt.id AND ea.report_date = ds.report_date
    LEFT JOIN expected_departures ed ON ed.company_id = rc.id AND ed.room_type_id = rt.id AND ed.report_date = ds.report_date
    LEFT JOIN in_house ih ON ih.company_id = rc.id AND ih.room_type_id = rt.id AND ih.report_date = ds.report_date
)

SELECT
    fr.report_date,
    fr.company_id,  -- Include company_id
    fr.company_name,
    fr.room_type_name,
    fr.meal_pattern,
    rc_country.name->>'en_US' AS nationality,  -- Extract English value from JSON
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
    
    -- **Added Columns**
    -- Total Pax: Sum of arrivals, departures, and in-house counts
   -- SUM(fr.expected_arrivals) + SUM(fr.expected_departures) + SUM(fr.in_house) AS total_pax,

    -- Total Adults: Sum of adults from arrivals, departures, and in-house
    SUM(fr.expected_arrivals_adults) + SUM(fr.in_house_adults) AS total_adults,

    -- Total Children: Sum of children from arrivals, departures, and in-house
    SUM(fr.expected_arrivals_children) + SUM(fr.expected_departures_children) + SUM(fr.in_house_children) AS total_children,

    -- Total Infants: Sum of infants from arrivals, departures, and in-house
    SUM(fr.expected_arrivals_infants) + SUM(fr.expected_departures_infants) + SUM(fr.in_house_infants) AS total_infants,

    -- Total of All: Sum of all pax categories
    (SUM(fr.expected_arrivals) + SUM(fr.expected_departures) + SUM(fr.in_house)) +
    (SUM(fr.expected_arrivals_adults) + SUM(fr.expected_departures_adults) + SUM(fr.in_house_adults)) +
    (SUM(fr.expected_arrivals_children) + SUM(fr.expected_departures_children) + SUM(fr.in_house_children)) +
    (SUM(fr.expected_arrivals_infants) + SUM(fr.expected_departures_infants) + SUM(fr.in_house_infants))
    AS total_of_all

FROM final_report fr
LEFT JOIN res_country rc_country ON fr.nationality_id = rc_country.id
GROUP BY 
    fr.report_date, 
    fr.company_id,  -- Include in GROUP BY
    fr.company_name, 
    fr.room_type_name, 
    fr.meal_pattern,
    rc_country.name->>'en_US'  -- Adjust GROUP BY to match SELECT
ORDER BY 
    fr.report_date, 
    fr.company_id,  -- Include in ORDER BY
    fr.company_name, 
    fr.room_type_name, 
    fr.meal_pattern,
    rc_country.name->>'en_US';


        """

        self.env.cr.execute(query)
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

                total_adults = expected_arrivals_adults + in_house_adults

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
