from odoo import models, fields, api
import logging
import sys

sys.setrecursionlimit(1000)

_logger = logging.getLogger(__name__)


class RoomResultByRoomType(models.Model):
    _name = 'room.result.by.room.type'
    _description = 'Room Result by Room Type'

    report_date = fields.Date(string='Report Date', required=True)
    room_type = fields.Char(string='Room Type', required=True)
    company_id = fields.Many2one('res.company',string='company', required = True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True)
    available = fields.Integer(string='Available', readonly=True)
    inhouse = fields.Integer(string='In-House', readonly=True)
    expected_arrivals = fields.Integer(string='Exp.Arrivals', readonly=True)
    expected_departures = fields.Integer(string='Exp.Departures', readonly=True)
    expected_inhouse = fields.Integer(string='Exp.Inhouse', readonly=True)
    reserved = fields.Integer(string='Reserved', readonly=True)
    expected_occupied_rate = fields.Integer(string='Exp.Occupied Rate (%)', readonly=True)
    out_of_order = fields.Integer(string='Out of Order', readonly=True)
    overbook = fields.Integer(string='Overbook', readonly=True)
    free_to_sell = fields.Integer(string='Free to sell', readonly=True)
    sort_order = fields.Integer(string='Sort Order', readonly=True)

    @api.model
    def action_generate_results(self):
        """Generate and update room results by client."""
        print("line 34")
        try:
            # Call the run_process method to execute the query and process results
            self.run_process_by_room_type()

        except Exception as e:
            _logger.error(f"Error generating room results: {str(e)}")
            raise ValueError(f"Error generating room results: {str(e)}")

    def run_process_by_room_type(self):
        """Execute the SQL query and process the results."""
        _logger.info("Started run_process_by_room_type")
        # SQL Query (modified)
        self.env.cr.execute("DELETE FROM room_result_by_room_type")
        _logger.info("Existing records deleted")
        print("line 47")
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
   1) LATEST_LINE_STATUS:
   For each (booking_line + report_date), find the latest status 
   as of that day (DISTINCT ON plus descending change_time).
   We also pull in:
     - rb.house_use (boolean)
     - rb.complementary (boolean)
   so we can filter them in separate CTEs (house_use_cte, complementary_use_cte).
   ---------------------------------------------------------------------------- */
latest_line_status AS (
    SELECT DISTINCT ON (rbl.id, ds.report_date)
           rbl.id AS booking_line_id,
           ds.report_date,
           rb.checkin_date::date   AS checkin_date,
           rb.checkout_date::date  AS checkout_date,
           hr.company_id,
           rt.id                   AS room_type_id,
           rbls.status             AS final_status,
           rbls.change_time,
           rb.house_use            AS house_use,
           rb.complementary        AS complementary
    FROM room_booking_line rbl
    CROSS JOIN date_series ds
    JOIN room_booking rb    ON rb.id = rbl.booking_id
    JOIN hotel_room hr      ON hr.id = rbl.room_id
    JOIN room_type rt       ON rt.id = hr.room_type_name
    LEFT JOIN room_booking_line_status rbls
           ON rbls.booking_line_id = rbl.id
           AND rbls.change_time::date <= ds.report_date
    ORDER BY
       rbl.id,
       ds.report_date,
       rbls.change_time DESC NULLS LAST
),

/* ----------------------------------------------------------------------------
   2) IN-HOUSE:
   Lines in final_status='check_in' with date in [checkin_date,checkout_date).
   ---------------------------------------------------------------------------- */
in_house AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        COUNT(DISTINCT sub.booking_line_number) AS in_house_count
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type   rt

    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number
        FROM (
            SELECT 
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rbl.checkin_date,
                rbl.checkout_date,
                rbl.id              AS booking_line_number,
                rbls.status,
                rbls.change_time
            FROM room_booking rb
            JOIN room_booking_line rbl
                  ON rbl.booking_id = rb.id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
        ) AS qry
        WHERE qry.company_id     = rc.id
          AND qry.room_type_id   = rt.id

          /* Lines that physically cover ds.report_date: [checkin_date, checkout_date) */
          AND qry.checkin_date::date <= ds.report_date
          AND qry.checkout_date::date > ds.report_date

          /* Must have had status='check_in' as of or before ds.report_date */
          AND qry.status = 'check_in'
          AND qry.change_time::date <= ds.report_date

        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE

    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id
),

/* ----------------------------------------------------------------------------
   3) EXPECTED ARRIVALS:
   Lines that arrive on this date => checkin_date = report_date,
   final_status in ('confirmed','block').
   ---------------------------------------------------------------------------- */
expected_arrivals AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        /* 
           Count how many DISTINCT booking lines 
           match 'confirmed' or 'block' for that day.
        */
        COUNT(DISTINCT sub.booking_line_number) AS expected_arrivals_count
    FROM date_series ds
    /* 
       Adjust these CROSS JOINs to however you want to 
       iterate over each company & room type.
    */
    CROSS JOIN res_company rc
    CROSS JOIN room_type   rt

    /*
       LATERAL sub‐query: Reuse your “distinct on” query, 
       but parameterize the date based on ds.report_date.
    */
    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number
        FROM (
            SELECT 
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rbl.checkin_date    AS checkin_dt,
                rb.name,
                rbls.status,
                rbl.id              AS booking_line_number,
                rbls.change_time
            FROM room_booking rb
            JOIN room_booking_line rbl 
                  ON rbl.booking_id = rb.id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
        ) AS qry
        WHERE qry.company_id    = rc.id
          AND qry.room_type_id  = rt.id
          AND qry.status        IN ('confirmed','block')
          /* 
             Use ds.report_date in place of your old '2025-01-15'.
          */
          AND qry.change_time::date <= ds.report_date
          AND qry.checkin_dt::date   = ds.report_date

        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE
	GROUP BY ds.report_date, rc.id, rt.id
),

/* ----------------------------------------------------------------------------
   4) EXPECTED DEPARTURES:
   Lines that depart on this date => checkout_date = report_date,
   final_status = 'check_in'.
   ---------------------------------------------------------------------------- */
expected_departures AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rt.id AS room_type_id,
        COUNT(DISTINCT sub.booking_line_number) AS expected_departures_count
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type   rt

    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (qry.booking_line_number)
               qry.booking_line_number
        FROM (
            SELECT 
                rb.company_id,
                rbl.hotel_room_type AS room_type_id,
                rbl.checkin_date,
                rbl.checkout_date,
                rbl.id              AS booking_line_number,
                rbls.status,
                rbls.change_time
            FROM room_booking rb
            JOIN room_booking_line rbl
                  ON rbl.booking_id = rb.id
            JOIN room_booking_line_status rbls
                  ON rbls.booking_line_id = rbl.id
        ) AS qry
        WHERE qry.company_id    = rc.id
          AND qry.room_type_id  = rt.id

          /* Depart on ds.report_date */
          AND qry.checkout_date::date = ds.report_date

          /* Must have had status='check_in' by ds.report_date */
          AND qry.status = 'check_in'
          AND qry.change_time::date <= ds.report_date

        ORDER BY qry.booking_line_number, qry.change_time DESC
    ) AS sub ON TRUE

    GROUP BY 
        ds.report_date,
        rc.id,
        rt.id
),

/* ----------------------------------------------------------------------------
   5) HOUSE USE:
   Lines in final_status='check_in', date in [checkin_date,checkout_date),
   and house_use = TRUE.
   ---------------------------------------------------------------------------- */
house_use_cte AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS house_use_count
    FROM latest_line_status lls
    WHERE lls.house_use = TRUE
      AND lls.final_status = 'check_in'
      AND lls.checkin_date <= lls.report_date
      AND lls.checkout_date > lls.report_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),

/* ----------------------------------------------------------------------------
   6) COMPLEMENTARY USE:
   Lines in final_status='check_in', date in [checkin_date,checkout_date),
   and complementary = TRUE.
   ---------------------------------------------------------------------------- */
complementary_use_cte AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS complementary_use_count
    FROM latest_line_status lls
    WHERE lls.complementary = TRUE
      AND lls.final_status = 'check_in'
      AND lls.checkin_date <= lls.report_date
      AND lls.checkout_date > lls.report_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),

/* ----------------------------------------------------------------------------
   7) INVENTORY (with Overbooking):
   Aggregated by (company_id, room_type).
   ---------------------------------------------------------------------------- */
inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        SUM(COALESCE(hi.total_room_count, 0)) AS total_room_count,
        SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms,
        BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    GROUP BY hi.company_id, hi.room_type
),

/* ----------------------------------------------------------------------------
   8) OUT_OF_ORDER, ROOMS_ON_HOLD, OUT_OF_SERVICE
   ---------------------------------------------------------------------------- */
out_of_order AS (
    SELECT
        rt.id                  AS room_type_id,
        hr.company_id          AS company_id,
        ds.report_date         AS report_date,
        COUNT(DISTINCT hr.id)  AS out_of_order_count
    FROM date_series ds
    JOIN out_of_order_management_fron_desk ooo
      ON ds.report_date BETWEEN ooo.from_date AND ooo.to_date
    JOIN hotel_room hr
      ON hr.id = ooo.room_number
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
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
out_of_service AS (
    SELECT
        rt.id                  AS room_type_id,
        hr.company_id          AS company_id,
        ds.report_date         AS report_date,
        COUNT(DISTINCT hr.id)  AS out_of_service_count
    FROM date_series ds
    JOIN housekeeping_management hm
      ON hm.out_of_service = TRUE
      AND (hm.repair_ends_by IS NULL OR ds.report_date <= hm.repair_ends_by)
    JOIN hotel_room hr
      ON hr.room_type_name = hm.room_type
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),

/* ----------------------------------------------------------------------------
   9) FINAL_REPORT:
   Cross-join (date, company, room_type) => 1 row per combination,
   then LEFT JOIN each aggregated CTE.
   ---------------------------------------------------------------------------- */
final_report AS (
    SELECT
        ds.report_date,
        rc.id                    AS company_id,
        rc.name                  AS company_name,
        rt.id                    AS room_type_id,
        --rt.room_type             AS room_type_name,
		    COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
        COALESCE(inv.total_room_count, 0)           AS total_rooms,
        COALESCE(inv.overbooking_rooms, 0)          AS overbooking_rooms,
        COALESCE(inv.overbooking_allowed, false)    AS overbooking_allowed,

        COALESCE(ooo.out_of_order_count, 0)         AS out_of_order,
        COALESCE(roh.rooms_on_hold_count, 0)        AS rooms_on_hold,
        COALESCE(oos.out_of_service_count, 0)       AS out_of_service,

        COALESCE(ih.in_house_count, 0)              AS in_house,
        COALESCE(ea.expected_arrivals_count, 0)     AS expected_arrivals,
        COALESCE(ed.expected_departures_count, 0)   AS expected_departures,

        COALESCE(hc.house_use_count, 0)             AS house_use_count,
        COALESCE(cc.complementary_use_count, 0)     AS complementary_use_count,

        /* available_rooms = total_rooms - (out_of_order + rooms_on_hold) */
        ( COALESCE(inv.total_room_count, 0)
          - COALESCE(ooo.out_of_order_count, 0)
          - COALESCE(roh.rooms_on_hold_count, 0)
        ) AS available_rooms,

        /* expected_in_house = in_house + arrivals - departures */
        ( COALESCE(ih.in_house_count, 0)
          + COALESCE(ea.expected_arrivals_count, 0)
          - COALESCE(ed.expected_departures_count, 0)
        ) AS expected_in_house
    FROM date_series ds
    CROSS JOIN res_company rc
    CROSS JOIN room_type rt

    LEFT JOIN inventory           inv ON inv.company_id   = rc.id
                                    AND inv.room_type_id = rt.id

    LEFT JOIN out_of_order        ooo ON ooo.company_id   = rc.id
                                    AND ooo.room_type_id  = rt.id
                                    AND ooo.report_date   = ds.report_date

    LEFT JOIN rooms_on_hold       roh ON roh.company_id   = rc.id
                                    AND roh.room_type_id  = rt.id
                                    AND roh.report_date   = ds.report_date

    LEFT JOIN out_of_service      oos ON oos.company_id   = rc.id
                                    AND oos.room_type_id  = rt.id
                                    AND oos.report_date   = ds.report_date

    LEFT JOIN in_house            ih  ON ih.company_id    = rc.id
                                    AND ih.room_type_id   = rt.id
                                    AND ih.report_date    = ds.report_date

    LEFT JOIN expected_arrivals   ea  ON ea.company_id    = rc.id
                                    AND ea.room_type_id   = rt.id
                                    AND ea.report_date    = ds.report_date

    LEFT JOIN expected_departures ed  ON ed.company_id    = rc.id
                                    AND ed.room_type_id   = rt.id
                                    AND ed.report_date    = ds.report_date

    LEFT JOIN house_use_cte       hc  ON hc.company_id    = rc.id
                                    AND hc.room_type_id   = rt.id
                                    AND hc.report_date    = ds.report_date

    LEFT JOIN complementary_use_cte cc ON cc.company_id   = rc.id
                                    AND cc.room_type_id   = rt.id
                                    AND cc.report_date    = ds.report_date
)

/* ----------------------------------------------------------------------------
   10) GROUP BY + FINAL SELECT:
   We sum up values in case of duplicates, 
   then compute free_to_sell & over_booked with negative clamp (GREATEST(0,...)).
   ---------------------------------------------------------------------------- */
SELECT
  fr.report_date,
  fr.company_id,
  fr.company_name,
  fr.room_type_id,
  fr.room_type_name,

  SUM(fr.total_rooms)                    AS total_rooms,
  BOOL_OR(fr.overbooking_allowed)        AS any_overbooking_allowed,
  SUM(fr.overbooking_rooms)              AS total_overbooking_rooms,

  SUM(fr.out_of_order)                   AS out_of_order,
  SUM(fr.rooms_on_hold)                  AS rooms_on_hold,
  SUM(fr.out_of_service)                 AS out_of_service,

  SUM(fr.in_house)                       AS in_house,
  SUM(fr.expected_arrivals)              AS expected_arrivals,
  SUM(fr.expected_departures)            AS expected_departures,

  /* Summing house_use_count + complementary_use_count if duplicates exist */
  SUM(fr.house_use_count)               AS house_use_count,
  SUM(fr.complementary_use_count)       AS complementary_use_count,

  /* Summation of the derived columns as well */
  SUM(fr.available_rooms)               AS available_rooms,
  SUM(fr.expected_in_house)             AS expected_in_house,

  /* free_to_sell: if overbooking_allowed => (avail + overbook) - expected_in_house, else (avail - expected_in_house) */
  GREATEST(
    0,
    CASE WHEN BOOL_OR(fr.overbooking_allowed) THEN
      ( SUM(fr.available_rooms)
        + SUM(fr.overbooking_rooms)
        - SUM(fr.expected_in_house)
      )
    ELSE
      ( SUM(fr.available_rooms)
        - SUM(fr.expected_in_house)
      )
    END
  ) AS free_to_sell,

  /* over_booked = expected_in_house - available_rooms, then clamp to 0 */
  GREATEST(
    0,
    SUM(fr.expected_in_house) - SUM(fr.available_rooms)
  ) AS over_booked

FROM final_report fr
GROUP BY
  fr.report_date,
  fr.company_id,
  fr.company_name,
  fr.room_type_id,
  fr.room_type_name
ORDER BY
  fr.report_date,
  fr.company_name,
  fr.room_type_name;
           
        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")
        print('line 355 running room type')

        records_to_create = []
        # DEFAULT_COMPANY_ID = 1
        for result in results:
            try:
                if result[1]:
                    
                    company_id = result[1]
                    if company_id != self.env.company.id:
                        continue  
                    # print(result[1])  
                else:
                    continue
                report_date = result[0] if result[0] else False  # fr.report_date
                company_id = result[1] # if result[1] else DEFAULT_COMPANY_ID   fr.company_id
                room_type_id = result[3]  # fr.room_type_id
                room_type_name = result[4]  # fr.room_type_name

                records_to_create.append({
                    'report_date': report_date,            # Date
                    'company_id': company_id,              # Many2one to res.company
                    'room_type': room_type_name,           # Char (or room_type_id if Many2one)
                    'expected_inhouse': int(result[17] or 0), # SUM(fr.expected_departures)
                    # Add other fields here with correct index mapping
                })
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")

        _logger.info("Completed run_process_by_room_type")