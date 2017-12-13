# -*- coding: utf-8 -*-
{
    'name': "Ju Young Attendance Report",

    'summary': """
        Ju Young Attendance Report
        """,

    'description': """
        
    """,

    'author': "Feosco",
    'website': "http://www.feosco.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'HR',
    'version': '10.0.1',

    # any module necessary for this one to work correctly
    'depends': ['hr','hr_attendance','hr_holidays','jy_attendance_base','jy_attendance_ot'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        # 'views/res_config_view.xml',
        'views/templates.xml',
    ],
    'qweb':[
        'static/src/xml/qweb.xml'
    ],
    # only loaded in demonstration mode
}