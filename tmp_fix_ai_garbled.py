
from odoo import api, SUPERUSER_ID
from odoo.tools import config
from odoo import registry

db='odoo'
with registry(db).cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    Cat = env['diecut.catalog.param.category'].sudo()
    Param = env['diecut.catalog.param'].sudo()
    fixes = {
        '?????': '?????',
        '????': '????',
        '??': '????',
    }
    for rec in Cat.search([]):
        if rec.name in fixes:
            rec.write({'name': fixes[rec.name]})
    param_fixes = {
        'shelf_life_storage': '??????',
        'liner_option_sc2': '?????-SC2',
        'liner_option_pet': '?????-PET',
        'pluck_testing': '????',
        'torque_testing': '????',
    }
    for key, name in param_fixes.items():
        rec = Param.search([('param_key', '=', key)], limit=1)
        if rec:
            rec.write({'name': name, 'canonical_name_zh': name})
    SpecDef = env['diecut.catalog.spec.def'].sudo()
    Line = env['diecut.catalog.item.spec.line'].sudo()
    for key, name in param_fixes.items():
        SpecDef.search([('param_key', '=', key)]).write({'name': name})
        Line.search([('param_key', '=', key)]).write({'param_name': name})
    cr.commit()
    print('fixed')
