from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class RevenueForecast(models.Model):
    _name = 'revenue.forecast'
    _description = 'Revenue Forecast'

    
    # company_id = fields.Many2one('res.company', string='Company', required=True)
    report_date = fields.Date(string='Report Date', required=True)
    in_house = fields.Integer(string='Rooms')
    expected_occupied_rate = fields.Float(string='Occupancy(%)', readonly=True)
    out_of_order = fields.Integer(string='Out of order', readonly=True)
    available_rooms = fields.Integer(string='Available Rooms', readonly=True)
    rate_revenue = fields.Integer(string='Rate Revenue', readonly=True)
    total_revenue = fields.Integer(string='Total Revenue', readonly=True)
    fnb_revenue = fields.Integer(string='F&B Revenue', readonly=True)
    pax_chi_inf = fields.Char(string='Pax/Chi/Inf', readonly=True)
    average_rate_per_room = fields.Integer(string='Rate/Room', readonly=True)
    rate_per_pax = fields.Integer(string='Rate/Pax', readonly=True)
    meals_per_pax = fields.Integer(string='Meals/Pax', readonly=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True)
    

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_revenue_forecast()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_revenue_forecast(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_revenue_forecast")

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

/* LATEST_LINE_STATUS */
latest_line_status AS (
    SELECT DISTINCT ON (rbl.id, ds.report_date)
           rbl.id AS booking_line_id,
           ds.report_date,
           rb.checkin_date::date   AS checkin_date,
           rb.checkout_date::date  AS checkout_date,
           rbl.adult_count,
           rb.child_count,
           rb.infant_count,
           rbls.status             AS final_status
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb
      ON rb.id = rbl.booking_id
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
          AND rbls.change_time::date <= ds.report_date
    WHERE rb.checkin_date <= ds.report_date
      AND rb.checkout_date > ds.report_date
    ORDER BY
       rbl.id,
       ds.report_date,
       rbls.change_time DESC NULLS LAST
),

/* INVENTORY */
inventory AS (
    SELECT
        SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count
    FROM hotel_inventory hi
),

/* OUT_OF_ORDER */
out_of_order AS (
    SELECT
        ds.report_date,
        COUNT(DISTINCT hr.id) AS out_of_order_count
    FROM date_series ds
    JOIN out_of_order_management_fron_desk ooo
      ON ds.report_date BETWEEN ooo.from_date AND ooo.to_date
    JOIN hotel_room hr
      ON hr.id = ooo.room_number
    GROUP BY ds.report_date
),

/* IN-HOUSE */
in_house AS (
    SELECT
        lls.report_date,
        COUNT(DISTINCT lls.booking_line_id)     AS in_house_count,
        SUM(COALESCE(lls.adult_count, 0))       AS in_house_adults,
        SUM(COALESCE(lls.child_count, 0))       AS in_house_children,
        SUM(COALESCE(lls.infant_count, 0))      AS in_house_infants
    FROM latest_line_status lls
    JOIN room_booking_line rbl
      ON lls.booking_line_id = rbl.id
    WHERE lls.final_status = 'check_in'
    GROUP BY lls.report_date
),

/* ROOM AVAILABILITY */
room_availability AS (
    SELECT
        ds.report_date,
        (SELECT total_room_count FROM inventory) AS total_rooms,
        COALESCE(ooo.out_of_order_count, 0)      AS out_of_order,
        ((SELECT total_room_count FROM inventory) 
            - COALESCE(ooo.out_of_order_count, 0)) AS available_rooms,
        COALESCE(ih.in_house_count, 0)           AS in_house,
        COALESCE(ih.in_house_adults, 0)          AS in_house_adults,
        COALESCE(ih.in_house_children, 0)        AS in_house_children,
        COALESCE(ih.in_house_infants, 0)         AS in_house_infants
    FROM date_series ds
    LEFT JOIN out_of_order ooo 
           ON ds.report_date = ooo.report_date
    LEFT JOIN in_house ih 
           ON ds.report_date = ih.report_date
),

/* RATE DETAILS */
check_in_data AS (
    SELECT 
        rb.id               AS booking_id,
        rbl.id              AS room_booking_line_id,
        rsl.id              AS status_line_id,
        ds.report_date      AS report_date,
        rsl.status
    FROM room_booking rb
    JOIN room_booking_line rbl 
      ON rb.id = rbl.booking_id
    JOIN room_booking_line_status rsl 
      ON rbl.id = rsl.booking_line_id
    JOIN date_series ds 
      ON ds.report_date BETWEEN rb.checkin_date AND rb.checkout_date
    WHERE rsl.status = 'check_in'
),
rate_details AS (
    SELECT 
        cid.report_date,
        SUM(rrf.rate)               AS rate_revenue,
        SUM(rrf.meals)              AS fnb_revenue,
        SUM(rrf.rate) + SUM(rrf.meals) AS total_revenue
    FROM check_in_data cid
    JOIN room_rate_forecast rrf 
        ON cid.booking_id = rrf.room_booking_id
       AND cid.report_date = rrf.date
    GROUP BY 
        cid.report_date
)

SELECT 
    rd.report_date,
    rd.rate_revenue,
    rd.fnb_revenue,
    rd.total_revenue,
    ra.total_rooms,
    ra.out_of_order,
    ra.available_rooms,
    ra.in_house,
    
    -- Combine Adults / Children / Infants into one column
    (
       COALESCE(ra.in_house_adults, 0)::text 
       || '/' 
       || COALESCE(ra.in_house_children, 0)::text 
       || '/' 
       || COALESCE(ra.in_house_infants, 0)::text
    ) AS "pax/ch/inf",

    -- Average rate per room (only for rooms that have checked in)
    CASE 
      WHEN ra.in_house > 0 THEN rd.rate_revenue / ra.in_house
      ELSE 0 
    END AS "avg_rate_per_room",

    -- Total Pax calculation
    -- We'll reuse it inline in the CASE statements below
    -- but you could also do it in a sub-SELECT or CTE if you prefer.
    
    -- Rate per Pax
    CASE
      WHEN (COALESCE(ra.in_house_adults, 0) 
          + COALESCE(ra.in_house_children, 0) 
          + COALESCE(ra.in_house_infants, 0)) > 0
      THEN rd.rate_revenue 
            / (COALESCE(ra.in_house_adults, 0) 
             + COALESCE(ra.in_house_children, 0) 
             + COALESCE(ra.in_house_infants, 0))
      ELSE 0
    END AS "rate_per_pax",

    -- Meals per Pax
    CASE
      WHEN (COALESCE(ra.in_house_adults, 0) 
          + COALESCE(ra.in_house_children, 0) 
          + COALESCE(ra.in_house_infants, 0)) > 0
      THEN rd.fnb_revenue
            / (COALESCE(ra.in_house_adults, 0) 
             + COALESCE(ra.in_house_children, 0) 
             + COALESCE(ra.in_house_infants, 0))
      ELSE 0
    END AS "meals_per_pax"

FROM 
    rate_details rd
LEFT JOIN 
    room_availability ra 
      ON rd.report_date = ra.report_date
ORDER BY 
    rd.report_date;
        """

        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")

        records_to_create = []

        for result in results:
            try:
                (
                    report_date,
                    rate_revenue,
                    fnb_revenue,
                    total_revenue,
                    total_rooms,
                    out_of_order,
                    available_rooms,
                    in_house,
                    pax_chi_inf,
                    average_rate_per_room,
                    rate_per_pax,
                    meals_per_pax
                ) = result

                expected_occupied_rate = (in_house or 0) / (available_rooms or 1) * 100


                records_to_create.append({
                    'report_date': report_date,
                    'rate_revenue':rate_revenue,
                    'fnb_revenue':fnb_revenue,
                    'total_revenue':total_revenue,
                    'total_rooms': total_rooms,
                    'out_of_order': out_of_order,
                    'available_rooms':available_rooms,
                    'in_house': in_house,
                    'pax_chi_inf': pax_chi_inf,
                    'average_rate_per_room': average_rate_per_room,
                    'rate_per_pax': rate_per_pax,
                    'meals_per_pax': meals_per_pax,
                    'expected_occupied_rate': expected_occupied_rate,
                })


            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
 