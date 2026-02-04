# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class Material(models.Model):
    _name = 'material.material'
    _description = '材料'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'website.published.mixin']
    _order = 'name'
    
    # 基本信息
    name = fields.Char('材料名称', required=True, tracking=True)
    code = fields.Char('材料编号', required=True, copy=False, tracking=True)
    category_id = fields.Many2one('product.category', 
                                  '材料分类', 
                                  required=True, 
                                  tracking=True,
                                  domain="[('category_type', '=', 'raw')]")
    
    # 生产商信息
    manufacturer_id = fields.Many2one(
        'res.partner', 
        '生产商',
        domain="[('is_company', '=', True), ('supplier_rank', '>', 0)]",
        tracking=True
    )
    brand = fields.Char('品牌')
    origin = fields.Char('产地')
    
    # 状态
    state = fields.Selection([
        ('active', '在产'),
        ('discontinued', '停产'),
        ('development', '开发中'),
    ], string='状态', default='active', required=True, tracking=True)
    
    # 物理特性
    thickness = fields.Float('厚度(μm)', digits=(10, 2))
    width = fields.Float('宽度(mm)', digits=(10, 2))
    length = fields.Float('长度(m)', digits=(10, 2))
    density = fields.Float('密度(g/cm³)', digits=(10, 3))
    color = fields.Char('颜色')
    transparency = fields.Selection([
        ('transparent', '透明'),
        ('translucent', '半透明'),
        ('opaque', '不透明'),
    ], string='透明度')
    
    # 性能参数
    tensile_strength = fields.Float('拉伸强度(MPa)', digits=(10, 2))
    tear_strength = fields.Float('撕裂强度(N)', digits=(10, 2))
    temp_resistance_min = fields.Float('耐温下限(℃)')
    temp_resistance_max = fields.Float('耐温上限(℃)')
    adhesion = fields.Float('粘性(N/25mm)', digits=(10, 2))
    
    # 商务信息
    supplier_ids = fields.Many2many(
        'res.partner', 
        'material_supplier_rel',
        'material_id', 'partner_id',
        string='供应商',
        domain="[('is_company', '=', True), ('supplier_rank', '>', 0)]"
    )
    reference_price = fields.Monetary('参考价格(元/平方米)', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', 
        string='货币',
        default=lambda self: self.env.company.currency_id
    )
    moq = fields.Float('最小起订量', digits=(10, 2))
    moq_unit = fields.Selection([
        ('sqm', '平方米'),
        ('kg', '千克'),
        ('roll', '卷'),
        ('sheet', '张'),
    ], string='起订量单位', default='sqm')
    lead_time = fields.Integer('交货期(天)')
    
    # 文档资料
    datasheet = fields.Binary('规格书')
    datasheet_filename = fields.Char('规格书文件名')
    test_report = fields.Binary('测试报告')
    test_report_filename = fields.Char('测试报告文件名')
    
    # 图片
    image_1920 = fields.Binary('图片')
    image_1024 = fields.Binary('中等图片', related='image_1920', store=True)
    image_512 = fields.Binary('小图片', related='image_1920', store=True)
    image_256 = fields.Binary('缩略图', related='image_1920', store=True)
    
    # 应用信息
    application = fields.Text('应用场景')
    process_note = fields.Text('加工工艺说明')
    caution = fields.Text('注意事项')
    
    # 统计信息
    view_count = fields.Integer('浏览次数', default=0, readonly=True)
    inquiry_count = fields.Integer('询价次数', default=0, readonly=True)
    
    # 其他
    description = fields.Html('详细描述')
    # active = fields.Boolean('有效', default=True) # Field already defined in standard models, but okay
    active = fields.Boolean('有效', default=True)
    
    # 网站发布
    website_published = fields.Boolean('网站发布', copy=False)
    website_url = fields.Char('网站URL', compute='_compute_website_url')
    
    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError('材料编号必须唯一!')

    @api.depends('name')
    def _compute_website_url(self):
        for material in self:
            if material.id:
                material.website_url = '/material/%s' % material.id
            else:
                material.website_url = False
    
    def action_increase_view_count(self):
        """增加浏览次数"""
        self.sudo().write({'view_count': self.view_count + 1})
    
    def action_increase_inquiry_count(self):
        """增加询价次数"""
        self.sudo().write({'inquiry_count': self.inquiry_count + 1})
    
    def action_publish(self):
        """发布到网站"""
        self.website_published = True
    

    def action_unpublish(self):
        """从网站取消发布"""
        self.website_published = False

    def unlink(self):
        for record in self:
            # Check if referenced in Diecut Quote Material Lines
            # We use search count first for speed, but here we want names
            lines = self.env['diecut.quote.material.line'].search([('material_id', '=', record.id)])
            if lines:
                quotes = lines.mapped('quote_id.name')
                # Filter out False/None just in case and get unique names
                quotes = list(set([q for q in quotes if q]))
                
                quote_msg = ", ".join(quotes[:5])
                if len(quotes) > 5:
                     quote_msg += f" ... (共 {len(quotes)} 个引用)"
                
                raise UserError(f"无法删除材料 '{record.name}'！\n该材料已被以下报价单引用：\n[{quote_msg}]\n\n为了保持历史数据完整性，系统不允许直接删除。\n\n建议操作：\n请使用顶部菜单的【动作 -> 归档】功能来隐藏该材料。")
        
        return super().unlink()
    
