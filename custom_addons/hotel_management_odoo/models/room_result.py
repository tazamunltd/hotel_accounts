from odoo import models, fields, api
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class HotelRoomResult(models.Model):
    _name = 'hotel.room.result'
    _description = 'Hotel Room Result'

    # Fields definition
    report_date = fields.Date(string='Report Date', required=True)
    room_type = fields.Char(string='Room Type', required=True)
    company_id = fields.Many2one('res.company',string='company', required = True)
    total_rooms = fields.Integer(string='Total Rooms', readonly=True)
    available = fields.Integer(string='Available', readonly=True)
    inhouse = fields.Integer(string='In-House', readonly=True)
    expected_arrivals = fields.Integer(string='Exp.Arrivals', readonly=True)
    expected_departures = fields.Integer(string='Exp.Departures', readonly=True)
    expected_inhouse = fields.Integer(string='Exp.In House', readonly=True)
    reserved = fields.Integer(string='Reserved', readonly=True)
    expected_occupied_rate = fields.Integer(string='Exp.Occupied Rate (%)', readonly=True)
    out_of_order = fields.Integer(string='Out of Order', readonly=True)
    overbook = fields.Integer(string='Overbook', readonly=True)
    free_to_sell = fields.Integer(string='Free to sell', readonly=True)
    sort_order = fields.Integer(string='Sort Order', readonly=True)
    house_use_count = fields.Integer(string='House Use Count', readonly=True)
    complementary_use_count = fields.Integer(string='Complementar Use Count', readonly=True)
    any_overbooking_allowed = fields.Boolean(string='Any Overbooking Allowed', readonly=True)
    total_overbooking_rooms = fields.Integer(string='total_overbooking_rooms' ,readonly=True)
    rooms_on_hold = fields.Integer(string='Rooms On Hold', readonly=True)
    out_of_service = fields.Integer(string='Out of Service', readonly=True)
    # in_progress = fields.Integer(string='In Progress', readonly=True)
    # dirty_rooms = fields.Integer(string='Dirty Rooms', readonly=True)

    @api.model
    def action_generate_results(self):
        """Generate and update room results."""
        try:
            _logger.info("Generating room results")
            self.run_process_room_availability()
        except Exception as e:
            _logger.error(f"Error generating room results: {str(e)}")
            raise ValueError(f"Error generating room results: {str(e)}")

    def run_process_room_availability(self):
        """Execute the SQL query and process the results."""
        _logger.info("Starting run_process")

        # Clear existing records
        self.env.cr.execute("DELETE FROM hotel_room_result")
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

        records_to_create = []

        for row in results:
            # row is a tuple with indexes 0..19
            try:
                # Check if the company_id is present and matches the current company
                if row[1]:  # Assuming row[1] is the company_id
                    company_id = row[1]
                    # if company_id != self.env.company.id:
                    if company_id not in  self.env.context.get('allowed_company_ids'):
                        continue
                else:
                    continue

                report_date              = row[0]
                company_id               = row[1]
                company_name             = row[2]    # (not used directly, but available)
                room_type_id             = row[3]    # (not used directly, but available)
                room_type_name           = row[4]    # char/string like 'QUAD'
                total_rooms              = row[5]
                any_overbooking_allowed  = row[6]
                total_overbooking_rooms  = row[7]
                out_of_order             = row[8]
                rooms_on_hold            = row[9]
                out_of_service           = row[10]
                in_house                 = row[11]
                expected_arrivals        = row[12]
                expected_departures      = row[13]
                house_use_count          = row[14]
                complementary_use_count  = row[15]
                available_rooms          = row[16]
                expected_in_house        = row[17]
                free_to_sell             = row[18]
                over_booked              = row[19]

                # Only create records if there's a valid company_id or date, etc.
                if company_id and report_date:
                    records_to_create.append({
                        'report_date': report_date,
                        'company_id': company_id,
                        'room_type': room_type_name,  # This is a Char field
                        
                        'total_rooms': int(total_rooms or 0),
                        'any_overbooking_allowed': bool(any_overbooking_allowed),
                        'total_overbooking_rooms': int(total_overbooking_rooms or 0),
                        
                        'out_of_order': int(out_of_order or 0),
                        'rooms_on_hold': int(rooms_on_hold or 0),
                        'out_of_service': int(out_of_service or 0),
                        
                        'inhouse': int(in_house or 0),
                        'expected_arrivals': int(expected_arrivals or 0),
                        'expected_departures': int(expected_departures or 0),
                        'house_use_count': int(house_use_count or 0),
                        'complementary_use_count': int(complementary_use_count or 0),
                        'expected_occupied_rate': int(int(expected_in_house or 0)/int(available_rooms or 1) * 100),
                        'available': int(available_rooms or 0),
                        'expected_inhouse': int(expected_in_house or 0),
                        'free_to_sell': int(free_to_sell or 0),
                        
                        # 'reserved' was not actually returned by this query,
                        # so either remove it or set it to 0
                        'reserved': 0,
                        
                        'overbook': int(over_booked or 0),
                    })
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {row}")
                continue

        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")

        _logger.info("Completed run_process_room_availability")

        return

    def debug_room_results(self, company_id=None, report_date=None):
        """
        Comprehensive diagnostic method to print out room result records.
        
        :param company_id: Optional company ID to filter results
        :param report_date: Optional report date to filter results
        :return: Detailed debug information
        """
        domain = []
        if company_id:
            domain.append(('company_id', '=', company_id))
        if report_date:
            domain.append(('report_date', '=', report_date))
        
        results = self.search(domain)
        
        _logger.info("Debug Room Results - Search Parameters:")
        _logger.info("Company ID Filter: %s", company_id)
        _logger.info("Report Date Filter: %s", report_date)
        _logger.info("Total Matching Records: %s", len(results))
        
        for record in results:
            _logger.info("Detailed Record:")
            _logger.info("- Record ID: %s", record.id)
            _logger.info("- Company: %s (ID: %s)", record.company_id.name, record.company_id.id)
            _logger.info("- Report Date: %s", record.report_date)
            _logger.info("- Room Type: %s", record.room_type)
            _logger.info("- Expected Arrivals: %s", record.expected_arrivals)
            _logger.info("- Total Rooms: %s", record.total_rooms)
            _logger.info("- Available Rooms: %s", record.available)
            _logger.info("- In-House: %s", record.inhouse)
            _logger.info("-------------------")
        
        return {
            'total_records': len(results),
            'records_details': [
                {
                    'id': r.id,
                    'company_name': r.company_id.name,
                    'company_id': r.company_id.id,
                    'report_date': str(r.report_date),
                    'expected_arrivals': r.expected_arrivals
                } for r in results
            ]
        }

    @api.model
    def get_expected_arrivals_for_dashboard(self, company_id, report_date):
        """
        Retrieve sum of expected arrivals for different room types for a specific date and company.
        
        :param company_id: Company ID to filter records
        :param report_date: Date for which expected arrivals are to be calculated
        :return: Sum of expected arrivals across all room types or 0
        
        Modification Date: 2025-01-12
        Modification Time: 21:47:58
        """
        try:
            # Search for all records matching company and date
            records = self.search([
                ('company_id', '=', company_id),
                ('report_date', '=', report_date)
            ])
            
            if records:
                # Sum the expected quantities across all matching records
                total_expected_arrivals = sum(record.expected_arrivals for record in records)
                return total_expected_arrivals
            else:
                _logger.warning("No records found for given company and date")
                return 0
        except Exception as e:
            _logger.error("Error retrieving expected arrivals: %s", str(e))
            return 0

    @api.model
    def get_dashboard_room_metrics(self, company_id, report_date):
        """
        Retrieve aggregated dashboard metrics for rooms for a specific date and company.
        
        :param company_id: Company ID to filter records
        :param report_date: Date for which room metrics are to be calculated
        :return: Dictionary of aggregated room metrics
        
        Modification Date: 2025-01-12
        Modification Time: 22:40:00
        """
        try:
            # Search for all records matching company and date
            records = self.search([
                ('company_id', '=', company_id),
                ('report_date', '=', report_date)
            ])
            
            _logger.info(f"Found {len(records)} records for company {company_id} on {report_date}")
            
            if not records:
                _logger.warning("No records found for given company and date")
                return {
                    'out_of_order': 0,
                    'rooms_on_hold': 0,
                    'out_of_service': 0,
                    'inhouse': 0,
                    'expected_arrivals': 0,
                    'expected_departures': 0,
                    'house_use_count': 0,
                    'complementary_use_count': 0,
                    'expected_occupied_rate': 0,
                    'available': 0,
                    'expected_inhouse': 0,
                    'free_to_sell': 0,
                    'total_rooms': 0
                }
            
            # Detailed logging for each record
            _logger.info("Record Details:")
            for record in records:
                _logger.info(f"Room Type: {record.room_type}, "
                             f"In-House: {record.inhouse}, "
                             f"Available: {record.available}, "
                             f"Expected In-House: {record.expected_inhouse}")
            
            # Calculate aggregated metrics
            metrics = {
                'out_of_order': sum(record.out_of_order for record in records),
                'rooms_on_hold': sum(record.rooms_on_hold for record in records),
                'out_of_service': sum(record.out_of_service for record in records),
                'inhouse': sum(record.inhouse for record in records),
                'expected_arrivals': sum(record.expected_arrivals for record in records),
                'expected_departures': sum(record.expected_departures for record in records),
                'house_use_count': sum(record.house_use_count for record in records),
                'complementary_use_count': sum(record.complementary_use_count for record in records),
                'available': sum(record.available for record in records),
                'expected_inhouse': sum(record.expected_inhouse for record in records),
                'free_to_sell': sum(record.free_to_sell for record in records),
                'total_rooms': sum(record.total_rooms for record in records)
            }
            
            # Log the final metrics
            _logger.info(f"Aggregated Metrics: {metrics}")
            
            # Calculate expected occupied rate
            total_available_rooms = metrics['available'] or 1
            metrics['expected_occupied_rate'] = int((metrics['expected_inhouse'] / total_available_rooms) * 100)
            
            return metrics
        
        except Exception as e:
            _logger.error(f"Error retrieving dashboard room metrics: {str(e)}")
            return {
                'out_of_order': 0,
                'rooms_on_hold': 0,
                'out_of_service': 0,
                'inhouse': 0,
                'expected_arrivals': 0,
                'expected_departures': 0,
                'house_use_count': 0,
                'complementary_use_count': 0,
                'expected_occupied_rate': 0,
                'available': 0,
                'expected_inhouse': 0,
                'free_to_sell': 0,
                'total_rooms': 0
            }

    @api.model
    def get_occupancy_history(self, company_id, days=7):
        """
        Get occupancy rate history for the last N days.
        
        Args:
            company_id (int): ID of the company
            days (int): Number of days of history to fetch (default: 7)
            
        Returns:
            dict: Dictionary containing dates and corresponding occupancy rates
        """
        try:
            end_date = fields.Date.today()
            start_date = end_date - timedelta(days=days)
            
            domain = [
                ('company_id', '=', company_id),
                ('report_date', '>=', start_date),
                ('report_date', '<=', end_date)
            ]
            
            results = self.search(domain, order='report_date asc')
            
            # Group results by date and calculate average occupancy rate
            dates = []
            rates = []
            
            for date in (start_date + timedelta(n) for n in range(days + 1)):
                day_results = results.filtered(lambda r: r.report_date == date)
                
                if day_results:
                    total_rooms = sum(day_results.mapped('total_rooms'))
                    occupied_rooms = sum(day_results.mapped('inhouse'))
                    
                    # Calculate occupancy rate
                    rate = round((occupied_rooms / total_rooms * 100) if total_rooms else 0, 2)
                    
                    dates.append(date.strftime('%Y-%m-%d'))
                    rates.append(rate)
            
            return {
                'dates': dates,
                'rates': rates
            }
            
        except Exception as e:
            _logger.error(f"Error fetching occupancy history: {str(e)}")
            return {
                'dates': [],
                'rates': []
            }

    @api.model
    def get_arrivals_departures_history(self, company_id, days=7):
        """
        Get arrivals and departures history for the last N days.
        
        Args:
            company_id (int): ID of the company
            days (int): Number of days of history to fetch (default: 7)
            
        Returns:
            dict: Dictionary containing dates, arrivals, and departures lists
        """
        try:
            end_date = fields.Date.today()
            start_date = end_date - timedelta(days=days)
            
            domain = [
                ('company_id', '=', company_id),
                ('report_date', '>=', start_date),
                ('report_date', '<=', end_date)
            ]
            
            results = self.search(domain, order='report_date asc')
            
            dates = []
            arrivals = []
            departures = []
            
            for date in (start_date + timedelta(n) for n in range(days + 1)):
                day_results = results.filtered(lambda r: r.report_date == date)
                
                dates.append(date.strftime('%Y-%m-%d'))
                arrivals.append(sum(day_results.mapped('expected_arrivals')))
                departures.append(sum(day_results.mapped('expected_departures')))
            
            return {
                'dates': dates,
                'arrivals': arrivals,
                'departures': departures
            }
            
        except Exception as e:
            _logger.error(f"Error fetching arrivals vs departures history: {str(e)}")
            return {
                'dates': [],
                'arrivals': [],
                'departures': []
            }

    @api.model
    def get_room_type_distribution(self, company_id):
        """
        Get room distribution by room type.
        
        Args:
            company_id (int): ID of the company
            
        Returns:
            dict: Dictionary containing room types and their counts
        """
        try:
            today = fields.Date.today()
            domain = [
                ('company_id', '=', company_id),
                ('report_date', '=', today)
            ]
            
            results = self.search(domain)
            room_types = []
            counts = []
            
            for result in results:
                if result.room_type not in room_types:
                    room_types.append(result.room_type)
                    counts.append(result.total_rooms)
            
            return {
                'types': room_types,
                'counts': counts
            }
            
        except Exception as e:
            _logger.error(f"Error fetching room type distribution: {str(e)}")
            return {
                'types': [],
                'counts': []
            }

    @api.model
    def get_room_status_by_type(self, company_id):
        """
        Get room status breakdown by room type.
        
        Args:
            company_id (int): ID of the company
            
        Returns:
            dict: Dictionary containing room types and their status counts
        """
        try:
            today = fields.Date.today()
            domain = [
                ('company_id', '=', company_id),
                ('report_date', '=', today)
            ]
            
            results = self.search(domain)
            types = []
            available = []
            occupied = []
            reserved = []
            out_of_order = []
            
            for result in results:
                types.append(result.room_type)
                available.append(result.available)
                occupied.append(result.inhouse)
                reserved.append(result.reserved)
                out_of_order.append(result.out_of_order)
            
            return {
                'types': types,
                'available': available,
                'occupied': occupied,
                'reserved': reserved,
                'outOfOrder': out_of_order
            }
            
        except Exception as e:
            _logger.error(f"Error fetching room status by type: {str(e)}")
            return {
                'types': [],
                'available': [],
                'occupied': [],
                'reserved': [],
                'outOfOrder': []
            }

    @api.model
    def get_availability_timeline(self, company_id, days=30):
        """
        Get room availability timeline for the next N days.
        
        Args:
            company_id (int): ID of the company
            days (int): Number of days to look ahead (default: 30)
            
        Returns:
            dict: Dictionary containing dates, available rooms, and total rooms
        """
        try:
            start_date = fields.Date.today()
            end_date = start_date + timedelta(days=days)
            
            domain = [
                ('company_id', '=', company_id),
                ('report_date', '>=', start_date),
                ('report_date', '<=', end_date)
            ]
            
            results = self.search(domain, order='report_date asc')
            
            dates = []
            available = []
            total = []
            
            for date in (start_date + timedelta(n) for n in range(days + 1)):
                day_results = results.filtered(lambda r: r.report_date == date)
                
                dates.append(date.strftime('%Y-%m-%d'))
                available.append(sum(day_results.mapped('available')))
                total.append(sum(day_results.mapped('total_rooms')))
            
            return {
                'dates': dates,
                'available': available,
                'total': total
            }
            
        except Exception as e:
            _logger.error(f"Error fetching availability timeline: {str(e)}")
            return {
                'dates': [],
                'available': [],
                'total': []
            }