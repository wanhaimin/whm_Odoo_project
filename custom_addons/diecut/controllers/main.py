# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class MaterialWebsite(http.Controller):
    
    @http.route(['/materials', '/materials/page/<int:page>'], type='http', auth='public', website=True)
    def materials_list(self, page=1, category=None, search=None, **kwargs):
        """材料列表页面"""
        domain = [('is_published', '=', True)]
        
        # 分类筛选
        if category:
            category_obj = request.env['product.category'].sudo().browse(int(category or 0))
            domain.append(('category_id', '=', category_obj.id))
        
        # 搜索
        if search:
            domain += ['|', ('name', 'ilike', search), ('code', 'ilike', search)]
        
        # 分页
        materials_per_page = 12
        total_materials = request.env['my.material'].sudo().search_count(domain)
        pager = request.website.pager(
            url='/materials',
            total=total_materials,
            page=page,
            step=materials_per_page,
            url_args={'category': category, 'search': search}
        )
        
        materials = request.env['my.material'].sudo().search(
            domain,
            limit=materials_per_page,
            offset=pager['offset'],
            order='create_date desc'
        )
        
        # 获取所有分类
        categories = request.env['product.category'].sudo().search([])
        
        return request.render('diecut_custom.materials_list', {
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
        material = request.env['my.material'].sudo().browse(material_id)
        
        if not material.exists() or not material.is_published:
            return request.redirect('/materials')
        
        # 增加浏览次数
        material.action_increase_view_count()
        
        # 推荐材料(同分类)
        recommended_materials = request.env['my.material'].sudo().search([
            ('category_id', '=', material.category_id.id),
            ('id', '!=', material.id),
            ('is_published', '=', True)
        ], limit=4)
        
        return request.render('diecut_custom.material_detail', {
            'material': material,
            'recommended_materials': recommended_materials,
        })
    
    @http.route(['/sample/order'], type='http', auth='user', website=True)
    def sample_order_form(self, **kwargs):
        """打样订单表单"""
        materials = request.env['my.material'].sudo().search([
            ('is_published', '=', True)
        ])
        
        return request.render('diecut_custom.sample_order_form', {
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
        material_id = int(post.get('material_id') or 0)
        line_vals = {
            'order_id': order.id,
            'material_id': material_id,
            'length': float(post.get('length') or 0.0),
            'width': float(post.get('width') or 0.0),
            'thickness': float(post.get('thickness') or 0.0),
            'quantity': int(post.get('quantity') or 10),
            'process_type': post.get('process_type', 'die_cut'),
            'special_requirements': post.get('special_requirements'),
        }
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
        
        return request.render('diecut_custom.sample_order_success', {
            'order': order,
        })
    
    @http.route(['/my/sample/orders'], type='http', auth='user', website=True)
    def my_sample_orders(self, **kwargs):
        """我的打样订单"""
        orders = request.env['sample.order'].sudo().search([
            ('partner_id', '=', request.env.user.partner_id.id)
        ], order='create_date desc')
        
        return request.render('diecut_custom.my_sample_orders', {
            'orders': orders,
        })
