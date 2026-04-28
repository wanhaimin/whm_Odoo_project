# -*- coding: utf-8 -*-
{
    'name': '中国财税管理（多公司）',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': '补充小规模/一般纳税人税率，提供增值税申报和企业所得税预缴向导',
    'author': 'Custom',
    'depends': ['l10n_cn', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'wizard/vat_declaration_views.xml',
        'wizard/cit_prepayment_views.xml',
        'wizard/cn_balance_sheet_views.xml',
        'wizard/cn_profit_loss_views.xml',
        'report/cn_financial_report_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'translations': ['i18n/zh_CN.po'],
}
