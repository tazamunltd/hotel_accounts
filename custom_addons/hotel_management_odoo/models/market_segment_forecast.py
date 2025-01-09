from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class MarketSegmentForecastReport(models.Model):
    _name = 'market.segment.forecast.report'
    _description = 'Market Segment Forecast Report'

    
    company_id = fields.Many2one('res.company', string='Company', required=True)
    report_date = fields.Date(string='Report Date', required=True)
    room_type_name = fields.Char(string='Room Type')
    market_segment_name = fields.Char(string='Market segment')
    expected_arrivals = fields.Integer(string='Exp.Arrivals')
    expected_departures = fields.Integer(string='Exp.Departures')
    in_house = fields.Integer(string='In House')
    expected_arrivals_adults = fields.Integer(string='Exp.Arrivals Adults')
    expected_arrivals_children = fields.Integer(string='Exp.Arrivals Children')
    expected_arrivals_infants = fields.Integer(string='Exp.Arrivals Infants')
    expected_departures_adults = fields.Integer(string='Exp.Departures Adults')
    expected_departures_children = fields.Integer(string='Exp.Departures Children')
    expected_departures_infants = fields.Integer(string='Exp.Departures Infants')
    in_house_adults = fields.Integer(string='In House Adults')
    in_house_children = fields.Integer(string='In House Children')
    in_house_infants = fields.Integer(string='In House Infants')
    expected_in_house = fields.Integer(string='Exp.Inhouse')
    expected_in_house_adults = fields.Integer(string='Exp.Inhouse Adults')
    expected_in_house_children = fields.Integer(string='Exp.Inhouse Children')
    expected_in_house_infants = fields.Integer(string='Exp.Inhouse Infants')

    


    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_market_segment_forecast()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_market_segment_forecast(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_market_segment_forecast")

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

latest_line_status AS (
    SELECT DISTINCT ON (rbl.id, ds.report_date)
           rbl.id AS booking_line_id,
           ds.report_date,
           rb.checkin_date::date AS checkin_date,
           rb.checkout_date::date AS checkout_date,
           hr.company_id,
           rt.id AS room_type_id,
           rb.market_segment, -- Include market_segment ID here
           rbls.status AS final_status,
           rbls.change_time,
           rb.house_use,
           rb.complementary,
           rbl.adult_count,
           rb.child_count,
           rb.infant_count,
           rb.nationality,
           rb.meal_pattern,
           mp.meal_pattern AS meal_pattern_name
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
        lls.market_segment, -- Keep market_segment ID here
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count,
        SUM(lls.adult_count) AS expected_arrivals_adults,
        SUM(lls.child_count) AS expected_arrivals_children,
        SUM(lls.infant_count) AS expected_arrivals_infants,
        SUM(lls.adult_count + lls.child_count + lls.infant_count) AS expected_arrivals_total
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.market_segment
),

expected_departures AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.market_segment, -- Keep market_segment ID here
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count,
        SUM(lls.adult_count) AS expected_departures_adults,
        SUM(lls.child_count) AS expected_departures_children,
        SUM(lls.infant_count) AS expected_departures_infants,
        SUM(lls.adult_count + lls.child_count + lls.infant_count) AS expected_departures_total
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.market_segment
),

in_house AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        lls.market_segment, -- Keep market_segment ID here
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count,
        SUM(lls.adult_count) AS in_house_adults,
        SUM(lls.child_count) AS in_house_children,
        SUM(lls.infant_count) AS in_house_infants,
        SUM(lls.adult_count + lls.child_count + lls.infant_count) AS in_house_total
    FROM latest_line_status lls
    WHERE lls.checkin_date <= lls.report_date
      AND lls.checkout_date >= lls.report_date
      AND lls.final_status = 'check_in'
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id, lls.market_segment
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
        ms.market_segment AS market_segment_name, -- Fetch market_segment name
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
        COALESCE(ih.in_house_total, 0) AS in_house_total,
        /* Calculating expected_in_house and its counts */
        (COALESCE(ih.in_house_count, 0) 
         + COALESCE(ea.expected_arrivals_count, 0) 
         - COALESCE(ed.expected_departures_count, 0)) AS expected_in_house,
        (COALESCE(ih.in_house_adults, 0) 
         + COALESCE(ea.expected_arrivals_adults, 0) 
         - COALESCE(ed.expected_departures_adults, 0)) AS expected_in_house_adults,
        (COALESCE(ih.in_house_children, 0) 
         + COALESCE(ea.expected_arrivals_children, 0) 
         - COALESCE(ed.expected_departures_children, 0)) AS expected_in_house_children,
        (COALESCE(ih.in_house_infants, 0) 
         + COALESCE(ea.expected_arrivals_infants, 0) 
         - COALESCE(ed.expected_departures_infants, 0)) AS expected_in_house_infants
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type rt
    LEFT JOIN inventory inv 
        ON inv.company_id = rc.id 
        AND inv.room_type_id = rt.id
    LEFT JOIN expected_arrivals ea 
        ON ea.company_id = rc.id 
        AND ea.room_type_id = rt.id 
        AND ea.report_date = ds.report_date
    LEFT JOIN expected_departures ed 
        ON ed.company_id = rc.id 
        AND ed.room_type_id = rt.id 
        AND ed.report_date = ds.report_date
    LEFT JOIN in_house ih 
        ON ih.company_id = rc.id 
        AND ih.room_type_id = rt.id 
        AND ih.report_date = ds.report_date
    LEFT JOIN public.market_segment ms 
        ON ms.id = ea.market_segment -- Join market_segment table
)

SELECT
    fr.report_date,
    fr.company_id,
    fr.room_type_name,
    fr.market_segment_name, -- Display market_segment name
    --SUM(fr.total_rooms) AS total_rooms, -- Uncomment if needed
    SUM(fr.expected_arrivals) AS expected_arrivals,
    SUM(fr.expected_arrivals_adults) AS expected_arrivals_adults,
    SUM(fr.expected_arrivals_children) AS expected_arrivals_children,
    SUM(fr.expected_arrivals_infants) AS expected_arrivals_infants,
    --SUM(fr.expected_arrivals_total) AS expected_arrivals_total, -- Uncomment if needed
    SUM(fr.expected_departures) AS expected_departures,
    SUM(fr.expected_departures_adults) AS expected_departures_adults,
    SUM(fr.expected_departures_children) AS expected_departures_children,
    SUM(fr.expected_departures_infants) AS expected_departures_infants,
    --SUM(fr.expected_departures_total) AS expected_departures_total, -- Uncomment if needed
    SUM(fr.in_house) AS in_house,
    SUM(fr.in_house_adults) AS in_house_adults,
    SUM(fr.in_house_children) AS in_house_children,
    SUM(fr.in_house_infants) AS in_house_infants,
    /* Summing up expected_in_house and its counts */
    SUM(fr.expected_in_house) AS expected_in_house,
    SUM(fr.expected_in_house_adults) AS expected_in_house_adults,
    SUM(fr.expected_in_house_children) AS expected_in_house_children,
    SUM(fr.expected_in_house_infants) AS expected_in_house_infants
FROM final_report fr
GROUP BY 
    fr.report_date, 
    fr.company_id, 
    fr.room_type_name, 
    fr.market_segment_name
ORDER BY 
    fr.report_date, 
    fr.company_id, 
    fr.room_type_name, 
    fr.market_segment_name;
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
                    market_segment_name,  # Include market_segment in the output_pattern,
                    expected_arrivals,
                    expected_arrivals_adults,
                    expected_arrivals_children,
                    expected_arrivals_infants,
                    expected_departures,
                    expected_departures_adults,
                    expected_departures_children,
                    expected_departures_infants,
                    in_house,
                    in_house_adults,
                    in_house_children,
                    in_house_infants,
                    expected_in_house,
                    expected_in_house_adults,
                    expected_in_house_children,
                    expected_in_house_infants
                ) = result

                records_to_create.append({
                    'report_date': report_date,
                    'company_id': company_id,
                    'room_type_name': room_type_name,
                    'market_segment_name': market_segment_name,
                    'expected_arrivals': expected_arrivals,
                    'expected_arrivals_adults': expected_arrivals_adults,
                    'expected_arrivals_children': expected_arrivals_children,
                    'expected_arrivals_infants': expected_arrivals_infants,
                    'expected_departures': expected_departures,
                    'expected_departures_adults': expected_departures_adults,
                    'expected_departures_children': expected_departures_children,
                    'expected_departures_infants': expected_departures_infants,
                    'in_house': in_house,
                    'in_house_adults': in_house_adults,
                    'in_house_children': in_house_children,
                    'in_house_infants': in_house_infants,
                    'expected_in_house': expected_in_house,
                    'expected_in_house_adults': expected_in_house_adults,
                    'expected_in_house_children': expected_in_house_children,
                    'expected_in_house_infants': expected_in_house_infants
                    })

            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
 