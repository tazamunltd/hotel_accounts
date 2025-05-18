# -*- coding: utf-8 -*-
# Date: 2025-01-20 Time: 14:13:50 - Fixed dashboard data fetching
from odoo import api, fields, models, _
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class RoomBookingDashboard(models.Model):
    """Model for handling new dashboard metrics"""
    _name = 'room.booking.dashboard'
    _description = 'Room Booking Dashboard'

    @api.model
    def get_dashboard_data(self, filters=None):
        """Get dashboard metrics
        
        Date: 2025-01-20
        Time: 14:13:50
        
        Args:
            filters (dict): Dictionary containing start_date and end_date
            
        Returns:
            dict: Dashboard metrics
        """
        try:
            _logger.info('Starting dashboard data fetch with filters: %s', filters)
            
            # Get company and system date
            company = self.env.company
            _logger.info('Company ID: %s', company.id)
            hotel = self.env['hotel.room'].search([('company_id', '=', company.id)])
            system_date = company.system_date.date() or fields.Date.today()
            min_date = self.env['room.booking'].search([], order='checkin_date asc', limit=1).checkin_date.date()
            max_date = self.env['room.booking'].search([], order='checkout_date desc', limit=1).checkout_date.date()
            # print(f'MinMax:{min_date},{max_date}')
            _logger.info(f'Min Max date: {min_date}, {max_date}')
            
            # Initialize filters if None
            if not filters:
                filters = {}
            
            # Convert string dates to date objects if provided
            try:
                start_date = fields.Date.from_string(filters.get('start_date')) if filters.get('start_date') else False
                end_date = fields.Date.from_string(filters.get('end_date')) if filters.get('end_date') else False
                _logger.info('Parsed dates - Start: %s, End: %s', start_date, end_date)
            except Exception as e:
                _logger.error('Error parsing dates: %s', str(e))
                start_date = end_date = False
            
            if not start_date or not end_date:
                # Default to current month if no dates provided
                start_date = min_date
                end_date = max_date
                _logger.info('Using default dates - Start: %s, End: %s', start_date, end_date)
            
            # Base domain for room bookings
            domain = [
                ('company_id', '=', company.id),
                '|',
                '&', ('checkin_date', '>=', start_date), ('checkin_date', '<=', end_date),
                '&', ('checkout_date', '>=', start_date), ('checkout_date', '<=', end_date)
            ]
            _logger.info('Search domain: %s', domain)
            
            # Get booking records
            bookings = self.env['room.booking'].search(domain)
            _logger.info('Found %d booking records', len(bookings))

            arrivals = {}
            departures = {}
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                arrivals[date_str] = 0
                departures[date_str] = 0
                current_date += timedelta(days=1)

            for booking in bookings:
                checkin_date = booking.checkin_date.strftime('%Y-%m-%d')
                checkout_date = booking.checkout_date.strftime('%Y-%m-%d')
                
                if checkin_date in arrivals:
                    arrivals[checkin_date] += 1
                if checkout_date in departures:
                    departures[checkout_date] += 1

            # Calculate country-wise bookings
            # country_data = {}
            # for booking in bookings:
            #     # Get country from partner's country_id
            #     country = booking.partner_id.country_id
            #     country_name = country.name if country else 'Undefined'
            #     country_data[country_name] = country_data.get(
            #         country_name, 0) + 1

            # # Sort countries by number of bookings (descending) and get top 10
            # sorted_countries = sorted(
            #     country_data.items(), key=lambda x: x[1], reverse=True)[:10]
            # country_labels = [country[0] for country in sorted_countries]
            # country_values = [country[1] for country in sorted_countries]
            countries = {}
            for booking in bookings:
                country = booking.nationality
                # print(country, 'line 107')
                if country:  # If it's already a string
                    country = self.env['res.country'].browse(country.id)

                    if country.exists():  # Check if the record exists
                        country = country.name
                    else:
                        country = 'Other'
                else:
                    country = 'Other'
                countries[country] = countries.get(country, 0) + 1  
            
            # Calculate metrics
            metrics = {
                'total': len(bookings),
                'confirmed': len(bookings.filtered(lambda b: b.state == 'confirmed')),
                'not_confirmed': len(bookings.filtered(lambda b: b.state == 'not_confirmed')),
                'waiting': len(bookings.filtered(lambda b: b.state == 'waiting')),
                'cancelled': len(bookings.filtered(lambda b: b.state == 'cancel')),
                'blocked': len(bookings.filtered(lambda b: b.state == 'block')),
                'check_in': len(bookings.filtered(lambda b: b.state == 'check_in')),
                'check_out': len(bookings.filtered(lambda b: b.state == 'check_out'))
            }
            
            # Calculate total reservations (confirmed + blocked + waiting)
            metrics['total_reservations'] = (
                metrics['confirmed'] + 
                metrics['blocked'] + 
                metrics['waiting']
            )
            
            # Generate date range for occupancy data
            date_range = []
            current_date = start_date
            while current_date <= end_date:
                date_range.append(current_date)
                current_date += timedelta(days=1)
            
            # Calculate occupancy data
            occupancy_data = []
            occupancy_labels = []
            for date in date_range:
                date_bookings = bookings.filtered(
                    lambda b: b.checkin_date.date() <= date <= b.checkout_date.date()
                )
                occupancy_rate = (len(date_bookings) / len(hotel) * 100) if len(hotel) > 0 else 0
                occupancy_data.append(round(occupancy_rate, 2))
                occupancy_labels.append(date.strftime('%Y-%m-%d'))
                # print(f'Occupancy for {date}: {occupancy_rate}%')
            
            # Calculate market segments
            segments = {}
            for booking in bookings:
                segment = booking.market_segment
                # if segment != 'Other':  # If it's already a string
                if segment:
                    market_segment = self.env['market.segment'].browse(segment.id)

                    if market_segment.exists():  # Check if the record exists
                        segment = market_segment.market_segment
                    else:
                        segment = 'Other'
                else:
                    segment = 'Other'
                # print(segment)
                segments[segment] = segments.get(segment, 0) + 1
            
            # Calculate business sources
            sources = {}
            for booking in bookings:
                source = booking.source_of_business
                # if source != 'Other':  # If it's already a string
                # source_val = ()
                if source:
                    source_val = self.env['source.business'].browse(source.id)

                    if source_val.exists():  # Check if the record exists
                        source = source.source
                    else:
                        source = 'Other'
                else:
                    source = 'Other'

                sources[source] = sources.get(source, 0) + 1
            
            # Prepare expectations data (next 7 days)
            expectations = {}
            for i in range(7):
                future_date = system_date + timedelta(days=i)
                future_bookings = self.env['room.booking'].search([
                    ('checkin_date', '<=', future_date),
                    ('checkout_date', '>=', future_date),
                    ('state', 'in', ['confirmed', 'waiting', 'block'])
                ])
                expected_occupancy = (len(future_bookings) / len(hotel) * 100) if len(hotel) > 0 else 0
                expectations[future_date.strftime('%Y-%m-%d')] = round(expected_occupancy, 2)
            room_type_data = {}
            # ✅ Initialize the date range
            current_date = start_date

            # Create an empty dictionary for each date
            while current_date <= end_date:
                date_str = current_date.strftime('%Y-%m-%d')
                room_type_data[date_str] = {}  # ✅ Initialize with an empty dict for room types
                current_date += timedelta(days=1)

            # ✅ Process Bookings
            for booking in bookings:
                room = booking.hotel_room_type

                # ✅ Get Room Type Name if Exists
                if room:
                    room_type = self.env['room.type'].browse(room.id)
                    # print(room_type)

                    # ✅ Extract room type name from JSON if exists
                    if room_type.exists() and room_type.room_type:
                        room_data = room_type.room_type  # Can be JSON or direct string

                        # ✅ Check if it's a JSON (dictionary) or a direct string
                        if isinstance(room_data, dict):
                            room_name = room_data.get('en_US', 'Other')
                        elif isinstance(room_data, str):
                            room_name = room_data
                        else:
                            room_name = 'Other'
                    else:
                        room_name = 'Other'
                else:
                    room_name = 'Other'
                # print(room_name)
                # ✅ Count Room Types Only for Matching Check-in Dates
                checkin_date_str = booking.checkin_date.strftime('%Y-%m-%d')

                if checkin_date_str in room_type_data:
                    # ✅ Initialize dictionary for the date if it doesn't exist
                    if checkin_date_str not in room_type_data:
                        room_type_data[checkin_date_str] = {}

                    # ✅ Count the room type
                    room_type_data[checkin_date_str][room_name] = room_type_data[checkin_date_str].get(room_name, 0) + 1
            # ✅ Final Result
            # print(room_type_data)

            query = """
                    WITH parameters AS (
                        SELECT
                            %s::date AS from_date,
                            %s::date AS to_date
                    ),
                    date_series AS (
                        SELECT generate_series(p.from_date, p.to_date, INTERVAL '1 day')::date AS report_date
                        FROM parameters p
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
                          AND lls.report_date BETWEEN lls.checkin_date AND lls.checkout_date
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
                          AND lls.report_date - interval '1 day' BETWEEN lls.checkin_date AND lls.checkout_date
                        GROUP BY 
                            lls.report_date,
                            lls.company_id,
                            lls.room_type_id
                    ),
                    expected_arrivals AS (
                        SELECT
                            ds.report_date,
                            rc.id AS company_id,
                            rt.id AS room_type_id,
                            COUNT(DISTINCT bd.booking_line_id) AS expected_arrivals_count
                        FROM date_series ds
                        CROSS JOIN res_company rc
                        CROSS JOIN room_type rt
                        JOIN base_data bd
                          ON bd.company_id = rc.id
                          AND bd.room_type_id = rt.id
                          AND bd.checkin_date = ds.report_date
                          AND bd.status IN ('confirmed', 'block')
                        GROUP BY 
                            ds.report_date,
                            rc.id,
                            rt.id
                    ),
                    expected_departures AS (
                        SELECT
                            ds.report_date,
                            rc.id AS company_id,
                            rt.id AS room_type_id,
                            COUNT(DISTINCT bd.booking_line_id) AS expected_departures_count
                        FROM date_series ds
                        CROSS JOIN res_company rc
                        CROSS JOIN room_type rt
                        JOIN base_data bd
                          ON bd.company_id = rc.id
                          AND bd.room_type_id = rt.id
                          AND bd.checkout_date = ds.report_date
                          AND bd.status = 'check_in'
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
                              COALESCE(yh.in_house_count, 0) 
                              + COALESCE(ea.expected_arrivals_count, 0)
                              - LEAST(COALESCE(ed.expected_departures_count, 0), COALESCE(yh.in_house_count, 0))
                            ) AS expected_in_house
                        FROM date_series ds
                        CROSS JOIN res_company rc
                        CROSS JOIN room_type rt
                        LEFT JOIN inventory inv ON inv.company_id = rc.id AND inv.room_type_id = rt.id
                        LEFT JOIN out_of_order ooo ON ooo.company_id = rc.id AND ooo.room_type_id = rt.id AND ooo.report_date = ds.report_date
                        LEFT JOIN rooms_on_hold roh ON roh.company_id = rc.id AND roh.room_type_id = rt.id AND roh.report_date = ds.report_date
                        LEFT JOIN out_of_service oos ON oos.company_id = rc.id AND oos.room_type_id = rt.id AND oos.report_date = ds.report_date
                        LEFT JOIN in_house ih ON ih.company_id = rc.id AND ih.room_type_id = rt.id AND ih.report_date = ds.report_date
                        LEFT JOIN expected_arrivals ea ON ea.company_id = rc.id AND ea.room_type_id = rt.id AND ea.report_date = ds.report_date
                        LEFT JOIN expected_departures ed ON ed.company_id = rc.id AND ed.room_type_id = rt.id AND ed.report_date = ds.report_date
                        LEFT JOIN house_use_cte hc ON hc.company_id = rc.id AND hc.room_type_id = rt.id AND hc.report_date = ds.report_date
                        LEFT JOIN complementary_use_cte cc ON cc.company_id = rc.id AND cc.room_type_id = rt.id AND cc.report_date = ds.report_date
                        LEFT JOIN yesterday_in_house yh ON yh.company_id = rc.id AND yh.room_type_id = rt.id AND yh.report_date = ds.report_date
                    )
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
                      SUM(fr.in_house) AS in_house,
                      SUM(fr.expected_arrivals) AS expected_arrivals,
                      SUM(fr.expected_departures) AS expected_departures,
                      SUM(fr.house_use_count) AS house_use_count,
                      SUM(fr.complementary_use_count) AS complementary_use_count,
                      SUM(fr.available_rooms) AS available_rooms,
                      SUM(fr.expected_in_house) AS expected_in_house,
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
                      END AS free_to_sell,
                      GREATEST(0, SUM(fr.expected_in_house) - SUM(fr.available_rooms)) AS over_booked
                    FROM final_report fr
                    
                    --where fr.company_id = 43 and fr.report_date in ('2025-02-01', '2025-01-31') and fr.room_type_name = 'FAMS'
                    GROUP BY
                      fr.report_date,
                      fr.company_id,
                      fr.company_name,
                      fr.room_type_id,
                      fr.room_type_name
                    ORDER BY
                      fr.report_date,
                      fr.company_name,
                      fr.room_type_name;"""

            # Execute the SQL query
            self.env.cr.execute(query, (start_date, end_date))
            results = self.env.cr.fetchall()

            # Initialize dictionary to store aggregated results by report_date
            final_dict = {}

            # Iterate over the results and process them into the desired format
            for row in results:
                if row[1] != self.env.company.id:
                    continue
                report_date = str(row[0])  # Convert date to string to use as dictionary key
                data = {
                    'company_id': row[1],
                    'company_name': row[2],
                    'room_type_id': row[3],
                    'room_type_name': row[4],
                    'total_rooms': row[5],
                    'any_overbooking_allowed': row[6],
                    'overbooking_rooms': row[7],
                    'out_of_order': row[8],
                    'rooms_on_hold': row[9],
                    'out_of_service': row[10],
                    'in_house': row[11],
                    'expected_arrivals': row[12],
                    'expected_departures': row[13],
                    'house_use': row[14],
                    'complementary_use': row[15],
                    'available_rooms': row[16],
                    'expected_in_house': row[17],
                    'free_to_sell': row[18],
                    'over_booked': row[19]
                }

                # Calculate "Available" as: total_rooms - (out_of_order + house_use)
                data['available'] = max(0, data['total_rooms'] - (data['out_of_order'] + data['house_use']))

                # Append the processed data into the final dictionary
                # Append the processed data into the final dictionary
                if report_date not in final_dict:
                    final_dict[report_date] = {
                        'total_rooms': 0,
                        'overbooking_rooms': 0,
                        'out_of_order': 0,
                        'rooms_on_hold': 0,
                        'out_of_service': 0,
                        'in_house': 0,
                        'expected_arrivals': 0,
                        'expected_departures': 0,
                        'house_use': 0,
                        'complementary_use': 0,
                        'available_rooms': 0,
                        'expected_in_house': 0,
                        'free_to_sell': 0,
                        'over_booked': 0,
                        'available': 0
                    }

                # Aggregate the data for the same report_date
                for key in final_dict[report_date].keys():
                    if key in data:
                        final_dict[report_date][key] += data[key]

            # Prepare cumulative totals
            cumulative_inventory = {
                'totalRoom': 0,
                'outOfService': 0,
                'outOfOrder': 0,
                'houseUse': 0,
                'availability': 0
            }
            cumulative_forecast = {
                'InHouse': 0,
                'outOfService': 0,
                'outOfOrder': 0,
                'houseUse': 0,
                'availability': 0
            }
            cumulative_sales = {
                'overbooked': 0,
                'freeToSell': 0
            }

            # Aggregate totals
            for data in final_dict.values():
                cumulative_inventory['totalRoom'] += data['total_rooms']
                cumulative_inventory['outOfService'] += data['out_of_service']
                cumulative_inventory['outOfOrder'] += data['out_of_order']
                cumulative_inventory['houseUse'] += data['house_use']
                cumulative_inventory['availability'] += data['available']

                cumulative_forecast['InHouse'] += data['in_house']
                cumulative_forecast['outOfService'] += data['out_of_service']
                cumulative_forecast['outOfOrder'] += data['out_of_order']
                cumulative_forecast['houseUse'] += data['house_use']
                cumulative_forecast['availability'] += data['available']

                cumulative_sales['overbooked'] += data['over_booked']
                cumulative_sales['freeToSell'] += data['free_to_sell']

            # print(sales_data,forecast_data,forecast_data)
            response_data = {
                # Basic metrics
                'total': metrics['total'],
                'confirmed': metrics['confirmed'],
                'not_confirmed': metrics['not_confirmed'],
                'waiting': metrics['waiting'],
                'cancelled': metrics['cancelled'],
                'blocked': metrics['blocked'],
                'total_reservations': metrics['total_reservations'],
                'check_in': metrics['check_in'],
                'check_out': metrics['check_out'],
                
                # Occupancy chart data
                'occupancy_labels': occupancy_labels,
                'occupancy_data': occupancy_data,
                
                # Market segment chart data
                'segment_labels': list(segments.keys()),
                'segment_data': list(segments.values()),
                
                # Business source chart data
                'source_labels': list(sources.keys()),
                'source_data': list(sources.values()),
                
                # Expectations chart data
                'expectation_labels': list(expectations.keys()),
                'expectation_data': list(expectations.values()),

                # Country chart data
                'country_labels': list(countries.keys()),
                'country_data': list(countries.values()),

                # New arrival/departure data
                'arrival_labels': list(arrivals.keys()),
                'arrival_data': list(arrivals.values()),
                'departure_labels': list(departures.keys()),
                'departure_data': list(departures.values()),

                'room_type_data': room_type_data,
                'dashboard_data_inventory': final_dict,
                'inventoryData' : cumulative_inventory,
                'forecastData'  : cumulative_forecast,
                'salesData'     : cumulative_sales,
             }
            
            # _logger.info('Returning dashboard data: %s', response_data)
            return response_data
            
        except Exception as e:
            _logger.error('Error fetching dashboard data: %s', str(e), exc_info=True)
            return {
                'error': str(e),
                'total': 0,
                'confirmed': 0,
                'not_confirmed': 0,
                'waiting': 0,
                'cancelled': 0,
                'blocked': 0,
                'total_reservations': 0,
                'country_labels': [],
                'country_data': []
            }
