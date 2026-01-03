# -*- coding: utf-8 -*-
from odoo import models, fields, api

class MyMaterial(models.Model):
    _name = 'my.material'
    _inherit = ['my.material', 'website.published.mixin']

    # 扩展网站统计字段
    view_count = fields.Integer('浏览次数', default=0, readonly=True)
    inquiry_count = fields.Integer('询价次数', default=0, readonly=True)

    # 扩展业务字段以支持网站展示
    application = fields.Text('应用场景', help="用于网站前端展示该材料的典型应用领域")
    process_note = fields.Text('加工工艺说明', help="用于网站前端展示加工建议")

    # 定义 website_url 字段
    website_url = fields.Char('网站URL', compute='_compute_website_url', readonly=True)

    # 覆盖 website_url 的计算逻辑
    def _compute_website_url(self):
        for material in self:
            material.website_url = '/material/%s' % material.id

    def action_increase_view_count(self):
        self.sudo().write({'view_count': self.view_count + 1})

    def action_increase_inquiry_count(self):
        self.sudo().write({'inquiry_count': self.inquiry_count + 1})

    def action_publish(self):
        self.write({'is_published': True})

    def action_unpublish(self):
        self.write({'is_published': False})

class MyMaterialCategory(models.Model):
    _inherit = 'my.material.category'

    material_count = fields.Integer(
        '官网展示材料数量', 
        compute='_compute_material_count'
    )
    
    image = fields.Binary('分类图片')

    def _compute_material_count(self):
        for category in self:
            # 计算该分类下已发布的材料数量
            category.material_count = self.env['my.material'].search_count([
                ('category_id', '=', category.id),
                ('is_published', '=', True)
            ])
