from odoo import models, fields, api, Command
import math

class DiecutQuoteMaterialLine(models.Model):
    _name = 'diecut.quote.material.line'
    _description = '模切报价材料明细'

    quote_id = fields.Many2one('diecut.quote', ondelete='cascade', string='报价单')
    material_id = fields.Many2one('my.material', string='材质/品牌/型号')
    
    # Inputs
    # Inputs - Fetch from Material directly (Read-Only)
    raw_width = fields.Float(
        string='原材料规格(宽mm)', 
        related='material_id.width', store=True, readonly=True)
    
    # Unit Conversion: Material(M) -> Quote(mm), so we use compute instead of related
    raw_length = fields.Float(
        string='原材料规格(长mm)', 
        compute='_compute_raw_length', store=True, readonly=True)
        
    price_unit_total = fields.Float(
        string='含税单价(整支/张/支)', digits=(16, 2), 
        related='material_id.raw_material_total_price', store=True, readonly=True)
    
    slitting_width = fields.Float(string='分切宽度(mm)')
    pitch = fields.Float(string='跳距(mm)')
    cavity = fields.Integer(string='穴数(pcs)', default=1)
    yield_rate = fields.Float(string='良率 %', default=100.0)

    # Calculated
    slitting_rolls = fields.Integer(string='分切卷数', compute='_compute_material_stats', store=True)
    qty_per_roll = fields.Integer(string='每卷数量', compute='_compute_material_stats', store=True)
    total_prod_qty = fields.Integer(string='原材生产总数', compute='_compute_material_stats', store=True)
    unit_usage = fields.Float(string='单位用量(㎡/pcs)', compute='_compute_material_stats', digits=(16, 6), store=True)
    unit_consumable_cost = fields.Float(string='单位耗材成本(RMB/pcs)', compute='_compute_material_stats', digits=(16, 4), store=True)

    
    currency_id = fields.Many2one('res.currency', string='币种', related='quote_id.currency_id')

    @api.depends('material_id', 'material_id.length')
    def _compute_raw_length(self):
        for rec in self:
            # Material length is in Meters, Quote needs mm
            rec.raw_length = (rec.material_id.length or 0) * 1000

    @api.depends('raw_width', 'raw_length', 'slitting_width', 'pitch', 'cavity', 'yield_rate', 'price_unit_total')
    @api.onchange('raw_width', 'raw_length', 'slitting_width', 'pitch', 'cavity', 'yield_rate', 'price_unit_total')
    def _compute_material_stats(self):
        for rec in self:
            # 1. 分切卷数 = 向下取整(原材宽 / 分切宽)
            slitting_rolls = 0
            if rec.slitting_width and rec.slitting_width > 0:
                slitting_rolls = int(rec.raw_width / rec.slitting_width)
            rec.slitting_rolls = slitting_rolls

            # 2. 每卷数量 = 向下取整(原材长 / 跳距) * 穴数
            # 物理逻辑：先算能切多少“模”(Step)，再乘以每模穴数
            qty_per_roll = 0
            if rec.pitch and rec.pitch > 0:
                steps = int(rec.raw_length / rec.pitch)
                qty_per_roll = steps * rec.cavity
            rec.qty_per_roll = qty_per_roll

            # 3. 生产总数 = 每卷数量 * 分切卷数 * (良率%)
            rec.total_prod_qty = int(qty_per_roll * slitting_rolls * (rec.yield_rate / 100.0))

            # 4. 单位用量(㎡) = (跳距 * 分切宽) / 穴数 / 1,000,000
            # 逻辑：分切宽*跳距 是“一模”的面积，除以穴数才是单PCS面积
            if rec.cavity and rec.cavity > 0:
                area_per_shot = rec.pitch * rec.slitting_width
                rec.unit_usage = (area_per_shot / rec.cavity) / 1000000.0
            else:
                rec.unit_usage = 0.0

            # 5. 单位成本 = 含税整卷总价 / 生产总数
            if rec.total_prod_qty > 0:
                rec.unit_consumable_cost = rec.price_unit_total / rec.total_prod_qty
            else:
                rec.unit_consumable_cost = 0.0



class DiecutQuoteManufacturingLine(models.Model):
    _name = 'diecut.quote.manufacturing.line'
    _description = '模切报价制造成本'

    quote_id = fields.Many2one('diecut.quote', ondelete='cascade', string='报价单')
    step_1 = fields.Char(string='工位')
    step_2 = fields.Char(string='说明')
    
    # Inputs
    mfg_fee = fields.Float(string='制造费用', digits=(16, 4))
    workstation_qty = fields.Integer(string='所需工位')
    unit_price_hr = fields.Float(string='单价/人/小时', digits=(16, 4))
    capacity = fields.Float(string='产能')
    yield_rate = fields.Float(string='良率 %', default=100.0)

    # Calculated
    cost_per_pcs = fields.Float(string='费用 (RMB/PCS)', compute='_compute_mfg_cost', store=True, digits=(16, 4))

    
    currency_id = fields.Many2one('res.currency', string='币种', related='quote_id.currency_id')

    @api.depends('mfg_fee', 'workstation_qty', 'capacity', 'yield_rate')
    def _compute_mfg_cost(self):
        for rec in self:
            if rec.capacity and rec.yield_rate:
                rec.cost_per_pcs = (rec.mfg_fee * rec.workstation_qty / rec.capacity) / (rec.yield_rate / 100.0)
            else:
                rec.cost_per_pcs = 0.0



class DiecutQuote(models.Model):
    _name = 'diecut.quote'
    _description = '模切报价'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='品名', required=True, tracking=True)
    internal_sn = fields.Char(string='料号', tracking=True)
    project_sn = fields.Char(string='项目号', tracking=True)
    customer_id = fields.Many2one('res.partner', string='客户', tracking=True)
    user_id = fields.Many2one('res.users', string='销售员', default=lambda self: self.env.user, tracking=True)
    terminal = fields.Char(string='终端', tracking=True)
    
    quote_date = fields.Date(string='报价日期', default=fields.Date.context_today)
    quote_date_show = fields.Char(string='报价日期', compute='_compute_quote_date_show', store=True)
    quote_category = fields.Selection([
        ('standard', '标准报价'),
        ('special', '特殊报价')
    ], string='计价类别', default='standard')
    
    currency_id = fields.Many2one('res.currency', string='币种', default=lambda self: self.env['res.currency'].search([('name', '=', 'CNY')], limit=1).id or self.env.company.currency_id.id)
    uom_id = fields.Many2one('uom.uom', string='计价单位')
    
    specification = fields.Char(string='规格')
    moq = fields.Float(string='MOQ', default=1000000)
    lead_time = fields.Char(string='L/T (天)')
    
    profit_rate = fields.Float(string='利润 (%)', default=10.0)
    vat_rate = fields.Float(string='增值税率 (%)', default=13.0)

    # Line items
    material_line_ids = fields.One2many('diecut.quote.material.line', 'quote_id', string='材料成本细项')
    manufacturing_line_ids = fields.One2many('diecut.quote.manufacturing.line', 'quote_id', string='制造成本细项')

    # Totals
    total_material_cost = fields.Float(string='材料成本总计 (RMB/pcs)', compute='_compute_total_material_cost', store=True, digits=(16, 4))
    total_manufacturing_cost_nosetax = fields.Float(string='制造成本总计 (不含税)', compute='_compute_total_manufacturing_cost', store=True, digits=(16, 4))
    total_manufacturing_cost = fields.Float(string='制造成本总计 (含税)', compute='_compute_total_manufacturing_cost', store=True, digits=(16, 4))
    
    # Marketing costs
    transport_rate = fields.Float(string='运输成本比例 (%)', default=1.0)
    management_rate = fields.Float(string='管理费用比例 (%)', default=3.0)
    utility_rate = fields.Float(string='厂租水电比例 (%)', default=1.0)
    packaging_rate = fields.Float(string='包材成本比例 (%)', default=1.0)
    depreciation_rate = fields.Float(string='机器折旧比例 (%)', default=1.0)
    
    transport_cost = fields.Float(string='运输成本', compute='_compute_marketing_costs', store=True, digits=(16, 4))
    management_cost = fields.Float(string='管理费用', compute='_compute_marketing_costs', store=True, digits=(16, 4))
    utility_cost = fields.Float(string='厂租水电费用', compute='_compute_marketing_costs', store=True, digits=(16, 4))
    packaging_cost = fields.Float(string='包材成本', compute='_compute_marketing_costs', store=True, digits=(16, 4))
    depreciation_cost = fields.Float(string='机器折旧', compute='_compute_marketing_costs', store=True, digits=(16, 4))
    total_marketing_cost = fields.Float(string='管销成本总计', compute='_compute_marketing_costs', store=True, digits=(16, 4))
    
    # Ratios
    material_cost_ratio = fields.Float(string='材料占比', compute='_compute_cost_ratios', store=True)
    manufacturing_cost_ratio = fields.Float(string='制造成本占比', compute='_compute_cost_ratios', store=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'manufacturing_line_ids' in fields_list:
            default_lines = [
                {'step_1': '分条', 'mfg_fee': 25, 'workstation_qty': 0, 'capacity': 1000000, 'yield_rate': 100.0},
                {'step_1': '贴合', 'mfg_fee': 25, 'workstation_qty': 0, 'capacity': 1000000, 'yield_rate': 100.0},
                {'step_1': '模切', 'mfg_fee': 35, 'workstation_qty': 0, 'capacity': 100000, 'yield_rate': 97.0},
                {'step_1': '排废', 'mfg_fee': 25, 'workstation_qty': 0, 'capacity': 8000, 'yield_rate': 100.0},
                {'step_1': '对贴', 'mfg_fee': 30, 'workstation_qty': 0, 'capacity': 5000, 'yield_rate': 100.0},
                {'step_1': '折弯', 'mfg_fee': 25, 'workstation_qty': 0, 'capacity': 50, 'yield_rate': 100.0},
                {'step_1': '品检', 'mfg_fee': 25, 'workstation_qty': 0, 'capacity': 1000000, 'yield_rate': 100.0},
                {'step_1': '包装', 'mfg_fee': 25, 'workstation_qty': 0, 'capacity': 1000000, 'yield_rate': 100.0},
            ]
            res['manufacturing_line_ids'] = [Command.create(vals) for vals in default_lines]
        return res

    @api.onchange('material_line_ids')
    def _onchange_material_line_ids(self):
        # 至少需要两行才有复制的意义（第一行作为源）
        if not self.material_line_ids or len(self.material_line_ids) < 2:
            return
            
        # 获取第一行及其数据
        first_line = self.material_line_ids[0]
        target_pitch = first_line.pitch
        target_cavity = first_line.cavity
        target_slitting_width = first_line.slitting_width
        
        # 只检查最后一行，因为新增行通常在末尾
        # 避免遍历整个列表，防止在删除中间行时触发不必要的逻辑
        last_line = self.material_line_ids[-1]
        
        # 仅当最后一行是“新行”特征（pitch=0, cavity=1）时才自动填充
        if last_line.pitch == 0.0 and last_line.cavity == 1:
            last_line.pitch = target_pitch
            last_line.cavity = target_cavity
            # 如果分切宽度也是默认值0，则一并填充
            if last_line.slitting_width == 0.0:
                last_line.slitting_width = target_slitting_width

    # Other costs
    sample_cost_input = fields.Float(string='样品成本输入', digits=(16, 0))
    sample_cost = fields.Float(string='样品成本', compute='_compute_other_costs', store=True, digits=(16, 4))
    mold_fee = fields.Float(string='模具费用', digits=(16, 0))
    punch_qty = fields.Integer(string='可冲压数量', default=20000000)
    mold_cost = fields.Float(string='模具成本', compute='_compute_other_costs', store=True, digits=(16, 4))
    total_other_cost = fields.Float(string='其它成本总计', compute='_compute_other_costs', store=True, digits=(16, 4))

    # Final Totals
    subtotal_cost = fields.Float(string='制造、管销、模具成本总计', compute='_compute_final_price', store=True, digits=(16, 4))
    profit_amount = fields.Float(string='利润', compute='_compute_final_price', store=True, digits=(16, 4))
    final_unit_price = fields.Float(string='合计单价', compute='_compute_final_price', store=True, digits=(16, 4))

    @api.depends('quote_date')
    def _compute_quote_date_show(self):
        for rec in self:
            if rec.quote_date:
                rec.quote_date_show = rec.quote_date.strftime('%Y-%m-%d')
            else:
                rec.quote_date_show = ''

    @api.depends('material_line_ids.unit_consumable_cost')
    def _compute_total_material_cost(self):
        for rec in self:
            rec.total_material_cost = sum(rec.material_line_ids.mapped('unit_consumable_cost'))

    @api.depends('manufacturing_line_ids.cost_per_pcs')
    def _compute_total_manufacturing_cost(self):
        for rec in self:
            nosetax = sum(rec.manufacturing_line_ids.mapped('cost_per_pcs'))
            rec.total_manufacturing_cost_nosetax = nosetax
            rec.total_manufacturing_cost = nosetax * 1.13

    @api.depends('total_material_cost', 'total_manufacturing_cost_nosetax', 
                 'transport_rate', 'management_rate', 'utility_rate', 'packaging_rate', 'depreciation_rate')
    def _compute_marketing_costs(self):
        for rec in self:
            base = rec.total_material_cost + rec.total_manufacturing_cost_nosetax
            rec.transport_cost = base * (rec.transport_rate / 100.0)
            rec.management_cost = base * (rec.management_rate / 100.0)
            rec.utility_cost = base * (rec.utility_rate / 100.0)
            rec.packaging_cost = base * (rec.packaging_rate / 100.0)
            rec.depreciation_cost = base * (rec.depreciation_rate / 100.0)
            rec.total_marketing_cost = rec.transport_cost + rec.management_cost + rec.utility_cost + rec.packaging_cost + rec.depreciation_cost

    @api.depends('sample_cost_input', 'mold_fee', 'punch_qty')
    def _compute_other_costs(self):
        for rec in self:
            rec.sample_cost = rec.sample_cost_input
            if rec.punch_qty:
                rec.mold_cost = (rec.sample_cost_input + rec.mold_fee) / rec.punch_qty
            else:
                rec.mold_cost = 0.0
            # 单位模具成本已包含样品费分摊，且other_cost应为单价逻辑，故不再重复加 sample_cost(总额)
            rec.total_other_cost = rec.mold_cost

    @api.depends('total_material_cost', 'total_manufacturing_cost', 'total_marketing_cost', 'total_other_cost', 'profit_rate')
    def _compute_final_price(self):
        for rec in self:
            rec.subtotal_cost = rec.total_material_cost + rec.total_manufacturing_cost + rec.total_marketing_cost + rec.total_other_cost
            rec.profit_amount = rec.subtotal_cost * (rec.profit_rate / 100.0)
            rec.final_unit_price = rec.subtotal_cost + rec.profit_amount

    @api.depends('total_material_cost', 'total_manufacturing_cost', 'final_unit_price')
    def _compute_cost_ratios(self):
        for rec in self:
            if rec.final_unit_price:
                rec.material_cost_ratio = rec.total_material_cost / rec.final_unit_price
                rec.manufacturing_cost_ratio = rec.total_manufacturing_cost / rec.final_unit_price
            else:
                rec.material_cost_ratio = 0.0
                rec.manufacturing_cost_ratio = 0.0
