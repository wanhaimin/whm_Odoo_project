# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductCategoryExtend(models.Model):
    """产品分类扩展 - 添加三级目录结构字段"""
    _inherit = 'product.category'
    _order = 'sequence, id'  # 按序列和ID排序
    
    _name_parent_uniq = models.Constraint(
        'UNIQUE(name, parent_id)',
        '同一层级下不能有重复的分类名称！',
    )
    
    # ==================== 排序字段 ====================
    sequence = fields.Integer(
        string='排序',
        default=10,
        help='用于控制分类在层级视图中的显示顺序，数字越小越靠前'
    )
    
    # ==================== 通用字段 ====================
    level = fields.Integer(
        string='分类级别',
        compute='_compute_level',
        store=True,
        recursive=True,
        help='1=一级分类, 2=二级分类, 3=三级分类'
    )
    
    # 带缩进的分类名称（用于列表视图显示层级）
    indent_name = fields.Char(
        string='分类名称',
        compute='_compute_indent_name',
        search='_search_indent_name'
    )
    
    description = fields.Text('分类描述')
    
    # ==================== 一级分类字段 ====================
    category_type = fields.Selection([
        ('raw', '原材料'),
        ('semi', '半成品'),
        ('finished', '成品'),
    ], string='分类类型', help='一级分类手动设置，子分类自动继承', compute='_compute_category_type', store=True, recursive=True, readonly=False)
    
    # ==================== 二级分类字段 ====================
    material_code_prefix = fields.Char(
        string='材料编码前缀',
        help='二级分类的材料编码前缀，如：JD(胶带), PM(泡棉)'
    )
    
    # ==================== 三级分类字段 ====================
    specification = fields.Char(
        string='规格描述',
        help='三级分类的规格描述'
    )
    
    default_thickness = fields.Float(
        string='默认厚度(mm)',
        help='三级分类的默认厚度'
    )
    
    # ==================== 动态属性字段 ====================
    diecut_properties_definition = fields.PropertiesDefinition(string='物理特性库')
    
    @api.depends('parent_id', 'parent_id.level')
    def _compute_level(self):
        """计算分类级别"""
        for category in self:
            if not category.parent_id:
                category.level = 1
            elif not category.parent_id.parent_id:
                category.level = 2
            else:
                category.level = 3
    
    @api.depends('parent_id.category_type')
    def _compute_category_type(self):
        """子分类自动继承父分类的类型"""
        for category in self:
            if category.parent_id:
                category.category_type = category.parent_id.category_type
    
    @api.depends('name', 'level')
    def _compute_indent_name(self):
        """计算带缩进的分类名称"""
        for category in self:
            # 使用等宽字体对齐逻辑 (每级4字符宽)
            # ├──  (4 chars)
            # │   ├──  (4 chars + 4 chars)
            prefix = ''
            if category.level == 1:
                prefix = ''
            elif category.level == 2:
                prefix = '├── '
            elif category.level == 3:
                # │ + 3个空格 = 4字符宽，对齐上一级的 ├── 
                prefix = '│      ├── '
            
            category.indent_name = prefix + (category.name or '')
    
    def _search_indent_name(self, operator, value):
        """支持按名称搜索"""
        return [('name', operator, value)]
    
    @api.constrains('name', 'parent_id')
    def _check_unique_name_per_parent(self):
        """检查同一父分类下是否有重复名称"""
        for category in self:
            domain = [
                ('name', '=', category.name),
                ('parent_id', '=', category.parent_id.id if category.parent_id else False),
                ('id', '!=', category.id)
            ]
            if self.search_count(domain) > 0:
                parent_name = category.parent_id.name if category.parent_id else '根目录'
                raise ValidationError(
                    f'分类名称"{category.name}"在"{parent_name}"下已存在，请使用不同的名称！'
                )


    # ==================== 网站展示字段 ====================
    image = fields.Binary('分类图片')
    
    material_count = fields.Integer(
        '官网展示材料数量', 
        compute='_compute_material_count'
    )
    
    def _compute_material_count(self):
        for category in self:
            # 计算该分类下已发布的材料数量
            # 注意：这里需要根据实际情况查询 product.template 或 my.material
            # 假设我们现在主要关注 my.material 的数量（如果是用于网站展示）
            # 或者如果是通用的，应该查询 product.product
            
            # 改为查询 product.template
            count = self.env['product.template'].search_count([
                ('categ_id', 'child_of', category.id),
                ('is_published', '=', True),
                ('is_raw_material', '=', True)
            ])
            category.material_count = count
