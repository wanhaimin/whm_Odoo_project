---
name: odoo_diecut_dev
description: 模切管理系统 (Diecut ERP) 专属 Odoo 19 开发规范与领域知识。在处理 diecut 模块的代码编写、视图美化、数据建模或价格换算任务时，必须先阅读此技能。
---

# 模切管理系统 (Diecut ERP) 开发指南

欢迎协助开发 Odoo 19 `diecut` 模块！该系统专为电子辅料模切行业设计，包含材料选型大全、原材料管理、成本计算器等功能。在修改此模块前，请**务必遵循以下核心开发准则**。更详尽的架构和决定请随时查阅 `custom_addons/diecut/docs/DESIGN_MANUAL.md`。

## 1. 核心数据模型职责与隔离 (`product_diecut.py`)

系统基于原生的 `product.template` 和 `product.product` 进行扩展，通过两个互斥的布尔标志位区分产品用途：

*   **`is_catalog=True` (选型目录材料)**:
    *   仅用于技术选型参考。
    *   **不要**让其出现在销售、采购、库存等原生业务链路上。
    *   相关的搜索视图或动作域 (Domain) 必须明确添加隔离条件：例如采购入口过滤掉它。
*   **`is_raw_material=True` (ERP 原材料)**:
    *   真正参与模切生产和采购交易的业务数据实体。
    *   带有具体的形态（卷料 R / 片料 S）、宽度、长度、供应商和精确的面积计价。

当用户觉得某个目录材料适合使用时，通过 `diecut.catalog.activate.wizard` (选型目录启用向导) 将其一键转化为新的 ERP 原材料 (`is_raw_material=True`)，并建立 `source_catalog_variant_id` 的防重复追溯关系。

## 2. 统一底层价格换算体系 (平方米计价)

这是**最容易出错的业务逻辑**，所有涉及单价的修改必须遵守此规则：
所有材料在底层必须统一按**每平方米单价 (RMB/m²)** 计价。

*   `product.supplierinfo` (供应商价格表) 上的原生 `price` 也就是 `price_per_m2`。
*   **计算公式**:
    *   `面积 (m²) = 宽度(mm) / 1000 × 长度(m)` （如果是片料，长度字段后台也必须转换为米）
    *   `整卷/片成本 (raw_material_unit_price) = price_per_m2 × 面积`
    *   `公斤单价 (price_per_kg) = price_per_m2 × 面积 ÷ 重量`

## 3. 视图设计与前端交互规范 (ADR-010)

针对 Odoo 19 的前端 (Owl VDOM)：

*   **严禁前端拖拽操作 DOM 排版**: 我们废弃了使用原生 JS (如 MutationObserver, 拖拽修改顺序) 手动对 Form 视图中 `<group>` 和字段进行重排的尝试，那会严重破坏 Odoo 19 VDOM 的底层绑定。
*   **采用 Bootstrap 5 栅格卡片**: 任何表单界面的高级美化，**必须使用底层 XML + Bootstrap 5 Card & Grid 方案**。
    *   示例结构：`<div class="row g-3"><div class="col-md-4"><div class="card shadow-sm border-0">...</div></div></div>`。
    *   请通过色块区分（如 `bg-light`, `text-primary`）和图标来提升表单的现代化 Dashboard 体验。

## 4. 动态列显隐与 SearchPanel 联动

在型号清单的列表视图 (List View) 中，为了根据数据的不同实现“全空列自动隐藏”或隐藏特定列（如密度），系统使用了 Odoo 钦定的 Owl VDOM 扩展机制：
通过 `@web/core/utils/patch` 拦截 `@web/views/list/list_renderer` 组件的 `getActiveColumns()` 方法，**在渲染前剔除无数据的属性列** (`static/src/js/catalog_dynamic_columns.js`)。

*   **严禁使用 DOM 操作**: 不要用以往的 jQuery 或者纯 Vanilla JS (如 `document.querySelectorAll`) 去操作界面节点或注入隐藏 CSS。那是 Anti-pattern，会导致 Owl 组件重绘冲突和严重崩盘。
*   **性能优化 (最佳实践)**: 这种在数据层 (Props/State) 挂载到视图 (View) 之前提前剔除“无用列”的做法，相比先在 DOM 渲染完整表格再注入 CSS 隐藏的方案，**彻底避免了浏览器极其昂贵的 DOM 强制重绘与重排 (Repaint & Reflow)**。它让浏览器少渲染了成百上千个不必要的 `<td/>` 节点，极大提升了加载速度和内存效率。
*   所有的前端列表/表格视图拓展都应该建立在拦截 Owl 的 Props、Hook 或拦截 Renderer 函数的思路上。

## 5. 选型目录数据的初始化规范 (Excel 驱动多变体代码生成)

*   **分离与降维原则**：严禁在 XML 内部使用 `<function>` 或复杂的 `<record>` 强行注入 `product.product` 变体级别的技术参数（如厚度、初粘力、颜色）。
*   **全自动化代码生成模式**：考虑到可能有成百上千个系列和成千上万个变体，所有选型目录的数据维护**必须完全剥离给业务人员在 Excel CSV（`scripts/series.csv` 和 `scripts/variants.csv`）中进行维护**。
*   **XML 仅用于注册骨架**：像 `product.template` (系列)、`product.attribute` (大类) 和 `product.attribute.value` (型号) 这种需要在 Odoo 中取得外部 ID (`ir.model.data`) 的底层字典，由 Python 生成器（`scripts/generate_catalog.py`）自动读取 Excel 生成（如 `catalog_sidike_data.xml`、`catalog_tesa_data.xml`）。
*   **JSON 专门管理变体血肉**：所有变体的具体参数值（如物理特性）由上述脚本自动萃取清洗并生成至统一的 `data/catalog_materials.json` 脑图文件中，以防人为修改引发语法报错。
*   **后置触发器 (`noupdate=0` 大法)**：在模块最后加载 `data/load_json_data.xml` 触发对 `product.template` 模型上的 `_load_catalog_base_data_from_json()` 调用。每次点击“Upgrade”更新模型时，这层逻辑会自动遍历读取 JSON 并赋予给变体参数：**此逻辑内嵌了 `getattr` 防覆盖机制**，绝不会顶替用户在前端手动修改过的值。

## 5. 富文本与富客户端体验

*   产品特点 (`catalog_features`) 和典型应用 (`catalog_applications`) 是 Odoo `Html` 字段类型。请注意，它们以 HTML 标签形式存储结构化排版。
*   型号标准索引 (`variant_thickness_std_index` 等) 是一种为了方便快速查询而派生的字段字符串聚合机制，通过 `_compute_variant_std_index` 维护，请勿随意破坏它。

***
> **Agent 工作流提示**：
> 如果您看到涉及 `diecut` 的改动（尤其是 Python 计算逻辑、XML 界面排版的优化），请将这些规则视为第一优先级。若有未尽事宜，请调用文件读取工具翻阅 `DESIGN_MANUAL.md` 以获取最新最全的设计意图。
