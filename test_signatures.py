import inspect
from odoo.addons.base.models import ir_ui_view
from odoo.models import BaseModel

print("search_panel_select_range signature:", inspect.signature(BaseModel.search_panel_select_range))
print("search_panel_select_multi_range signature:", inspect.signature(BaseModel.search_panel_select_multi_range))
