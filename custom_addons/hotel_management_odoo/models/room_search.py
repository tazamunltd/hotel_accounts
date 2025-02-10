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
            _logger.info("Room search completed - Parameters: %s, Found: %d results", params, len(results))
            _logger.info("=== Detailed Room Search Results ===")
            for idx, room in enumerate(results, 1):
                _logger.info(
                    "Room %d:\n"
                    "  - Room Type: %s\n"
                    "  - Company: %s\n"
                    "  - Free to Sell: %s\n"
                    "  - Total Rooms: %s\n"
                    "  - Total Overbooking: %s",
                    idx,
                    room.get('room_type_name', 'N/A'),
                    room.get('company_name', 'N/A'),
                    room.get('min_free_to_sell', 0),
                    room.get('total_rooms', 0),
                    room.get('total_overbooking_rooms', 0)
                )
            _logger.info("=== End of Room Search Results ===")
            
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
            _logger.info("Room search results (%d rooms found):", len(results))
            for idx, room in enumerate(results, 1):
                _logger.info("Room %d: Type: %s, Company: %s, Free to Sell: %s, Total Rooms: %s, Overbooking: %s",
                            idx,
                            room.get('room_type_name', 'N/A'),
                            room.get('company_name', 'N/A'),
                            room.get('min_free_to_sell', 0),
                            room.get('total_rooms', 0),
                            room.get('total_overbooking_rooms', 0))
            
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
        WITH parameters AS (
            SELECT 
                %(from_date)s::date AS from_date,
                %(to_date)s::date AS to_date,
                CAST(%(company_id)s AS INTEGER) as company_id
        
            ),

date_series AS (
            SELECT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
            FROM parameters p
        ),
        system_date_company AS (
            select id as company_id 
            , system_date::date	from res_company rc where  rc.id = (SELECT company_id FROM parameters)
        ),
        base_data AS (
            SELECT
                rb.id AS booking_id,
                rb.company_id,
                rb.checkin_date::date AS checkin_date,
                rb.checkout_date::date AS checkout_date,
                rbl.id AS booking_line_id,
                rbl.room_id,
                rbl.hotel_room_type AS room_type_id,
                rbls.status,
                rbls.change_time,
                rb.house_use,
                rb.complementary
            FROM room_booking rb
            JOIN room_booking_line rbl ON rb.id = rbl.booking_id
            LEFT JOIN room_booking_line_status rbls ON rbl.id = rbls.booking_line_id
            WHERE rb.company_id = (SELECT company_id FROM parameters)
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
              ON ds.report_date >= bd.checkin_date 
              AND ds.report_date <= bd.checkout_date
            WHERE bd.change_time::date <= ds.report_date
            ORDER BY
               bd.booking_line_id,
               ds.report_date,
               bd.change_time DESC NULLS LAST
        ),
        
        in_house AS (
            SELECT
                lls.report_date,
                lls.company_id,
                lls.room_type_id,
                COUNT(DISTINCT lls.booking_line_id) AS in_house_count
            FROM latest_line_status lls
            WHERE lls.final_status = 'check_in'
              AND lls.report_date >= lls.checkin_date 
              AND lls.report_date <= lls.checkout_date
            GROUP BY 
                lls.report_date,
                lls.company_id,
                lls.room_type_id
        ),
        
        yesterday_in_house AS (
            SELECT
                lls.report_date,
                lls.company_id,
                lls.room_type_id,
                COUNT(DISTINCT lls.booking_line_id) AS in_house_count
            FROM latest_line_status lls
            WHERE lls.final_status = 'check_in'
              -- AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
              AND lls.report_date - interval '1 day' >= lls.checkin_date 
              AND lls.report_date - interval '1 day' <= lls.checkout_date
            GROUP BY 
                lls.report_date,
                lls.company_id,
                lls.room_type_id
        ),
        expected_arrivals AS (
            SELECT 
                lls.report_date,
                lls.company_id,
                lls.room_type_id,
                COUNT(DISTINCT lls.booking_line_id) AS expected_arrivals_count
            FROM latest_line_status lls
            WHERE lls.checkin_date = lls.report_date
              AND lls.final_status IN ('confirmed', 'block')
            GROUP BY 
                lls.report_date,
                lls.company_id,
                lls.room_type_id
        ),
        expected_departures AS (
            SELECT
                lls.report_date,
                lls.company_id,
                lls.room_type_id,
                COUNT(DISTINCT lls.booking_line_id) AS expected_departures_count
            FROM latest_line_status lls
            WHERE lls.checkout_date = lls.report_date
              AND lls.final_status = 'check_in'
            GROUP BY 
                lls.report_date,
                lls.company_id,
                lls.room_type_id
        ),
        house_use_cte AS (
            SELECT
                lls.report_date,
                lls.company_id,
                lls.room_type_id,
                COUNT(DISTINCT lls.booking_line_id) AS house_use_count
            FROM latest_line_status lls
            WHERE lls.house_use = TRUE
              AND lls.final_status in ('check_in', 'check_out')
              AND lls.checkin_date <= lls.report_date
              AND lls.checkout_date >= lls.report_date
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
              AND lls.final_status in ('check_in', 'check_out')
              AND lls.checkin_date <= lls.report_date
              AND lls.checkout_date >= lls.report_date
            GROUP BY lls.report_date, lls.company_id, lls.room_type_id
        ),
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
        final_report AS (
            SELECT
                ds.report_date,
                rc.id                    AS company_id,
                rc.name                  AS company_name,
                rt.id                    AS room_type_id,
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
                (COALESCE(inv.total_room_count, 0)
                 - COALESCE(ooo.out_of_order_count, 0)
                 - COALESCE(roh.rooms_on_hold_count, 0))    AS available_rooms,
                GREATEST(0, 
              -- Use ih.in_house_count when system_date is today, otherwise use yh.in_house_count
              COALESCE(
                  CASE 
                      WHEN sdc.system_date = ds.report_date THEN ih.in_house_count 
                      ELSE yh.in_house_count 
                  END, 0
              ) 
              + COALESCE(ea.expected_arrivals_count, 0)
              - LEAST(COALESCE(ed.expected_departures_count, 0), 
                      COALESCE(
                          CASE 
                              WHEN sdc.system_date = ds.report_date THEN ih.in_house_count 
                              ELSE yh.in_house_count 
                          END, 0
                      )
              )
            ) AS expected_in_house
            FROM date_series ds
             LEFT JOIN res_company rc ON rc.id = (SELECT company_id FROM parameters) 
            -- CROSS JOIN res_company rc
            CROSS JOIN room_type rt
            INNER JOIN inventory inv ON inv.company_id = rc.id AND inv.room_type_id = rt.id
            LEFT JOIN out_of_order ooo ON ooo.company_id = rc.id AND ooo.room_type_id = rt.id AND ooo.report_date = ds.report_date
            LEFT JOIN rooms_on_hold roh ON roh.company_id = rc.id AND roh.room_type_id = rt.id AND roh.report_date = ds.report_date
            LEFT JOIN out_of_service oos ON oos.company_id = rc.id AND oos.room_type_id = rt.id AND oos.report_date = ds.report_date
            LEFT JOIN in_house ih ON ih.company_id = rc.id AND ih.room_type_id = rt.id AND ih.report_date = ds.report_date
            LEFT JOIN expected_arrivals ea ON ea.company_id = rc.id AND ea.room_type_id = rt.id AND ea.report_date = ds.report_date
            LEFT JOIN expected_departures ed ON ed.company_id = rc.id AND ed.room_type_id = rt.id AND ed.report_date = ds.report_date
            LEFT JOIN house_use_cte hc ON hc.company_id = rc.id AND hc.room_type_id = rt.id AND hc.report_date = ds.report_date
            LEFT JOIN complementary_use_cte cc ON cc.company_id = rc.id AND cc.room_type_id = rt.id AND cc.report_date = ds.report_date
            LEFT JOIN yesterday_in_house yh ON yh.company_id = rc.id AND yh.room_type_id = rt.id AND yh.report_date = ds.report_date
            LEFT JOIN system_date_company sdc on sdc.company_id = rc.id
        )
        SELECT
          fr.room_type_id,
          fr.room_type_name, 
          fr.company_id,
          fr.company_name,
          CASE 
        WHEN BOOL_OR(fr.overbooking_allowed) THEN
            CASE
                WHEN SUM(fr.available_rooms) < 0 OR SUM(fr.overbooking_rooms) < 0 OR SUM(fr.expected_in_house) < 0 THEN 0
                ELSE GREATEST(0, SUM(fr.available_rooms) + SUM(fr.overbooking_rooms) - SUM(fr.expected_in_house))
            END
        ELSE
            CASE
                WHEN SUM(fr.available_rooms) < 0 OR SUM(fr.expected_in_house) < 0 THEN 0
                ELSE GREATEST(0, SUM(fr.available_rooms) - SUM(fr.expected_in_house))
            END
    END AS min_free_to_sell,
    
          SUM(fr.total_rooms) AS total_rooms,
          BOOL_OR(fr.overbooking_allowed) AS has_overbooking,
          SUM(fr.overbooking_rooms) AS total_overbooking_rooms
        FROM final_report fr
        where fr.report_date BETWEEN (SELECT from_date FROM parameters) 
                                        AND (SELECT to_date - interval '1 day' FROM parameters) 
                                        
        GROUP BY
          fr.report_date,
          fr.company_id,
          fr.company_name,
          fr.room_type_id,
          fr.room_type_name
          HAVING 
			    fr.room_type_id NOT IN (
        SELECT fr2.room_type_id 
        FROM final_report fr2
        WHERE fr2.report_date BETWEEN (SELECT from_date FROM parameters) 
                                AND (SELECT to_date - INTERVAL '1 day' FROM parameters)
        GROUP BY fr2.room_type_id, fr2.report_date
        HAVING 
            CASE 
                WHEN BOOL_OR(fr2.overbooking_allowed) THEN
                    CASE
                        WHEN SUM(fr2.available_rooms) < 0 
                             OR SUM(fr2.overbooking_rooms) < 0 
                             OR SUM(fr2.expected_in_house) < 0 
                        THEN 0
                        ELSE GREATEST(0, SUM(fr2.available_rooms) + SUM(fr2.overbooking_rooms) - SUM(fr2.expected_in_house))
                    END
                ELSE
                    CASE
                        WHEN SUM(fr2.available_rooms) < 0 
                             OR SUM(fr2.expected_in_house) < 0 
                        THEN 0
                        ELSE GREATEST(0, SUM(fr2.available_rooms) - SUM(fr2.expected_in_house))
                    END
            END < %(room_count)s  -- Exclude any room_type_id with min_free_to_sell < 1 on any date
    )
        ORDER BY
          fr.report_date,
          fr.company_name,
          fr.room_type_name;
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
