
from odoo import api, SUPERUSER_ID
from odoo import registry

db='odoo'
with registry(db).cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    rec = env['diecut.catalog.source.document'].sudo().create({
        'name': '??????',
        'source_type': 'manual',
        'raw_text': '3M DC2000
DC2005 0.51 mm black acrylic foam acrylic adhesive
DC2008 0.76 mm black acrylic foam acrylic adhesive',
    })
    rec.action_generate_draft()
    print(rec.import_status)
    print(bool(rec.draft_payload))
    print(rec.parse_version)
    cr.rollback()
