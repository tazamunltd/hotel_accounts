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
                %(to_date)s::date AS to_date
        ),
        room_types AS (
            SELECT 
                rt.id,
                rt.room_type
            FROM room_type rt
            where rt.obsolete = False
           -- WHERE %(room_type_id)s IS NULL OR rt.id = CAST(%(room_type_id)s AS INTEGER)
        ),
        companies AS (
            SELECT 
                c.id,
                c.name
            FROM res_company c
            WHERE c.id = CAST(%(company_id)s AS INTEGER)
        ),
        date_series AS (
            SELECT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
            FROM parameters p
        ),
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
            JOIN room_booking rb ON rb.id = rbl.booking_id
            JOIN hotel_room hr ON hr.id = rbl.room_id
            JOIN room_types rt ON rt.id = hr.room_type_name
            LEFT JOIN room_booking_line_status rbls
                   ON rbls.booking_line_id = rbl.id
                   AND rbls.change_time::date <= ds.report_date
            ORDER BY
               rbl.id,
               ds.report_date,
               rbls.change_time DESC NULLS LAST
        ),
        in_house AS (
            SELECT
                lls.report_date,    
                lls.company_id,
                lls.room_type_id,
                COUNT(DISTINCT lls.booking_line_id) AS in_house_count
            FROM latest_line_status lls
            WHERE lls.checkin_date <= lls.report_date
              AND lls.checkout_date > lls.report_date
              AND lls.final_status = 'check_in'
            GROUP BY lls.report_date, lls.company_id, lls.room_type_id
        ),
        expected_arrivals AS (
            SELECT
                ds.report_date,
                rc.id AS company_id,
                rt.id AS room_type_id,
                COUNT(DISTINCT sub.booking_line_number) AS expected_arrivals_count
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
              AND qry.change_time::date <= ds.report_date
              AND qry.checkin_dt::date   = ds.report_date
    
            ORDER BY qry.booking_line_number, qry.change_time DESC
            ) AS sub ON TRUE
            GROUP BY ds.report_date, rc.id, rt.id
            ),

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
              AND qry.checkout_date::date = ds.report_date
              AND qry.status = 'check_in'
              AND qry.change_time::date <= ds.report_date
            ORDER BY qry.booking_line_number, qry.change_time DESC
            ) AS sub ON TRUE
       
            GROUP BY 
                ds.report_date,
                rc.id,
                rt.id
        ),
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
            JOIN room_types rt
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
            JOIN room_types rt
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
            JOIN room_types rt
              ON hr.room_type_name = rt.id
            GROUP BY rt.id, hr.company_id, ds.report_date
        ),
        daily_availability AS (
            SELECT 
                ds.report_date,
                rt.id AS room_type_id,
                rt.room_type AS room_type_name,
                c.id AS company_id,
                c.name AS company_name,
                COALESCE(i.total_room_count, 0) AS total_rooms,
                COALESCE(i.overbooking_rooms, 0) AS overbooking_rooms,
                COALESCE(i.overbooking_allowed, FALSE) AS overbooking_allowed,
                COALESCE(ih.in_house_count, 0) AS in_house,
                COALESCE(ea.expected_arrivals_count, 0) AS expected_arrivals,
                COALESCE(ed.expected_departures_count, 0) AS expected_departures,
                COALESCE(hu.house_use_count, 0) AS house_use,
                COALESCE(cu.complementary_use_count, 0) AS complementary_use,
                COALESCE(oo.out_of_order_count, 0) AS out_of_order,
                COALESCE(rh.rooms_on_hold_count, 0) AS rooms_on_hold,
                COALESCE(os.out_of_service_count, 0) AS out_of_service,
                /* Calculate free_to_sell for each day */
                CASE 
                    WHEN i.overbooking_allowed THEN
                        GREATEST(0,
                            i.total_room_count + i.overbooking_rooms
                            - (COALESCE(ih.in_house_count, 0)
                               + COALESCE(ea.expected_arrivals_count, 0)
                               - COALESCE(ed.expected_departures_count, 0)
                               + COALESCE(hu.house_use_count, 0)
                               + COALESCE(cu.complementary_use_count, 0)
                               + COALESCE(oo.out_of_order_count, 0)
                               + COALESCE(rh.rooms_on_hold_count, 0)
                               + COALESCE(os.out_of_service_count, 0))
                        )
                    ELSE
                        GREATEST(0,
                            i.total_room_count
                            - (COALESCE(ih.in_house_count, 0)
                               + COALESCE(ea.expected_arrivals_count, 0)
                               - COALESCE(ed.expected_departures_count, 0)
                               + COALESCE(hu.house_use_count, 0)
                               + COALESCE(cu.complementary_use_count, 0)
                               + COALESCE(oo.out_of_order_count, 0)
                               + COALESCE(rh.rooms_on_hold_count, 0)
                               + COALESCE(os.out_of_service_count, 0))
                        )
                END AS free_to_sell
            FROM date_series ds
            CROSS JOIN room_types rt
            CROSS JOIN companies c
            LEFT JOIN inventory i
                ON i.room_type_id = rt.id
                AND i.company_id = c.id
            LEFT JOIN in_house ih
                ON ih.room_type_id = rt.id
                AND ih.company_id = c.id
                AND ih.report_date = ds.report_date
            LEFT JOIN expected_arrivals ea
                ON ea.room_type_id = rt.id
                AND ea.company_id = c.id
                AND ea.report_date = ds.report_date
            LEFT JOIN expected_departures ed
                ON ed.room_type_id = rt.id
                AND ed.company_id = c.id
                AND ed.report_date = ds.report_date
            LEFT JOIN house_use_cte hu
                ON hu.room_type_id = rt.id
                AND hu.company_id = c.id
                AND hu.report_date = ds.report_date
            LEFT JOIN complementary_use_cte cu
                ON cu.room_type_id = rt.id
                AND cu.company_id = c.id
                AND cu.report_date = ds.report_date
            LEFT JOIN out_of_order oo
                ON oo.room_type_id = rt.id
                AND oo.company_id = c.id
                AND oo.report_date = ds.report_date
            LEFT JOIN rooms_on_hold rh
                ON rh.room_type_id = rt.id
                AND rh.company_id = c.id
                AND rh.report_date = ds.report_date
            LEFT JOIN out_of_service os
                ON os.room_type_id = rt.id
                AND os.company_id = c.id
                AND os.report_date = ds.report_date
        )
        /* Final selection with minimum free_to_sell check */
        SELECT 
            da.room_type_id,
            da.room_type_name,
            da.company_id,
            da.company_name,
            MIN(da.free_to_sell) as min_free_to_sell,
            MIN(da.total_rooms) as total_rooms,
            BOOL_OR(da.overbooking_allowed) as has_overbooking,
            da.overbooking_rooms as total_overbooking_rooms
        FROM daily_availability da
        WHERE da.report_date BETWEEN (SELECT from_date FROM parameters) 
                                AND (SELECT to_date FROM parameters)
        GROUP BY 
            da.room_type_id,
            da.room_type_name,
            da.company_id,
            da.company_name,
            da.overbooking_rooms
        HAVING MIN(da.free_to_sell) >= %(room_count)s
        ORDER BY da.company_name, da.room_type_name;
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
