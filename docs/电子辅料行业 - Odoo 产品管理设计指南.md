# 

## 行业背景

电子辅料行业主要涉及：
- **原材料**：胶带、泡棉、离型膜、保护膜、屏蔽材料、导电布等
- **加工产品**：分切料、模切件、复合材料等

---

## 产品分类设计

### 推荐分类结构

```
产品分类 (product.category)
├── 原材料
│   ├── 胶带类
│   │   ├── 双面胶带
│   │   ├── 单面胶带
│   │   ├── 导电胶带
│   │   └── 导热胶带
│   ├── 泡棉类
│   │   ├── PE泡棉
│   │   ├── IXPE泡棉
│   │   └── PU泡棉
│   ├── 离型膜
│   ├── 保护膜
│   ├── 屏蔽材料
│   │   ├── 铜箔
│   │   ├── 铝箔
│   │   └── 导电布
│   └── 其他辅料
├── 半成品
│   ├── 分切料
│   └── 复合材料
└── 成品
    ├── 模切件
    └── 定制产品
```

---

## 设计方案一：使用标准 product.template（推荐新手）

### 优点
- 使用 Odoo 原生产品管理
- 无需额外开发
- 与销售、采购、库存完美集成

### 实现方式

#### 1. 创建产品分类

```xml
<!-- data/product_category_data.xml -->
<odoo>
    <data noupdate="1">
        <!-- 原材料分类 -->
        <record id="category_raw_material" model="product.category">
            <field name="name">原材料</field>
        </record>
        
        <record id="category_tape" model="product.category">
            <field name="name">胶带类</field>
            <field name="parent_id" ref="category_raw_material"/>
        </record>
        
        <record id="category_foam" model="product.category">
            <field name="name">泡棉类</field>
            <field name="parent_id" ref="category_raw_material"/>
        </record>
        
        <!-- 成品分类 -->
        <record id="category_finished" model="product.category">
            <field name="name">成品</field>
        </record>
        
        <record id="category_die_cut" model="product.category">
            <field name="name">模切件</field>
            <field name="parent_id" ref="category_finished"/>
        </record>
    </data>
</odoo>
```

#### 2. 继承 product.template 添加行业特有字段

```python
# models/product_extend.py
from odoo import models, fields, api

class ProductTemplateElectronic(models.Model):
    _inherit = 'product.template'
    
    # ========== 原材料通用字段 ==========
    material_type = fields.Selection([
        ('raw', '原材料'),
        ('semi', '半成品'),
        ('finished', '成品'),
    ], string='材料类型', default='raw')
    
    # 供应商信息（扩展）
    brand = fields.Char('品牌')
    origin_country = fields.Many2one('res.country', string='原产国')
    
    # ========== 规格参数 ==========
    # 基材信息
    base_material = fields.Char('基材')  # 如 PET, PI, PE 等
    adhesive_type = fields.Char('胶系')  # 如 亚克力胶, 硅胶, 橡胶等
    
    # 尺寸规格
    spec_thickness = fields.Float('厚度 (mm)', digits=(10, 3))
    spec_width = fields.Float('宽度 (mm)', digits=(10, 2))
    spec_length = fields.Float('长度 (m)', digits=(10, 2))
    
    # 卷材信息
    roll_diameter = fields.Float('卷径 (mm)')
    core_diameter = fields.Selection([
        ('25', '25mm'),
        ('38', '38mm'),
        ('50', '50mm'),
        ('76', '76mm'),
    ], string='管芯')
    
    # ========== 性能参数 ==========
    # 粘性相关
    adhesion_strength = fields.Float('粘着力 (N/25mm)')
    initial_tack = fields.Char('初粘性')
    holding_power = fields.Char('保持力')
    
    # 温度相关
    temp_resistance_min = fields.Float('耐温下限 (°C)')
    temp_resistance_max = fields.Float('耐温上限 (°C)')
    
    # 电气性能
    surface_resistance = fields.Char('表面电阻')
    volume_resistance = fields.Char('体积电阻')
    dielectric_strength = fields.Float('击穿电压 (kV)')
    
    # 其他性能
    tensile_strength = fields.Float('拉伸强度 (N/25mm)')
    elongation = fields.Float('伸长率 (%)')
    
    # ========== 颜色/外观 ==========
    material_color = fields.Selection([
        ('transparent', '透明'),
        ('white', '白色'),
        ('black', '黑色'),
        ('gray', '灰色'),
        ('other', '其他'),
    ], string='颜色')
    
    # ========== 认证与合规 ==========
    rohs_compliant = fields.Boolean('RoHS 认证')
    reach_compliant = fields.Boolean('REACH 认证')
    ul_certified = fields.Boolean('UL 认证')
    halogen_free = fields.Boolean('无卤')
    
    # ========== 存储要求 ==========
    storage_temp_min = fields.Float('存储温度下限 (°C)')
    storage_temp_max = fields.Float('存储温度上限 (°C)')
    storage_humidity = fields.Char('存储湿度要求')
    shelf_life = fields.Integer('保质期 (月)')
    
    # ========== 技术资料 ==========
    tds_file = fields.Binary('TDS (技术规格书)')
    tds_filename = fields.Char('TDS 文件名')
    msds_file = fields.Binary('MSDS (安全数据表)')
    msds_filename = fields.Char('MSDS 文件名')
    
    # ========== 计算字段 ==========
    spec_display = fields.Char('规格描述', compute='_compute_spec_display', store=True)
    
    @api.depends('spec_thickness', 'spec_width', 'spec_length')
    def _compute_spec_display(self):
        for record in self:
            parts = []
            if record.spec_thickness:
                parts.append(f'{record.spec_thickness}mm')
            if record.spec_width:
                parts.append(f'{record.spec_width}mm')
            if record.spec_length:
                parts.append(f'{record.spec_length}m')
            record.spec_display = ' × '.join(parts) if parts else ''
```

#### 3. 创建视图

```xml
<!-- views/product_template_views.xml -->
<odoo>
    <!-- 继承产品模板表单视图 -->
    <record id="product_template_form_electronic" model="ir.ui.view">
        <field name="name">product.template.form.electronic</field>
        <field name="model">product.template</field>
        <field name="inherit_id" ref="product.product_template_form_view"/>
        <field name="arch" type="xml">
            <!-- 在基本信息后添加规格页签 -->
            <xpath expr="//page[@name='general_information']" position="after">
                <page string="规格参数" name="specifications">
                    <group>
                        <group string="基本规格">
                            <field name="material_type"/>
                            <field name="brand"/>
                            <field name="base_material"/>
                            <field name="adhesive_type"/>
                            <field name="material_color"/>
                        </group>
                        <group string="尺寸规格">
                            <field name="spec_thickness"/>
                            <field name="spec_width"/>
                            <field name="spec_length"/>
                            <field name="roll_diameter"/>
                            <field name="core_diameter"/>
                        </group>
                    </group>
                    <group>
                        <group string="粘性参数">
                            <field name="adhesion_strength"/>
                            <field name="initial_tack"/>
                            <field name="holding_power"/>
                        </group>
                        <group string="温度性能">
                            <field name="temp_resistance_min"/>
                            <field name="temp_resistance_max"/>
                        </group>
                    </group>
                    <group>
                        <group string="电气性能">
                            <field name="surface_resistance"/>
                            <field name="volume_resistance"/>
                            <field name="dielectric_strength"/>
                        </group>
                        <group string="机械性能">
                            <field name="tensile_strength"/>
                            <field name="elongation"/>
                        </group>
                    </group>
                </page>
                
                <page string="认证与存储" name="certifications">
                    <group>
                        <group string="认证信息">
                            <field name="rohs_compliant"/>
                            <field name="reach_compliant"/>
                            <field name="ul_certified"/>
                            <field name="halogen_free"/>
                        </group>
                        <group string="存储要求">
                            <field name="storage_temp_min"/>
                            <field name="storage_temp_max"/>
                            <field name="storage_humidity"/>
                            <field name="shelf_life"/>
                        </group>
                    </group>
                    <group string="技术资料">
                        <field name="tds_file" filename="tds_filename"/>
                        <field name="msds_file" filename="msds_filename"/>
                    </group>
                </page>
            </xpath>
            
            <!-- 在产品名称下方显示规格 -->
            <xpath expr="//field[@name='name']" position="after">
                <field name="spec_display" readonly="1" class="oe_inline"/>
            </xpath>
        </field>
    </record>
    
    <!-- 列表视图添加规格列 -->
    <record id="product_template_tree_electronic" model="ir.ui.view">
        <field name="name">product.template.tree.electronic</field>
        <field name="model">product.template</field>
        <field name="inherit_id" ref="product.product_template_tree_view"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='name']" position="after">
                <field name="spec_display" optional="show"/>
                <field name="brand" optional="hide"/>
                <field name="material_type" optional="show"/>
            </xpath>
        </field>
    </record>
</odoo>
```

---

## 设计方案二：区分原材料和成品（推荐复杂业务）

如果您的业务需要严格区分原材料和成品，可以使用产品分类 + 筛选视图：

### 1. 原材料专用视图

```xml
<!-- views/raw_material_views.xml -->
<odoo>
    <!-- 原材料列表视图 -->
    <record id="view_raw_material_tree" model="ir.ui.view">
        <field name="name">raw.material.tree</field>
        <field name="model">product.template</field>
        <field name="arch" type="xml">
            <list string="原材料列表">
                <field name="default_code"/>
                <field name="name"/>
                <field name="brand"/>
                <field name="spec_display"/>
                <field name="base_material"/>
                <field name="spec_thickness"/>
                <field name="spec_width"/>
                <field name="standard_price" widget="monetary"/>
                <field name="uom_id"/>
                <field name="qty_available" optional="show"/>
            </list>
        </field>
    </record>
    
    <!-- 原材料动作 -->
    <record id="action_raw_materials" model="ir.actions.act_window">
        <field name="name">原材料</field>
        <field name="res_model">product.template</field>
        <field name="view_mode">list,form,kanban</field>
        <field name="domain">[('material_type', '=', 'raw')]</field>
        <field name="context">{'default_material_type': 'raw', 'default_purchase_ok': True}</field>
        <field name="help" type="html">
            <p class="o_view_nocontent_smiling_face">
                创建您的第一个原材料
            </p>
        </field>
    </record>
    
    <!-- 成品动作 -->
    <record id="action_finished_products" model="ir.actions.act_window">
        <field name="name">成品</field>
        <field name="res_model">product.template</field>
        <field name="view_mode">list,form,kanban</field>
        <field name="domain">[('material_type', '=', 'finished')]</field>
        <field name="context">{'default_material_type': 'finished', 'default_sale_ok': True}</field>
    </record>
    
    <!-- 菜单 -->
    <menuitem id="menu_electronic_materials" 
              name="电子辅料管理" 
              sequence="5"/>
    
    <menuitem id="menu_raw_materials" 
              name="原材料" 
              parent="menu_electronic_materials"
              action="action_raw_materials"
              sequence="10"/>
    
    <menuitem id="menu_finished_products" 
              name="成品" 
              parent="menu_electronic_materials"
              action="action_finished_products"
              sequence="20"/>
</odoo>
```

---

## 设计方案三：使用变体管理规格（高级）

如果同一种材料有多种规格（如同一品牌胶带有不同宽度），可以使用产品变体：

### 概念

```
产品模板：3M 9495LE 双面胶带
    ├── 变体1：3M 9495LE - 10mm宽
    ├── 变体2：3M 9495LE - 20mm宽
    ├── 变体3：3M 9495LE - 50mm宽
    └── 变体4：3M 9495LE - 100mm宽
```

### 实现

```python
# 1. 创建宽度属性
# 在 Odoo 界面：产品 > 配置 > 属性

# 2. 或通过代码创建
class ProductAttributeData(models.Model):
    _inherit = 'product.attribute'
    
    @api.model
    def _create_width_attribute(self):
        # 创建宽度属性
        width_attr = self.create({
            'name': '宽度',
            'display_type': 'select',
            'create_variant': 'always',
        })
        
        # 创建属性值
        widths = ['10mm', '20mm', '30mm', '50mm', '100mm', '200mm', '500mm', '1000mm']
        for width in widths:
            self.env['product.attribute.value'].create({
                'name': width,
                'attribute_id': width_attr.id,
            })
```

### 变体应用场景

| 场景                 | 是否使用变体 | 说明               |
| -------------------- | ------------ | ------------------ |
| 同品牌同型号不同宽度 | ✅ 是         | 宽度作为变体属性   |
| 不同品牌的类似产品   | ❌ 否         | 创建不同的产品模板 |
| 同产品不同颜色       | ✅ 是         | 颜色作为变体属性   |
| 完全不同的产品       | ❌ 否         | 创建不同的产品模板 |

---

## 原材料编码规则建议

### 编码格式

```
[分类代码]-[品牌代码]-[型号]-[规格]
```

### 示例

| 编码              | 说明                    |
| ----------------- | ----------------------- |
| `TP-3M-9495LE-50` | 胶带-3M-9495LE-50mm宽   |
| `FM-ROG-4701-10`  | 泡棉-Rogers-4701-10mm厚 |
| `SF-TDK-ICF5-10`  | 屏蔽-TDK-ICF5-10um      |

### 自动编码

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    @api.model
    def create(self, vals):
        if not vals.get('default_code'):
            # 自动生成编码
            categ = self.env['product.category'].browse(vals.get('categ_id'))
            prefix = self._get_category_prefix(categ)
            sequence = self.env['ir.sequence'].next_by_code('product.material.code')
            vals['default_code'] = f'{prefix}-{sequence}'
        return super().create(vals)
    
    def _get_category_prefix(self, categ):
        """根据分类返回前缀"""
        prefix_map = {
            '胶带类': 'TP',
            '泡棉类': 'FM',
            '离型膜': 'RL',
            '保护膜': 'PF',
            '屏蔽材料': 'SF',
        }
        return prefix_map.get(categ.name, 'XX')
```

---

## 与库存模块集成

### 1. 启用批次管理

对于需要追溯的原材料：

```python
class ProductTemplateElectronic(models.Model):
    _inherit = 'product.template'
    
    @api.model
    def create(self, vals):
        # 原材料默认启用批次追踪
        if vals.get('material_type') == 'raw':
            vals.setdefault('tracking', 'lot')
        return super().create(vals)
```

### 2. 批次扩展字段

```python
class StockLot(models.Model):
    _inherit = 'stock.lot'
    
    # 原材料批次信息
    manufacture_date = fields.Date('生产日期')
    expiry_date = fields.Date('有效期')
    supplier_lot = fields.Char('供应商批号')
    coa_file = fields.Binary('COA (检验报告)')
    coa_filename = fields.Char('COA 文件名')
```

---

## 完整模块结构

```
my_electronic_materials/
├── __init__.py
├── __manifest__.py
├── data/
│   ├── product_category_data.xml
│   └── ir_sequence_data.xml
├── models/
│   ├── __init__.py
│   ├── product_template.py
│   └── stock_lot.py
├── views/
│   ├── product_template_views.xml
│   ├── raw_material_views.xml
│   └── menu_views.xml
└── security/
    └── ir.model.access.csv
```

---

## 快速开始步骤

### 第一步：创建产品分类
在 Odoo 界面：**库存 > 配置 > 产品分类**

### 第二步：添加自定义字段
通过自定义模块继承 `product.template`

### 第三步：创建原材料
1. 进入 **库存 > 产品 > 产品**
2. 点击 **创建**
3. 填写产品信息和规格参数
4. 设置 **可采购** = True
5. 设置 **产品类型** = 可库存产品

### 第四步：创建成品
1. 创建产品，设置 **可销售** = True
2. 关联 BOM（物料清单）指定原材料用量

---

## 总结

| 方案               | 适用场景                 | 复杂度 |
| ------------------ | ------------------------ | ------ |
| 方案一（标准扩展） | 中小企业，产品种类适中   | ⭐⭐     |
| 方案二（分类视图） | 需要严格区分原材料和成品 | ⭐⭐⭐    |
| 方案三（变体管理） | 同一产品多种规格         | ⭐⭐⭐⭐   |

**建议**：从方案一开始，根据业务需要逐步扩展。
