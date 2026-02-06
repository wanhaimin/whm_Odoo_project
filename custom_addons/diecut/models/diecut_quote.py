from odoo import models, fields, api

# 这是一个模切成本核算模型
class DiecutQuote(models.Model):
    _name = 'diecut.quote'
    _description = '模切成本计算器'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- Header ---
    name = fields.Char(string="报价单号", required=True, copy=False, readonly=True, index=True, default='New')
    customer_id = fields.Many2one('res.partner', string="客户", required=True, domain="[('is_company', '=', True)]")
    
    internal_sn = fields.Char(string="内部料号")
    project_sn = fields.Char(string="项目编号")
    terminal = fields.Char(string="终端客户")
    user_id = fields.Many2one('res.users', string="负责人", default=lambda self: self.env.user)
    
    quote_date = fields.Date(string="报价日期", default=fields.Date.context_today)
    quote_date_show = fields.Date(string="报价日期", related='quote_date', store=True) # For list view if needed
    quote_category = fields.Char(string="报价类别") # Or Selection if known
    
    currency_id = fields.Many2one('res.currency', string="币种", default=lambda self: self.env.company.currency_id)
    uom_id = fields.Many2one('uom.uom', string="单位", default=lambda self: self.env.ref('uom.product_uom_unit'))
    
    specification = fields.Char(string="规格(mm)", placeholder="如: 33.35 * 17.05")
    moq = fields.Integer(string="MOQ")
    lead_time = fields.Integer(string="交期(天)")

    # --- Cost Calculations ---
    # 1. Material
    material_line_ids = fields.One2many('diecut.quote.material.line', 'quote_id', string="材料成本明细")
    total_material_cost = fields.Monetary(string="材料成本总计 (RMB/pcs)", compute='_compute_total_material_cost', store=True)
    material_cost_ratio = fields.Float(string="材料占比", compute='_compute_ratios')

    # 2. Manufacturing
    manufacturing_line_ids = fields.One2many('diecut.quote.manufacturing.line', 'quote_id', string="制造成本明细")
    # Note: total_manufacturing_cost_nosetax and total_manufacturing_cost in XML
    total_manufacturing_cost_nosetax = fields.Monetary(string="制造成本 (不含税)", compute='_compute_total_manufacturing_cost', store=True)
    total_manufacturing_cost = fields.Monetary(string="制造成本 (含税 1.13)", compute='_compute_total_manufacturing_cost', store=True)
    manufacturing_cost_ratio = fields.Float(string="制造成本占比", compute='_compute_ratios')

    # 3. Marketing / Overhead
    transport_rate = fields.Float(string="运输成本率", default=1.0)
    transport_cost = fields.Monetary(string="运输成本", compute='_compute_overhead_costs', store=True)
    
    management_rate = fields.Float(string="管理费用率", default=5.0)
    management_cost = fields.Monetary(string="管理费用", compute='_compute_overhead_costs', store=True)
    
    utility_rate = fields.Float(string="厂租水电率", default=2.0)
    utility_cost = fields.Monetary(string="厂租水电", compute='_compute_overhead_costs', store=True)
    
    packaging_rate = fields.Float(string="包材成本率", default=1.0)
    packaging_cost = fields.Monetary(string="包材成本", compute='_compute_overhead_costs', store=True)
    
    depreciation_rate = fields.Float(string="机器折旧率", default=2.0)
    depreciation_cost = fields.Monetary(string="机器折旧", compute='_compute_overhead_costs', store=True)
    
    total_marketing_cost = fields.Monetary(string="管销成本总计", compute='_compute_overhead_costs', store=True)

    # 4. Other Costs
    sample_cost_input = fields.Float(string="样品成本")
    mold_fee = fields.Float(string="模具总费用")
    punch_qty = fields.Integer(string="预计冲压总数", default=100000)
    mold_cost = fields.Monetary(string="单位模具成本", compute='_compute_other_costs', store=True)
    
    total_other_cost = fields.Monetary(string="其它成本总计", compute='_compute_other_costs', store=True)

    # Summary
    subtotal_cost = fields.Monetary(string="成本总和", compute='_compute_final_price', store=True)
    profit_rate = fields.Float(string="预估利润率", default=15.0)
    profit_amount = fields.Monetary(string="利润金额", compute='_compute_final_price', store=True)
    final_unit_price = fields.Monetary(string="合计建议报价 (RMB/PCS)", compute='_compute_final_price', store=True)

    # --- Computes ---
    @api.depends('material_line_ids.unit_consumable_cost')
    def _compute_total_material_cost(self):
        for record in self:
            record.total_material_cost = sum(record.material_line_ids.mapped('unit_consumable_cost'))

    @api.depends('manufacturing_line_ids.cost_per_pcs')
    def _compute_total_manufacturing_cost(self):
        for record in self:
            nosetax = sum(record.manufacturing_line_ids.mapped('cost_per_pcs'))
            record.total_manufacturing_cost_nosetax = nosetax
            record.total_manufacturing_cost = nosetax * 1.13 # Simple assumption based on XML label

    @api.depends('subtotal_cost', 'transport_rate', 'management_rate', 'utility_rate', 'packaging_rate', 'depreciation_rate')
    def _compute_overhead_costs(self):
        for record in self:
            # Usually overhead is based on Material + Mfg costs? Or Sales Price?
            # Assuming based on (Material + Mfg) for now or similar base. 
            # Or maybe just rates? If rate is %, need a base. 
            # Let's assume the rate is percentage of 'Cost Base' (Material + Mfg)
            base_cost = record.total_material_cost + record.total_manufacturing_cost
            record.transport_cost = base_cost * (record.transport_rate / 100.0)
            record.management_cost = base_cost * (record.management_rate / 100.0)
            record.utility_cost = base_cost * (record.utility_rate / 100.0)
            record.packaging_cost = base_cost * (record.packaging_rate / 100.0)
            record.depreciation_cost = base_cost * (record.depreciation_rate / 100.0)
            
            record.total_marketing_cost = (record.transport_cost + record.management_cost + 
                                         record.utility_cost + record.packaging_cost + 
                                         record.depreciation_cost)

    @api.depends('sample_cost_input', 'mold_fee', 'punch_qty')
    def _compute_other_costs(self):
        for record in self:
            mold_unit_cost = 0.0
            if record.punch_qty > 0:
                mold_unit_cost = record.mold_fee / record.punch_qty
            record.mold_cost = mold_unit_cost
            record.total_other_cost = mold_unit_cost + record.sample_cost_input # Just simple sum? Sample cost per unit?

    @api.depends('total_material_cost', 'total_manufacturing_cost', 'total_marketing_cost', 'total_other_cost', 'profit_rate')
    def _compute_final_price(self):
        for record in self:
            subtotal = record.total_material_cost + record.total_manufacturing_cost + record.total_marketing_cost + record.total_other_cost
            record.subtotal_cost = subtotal
            
            margin = subtotal * (record.profit_rate / 100.0)
            record.profit_amount = margin
            record.final_unit_price = subtotal + margin

    @api.depends('total_material_cost', 'total_manufacturing_cost', 'subtotal_cost')
    def _compute_ratios(self):
        for record in self:
            if record.subtotal_cost > 0:
                record.material_cost_ratio = record.total_material_cost / record.subtotal_cost
                record.manufacturing_cost_ratio = record.total_manufacturing_cost / record.subtotal_cost
            else:
                record.material_cost_ratio = 0.0
                record.manufacturing_cost_ratio = 0.0

    @api.onchange('material_line_ids')
    def _onchange_material_line_ids(self):
        """新增行时，默认带入第一行的参数"""
        if not self.material_line_ids or len(self.material_line_ids) < 2:
            return
        
        # 获取第一行作为模板 (按顺序，第一个通常是索引0)
        # 注意：material_line_ids在UI编辑时可能包含NewId记录，Odoo会自动维护顺序
        first_line = self.material_line_ids[0]
        
        # 遍历后续行
        for i in range(1, len(self.material_line_ids)):
            line = self.material_line_ids[i]
            # 如果是新加的行（特征是这些必填参数为0/空），则复制第一行
            # 这里判断 slitting_width, pitch 是否为0
            if line.slitting_width == 0.0 and line.pitch == 0.0:
                line.slitting_width = first_line.slitting_width
                line.pitch = first_line.pitch
                line.cavity = first_line.cavity
                # 注意：不要覆盖 yield_rate，因为已有默认值 98.0，且用户未要求复制它 (虽然通常可能一致)
                
    def action_sync_first_line_params(self):
        """Button Action: 将第一行的工艺参数同步给所有行"""
        for record in self:
            if not record.material_line_ids or len(record.material_line_ids) < 2:
                continue
            
            first = record.material_line_ids[0]
            # 获取源数据
            s_width = first.slitting_width
            s_pitch = first.pitch
            s_cavity = first.cavity
            
            # 覆盖后续所有行
            for i in range(1, len(record.material_line_ids)):
                line = record.material_line_ids[i]
                line.slitting_width = s_width
                line.pitch = s_pitch
                line.cavity = s_cavity

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('diecut.quote') or 'New'
        return super().create(vals_list)


class DiecutQuoteMaterialLine(models.Model):
    _name = 'diecut.quote.material.line'
    _description = '模切报价-材料明细'

    quote_id = fields.Many2one('diecut.quote', string="报价单", ondelete='cascade')
    currency_id = fields.Many2one(related='quote_id.currency_id')

    material_id = fields.Many2one('product.product', string="材料", required=True, domain=[('is_raw_material', '=', True)])
    raw_width = fields.Float(string="原材宽(mm)", compute='_compute_material_defaults', store=True, readonly=False)
    raw_length = fields.Float(string="原材长(mm)", compute='_compute_material_defaults', store=True, readonly=False)
    
    price_unit_total = fields.Monetary(string="含税总价", help="材料采购含税总价")
    price_unit_tax_inc = fields.Monetary(string="含税单价 (RMB/㎡/张/支)", compute='_compute_material_defaults', store=True, readonly=False, help="自动更新：依赖原材料库整支价格")
    
    # Slitting info
    slitting_width = fields.Float(string="分切宽(mm)")
    slitting_rolls = fields.Integer(string="分切卷数", compute='_compute_slitting', store=True)
    
    # Production info
    pitch = fields.Float(string="跳距(mm)")
    cavity = fields.Integer(string="穴数", default=1)
    
    qty_per_roll = fields.Integer(string="每卷模切数量", compute='_compute_yield', store=True)
    total_prod_qty = fields.Integer(string="原材料生产总数", compute='_compute_yield', store=True)
    
    unit_usage = fields.Float(string="单位用量 (m²/pcs)", digits=(16,6), compute='_compute_unit_cost', store=True)
    yield_rate = fields.Float(string="良率(%)", default=0.98)
    
    unit_consumable_cost = fields.Monetary(string="单位耗材成本 (RMB/pcs)", compute='_compute_unit_cost', store=True)

    # --- Computes ---

    # --- Onchange ---
    # --- Computes ---
    @api.depends('material_id.width', 'material_id.length', 'material_id.raw_material_total_price')
    def _compute_material_defaults(self):
        for line in self:
            if line.material_id:
                line.raw_width = line.material_id.width
                line.raw_length = (line.material_id.length or 0.0) * 1000.0
                line.price_unit_tax_inc = line.material_id.raw_material_total_price or 0.0
    @api.depends('raw_width', 'slitting_width')
    def _compute_slitting(self):
        for line in self:
            if line.slitting_width > 0:
                line.slitting_rolls = int(line.raw_width / line.slitting_width)
            else:
                line.slitting_rolls = 0

    @api.depends('raw_length', 'pitch', 'cavity', 'slitting_rolls')
    def _compute_yield(self):
        for line in self:
            if line.pitch > 0:
                # raw_length is in mm, pitch is in mm
                line.qty_per_roll = int((line.raw_length / line.pitch) * line.cavity)
            else:
                line.qty_per_roll = 0
            
            line.total_prod_qty = line.qty_per_roll * line.slitting_rolls

    @api.depends('price_unit_tax_inc', 'total_prod_qty', 'yield_rate', 'slitting_width', 'pitch', 'cavity')
    def _compute_unit_cost(self):
        for line in self:
            # 1. Calculate Unit Usage (Area per piece in m2)
            if line.cavity > 0:
                area_mm2 = line.slitting_width * line.pitch
                line.unit_usage = (area_mm2 / line.cavity) / 1000000.0
            else:
                line.unit_usage = 0.0

            # 2. Calculate Consumable Cost per Piece
            if line.total_prod_qty > 0:
                # User Request: Unit Cost = (Price / Qty) * (1 + (1 - Yield))
                # Interpretation: Base Cost * (1 + LossRate)
                # Yield is now 0-1 scale (e.g. 0.98), so no need to divide by 100
                loss_factor = 1.0 + (1.0 - line.yield_rate)
                line.unit_consumable_cost = (line.price_unit_tax_inc / line.total_prod_qty) * loss_factor
            else:
                line.unit_consumable_cost = 0.0

class DiecutQuoteManufacturingLine(models.Model):
    _name = 'diecut.quote.manufacturing.line'
    _description = '模切报价-制造明细'

    quote_id = fields.Many2one('diecut.quote', string="报价单", ondelete='cascade')
    currency_id = fields.Many2one(related='quote_id.currency_id')

    step_1 = fields.Char(string="工位") # process step
    step_2 = fields.Char(string="说明")
    
    mfg_fee = fields.Float(string="人均制造费/小时", default=30.0)
    workstation_qty = fields.Integer(string="工位人数", default=1)
    capacity = fields.Integer(string="产能(PCS/H)", default=1000)
    yield_rate = fields.Float(string="良率(%)", default=0.98)
    
    cost_per_pcs = fields.Monetary(string="费用(RMB/PCS)", compute='_compute_cost', store=True)

    @api.depends('mfg_fee', 'workstation_qty', 'capacity', 'yield_rate')
    def _compute_cost(self):
        for line in self:
            # Cost = (Fee * People) / Capacity / Yield
            if line.capacity > 0 and line.yield_rate > 0:
                hourly_cost = line.mfg_fee * line.workstation_qty
                # Yield is 0.98 (Ratio), so use directly
                effective_capacity = line.capacity * line.yield_rate
                line.cost_per_pcs = hourly_cost / effective_capacity
            else:
                line.cost_per_pcs = 0.0