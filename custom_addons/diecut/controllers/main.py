# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class MaterialWebsite(http.Controller):
    
    @http.route(['/materials', '/materials/page/<int:page>'], type='http', auth='public', website=True)
    def materials_list(self, page=1, category=None, search=None, **kwargs):
        """材料列表页面"""
        # 使用 Odoo 原生的 website_published 机制
        # 对于 Product, 可以在 is_published 上过滤，且只看 raw material
        domain = [('is_published', '=', True), ('is_raw_material', '=', True)]
        
        # 分类筛选
        if category:
            category_obj = request.env['product.category'].sudo().browse(int(category or 0))
            domain.append(('categ_id', '=', category_obj.id))
        
        # 搜索
        if search:
            domain += ['|', ('name', 'ilike', search), ('default_code', 'ilike', search)]
        
        # 分页
        materials_per_page = 12
        total_materials = request.env['product.template'].sudo().search_count(domain)
        pager = request.website.pager(
            url='/materials',
            total=total_materials,
            page=page,
            step=materials_per_page,
            url_args={'category': category, 'search': search}
        )
        
        materials = request.env['product.template'].sudo().search(
            domain,
            limit=materials_per_page,
            offset=pager['offset'],
            order='create_date desc'
        )
        
        # 获取所有分类 (只获取原材料分类)
        # 假设原材料分类是 'category_type'='raw' 或者您有特定的根分类
        categories = request.env['product.category'].sudo().search([('category_type', '=', 'raw')]) 
        if not categories:
             categories = request.env['product.category'].sudo().search([])

        return request.render('diecut.materials_list', {
            'materials': materials,
            'categories': categories,
            'pager': pager,
            'search': search,
            'current_category': int(category or 0) if category else None,
            'total_count': total_materials,
        })
    
    @http.route(['/material/<int:material_id>'], type='http', auth='public', website=True)
    def material_detail(self, material_id, **kwargs):
        """材料详情页面"""
        # Browse product.template
        material = request.env['product.template'].sudo().browse(material_id)
        
        if not material.exists() or not material.is_published: # or not material.is_raw_material:
            return request.redirect('/materials')
        
        # 增加浏览次数
        # 注意：product.template 原生没有 view_count, 使用我们自定义加的
        if hasattr(material, 'view_count'):
             material.sudo().write({'view_count': material.view_count + 1})

        # 推荐材料(同分类)
        recommended_materials = request.env['product.template'].sudo().search([
            ('categ_id', '=', material.categ_id.id),
            ('id', '!=', material.id),
            ('is_published', '=', True),
            ('is_raw_material', '=', True)
        ], limit=4)
        
        return request.render('diecut.material_detail', {
            'material': material,
            'recommended_materials': recommended_materials,
        })
    
    @http.route(['/sample/order'], type='http', auth='user', website=True)
    def sample_order_form(self, **kwargs):
        """打样订单表单"""
        materials = request.env['product.template'].sudo().search([
            ('is_published', '=', True),
            ('is_raw_material', '=', True)
        ])
        
        return request.render('diecut.sample_order_form', {
            'materials': materials,
        })
    
    @http.route(['/sample/order/submit'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def sample_order_submit(self, **post):
        """提交打样订单"""
        # 创建打样订单
        order_vals = {
            'partner_id': request.env.user.partner_id.id,
            'product_name': post.get('product_name'),
            'product_model': post.get('product_model'),
            'application': post.get('application'),
            'quantity': int(post.get('quantity') or 10),
            'urgency': post.get('urgency', 'normal'),
            'note': post.get('note'),
        }
        
        order = request.env['sample.order'].sudo().create(order_vals)
        
        # 创建订单明细
        # material_id 此处来自前端选择，实际上是 product.template ID
        # 如果 sample.order.line 需要 product.product, 我们需要转换
        template_id = int(post.get('material_id') or 0)
        product_id = False
        if template_id:
             tmpl = request.env['product.template'].sudo().browse(template_id)
             # 获取第一个变体
             if tmpl.product_variant_ids:
                 product_id = tmpl.product_variant_ids[0].id
        
        line_vals = {
            'order_id': order.id,
            'material_id': product_id, # 注意 sample.order.line 现在应该链接 product.product
            'length': float(post.get('length') or 0.0),
            'width': float(post.get('width') or 0.0),
            'thickness': float(post.get('thickness') or 0.0),
            'quantity': int(post.get('quantity') or 10),
            'process_type': post.get('process_type', 'die_cut'),
            'special_requirements': post.get('special_requirements'),
        }
        # 如果没选材料（product_id is False），可能要在 sample.order.line 允许为空或者抛错
        # 假设允许为空
        
        request.env['sample.order.line'].sudo().create(line_vals)
        
        # 提交订单
        order.action_submit()
        
        return request.redirect('/sample/order/success/%s' % order.id)
    
    @http.route(['/sample/order/success/<int:order_id>'], type='http', auth='user', website=True)
    def sample_order_success(self, order_id, **kwargs):
        """订单提交成功页面"""
        order = request.env['sample.order'].sudo().browse(order_id)
        
        if not order.exists():
            return request.redirect('/materials')
        
        return request.render('diecut.sample_order_success', {
            'order': order,
        })
    
    @http.route(['/my/sample/orders'], type='http', auth='user', website=True)
    def my_sample_orders(self, **kwargs):
        """我的打样订单"""
        orders = request.env['sample.order'].sudo().search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], order='create_date desc')
        
        return request.render('diecut.my_sample_orders', {
            'orders': orders,
        })
