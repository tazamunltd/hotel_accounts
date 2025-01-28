from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class MealsForecastReport(models.Model):
    _name = 'meals.forecast.report'
    _description = 'Meals Forecast Report'

    
    company_id = fields.Many2one('res.company', string='Company', required=True)
    report_date = fields.Date(string='Report Date', required=True)
    room_type_name = fields.Char(string='Room Type')
    meal_pattern = fields.Char(string='Meal Pattern')
    expected_arrivals = fields.Integer(string='Exp.Arrivals')
    expected_departures = fields.Integer(string='Exp.Departures')
    in_house = fields.Integer(string='In House')
    expected_arrivals_adults = fields.Integer(string='Exp.Arrivals Adults')
    expected_arrivals_children = fields.Integer(string='Exp.Arrivals Children')
    expected_arrivals_infants = fields.Integer(string='Exp.Arrivals Infants')
    expected_arrivals_total = fields.Integer(string='Exp.Arrivals Total')
    expected_departures_adults = fields.Integer(string='Exp.Departures Adults')
    expected_departures_children = fields.Integer(string='Exp.Departures Children')
    expected_departures_infants = fields.Integer(string='Exp.Departures Infants')
    expected_departures_total = fields.Integer(string='Exp.Departures Total')
    in_house_adults = fields.Integer(string='In House Adults')
    in_house_children = fields.Integer(string='In House Children')
    in_house_infants = fields.Integer(string='In House Infants')
    in_house_total = fields.Integer(string='In House Total')
    total_adults = fields.Integer(string='Total Adults')
    total_children = fields.Integer(string='Total Children')
    total_infants = fields.Integer(string='Total Infants')
    total_of_all = fields.Integer(string='Total of All')


    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_meals_forecast()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_meals_forecast(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_meals_forecast")

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
   1) LATEST LINE STATUS:
   For each booking line and report date, determine the latest status as of that date.
   ---------------------------------------------------------------------------- */
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
           rb.house_use AS house_use,
           rb.complementary AS complementary,
           rbl.adult_count,
           rb.child_count,
           rb.infant_count,
           rb.nationality,
           rb.meal_pattern,
           mp.meal_pattern AS meal_pattern_name
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb    ON rb.id = rbl.booking_id
    JOIN hotel_room hr      ON hr.id = rbl.room_id
    JOIN room_type rt       ON rt.id = hr.room_type_name
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
           AND rbls.change_time::date <= ds.report_date
    LEFT JOIN public.meal_pattern mp 
           ON mp.id = rb.meal_pattern
    ORDER BY rbl.id, ds.report_date, rbls.change_time DESC NULLS LAST
),

/* ----------------------------------------------------------------------------
   2) IN-HOUSE:
   Lines with status 'check_in' covering the report date.
   ---------------------------------------------------------------------------- */
in_house AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        mp.meal_pattern AS meal_pattern_name,
        COUNT(DISTINCT sub.booking_line_number) AS in_house_count,
        SUM(sub.adult_count) AS in_house_adults,
        SUM(sub.child_count) AS in_house_children,
        SUM(sub.infant_count) AS in_house_infants,
        SUM(sub.adult_count + sub.child_count + sub.infant_count) AS in_house_total
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type rt
    CROSS JOIN public.meal_pattern mp
    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number,
               qry.adult_count,
               qry.child_count,
               qry.infant_count
        FROM (
            SELECT 
                rbl.id AS booking_line_number,
                rbl.adult_count,
                rb.child_count,
                rb.infant_count,
                rbls.status,
                rbls.change_time,
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rb.meal_pattern,
                rbl.checkin_date::date,
                rbl.checkout_date::date
            FROM room_booking_line rbl
            JOIN room_booking rb    ON rb.id = rbl.booking_id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
        ) AS qry
        WHERE qry.company_id     = rc.id
          AND qry.room_type_id   = rt.id
          AND qry.meal_pattern   = mp.id
          /* Lines that physically cover ds.report_date: [checkin_date, checkout_date) */
          AND qry.checkin_date <= ds.report_date
          AND qry.checkout_date > ds.report_date
          /* Must have had status='check_in' as of or before ds.report_date */
          AND qry.status = 'check_in'
          AND qry.change_time::date <= ds.report_date
        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE
    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id,
        mp.meal_pattern
),

/* ----------------------------------------------------------------------------
   3) EXPECTED ARRIVALS:
   Lines that arrive on the report date with status 'confirmed' or 'block'.
   ---------------------------------------------------------------------------- */
expected_arrivals AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        mp.meal_pattern AS meal_pattern_name,
        COUNT(DISTINCT sub.booking_line_number) AS expected_arrivals_count,
        SUM(sub.adult_count) AS expected_arrivals_adults,
        SUM(sub.child_count) AS expected_arrivals_children,
        SUM(sub.infant_count) AS expected_arrivals_infants,
        SUM(sub.adult_count + sub.child_count + sub.infant_count) AS expected_arrivals_total
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type rt
    CROSS JOIN public.meal_pattern mp
    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number,
               qry.adult_count,
               qry.child_count,
               qry.infant_count
        FROM (
            SELECT 
                rbl.id AS booking_line_number,
                rbl.adult_count,
                rb.child_count,
                rb.infant_count,
                rbls.status,
                rbls.change_time,
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rb.meal_pattern,
                rbl.checkin_date::date
            FROM room_booking_line rbl
            JOIN room_booking rb    ON rb.id = rbl.booking_id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
        ) AS qry
        WHERE qry.company_id    = rc.id
          AND qry.room_type_id  = rt.id
          AND qry.meal_pattern  = mp.id
          /* Lines arriving on ds.report_date */
          AND qry.checkin_date = ds.report_date
          /* Must have status 'confirmed' or 'block' as of ds.report_date */
          AND qry.status IN ('confirmed', 'block')
          AND qry.change_time::date <= ds.report_date
        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE
    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id,
        mp.meal_pattern
),

/* ----------------------------------------------------------------------------
   4) EXPECTED DEPARTURES:
   Lines that depart on the report date with status 'check_in'.
   ---------------------------------------------------------------------------- */
expected_departures AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        mp.meal_pattern AS meal_pattern_name,
        COUNT(DISTINCT sub.booking_line_number) AS expected_departures_count,
        SUM(sub.adult_count) AS expected_departures_adults,
        SUM(sub.child_count) AS expected_departures_children,
        SUM(sub.infant_count) AS expected_departures_infants,
        SUM(sub.adult_count + sub.child_count + sub.infant_count) AS expected_departures_total
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type rt
    CROSS JOIN public.meal_pattern mp
    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number,
               qry.adult_count,
               qry.child_count,
               qry.infant_count
        FROM (
            SELECT 
                rbl.id AS booking_line_number,
                rbl.adult_count,
                rb.child_count,
                rb.infant_count,
                rbls.status,
                rbls.change_time,
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rb.meal_pattern,
                rbl.checkout_date::date
            FROM room_booking_line rbl
            JOIN room_booking rb    ON rb.id = rbl.booking_id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
        ) AS qry
        WHERE qry.company_id    = rc.id
          AND qry.room_type_id  = rt.id
          AND qry.meal_pattern  = mp.id
          /* Lines departing on ds.report_date */
          AND qry.checkout_date = ds.report_date
          /* Must have status 'check_in' as of ds.report_date */
          AND qry.status = 'check_in'
          AND qry.change_time::date <= ds.report_date
        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE
    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id,
        mp.meal_pattern
),

/* ----------------------------------------------------------------------------
   5) INVENTORY:
   Total room counts per company and room type.
   ---------------------------------------------------------------------------- */
inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count
    FROM hotel_inventory hi
    GROUP BY hi.company_id, hi.room_type
),

/* ----------------------------------------------------------------------------
   6) FINAL REPORT:
   Combine all metrics into a comprehensive report.
   ---------------------------------------------------------------------------- */
final_report AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rc.name AS company_name,
        rt.id AS room_type_id,
        COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,

        mp.id AS meal_pattern_id,
        COALESCE(jsonb_extract_path_text(mp.meal_pattern::jsonb, 'en_US'),'N/A') AS meal_pattern,

        COALESCE(inv.total_room_count, 0) AS total_rooms,

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
        COALESCE(ih.in_house_total, 0) AS in_house_total
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type rt
    CROSS JOIN public.meal_pattern mp  -- CROSS JOIN to include all meal patterns
    LEFT JOIN inventory inv
        ON inv.company_id = rc.id
        AND inv.room_type_id = rt.id
    LEFT JOIN expected_arrivals ea
        ON ea.company_id = rc.id
        AND ea.room_type_id = rt.id
        AND ea.meal_pattern_name = mp.meal_pattern
        AND ea.report_date = ds.report_date
    LEFT JOIN expected_departures ed
        ON ed.company_id = rc.id
        AND ed.room_type_id = rt.id
        AND ed.meal_pattern_name = mp.meal_pattern
        AND ed.report_date = ds.report_date
    LEFT JOIN in_house ih
        ON ih.company_id = rc.id
        AND ih.room_type_id = rt.id
        AND ih.meal_pattern_name = mp.meal_pattern
        AND ih.report_date = ds.report_date
)
SELECT
    fr.report_date,
    fr.company_id,
    fr.room_type_name,
    fr.meal_pattern,

    -- Summations
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

    (SUM(fr.expected_arrivals_adults)
      + SUM(fr.expected_departures_adults)
      + SUM(fr.in_house_adults)) AS total_adults,

    (SUM(fr.expected_arrivals_children)
      + SUM(fr.expected_departures_children)
      + SUM(fr.in_house_children)) AS total_children,

    (SUM(fr.expected_arrivals_infants)
      + SUM(fr.expected_departures_infants)
      + SUM(fr.in_house_infants)) AS total_infants,

    (
      (SUM(fr.expected_arrivals) + SUM(fr.expected_departures) + SUM(fr.in_house))
      + (SUM(fr.expected_arrivals_adults) + SUM(fr.expected_departures_adults) + SUM(fr.in_house_adults))
      + (SUM(fr.expected_arrivals_children) + SUM(fr.expected_departures_children) + SUM(fr.in_house_children))
      + (SUM(fr.expected_arrivals_infants) + SUM(fr.expected_departures_infants) + SUM(fr.in_house_infants))
    ) AS total_of_all

FROM final_report fr
WHERE (
    -- Only keep meal patterns actually in use
    COALESCE(fr.expected_arrivals, 0)
    + COALESCE(fr.expected_departures, 0)
    + COALESCE(fr.in_house, 0)
) > 0
GROUP BY
    fr.report_date,
    fr.company_id,
    fr.room_type_name,
    fr.meal_pattern
ORDER BY
    fr.report_date,
    fr.company_id,
    fr.room_type_name,
    fr.meal_pattern;


        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        records_to_create = []

        for result in results:
            try:
                if result[1]:  # Ensure company_id is present
                    company_id = result[1]
                    if company_id != self.env.company.id:  # Skip if company_id doesn't match
                        continue
                else:
                    continue
                (
                    report_date,
                    company_id,
                    room_type_name,
                    meal_pattern,
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

                records_to_create.append({
                    'report_date': report_date,
                    'company_id': company_id,
                    'room_type_name': room_type_name,
                    'meal_pattern': meal_pattern,
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
                    'total_of_all': total_of_all
                })

            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
 