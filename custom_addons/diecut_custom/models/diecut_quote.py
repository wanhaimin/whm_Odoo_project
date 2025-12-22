from odoo import models, fields, api

class DiecutQuote(models.Model):
    _name = 'diecut.quote'
    _description = '模切报价单'

    # --- 全局排版参数 ---
    name = fields.Char(string="报价单号", required=True, copy=False, readonly=True, index=True, default='New')
    total_pcs = fields.Integer(string="计划产量 (PCS)", default=1000, help="客户需要的成品总数量")
    diecut_pitch = fields.Float(string="模切跳步 (mm)", default=1.0, help="模切刀模两个产品中心之间的距离")
    columns = fields.Integer(string="排版列数", default=1, help="材料横向排几列产品")
    extra_loss_meter = fields.Float(string="额外调机损耗 (m)", default=10.0, help="生产前调机预估消耗的长度")

    # --- 材料明细关联 ---
    layer_ids = fields.One2many('diecut.quote.layer', 'quote_id', string="材料层明细")

    # --- 汇总金额 ---
    amount_total = fields.Float(string="总成本小计", compute="_compute_amount_total", store=True)

    @api.depends('layer_ids.subtotal')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = sum(record.layer_ids.mapped('subtotal'))

    # 自动生成单号逻辑（可选）
    @api.model_create_multi
    def create(self, vals_list):
        # 兼容性处理: 如果传入的是字典而不是列表,转换为列表
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('diecut.quote') or 'DQ-New'
        return super(DiecutQuote, self).create(vals_list)


class DiecutQuoteLayer(models.Model):
    _name = 'diecut.quote.layer'
    _description = '模切材料层明细'

    quote_id = fields.Many2one('diecut.quote', ondelete='cascade', string="报价单引用")
    
    # 材料选择
    product_id = fields.Many2one('product.product', string="材料型号", required=True)
    layer_role = fields.Selection([
        ('liner', '底纸'),
        ('adhesive', '胶粘层'),
        ('face', '面料/保护膜'),
        ('other', '其他')
    ], string="层角色", default='adhesive')

    # 规格参数
    slitting_width = fields.Float(string="分条宽度 (mm)", help="该层材料分条后的实际宽度")
    price_unit = fields.Float(string="单价/㎡", help="材料的平方米单价")

    # --- 核心计算逻辑 (@api.depends) ---
    layer_sqm = fields.Float(string="所需面积 (㎡)", compute="_compute_layer_metrics", store=True)
    subtotal = fields.Float(string="材料小计", compute="_compute_layer_metrics", store=True)

    @api.depends('slitting_width', 'price_unit', 'quote_id.total_pcs', 
                 'quote_id.diecut_pitch', 'quote_id.columns', 'quote_id.extra_loss_meter')
    def _compute_layer_metrics(self):
        """
        核心公式应用：
        1. 生产长度 (m) = (总PCS / 列数) * 跳步 / 1000 + 损耗
        2. 需求面积 (㎡) = 生产长度 * 分条宽度 / 1000
        """
        for line in self:
            main = line.quote_id
            # 基础校验，防止除以零报错
            if main and main.diecut_pitch > 0 and main.columns > 0 and line.slitting_width > 0:
                # 1. 计算生产该批次所需的材料总长度
                total_length_m = ((main.total_pcs / main.columns) * main.diecut_pitch / 1000.0) + main.extra_loss_meter
                
                # 2. 计算本层面积
                line.layer_sqm = total_length_m * (line.slitting_width / 1000.0)
                
                # 3. 计算金额
                line.subtotal = line.layer_sqm * line.price_unit
            else:
                line.layer_sqm = 0.0
                line.subtotal = 0.0
