from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class RevenueForecast(models.Model):
    _name = 'revenue.forecast'
    _description = 'Revenue Forecast'

    
    company_id = fields.Many2one('res.company', string='Company', required=True)
    company_name = fields.Char(string='Company')
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
            'company_name',
            'in_house',
            'expected_occupied_rate',
            'out_of_order',
            'available_rooms',
            'rate_revenue',
            'total_revenue',
            'fnb_revenue',
            'pax_chi_inf',
            'average_rate_per_room',
            'rate_per_pax',
            'meals_per_pax',
            'total_rooms'
        ])
    

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
    
    /* ----------------------------------------------------------------------------
       3) LATEST_LINE_STATUS:
       For each booking line and report date, find the latest status as of that day.
       ---------------------------------------------------------------------------- */
    latest_line_status AS (
        SELECT DISTINCT ON (rbl.id, ds.report_date)
               rc.id AS company_id,                  -- NEW: Include company_id
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
        JOIN hotel_room hr 
          ON hr.id = rbl.room_id
        JOIN res_company rc                    -- NEW: Join with res_company
          ON rb.company_id = rc.id
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
    
    /* ----------------------------------------------------------------------------
       4) INVENTORY:
       Calculate total room counts per company.
       ---------------------------------------------------------------------------- */
    inventory AS (
        SELECT
            rc.id AS company_id,                                   -- NEW: Include company_id
            SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count
        FROM hotel_inventory hi
        JOIN res_company rc
          ON hi.company_id = rc.id
        GROUP BY rc.id
    ),
    
    /* ----------------------------------------------------------------------------
       5) OUT_OF_ORDER:
       Count out-of-order rooms per company and date.
       ---------------------------------------------------------------------------- */
    out_of_order AS (
        SELECT
            rc.id AS company_id,                   -- NEW: Include company_id
            ds.report_date,
            COUNT(DISTINCT hr.id) AS out_of_order_count
        FROM date_series ds
        JOIN out_of_order_management_fron_desk ooo
          ON ds.report_date BETWEEN ooo.from_date AND ooo.to_date
        JOIN hotel_room hr
          ON hr.id = ooo.room_number
        JOIN res_company rc
          ON hr.company_id = rc.id                -- NEW: Join with res_company
        GROUP BY rc.id, ds.report_date
    ),
    
    /* ----------------------------------------------------------------------------
       6) IN-HOUSE:
       Count in-house bookings per company and date.
       ---------------------------------------------------------------------------- */
    in_house AS (
        SELECT
            lls.report_date,
            lls.company_id,
            COUNT(DISTINCT lls.booking_line_id)     AS in_house_count,
            SUM(COALESCE(lls.adult_count, 0))       AS in_house_adults,
            SUM(COALESCE(lls.child_count, 0))       AS in_house_children,
            SUM(COALESCE(lls.infant_count, 0))      AS in_house_infants
        FROM latest_line_status lls
        WHERE lls.final_status = 'check_in'
        GROUP BY lls.report_date, lls.company_id
    ),
    
    /* ----------------------------------------------------------------------------
       7) ROOM_AVAILABILITY:
       Combine inventory, out-of-order, and in-house data to determine availability.
       ---------------------------------------------------------------------------- */
    room_availability AS (
        SELECT
            ds.report_date,
            rc.id AS company_id,
            COALESCE(inv.total_room_count, 0) AS total_rooms,
            COALESCE(ooo.out_of_order_count, 0) AS out_of_order,
            (COALESCE(inv.total_room_count, 0) - COALESCE(ooo.out_of_order_count, 0)) AS available_rooms,
            COALESCE(ih.in_house_count, 0) AS in_house,
            COALESCE(ih.in_house_adults, 0) AS in_house_adults,
            COALESCE(ih.in_house_children, 0) AS in_house_children,
            COALESCE(ih.in_house_infants, 0) AS in_house_infants
        FROM date_series ds
        CROSS JOIN res_company rc
        LEFT JOIN inventory inv 
               ON inv.company_id = rc.id
        LEFT JOIN out_of_order ooo 
               ON ooo.company_id = rc.id
              AND ooo.report_date = ds.report_date
        LEFT JOIN in_house ih 
               ON ih.company_id = rc.id
              AND ih.report_date = ds.report_date
    ),
    
    /* ----------------------------------------------------------------------------
       8) CHECK-IN DATA:
       Identify bookings that have checked in within the reporting period.
       ---------------------------------------------------------------------------- */
    check_in_data AS (
        SELECT 
            rc.id AS company_id,                                   -- NEW: Include company_id
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
        JOIN res_company rc                                      -- NEW: Join with res_company
          ON rb.company_id = rc.id
        WHERE rsl.status = 'check_in'
    ),
    
    /* ----------------------------------------------------------------------------
       9) RATE_DETAILS:
       Calculate revenue based on room rates and meals per company and date.
       ---------------------------------------------------------------------------- */
    rate_details AS (
        SELECT 
            cid.company_id,                                      -- NEW: Include company_id
            cid.report_date,
            SUM(rrf.rate)               AS rate_revenue,
            SUM(rrf.meals)              AS fnb_revenue,
            SUM(rrf.rate) + SUM(rrf.meals) AS total_revenue
        FROM check_in_data cid
        JOIN room_rate_forecast rrf 
            ON cid.booking_id = rrf.room_booking_id
           AND cid.report_date = rrf.date
        GROUP BY 
            cid.company_id,
            cid.report_date
    )
    
    /* ----------------------------------------------------------------------------
       10) FINAL SELECT:
       Aggregate and present the data with company-wise segregation.
       ---------------------------------------------------------------------------- */
    SELECT 
        ra.report_date,
        ra.company_id,
        rc.name AS company_name,                             -- NEW: Include company name
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
        room_availability ra
		
    LEFT JOIN 
        rate_details rd 
          ON ra.company_id = rd.company_id
         AND ra.report_date = rd.report_date
    JOIN 
        res_company rc 
          ON ra.company_id = rc.id                     -- NEW: Join to get company name

    ORDER BY 
        ra.report_date,
        rc.name;

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
                    'company_id': company_id,
                    'company_name': company_name,
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
 