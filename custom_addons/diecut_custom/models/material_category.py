# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MaterialCategory(models.Model):
    _name = 'material.category'
    _description = '材料分类'
    _parent_name = 'parent_id'
    _parent_store = True
    _order = 'complete_name'
    
    name = fields.Char('分类名称', required=True, translate=True)
    complete_name = fields.Char(
        '完整名称', 
        compute='_compute_complete_name',
        recursive=True, 
        store=True
    )
    parent_id = fields.Many2one(
        'material.category', 
        '父分类', 
        index=True, 
        ondelete='cascade'
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('material.category', 'parent_id', '子分类')
    
    material_count = fields.Integer(
        '材料数量', 
        compute='_compute_material_count'
    )
    
    description = fields.Text('描述')
    image = fields.Binary('分类图片')
    active = fields.Boolean('有效', default=True)
    
    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = '%s / %s' % (category.parent_id.complete_name, category.name)
            else:
                category.complete_name = category.name
    
    def _compute_material_count(self):
        for category in self:
            category.material_count = self.env['material.material'].search_count([
                ('category_id', 'child_of', category.id)
            ])
    
    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError('不能创建循环的分类层级!')
        return True
 