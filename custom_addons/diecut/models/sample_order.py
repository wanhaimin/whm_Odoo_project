# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SampleOrder(models.Model):
    _name = 'sample.order'
    _description = '打样订单'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    
    name = fields.Char('订单号', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', '客户', required=True, tracking=True)
    partner_email = fields.Char(related='partner_id.email', string='客户邮箱', store=True)
    partner_phone = fields.Char(related='partner_id.phone', string='客户电话', store=True)
    
    # 产品信息
    product_name = fields.Char('产品名称', required=True)
    product_model = fields.Char('产品型号')
    application = fields.Char('应用场景')
    
    # 明细行
    line_ids = fields.One2many('sample.order.line', 'order_id', '打样明细')
    
    # 数量
    quantity = fields.Integer('打样数量', default=10, required=True)
    
    # 交期
    urgency = fields.Selection([
        ('normal', '正常(3-5天)'),
        ('urgent', '加急(1-2天)'),
        ('super_urgent', '特急(24小时)'),
    ], string='紧急程度', default='normal', required=True)
    
    requested_date = fields.Date('期望交期')
    promised_date = fields.Date('承诺交期', tracking=True)
    
    # 费用
    material_cost = fields.Monetary('材料成本', compute='_compute_costs', store=True)
    processing_cost = fields.Monetary('加工费用', compute='_compute_costs', store=True)
    sample_fee = fields.Monetary('打样费', compute='_compute_costs', store=True)
    shipping_cost = fields.Monetary('运费', default=0)
    total_cost = fields.Monetary('总费用', compute='_compute_costs', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # 状态
    state = fields.Selection([
        ('draft', '草稿'),
        ('submitted', '已提交'),
        ('confirmed', '已确认'),
        ('in_production', '生产中'),
        ('ready', '待发货'),
        ('shipped', '已发货'),
        ('delivered', '已交付'),
        ('cancelled', '已取消'),
    ], string='状态', default='draft', tracking=True)
    
    # 备注
    note = fields.Text('备注')
    
    @api.depends('line_ids.material_cost', 'line_ids.processing_cost', 'urgency', 'shipping_cost')
    def _compute_costs(self):
        for record in self:
            record.material_cost = sum(record.line_ids.mapped('material_cost'))
            record.processing_cost = sum(record.line_ids.mapped('processing_cost'))
            
            # 打样费计算
            base_fee = 100
            if record.urgency == 'urgent':
                base_fee *= 1.5
            elif record.urgency == 'super_urgent':
                base_fee *= 2.0
            
            record.sample_fee = base_fee
            record.total_cost = (record.material_cost + 
                               record.processing_cost + 
                               record.sample_fee + 
                               record.shipping_cost)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sample.order') or 'New'
        return super().create(vals_list)
    
    def action_submit(self):
        """提交订单"""
        self.state = 'submitted'
        # 发送邮件通知
        template = self.env.ref('diecut_custom.email_template_sample_order_submitted', raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=True)
    
    def action_confirm(self):
        """确认订单"""
        self.state = 'confirmed'
    
    def action_cancel(self):
        """取消订单"""
        self.state = 'cancelled'


class SampleOrderLine(models.Model):
    _name = 'sample.order.line'
    _description = '打样明细'
    _order = 'sequence, id'
    
    order_id = fields.Many2one('sample.order', '打样订单', required=True, ondelete='cascade')
    sequence = fields.Integer('序号', default=10)
    
    # 材料
    material_id = fields.Many2one('material.material', '材料', required=True)
    material_code = fields.Char(related='material_id.code', string='材料编号', store=True)
    
    # 尺寸
    length = fields.Float('长度(mm)', digits=(10, 2), required=True)
    width = fields.Float('宽度(mm)', digits=(10, 2), required=True)
    thickness = fields.Float('厚度(μm)', digits=(10, 2))
    
    # 数量
    quantity = fields.Integer('数量', default=1, required=True)
    area = fields.Float('面积(cm²)', compute='_compute_area', store=True)
    
    # 加工
    process_type = fields.Selection([
        ('die_cut', '模切'),
        ('lamination', '贴合'),
        ('printing', '印刷'),
        ('slitting', '分切'),
    ], string='加工类型', required=True, default='die_cut')
    
    special_requirements = fields.Text('特殊要求')
    
    # 费用
    material_cost = fields.Monetary('材料成本', compute='_compute_costs', store=True)
    processing_cost = fields.Monetary('加工费用', compute='_compute_costs', store=True)
    subtotal = fields.Monetary('小计', compute='_compute_costs', store=True)
    currency_id = fields.Many2one(related='order_id.currency_id')
    
    @api.depends('length', 'width')
    def _compute_area(self):
        for record in self:
            record.area = (record.length * record.width) / 100 if record.length and record.width else 0
    
    @api.depends('material_id', 'area', 'quantity', 'process_type')
    def _compute_costs(self):
        for record in self:
            # 材料成本
            material_price = record.material_id.reference_price or 0
            record.material_cost = material_price * record.area * record.quantity / 10000
            
            # 加工费用
            process_rates = {
                'die_cut': 0.05,
                'lamination': 0.08,
                'printing': 0.10,
                'slitting': 0.03,
            }
            rate = process_rates.get(record.process_type, 0.05)
            record.processing_cost = record.area * record.quantity * rate
            
            record.subtotal = record.material_cost + record.processing_cost
