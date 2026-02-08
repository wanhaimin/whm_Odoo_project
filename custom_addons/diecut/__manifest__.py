# -*- coding: utf-8 -*-
{
    'name': '模切管理系统',
    'version': '1.0',
    'category': 'Manufacturing',
    'summary': '模切管理系统',
    'depends': ['base', 'product', 'sale', 'purchase', 'stock', 'website', 'mail'],
    "data": [
        "data/ir_sequence_data.xml",
        "data/mail_template_data.xml",
        "data/sequence.xml",
        "data/product_category_data.xml",
        "security/ir.model.access.csv",
        
        "views/my_material_base_views.xml",
        "report/diecut_mold_reports.xml",
        "views/diecut_quote_views.xml",
        "views/requisition_views.xml",
        "views/slitting_views.xml",
        "views/mold_views.xml",
        "views/mold_search_view.xml",
        "views/mold_location_views.xml",
        "views/mold_scrap_wizard_view.xml",
        "views/mold_qc_wizard_view.xml",
        "views/purchase_order_inherit_view.xml",
        "views/stock_quant_views.xml",

        "views/res_partner_view.xml",
        "views/sale_order_inherit_view.xml",
        "views/sample_order_view.xml",
        "views/website_templates.xml",
        "views/product_category_view.xml",
        "views/diecut_menu_view.xml"
    ],
    'assets': {
        'web.assets_backend': [
            'diecut/static/src/scss/custom_font.scss',
            'diecut/static/src/scss/hierarchy_view.scss',
            'diecut/static/src/scss/list_view_hover.scss',
            'diecut/static/src/js/enter_to_next.js',
        ],
    },
    'external_dependencies': {
        'python': ['qrcode'],
    },
    'installable': True,
    'application': True,
}
