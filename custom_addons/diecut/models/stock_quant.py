from odoo import models, fields, api

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    dimension_spec = fields.Char(string='规格(T*W*L)', compute='_compute_dimension_spec', store=True)

    @api.depends('product_id.thickness', 'product_id.width', 'product_id.length', 
                 'lot_id.material_width', 'lot_id.material_length')
    def _compute_dimension_spec(self):
        for record in self:
            spec = ""
            product = record.product_id
            if not product:
                record.dimension_spec = spec
                continue

            # 0. 仅针对原材料显示 (过滤办公用品、成品等)
            # 使用 getattr 安全获取，因为 is_raw_material 是在 custom模块定义的
            if not getattr(product, 'is_raw_material', False):
                record.dimension_spec = ""
                continue

            # 尝试获取模切相关属性，如果产品没有这些字段（非模切产品），则跳过
            # 使用 getattr 安全获取，避免 AttributeError
            thickness = getattr(product, 'thickness', None)
            
            # 只有当 thickness 存在时（说明是模切相关产品），才进行计算
            if thickness is not None:
                def fmt(v):
                    return f"{v:g}"

                # 1. 确定 T (厚度) - 始终来自产品
                t = thickness or 0
                
                # 2. 确定 W (宽度) 和 L (长度) - 优先取批次，否则取产品
                lot = record.lot_id
                
                # 尝试从批次获取宽度/长度 (定义在 slitting.py)
                lot_w = getattr(lot, 'material_width', 0.0)
                lot_l = getattr(lot, 'material_length', 0.0)
                
                prod_w = getattr(product, 'width', 0.0) or 0.0
                prod_l = getattr(product, 'length', 0.0) or 0.0
                
                w = lot_w if lot_w > 0 else prod_w
                l = lot_l if lot_l > 0 else prod_l
                
                # 3. 确定显示格式 (卷/片)
                rs_type = getattr(product, 'rs_type', 'R')
                
                if rs_type == 'S':
                    # Sheet: L 显示为 mm
                    l_disp = l * 1000.0
                    spec = f"{fmt(t)}*{fmt(w)}*{fmt(l_disp)}"
                else:
                    # Roll: L 显示为 m
                    spec = f"{fmt(t)}*{fmt(w)}*{fmt(l)}"
            
            record.dimension_spec = spec
