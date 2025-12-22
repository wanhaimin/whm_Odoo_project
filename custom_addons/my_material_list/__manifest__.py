{
    'name': 'Material List',
    'version': '1.0',
    'summary': 'Manage Raw Materials and Specifications',
    'description': """
        Module to manage material list based on Excel requirements.
        Fields: Name, Category, Vendor, Spec, Thickness, Width, Length, UoM, Unit Price.
    """,
    'category': 'mrp',
    'author': 'Odoo Assistant',
    'depends': ['base', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/my.material.category.csv',
        'views/category_views.xml',
        'views/material_views.xml',
        'views/requisition_views.xml',
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
