from odoo import models, fields, api
import logging
import datetime

_logger = logging.getLogger(__name__)

class RoomsForecastReport(models.Model):
    _name = 'rooms.forecast.report'
    _description = 'Rooms Forecast Report'

    
    company_id = fields.Many2one('res.company', string='Company', required=True)
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

    def run_process_by_rooms_forecast(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_rooms_forecast")

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
    SELECT p.from_date + (n || ' day')::interval AS report_date
    FROM parameters p, generate_series(0, (p.to_date - p.from_date)) n
),

system_date_company AS (
	select id as company_id 
	, system_date::date	from res_company rc where  rc.id = (SELECT company_id FROM parameters)
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
           rb.infant_count
    FROM room_booking_line rbl
    JOIN room_booking rb ON rb.id = rbl.booking_id
    JOIN hotel_room hr ON hr.id = rbl.room_id
    JOIN room_type rt ON rt.id = hr.room_type_name
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
           AND rbls.change_time::date <= CURRENT_DATE
    CROSS JOIN date_series ds
    WHERE ds.report_date BETWEEN rb.checkin_date AND rb.checkout_date
    ORDER BY rbl.id, ds.report_date, rbls.change_time DESC NULLS LAST
),

in_house AS (
    SELECT
        report_date,
        company_id,
        room_type_id,
        COUNT(DISTINCT booking_line_id) AS in_house_count,
        SUM(adult_count) AS in_house_adult_count,
        SUM(child_count) AS in_house_child_count,
        SUM(infant_count) AS in_house_infant_count
    FROM latest_line_status
    WHERE final_status = 'check_in'
    GROUP BY report_date, company_id, room_type_id
),

expected_arrivals AS (
    SELECT
        checkin_date AS report_date,
        company_id,
        room_type_id,
        COUNT(DISTINCT booking_line_id) AS expected_arrivals_count,
        SUM(adult_count) AS expected_arrivals_adult_count,
        SUM(child_count) AS expected_arrivals_child_count,
        SUM(infant_count) AS expected_arrivals_infant_count
    FROM latest_line_status
    WHERE final_status IN ('confirmed', 'block')
    GROUP BY checkin_date, company_id, room_type_id
),

expected_departures AS (
    SELECT
        checkout_date AS report_date,
        company_id,
        room_type_id,
        COUNT(DISTINCT booking_line_id) AS expected_departures_count,
        SUM(adult_count) AS expected_departures_adult_count,
        SUM(child_count) AS expected_departures_child_count,
        SUM(infant_count) AS expected_departures_infant_count
    FROM latest_line_status
    WHERE final_status = 'check_in'
    GROUP BY checkout_date, company_id, room_type_id
),

inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        SUM(COALESCE(hi.total_room_count, 0)) AS total_rooms,
	 SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms,
	BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    GROUP BY hi.company_id, hi.room_type
),

out_of_service AS (
    SELECT
        hr.company_id,
        rt.id AS room_type_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS out_of_service_count
    FROM date_series ds
    JOIN housekeeping_management hm ON hm.out_of_service = TRUE
        AND (hm.repair_ends_by IS NULL OR ds.report_date <= hm.repair_ends_by)
    JOIN hotel_room hr ON hr.id = hm.id
    JOIN room_type rt ON rt.id = hr.room_type_name
    GROUP BY hr.company_id, rt.id, ds.report_date
),

out_of_order AS (
    SELECT
        hr.company_id,
        rt.id AS room_type_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS out_of_order_count
    FROM date_series ds
    JOIN out_of_order_management ooo ON ds.report_date BETWEEN ooo.from_date AND ooo.to_date
    JOIN hotel_room hr ON hr.id = ooo.room_number
    JOIN room_type rt ON rt.id = hr.room_type_name
    GROUP BY hr.company_id, rt.id, ds.report_date
),
rooms_on_hold AS (
    SELECT
        rt.id                  AS room_type_id,
        hr.company_id          AS company_id,
        ds.report_date         AS report_date,
        COUNT(DISTINCT hr.id)  AS rooms_on_hold_count
    FROM date_series ds
    JOIN rooms_on_hold_management_front_desk roh
      ON ds.report_date BETWEEN roh.from_date AND roh.to_date
    JOIN hotel_room hr
      ON hr.id = roh.room_number
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
final_report AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rc.name AS company_name,
        rt.id AS room_type_id,
        COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
        COALESCE(ih.in_house_count, 0) AS in_house,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures,
	 COALESCE(inv.overbooking_allowed, false)    AS overbooking_allowed,
        COALESCE(ih.in_house_adult_count, 0) AS in_house_adult_count,
        COALESCE(ih.in_house_child_count, 0) AS in_house_child_count,
        COALESCE(ih.in_house_infant_count, 0) AS in_house_infant_count,
	COALESCE(inv.overbooking_rooms, 0)          AS overbooking_rooms,
	/* Calculating expected_in_house adult, child, infant counts */
        GREATEST(
            0,
            COALESCE(ih.in_house_adult_count, 0) 
            + COALESCE(ea.expected_arrivals_adult_count, 0) 
            - COALESCE(ed.expected_departures_adult_count, 0)
        ) AS expected_in_house_adult_count,

        GREATEST(
            0,
            COALESCE(ih.in_house_child_count, 0) 
            + COALESCE(ea.expected_arrivals_child_count, 0) 
            - COALESCE(ed.expected_departures_child_count, 0)
        ) AS expected_in_house_child_count,

        GREATEST(
            0,
            COALESCE(ih.in_house_infant_count, 0) 
            + COALESCE(ea.expected_arrivals_infant_count, 0) 
            - COALESCE(ed.expected_departures_infant_count, 0)
        ) AS expected_in_house_infant_count,
        COALESCE(ea.expected_arrivals_adult_count, 0) AS expected_arrivals_adult_count,
        COALESCE(ea.expected_arrivals_child_count, 0) AS expected_arrivals_child_count,
        COALESCE(ea.expected_arrivals_infant_count, 0) AS expected_arrivals_infant_count,
        COALESCE(ed.expected_departures_adult_count, 0) AS expected_departures_adult_count,
        COALESCE(ed.expected_departures_child_count, 0) AS expected_departures_child_count,
        COALESCE(ed.expected_departures_infant_count, 0) AS expected_departures_infant_count,
        COALESCE(inv.total_rooms, 0) AS total_rooms,
        COALESCE(oos.out_of_service_count, 0) AS out_of_service,
        COALESCE(ooo.out_of_order_count, 0) AS out_of_order,
        GREATEST(0, 
      -- Use ih.in_house_count when system_date is today, otherwise use yh.in_house_count
      COALESCE(
          CASE 
              WHEN sdc.system_date = ds.report_date THEN ih.in_house_count 
              ELSE ih.in_house_count 
          END, 0
      ) 
      + COALESCE(ea.expected_arrivals_count, 0)
      - LEAST(COALESCE(ed.expected_departures_count, 0), 
              COALESCE(
                  CASE 
                      WHEN sdc.system_date = ds.report_date THEN ih.in_house_count 
                      ELSE ih.in_house_count 
                  END, 0
              )
      )
    ) AS expected_in_house,
	/* available_rooms = total_rooms - (out_of_order + rooms_on_hold) */
        ( COALESCE(inv.total_rooms, 0)
          - COALESCE(ooo.out_of_order_count, 0)
          - COALESCE(roh.rooms_on_hold_count, 0)
        ) AS available_rooms
    FROM date_series ds
--     CROSS JOIN res_company rc
	LEFT JOIN res_company rc ON rc.id = (SELECT company_id FROM parameters)
    CROSS JOIN room_type rt
    LEFT JOIN in_house ih ON ih.company_id = rc.id AND ih.room_type_id = rt.id AND ih.report_date = ds.report_date
    LEFT JOIN expected_arrivals ea ON ea.company_id = rc.id AND ea.room_type_id = rt.id AND ea.report_date = ds.report_date
    LEFT JOIN expected_departures ed ON ed.company_id = rc.id AND ed.room_type_id = rt.id AND ed.report_date = ds.report_date
    INNER JOIN inventory inv ON inv.company_id = rc.id AND inv.room_type_id = rt.id
    LEFT JOIN out_of_service oos ON oos.company_id = rc.id AND oos.room_type_id = rt.id AND oos.report_date = ds.report_date
    LEFT JOIN out_of_order ooo ON ooo.company_id = rc.id AND ooo.room_type_id = rt.id AND ooo.report_date = ds.report_date
	LEFT JOIN rooms_on_hold       roh ON roh.company_id   = rc.id
                                    AND roh.room_type_id  = rt.id
                                    AND roh.report_date   = ds.report_date
    LEFT JOIN system_date_company sdc on sdc.company_id = rc.id

)

SELECT
  report_date,
  company_id,
--   company_name,
--   room_type_id,
  room_type_name,
	 SUM(total_rooms) AS total_rooms,
--   SUM(out_of_service) AS out_of_service,
  SUM(out_of_order) AS out_of_order,
  SUM(in_house) AS in_house,
  SUM(expected_arrivals) AS expected_arrivals,
  SUM(expected_departures) AS expected_departures,
  
  SUM(in_house_adult_count) AS in_house_adult_count,
  SUM(in_house_child_count) AS in_house_child_count,
  SUM(in_house_infant_count) AS in_house_infant_count,
  
  SUM(expected_arrivals_adult_count) AS expected_arrivals_adult_count,
  SUM(expected_arrivals_child_count) AS expected_arrivals_child_count,
  SUM(expected_arrivals_infant_count) AS expected_arrivals_infant_count,
  
  SUM(expected_departures_adult_count) AS expected_departures_adult_count,
  SUM(expected_departures_child_count) AS expected_departures_child_count,
  SUM(expected_departures_infant_count) AS expected_departures_infant_count,
  
	SUM(expected_in_house_adult_count)          AS expected_in_house_adult_count,
  SUM(expected_in_house_child_count)          AS expected_in_house_child_count,
  SUM(expected_in_house_infant_count)         AS expected_in_house_infant_count,
  
  SUM(available_rooms) AS available_rooms,
  SUM(expected_in_house) AS expected_in_house,
  GREATEST(
    0,
    CASE WHEN BOOL_OR(overbooking_allowed) THEN
      ( SUM(available_rooms)
        + SUM(overbooking_rooms)
        - SUM(expected_in_house)
      )
    ELSE
      ( SUM(available_rooms)
        - SUM(expected_in_house)
      )
    END
  ) AS free_to_sell,

-- Expected Occupied Rate Calculation
ROUND(
    (COALESCE(SUM(expected_in_house), 0)::numeric / 
    NULLIF(COALESCE(SUM(available_rooms), 0), 0)::numeric * 100), 
    2
) AS expected_occupied_rate

  
 
FROM final_report
GROUP BY report_date, company_id, company_name, room_type_id, room_type_name
ORDER BY report_date, company_name, room_type_name;
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
                    total_rooms,
                    out_of_order,
                    in_house,
                    expected_arrivals,
                    expected_departures,
                    in_house_adult_count,
                    in_house_child_count,
                    in_house_infant_count,
                    expected_arrivals_adult_count,
                    expected_arrivals_child_count,
                    expected_arrivals_infant_count,
                    expected_departures_adult_count,
                    expected_departures_child_count,
                    expected_departures_infant_count,  
                    expected_in_house_adult_count,  
                    expected_in_house_child_count,  
                    expected_in_house_infant_count,  
                    available_rooms,
                    expected_in_house,
                    free_to_sell,
                    expected_occupied_rate
                ) = result

                records_to_create.append({
                    'report_date': report_date,
                    'company_id': company_id,
                    'room_type_name': room_type_name,
                    'total_rooms': total_rooms,
                    'out_of_order': out_of_order,
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
                    'available_rooms': available_rooms,
                    'free_to_sell': free_to_sell,
                    'expected_occupied_rate': int(int(expected_in_house or 0)/int(available_rooms or 1) * 100),
                })

            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
        else:
            _logger.info("No records to create")
 