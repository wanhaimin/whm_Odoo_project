{
    'name': 'PDF Preview Fix',
    'version': '1.0',
    'category': 'Hidden',
    'summary': 'Fix PDF preview in Docker environments',
    'description': """
        Forces PDF viewer to use simple loading instead of range requests which fail in some Docker setups.
    """,
    'depends': ['web'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'web_pdf_preview_fix/static/src/js/pdf_viewer_fix.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
