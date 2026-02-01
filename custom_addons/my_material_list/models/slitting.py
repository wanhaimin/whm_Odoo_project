from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError

class StockLot(models.Model):
    _inherit = 'stock.lot'

    # 扩展批次信息，记录该卷材料的具体规格
    material_width = fields.Float(string='宽度 (mm)', digits=(16, 2))
    material_length = fields.Float(string='长度 (m)', digits=(16, 2))
    parent_lot_id = fields.Many2one('stock.lot', string='原卷批次', help="如果是由大卷分切而来，记录原卷")

class MaterialSlittingOrder(models.Model):
    _name = 'my.material.slitting'
    _description = '材料分切单'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='单号', required=True, copy=False, readonly=True, default='New')
    
    # 来源信息
    product_id = fields.Many2one('product.product', string='产品', required=True, domain="[('tracking', 'in', ['lot', 'serial'])]")
    
    # Allow searching lot without product first (remove static domain relying on product_id)
    # We will control domain via onchange or keep it flexible in XML
    source_lot_id = fields.Many2one('stock.lot', string='源批次', required=True, 
                                  domain="[('quant_ids.quantity', '>', 0)]")
    
    source_qty = fields.Float(string='源卷数量', compute='_compute_source_info', store=True) # store=True for easier debugging/search? No, keep it computed.
    source_width = fields.Float(string='源卷宽度', related='source_lot_id.material_width')
    source_length = fields.Float(string='源卷长度', related='source_lot_id.material_length')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            return {'domain': {'source_lot_id': [('product_id', '=', self.product_id.id), ('quant_ids.quantity', '>', 0)]}}
        else:
            return {'domain': {'source_lot_id': [('quant_ids.quantity', '>', 0)]}}

    @api.onchange('source_lot_id')
    def _onchange_source_lot_id(self):
        if self.source_lot_id:
            if not self.product_id or self.product_id != self.source_lot_id.product_id:
                self.product_id = self.source_lot_id.product_id
            
            # Also try to auto-set location if possible
            quants = self.source_lot_id.quant_ids.filtered(lambda q: q.quantity > 0 and q.location_id.usage == 'internal')
            if quants:
                self.location_id = quants[0].location_id

    # 仓库信息
    def _default_warehouse_id(self):
        warehouse = getattr(self.env.user, 'property_warehouse_id', None)
        if not warehouse:
            warehouse = self.env['stock.warehouse'].search([], limit=1)
        return warehouse

    warehouse_id = fields.Many2one('stock.warehouse', string='仓库', required=True, default=_default_warehouse_id)
    location_id = fields.Many2one('stock.location', string='源位置', required=True, domain="[('usage', '=', 'internal')]")
    location_dest_id = fields.Many2one('stock.location', string='目标位置', required=True, domain="[('usage', '=', 'internal')]")

    # 分切明细
    line_ids = fields.One2many('my.material.slitting.line', 'slitting_id', string='分切明细')
    
    state = fields.Selection([
        ('draft', '草稿'),
        ('done', '已完成'),
    ], string='状态', default='draft', tracking=True)

    @api.depends('source_lot_id', 'location_id')
    def _compute_source_info(self):
        for record in self:
            if record.source_lot_id and record.location_id:
                quants = self.env['stock.quant'].search([
                    ('lot_id', '=', record.source_lot_id.id),
                    ('location_id', '=', record.location_id.id),
                    ('product_id', '=', record.product_id.id)
                ])
                record.source_qty = sum(q.quantity for q in quants)
            else:
                record.source_qty = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('my.material.slitting') or 'New'
        return super().create(vals_list)

    def action_confirm_slitting(self):
        """执行分切：扣减库存，生成新库存（含余料）"""
        self.ensure_one()
        
        # 强制刷新缓存，确保获取最新的库存数量
        self.invalidate_recordset(['source_qty'])
        if self.source_qty <= 0:
            raise UserError(_(f"源批次 {self.source_lot_id.name or ''} 在位置 {self.location_id.display_name} 的在手数量为 0，无法执行分切。"))

        if not self.line_ids:
            raise UserError("请添加分切明细")

        # 获取生产位置
        production_location = self.env['stock.location'].search([
            ('usage', '=', 'production'),
            ('company_id', 'in', [self.env.company.id, False])
        ], limit=1)
        if not production_location:
            raise UserError(_("未找到虚拟生产位置，请联系管理员配置。"))

        # 校验宽度 (Check width)
        total_cut_width = 0
        for line in self.line_ids:
            if line.target_width <= 0:
                 raise UserError(_(f"分切明细行存在无效宽度 {line.target_width}，宽度必须大于0。"))
            if line.quantity <= 0:
                 raise UserError(_("分切卷数必须至少为 1。"))
            total_cut_width += line.target_width * line.quantity

        if total_cut_width > self.source_width:
             raise UserError(_(f"分切总宽度 ({total_cut_width}) 超过了源卷宽度 ({self.source_width})"))

        # 1. 消耗源库存 (Stock Move Out)
        consume_qty = self.source_qty 
        
        move_out_vals = {
            'description_picking': f'Slitting Consume: {self.name}',
            'origin': self.name,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_id.id,
            'product_uom_qty': consume_qty,
            'location_id': self.location_id.id,
            'location_dest_id': production_location.id,
            'company_id': self.env.company.id,
            'picked': True,
            'move_line_ids': [Command.create({
                'company_id': self.env.company.id,
                'product_id': self.product_id.id,
                'product_uom_id': self.product_id.uom_id.id,
                'quantity': consume_qty,
                'lot_id': self.source_lot_id.id,
                'location_id': self.location_id.id,
                'location_dest_id': production_location.id,
                'picked': True
            })]
        }
        
        move_out = self.env['stock.move'].create(move_out_vals)
        move_out._action_confirm()
        move_out._action_done()

        # 2. 生成新库存 (Stock Move In)
        common_lot_vals = {
            'product_id': self.product_id.id,
            'material_length': self.source_length, 
            'parent_lot_id': self.source_lot_id.id,
            'company_id': self.env.company.id,
        }

        # 2.1 处理分切行
        for line in self.line_ids:
            for i in range(line.quantity):
                new_lot = self.env['stock.lot'].create(dict(common_lot_vals, **{
                    'name': self.env['ir.sequence'].next_by_code('stock.lot.serial'),
                    'material_width': line.target_width,
                }))
                self._create_move_in(new_lot, production_location)

        # 2.2 处理余料 (Remainder)
        remainder_width = self.source_width - total_cut_width
        if remainder_width > 0:
            remainder_lot = self.env['stock.lot'].create(dict(common_lot_vals, **{
                'name': self.env['ir.sequence'].next_by_code('stock.lot.serial'),
                'material_width': remainder_width,
                'ref': 'Remainder/尾料', 
            }))
            self._create_move_in(remainder_lot, production_location)

        self.state = 'done'

    def _create_move_in(self, lot_record, production_location):
        """辅助函数：创建入库移动"""
        move_in_vals = {
            'description_picking': f'Slitting Produce: {self.name}',
            'origin': self.name,
            'product_id': self.product_id.id,
            'product_uom': self.product_id.uom_id.id,
            'product_uom_qty': 1.0,
            'location_id': production_location.id,
            'location_dest_id': self.location_dest_id.id,
            'company_id': self.env.company.id,
            'picked': True,
            'move_line_ids': [Command.create({
                'company_id': self.env.company.id,
                'product_id': self.product_id.id,
                'product_uom_id': self.product_id.uom_id.id,
                'quantity': 1.0,
                'lot_id': lot_record.id,
                'location_id': production_location.id,
                'location_dest_id': self.location_dest_id.id,
                'picked': True
            })]
        }
        move_in = self.env['stock.move'].create(move_in_vals)
        move_in._action_confirm()
        move_in._action_done()


class MaterialSlittingLine(models.Model):
    _name = 'my.material.slitting.line'
    _description = '分切明细行'

    slitting_id = fields.Many2one('my.material.slitting', string='分切单')
    target_width = fields.Float(string='目标宽度 (mm)', required=True)
    quantity = fields.Integer(string='卷数', default=1) 
    
    # 简单起见，如果需要切出多卷同样宽度的，用户可以录入多行或者加qty字段逻辑循环创建
    # 这里演示逻辑：如果 quantity > 1，上述 action_confirm 需要循环
    
