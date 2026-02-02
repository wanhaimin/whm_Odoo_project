from odoo import models, fields, api
from odoo.exceptions import UserError
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
    customer_id = fields.Many2one('res.partner', string='所属客户', tracking=True, domain=[('customer_rank', '>', 0)])
    product_id = fields.Many2one('product.product', string='关联产品', tracking=True)
    supplier_id = fields.Many2one('res.partner', string='供应商', tracking=True)
    purchase_date = fields.Date(string='采购日期', tracking=True)
    design_by = fields.Many2one('res.partner', string='工程师', tracking=True)
    
    
    state = fields.Selection([
        ('draft', '草稿'),
        ('qc_inspection', 'QC检验'),
        ('available', '可使用'),
        ('using', '使用中'),
        ('repair', '维修中'),
        ('scrapped', '已报废')
    ], string='状态', default='draft', tracking=True)
    
    # QC检验相关字段
    qc_assigned_to = fields.Many2one('res.users', string='指定检验员', tracking=True,
                                     help="指定负责QC检验的人员")
    qc_result = fields.Selection([
        ('pass', '合格'),
        ('fail', '不合格'),
    ], string='QC结果', tracking=True)
    qc_date = fields.Datetime(string='QC检验时间', readonly=True, tracking=True)
    qc_inspector = fields.Many2one('res.users', string='实际检验员', readonly=True, tracking=True,
                                   help="实际执行QC检验的人员")
    qc_notes = fields.Text(string='QC备注')

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
    location_id = fields.Many2one('diecut.mold.location', string='存放位置', tracking=True)
    active = fields.Boolean(string='有效', default=True, tracking=True)
    note = fields.Text(string='备注')
    
    # --- 报废信息 (审计) ---
    scrap_reason = fields.Text(string='报废原因', readonly=True, tracking=True)
    scrap_date = fields.Datetime(string='报废时间', readonly=True, tracking=True)
    scrapped_by = fields.Many2one('res.users', string='报废操作人', readonly=True, tracking=True)


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
            error_correction=qrcode.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(self.code)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        # 使用 positional argument 避免 vague "format not found" 错误，且兼容性更好
        img.save(buffer, "PNG")
        return base64.b64encode(buffer.getvalue()).decode()

    # === 状态转换方法 (QC检验流程) ===
    
    def action_submit_to_qc(self):
        """打开QC检验向导，指定检验员"""
        self.ensure_one()
        return {
            'name': '提交QC检验',
            'type': 'ir.actions.act_window',
            'res_model': 'diecut.mold.qc.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_mold_id': self.id},
        }
    
    def action_qc_pass(self):
        """QC检验合格 - 仅检验员可操作"""
        self.ensure_one()
        
        # 权限检查：只有被指定的检验员才能操作
        if self.qc_assigned_to and self.qc_assigned_to.id != self.env.user.id:
            raise UserError(f"只有被指定的检验员 {self.qc_assigned_to.name} 才能执行QC检验操作!")
        
        self.write({
            'state': 'available',
            'qc_result': 'pass',
            'qc_date': fields.Datetime.now(),
            'qc_inspector': self.env.user.id,
        })
        
        # 发送通知给提交人
        self.message_post(
            body=f"✅ QC检验合格！检验员: {self.env.user.name}",
            subject="QC检验通过",
            message_type='notification',
        )
    
    def action_qc_fail(self):
        """QC检验不合格 - 仅检验员可操作"""
        self.ensure_one()
        
        # 权限检查：只有被指定的检验员才能操作
        if self.qc_assigned_to and self.qc_assigned_to.id != self.env.user.id:
            raise UserError(f"只有被指定的检验员 {self.qc_assigned_to.name} 才能执行QC检验操作!")
        
        if not self.qc_notes:
            raise UserError("QC检验不合格时,必须填写QC备注说明不合格原因!")
        
        self.write({
            'state': 'draft',
            'qc_result': 'fail',
            'qc_date': fields.Datetime.now(),
            'qc_inspector': self.env.user.id,
        })
        
        # 发送通知给提交人
        self.message_post(
            body=f"❌ QC检验不合格！检验员: {self.env.user.name}<br/>原因: {self.qc_notes}",
            subject="QC检验不通过",
            message_type='notification',
        )
    
    def action_set_using(self):
        """投入使用"""
        if self.state != 'available':
            raise UserError("只有'可使用'状态的刀模才能投入使用!")
        self.write({'state': 'using'})
    
    def action_set_repair(self):
        """送修"""
        self.write({'state': 'repair'})
    
    def action_repair_complete(self):
        """维修完成 - 提交QC检验"""
        self.write({
            'state': 'qc_inspection',
            'qc_result': False,  # 清空之前的检验结果
            'qc_date': False,
            'qc_inspector': False,
        })
    
    def action_set_scrapped(self):
        """打开报废向导"""
        self.ensure_one()
        return {
            'name': '确认报废',
            'type': 'ir.actions.act_window',
            'res_model': 'diecut.mold.scrap.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_mold_id': self.id},
        }
    
    def action_back_to_draft(self):
        """退回草稿状态"""
        self.write({'state': 'draft'})


# ============================================================================
# 刀模存放位置模型
# ============================================================================
class MoldLocation(models.Model):
    _name = 'diecut.mold.location'
    _description = '刀模存放位置'
    _order = 'name'
    
    name = fields.Char(string='位置编号', required=True, help="例如: A-01-03")
    description = fields.Text(string='位置说明')
    active = fields.Boolean(string='有效', default=True)
    
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', '位置编号必须唯一！')
    ]


# ============================================================================
# 刀模报废向导
# ============================================================================
class MoldScrapWizard(models.TransientModel):
    _name = 'diecut.mold.scrap.wizard'
    _description = '刀模报废向导'
    
    mold_id = fields.Many2one('diecut.mold', string='刀模', required=True, readonly=True)
    
    scrap_reason_type = fields.Selection([
        ('wear', '刀锋磨损严重,无法继续使用'),
        ('deform', '基材变形,影响产品质量'),
        ('lifetime', '已达到设计寿命上限'),
        ('obsolete', '客户产品停产,不再需要'),
        ('damaged', '运输或使用中损坏'),
        ('quality', '质量问题,无法满足精度要求'),
        ('other', '其他原因(请在下方说明)'),
    ], string='报废原因', required=True, default='wear')
    
    scrap_reason_custom = fields.Text(
        string='详细说明', 
        help="请详细描述报废的具体情况"
    )
    
    # 保存最终的完整报废原因
    scrap_reason = fields.Text(string='完整报废原因', compute='_compute_scrap_reason', store=True)
    
    @api.depends('scrap_reason_type', 'scrap_reason_custom')
    def _compute_scrap_reason(self):
        for record in self:
            # 获取选项的显示文本
            selection_list = [
                ('wear', '刀锋磨损严重,无法继续使用'),
                ('deform', '基材变形,影响产品质量'),
                ('lifetime', '已达到设计寿命上限'),
                ('obsolete', '客户产品停产,不再需要'),
                ('damaged', '运输或使用中损坏'),
                ('quality', '质量问题,无法满足精度要求'),
                ('other', '其他原因(请在下方说明)'),
            ]
            
            main_reason = ''
            for key, label in selection_list:
                if key == record.scrap_reason_type:
                    main_reason = label
                    break
            
            if record.scrap_reason_type == 'other' and record.scrap_reason_custom:
                record.scrap_reason = f"{main_reason}\n详细说明: {record.scrap_reason_custom}"
            elif record.scrap_reason_custom:
                record.scrap_reason = f"{main_reason}\n补充说明: {record.scrap_reason_custom}"
            else:
                record.scrap_reason = main_reason
    
    def action_confirm_scrap(self):
        """确认报废"""
        self.ensure_one()
        
        # 如果选择"其他原因",必须填写详细说明
        if self.scrap_reason_type == 'other' and not self.scrap_reason_custom:
            raise UserError("选择'其他原因'时,必须填写详细说明!")
        
        if self.scrap_reason_type == 'other' and len(self.scrap_reason_custom.strip()) < 5:
            raise UserError("详细说明不少于5个字符!")
        
        # 更新刀模状态和报废信息，并自动存档
        self.mold_id.write({
            'state': 'scrapped',
            'active': False,  # 自动存档
            'scrap_reason': self.scrap_reason,
            'scrap_date': fields.Datetime.now(),
            'scrapped_by': self.env.user.id,
        })
        
        return {'type': 'ir.actions.act_window_close'}


# ============================================================================
# QC检验向导
# ============================================================================
class MoldQCWizard(models.TransientModel):
    _name = 'diecut.mold.qc.wizard'
    _description = 'QC检验向导'
    
    mold_id = fields.Many2one('diecut.mold', string='刀模', required=True, readonly=True)
    qc_assigned_to = fields.Many2one('res.users', string='指定检验员', required=True,
                                     help="选择负责此次QC检验的人员")
    notes = fields.Text(string='备注说明')
    
    def action_confirm_qc(self):
        """确认提交QC检验"""
        self.ensure_one()
        
        # 更新刀模状态并指定检验员
        self.mold_id.write({
            'state': 'qc_inspection',
            'qc_assigned_to': self.qc_assigned_to.id,
            'qc_result': False,  # 清空之前的检验结果
            'qc_date': False,
            'qc_inspector': False,
        })
        
        # 创建活动提醒通知检验员
        self.mold_id.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.qc_assigned_to.id,
            summary=f'QC检验: {self.mold_id.code}',
            note=f"""
                <p><strong>刀模QC检验任务</strong></p>
                <ul>
                    <li>刀模编号: {self.mold_id.code}</li>
                    <li>刀模名称: {self.mold_id.name}</li>
                    <li>提交人: {self.env.user.name}</li>
                    {f'<li>备注: {self.notes}</li>' if self.notes else ''}
                </ul>
                <p>请及时进行QC检验并标记为合格或不合格。</p>
            """,
        )
        
        # 发送消息通知
        self.mold_id.message_post(
            body=f"🔍 已提交QC检验<br/>检验员: {self.qc_assigned_to.name}<br/>提交人: {self.env.user.name}",
            subject="提交QC检验",
            message_type='notification',
            partner_ids=[self.qc_assigned_to.partner_id.id],
        )
        
        return {'type': 'ir.actions.act_window_close'}
