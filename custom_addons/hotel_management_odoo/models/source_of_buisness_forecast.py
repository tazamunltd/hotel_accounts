from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class SourceOfBuisnessForecast(models.Model):
    _name = 'source.of.buisness.forecast'
    _description = 'Source of Buisness Forecast'

    
    company_id = fields.Many2one('res.company', string='Company', required=True)
    report_date = fields.Date(string='Report Date', required=True)
    room_type_name = fields.Char(string='Room Type')
    source_of_business = fields.Char(string='Source of Business')
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
            'source_of_business',
            'expected_arrivals',
            'expected_arrivals_adults',
            'expected_arrivals_children',
            'expected_arrivals_infants',
            'expected_departures',
            'expected_departures_adults',
            'expected_departures_children',
            'expected_departures_infants',
            'in_house',
            'in_house_adults',
            'in_house_children',
            'in_house_infants',
            'expected_in_house',
            'expected_in_house_adults',
            'expected_in_house_children',
            'expected_in_house_infants'
        ])


    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_source_of_buisness_forecast()
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

    def run_process_by_source_of_buisness_forecast(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_source_of_buisness_forecast")

        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")

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
        rb.nationality AS nationality_id,
        sb.source ->> 'en_US' AS source_of_business,  -- Extracted source_of_business  
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
	LEFT JOIN public.source_business sb ON sb.id = rb.source_of_business  -- Joined with source_business
),
in_house AS (
    SELECT
        bd.checkin_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.nationality_id,
        bd.source_of_business,
        COUNT(DISTINCT bd.booking_line_id) AS in_house_count,
        SUM(bd.adult_count) AS in_house_adults,
        SUM(bd.child_count) AS in_house_children,
        SUM(bd.infant_count) AS in_house_infants
    FROM base_data bd
    WHERE bd.status = 'check_in'
    GROUP BY bd.checkin_date, bd.company_id, bd.room_type_id, bd.nationality_id, bd.source_of_business
),
yesterday_in_house AS (
    SELECT
        bd.checkin_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.nationality_id,
        bd.source_of_business,
        COUNT(DISTINCT bd.booking_line_id) AS yesterday_in_house_count
    FROM base_data bd
    WHERE bd.status = 'check_in' AND bd.checkin_date = CURRENT_DATE - INTERVAL '1 day'
    GROUP BY bd.checkin_date, bd.company_id, bd.room_type_id, bd.nationality_id, bd.source_of_business
),
expected_arrivals AS (
    SELECT
        bd.checkin_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.nationality_id,
        bd.source_of_business,
        COUNT(DISTINCT bd.booking_line_id) AS expected_arrivals_count,
        SUM(bd.adult_count) AS expected_arrivals_adults,
        SUM(bd.child_count) AS expected_arrivals_children,
        SUM(bd.infant_count) AS expected_arrivals_infants
    FROM base_data bd
    WHERE bd.status IN ('confirmed', 'block')
    GROUP BY bd.checkin_date, bd.company_id, bd.room_type_id, bd.nationality_id, bd.source_of_business
),
expected_departures AS (
    SELECT
        bd.checkout_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.nationality_id,
        bd.source_of_business,
        COUNT(DISTINCT bd.booking_line_id) AS expected_departures_count,
        SUM(bd.adult_count) AS expected_departures_adults,
        SUM(bd.child_count) AS expected_departures_children,
        SUM(bd.infant_count) AS expected_departures_infants
    FROM base_data bd
    WHERE bd.status = 'check_in'
    GROUP BY bd.checkout_date, bd.company_id, bd.room_type_id, bd.nationality_id, bd.source_of_business
),
final_report AS (
    SELECT
        ds.report_date,
        bd.company_id,
        bd.room_type_id,
        bd.nationality_id,
        bd.source_of_business,
        COALESCE(inh.in_house_count, 0) AS in_house_count,
        COALESCE(inh.in_house_adults, 0) AS in_house_adults,
        COALESCE(inh.in_house_children, 0) AS in_house_children,
        COALESCE(inh.in_house_infants, 0) AS in_house_infants,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count,
        COALESCE(ea.expected_arrivals_adults, 0) AS expected_arrivals_adults,
        COALESCE(ea.expected_arrivals_children, 0) AS expected_arrivals_children,
        COALESCE(ea.expected_arrivals_infants, 0) AS expected_arrivals_infants,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures_count,
        COALESCE(ed.expected_departures_adults, 0) AS expected_departures_adults,
        COALESCE(ed.expected_departures_children, 0) AS expected_departures_children,
        COALESCE(ed.expected_departures_infants, 0) AS expected_departures_infants,
        GREATEST(
            COALESCE(inh.in_house_count, 0) + COALESCE(ea.expected_arrivals_count, 0) - COALESCE(ed.expected_departures_count, 0),
            0
        ) AS expected_in_house,
        GREATEST(
            COALESCE(inh.in_house_adults, 0) + COALESCE(ea.expected_arrivals_adults, 0) - COALESCE(ed.expected_departures_adults, 0),
            0
        ) AS expected_in_house_adults,
        GREATEST(
            COALESCE(inh.in_house_children, 0) + COALESCE(ea.expected_arrivals_children, 0) - COALESCE(ed.expected_departures_children, 0),
            0
        ) AS expected_in_house_children,
        GREATEST(
            COALESCE(inh.in_house_infants, 0) + COALESCE(ea.expected_arrivals_infants, 0) - COALESCE(ed.expected_departures_infants, 0),
            0
        ) AS expected_in_house_infants
    FROM date_series ds
    JOIN base_data bd ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    LEFT JOIN in_house inh ON ds.report_date = inh.report_date AND bd.company_id = inh.company_id AND bd.room_type_id = inh.room_type_id AND bd.nationality_id = inh.nationality_id AND bd.source_of_business = inh.source_of_business
    LEFT JOIN yesterday_in_house yih ON ds.report_date = yih.report_date AND bd.company_id = yih.company_id AND bd.room_type_id = yih.room_type_id AND bd.nationality_id = yih.nationality_id AND bd.source_of_business = yih.source_of_business
    LEFT JOIN expected_arrivals ea ON ds.report_date = ea.report_date AND bd.company_id = ea.company_id AND bd.room_type_id = ea.room_type_id AND bd.nationality_id = ea.nationality_id AND bd.source_of_business = ea.source_of_business
    LEFT JOIN expected_departures ed ON ds.report_date = ed.report_date AND bd.company_id = ed.company_id AND bd.room_type_id = ed.room_type_id AND bd.nationality_id = ed.nationality_id AND bd.source_of_business = ed.source_of_business
)
SELECT
    fr.report_date,
    fr.company_id,
    COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
    fr.source_of_business,
    fr.expected_in_house,
    fr.expected_in_house_adults,
    fr.expected_in_house_children,
    fr.expected_in_house_infants,
    fr.in_house_count,
    fr.in_house_adults,
    fr.in_house_children,
    fr.in_house_infants,
    fr.expected_arrivals_count,
    fr.expected_arrivals_adults,
    fr.expected_arrivals_children,
    fr.expected_arrivals_infants,
    fr.expected_departures_count,
    fr.expected_departures_adults,
    fr.expected_departures_children,
    fr.expected_departures_infants
FROM final_report fr
JOIN res_company rc ON fr.company_id = rc.id
JOIN room_type rt ON fr.room_type_id = rt.id
LEFT JOIN res_country rc_country ON rc_country.id = fr.nationality_id
LEFT JOIN country_region_res_country_rel crrc ON rc_country.id = crrc.res_country_id
LEFT JOIN country_region cr ON crrc.country_region_id = cr.id
GROUP BY fr.source_of_business, fr.report_date, fr.company_id, rc.name, fr.room_type_id, rt.room_type, fr.expected_in_house, fr.expected_in_house_adults, fr.expected_in_house_children, fr.expected_in_house_infants, fr.in_house_count, fr.in_house_adults, fr.in_house_children, fr.in_house_infants, fr.expected_arrivals_count, fr.expected_arrivals_adults, fr.expected_arrivals_children, fr.expected_arrivals_infants, fr.expected_departures_count, fr.expected_departures_adults, fr.expected_departures_children, fr.expected_departures_infants
ORDER BY
    fr.report_date,
    rc.name,
    rt.room_type;
        """

        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        self.env.cr.execute(query, (get_company, get_company, get_company))
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
                    source_of_business,  # Include market_segment in the output_pattern,
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
                    'source_of_business': source_of_business,
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
                _logger.error(f"Error processing record Source of Business Forecast: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
 