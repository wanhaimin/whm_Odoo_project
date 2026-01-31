# -*- coding: utf-8 -*-
{
    'name': 'diecut_custom',
    'version': '1.0',
    'category': 'Manufacturing',
    'summary': '模切行业报价管理',
    'depends': ['base', 'product', 'sale', 'purchase', 'website', 'mail', 'my_material_list'],
    "data": [
        "data/ir_sequence_data.xml",
        "data/mail_template_data.xml",
        "data/sequence.xml",
        "security/ir.model.access.csv",
        "report/diecut_mold_reports.xml",
        "views/diecut_quote_view.xml",
        "views/material_category_view.xml",
        "views/material_view.xml",
        "views/mold_views.xml",
        "views/my_material_inherit_view.xml",
        "views/purchase_order_inherit_view.xml",
        "views/res_partner_view.xml",
        "views/sale_order_inherit_view.xml",
        "views/sample_order_view.xml",
        "views/website_templates.xml",
        "views/diecut_menu_view.xml"
    ],
    'assets': {
        'web.assets_backend': [
            'diecut_custom/static/src/scss/custom_font.scss',
        ],
    },
    'installable': True,
    'application': True,
}
