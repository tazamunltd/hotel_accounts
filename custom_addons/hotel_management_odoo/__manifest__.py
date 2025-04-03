# -*- coding: utf-8 */
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
    'depends': ['account', 'event', 'fleet', 'lunch', 'base', 'setup_configuration', 'web'],
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
        # 'views/dashboard_view.xml',
        'wizard/room_booking_detail_views.xml',
        'wizard/sale_order_detail_views.xml',
        'views/reporting_views.xml',
        # 'views/report_template.xml',
        'views/room_result_byclient_view.xml',
        'views/room_result_by_room_type.xml',
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
        'data/waiting_list_cron.xml',
        'data/send_reminder_mail_job.xml',
        'views/housekeeping_maintenance_inherit.xml',
        # 'security/hotel_security.xml',
        'views/monthly_groups_charts.xml',
        'views/reservation_status_report_views.xml',
        'views/deleted_reservation_report_views.xml',
        'views/meals_forecast_report.xml',
        'views/market_segement_forecast_views.xml',
        'views/company_forecast.xml',
        'views/source_of_buisness_forecast_views.xml',
        'views/meals_by_nationality_views.xml',
        'views/rooms_forecast_views.xml',
        'views/revenue_forecast_views.xml',
        'views/reservation_summary_report.xml',
        'views/all_reservation_status_report.xml',
        # HEADER DATETIME
        # 'views/header_datetime.xml',
        'views/new_dashboard_views.xml',
        'views/new_dashboard_action.xml',  # Added new dashboard action - 2025-01-20T00:16:16
        # 'views/templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Date: 2025-01-20 Time: 13:25:51 - Using shared Chart.js for both dashboards
            # Core web client dependencies
            '/web/static/src/webclient/webclient.js',
            '/web/static/src/webclient/webclient.xml',
            
            # Chart.js library from static assets
            '/hotel_management_odoo/static/src/lib/chart.js/chart.umd.js',
            
            # Dashboard files that depend on Chart.js
            '/hotel_management_odoo/static/src/js/dashboard_action.js',
            '/hotel_management_odoo/static/src/js/new_dashboard_action.js',
            
            # Module specific assets
            'hotel_management_odoo/static/src/css/dashboard.css',
            'hotel_management_odoo/static/src/css/disable.css',
            'hotel_management_odoo/static/src/css/timer.css',
            'hotel_management_odoo/static/css/hotel_booking_styles.css',
            
            # JavaScript files
            'hotel_management_odoo/static/src/js/generate_pdf_report.js',
            'hotel_management_odoo/static/src/js/action_manager.js',
            'hotel_management_odoo/static/src/js/offline_search_widget.js',
            'hotel_management_odoo/static/src/js/system_date_notification_service.js',
            'hotel_management_odoo/static/src/js/offline_search_widget_registry.js',
            'hotel_management_odoo/static/src/js/generate_rc_guest_pdf_report.js',
            'hotel_management_odoo/static/src/js/generate_rc_pdf_report.js',
            'hotel_management_odoo/static/src/js/timer.js',
            
            # XML templates
            'hotel_management_odoo/static/src/xml/offline_search_widget.xml',
            'hotel_management_odoo/static/src/xml/dashboard_templates.xml',
            'hotel_management_odoo/static/src/xml/timer.xml',
            'hotel_management_odoo/static/src/xml/new_dashboard_templates.xml',

            'hotel_management_odoo/static/src/views/*.js',
            'hotel_management_odoo/static/src/**/*.xml',

            'hotel_management_odoo/static/src/views/hotel_room_result.js',
            'hotel_management_odoo/static/src/views/templates.xml',
            'hotel_management_odoo/static/src/js/plotly_min.js',
            'hotel_management_odoo/static/src/xml/delete_with_notification.xml',
            'hotel_management_odoo/static/src/js/delete_with_notification.js',


        ],
    },
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
