from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_name = fields.Char(string='对应项目', help="例如：华为P70模切专案")
    is_urgent = fields.Boolean(string='是否加急', default=False)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # 新增采购专属宽、长、和卷数
    product_spec = fields.Char(string='规格')
    purchase_rolls = fields.Float(string='件/卷数', default=1.0, digits='Product Unit of Measure')
    purchase_width = fields.Float(string='宽度(mm)', digits=(16, 2))
    purchase_length = fields.Float(string='长度(m)', digits=(16, 2))
    is_diecut_material = fields.Boolean(related='product_id.is_raw_material', store=False)

    @api.onchange('product_id')
    def _onchange_product_id_set_dimensions(self):
        if self.product_id and self.product_id.is_raw_material:
            self.purchase_width = self.product_id.width or 0.0
            # 后台的 product.template.length 统一为 m
            self.purchase_length = self.product_id.length or 0.0
            self.purchase_rolls = 1.0

    @api.onchange('purchase_width', 'purchase_length', 'purchase_rolls', 'product_id')
    def _onchange_dimensions_compute_qty_and_price(self):
        """核心成本计算逻辑：库存按平米计价"""
        if self.product_id and self.product_id.is_raw_material:
            w_m = self.purchase_width / 1000.0
            l_m = self.purchase_length
            area_per_roll = w_m * l_m
            
            # 1. 强制将采购明细行的单价设置为产品的“平米标准单价”
            if self.product_id.raw_material_price_m2 > 0:
                self.price_unit = self.product_id.raw_material_price_m2
                
            # 2. 将 Odoo 真正识别的“采购总数量 (product_qty)” 设置为：卷数 * 单卷平米数
            # 这样入库时，仓库看到的库存永远是“纯洁的平米数”，财务核算也完美基于它。
            total_m2 = area_per_roll * self.purchase_rolls
            if total_m2 > 0:
                self.product_qty = total_m2

    @api.onchange('purchase_width', 'purchase_length', 'purchase_rolls')
    def _update_product_spec_text(self):
        if self.product_id and self.product_id.is_raw_material:
            t = self.product_id.thickness or 0
            w = self.purchase_width or 0
            l_val = self.purchase_length or 0
            # 更新可读的描述 (带上数量)
            self.product_spec = f"[{self.purchase_rolls}卷] {t:g}T * {w:g}mm * {l_val:g}m"

    def _prepare_stock_moves(self, picking):
        res = super()._prepare_stock_moves(picking)
        for val in res:
            val['material_width'] = self.purchase_width
            val['material_length'] = self.purchase_length
        return res
