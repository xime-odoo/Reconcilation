# -*- coding: utf-8 -*-
{
    'name': "custom/xime/addons/zb_sbl_bank_reconciliation",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '15.0',

    # any module necessary for this one to work correctly
    'depends': ['account'],

    # always loaded
    'data': [
        'security/reconcilation_security.xml',
        'security/ir.model.access.csv',
        'views/quick_reconcile_view.xml',
        # 'views/reconcile_history_view.xml',
    ],
}
