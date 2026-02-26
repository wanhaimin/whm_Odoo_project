# Odoo 19 `searchpanel` 侧边栏筛选功能指南

## 一、功能背景
在很多业务场景（尤其是物料台账、原材料管理等）下，用户需要类似 **Excel 筛选器** 的操作体验：能够快速勾选出某个分类、选定某个供应商的数据，并实时更新列表视图。
而在 Odoo 的官方“Odoo Way”设计理念中，为了保证列表上方的整洁，这种“多选、统计数量且高度交互”的过滤功能被统一封装为 **侧边栏面板（SearchPanel）**，而不是塞在树状图的表头（Column Header）上。

## 二、功能优势
1. **纯原生配置**：这是 Odoo 框架内建支持的功能。无需编写任何额外的 JavaScript/Owl 代码，无需安装第三方复杂的前端插件。
2. **多维统计与过滤**：
   - 它可以做到**多选关联（Selection: Multiple）**。
   - 它可以智能带出该维度当前的**数量汇总统计（Count）**。
3. **高内聚性**：它的定义被放置在视图架构层 `ir.ui.view` 的 `<search>` 标签下，与其他过滤器统一进行权限与渲染分发。

---

## 三、代码实施步骤

### 1. 明确适用的字段条件
在 Odoo 中，左侧面版的 `searchpanel` 标签下的字段 **必须是**：
* 关联类型 (`Many2one`)
* 或 下拉选择类型 (`Selection`)

> **⚠️核心避坑：**
> 普通文本字段（`Char`）不支持被放入 `searchpanel`。如果您的某项分类（诸如 `material_type` ）被定义为 `Char`，为了利用这种原生的多选筛选功能，架构上推荐将其改造为 `Many2one` 关联独立的一张数据表，或 `Selection` 枚举字段。

### 2. 在视图的 XML 内编写 `<searchpanel>`

首先，您需要单独定义一个 `search` 视图（如果还没有的话）：

```xml
<!-- 示例：定义专用的 Search 视图 -->
<record id="view_diecut_raw_material_search" model="ir.ui.view">
    <field name="name">diecut.raw.material.search</field>
    <field name="model">product.template</field> <!-- 指定您的模型 -->
    <field name="arch" type="xml">
        <search>
            <!-- 顶部的常规条件搜索逻辑 -->
            <field name="name" string="产品名称/编码" filter_domain="['|', '|', ('default_code', 'ilike', self), ('name', 'ilike', self), ('barcode', 'ilike', self)]"/>
            <field name="material_type" string="材质/牌号"/>
            
            <!-- 🌟 左侧 Excel 风格过滤面板 🌟 -->
            <searchpanel>
                <!-- select="multi": 允许像Excel一样勾选多个类别 -->
                <!-- enable_counters="1": 显示各个分类下的条目数量 -->
                <!-- icon="fa-tags": 设置面板图标 -->
                <field name="categ_id" string="材料分类" select="multi" enable_counters="1" icon="fa-tags"/>
                
                <field name="main_vendor_id" string="厂商" select="multi" enable_counters="1" icon="fa-building"/>
            </searchpanel>
        </search>
    </field>
</record>
```

### 3. 将搜索视图绑定至业务 Action

创建好了搜索视图后，需要将其绑定到对应的窗口动作（`ir.actions.act_window`）上。通过指定 `search_view_id` 属性让该入口独享这个左侧面板特性，保证不干扰全局通用的产品视图。

```xml
<record id="action_diecut_raw_material" model="ir.actions.act_window">
    <field name="name">原材料库</field>
    <field name="res_model">product.template</field>
    <field name="view_mode">list,kanban,form</field>
    <!-- domain与上下文，按需配置 -->
    <field name="domain">[('is_raw_material', '=', True)]</field>
    <field name="context">{'default_is_raw_material': True}</field>
    
    <!-- 关键属性映射：指向刚才定义的 Search 视图 ID -->
    <field name="search_view_id" ref="view_diecut_raw_material_search"/>
    
    <field name="view_ids" eval="[(5, 0, 0),
        (0, 0, {'view_mode': 'list', 'view_id': ref('view_diecut_raw_material_tree')}),
        (0, 0, {'view_mode': 'form', 'view_id': ref('product.product_template_only_form_view')})]"/>
</record>
```

---

## 四、进阶：实现树状层级结构 (Tree / Hierarchy)

对于具有产品分类 (`product.category`) 等具有无限极父子关联（即内置 `parent_id`）的模型，Odoo 能够完美地渲染出**支持点击展开/折叠**的树状结构导航。

### 实现方式
在使用 `<searchpanel>` 时，需要做如下关键属性调整：
1. **移除 `select="multi"`**：因为在严谨的树形钻取结构中，往往表示层层递进的单选查看模式，与毫无限制的复选框打平逻辑存在天然冲突，必须去掉才能启用真正的层级数。
2. **新增 `hierarchize="1"`**：这是一个决定性的参数，用于告诉 Odoo 此时要自动通过模型的 `parent_id` 加载为多级树。
3. **新增 `expand="1"` (可选但推荐)**：如果不加该参数，树状结构默认是全部折叠的，用户需逐级点击三角箭头展开。加上之后，页面刷新时会自动展开下面的所有层级！
4. （可选）修改图标：例如将标签形图标 `icon="fa-tags"` 更换为适合目录列表的 `icon="fa-list"`。

### 示例代码
```xml
<searchpanel>
    <!-- hierarchize="1": 开启无限极树状结构 -->
    <!-- expand="1" : 默认展开所有的子层级分类 -->
    <!-- 注意：此处去掉了 select="multi" -->
    <field name="categ_id" string="分类" enable_counters="1" icon="fa-list" hierarchize="1" expand="1" />
</searchpanel>
```

---

## 五、核心避坑：如何彻底隐藏 SearchPanel 中其他无关的空根分类？

在原生 Odoo 中，如果你给 `searchpanel` 内的字段配置了 `hierarchize="1"`（树状折叠），**Odoo 的底层逻辑会强制查询该分类模型里的所有“根节点（Root）”来进行全树渲染**。这会导致即使你在字段上写了各种 `domain` 限制，左侧面板依然会顽固地把“成品、半成品、Goods”等无关大类全部列出来（只是计数为 0），显得极其冗长。而且在 XML 内强加 `domain` 直接会导致解析致命报错。

👉 **终极“重载”救国解决方案如下：**

因为 `<searchpanel>` 的数据提取逻辑是由后端的专门接口负责查询的，我们只需要到你的目标产品模型中，**拦截（Override）** Odoo 原生的 `search_panel_select_multi_range` 和 `search_panel_select_range` 方法，直接过滤掉无关数据！

在你的产品模型 `product.template` 里面增加以下重写方法：

```python
    @api.model
    def search_panel_select_multi_range(self, field_name, **kwargs):
        """ 重写多选搜索面板获取方法，暴力干掉与原材料无关的分类 """
        res = super(ProductTemplate, self).search_panel_select_multi_range(field_name, **kwargs)
        if field_name == 'raw_material_categ_id':  # 这里拦截你专门给面板分配的那个字段
            # 从数据库里查出允许显示的分类ID池（比如只有 raw 这个大类和它的子类）
            allowed_ids = self.env['product.category'].search([('category_type', '=', 'raw')]).ids
            if isinstance(res, list):
                res = [r for r in res if dict(r).get('id') in allowed_ids]
            elif isinstance(res, dict) and 'values' in res:
                res['values'] = [r for r in res['values'] if dict(r).get('id') in allowed_ids]
        return res

    @api.model
    def search_panel_select_range(self, field_name, **kwargs):
        """ 兼容单选模式获取方法的拦截 """
        res = super(ProductTemplate, self).search_panel_select_range(field_name, **kwargs)
        if field_name == 'raw_material_categ_id':
            allowed_ids = self.env['product.category'].search([('category_type', '=', 'raw')]).ids
            if isinstance(res, list):
                res = [r for r in res if dict(r).get('id') in allowed_ids]
            elif isinstance(res, dict) and 'values' in res:
                res['values'] = [r for r in res['values'] if dict(r).get('id') in allowed_ids]
        return res
```

通过这一招硬核拦截，你返回给前台视图的数据里就彻底失去了那群“无关根节点分类”的户口，再复杂的查询引擎也只能乖乖渲染我们指定的分类体系！

---

## 六、总结

通过 `<searchpanel>` 结构处理类 Excel 表格头的多选条件，以及利用 `hierarchize="1"` 开启清晰直观的树状缩进导航，是被 Odoo 官方长期维护且极力推崇的最优途径。只要结合上 Python 后端方法 `search_panel_select_multi_range` 的拦截过滤技巧，整个渲染将既灵活又干净，同时大幅度提高查询的精准度与用户操作体验！
