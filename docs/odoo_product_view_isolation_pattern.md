# Odoo 产品矩阵隔离设计：底层统一，前端千人千面

在制造与模切行业中，物料种类横跨极广（原材料、包材辅料、半成品、产成品、模治具等）。如果将所有产品混在一个列表中展示，不仅会让视图显得极其杂乱，而且会导致严重的字段冗余（例如：产成品列表被强行塞入“原材料厚度、离型力”等完全无关的字段）。

为了解决这一痛点，Odoo 最佳架构实践主张：**“底层统一归口 `product.template`，前端依靠 `Action Domain` 与 `专属 View` 彻底隔离各个大类。”**

---

## 一、架构设计核心思路

这种设计方案具有三大核心优势，属于框架层面的“降维打击”：

1. **千人千面（视图解耦）**：采购人员点开“原材料库”，看到的是附带搜索面板（SearchPanel）、单价/m²、厚度参数的专属列表；业务员点开“产成品库”，看到的是清爽的含有客户指导价、BOM结构的专属列表。两者互不干扰。
2. **底层安全（性能最优）**：因为数据库底座全都是标准产品表（`product.template`），无论是仓库收发货打单子、盘点库存，还是跑 MRP（物料需求计划）运算时，系统都无需跨多表查询。数据流闭环且极度高效。
3. **极强扩展性（极速配置）**：未来若新增如“行政办公耗材”、“设备备件”等大类，无需任何 Python 建模成本，仅需复制几十行 XML 并在 Domain 中配置拦截条件，瞬间就能生成一个具备完备进销存能力的独立菜单体系。

---

## 二、三步实现“产成品与原材料”的完美隔离

### 第一步：在模型定义专属大类标记（Python 改造）

我们不再使用单一零散的 Boolean 字段（如 `is_raw_material`），而是通过统一的 `Selection` 枚举对产品的大物权属性进行强分类管理。

```python
# models/product_diecut.py
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # 定义一个模切行业专用的核心物料生命周期大类标记
    diecut_product_type = fields.Selection([
        ('raw', '原材料'),
        ('packaging', '包材/辅料'),
        ('mold', '模具/治具/刀具'),
        ('semi_finished', '内加工半成品'),
        ('finished', '对外销售产成品'),
    ], string="物料专属大类", default='finished', required=True, tracking=True)
```

### 第二步：为每一个大类“量身定制”专属视图（XML 渲染层）

抛弃杂糅的通用表头，为“原材料”、“产成品”、“包材”单独编写它们最关心的 `List` (曾称 `Tree`) 视图和 `Form` 视图。

```xml
<!-- 1. 产成品 专属树状(List)视图：重心为销售属性 -->
<record id="view_diecut_finished_tree" model="ir.ui.view">
    <field name="name">diecut.finished.tree</field>
    <field name="model">product.template</field>
    <field name="arch" type="xml">
        <list string="产成品库">
            <field name="name"/>
            <field name="default_code" string="型号/零件号"/>
            <!-- 产成品销售属性：价格与对应的客户群 -->
            <field name="list_price" string="指导零售价" widget="monetary"/>
            <field name="categ_id" string="产品线大类"/>
            <!-- 无需显示原辅料属性（如厚度、胶系、米数） -->
        </list>
    </field>
</record>

<!-- 2. 包材辅料 专属树状(List)视图：重心为包装规格与供应商属性 -->
<record id="view_diecut_packaging_tree" model="ir.ui.view">
    <field name="name">diecut.packaging.tree</field>
    <field name="model">product.template</field>
    <field name="arch" type="xml">
        <list string="包材辅料库">
            <field name="name"/>
            <field name="uom_id" string="包装单位(包/卷/箱)"/>
            <field name="seller_ids" string="包材主要来源" widget="many2many_tags"/>
        </list>
    </field>
</record>
```

### 第三步：定义行为与权限边界（Action Domain 切割数据集）

这是至关重要的一步，利用 Odoo 强大的窗口动作调度能力拦截数据库结果集，并通过 Context 赋权绑定给特定菜单使用。

```xml
<!-- 行动 1：发往产成品的独立 Action -->
<record id="action_diecut_finished" model="ir.actions.act_window">
    <field name="name">产成品库</field>
    <field name="res_model">product.template</field>
    
    <!-- 【域拦截核心】：通过 Domain 限制这个菜单查询引擎只返回 'finished' 类型的物料 -->
    <field name="domain">[('diecut_product_type', '=', 'finished')]</field>
    
    <!-- 【上下文核心】：当用户位于此页面点击新建按钮时，默默带上产成品标记，同时智能默认其可售属性 -->
    <field name="context">{
        'default_diecut_product_type': 'finished',
        'default_sale_ok': True,
        'default_purchase_ok': False
    }</field>
    
    <!-- 【视图强绑定核心】：强行将列表渲染器指向第二步里写好的“产成品专属 XML”界面 -->
    <field name="view_ids" eval="[(5, 0, 0), (0, 0, {'view_mode': 'list', 'view_id': ref('view_diecut_finished_tree')})]"/>
</record>

<!-- 行动 2：发往包材辅料的独立 Action -->
<record id="action_diecut_packaging" model="ir.actions.act_window">
    <field name="name">包材与辅料</field>
    <field name="res_model">product.template</field>
    <field name="domain">[('diecut_product_type', '=', 'packaging')]</field>
    <!-- 包材基本不可直接销售，但完全允许采购外购 -->
    <field name="context">{
        'default_diecut_product_type': 'packaging',
        'default_sale_ok': False,
        'default_purchase_ok': True
    }</field>
    <field name="view_ids" eval="[(5, 0, 0), (0, 0, {'view_mode': 'list', 'view_id': ref('view_diecut_packaging_tree')})]"/>
</record>
```

---

## 总结：一种大道至简的工程美学

当完成了上述重构，看似业务前台上**“凭空多出了五个完全独立且专业的物料管理软件与报表”**，但对于底层数据库维护和后续诸如 MRP 等子模块而言，我们依然在操作同一张 `product.template` 表。

这种将复杂性的隔离交由渲染端和业务路由端处理，而把连贯性留给数据库底座的做法，正是** Odoo 最为推崇的工程美学和架构之道。**
