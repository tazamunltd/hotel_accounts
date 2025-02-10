from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class CompanyForecastReport(models.Model):
    _name = 'company.forecast.report'
    _description = 'Company Forecast Report'

    
    company_id = fields.Many2one('res.company', string='Company id', required=True)
    company_name = fields.Char(string='Company')
    report_date = fields.Date(string='Report Date', required=True)
    room_type_name = fields.Char(string='Room Type')
    customer_name = fields.Char(string='Customer Name')
    expected_arrivals_count = fields.Integer(string='Exp.Arrivals')
    expected_departures_count = fields.Integer(string='Exp.Departures')
    in_house_count = fields.Integer(string='In House')
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
    expected_in_house_count = fields.Integer(string='Exp.Inhouse')
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
            'room_type_name',
            'customer_name',
            'expected_arrivals_count',
            'expected_departures_count',
            'in_house_count',
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
            'expected_in_house_count',
            'expected_in_house_adults',
            'expected_in_house_children',
            'expected_in_house_infants'

        ])


    @api.model
    def action_generate_results(self):
        """Generate and update room results by company."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_company_forecast_report()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_company_forecast_report(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_company_forecast_report")

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
        rbl.id AS booking_line_id,
        rb.company_id,
        rbl.hotel_room_type AS room_type_id,
        rb.partner_id AS customer_id,
        rp.name AS customer_name,
        rbl.checkin_date::date AS checkin_date,
        rbl.checkout_date::date AS checkout_date,
        rbl.adult_count,
        rb.child_count,
        rb.infant_count,
        rbls.status,
        rbls.change_time
    FROM room_booking_line rbl
    JOIN room_booking rb ON rb.id = rbl.booking_id
    JOIN res_partner rp ON rb.partner_id = rp.id
    LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
),
in_house AS (
    SELECT
        ds.report_date,
        bd.company_id,
        bd.room_type_id,
        bd.customer_id,
        bd.customer_name,
        COUNT(DISTINCT bd.booking_line_id) AS in_house_count,
        SUM(bd.adult_count) AS in_house_adults,
        SUM(bd.child_count) AS in_house_children,
        SUM(bd.infant_count) AS in_house_infants
    FROM date_series ds
    JOIN base_data bd 
        ON bd.checkin_date <= ds.report_date 
       AND bd.checkout_date > ds.report_date 
       AND bd.status = 'check_in'
    GROUP BY ds.report_date, bd.company_id, bd.room_type_id, bd.customer_id, bd.customer_name
),
expected_arrivals AS (
    SELECT
        bd.checkin_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.customer_id,
        bd.customer_name,
        COUNT(DISTINCT bd.booking_line_id) AS expected_arrivals_count,
        SUM(bd.adult_count) AS expected_arrivals_adults,
        SUM(bd.child_count) AS expected_arrivals_children,
        SUM(bd.infant_count) AS expected_arrivals_infants
    FROM base_data bd
    WHERE bd.status IN ('confirmed', 'block')
    GROUP BY bd.checkin_date, bd.company_id, bd.room_type_id, bd.customer_id, bd.customer_name
),
expected_departures AS (
    SELECT
        bd.checkout_date AS report_date,
        bd.company_id,
        bd.room_type_id,
        bd.customer_id,
        bd.customer_name,
        COUNT(DISTINCT bd.booking_line_id) AS expected_departures_count,
        SUM(bd.adult_count) AS expected_departures_adults,
        SUM(bd.child_count) AS expected_departures_children,
        SUM(bd.infant_count) AS expected_departures_infants
    FROM base_data bd
    WHERE bd.status = 'check_in'
    GROUP BY bd.checkout_date, bd.company_id, bd.room_type_id, bd.customer_id, bd.customer_name
),
master_keys AS (
    SELECT DISTINCT report_date, company_id, room_type_id, customer_id, customer_name FROM in_house
    UNION
    SELECT DISTINCT report_date, company_id, room_type_id, customer_id, customer_name FROM expected_arrivals
    UNION
    SELECT DISTINCT report_date, company_id, room_type_id, customer_id, customer_name FROM expected_departures
),
final_report AS (
    SELECT
        mk.report_date,
        mk.company_id,
        mk.room_type_id,
        mk.customer_id,
        mk.customer_name,
        COALESCE(ih.in_house_count, 0) AS in_house_count,
        COALESCE(ih.in_house_adults, 0) AS in_house_adults,
        COALESCE(ih.in_house_children, 0) AS in_house_children,
        COALESCE(ih.in_house_infants, 0) AS in_house_infants,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals_count,
        COALESCE(ea.expected_arrivals_adults, 0) AS expected_arrivals_adults,
        COALESCE(ea.expected_arrivals_children, 0) AS expected_arrivals_children,
        COALESCE(ea.expected_arrivals_infants, 0) AS expected_arrivals_infants,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures_count,
        COALESCE(ed.expected_departures_adults, 0) AS expected_departures_adults,
        COALESCE(ed.expected_departures_children, 0) AS expected_departures_children,
        COALESCE(ed.expected_departures_infants, 0) AS expected_departures_infants
    FROM master_keys mk
    LEFT JOIN in_house ih 
        ON mk.report_date = ih.report_date 
       AND mk.company_id = ih.company_id
       AND mk.room_type_id = ih.room_type_id
       AND mk.customer_id = ih.customer_id
    LEFT JOIN expected_arrivals ea 
        ON mk.report_date = ea.report_date 
       AND mk.company_id = ea.company_id
       AND mk.room_type_id = ea.room_type_id
       AND mk.customer_id = ea.customer_id
    LEFT JOIN expected_departures ed 
        ON mk.report_date = ed.report_date 
       AND mk.company_id = ed.company_id
       AND mk.room_type_id = ed.room_type_id
       AND mk.customer_id = ed.customer_id
),
expected_in_house AS (
    SELECT
        fr.report_date,
        fr.company_id,
        fr.room_type_id,
        fr.customer_id,
        fr.customer_name,
        GREATEST(
            (COALESCE(fr.in_house_count, 0) + COALESCE(fr.expected_arrivals_count, 0) - COALESCE(fr.expected_departures_count, 0)),
            0
        ) AS expected_in_house_total,
        GREATEST(
            (COALESCE(fr.in_house_adults, 0) + COALESCE(fr.expected_arrivals_adults, 0) - COALESCE(fr.expected_departures_adults, 0)),
            0
        ) AS expected_in_house_adults,
        GREATEST(
            (COALESCE(fr.in_house_children, 0) + COALESCE(fr.expected_arrivals_children, 0) - COALESCE(fr.expected_departures_children, 0)),
            0
        ) AS expected_in_house_children,
        GREATEST(
            (COALESCE(fr.in_house_infants, 0) + COALESCE(fr.expected_arrivals_infants, 0) - COALESCE(fr.expected_departures_infants, 0)),
            0
        ) AS expected_in_house_infants
    FROM final_report fr
)
SELECT
    fr.report_date,
    fr.company_id,
    rc.name AS company_name,
    COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'), 'N/A') AS room_type_name,
    fr.customer_name,
    SUM(fr.expected_arrivals_count) AS expected_arrivals_count,
    SUM(fr.expected_arrivals_adults) AS expected_arrivals_adults,
    SUM(fr.expected_arrivals_children) AS expected_arrivals_children,
    SUM(fr.expected_arrivals_infants) AS expected_arrivals_infants,
    SUM(fr.expected_departures_count) AS expected_departures_count,
    SUM(fr.expected_departures_adults) AS expected_departures_adults,
    SUM(fr.expected_departures_children) AS expected_departures_children,
    SUM(fr.expected_departures_infants) AS expected_departures_infants,
    SUM(fr.in_house_count) AS in_house_count,
    SUM(fr.in_house_adults) AS in_house_adults,
    SUM(fr.in_house_children) AS in_house_children,
    SUM(fr.in_house_infants) AS in_house_infants,
    SUM(ei.expected_in_house_total) AS expected_in_house_total,
    SUM(ei.expected_in_house_adults) AS expected_in_house_adults,
    SUM(ei.expected_in_house_children) AS expected_in_house_children,
    SUM(ei.expected_in_house_infants) AS expected_in_house_infants
FROM final_report fr
JOIN res_company rc ON fr.company_id = rc.id
JOIN room_type rt ON fr.room_type_id = rt.id
JOIN expected_in_house ei 
    ON fr.report_date = ei.report_date
   AND fr.company_id = ei.company_id
   AND fr.room_type_id = ei.room_type_id
   AND fr.customer_id = ei.customer_id
WHERE fr.customer_id IS NOT NULL
GROUP BY fr.report_date, fr.company_id, rc.name, rt.room_type, fr.customer_name
ORDER BY fr.report_date, rc.name, rt.room_type, fr.customer_name;
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
                    company_name,
                    room_type_name,
                    customer_name,
                    expected_arrivals_count,
                    expected_arrivals_adults,
                    expected_arrivals_children,
                    expected_arrivals_infants,

                    expected_departures_count,
                    expected_departures_adults,
                    expected_departures_children,
                    expected_departures_infants,

                    in_house_count,
                    in_house_adults,
                    in_house_children,
                    in_house_infants,

                    expected_in_house_count,
                    expected_in_house_adults,
                    expected_in_house_children,
                    expected_in_house_infants
                ) = result

                records_to_create.append({
                    'report_date': report_date,
                    'company_id': company_id,
                    'company_name': company_name,
                    'room_type_name': room_type_name,
                    'customer_name': customer_name,
                    'expected_arrivals_count': expected_arrivals_count,
                    'expected_arrivals_adults': expected_arrivals_adults,
                    'expected_arrivals_children': expected_arrivals_children,
                    'expected_arrivals_infants': expected_arrivals_infants,
                    'expected_departures_count': expected_departures_count,
                    'expected_departures_adults': expected_departures_adults,
                    'expected_departures_children': expected_departures_children,
                    'expected_departures_infants': expected_departures_infants,
                    'in_house_count': in_house_count,
                    'in_house_adults': in_house_adults,
                    'in_house_children': in_house_children,
                    'in_house_infants': in_house_infants,
                    'expected_in_house_count': expected_in_house_count,
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
 