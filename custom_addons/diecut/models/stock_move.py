from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    material_width = fields.Float(string='宽度(mm)')
    material_length = fields.Float(string='长度(m)')


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    # 允许在收货明细行里手动确认并修改宽度和长度
    material_width = fields.Float(string='收到宽度(mm)', compute='_compute_material_dims', store=True, readonly=False)
    material_length = fields.Float(string='收到长度(m)', compute='_compute_material_dims', store=True, readonly=False)

    @api.depends('move_id.material_width', 'move_id.material_length')
    def _compute_material_dims(self):
        for line in self:
            if not line.material_width and line.move_id.material_width:
                line.material_width = line.move_id.material_width
            if not line.material_length and line.move_id.material_length:
                line.material_length = line.move_id.material_length

    # 拦截 Odoo 原生从 line 创建 lot 的字典构建方法，Odoo 17 以后使用 actions 创建时可能不是这个，
    # 但如果是基于 `lot_name` 直接 create 的，我们需要另外处理
    def write(self, vals):
        res = super().write(vals)
        # 如果填写了批次号（产生了 lot_id）或者本身就在收货，我们可以同步更新 lot
        for line in self:
            if line.lot_id and (line.material_width or line.material_length):
                lot_vals = {}
                if line.material_width and not line.lot_id.material_width:
                    lot_vals['material_width'] = line.material_width
                if line.material_length and not line.lot_id.material_length:
                    lot_vals['material_length'] = line.material_length
                if lot_vals:
                    line.lot_id.write(lot_vals)
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.lot_id and (line.material_width or line.material_length):
                lot_vals = {}
                if line.material_width and not line.lot_id.material_width:
                    lot_vals['material_width'] = line.material_width
                if line.material_length and not line.lot_id.material_length:
                    lot_vals['material_length'] = line.material_length
                if lot_vals:
                    line.lot_id.write(lot_vals)
        return lines
