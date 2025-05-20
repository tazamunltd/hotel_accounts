# -*- coding: utf-8 -*-

{
    'name': "Tazamun Front Office Management",

    'summary': """
        Comprehensive front office system for managing reservations, check-ins, check-outs, and daily hotel operations.
    """,

    'description': """
        The Tazamun Front Office Management module is a robust solution designed to streamline hotel operations, including reception, accounting, and daily management tasks. It provides a unified interface for front-desk staff to efficiently handle reservations, guest check-ins, check-outs, and financial transactions.

        Key Features:
        - **Reservation Management**: Create and administer reservations for walk-in guests and in-house stays. Immediate check-ins can be performed from a single interface.
        - **Guest Check-In/Check-Out**: Monitor in-house stays, manage check-out procedures, and settle guest accounts seamlessly.
        - **Financial Transactions**: Handle manual and automatic postings, ensuring accurate financial records.
        - **Daily Operations**: Perform end-of-day closing and date rollover to maintain operational efficiency.
        - **Group and Dummy Accounts**: Manage group accounts (Master Rooms) and dummy accounts (Dummy Rooms) for flexible room allocation.
        - **Real-Time Room Status**: Monitor room availability and status in real-time through the Rooms Rack, enabling on-the-fly actions.
        - **Guest Profiles**: Link guest and companion details to existing profiles or create new profiles as needed.
        - **Billing Integration**: Integrate with the billing module to display reservation cost breakdowns and ensure accurate invoicing.

        The module ensures that:
        - New reservations are created with unique Reservation IDs.
        - Rooms are marked as occupied upon check-in.
        - Guest details are accurately recorded and linked to profiles.
        - Financial transactions are tracked and posted correctly.

        Designed for efficiency and ease of use, this module empowers front-desk staff to deliver exceptional guest experiences while maintaining operational excellence.
    """,

    'author': "Tazamun",
    'website': "https://www.tazamun.com.sa",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Tazamun',
    'installable': True,
    'auto_install': False,
    'application': True,
    'version': '0.1',
    'license': 'OEEL-1',

    # any module necessary for this one to work correctly
    'depends': ['hotel_management_odoo'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'data/ir_data_sequence.xml',
        'views/front_desk_room_booking_views.xml',
        'views/tz_manual_posting_views.xml',
        'views/tz_master_folio_views.xml',
        # 'views/dummy_group_views.xml',
        'wizard/tz_auto_posting_views.xml',
        'report/report_master_folio.xml',
    ],
}
