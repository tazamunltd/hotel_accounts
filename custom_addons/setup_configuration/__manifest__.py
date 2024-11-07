# -*- coding: utf-8 -*-
{
    'name': "setup_configuration",

    'summary': "Short (1 phrase/line) summary of the module's purpose",

    'description': """
Long description of module's purpose
    """,

    'author': "My Company",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','fieldservice'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'views/menu.xml',
        'views/front_desk_menu.xml',
        'views/front_desk_views.xml',
        'views/cashier_menu.xml',
        'views/cashier_views.xml',
        'views/profile_code_menu.xml',
        'views/profile_code_views.xml',
        'views/codes_menu.xml',
        'views/codes_views.xml',
        'views/reservation_menu.xml',
        'views/reservation_profile_views.xml',
        'views/group_profile.xml',
        'views/reservation_reservations.xml',
        'views/reservation_trace_views.xml',
        'views/misc_menu.xml',
        'views/front_desk_main_menu.xml',
        'views/front_desk_walkin_views.xml',
        'views/front_desk_inhouse.xml',
        'views/misc_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

