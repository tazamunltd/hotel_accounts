from odoo import models, fields, api, _
import logging
import datetime

_logger = logging.getLogger(__name__)

class RoomsForecastReport(models.Model):
    _name = 'rooms.forecast.report'
    _description = 'Rooms Forecast Report'

    
    company_id = fields.Many2one('res.company', string='Hotel', required=True)
    report_date = fields.Date(string='Report Date', required=True)
    room_type_name = fields.Char(string='Room Type')
    total_rooms = fields.Integer(string='Total Rooms')
    expected_arrivals = fields.Integer(string='Exp.Arrivals')
    expected_departures = fields.Integer(string='Exp.Departures')
    in_house = fields.Integer(string='In House')
    expected_arrivals_adult_count = fields.Integer(string='Exp.Arrivals Adults')
    expected_arrivals_child_count = fields.Integer(string='Exp.Arrivals Children')
    expected_arrivals_infant_count = fields.Integer(string='Exp.Arrivals Infants')
    expected_departures_adult_count = fields.Integer(string='Exp.Departures Adults')
    expected_departures_child_count = fields.Integer(string='Exp.Departures Children')
    expected_departures_infant_count = fields.Integer(string='Exp.Departures Infants')
    in_house_adult_count = fields.Integer(string='In House Adults')
    in_house_child_count = fields.Integer(string='In House Children')
    in_house_infant_count = fields.Integer(string='In House Infants')
    in_house_total = fields.Integer(string='In House Total')
    available = fields.Integer(string='Available', readonly=True)
    expected_occupied_rate = fields.Integer(string='Exp.Occupied Rate (%)', readonly=True)
    out_of_order = fields.Integer(string='Out of Order', readonly=True)
    # overbook  = fields.Integer(string='Overbook', readonly=True)
    free_to_sell = fields.Integer(string='Free to sell', readonly=True)
    sort_order = fields.Integer(string='Sort Order', readonly=True)
    out_of_service = fields.Integer(string='Out of Service', readonly=True)
    expected_in_house = fields.Integer(string='Expected In House', readonly=True)
    expected_in_house_adult_count = fields.Integer(string='Exp.In House Adults', readonly=True)
    expected_in_house_child_count = fields.Integer(string='Exp.In House Children', readonly=True)
    expected_in_house_infant_count = fields.Integer(string='Exp.In House Infants', readonly=True)
    available_rooms = fields.Integer(string='Available Rooms', readonly=True) 

    @api.model
    def action_run_process_by_rooms_forecast(self):
        """Runs the rooms forecast process based on context and returns the action."""
        if self.env.context.get('filtered_date_range'):
            self.env["rooms.forecast.report"].run_process_by_rooms_forecast()

            return {
                'name': _('Rooms Forecast Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'rooms.forecast.report',
                'view_mode': 'tree,pivot,graph',
                'views': [
                    (self.env.ref('hotel_management_odoo.view_rooms_forecast_tree').id, 'tree'),
                    (self.env.ref('hotel_management_odoo.view_rooms_forecast_pivot').id, 'pivot'),
                    (self.env.ref('hotel_management_odoo.view_rooms_forecast_graph').id, 'graph'),
                ],
                'target': 'current',
            }
        else:
            return {
                'name': _('Rooms Forecast Report'),
                'type': 'ir.actions.act_window',
                'res_model': 'rooms.forecast.report',
                'view_mode': 'tree,pivot,graph',
                'views': [
                    (self.env.ref('hotel_management_odoo.view_rooms_forecast_tree').id, 'tree'),
                    (self.env.ref('hotel_management_odoo.view_rooms_forecast_pivot').id, 'pivot'),
                    (self.env.ref('hotel_management_odoo.view_rooms_forecast_graph').id, 'graph'),
                ],
                'domain': [('id', '=', False)],  # Ensures no data is displayed
                'target': 'current',
            }
    

    @api.model
    def search_available_rooms(self, from_date, to_date):
        """
        Search for available rooms based on the provided criteria.
        """
        self.run_process_by_rooms_forecast(from_date, to_date)
        company_ids = [company.id for company in self.env.companies]
        domain = [
            ('report_date', '>=', from_date),
            ('report_date', '<=', to_date),
            ('company_id', 'in', company_ids)
        ]

        results = self.search(domain)

        return results.read([
            'report_date',
            'room_type_name',
            'total_rooms',
            'expected_arrivals',
            'expected_departures',
            'in_house',
            'expected_arrivals_adult_count',
            'expected_arrivals_child_count',
            'expected_arrivals_infant_count',
            'expected_departures_adult_count',
            'expected_departures_child_count',
            'expected_departures_infant_count',
            'in_house_adult_count',
            'in_house_child_count',
            'in_house_infant_count',
            'in_house_total',
            'available',
            'expected_occupied_rate',
            'out_of_order',
            'free_to_sell',
            'sort_order',
            'out_of_service',
            'expected_in_house',
            'expected_in_house_adult_count',
            'expected_in_house_child_count',
            'expected_in_house_infant_count',
            'available_rooms'

        ])

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        _logger.info("Starting action_generate_results")
        try:
            self.run_process_by_rooms_forecast()
        except Exception as e:
            _logger.error(f"Error generating booking results: {str(e)}")
            raise ValueError(f"Error generating booking results: {str(e)}")

    def run_process_by_rooms_forecast(self,from_date = None, to_date = None):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_rooms_forecast")

        # Delete existing records
        self.search([]).unlink()
        _logger.info("Existing records deleted")
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
	 	hi.room_type AS hi_room_type_id,
        SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count,
        SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms,
        BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    GROUP BY hi.company_id , hi.room_type
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
		sdc.system_date ::date as system_date,
        rbl.id AS booking_line_id,
        rbl.room_id,
        rbl.hotel_room_type AS room_type_id,
		rtd.room_type_name,
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
	
),
in_house AS (
    SELECT
        lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_id,
		lls.room_type_name,
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
		lls.room_type_id,
		lls.room_type_name

),
out_of_order AS (
    SELECT
        lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_id,
		lls.room_type_name,
        COALESCE(COUNT(DISTINCT hr.id), 0)  AS out_of_order_count
    FROM latest_line_status as lls
    JOIN out_of_order_management_fron_desk ooo
    ON ooo.company_id = lls.company_id 
	and  lls.report_date BETWEEN ooo.from_date AND ooo.to_date
    JOIN hotel_room hr
    ON hr.id = ooo.room_number
    AND hr.room_type_name = lls.room_type_id
    GROUP BY 
	 lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_id,
		lls.room_type_name
   
),
yesterday_in_house AS (
    SELECT
lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_id,
		lls.room_type_name,
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
		lls.room_type_id,
		lls.room_type_name
   
),   
  
expected_arrivals AS (
    SELECT 
lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_id,
		lls.room_type_name,
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
		lls.room_type_id,
		lls.room_type_name
	),
expected_departures AS (
    SELECT
lls.report_date,
        lls.system_date,
        lls.company_id,
		lls.company_name,
		lls.room_type_id,
		lls.room_type_name,
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
		lls.room_type_id,
		lls.room_type_name
),
master_keys AS (
    SELECT report_date, company_id, system_date, company_name, room_type_id, room_type_name
	
    FROM in_house
    UNION
 	SELECT report_date, company_id, system_date, company_name, room_type_id, room_type_name		
	FROM expected_arrivals
    UNION
 	SELECT report_date, company_id, system_date, company_name, room_type_id, room_type_name
	FROM expected_departures
    UNION
 	SELECT report_date, company_id, system_date, company_name, room_type_id, room_type_name
	FROM yesterday_in_house
	UNION
	SELECT report_date, company_id, system_date, company_name, room_type_id, room_type_name
	FROM out_of_order

),
final_report AS (
    SELECT
        mk.report_date,
        mk.company_id,
        mk.company_name,
		mk.room_type_name,
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
        END AS expected_in_house_infants
	
	FROM master_keys mk
    LEFT JOIN in_house ih
        ON  mk.report_date   = ih.report_date
        AND mk.company_id    = ih.company_id
		AND mk.room_type_id = ih.room_type_id
		
        
    LEFT JOIN yesterday_in_house yh
        ON  mk.report_date   = yh.report_date
        AND mk.company_id    = yh.company_id
		AND mk.room_type_id = yh.room_type_id
        
    LEFT JOIN expected_arrivals ea
        ON  mk.report_date   = ea.report_date
        AND mk.company_id    = ea.company_id
		AND mk.room_type_id = ea.room_type_id
        
	LEFT JOIN expected_departures ed
        ON  mk.report_date   = ed.report_date
        AND mk.company_id    = ed.company_id
		AND mk.room_type_id = ed.room_type_id
        
	LEFT JOIN out_of_order ooo
        ON  mk.report_date   = ooo.report_date
        AND mk.company_id    = ooo.company_id
		AND mk.room_type_id = ooo.room_type_id
        
	LEFT JOIN inventory inv 
	    --ON  mk.report_date   = ed.report_date
		ON inv.company_id = mk.company_id 
		and inv.hi_room_type_id = mk.room_type_id
	
)

SELECT
    fr.report_date,
	fr.room_type_name,
	fr.total_rooms,
	fr.out_of_order_rooms,
	fr.available_rooms,
	
	SUM(fr.in_house_count) AS in_house,
    SUM(fr.in_house_adults) AS in_house_adult_count,
    SUM(fr.in_house_children) AS in_house_child_count,
    SUM(fr.in_house_infants) AS in_house_infant_count,
--     SUM(fr.in_house_total) AS in_house_total,
	
	SUM(fr.expected_arrivals) AS expected_arrivals,
    SUM(fr.expected_arrivals_adults) AS expected_arrivals_adult_count,
    SUM(fr.expected_arrivals_children) AS expected_arrivals_child_count,
    SUM(fr.expected_arrivals_infants) AS expected_arrivals_infant_count,
--     SUM(fr.expected_arrivals_total) AS expected_arrivals_total,
	
	SUM(fr.expected_departures) AS expected_departures,
    SUM(fr.expected_departures_adults) AS expected_departures_adult_count,
    SUM(fr.expected_departures_children) AS expected_departures_child_count,
    SUM(fr.expected_departures_infants) AS expected_departures_infant_count,
--     SUM(fr.expected_departures_total) AS expected_departures_total,
	
	SUM(fr.expected_in_house) AS expected_in_house,
    SUM(fr.expected_in_house_adults) AS expected_in_house_adult_count,
    SUM(fr.expected_in_house_children) AS expected_in_house_child_count,
    SUM(fr.expected_in_house_infants) AS expected_in_house_infant_count,
--     SUM(fr.expected_in_house_adults + fr.expected_in_house_children + fr.expected_in_house_infants) AS pax_total,
	CASE WHEN  fr.available_rooms >0 THEN
	SUM(fr.expected_in_house) * 100 / fr.available_rooms
	ELSE SUM(0)
	END
	as expected_occupied_rate,
	-- free to sell =  fr.available_rooms - (expected_in_house + expected_arrivals - expected_departues)
	GREATEST(
    0,
    fr.available_rooms 
    - (SUM(fr.expected_in_house) + SUM(fr.expected_arrivals) - SUM(fr.expected_departures))
) AS free_to_sell,

	fr.company_id
-- 	fr.company_name,
	
FROM final_report fr

WHERE fr.company_id IN (SELECT company_id FROM company_ids)  -- ✅ Fix: Apply WHERE condition here
  AND (COALESCE(fr.expected_arrivals, 0) + COALESCE(fr.expected_departures, 0) + COALESCE(fr.in_house_count, 0)) > 0
GROUP BY fr.report_date, fr.company_name, fr.company_id , fr.room_type_name, fr.total_rooms, fr.out_of_order_rooms, fr.available_rooms
ORDER BY fr.report_date, fr.company_id;
        """

        # self.env.cr.execute(query)
        # self.env.cr.execute(query, (from_date, to_date))
        # params = (from_date, to_date, get_company)
        self.env.cr.execute(query)
        # self.env.cr.execute(query, (get_company, get_company, get_company))
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully for Room Forecast. {len(results)} results fetched")

        records_to_create = []

        for result in results:
            try:
                (
                    report_date,
                    room_type_name,
                    total_rooms,
                    out_of_order,
                    available_rooms,
                    in_house,
                    in_house_adult_count,
                    in_house_child_count,
                    in_house_infant_count,
                    expected_arrivals,
                    expected_arrivals_adult_count,
                    expected_arrivals_child_count,
                    expected_arrivals_infant_count,
                    expected_departures,
                    expected_departures_adult_count,
                    expected_departures_child_count,
                    expected_departures_infant_count,  
                    expected_in_house,
                    expected_in_house_adult_count,  
                    expected_in_house_child_count,  
                    expected_in_house_infant_count,  
                    expected_occupied_rate,
                    free_to_sell,
                    company_id
                ) = result

                records_to_create.append({
                    'report_date': report_date,
                    'company_id': company_id,
                    'room_type_name': room_type_name,
                    'total_rooms': total_rooms,
                    'out_of_order': out_of_order,
                    'available_rooms': available_rooms,
                    'expected_arrivals': expected_arrivals,
                    'expected_arrivals_adult_count': expected_arrivals_adult_count,
                    'expected_arrivals_child_count': expected_arrivals_child_count,
                    'expected_arrivals_infant_count': expected_arrivals_infant_count,
                    'expected_departures': expected_departures,
                    'expected_departures_adult_count': expected_departures_adult_count,
                    'expected_departures_child_count': expected_departures_child_count,
                    'expected_departures_infant_count': expected_departures_infant_count,   
                    'in_house': in_house,
                    'in_house_adult_count': in_house_adult_count,
                    'in_house_child_count': in_house_child_count,
                    'in_house_infant_count': in_house_infant_count,
                    'expected_in_house': expected_in_house,
                    'expected_in_house_adult_count': expected_in_house_adult_count,
                    'expected_in_house_child_count': expected_in_house_child_count,
                    'expected_in_house_infant_count': expected_in_house_infant_count,
                    'free_to_sell': free_to_sell,
                    # 'expected_occupied_rate': int(int(expected_in_house or 0)/int(available_rooms or 1) * 100),
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
 