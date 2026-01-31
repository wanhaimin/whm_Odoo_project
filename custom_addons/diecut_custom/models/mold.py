from odoo import models, fields, api
import base64
import io
import qrcode

class DiecutMold(models.Model):
    _name = 'diecut.mold'
    _description = '刀模数据库'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'code'

    # --- 基础信息 ---
    name = fields.Char(string='刀模名称', required=True, tracking=True)
    code = fields.Char(string='模具编号', required=True, default='New', readonly=True, tracking=True)
    image = fields.Image(string='模具照片')

    # --- 业务信息 (提前到这里) ---
    customer_id = fields.Many2one('res.partner', string='所属客户', tracking=True)
    product_id = fields.Many2one('product.product', string='关联产品', tracking=True)
    supplier_id = fields.Many2one('res.partner', string='供应商', tracking=True)
    purchase_date = fields.Date(string='采购日期', tracking=True)
    design_by = fields.Many2one('res.partner', string='工程师', tracking=True)
    
    state = fields.Selection([
        ('draft', '草稿'),
        ('available', '待用'),
        ('using', '使用中'),
        ('repair', '维修中'),
        ('scrapped', '已报废')
    ], string='状态', default='draft', tracking=True)

    mold_type = fields.Selection([
        ('wood', '木板模'),
        ('etch', '蚀刻模'),
        ('engrave', '雕刻模'),
        ('QDC', 'QDC模'),
        ('other', '其他')
    ], string='模具类型', default='etch', tracking=True)

    # --- 技术规格 ---
    size_length = fields.Float(string='长度 (mm)', tracking=True)
    size_width = fields.Float(string='宽度 (mm)', tracking=True)
    size_height = fields.Float(string='高度 (mm)', tracking=True)
    blade_height = fields.Float(string='刀锋高度 (mm)', tracking=True)
    blade_thickness = fields.Float(string='刀锋厚度 (mm)', tracking=True)
    
    # --- 生产与工艺参数 ---
    cavity = fields.Integer(string='出数 (UPS)', default=1, help="一刀切多少个产品，例如 1出4，填4", tracking=True)
    gap_distance = fields.Float(string='跳距 (mm)', help="模具行进的步距", tracking=True)
    machine_models = fields.Char(string='适用机型', help="该刀模适用的机器型号")
    blade_brand = fields.Char(string='刀材品牌', help="例如：日本中山、奥地利BOHLER")
    
    # --- 圆刀专用参数 ---
    gear_teeth = fields.Integer(string='齿数 (Z)', help="圆刀模专用")
    is_rotary = fields.Boolean(string='是圆刀', compute='_compute_is_rotary', store=True)

    # --- 二维码专用字段 (用于报表) ---
    qr_code_image = fields.Binary(string="二维码", compute="_compute_qr_code_image")

    @api.depends('code')
    def _compute_qr_code_image(self):
        for record in self:
            record.qr_code_image = record.get_qr_code_base64()

    @api.depends('mold_type')
    def _compute_is_rotary(self):
        for record in self:
            # 假定 蚀刻模(flexible) 和 雕刻模(solid) 通常用于轮转机
            record.is_rotary = record.mold_type in ['etch', 'engrave']
    
    # --- 寿命管理 ---
    total_life = fields.Integer(string='设计寿命 (冲次)', default=100000)
    used_life = fields.Integer(string='已使用冲次', default=0, tracking=True)
    remaining_life = fields.Integer(string='剩余寿命', compute='_compute_remaining_life', store=True)

    @api.depends('total_life', 'used_life')
    def _compute_remaining_life(self):
        for record in self:
            record.remaining_life = record.total_life - record.used_life

    # --- 存储信息 ---
    location = fields.Char(string='存放位置', help="例如: A-01-03", tracking=True)
    active = fields.Boolean(string='有效', default=True, tracking=True)
    note = fields.Text(string='备注')


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                vals['code'] = self.env['ir.sequence'].next_by_code('diecut.mold') or 'New'
        return super(DiecutMold, self).create(vals_list)

    def get_qr_code_base64(self):
        self.ensure_one()
        if not self.code:
            return ''
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(self.code)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
