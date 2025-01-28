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
            
            # Calculate metrics
            metrics = {
                'total': len(bookings),
                'confirmed': len(bookings.filtered(lambda b: b.state == 'confirmed')),
                'not_confirmed': len(bookings.filtered(lambda b: b.state == 'not_confirmed')),
                'waiting': len(bookings.filtered(lambda b: b.state == 'waiting')),
                'cancelled': len(bookings.filtered(lambda b: b.state == 'cancel')),
                'blocked': len(bookings.filtered(lambda b: b.state == 'block'))
            }
            
            # Calculate total reservations (confirmed + blocked + waiting)
            metrics['total_reservations'] = (
                metrics['confirmed'] + 
                metrics['blocked'] + 
                metrics['waiting']
            )
            
            # print(metrics)
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
                segment = booking.market_segment or 'Other'
                if segment != 'Other':  # If it's already a string
                    market_segment = self.env['market.segment'].browse(segment.id)

                    if market_segment.exists():  # Check if the record exists
                        segment = market_segment.market_segment or 'Other'
                # print(segment)
                segments[segment] = segments.get(segment, 0) + 1
            
            # Calculate business sources
            sources = {}
            for booking in bookings:
                source = booking.source_of_business or 'Other'
                if source != 'Other':  # If it's already a string
                    source = self.env['source.business'].browse(source.id)

                    if source.exists():  # Check if the record exists
                        source = source.source or 'Other'

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
            
            response_data = {
                # Basic metrics
                'total': metrics['total'],
                'confirmed': metrics['confirmed'],
                'not_confirmed': metrics['not_confirmed'],
                'waiting': metrics['waiting'],
                'cancelled': metrics['cancelled'],
                'blocked': metrics['blocked'],
                'total_reservations': metrics['total_reservations'],
                
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
                'expectation_data': list(expectations.values())
            }
            
            _logger.info('Returning dashboard data: %s', response_data)
            return response_data
            
        except Exception as e:
            _logger.error('Error fetching dashboard data: %s', str(e))
            return {
                'error': str(e),
                'total': 0,
                'confirmed': 0,
                'not_confirmed': 0,
                'waiting': 0,
                'cancelled': 0,
                'blocked': 0,
                'total_reservations': 0
            }
