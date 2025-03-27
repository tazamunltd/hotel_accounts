from odoo import models, fields, api, _
import logging
import datetime
from datetime import timedelta

_logger = logging.getLogger(__name__)

class RevenueForecast(models.Model):
    _name = 'revenue.forecast'
    _description = 'Revenue Forecast'

    
    company_id = fields.Many2one('res.company', string='Hotel', required=True)
    company_name = fields.Char(string='Hotel')
    report_date = fields.Date(string='Report Date', required=True)
    in_house = fields.Integer(string='Rooms')
    expected_occupied_rate = fields.Float(string='Occupancy(%)', readonly=True)
    out_of_order = fields.Integer(string='Out of order', readonly=True)
    available_rooms = fields.Integer(string='Available Rooms', readonly=True)
    rate_revenue = fields.Integer(string='Rate Revenue', readonly=True)
    total_revenue = fields.Integer(string='Total Revenue', readonly=True)
    fnb_revenue = fields.Integer(string='F&B Revenue', readonly=True)
    pax_adults = fields.Integer(string='Adult', readonly=True)
    pax_children = fields.Integer(string='Children', readonly=True)
    pax_infants = fields.Integer(string='Infants', readonly=True)
    pax_totals = fields.Integer(string='Total', readonly=True)
    pax_chi_inf = fields.Char(string='Pax/Chi/Inf', readonly=True)
    rate_per_room = fields.Integer(string='Rate/Room', readonly=True)
    rate_per_pax = fields.Integer(string='Rate/Pax', readonly=True)
    meals_per_pax = fields.Integer(string='Meals/Pax', readonly=True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True)

    @api.model
    def action_run_process_by_revenue_forecast(self):
        """Runs the revenue forecast process based on context and returns the action."""
        system_date = self.env.company.system_date.date()  # or fields.Date.today() if needed
        default_from_date = system_date
        default_to_date = system_date + timedelta(days=30)

        if self.env.context.get('filtered_date_range'):
            self.env["revenue.forecast"].run_process_by_revenue_forecast()

            return {
                'name': _('Revenue Forecast Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'revenue.forecast',
                'view_mode': 'tree,pivot,graph',
                'views': [
                    (self.env.ref(
                        'hotel_management_odoo.view_revenue_forecast_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management_odoo.view_revenue_forecast_pivot').id, 'pivot'),
                    (self.env.ref(
                        'hotel_management_odoo.view_revenue_forecast_graph').id, 'graph'),
                ],
                'target': 'current',
            }
        else:
            self.env["revenue.forecast"].run_process_by_revenue_forecast(
                from_date=default_from_date,
                to_date=default_to_date
            )

            # 3) Show only records for that 30-day window by specifying a domain
            domain = [
                ('report_date', '>=', default_from_date),
                ('report_date', '<=', default_to_date),
            ]
            return {
                'name': _('Revenue Forecast Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'revenue.forecast',
                'view_mode': 'tree,pivot,graph',
                'views': [
                    (self.env.ref(
                        'hotel_management_odoo.view_revenue_forecast_tree').id, 'tree'),
                    (self.env.ref(
                        'hotel_management_odoo.view_revenue_forecast_pivot').id, 'pivot'),
                    (self.env.ref(
                        'hotel_management_odoo.view_revenue_forecast_graph').id, 'graph'),
                ],
                'domain': domain,  # Ensures no data is displayed
                'target': 'current',
            }
    
    @api.model
    def search_available_rooms(self, from_date, to_date):
        """
        Search for available rooms based on the provided criteria.
        """
        self.run_process_by_revenue_forecast(from_date, to_date)
        company_ids = [company.id for company in self.env.companies]
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
            ('company_id', 'in', company_ids)
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
            'rate_per_room',
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

    def run_process_by_revenue_forecast(self,from_date = None, to_date = None):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_revenue_forecast")

        # Delete existing records
        self.search([]).unlink()
        if not from_date or not to_date:
            # Fallback if the method is called without parameters
            system_date = self.env.company.system_date.date()
            from_date = system_date
            to_date = system_date + timedelta(days=30)
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
        SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count,
        SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms,
        BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    GROUP BY hi.company_id 
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
        rcs.name as company_name,
        rb.checkin_date::date AS checkin_date,
        rb.checkout_date::date AS checkout_date,
        sdc.system_date::date as system_date,
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
    JOIN room_forecast_booking_line_rel rfbl ON rbl.id = rfbl.booking_line_id  
    LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
    LEFT JOIN res_partner rp ON rb.partner_id = rp.id
    LEFT JOIN public.meal_pattern mp ON rb.meal_pattern = mp.id
    LEFT JOIN res_country rc ON rb.nationality = rc.id
    LEFT JOIN system_date_company sdc ON sdc.company_id = rb.company_id
    LEFT JOIN res_company rcs ON rcs.id = rb.company_id
    LEFT JOIN room_type_data rtd ON rtd.room_type_id = rbl.hotel_room_type
    WHERE rb.company_id in (SELECT company_id FROM company_ids)
)
	,
latest_line_status AS (
    --     SELECT DISTINCT ON (bd.booking_id)  -- Select the latest status per booking
	SELECT DISTINCT ON (bd.booking_id, ds.report_date)
        ds.report_date,
        bd.system_date,
        bd.checkin_date,
        bd.checkout_date,
        bd.booking_id,
        bd.company_id,
        bd.company_name,
        bd.booking_line_id,
        bd.room_id,
        bd.adult_count,
        bd.child_count,
        bd.infant_count,
        bd.status AS final_status,   
        bd.change_time,
        bd.house_use,
        bd.complementary
    FROM base_data bd
    JOIN date_series ds ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
    ORDER BY bd.booking_id, ds.report_date, bd.change_time DESC  -- Get latest change_time for each booking_id
)
	,

	
rate_details AS (
        SELECT 
            lls.report_date,
        	lls.system_date,
       	 	lls.company_id,
			lls.company_name,

            SUM(rrf.rate)               AS rate_revenue,
            SUM(rrf.meals)              AS fnb_revenue,
            SUM(rrf.rate) + SUM(rrf.meals) AS total_revenue
        FROM latest_line_status as lls
        JOIN room_rate_forecast rrf 
            ON rrf.room_booking_id = lls.booking_id
           AND rrf.date = lls.report_date
			join room_booking_line rbl on rbl.booking_id = rrf.room_booking_id 
			and rrf.room_booking_id is not null 
			and rbl.current_company_id = lls.company_id
        GROUP BY 
        lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name

    )
--	select * from rate_details;
	,
in_house AS (
    SELECT
        lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
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
		lls.company_name

)
-- Select * from in_house;
,
out_of_order AS (
    SELECT
        lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
        COALESCE(COUNT(DISTINCT hr.id), 0)  AS out_of_order_count
    FROM latest_line_status as lls
    JOIN out_of_order_management_fron_desk ooo
    ON ooo.company_id = lls.company_id 
	and  lls.report_date BETWEEN ooo.from_date AND ooo.to_date
    JOIN hotel_room hr
    ON hr.id = ooo.room_number
    GROUP BY 
	 lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name
   
)
	,
yesterday_in_house AS (
    SELECT
lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
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
		lls.company_name
   
)
-- Select * from yesterday_in_house;
,   
  
expected_arrivals AS (
    SELECT 
lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count,
	    SUM(lls.adult_count) AS ea_adults_count,
        SUM(lls.child_count) AS ea_children_count,
        SUM(lls.infant_count) AS ea_infants_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY 
		lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name
	),
expected_departures AS (
    SELECT
lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
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
		lls.company_name
),
master_keys AS (
    SELECT report_date, company_id, system_date, company_name
		
    FROM in_house
    UNION
 	SELECT report_date, company_id, system_date, company_name		
	FROM expected_arrivals
    UNION
 	SELECT report_date, company_id, system_date, company_name
	FROM expected_departures
    UNION
 	SELECT report_date, company_id, system_date, company_name
	FROM yesterday_in_house
	UNION
	SELECT report_date, company_id, system_date, company_name
	FROM out_of_order
	UNION
	SELECT report_date, company_id, system_date, company_name
	FROM rate_details
),
final_report AS (
    SELECT
        mk.report_date,
        mk.company_id,
        mk.company_name,
        COALESCE(inv.total_room_count, 0) AS total_rooms,
		COALESCE(ooo.out_of_order_count, 0) AS out_of_order_rooms,
		COALESCE(inv.total_room_count - COALESCE(ooo.out_of_order_count , 0), 0) AS available_rooms,
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
            )
         AS expected_in_house,
     	
	
		CASE WHEN mk.report_date <= mk.system_date THEN
            ih.in_house_adults
        ELSE
            GREATEST(
                COALESCE(yh.yin_house_adults, 0)
                + COALESCE(ea.ea_adults_count, 0)
                - COALESCE(ed.ed_adults_count, 0),
                0
            )
        END AS expected_in_house_adults,
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
        END AS expected_in_house_children,
		CASE WHEN mk.report_date <= mk.system_date THEN
            ih.in_house_infants
        ELSE
            GREATEST(
                COALESCE(yh.yin_house_infants, 0)
                + COALESCE(ea.ea_infants_count, 0)
                - COALESCE(ed.ed_infants_count, 0),
                0
            )
        END AS expected_in_house_infants,
	COALESCE(rd.rate_revenue, 0) AS rate_revenue,
	COALESCE(rd.fnb_revenue, 0) AS fnb_revenue,
	COALESCE(rd.total_revenue, 0) AS total_revenue
	
	FROM master_keys mk
    LEFT JOIN in_house ih
        ON  mk.report_date   = ih.report_date
        AND mk.company_id    = ih.company_id
        
    LEFT JOIN yesterday_in_house yh
        ON  mk.report_date   = yh.report_date
        AND mk.company_id    = yh.company_id
        
    LEFT JOIN expected_arrivals ea
        ON  mk.report_date   = ea.report_date
        AND mk.company_id    = ea.company_id
        
	LEFT JOIN expected_departures ed
        ON  mk.report_date   = ed.report_date
        AND mk.company_id    = ed.company_id
        
	LEFT JOIN out_of_order ooo
        ON  mk.report_date   = ooo.report_date
        AND mk.company_id    = ooo.company_id
        
	LEFT JOIN rate_details rd
        ON  mk.report_date   = rd.report_date
        AND mk.company_id    = rd.company_id
        
	LEFT JOIN inventory inv 
	    --ON  mk.report_date   = ed.report_date
		ON inv.company_id = mk.company_id 
	
)

SELECT
    fr.report_date,
    fr.company_id,
	fr.company_name,
	fr.total_rooms,
	fr.out_of_order_rooms,
	fr.available_rooms,
	SUM(fr.in_house_count) AS in_house,
    SUM(fr.in_house_adults) AS pax_adults,
    SUM(fr.in_house_children) AS pax_children,
    SUM(fr.in_house_infants) AS pax_infants,
    SUM(fr.in_house_adults + fr.in_house_children + fr.in_house_infants) AS pax_total,
	CASE WHEN  fr.available_rooms >0 THEN
	SUM(fr.expected_in_house) * 100 / fr.available_rooms
	ELSE SUM(0)
	END
	as expected_occupied_rate,
	SUM(fr.rate_revenue) as rate_revenue,
	SUM(fr.fnb_revenue) as fnb_revenue,
	SUM(fr.total_revenue) as total_revenue,
	CASE WHEN SUM(fr.expected_in_house) >0 then
	SUM(fr.rate_revenue) / SUM(fr.expected_in_house) 
	ELSE SUM(0)
	END
	as rate_per_room,
	CASE WHEN  SUM(fr.expected_in_house_adults) > 0 THEN
	SUM(fr.rate_revenue) / SUM(fr.expected_in_house_adults)
	ELSE SUM(0)
	END
	as rate_per_pax,
	CASE WHEN SUM(fr.expected_in_house_adults) > 0 THEN
	SUM(fr.fnb_revenue) / SUM(fr.expected_in_house_adults)
	ELSE SUM(0)
	END
	as rate_per_meal
	
	
FROM final_report fr

WHERE fr.company_id IN (SELECT company_id FROM company_ids)  -- ✅ Fix: Apply WHERE condition here
--   AND (COALESCE(fr.expected_arrivals, 0) + COALESCE(fr.expected_departures, 0) + COALESCE(fr.in_house_count, 0)) > 0
GROUP BY fr.report_date, fr.company_name, fr.company_id , fr.total_rooms, fr.out_of_order_rooms, fr.available_rooms
ORDER BY fr.report_date, fr.company_id;

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
                (
                    report_date,
                    company_id,
                    company_name,
                    total_rooms,
                    out_of_order,
                    available_rooms,
                    in_house,
                    pax_adults,
                    pax_children,
                    pax_infants,
                    pax_totals,
                    occupancy_rate,
                    rate_revenue,
                    fnb_revenue,
                    total_revenue,
                    rate_per_room,
                    rate_per_pax,
                    rate_per_meal
                ) = result


                records_to_create.append({
                    'report_date': report_date,
                    'company_id': company_id,
                    'rate_revenue':rate_revenue,
                    'fnb_revenue':fnb_revenue,
                    'total_revenue':total_revenue,
                    'total_rooms': total_rooms,
                    'out_of_order': out_of_order,
                    'available_rooms':available_rooms,
                    'in_house': in_house,
                    'pax_adults': pax_adults,
                    'pax_children': pax_children,
                    'pax_infants': pax_infants,
                    'pax_totals': pax_totals,
                    'rate_per_room': rate_per_room,
                    'rate_per_pax': rate_per_pax,
                    'meals_per_pax': rate_per_meal,
                    'expected_occupied_rate': occupancy_rate,
                })


            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
 