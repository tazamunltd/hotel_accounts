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
    expected_arrivals = fields.Integer(string='Expected Arrivals', readonly=True)
    expected_departures = fields.Integer(string='Expected Departures', readonly=True)
    expected_inhouse = fields.Integer(string='Expected In House', readonly=True)
    reserved = fields.Integer(string='Reserved', readonly=True)
    expected_occupied_rate = fields.Integer(string='Expected Occupied Rate (%)', readonly=True)
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
        self.env.cr.execute("DELETE FROM room_result_by_client")
        _logger.info("Existing records deleted")
        print("line 47")
        query = """
            
WITH parameters AS (
    SELECT
        (SELECT MIN(checkin_date::date) FROM room_booking) AS from_date,
        (SELECT MAX(checkout_date::date) FROM room_booking) AS to_date,
        NULL::integer AS selected_room_type
),
date_series AS (
    SELECT generate_series(p.from_date, p.to_date, interval '1 day')::date AS report_date
    FROM parameters p
),
room_types AS (
    SELECT rt.id AS room_type_id,
           rt.room_type,
           rt.description AS room_type_name
    FROM room_type rt
),
line_status_by_day AS (
    SELECT
        ds.report_date,
        rbl.id AS booking_line_id,
        (
            SELECT s.status
            FROM room_booking_line_status s
            WHERE s.booking_line_id = rbl.id
              AND s.change_time::date <= ds.report_date
            ORDER BY s.change_time DESC
            LIMIT 1
        ) AS status
    FROM date_series ds
    JOIN room_booking_line rbl ON rbl.id IS NOT NULL
),
hrb AS (
    SELECT
        ds.report_date,
        rbl.id,
        rb.checkin_date,
        rb.checkout_date,
        lsd.status AS state,
        hr.room_type_name AS room_type_id,
        hr.company_id,
        rc.name AS company_name,
        rb.house_use,
        rb.complementary
    FROM date_series ds
    CROSS JOIN room_types rt
    JOIN room_booking_line rbl ON TRUE
    JOIN room_booking rb ON rb.id = rbl.booking_id
    JOIN hotel_room hr ON rbl.room_id = hr.id
    JOIN res_company rc ON hr.company_id = rc.id
    JOIN line_status_by_day lsd ON lsd.report_date = ds.report_date AND lsd.booking_line_id = rbl.id
    WHERE rb.checkin_date::date <= ds.report_date
      AND rb.checkout_date::date >= ds.report_date
      AND hr.room_type_name = rt.room_type_id
),
in_house AS (
    SELECT
        hrb.report_date,
        hrb.room_type_id,
        hrb.company_id,
        hrb.company_name,
        COUNT(DISTINCT hrb.id) AS in_house
    FROM hrb
    WHERE hrb.state = 'check_in'
    GROUP BY hrb.report_date, hrb.room_type_id, hrb.company_id, hrb.company_name
),
in_house_house_use AS (
    SELECT
        hrb.report_date,
        hrb.room_type_id,
        hrb.company_id,
        hrb.company_name,
        COUNT(DISTINCT hrb.id) AS house_use_in_house
    FROM hrb
    WHERE hrb.state = 'check_in'
      AND hrb.house_use = TRUE
    GROUP BY hrb.report_date, hrb.room_type_id, hrb.company_id, hrb.company_name
),
in_house_complementary AS (
    SELECT
        hrb.report_date,
        hrb.room_type_id,
        hrb.company_id,
        hrb.company_name,
        COUNT(DISTINCT hrb.id) AS complementary_in_house
    FROM hrb
    WHERE hrb.state = 'check_in'
      AND hrb.complementary = TRUE
    GROUP BY hrb.report_date, hrb.room_type_id, hrb.company_id, hrb.company_name
),
expected_arrivals AS (
    SELECT
        hrb.report_date,
        hrb.room_type_id,
        hrb.company_id,
        hrb.company_name,
        COUNT(DISTINCT hrb.id) AS expected_arrivals
    FROM hrb
    WHERE hrb.state IN ('confirmed', 'block')
      AND hrb.checkin_date::date = hrb.report_date
    GROUP BY hrb.report_date, hrb.room_type_id, hrb.company_id, hrb.company_name
),
expected_departures AS (
    SELECT
        hrb.report_date,
        hrb.room_type_id,
        hrb.company_id,
        hrb.company_name,
        COUNT(DISTINCT hrb.id) AS expected_departures
    FROM hrb
    WHERE hrb.state IN ('confirmed', 'block')
      AND hrb.checkout_date::date = hrb.report_date
    GROUP BY hrb.report_date, hrb.room_type_id, hrb.company_id, hrb.company_name
),
actual_departures AS (
    SELECT
        hrb.report_date,
        hrb.room_type_id,
        hrb.company_id,
        hrb.company_name,
        COUNT(DISTINCT hrb.id) AS actual_departures
    FROM hrb
    WHERE hrb.state = 'check_out'
      AND hrb.checkout_date::date = hrb.report_date
    GROUP BY hrb.report_date, hrb.room_type_id, hrb.company_id, hrb.company_name
),
total_rooms AS (
    SELECT
        tr.report_date,
        rt.room_type_id,
        rt.room_type_name,
        hr.company_id,
        rc.name AS company_name,
        COUNT(hr.id) AS total_rooms
    FROM date_series tr
    CROSS JOIN room_types rt
    LEFT JOIN hotel_room hr ON hr.room_type_name = rt.room_type_id
    LEFT JOIN res_company rc ON hr.company_id = rc.id
    GROUP BY tr.report_date, rt.room_type_id, rt.room_type_name, hr.company_id, rc.name
),
out_of_order_rooms AS (
    SELECT
        ds.report_date,
        rt.room_type_id,
        hr.company_id,
        rc.name AS company_name,
        CASE 
            WHEN ds.report_date < CURRENT_DATE THEN 0 
            ELSE COUNT(DISTINCT hr.id) FILTER (
                WHERE ooom.id IS NOT NULL OR roh.id IS NOT NULL
            )
        END AS out_of_order_count
    FROM date_series ds
    CROSS JOIN room_types rt
    LEFT JOIN hotel_room hr ON hr.room_type_name = rt.room_type_id
    LEFT JOIN res_company rc ON hr.company_id = rc.id
    LEFT JOIN out_of_order_management_fron_desk ooom 
        ON ooom.room_number = hr.id
        AND ds.report_date BETWEEN ooom.from_date AND ooom.to_date
    LEFT JOIN rooms_on_hold_management_front_desk roh
        ON roh.room_number = hr.id
        AND ds.report_date BETWEEN roh.from_date AND roh.to_date
    GROUP BY ds.report_date, rt.room_type_id, hr.company_id, rc.name
),
available_rooms AS (
    SELECT
        tr.report_date,
        tr.room_type_id,
        tr.company_id,
        tr.company_name,
        tr.total_rooms - COALESCE(oor.out_of_order_count, 0) AS available_rooms
    FROM total_rooms tr
    LEFT JOIN out_of_order_rooms oor ON tr.report_date = oor.report_date 
        AND tr.room_type_id = oor.room_type_id 
        AND tr.company_id = oor.company_id
),
reserved AS (
    SELECT
        ds.report_date,
        rt.room_type_id,
        hrb.company_id,
        hrb.company_name,
        COUNT(DISTINCT hrb.id) AS reserved_count
    FROM date_series ds
    CROSS JOIN room_types rt
    JOIN hrb ON hrb.checkin_date::date > ds.report_date
              AND hrb.state IN ('confirmed', 'block')
              AND hrb.room_type_id = rt.room_type_id
    GROUP BY ds.report_date, rt.room_type_id, hrb.company_id, hrb.company_name
),
daily_data AS (
    SELECT
        tr.report_date,
        tr.room_type_id,
        tr.company_id,
        tr.company_name,
        COALESCE(ih.in_house, 0) AS in_house,
        COALESCE(ea.expected_arrivals, 0) AS expected_arrivals,
        COALESCE(ed.expected_departures, 0) AS expected_departures,
        COALESCE(ad.actual_departures, 0) AS actual_departures,
        COALESCE(hh.house_use_in_house, 0) AS house_use_in_house,
        COALESCE(ch.complementary_in_house, 0) AS complementary_in_house
    FROM total_rooms tr
    LEFT JOIN in_house ih ON tr.report_date = ih.report_date 
        AND tr.room_type_id = ih.room_type_id 
        AND tr.company_id = ih.company_id
    LEFT JOIN expected_arrivals ea ON tr.report_date = ea.report_date 
        AND tr.room_type_id = ea.room_type_id 
        AND tr.company_id = ea.company_id
    LEFT JOIN expected_departures ed ON tr.report_date = ed.report_date
        AND tr.room_type_id = ed.room_type_id
        AND tr.company_id = ed.company_id
    LEFT JOIN actual_departures ad ON tr.report_date = ad.report_date 
        AND tr.room_type_id = ad.room_type_id 
        AND tr.company_id = ad.company_id
    LEFT JOIN in_house_house_use hh ON tr.report_date = hh.report_date
        AND tr.room_type_id = hh.room_type_id
        AND tr.company_id = hh.company_id
    LEFT JOIN in_house_complementary ch ON tr.report_date = ch.report_date
        AND tr.room_type_id = ch.room_type_id
        AND tr.company_id = ch.company_id
),
expected_in_house_data AS (
    SELECT
        dd.*,
        (dd.in_house + SUM(dd.expected_arrivals - dd.expected_departures) OVER (
            PARTITION BY dd.room_type_id, dd.company_id ORDER BY dd.report_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        )) AS expected_in_house
    FROM daily_data dd
),
no_shows AS (
    SELECT
        eih.*,
        CASE
            WHEN eih.report_date <= CURRENT_DATE THEN GREATEST(
                LAG(eih.expected_in_house, 1, 0) OVER (PARTITION BY eih.room_type_id, eih.company_id ORDER BY eih.report_date) - eih.in_house,
                0
            )
            ELSE 0
        END AS no_show_count
    FROM expected_in_house_data eih
),
adjusted_in_house_data AS (
    SELECT
        ns.*,
        GREATEST(
          ns.expected_in_house 
          - SUM(ns.no_show_count) OVER (PARTITION BY ns.room_type_id, ns.company_id ORDER BY ns.report_date
             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
          0
        ) AS adjusted_expected_in_house
    FROM no_shows ns
)
SELECT
    aih.company_id AS "Company ID",
    aih.company_name AS "Company Name",
    aih.report_date AS "Date",
    COALESCE(rt.room_type_name, 'Total') AS "Room Type",
    SUM(tr.total_rooms) AS "Total Rooms",
    SUM(ar.available_rooms) AS "Available Rooms",
    SUM(aih.in_house) AS "In House",
    SUM(aih.expected_arrivals) AS "Expected Arrivals",
    SUM(aih.expected_departures) AS "Expected Departures",
    SUM(aih.actual_departures) AS "Actual Departures",
    SUM(aih.adjusted_expected_in_house) AS "Expected In House",
    SUM(COALESCE(res.reserved_count, 0)) AS "Reserved",
    ROUND(
        (SUM(aih.adjusted_expected_in_house::numeric) / NULLIF(SUM(tr.total_rooms::numeric), 0)) * 100,
        2
    ) AS "Expected Occupied Rate (%)",
    SUM(COALESCE(oor.out_of_order_count, 0)) AS "Out of Order Count",
    GREATEST(
        SUM(COALESCE(res.reserved_count, 0)) - SUM(tr.total_rooms),
        0
    ) AS "Overbooked Count",
    CASE 
        WHEN GREATEST(SUM(COALESCE(res.reserved_count, 0)) - SUM(tr.total_rooms), 0) > 0 THEN 0
        ELSE GREATEST(SUM(ar.available_rooms) - SUM(aih.adjusted_expected_in_house), 0)
    END AS "Free to Sell",
    SUM(aih.no_show_count) AS "No Show Count",
    -- New fields for house use and complementary use in-house counts
    SUM(aih.house_use_in_house) AS "House Use In House",
    SUM(aih.complementary_in_house) AS "Complementary In House",
    CASE WHEN rt.room_type_name IS NULL THEN 1 ELSE 0 END AS sort_order
FROM adjusted_in_house_data aih
LEFT JOIN room_types rt ON aih.room_type_id = rt.room_type_id
LEFT JOIN total_rooms tr ON aih.report_date = tr.report_date 
    AND aih.room_type_id = tr.room_type_id 
    AND aih.company_id = tr.company_id
LEFT JOIN available_rooms ar ON aih.report_date = ar.report_date 
    AND aih.room_type_id = ar.room_type_id 
    AND aih.company_id = ar.company_id
LEFT JOIN reserved res ON aih.report_date = res.report_date 
    AND aih.room_type_id = res.room_type_id 
    AND aih.company_id = res.company_id
LEFT JOIN out_of_order_rooms oor ON aih.report_date = oor.report_date 
    AND aih.room_type_id = oor.room_type_id 
    AND aih.company_id = oor.company_id
GROUP BY aih.company_id, aih.company_name, aih.report_date, rt.room_type_name, sort_order
ORDER BY aih.company_id, aih.report_date, sort_order, rt.room_type_name;
        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        _logger.info(f"Query executed successfully. {len(results)} results fetched")
        print('line 355 running room type')

        records_to_create = []
        # DEFAULT_COMPANY_ID = 1
        for result in results:
            try:
                if result[0] is not None:
                    company_id = result[0] 
                # company_id = result[0] if result[0] is not None else DEFAULT_COMPANY_ID  # Replace DEFAULT_COMPANY_ID with an actual ID or logic to fetch a default
                    print(result[4],result[5])
                    records_to_create.append({
                        'company_id': company_id,  # Company ID
                        'report_date': result[2],  # Report Date
                        'room_type': result[3],  # Room Type
                        'total_rooms': int(result[4] or 0),  # Total Rooms
                        'available': int(result[5] or 0),  # Available Rooms
                        'expected_inhouse': int(result[9] or 0),  # Expected In House
                    })
  # Expected In House
                    # 'inhouse': int(result[6] or 0),  # In House
                    # 'expected_arrivals': int(result[7] or 0),  # Expected Arrivals
                    # 'expected_departures': int(result[8] or 0),  # Expected Departures
                    
                    # 'reserved': int(result[10] or 0),  # Reserved
                    # 'expected_occupied_rate': int(float(result[11] or 0)),  # Expected Occupied Rate
                    # 'out_of_order': int(result[12] or 0),  # Out of Order Count
                    # 'overbook': int(result[13] or 0),  # Overbooked Count
                    # 'free_to_sell': int(result[14] or 0),  # Free to Sell
                    # 'sort_order': int(result[15] or 0),  # Sort Order
                
            except Exception as e:
                _logger.error(f"Error processing record: {str(e)}, Data: {result}")
            
        if records_to_create:
            self.create(records_to_create)
            _logger.info(f"{len(records_to_create)} records created")
            
            _logger.info("Completed run_process_by_room_type")