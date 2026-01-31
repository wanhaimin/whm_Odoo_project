{
    'name': '材料清单',
    'version': '1.0',
    'summary': '管理原材料和规格 ',
    'description': """
        基于Excel需求管理的材料清单模块。
        字段：名称，类别，供应商，规格，厚度，宽度，长度，单位，单价。
    """,
    'category': 'mrp',
    'author': 'Odoo Assistant',
    'depends': ['base', 'account', 'mail', 'stock'],
    "data": [
        "data/my.material.category.csv",
        "data/sequence.xml",
        "data/sync_cron.xml",
        "security/ir.model.access.csv",
        "views/category_views.xml",
        "views/material_views.xml",
        "views/slitting_views.xml",
        "views/requisition_views.xml",
        "reports/my_material_report.xml"
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
    'assets': {
        'web.assets_backend': [
            'my_material_list/static/src/css/material_list.css',
            'my_material_list/static/src/js/table_width_controller.js',
            'my_material_list/static/src/js/enter_navigation.js',
        ],
    },
}
