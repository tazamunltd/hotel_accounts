# -*- coding: utf-8 -*-
"""
Room Search Module
Created: 2025-01-08T01:22:36+05:00
Author: Cascade AI

This module handles room search functionality for the hotel management system.
It provides methods to search for available rooms based on various criteria
including check-in date, check-out date, and room count.
"""

from odoo import models, api, _, fields
from odoo.exceptions import UserError, ValidationError, AccessError
from datetime import datetime, date, timedelta
import logging
import pytz

_logger = logging.getLogger(__name__)

class RoomSearch(models.Model):
    """
    Model for handling room search operations
    Provides methods to search available rooms based on various criteria
    """
    _name = 'room.search'
    _description = 'Room Search Operations'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Search History Fields
    search_date = fields.Datetime(string='Search Date', default=fields.Datetime.now, readonly=True)
    checkin_date = fields.Date(string='Check-in Date', required=True)
    checkout_date = fields.Date(string='Check-out Date', required=True)
    room_count = fields.Integer(string='Room Count', required=True, default=1)
    company_id = fields.Many2one('res.company', string='Hotel', required=True)
    room_type_id = fields.Many2one('room.type', string='Room Type')
    # search_result = fields.Text(string='Search Result', readonly=True)
    # state = fields.Selection([
    #     ('draft', 'Draft'),
    #     ('searched', 'Searched'),
    #     ('booked', 'Booked'),
    #     ('cancelled', 'Cancelled')
    # ], string='Status', default='draft', tracking=True)

    @api.constrains('checkin_date', 'checkout_date')
    def _check_dates(self):
        """
        Validate check-in and check-out dates
        
        Raises:
            ValidationError: If dates are invalid
            
        Created: 2025-01-08T01:24:57+05:00
        """
        for record in self:
            if record.checkin_date and record.checkout_date:
                if record.checkin_date > record.checkout_date:
                    raise ValidationError(_("Check-out date must be after check-in date"))
                if record.checkin_date < fields.Date.today():
                    raise ValidationError(_("Check-in date cannot be in the past"))

    @api.model
    def search_available_rooms(self, from_date, to_date, room_count, company_id, room_type_id=None):
        """
        Search for available rooms based on given criteria
        
        Args:
            from_date (str): Check-in date
            to_date (str): Check-out date
            room_count (int): Number of rooms needed
            company_id (int): Company/Hotel ID
            room_type_id (int, optional): Room type ID to filter by
            
        Returns:
            list: List of available rooms matching criteria
            
        Modified: 2025-01-09T20:53:53+05:00
        """
        try:
            # Convert string dates to datetime.date objects
            from_date = fields.Date.from_string(from_date)
            to_date = fields.Date.from_string(to_date)
            
            # Get and execute search query
            query = self._get_room_search_query()
            params = {
                'from_date': from_date,
                'to_date': to_date,
                'room_count': room_count,
                'company_id': company_id,
                'room_type_id': room_type_id,
            }
            
            results = self.execute_room_search(query, params)
            
            # Log detailed results
            # _logger.info("Room search completed - Parameters: %s, Found: %d results", params, len(results))
            # _logger.info("=== Detailed Room Search Results ===")
            # for idx, room in enumerate(results, 1):
            #     _logger.info(
            #         "Room %d:\n"
            #         "  - Room Type: %s\n"
            #         "  - Company: %s\n"
            #         "  - Free to Sell: %s\n"
            #         "  - Total Rooms: %s\n"
            #         "  - Total Overbooking: %s",
            #         idx,
            #         room.get('room_type_name', 'N/A'),
            #         room.get('company_name', 'N/A'),
            #         room.get('min_free_to_sell', 0),
            #         room.get('total_rooms', 0),
            #         room.get('total_overbooking_rooms', 0)
            #     )
            # _logger.info("=== End of Room Search Results ===")
            
            return results
            
        except Exception as e:
            _logger.error("Error in search_available_rooms: %s", str(e), exc_info=True)
            raise UserError(_("Error searching rooms: %s") % str(e))

    @api.model
    def execute_room_search(self, query, params):
        """
        Execute a room search query with the given parameters
        
        Args:
            query (str): The SQL query to execute
            params (dict): Dictionary of parameters for the query
        
        Returns:
            list: List of dictionaries containing room availability information
            
        Raises:
            UserError: If there's an error executing the query
            
        Modified: 2025-01-09T20:50:23+05:00
        """
        try:
            # Format parameters for logging
            formatted_params = {k: v for k, v in params.items()}
            _logger.info("Executing room search with params: %s", formatted_params)
            
            self.env.cr.execute(query, params)
            results = self.env.cr.dictfetchall()
            
            # Log each result row with detailed information
            # _logger.info("Room search results (%d rooms found):", len(results))
            # for idx, room in enumerate(results, 1):
            #     _logger.info("Room %d: Type: %s, Company: %s, Free to Sell: %s, Total Rooms: %s, Overbooking: %s",
            #                 idx,
            #                 room.get('room_type_name', 'N/A'),
            #                 room.get('company_name', 'N/A'),
            #                 room.get('min_free_to_sell', 0),
            #                 room.get('total_rooms', 0),
            #                 room.get('total_overbooking_rooms', 0))
            
            return results
            
        except Exception as e:
            _logger.error("Error executing room search query: %s\nQuery: %s\nParams: %s",
                         str(e), query, formatted_params, exc_info=True)
            raise UserError(_("Error executing room search: %s") % str(e))

    def _get_room_search_query(self):
        """
        Get the room search query template that filters rooms based on availability.
        Only returns rooms where free-to-sell quantity >= requested room count
        across the entire date range.
        
        Returns:
            str: SQL query for room search with availability calculations
            
        Modified: 2025-01-09T12:52:13+05:00
        """
        return """
        WITH RECURSIVE
parameters AS (
    SELECT
		%(from_date)s::date AS from_date,
        %(to_date)s::date AS to_date
		),
company_ids AS (
    select CAST(%(company_id)s AS INTEGER) as company_id
),
system_date_company AS (
    SELECT 
        id AS company_id, 
        system_date::date AS system_date,
        create_date::date AS create_date
    FROM res_company rc 
    WHERE rc.id IN (SELECT company_id FROM company_ids)
),
-- 2. Generate report dates from the earliest system_date to the specified to_date
date_series AS (
    SELECT generate_series(
        (SELECT MIN(system_date) FROM system_date_company), 
        (SELECT to_date FROM parameters),
        INTERVAL '1 day'
    )::date AS report_date
),
-- 3. Base data & Latest status per booking line
base_data AS (
        SELECT
            rb.id AS booking_id,
            rb.parent_booking_id,
            rb.company_id,
            rb.checkin_date::date AS checkin_date,
            rb.checkout_date::date AS checkout_date,
            rbl.id AS booking_line_id,
            rbl.sequence,
            rbl.room_id,
            rbl.hotel_room_type AS room_type_id,
            rbls.status,
            rbls.change_time,
            rb.house_use,
            rb.complementary
        FROM room_booking rb
        JOIN room_booking_line rbl ON rb.id = rbl.booking_id
        LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
        WHERE rb.company_id IN (SELECT company_id FROM company_ids) and rb.active = true

),
latest_line_status AS (
    SELECT DISTINCT ON (bd.booking_line_id, ds.report_date)
           bd.booking_line_id,
           ds.report_date,
           bd.checkin_date,
           bd.checkout_date,
           bd.company_id,
           bd.room_type_id,
           bd.status AS final_status,
           bd.change_time,
           bd.house_use,
           bd.complementary
    FROM base_data bd
    JOIN date_series ds 
      ON ds.report_date BETWEEN bd.checkin_date AND bd.checkout_date
    WHERE bd.change_time::date <= ds.report_date
    ORDER BY
       bd.booking_line_id,
       ds.report_date DESC,
       bd.change_time DESC NULLS LAST
)
	-- select * from latest_line_status;
	,
-- 4. Compute the system date metrics (anchor values)
-- Actual in_house on system_date (using check_in status)
system_date_in_house AS (
    SELECT
        sdc.system_date AS report_date,
        sdc.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS in_house_count
    FROM latest_line_status lls
    JOIN system_date_company sdc ON sdc.company_id = lls.company_id
    WHERE lls.final_status = 'check_in'
      AND sdc.system_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
),
-- Expected arrivals on system_date: bookings where checkin_date equals system_date and status is confirmed or block
system_date_expected_arrivals AS (
    SELECT
        sdc.system_date AS report_date,
        sdc.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    JOIN system_date_company sdc ON sdc.company_id = lls.company_id
    WHERE lls.checkin_date = sdc.system_date
      AND lls.final_status IN ('confirmed', 'block')
    GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
),
-- Expected departures on system_date: bookings where checkout_date equals system_date and status in (check_in, confirmed, block)
system_date_expected_departures AS (
    SELECT
        sdc.system_date AS report_date,
        sdc.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    JOIN system_date_company sdc ON sdc.company_id = lls.company_id
    WHERE lls.checkout_date = sdc.system_date
      AND lls.final_status IN ('check_in', 'confirmed', 'block')
    GROUP BY sdc.system_date, sdc.company_id, lls.room_type_id
),
-- Compute the anchor expected_in_house on the system_date using the formula:
-- expected_in_house = in_house (from check_in) + expected arrivals – expected departures
system_date_base AS (
  SELECT
    sdc.system_date AS report_date,
    sdc.company_id,
    rt.id AS room_type_id,
    COALESCE(sdih.in_house_count, 0) AS in_house,
    COALESCE(sdea.expected_arrivals_count, 0) AS expected_arrivals,
    COALESCE(sded.expected_departures_count, 0) AS expected_departures,
    (COALESCE(sdih.in_house_count, 0)
     + COALESCE(sdea.expected_arrivals_count, 0)
     - COALESCE(sded.expected_departures_count, 0)) AS expected_in_house
  FROM system_date_company sdc
  CROSS JOIN room_type rt
  LEFT JOIN system_date_in_house sdih 
         ON sdih.company_id = sdc.company_id 
         AND sdih.room_type_id = rt.id 
         AND sdih.report_date = sdc.system_date
  LEFT JOIN system_date_expected_arrivals sdea 
         ON sdea.company_id = sdc.company_id 
         AND sdea.room_type_id = rt.id 
         AND sdea.report_date = sdc.system_date
  LEFT JOIN system_date_expected_departures sded 
         ON sded.company_id = sdc.company_id 
         AND sded.room_type_id = rt.id 
         AND sded.report_date = sdc.system_date
),
-- 5. For subsequent dates, calculate expected arrivals and departures per report_date
expected_arrivals AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
    FROM latest_line_status lls
    WHERE lls.checkin_date = lls.report_date
      AND lls.final_status IN ('confirmed','block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
expected_departures AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
    FROM latest_line_status lls
    WHERE lls.checkout_date = lls.report_date
      AND lls.final_status IN ('check_in','confirmed','block')
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
-- 6. Recursive Calculation for in_house and expected_in_house
-- For days after the system date, set:
--   new in_house = previous day's expected_in_house (i.e. yesterday’s expected in_house)
--   new expected_in_house = new in_house + (today's expected arrivals) - (today's expected departures)
recursive_in_house AS (
    -- Anchor row: system_date_base values
    SELECT 
        sdb.report_date,
        sdb.company_id,
        sdb.room_type_id,
        sdb.in_house,
        sdb.expected_in_house
    FROM system_date_base sdb
    UNION ALL
    -- Recursive step: for each subsequent day
    SELECT
        ds.report_date,
        r.company_id,
        r.room_type_id,
        r.expected_in_house AS in_house,  -- new in_house equals previous expected_in_house
        (r.expected_in_house + COALESCE(ea.expected_arrivals_count, 0)
                              - COALESCE(ed.expected_departures_count, 0)) AS expected_in_house
    FROM recursive_in_house r
    JOIN date_series ds 
         ON ds.report_date = r.report_date + INTERVAL '1 day'
    LEFT JOIN expected_arrivals ea 
         ON ea.report_date = ds.report_date 
         AND ea.company_id = r.company_id 
         AND ea.room_type_id = r.room_type_id
    LEFT JOIN expected_departures ed 
         ON ed.report_date = ds.report_date 
         AND ed.company_id = r.company_id 
         AND ed.room_type_id = r.room_type_id
),
recursive_in_house_distinct AS (
  SELECT
    report_date,
    company_id,
    room_type_id,
    MAX(in_house) AS in_house,
    MAX(expected_in_house) AS expected_in_house
  FROM recursive_in_house
  GROUP BY report_date, company_id, room_type_id
),
-- 7. Additional Metrics (house use, complementary use, inventory, out_of_order, rooms on hold, out_of_service)
house_use_cte AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS house_use_count
    FROM latest_line_status lls
    WHERE lls.house_use = TRUE
      AND lls.final_status IN ('check_in', 'check_out')
      AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
complementary_use_cte AS (
    SELECT
        lls.report_date,
        lls.company_id,
        lls.room_type_id,
        COUNT(DISTINCT lls.booking_line_id) AS complementary_use_count
    FROM latest_line_status lls
    WHERE lls.complementary = TRUE
      AND lls.final_status IN ('check_in', 'check_out')
      AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
    GROUP BY lls.report_date, lls.company_id, lls.room_type_id
),
inventory AS (
    SELECT
        hi.company_id,
        hi.room_type AS room_type_id,
        COUNT(DISTINCT hr.id) AS total_room_count,
        SUM(COALESCE(hi.overbooking_rooms, 0)) AS overbooking_rooms,
        BOOL_OR(COALESCE(hi.overbooking_allowed, false)) AS overbooking_allowed
    FROM hotel_inventory hi
    JOIN hotel_room hr
      ON hr.company_id    = hi.company_id
     AND hr.room_type_name = hi.room_type
     AND hr.active = TRUE
    GROUP BY hi.company_id, hi.room_type
),
out_of_order AS (
    SELECT
        rt.id AS room_type_id,
        hr.company_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS out_of_order_count
    FROM date_series ds
    JOIN out_of_order_management_fron_desk ooo
      ON ds.report_date BETWEEN ooo.from_date AND ooo.to_date
    JOIN hotel_room hr
      ON hr.id = ooo.room_number
      AND hr.active = TRUE
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
rooms_on_hold AS (
    SELECT
        rt.id AS room_type_id,
        hr.company_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS rooms_on_hold_count
    FROM date_series ds
    JOIN rooms_on_hold_management_front_desk roh
      ON ds.report_date BETWEEN roh.from_date AND roh.to_date
    JOIN hotel_room hr
      ON hr.id = roh.room_number
      AND hr.active = TRUE
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
out_of_service AS (
    SELECT
        rt.id AS room_type_id,
        hr.company_id,
        ds.report_date,
        COUNT(DISTINCT hr.id) AS out_of_service_count
    FROM date_series ds
    JOIN housekeeping_management hm
      ON hm.out_of_service = TRUE
      AND (hm.repair_ends_by IS NULL OR ds.report_date <= hm.repair_ends_by)
    JOIN hotel_room hr
      ON hr.room_type_name = hm.room_type
      AND hr.active = TRUE
    JOIN room_type rt
      ON hr.room_type_name = rt.id
    GROUP BY rt.id, hr.company_id, ds.report_date
),
-- 8. Final Report (metrics aggregated per report_date, company and room type)
final_report AS (
    SELECT
        ds.report_date,
        rc.id AS company_id,
        rc.name AS company_name,
        rt.id AS room_type_id,
        COALESCE(jsonb_extract_path_text(rt.room_type::jsonb, 'en_US'),'N/A') AS room_type_name,
        COALESCE(inv.total_room_count, 0) AS total_rooms,
        COALESCE(inv.overbooking_rooms, 0) AS overbooking_rooms,
        COALESCE(inv.overbooking_allowed, false) AS overbooking_allowed,
        COALESCE(ooo.out_of_order_count, 0) AS out_of_order,
        COALESCE(roh.rooms_on_hold_count, 0) AS rooms_on_hold,
        COALESCE(oos.out_of_service_count, 0) AS out_of_service,
        COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals,
        COALESCE(ed.expected_departures_count, 0) AS expected_departures,
        COALESCE(hc.house_use_count, 0) AS house_use_count,
        COALESCE(cc.complementary_use_count, 0) AS complementary_use_count,
        (COALESCE(inv.total_room_count, 0)
         - COALESCE(ooo.out_of_order_count, 0)
         - COALESCE(roh.rooms_on_hold_count, 0)) AS available_rooms,
        COALESCE((
          SELECT in_house_count 
          FROM system_date_in_house sdi 
          WHERE sdi.company_id = rc.id 
            AND sdi.room_type_id = rt.id 
            AND sdi.report_date = ds.report_date
        ), 0) AS in_house
    FROM date_series ds
    LEFT JOIN res_company rc
         ON rc.id IN (SELECT company_id FROM company_ids)
    CROSS JOIN room_type rt
    INNER JOIN inventory inv
         ON inv.company_id = rc.id AND inv.room_type_id = rt.id
    LEFT JOIN out_of_order ooo
         ON ooo.company_id = rc.id AND ooo.room_type_id = rt.id AND ooo.report_date = ds.report_date
    LEFT JOIN rooms_on_hold roh
         ON roh.company_id = rc.id AND roh.room_type_id = rt.id AND roh.report_date = ds.report_date
    LEFT JOIN out_of_service oos
         ON oos.company_id = rc.id AND oos.room_type_id = rt.id AND oos.report_date = ds.report_date
    LEFT JOIN expected_arrivals ea
         ON ea.company_id = rc.id AND ea.room_type_id = rt.id AND ea.report_date = ds.report_date
    LEFT JOIN expected_departures ed
         ON ed.company_id = rc.id AND ed.room_type_id = rt.id AND ed.report_date = ds.report_date
    LEFT JOIN house_use_cte hc
         ON hc.company_id = rc.id AND hc.room_type_id = rt.id AND hc.report_date = ds.report_date
    LEFT JOIN complementary_use_cte cc
         ON cc.company_id = rc.id AND cc.room_type_id = rt.id AND cc.report_date = ds.report_date
    LEFT JOIN system_date_company sdc
         ON sdc.company_id = rc.id
    WHERE ds.report_date >= (SELECT from_date FROM parameters)
),
-- 9. Final Output: Join recursive in_house values with aggregated metrics
final_output AS (
    SELECT
      fr.report_date,
      fr.company_id,
      fr.company_name,
      fr.room_type_id,
      fr.room_type_name,
      SUM(fr.total_rooms) AS total_rooms,
      BOOL_OR(fr.overbooking_allowed) AS any_overbooking_allowed,
      SUM(fr.overbooking_rooms) AS total_overbooking_rooms,
      SUM(fr.out_of_order) AS out_of_order,
      SUM(fr.rooms_on_hold) AS rooms_on_hold,
      SUM(fr.out_of_service) AS out_of_service,
      SUM(fr.expected_arrivals) AS expected_arrivals,
      SUM(fr.expected_departures) AS expected_departures,
      SUM(fr.house_use_count) AS house_use_count,
      SUM(fr.complementary_use_count) AS complementary_use_count,
      SUM(fr.available_rooms) AS available_rooms,
      rih.in_house AS in_house,
      rih.expected_in_house AS expected_in_house,
      CASE 
        WHEN BOOL_OR(fr.overbooking_allowed) THEN
          CASE
            WHEN SUM(fr.available_rooms) < 0 
              OR SUM(fr.overbooking_rooms) < 0 
              OR rih.expected_in_house < 0 THEN 0
            ELSE GREATEST(0, SUM(fr.available_rooms) + SUM(fr.overbooking_rooms) - rih.expected_in_house)
          END
        ELSE
          CASE
            WHEN SUM(fr.available_rooms) < 0 THEN 0
            ELSE GREATEST(0, SUM(fr.available_rooms) - rih.expected_in_house)
          END
      END AS free_to_sell,
      GREATEST(0, rih.expected_in_house - SUM(fr.available_rooms)) AS over_booked
    FROM final_report fr
    JOIN recursive_in_house_distinct rih
      ON fr.report_date = rih.report_date
     AND fr.company_id = rih.company_id
     AND fr.room_type_id = rih.room_type_id
    WHERE fr.report_date >= (SELECT from_date FROM parameters)
    GROUP BY
      fr.report_date,
      fr.company_id,
      fr.company_name,
      fr.room_type_id,
      fr.room_type_name,
      rih.in_house,
      rih.expected_in_house
    ORDER BY
      fr.report_date,
      fr.company_name,
      fr.room_type_name
)

SELECT
	
    room_type_id,
	room_type_name,
    company_id,
    company_name,
	
    min(free_to_sell) AS min_free_to_sell,
	total_rooms,
	any_overbooking_allowed as has_overbooking,
	total_overbooking_rooms
	
FROM final_output
	group by room_type_id,room_type_name,company_id,company_name,total_rooms,any_overbooking_allowed,total_overbooking_rooms
having min(free_to_sell) >= %(room_count)s;
        """

    
    
    def action_cancel(self):
        """
        Cancel the room search
        
        Created: 2025-01-08T01:24:57+05:00
        """
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        """
        Reset the search to draft state
        
        Created: 2025-01-08T01:24:57+05:00
        """
        self.write({'state': 'draft'})

    def _run_room_search_test(self):
        """
        Comprehensive test suite for room search functionality
        
        This method runs multiple test cases to validate the room search functionality
        
        Returns:
            bool: True if all tests pass, False otherwise
            
        Created: 2025-01-08T01:24:57+05:00
        """
        try:
            today = fields.Date.today()
            tomorrow = today + timedelta(days=1)
            next_week = today + timedelta(days=7)
            
            test_cases = [
                # Test case 1: Basic search
                {
                    'name': 'Basic search',
                    'params': [today, tomorrow, 1],
                    'expected_result': True
                },
                # Test case 2: Multiple rooms
                {
                    'name': 'Multiple rooms search',
                    'params': [today, tomorrow, 2],
                    'expected_result': True
                },
                # Test case 3: Longer stay
                {
                    'name': 'Week-long stay search',
                    'params': [today, next_week, 1],
                    'expected_result': True
                },
                # Test case 4: Invalid dates
                {
                    'name': 'Invalid dates test',
                    'params': [tomorrow, today, 1],
                    'expected_error': ValidationError
                }
            ]
            
            for test_case in test_cases:
                _logger.info(f"Running test case: {test_case['name']}")
                
                try:
                    if 'expected_error' in test_case:
                        # Test should raise an error
                        with self.assertRaises(test_case['expected_error']):
                            self.search_available_rooms(*test_case['params'])
                    else:
                        # Test should succeed
                        result = self.search_available_rooms(*test_case['params'])
                        assert bool(result) == test_case['expected_result'], \
                            f"Test case '{test_case['name']}' failed: unexpected result"
                
                except AssertionError as e:
                    _logger.error(f"Test case '{test_case['name']}' failed: {str(e)}")
                    return False
                
                _logger.info(f"Test case '{test_case['name']}' passed")
            
            _logger.info("All room search tests completed successfully")
            return True
            
        except Exception as e:
            _logger.error(f"Room search test suite failed: {str(e)}")
            return False
