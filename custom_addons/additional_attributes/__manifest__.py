# -*- coding: utf-8 -*-
{
    'name': "Additional Attributes",

    'summary': "Manage additional attributes for various entities with customizable fields",

    'description': """
        The Additional Attributes module allows users to define and manage attributes and its abbrevation  and arabic abbraviations
    """,

    'author': "Neomoment AIOT",
    'website': "https://www.neomoment.org",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'views/ir_sequence_data.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    
    'images': ['static/description/banner.jpg'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}

