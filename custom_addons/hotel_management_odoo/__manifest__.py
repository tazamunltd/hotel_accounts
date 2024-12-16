# -*- coding: utf-8 -*-
###############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Vishnu K P (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
{
    'name': 'Odoo17 Hotel Management',
    'version': '17.0.1.1.4',
    'category': 'Services',
    'summary': """Hotel Management, Odoo Hotel Management, Hotel, Room Booking odoo, Amenities Odoo, Event management, Rooms, Events, Food, Booking, Odoo Hotel, Odoo17, Odoo Apps""",
    'description': """The module helps you to manage rooms, amenities, 
     services, food, events and vehicles. End Users can book rooms and reserve 
     foods from hotel.""",
    'author': 'Cybrosys Techno Solutions',
    'company': 'Cybrosys Techno Solutions',
    'maintainer': 'Cybrosys Techno Solutions',
    'website': 'https://www.cybrosys.com',
    'depends': ['account', 'event', 'fleet', 'lunch', 'base', 'setup_configuration'],
    'data': [
        'security/hotel_management_odoo_groups.xml',
        # 'security/hotel_management_odoo_security.xml',
        'security/ir.model.access.csv',
        'data/ir_data_sequence.xml',
        'views/account_move_views.xml',
        'views/hotel_menu_views.xml',
        'views/hotel_amenity_views.xml',
        'views/hotel_service_views.xml',
        'views/hotel_floor_views.xml',
        'views/hotel_room_views.xml',
        'views/lunch_product_views.xml',
        'views/fleet_vehicle_model_views.xml',
        'views/room_booking_views.xml',
        # 'views/maintenance_team_views.xml',
        # 'views/maintenance_request_views.xml',
        'views/cleaning_team_views.xml',
        'views/cleaning_request_views.xml',
        'views/food_booking_line_views.xml',
        'views/dashboard_view.xml',
        'wizard/room_booking_detail_views.xml',
        'wizard/sale_order_detail_views.xml',
        'views/reporting_views.xml',
        'views/report_template.xml',
        'views/room_result_by_room_type.xml',
        'views/room_result_byclient_view.xml',
        'report/room_booking_reports.xml',
        'report/sale_order_reports.xml',
        'views/hotel_view.xml',
        # 'views/res_partner_agent_view.xml',
        'views/group_booking.xml',
        'views/conpany.xml',
        # 'views/rate_code.xml',
        'views/inherited_views.xml',
        'views/maintenance_request_inherit.xml',
        # 'views/fsm_location_views.xml',
        'views/room_result_view.xml',
        'views/room_rate_forecast.xml',
        'views/yearly_geographical_chart_views.xml',
        'views/monthly_allotment_charts_views.xml',
        # 'data/cron_job.xml',
        'data/room_booking_cron.xml',
        'views/housekeeping_maintenance_inherit.xml',
        # 'security/hotel_security.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hotel_management_odoo/static/src/js/action_manager.js',
            'hotel_management_odoo/static/src/css/dashboard.css',
            'hotel_management_odoo/static/src/js/dashboard_action.js',
            'hotel_management_odoo/static/src/xml/dashboard_templates.xml',
            # 'hotel_management_odoo/static/src/css/booking_styles.css',
            # 'hotel_management_odoo/static/src/js/room_booking_buttons.js',
            # 'hotel_management_odoo/static/src/xml/room_booking_buttons.xml',
            'hotel_management_odoo/static/src/views/*.js',
            'hotel_management_odoo/static/src/**/*.xml',
            'hotel_management_odoo/static/css/hotel_booking_styles.css',
            'hotel_management_odoo/static/src/css/disable.css',
        ],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
