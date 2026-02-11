from odoo import models, fields, api

# 这是一个模切成本核算模型
class DiecutQuote(models.Model):
    _name = 'diecut.quote'
    _description = '模切成本计算器'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- Header ---
    name = fields.Char(string="报价单号", required=True, copy=False, readonly=True, index=True, default='New')
    customer_id = fields.Many2one('res.partner', string="客户", required=True, domain="[('is_company', '=', True), ('customer_rank', '>', 0)]")
    contact_id = fields.Many2one('res.partner', string="联系人", domain="[('parent_id', '=', customer_id)]")

    product_name = fields.Char(string="品名 :") 
    project_sn = fields.Char(string="客户料号 :")  
    internal_sn = fields.Char(string="内部料号 :")
    terminal = fields.Char(string="终端客户 :")
    user_id = fields.Many2one('res.users', string="制单人", default=lambda self: self.env.user)
    specification = fields.Char(string="产品规格(mm) :", placeholder="如: 33.35 * 17.05")
    moq = fields.Integer(string="MOQ")
    lead_time = fields.Integer(string="交期(天) :")

    quote_date = fields.Date(string="报价日期 :", default=fields.Date.context_today)
    quote_date_show = fields.Date(string="报价日期 :", related='quote_date', store=True) # For list view if needed
    
    
    currency_id = fields.Many2one('res.currency', string="币种", default=lambda self: self.env.company.currency_id)
    uom_id = fields.Many2one('uom.uom', string="单位", default=lambda self: self.env.ref('uom.product_uom_unit'))
    
   

    # --- Cost Calculations ---
    # 1. Material
    material_line_ids = fields.One2many('diecut.quote.material.line', 'quote_id', string="材料成本明细")
    total_material_cost = fields.Float(string="材料成本总计 (RMB/pcs)", compute='_compute_total_material_cost', store=True, digits=(16, 4))
    material_cost_ratio = fields.Float(string="材料占比", compute='_compute_ratios')

    # 2. Manufacturing
    manufacturing_line_ids = fields.One2many('diecut.quote.manufacturing.line', 'quote_id', string="制造成本明细")
    # Note: total_manufacturing_cost_nosetax and total_manufacturing_cost in XML
    # Note: total_manufacturing_cost_nosetax and total_manufacturing_cost in XML
    total_manufacturing_cost_nosetax = fields.Float(string="制造成本 (不含税)", compute='_compute_total_manufacturing_cost', store=True, digits=(16, 4))
    total_manufacturing_cost = fields.Float(string="制造成本 (含税 1.13)", compute='_compute_total_manufacturing_cost', store=True, digits=(16, 4))
    manufacturing_cost_ratio = fields.Float(string="制造成本占比", compute='_compute_ratios')

    # 3. Marketing / Overhead
    transport_rate = fields.Float(string="运输成本率", default=1.0)
    transport_cost = fields.Float(string="运输成本", compute='_compute_overhead_costs', store=True, digits=(16, 4))
    
    management_rate = fields.Float(string="管理费用率", default=5.0)
    management_cost = fields.Float(string="管理费用", compute='_compute_overhead_costs', store=True, digits=(16, 4))
    
    utility_rate = fields.Float(string="厂租水电率", default=2.0)
    utility_cost = fields.Float(string="厂租水电", compute='_compute_overhead_costs', store=True, digits=(16, 4))
    
    packaging_rate = fields.Float(string="包材成本率", default=1.0)
    packaging_cost = fields.Float(string="包材成本", compute='_compute_overhead_costs', store=True, digits=(16, 4))
    
    depreciation_rate = fields.Float(string="机器折旧率", default=2.0)
    depreciation_cost = fields.Float(string="机器折旧", compute='_compute_overhead_costs', store=True, digits=(16, 4))
    
    total_marketing_cost = fields.Float(string="管销成本总计", compute='_compute_overhead_costs', store=True, digits=(16, 4))

    # 4. Other Costs
    sample_cost_input = fields.Float(string="样品成本")
    mold_fee = fields.Float(string="模具总费用", digits=(16, 4))
    punch_qty = fields.Integer(string="预计冲压总数", default=100000)
    mold_cost = fields.Float(string="单位模具成本", compute='_compute_other_costs', store=True, digits=(16, 4))
    
    total_other_cost = fields.Float(string="其它成本总计", compute='_compute_other_costs', store=True, digits=(16, 4))

    # Summary
    subtotal_cost = fields.Float(string="成本总和", compute='_compute_final_price', store=True, digits=(16, 4))
    profit_rate = fields.Float(string="利润率", default=15.0)
    profit_amount = fields.Float(string="利润金额", compute='_compute_final_price', store=True, digits=(16, 4))
    final_unit_price = fields.Float(string="合计建议报价 (RMB/PCS)", compute='_compute_final_price', store=True, digits=(16, 4))

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
                # Even if no logical change, we must return reload action to keep window open
                return record._get_action_reload()
            
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
            
            return record._get_action_reload()

    def action_sync_slitting_width(self):
        """Button Action: 仅同步分切宽"""
        for record in self:
            if not record.material_line_ids or len(record.material_line_ids) < 2:
                return record._get_action_reload()
            
            val = record.material_line_ids[0].slitting_width
            for line in record.material_line_ids[1:]:
                line.slitting_width = val
            return record._get_action_reload()

    def action_sync_pitch(self):
        """Button Action: 仅同步跳距"""
        for record in self:
            if not record.material_line_ids or len(record.material_line_ids) < 2:
                return record._get_action_reload()
            
            val = record.material_line_ids[0].pitch
            for line in record.material_line_ids[1:]:
                line.pitch = val
            return record._get_action_reload()

    def action_sync_cavity(self):
        """Button Action: 仅同步穴数"""
        for record in self:
            if not record.material_line_ids or len(record.material_line_ids) < 2:
                return record._get_action_reload()
            
            val = record.material_line_ids[0].cavity
            for line in record.material_line_ids[1:]:
                line.cavity = val
            return record._get_action_reload()

    def action_sync_yield_rate(self):
        """Button Action: 仅同步良率"""
        for record in self:
            if not record.material_line_ids or len(record.material_line_ids) < 2:
                return record._get_action_reload()
            
            val = record.material_line_ids[0].yield_rate
            for line in record.material_line_ids[1:]:
                line.yield_rate = val




    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('diecut.quote') or 'New'
        return super().create(vals_list)

    def action_open_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'diecut.quote',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {'form_view_initial_mode': 'edit', 'dialog_size': 'extra-large'},
        }

    # 定义报价form视图为弹窗
    def _get_action_reload(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'diecut.quote',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit', 'dialog_size': 'extra-large'},  # Ensure it stays editable
        }


    def action_save_and_stay(self):
        """保存并保持窗口打开"""
        return self._get_action_reload()

    def action_open_wizard(self):
        """打开快速录入向导"""
        self.ensure_one()
        return {
            'name': '快速录入报价信息',
            'type': 'ir.actions.act_window',
            'res_model': 'diecut.quote.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_quote_id': self.id, 'active_id': self.id, 'active_model': 'diecut.quote'},
        }



class DiecutQuoteMaterialLine(models.Model):
    _name = 'diecut.quote.material.line'
    _description = '模切报价-材料明细'

    quote_id = fields.Many2one('diecut.quote', string="报价单", ondelete='cascade')
    currency_id = fields.Many2one(related='quote_id.currency_id')

    material_id = fields.Many2one('product.product', string="材料", required=True, domain=[('is_raw_material', '=', True)])
    

    raw_width = fields.Float(string="原材宽(mm)", compute='_compute_material_defaults', store=True, readonly=False)
    raw_length = fields.Float(string="原材长(mm)", compute='_compute_material_defaults', store=True, readonly=False)
    
    price_unit_total = fields.Float(string="含税总价", help="材料采购含税总价", digits=(16, 4))
    price_unit_tax_inc = fields.Float(string="含税单价 (RMB/㎡/张/支)", compute='_compute_material_defaults', store=True, readonly=False, help="自动更新：依赖原材料库整支价格", digits=(16, 4))
    
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
    
    unit_consumable_cost = fields.Float(string="单位耗材成本 (RMB/pcs)", compute='_compute_unit_cost', store=True, digits=(16, 4))

    # --- Computes ---

    # --- Onchange ---
    # --- Computes ---
    @api.depends('material_id.width', 'material_id.length', 'material_id.raw_material_unit_price')
    def _compute_material_defaults(self):
        for line in self:
            if line.material_id:
                line.raw_width = line.material_id.width
                line.raw_length = (line.material_id.length or 0.0) * 1000.0
                line.price_unit_tax_inc = line.material_id.raw_material_unit_price or 0.0
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
    
    cost_per_pcs = fields.Float(string="费用(RMB/PCS)", compute='_compute_cost', store=True, digits=(16, 4))

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

class DiecutQuoteWizard(models.TransientModel):
    _name = 'diecut.quote.wizard'
    _description = '报价单快速录入向导'

    quote_id = fields.Many2one('diecut.quote', string="关联报价单")
    
    # 镜像字段
    customer_id = fields.Many2one('res.partner', string="客户", required=True, domain="[('is_company', '=', True), ('customer_rank', '>', 0)]")
    contact_id = fields.Many2one('res.partner', string="联系人", domain="[('parent_id', '=', customer_id)]")
    
    product_name = fields.Char(string="品名 :")   
    internal_sn = fields.Char(string="内部料号 :")
    project_sn = fields.Char(string="项目编号 :")
    terminal = fields.Char(string="终端客户 :")
    user_id = fields.Many2one('res.users', string="制单人")
    specification = fields.Char(string="产品规格(mm)", placeholder="如: 33.35 * 17.05")
    moq = fields.Integer(string="MOQ")
    lead_time = fields.Integer(string="交期(天)")
    quote_date = fields.Date(string="报价日期")
    currency_id = fields.Many2one('res.currency', string="币种")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')
        
        if active_model == 'diecut.quote' and active_id:
            quote = self.env['diecut.quote'].browse(active_id)
            if quote.exists():
                res.update({
                    'quote_id': quote.id,
                    'customer_id': quote.customer_id.id,
                    'contact_id': quote.contact_id.id,
                    'product_name': quote.product_name,
                    'internal_sn': quote.internal_sn,
                    'project_sn': quote.project_sn,
                    'terminal': quote.terminal,
                    'user_id': quote.user_id.id,
                    'specification': quote.specification,
                    'moq': quote.moq,
                    'lead_time': quote.lead_time,
                    'quote_date': quote.quote_date,
                    'currency_id': quote.currency_id.id,
                })
        return res

    def action_apply(self):
        self.ensure_one()
        if self.quote_id:
            self.quote_id.write({
                'customer_id': self.customer_id.id,
                'contact_id': self.contact_id.id,
                'product_name': self.product_name,
                'internal_sn': self.internal_sn,
                'project_sn': self.project_sn,
                'terminal': self.terminal,
                'user_id': self.user_id.id,
                'specification': self.specification,
                'moq': self.moq,
                'lead_time': self.lead_time,
                'quote_date': self.quote_date,
                'currency_id': self.currency_id.id,
            })
        return {'type': 'ir.actions.act_window_close'}
