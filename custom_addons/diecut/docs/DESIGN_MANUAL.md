# 模切管理系统 (Diecut ERP) — 设计手册

> **版本**: v1.7
> **模块技术名**: `diecut`
> **Odoo 版本**: 19
> **最后更新**: 2026-03-13
> **维护者**: 开发团队

---

## 目录

1. [系统概述](#1-系统概述)
2. [模块架构](#2-模块架构)
3. [数据模型详解](#3-数据模型详解)
4. [核心业务规则](#4-核心业务规则)
5. [状态机与工作流](#5-状态机与工作流)
6. [视图与菜单结构](#6-视图与菜单结构)（含 [6.7 表单视图高级 UI 布局 (Bootstrap 5 栅格)](#6-7-表单视图高级-ui-布局-bootstrap-5-栅格)、[6.8 型号清单分屏工作台](#6-8-型号清单分屏工作台)）
7. [安全与权限](#7-安全与权限)
8. [设计决策记录 (ADR)](#8-设计决策记录-adr)
9. [数据库约束与索引](#9-数据库约束与索引)
10. [变更日志](#10-变更日志)

- [附录 A: 如何维护本手册](#附录-a-如何维护本手册)
- [附录 B: Odoo 开发与运维指南](#附录-b-odoo-开发指南) (含 [B.4 数据备份与恢复](#b-4-数据备份与恢复))
- [附录 C: 材料选型大全行业共建共享（设想提纲）](#附录-c-材料选型大全行业共建共享设想提纲)

---

`<a id="1-系统概述"></a>`

## 1. 系统概述

### 1.1 业务背景

模切（Die-cutting）是电子产品制造中的关键工艺，涉及胶带、泡棉、铜箔、绝缘材料等多种辅材的精密裁切。本系统基于 Odoo 开发，为模切企业提供从**材料选型 → 成本核算 → 采购管理 → 生产排料**的全流程 ERP 支撑。

### 1.2 核心功能模块

| 模块                   | 功能                                                | 入口菜单        |
| ---------------------- | --------------------------------------------------- | --------------- |
| **材料选型大全** | 材料系列管理、型号对比、技术参数查询、一键启用到ERP | 📚 材料选型大全 |
| **原材料管理**   | ERP 原材料库，含价格、规格、供应商、认证            | 原材料          |
| **成本计算器**   | 模切产品报价：材料+制造+管销+模具，自动核算单价     | 成本计算器      |
| **刀模管理**     | 刀模台账、寿命追踪、二维码、报废                    | 刀模管理        |
| **分切管理**     | 原材料分切记录                                      | 分切管理        |
| **领料申请**     | 生产领料演示                                        | 领料申请        |
| **样品订单**     | 样品订单管理                                        | 样品订单        |

### 1.3 依赖关系

```
diecut 模块
├── base            (基础框架)
├── product         (产品管理)
├── sale            (销售)
├── purchase        (采购)
├── stock           (仓库)
├── website         (网站)
├── website_sale    (网上商城)
├── mail            (消息/追踪)
└── web_hierarchy   (层级视图)
```

---

`<a id="2-模块架构"></a>`

## 2. 模块架构

### 2.1 文件结构

```
custom_addons/diecut/
├── __manifest__.py              # 模块声明
├── models/
│   ├── __init__.py
│   ├── diecut_brand.py          # 品牌主数据（独立模型）
│   ├── product_diecut.py        # ★ 核心：产品模板/变体/供应商扩展
│   ├── product_category.py      # 产品分类扩展（三级目录）
│   ├── diecut_quote.py          # 成本计算器
│   ├── requisition.py           # 领料申请
│   ├── mold.py                  # 刀模管理
│   ├── slitting.py              # 分切管理
│   ├── sample_order.py          # 样品订单
│   ├── purchase_order.py        # 采购单扩展
│   ├── res_partner.py           # 联系人扩展
│   ├── stock_quant.py           # 库存扩展
│   ├── stock_move.py            # 库存移动扩展
│   ├── catalog_item.py          # 新架构目录模型（系列/型号统一）
│   └── catalog_ops_log.py       # 目录运维日志
├── wizard/
│   ├── catalog_activate_wizard.py       # 选型目录启用向导
│   └── catalog_ops_wizard.py            # 数据运维向导
├── views/
│   ├── catalog_item_views.xml      # ★ 型号清单（新架构主入口）
│   ├── diecut_brand_views.xml      # 品牌主数据视图
│   ├── my_material_base_views.xml  # 原材料视图
│   ├── product_category_view.xml   # 分类视图
│   ├── diecut_quote_views.xml      # 报价视图
│   ├── diecut_menu_view.xml        # 菜单定义
│   └── ...其他视图
├── security/
│   └── ir.model.access.csv        # 权限控制
├── data/
│   ├── product_category_data.xml   # 预置分类
│   ├── catalog_item_spec_migration.xml # Catalog Item 旧参数字段迁移脚本
│   └── catalog_spec_def_data.xml   # 技术参数定义初始化数据
├── scripts/                        # ★ 数据生成器脚本
│   ├── catalog_items.csv           # [业务维护] 目录主表
│   ├── catalog_item_specs.csv      # [业务维护] 技术参数明细表
│   ├── generate_catalog.py         # CSV 主数据生成/对齐脚本
│   ├── legacy_field # 厚度标准值单位迁移（um→μm）
│   ├── recompute_legacy_field_std.py     # 厚度标准值全量重算脚本
│   └── catalog_*_template.csv      # 主表/参数明细模板
├── docs/
│   ├── DESIGN_MANUAL.md            # 本文档
│   └── PHASE4_*                    # Catalog Item 收敛期文档
└── static/
    └── src/
        ├── scss/                   # 样式
        │   └── material_split_preview.scss   # 型号清单分屏布局样式
        ├── js/
        │   ├── catalog_dynamic_columns.js    # ★ SearchPanel 联动列显隐
        │   └── material_split_preview.js     # ★ 型号清单分屏控制器/渲染器
        └── xml/                    # 前端模板
            └── material_split_preview.xml    # ★ 分屏模板 + 原生控制栏切换按钮
```

**目录主数据与代码生成**：当前主线以 `catalog_items.csv` 与 `catalog_item_specs.csv` 作为运维输入，配合 `generate_catalog.py`、运维向导和迁移脚本维护 `diecut.catalog.item` 及其技术参数明细。`series.csv` / `variants.csv` 已在 v1.7 清理，不再作为任何维护入口。

### 2.2 模型继承关系图

```
diecut.catalog.item
  ├── 主表：型号主信息 / ERP 启用状态 / 标准筛选字段
  └── one2many → diecut.catalog.item.spec.line
                 └── many2one → diecut.catalog.spec.def（按分类参数模板）

product.template (Odoo 原生 + diecut 扩展)
  └── 仅承载 ERP 原材料主线（is_raw_material）

product.supplierinfo (Odoo 原生)
  └── ProductSupplierinfo (product_diecut.py)
        └── 扩展：平米单价、公斤单价、面积/重量缓存

product.category (Odoo 原生)
  └── ProductCategoryExtend (product_category.py)
        └── 三级目录、动态属性定义

diecut.brand          → 品牌主数据
diecut.color          → 颜色主数据
diecut.quote          → 模切报价单
diecut.catalog.item   → 目录型号主模型（新架构）
diecut.catalog.ops.log → 目录运维日志
diecut.catalog.activate.wizard → 选型启用向导
```

### 2.3 目录新结构（Phase 4，单模型收口）

当前目录架构已从“多服务路由/双写”收口为“单模型主线”：

1. **主数据模型层**（`diecut.catalog.item`）
   - 作为目录域的主模型，统一承载型号清单。
   - 以 `brand_id + code` 作为核心业务标识，`series_id` 作为系列主入口，`series_name` 作为导入与展示口径。
2. **业务动作层**（Model + Wizard）
   - `catalog_item.py`：主业务规则、索引、启用状态关联。
   - `catalog_activate_wizard.py`：型号启用到 ERP 的确认与落库。
   - `catalog_ops_wizard.py`：目录运维动作统一入口。
3. **可观测层**（日志 + 菜单）
   - `catalog_ops_log.py`：记录运维动作与结果。
   - `catalog_item_views.xml` + `diecut_menu_view.xml`：统一运营入口与菜单组织。

> 设计原则：单一事实源、显式兼容字段、减少运行时分支和双写复杂度。

### 2.4 网站兼容链路现状

当前后台目录主线已经收口到 `diecut.catalog.item`，但网站页面仍有一条刻意保留的兼容链路：

- `/materials`、`/material/<id>` 当前展示的是 **ERP 原材料**（`product.template`, `is_raw_material=True`），不是 `diecut.catalog.item`。
- `/sample/order` 及其提交链路依赖 `sample.order.line.material_id -> product.product`，并直接使用 ERP 原材料价格参与试算。

当前网站模板实际依赖了以下 `product.template / product.product` 字段能力：

- 商品图片：`image_1920`
- 价格与计量：`list_price`、`uom_id`
- 原材料规格：`width`、`length`、`thickness`、`spec`
- 原材料属性：`color_id`、`weight_gram`、`track_batch`
- 网站展示文案：`description`、`application`、`process_note`

因此，现阶段 **不能直接把网站页的模型查询从 `product.template` 替换为 `diecut.catalog.item`**。如果要继续下线旧产品模型链路，需要先补齐下面两类能力：

1. `diecut.catalog.item` 侧新增或映射网站所需字段。
2. 样品申请链路改造为接受 `diecut.catalog.item`，并在提交时明确映射到 ERP 原材料或目录型号。

> 结论：后台旧架构已经基本退出主线；网站兼容链路仍然是一个独立迁移项目，不能与后台入口清理混为一步。

---

`<a id="3-数据模型详解"></a>`

## 3. 数据模型详解

### 3.1 ProductTemplate（产品模板扩展）

**模型**: `product.template` | **文件**: `models/product_diecut.py`

> 同一模型通过 `is_catalog` 和 `is_raw_material` 两个布尔标志位区分用途，二者互斥。

> 当前口径说明（2026-03-13）：
> - `product.template` 现在主要承担 **ERP 原材料主模型** 与 **网站兼容链路**。
> - 后台“材料选型大全”的主模型已经收口到 `diecut.catalog.item`。
> - `legacy_field`、`is_activated`、`activated_product_tmpl_id` 这一组旧后台启用链路字段已退出当前代码主线；本节后续若提到旧目录字段，应理解为历史兼容说明，而不是当前后台主设计。

#### 3.1.1 标志位字段

| 字段名              | 类型    | 说明              | 默认值 |
| ------------------- | ------- | ----------------- | ------ |
| `is_raw_material` | Boolean | 是否为 ERP 原材料 | False  |
| `is_catalog`      | Boolean | 是否为选型目录    | False  |

**约束**: `_check_catalog_raw_material_exclusive` — 两者不能同时为 True。

#### 3.1.2 选型目录专用字段

| 字段名                            | 类型                      | 说明           | 备注                              |
| --------------------------------- | ------------------------- | -------------- | --------------------------------- |
| `catalog_status`                | Selection                 | 目录状态       | draft/review/published/deprecated |
| `recommendation_level`          | Selection                 | 推荐等级       | a(强推)/b(备选)/c(谨慎淘汰)       |
| `series_name`                   | Char                      | 系列名称       | 如 "PET Double Sided Tape"        |
| `manufacturer_id`               | Many2one→res.partner     | 原厂           | 区别于供应商                      |
| `catalog_base_material`         | Char                      | 基材类型       | 如 PET、PU、PI、铜箔              |
| `catalog_adhesive_type`         | Char                      | 胶系           | 如 丙烯酸、合成橡胶               |
| `catalog_features`              | Text                      | 产品特点       | 发布时必填                        |
| `catalog_applications`          | Html                      | 典型应用       | 发布时必填，富文本                |
| `catalog_structure_image`       | Binary                    | 产品结构图     | —                                |
| `catalog_ref_price`             | Float                     | 参考单价       | 仅供选型参考                      |
| `catalog_ref_currency_id`       | Many2one→res.currency    | 参考价币种     | —                                |
| `tds_file` / `tds_filename`   | Binary/Char               | TDS技术数据表  | —                                |
| `msds_file` / `msds_filename` | Binary/Char               | MSDS安全数据表 | —                                |
| `legacy_field`     | Many2one→product.product | 历史兼容字段 | 已退出后台主线，不建议继续扩展     |
| `replacement_catalog_ids`       | Many2many→self           | 替代系列       | 停产时推荐替代                    |
| `replaced_by_catalog_ids`       | Many2many→self           | 被替代系列     | 反向只读                          |

`<a id="3-1-2-1-富文本格式使用详解"></a>`

##### 3.1.2.1 富文本格式使用详解

本系统中「产品特点」（`catalog_features`）与「典型应用」（`catalog_applications`）使用 Odoo 的 **Html 字段**，在表单中提供所见即所得（WYSIWYG）富文本编辑，可做出接近网页的排版效果。

**适用字段**

| 字段                     | 模型             | 说明                   |
| ------------------------ | ---------------- | ---------------------- |
| `catalog_features`     | product.template | 产品特点，系列表单编辑 |
| `catalog_applications` | product.template | 典型应用，系列表单编辑 |
| 同上（related）          | product.product  | 型号详情页只读展示     |

**编辑器可选项（工具栏功能）**

| 类别     | 可选项                     | 说明                                     |
| -------- | -------------------------- | ---------------------------------------- |
| 段落格式 | 正文、标题 1～6            | 下拉选择，用于层级标题与正文             |
| 字体样式 | 加粗、斜体、下划线、删除线 | 选中文字后点击应用                       |
| 列表     | 有序列表、无序列表         | 多行分条、编号/符号列表                  |
| 缩进     | 增加缩进、减少缩进         | 段落层级                                 |
| 对齐     | 左对齐、居中、右对齐       | 段落对齐方式                             |
| 链接     | 插入/编辑链接              | 可填 URL，在新标签页打开（视 Odoo 版本） |
| 颜色     | 文字颜色、背景色           | 高亮或强调（部分版本提供）               |
| 图片     | 插入图片                   | 需上传或粘贴，视 Odoo 配置与版本而定     |
| 表格     | 插入表格                   | 部分版本提供，可做简单规格表             |

**展示与存储**

- 编辑时：在表单中直接显示工具栏与可编辑区域，宽度为当前区块整行（已通过 `colspan="2"` 占满表单内容区）。
- 保存后：内容以 HTML 源码存库，前端按 HTML 渲染，支持标题、段落、列表、加粗、链接等，与普通网页一致。
- 型号详情页：通过 `related` 字段只读展示，不显示工具栏。

**使用建议（材料选型场景）**

- **产品特点**：用标题区分「结构」「胶系」「性能」等小节，用无序列表列关键参数或卖点，重要数值可加粗。
- **典型应用**：用有序/无序列表列应用场景（如 LCD 铭板、手机部件粘接），或简短段落描述典型工序与适用基材。
- 若需插入图片（如结构示意图），优先使用「产品结构图」Binary 字段；富文本内插图适合小图或图标，注意体积与加载速度。
- 已有纯文本数据迁移到 Html 后仍可正常显示（等价于一段无标签正文）；后续可在编辑器中再改为标题、列表等。

**可选能力说明**

- **图片、表格、颜色**：依赖当前 Odoo 版本与模块是否启用相应编辑器插件，若工具栏中无对应按钮，则当前环境未开放该能力。
- **自定义样式**：字段存的是标准 HTML，若需公司 VI 或固定版式，可在前端通过 CSS 覆盖（需另做视图或前端资源），一般不推荐在内容里写内联样式。

**性能说明**

- 在材料选型场景下（产品特点、典型应用为几段文字+列表），富文本对系统速度的影响可忽略：存储与传输仅多出少量 HTML 标签，表单加载与 Text 字段同级，列表页通常不渲染完整 Html。
- 需注意：单条内容过大（如内嵌大量 base64 图片或超长文档）或同时打开大量表单时，才可能产生可感知影响；建议大图使用「产品结构图」等 Binary 字段，富文本内少嵌大图。

#### 3.1.3 型号标准化索引字段（聚合展示用）

| 字段名                              | 计算依赖                                 | 说明                           |
| ----------------------------------- | ---------------------------------------- | ------------------------------ |
| `legacy_field`     | 所有变体的 `legacy_field`     | 系列下所有型号的标准厚度值合集 |
| `legacy_field`         | 所有变体的 `legacy_field`         | 系列下所有型号的标准颜色值合集 |
| `legacy_field`      | 所有变体的 `legacy_field`      | 系列下所有型号的标准胶系值合集 |
| `legacy_field` | 所有变体的 `legacy_field` | 系列下所有型号的标准基材值合集 |

> 这些字段由 `legacy_field` 聚合计算，存储于模板层，用于搜索面板和分组过滤。

#### 3.1.4 规格型号字段（ERP原材料用）

| 字段名           | 类型        | 说明     | 单位              |
| ---------------- | ----------- | -------- | ----------------- |
| `spec`         | Char        | 规格型号 | —                |
| `thickness`    | Float(16,3) | 厚度     | mm                |
| `width`        | Float(16,0) | 宽度     | mm                |
| `length`       | Float(16,3) | 长度     | M（后台统一存米） |
| `length_mm`    | Float(16,0) | 长度(mm) | 计算字段，片料用  |
| `length_smart` | Char        | 智能长度 | 自动识别 mm/m     |
| `rs_type`      | Selection   | 形态     | R=卷料 / S=片料   |

#### 3.1.5 物理特征字段

| 字段名                    | 类型                   | 说明         |
| ------------------------- | ---------------------- | ------------ |
| `color_id`              | Many2one→diecut.color | 颜色         |
| `weight_gram`           | Float                  | 克重(g)      |
| `material_type`         | Char                   | 材质/牌号    |
| `brand_id`              | Many2one→diecut.brand | 品牌         |
| `origin`                | Char                   | 产地         |
| `density`               | Float(10,3)            | 密度(g/cm³) |
| `material_transparency` | Selection              | 透明度       |

#### 3.1.6 性能参数字段

| 字段名                  | 类型        | 说明          |
| ----------------------- | ----------- | ------------- |
| `tensile_strength`    | Float(10,2) | 拉伸强度(MPa) |
| `tear_strength`       | Float(10,2) | 撕裂强度(N)   |
| `temp_resistance_min` | Float       | 耐温下限(℃)  |
| `temp_resistance_max` | Float       | 耐温上限(℃)  |
| `adhesion`            | Float(10,2) | 粘性(N/25mm)  |

#### 3.1.7 认证与合规

| 字段名              | 类型      | 说明           |
| ------------------- | --------- | -------------- |
| `is_rohs`         | Boolean   | ROHS认证       |
| `is_reach`        | Boolean   | REACH认证      |
| `is_halogen_free` | Boolean   | 无卤           |
| `fire_rating`     | Selection | 防火等级(UL94) |

#### 3.1.8 价格字段

| 字段名                       | 类型                   | 说明                           | 读写            |
| ---------------------------- | ---------------------- | ------------------------------ | --------------- |
| `raw_material_price_m2`    | Float(16,2)            | **单价/m²**             | compute+inverse |
| `raw_material_unit_price`  | Monetary               | **标准成本(按规格折算)** | compute+inverse |
| `raw_material_currency_id` | Many2one→res.currency | 成本币种                       | —              |

> **核心原则**: 底层统一按平方米计价。`raw_material_price_m2` 为基准价，`raw_material_unit_price = price_m2 × 面积`。

#### 3.1.9 采购与库存字段

| 字段名                                     | 类型                  | 说明            |
| ------------------------------------------ | --------------------- | --------------- |
| `main_vendor_id`                         | Many2one→res.partner | 主要供应商      |
| `min_order_qty`                          | Float                 | 最小起订量(MOQ) |
| `lead_time`                              | Integer               | 采购周期(天)    |
| `safety_stock`                           | Float                 | 安全库存        |
| `track_batch`                            | Boolean               | 批次管理        |
| `datasheet` / `datasheet_filename`     | Binary/Char           | 规格书          |
| `test_report` / `test_report_filename` | Binary/Char           | 测试报告        |
| `application`                            | Text                  | 应用场景        |
| `process_note`                           | Text                  | 加工工艺说明    |
| `caution`                                | Text                  | 注意事项        |

#### 3.1.10 动态属性

| 字段名                | 类型       | 说明         |
| --------------------- | ---------- | ------------ |
| `diecut_properties` | Properties | 物理特性参数 |

> 定义来源: `categ_id.diecut_properties_definition`。每个分类可自定义不同的物理特性参数集。

---

### 3.2 ProductProduct（产品变体扩展）

**模型**: `product.product` | **文件**: `models/product_diecut.py`

> 变体 = 选型目录中的一个具体型号（如 DST-3、DST-6 等）

#### 3.2.1 关联/冗余字段（用于列表筛选与型号详情页）

| 字段名                            | Related 来源                                                         | 说明                                                                                                                                                                                                                                                  |
| --------------------------------- | -------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `catalog_categ_id`              | `product_tmpl_id.categ_id`                                         | 分类                                                                                                                                                                                                                                                  |
| `catalog_brand_id`              | `product_tmpl_id.brand_id`                                         | 品牌                                                                                                                                                                                                                                                  |
| `catalog_status`                | `product_tmpl_id.catalog_status`                                   | 目录状态                                                                                                                                                                                                                                              |
| `recommendation_level`          | `product_tmpl_id.recommendation_level`                             | 推荐等级                                                                                                                                                                                                                                              |
| `catalog_density`               | `product_tmpl_id.density`                                          | 密度(g/cm³)，型号清单列表中动态显隐                                                                                                                                                                                                                  |
| `catalog_structure_image`       | `product_tmpl_id.catalog_structure_image`                          | 产品结构图，型号详情页展示                                                                                                                                                                                                                            |
| `catalog_features`              | `product_tmpl_id.catalog_features`                                 | 产品特点，型号详情页展示                                                                                                                                                                                                                              |
| `catalog_applications`          | `product_tmpl_id.catalog_applications`                             | 典型应用，型号详情页展示（富文本）                                                                                                                                                                                                                    |
| `legacy_field`     | 自有，`definition='catalog_categ_id.diecut_properties_definition'` | 变体物理特性：**定义**来自分类（不能为变体单独建定义），**值**每型号独立；需系列已设分类且分类已配置物理特性库方可编辑。变体上不做 related 的 diecut_properties，避免创建变体时 Properties 的 definition_record 解析为 None 导致 RPC 错误 |
| `tds_file` / `tds_filename`   | `product_tmpl_id.tds_file` / `tds_filename`                      | TDS 技术数据表，型号详情页附件                                                                                                                                                                                                                        |
| `msds_file` / `msds_filename` | `product_tmpl_id.msds_file` / `msds_filename`                    | MSDS 安全数据表，型号详情页附件                                                                                                                                                                                                                       |

#### 3.2.2 变体级技术参数（原文保留）

| 字段名                         | 类型        | 说明         | 示例值                       |
| ------------------------------ | ----------- | ------------ | ---------------------------- |
| `legacy_field`          | Char        | 厚度（原始） | "35±5 μm"                  |
| `legacy_field` | Char        | 胶厚         | "13/13"                      |
| `legacy_field`              | Char        | 颜色（原始） | "透明"、"黑色"               |
| `legacy_field`      | Char        | 剥离力       | ">800 gf/inch"               |
| `legacy_field`          | Char        | 结构描述     | "胶+PET+胶+白色LXZ"          |
| `legacy_field`      | Char        | 胶系(变体级) | 可覆盖模板级                 |
| `legacy_field`      | Char        | 基材(变体级) | 可覆盖模板级                 |
| `legacy_field`           | Char        | SUS面剥离力  | "13.0/13.0 N/cm"             |
| `legacy_field`            | Char        | PE面剥离力   | "7.0/7.0 N/cm"               |
| `legacy_field`             | Char        | DuPont冲击   | "0.7/0.1"、"1.3/1.0 [A×cM]" |
| `legacy_field`         | Char        | 推出力       | "229 N"                      |
| `legacy_field`       | Char        | 可移除性     | 星号等级（与同品类比较）     |
| `legacy_field`            | Char        | Tumbler滚球  | "40.0"                       |
| `legacy_field`      | Char        | 保持力       | "4.0 N/cm"                   |
| `legacy_field`               | Text        | 型号备注     | —                           |
| `legacy_field`          | Float(16,4) | 型号参考单价 | —                           |

> **设计决策**: 使用 Char 类型而非 Float，因为原厂数据含公差(±)、条件说明、双面参数等复杂格式。
>
> **图册符号约定**（录入/识别图册时）：**—**（横线）表示无/没有；**〇** 表示白色；**●** 表示黑色。

#### 3.2.3 标准化字段（筛选/归类用）

| 字段名                        | 说明       | 自动归一化规则        |
| ----------------------------- | ---------- | --------------------- |
| `legacy_field`     | 标准化厚度 | "35±5 μm" → "35μm" |
| `legacy_field`         | 标准化颜色 | 去多余空格            |
| `legacy_field`      | 标准化胶系 | 去多余空格            |
| `legacy_field` | 标准化基材 | 去多余空格            |

> 通过 `legacy_field` 和 `legacy_field` 方法自动从原文字段派生，`create()` / `write()` 时自动同步。历史值修正采用脚本迁移（见 `legacy_field` 与 `legacy_field`）。

#### 3.2.4 变体独立：认证与合规、替代建议、附件与资料

每个型号可拥有独立于系列的值，在型号详情与规格页维护。

| 字段名                                                 | 类型                        | 说明              |
| ------------------------------------------------------ | --------------------------- | ----------------- |
| `legacy_field`                                    | Boolean                     | 该型号 ROHS 认证  |
| `legacy_field`                                   | Boolean                     | 该型号 REACH 认证 |
| `legacy_field`                            | Boolean                     | 该型号 无卤       |
| `legacy_field`                                | Selection                   | 该型号 防火等级   |
| `legacy_field`                    | Many2many→product.template | 该型号 可替代系列 |
| `legacy_field` / `legacy_field`        | Binary/Char                 | 该型号 TDS        |
| `legacy_field` / `legacy_field`      | Binary/Char                 | 该型号 MSDS       |
| `legacy_field` / `legacy_field` | Binary/Char                 | 该型号 规格书     |
| `legacy_field`                    | Binary                      | 该型号 产品结构图 |

系列表单中「认证与合规」「替代建议」「附件与资料」为系列默认；各型号在型号详情页可填独立值。关系表：`product_product_catalog_replacement_rel`（`src_item_id`, `dst_tmpl_id`）。约束：可替代系列不能包含本型号所属系列。

#### 3.2.5 选型目录溯源字段

| 字段名                        | 类型                       | 说明            |
| ----------------------------- | -------------------------- | --------------- |
| `is_activated`              | Boolean                    | 历史兼容字段 |
| `activated_product_tmpl_id` | Many2one→product.template | 历史兼容字段 |

---

### 3.3 ProductSupplierinfo（供应商价格表扩展）

**模型**: `product.supplierinfo` | **文件**: `models/product_diecut.py`

| 字段名                | 类型          | 说明                                       |
| --------------------- | ------------- | ------------------------------------------ |
| `price`             | Float(原生)   | **等同于平米单价**（改版后语义统一） |
| `price_per_m2`      | Float(16,2)   | 单价/m²（与 price 保持同步）              |
| `price_per_kg`      | Float(16,2)   | 单价/kg（自动计算）                        |
| `is_main_vendor`    | Boolean(计算) | 是否为当前产品的主选供应商                 |
| `calc_area_cache`   | Float         | 实时面积缓存（解决 onchange 上下文隔离）   |
| `calc_weight_cache` | Float         | 实时重量缓存                               |

---

### 3.4 ProductCategoryExtend（产品分类扩展）

**模型**: `product.category` | **文件**: `models/product_category.py`

支持**三级目录结构**：

| 级别 | 示例     | 特有字段                                  |
| ---- | -------- | ----------------------------------------- |
| 一级 | 原材料   | `category_type`（raw/semi/finished）    |
| 二级 | 胶带类   | `material_code_prefix`（编码前缀如 JD） |
| 三级 | 双面胶带 | `specification`、`default_thickness`  |

通用字段：

| 字段名                           | 说明                                 |
| -------------------------------- | ------------------------------------ |
| `level`                        | 计算字段，1/2/3 级                   |
| `sequence`                     | 排序                                 |
| `indent_name`                  | 带缩进的分类名（列表展示用）         |
| `diecut_properties_definition` | 动态属性定义（PropertiesDefinition） |
| `image`                        | 分类图片                             |
| `material_count`               | 已发布材料数量                       |

**约束**: `name_parent_uniq` — 同一层级下不能有重名。

---

### 3.5 DiecutQuote（模切成本计算器）

**模型**: `diecut.quote` | **文件**: `models/diecut_quote.py`

> 完整的模切产品成本核算工具，分四大成本模块。

#### 成本构成

```
最终报价 = (材料成本 + 制造成本 + 管销成本 + 其他成本) × (1 + 利润率)
```

| 成本项             | 子模型                              | 计算方式                                        |
| ------------------ | ----------------------------------- | ----------------------------------------------- |
| **材料成本** | `diecut.quote.material.line`      | Σ(含税总价 ÷ 生产总数 × 损耗系数)            |
| **制造成本** | `diecut.quote.manufacturing.line` | Σ(人均费用 × 人数 ÷ 产能 ÷ 良率)            |
| **管销成本** | —                                  | (材料+制造) × 各费率(运输/管理/水电/包材/折旧) |
| **其他成本** | —                                  | 样品成本 + 模具费÷冲压总数                     |

#### 材料行关键字段

| 字段名                         | 说明                                                 |
| ------------------------------ | ---------------------------------------------------- |
| `material_id`                | 选择的原材料                                         |
| `raw_width` / `raw_length` | 原材规格                                             |
| `price_unit_tax_inc`         | 含税总价（自动从原材料带入）                         |
| `slitting_width`             | 分切宽度                                             |
| `slitting_rolls`             | 分切卷数 = raw_width ÷ slitting_width               |
| `pitch`                      | 跳距(mm)                                             |
| `cavity`                     | 穴数                                                 |
| `qty_per_roll`               | 每卷模切数量 = (长度 ÷ 跳距) × 穴数                |
| `total_prod_qty`             | 总生产数量 = 每卷数量 × 分切卷数                    |
| `unit_usage`                 | 单位用量(m²/pcs) = (分切宽 × 跳距) ÷ 穴数 ÷ 10⁶ |
| `unit_consumable_cost`       | 单位耗材成本 = (价格 ÷ 总数) × (1 + 损耗率)        |

---

### 3.6 CatalogActivateWizard（选型启用向导）

**模型**: `diecut.catalog.activate.wizard` | **文件**: `wizard/catalog_activate_wizard.py`

当前向导将 `diecut.catalog.item` 中的目录型号“一键启用”为 ERP 原材料产品：

1. 自动预填产品名称、型号、分类、品牌、材质、厚度
2. 用户补填宽度、长度、形态、供应商
3. 确认后创建新的 `product.template`（`is_raw_material=True`）
4. 将新产品回写到 `diecut.catalog.item.erp_product_tmpl_id`
5. 同步标记 `diecut.catalog.item.erp_enabled=True`

> 说明：当前后台向导不再支持旧 `product.product` / `catalog_tmpl_id` 分支，也不再维护 `legacy_field` 溯源字段。

---

### 3.7 辅助模型

| 模型                              | 文件              | 说明                          |
| --------------------------------- | ----------------- | ----------------------------- |
| `diecut.brand`                  | diecut_brand.py   | 品牌主数据（独立模型）        |
| `diecut.color`                  | product_diecut.py | 颜色主数据                    |
| `diecut.catalog.item`           | catalog_item.py   | 新架构型号主模型              |
| `diecut.catalog.ops.log`        | catalog_ops_log.py| 目录运维日志                  |
| `my.material.requisition`       | requisition.py    | 领料申请（参考价按 m² 单价） |
| `diecut.material.filter.wizard` | diecut_quote.py   | 报价单中的材料筛选向导        |
| `diecut.material.filter.line`   | diecut_quote.py   | 筛选结果行                    |

---

### 3.8 数据运维字段维护清单（`diecut.catalog.item`）

> 本清单用于数据运维（导入/导出/对账/补录）口径统一，字段来源为 `models/catalog_item.py`。
>
> 口径说明：已排除 Odoo 系统原生元字段（`id`, `create_uid`, `create_date`, `write_uid`, `write_date`, `__last_update`, `display_name`）。

#### 3.8.1 基础结构字段

`name`, `active`, `sequence`

#### 3.8.2 组织与目录字段

`brand_id`, `categ_id`, `code`, `series_id`, `catalog_status`

#### 3.8.3 兼容映射与启用链路字段

`erp_enabled`, `erp_product_tmpl_id`

#### 3.8.4 产品信息与应用字段

`product_features`, `product_description`, `main_applications`, `equivalent_type`

#### 3.8.5 型号基础属性字段（主表保留）

`legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`

> 说明：这些字段属于“型号基础属性”，仍由主表直接维护，并继续参与标准化、列表展示或 ERP 启用链路。

#### 3.8.6 标准化字段（系统计算/可人工修正）

`legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`

#### 3.8.7 合规、结构图与文档字段

`legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`, `tds_content`, `msds_content`, `datasheet_content`

#### 3.8.8 技术参数关联与统计字段

`spec_line_ids`, `spec_line_count`

> 说明：`diecut.catalog.item` 已不再作为“技术参数主存储表”平铺维护大量测试字段。  
> 技术参数明细统一外置到：
> - `diecut.catalog.spec.def`：参数模板/定义
> - `diecut.catalog.item.spec.line`：参数值明细
>
> 例如剥离力、持粘力、导热系数、击穿电压、表面电阻等，都应通过参数模板按分类定义，再在 `spec_line_ids` 中维护具体值。

#### 3.8.9 运维检查字段（计算）

`is_duplicate_key`

#### 3.8.10 当前主表中的历史迁移保留字段

以下字段当前仍存在于模型中，但仅用于历史迁移或兼容，不再作为正式主维护入口：

`legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`, `legacy_field`

> 这些字段的正式语义已经迁移到 `diecut.catalog.item.spec.line`，设计和运维都不应再围绕它们继续扩展。

#### 3.8.11 合计

以上清单反映的是 `diecut.catalog.item` 当前主表口径；若涉及技术参数的分类模板、值类型和参数值维护，请以 **3.9 材料技术参数管理方法** 为准。

### 3.9 材料技术参数管理方法（Catalog Item 新架构）

> 当前 `diecut.catalog.item` 的技术参数管理已经从“主表平铺很多技术字段”升级为“主表 + 参数定义 + 参数值”的三层结构。

#### 3.9.1 三层结构

| 层级 | 模型 | 作用 |
| --- | --- | --- |
| 主表 | `diecut.catalog.item` | 管理型号主信息、标准筛选字段、ERP 启用链路 |
| 参数定义表 | `diecut.catalog.spec.def` | 定义“某个材料分类可以有哪些技术参数” |
| 参数值表 | `diecut.catalog.item.spec.line` | 保存某个型号在某个参数上的实际值 |

**设计原则**：

- 主表只保留高频检索、ERP 启用、合规与附件等稳定字段。
- 不同材料分类的“长尾技术参数”不再继续往主表堆字段，而是下沉到参数定义表与参数值表。
- 同一参数名称、单位、值类型、排序在同一分类内由参数模板统一约束，避免业务录入时自由发挥。

#### 3.9.2 参数定义表（`diecut.catalog.spec.def`）

该模型用于定义“某类材料应该维护哪些技术参数”。核心字段如下：

| 字段 | 含义 |
| --- | --- |
| `name` | 参数显示名称 |
| `param_key` | 参数内部键，分类内唯一 |
| `categ_id` | 适用材料分类 |
| `value_type` | 值类型：`char` / `float` / `boolean` / `selection` |
| `unit` | 默认单位 |
| `selection_options` | 枚举型可选值 |
| `sequence` | 同分类内展示顺序 |
| `required` | 是否必填 |
| `active` | 是否启用 |
| `show_in_form` | 是否在表单展示 |
| `allow_import` | 是否允许通过导入写入 |

**约束**：

- `(categ_id, param_key)` 唯一。
- `param_key` 不允许为空，不允许带空白字符。

#### 3.9.3 参数值表（`diecut.catalog.item.spec.line`）

该模型用于保存“某个型号的某个技术参数值”。核心字段如下：

| 字段 | 含义 |
| --- | --- |
| `catalog_item_id` | 所属型号 |
| `spec_def_id` | 对应参数定义 |
| `categ_id` | 关联出所属分类（related/store） |
| `sequence` | 展示顺序 |
| `param_key` / `param_name` | 从参数定义同步下来的冗余键与名称 |
| `value_char` / `value_float` / `value_boolean` / `value_selection` | 按值类型落到对应字段 |
| `value_text` | 统一编辑值（计算 + 反写，列表主展示列“值”） |
| `display_value` | 前端展示值（用于“值+单位”拼接场景） |
| `unit` | 实际单位 |
| `test_method` | 测试方法 |
| `test_condition` | 测试条件 |
| `remark` | 备注 |

**约束**：

- `(catalog_item_id, spec_def_id)` 唯一。
- `spec_def_id.categ_id` 必须与 `catalog_item_id.categ_id` 一致。
- 只允许填写与 `value_type` 匹配的那个值字段。
- 若参数定义 `required=True`，则该参数行必须有值。
- 枚举值必须落在 `selection_options` 定义范围内。

**界面交互（2026-03 收敛）**：

- 主 form 与 split form 的技术参数列表统一只显示单列 `value_text`（标题：`值`）。
- `value_text` 按参数类型自动映射：文本显示文本、数值显示数字字符串。
- `value_text` 在列表中使用 `diecut_spec_value_widget`：
  - `value_type=selection` 时渲染下拉菜单（选项来源 `spec_def_id.selection_options`）。
  - 其他类型保持文本输入框。
- `unit` 保持独立列展示，不在“值”列拼接单位。
- one2many 行内 form 仍保留分类型字段编辑（`value_char/value_float/value_boolean/value_selection`）。

#### 3.9.4 按分类定义技术参数的方法

每种材料分类通过 `diecut.catalog.spec.def` 维护一组“参数模板”，同一分类的所有型号共用这一组模板。

**运行机制**：

1. 新建 `diecut.catalog.item` 并选择 `categ_id` 后，系统会按该分类下 `active=True` 且 `show_in_form=True` 的参数定义自动补齐 `spec_line_ids`。
2. 若已有型号已存在参数值，不允许直接切换到另一分类，避免把 A 类模板参数错误带到 B 类材料。
3. 用户在型号表单里只需要填写参数值，不需要重复发明参数名称。

**管理入口**：

- 参数模板维护：`diecut.catalog.spec.def`
- 型号参数维护：`diecut.catalog.item.spec.line`（在型号表单 `spec_line_ids` 中编辑）

#### 3.9.5 当前已预置的分类参数模板

当前系统已经按分类预置了一批参数定义。每类材料的参数集合可以完全不同。

**EVA / 泡棉类**（`diecut.category_foam`）

- `density`：密度
- `hardness`：硬度
- `compression_set`：压缩永久变形
- `rebound_rate`：回弹率
- `temperature_range`：耐温范围
- `adhesive_backing`：背胶类型

**导电铜箔 / 金属箔类**（`diecut.category_metal_foil`）

- `surface_resistance`：表面电阻
- `shielding_effectiveness`：屏蔽效能
- `conductive_direction`：导电方向
- `foil_peel_strength`：铜箔剥离力
- `temperature_resistance`：耐温
- `conductive_adhesive_type`：导电胶类型

**PET 单面胶带**（`diecut.category_tape_pet_single`）

- `total_thickness`：总厚度
- `substrate_thickness`：基材厚度
- `adhesive_system`：胶系
- `peel_strength_180`：剥离力
- `temperature_grade`：耐温等级

**PET 双面胶带**（`diecut.category_tape_pet_double`）

- `total_thickness`：总厚度
- `carrier_thickness`：载体厚度
- `adhesive_system`：胶系
- `initial_tack`：初粘力
- `holding_power`：持粘力

**电气绝缘胶带**（`diecut.category_tape_insulation`）

- `base_material_type`：基材类型
- `breakdown_voltage`：击穿电压
- `dielectric_strength`：介电强度
- `temperature_class`：耐温等级
- `flame_class`：阻燃等级

**导热石墨 / 导热类材料**（`diecut.category_graphite`）

- `thermal_conductivity_xy`：面内导热系数
- `thermal_conductivity_z`：厚向导热系数
- `total_thickness`：总厚度
- `surface_resistance`：表面电阻
- `shielding_effectiveness`：屏蔽效能

**离型膜**（`diecut.category_release_film`）

- `base_film_type`：基膜类型
- `total_thickness`：总厚度
- `release_force`：离型力
- `surface_treatment`：表面处理
- `color_tone`：颜色/外观

**保护膜**（`diecut.category_protection_film`）

- `base_material_type`：基材类型
- `total_thickness`：总厚度
- `adhesion_force`：粘着力
- `temperature_grade`：耐温等级
- `application_surface`：适用表面

**导电布**（`diecut.category_conductive_cloth`）

- `cloth_base_type`：布基类型
- `total_thickness`：总厚度
- `surface_resistance`：表面电阻
- `shielding_effectiveness`：屏蔽效能
- `adhesive_backing`：背胶类型

**绝缘纸类**（`diecut.category_insulation_paper`）

- `paper_base_type`：纸基类型
- `total_thickness`：总厚度
- `breakdown_voltage`：击穿电压
- `temperature_class`：耐温等级
- `density`：密度

#### 3.9.6 维护与导入原则

**参数模板（定义层）**

- 由管理员维护，不建议业务同事在导入明细时随意创造新的 `param_key`。
- 新增一个全新材料分类时，优先先建好该分类的参数模板，再开始导入型号明细。

**参数值（数据层）**

- 业务数据可通过型号表单中的 `spec_line_ids` 维护。
- 批量维护时推荐使用“主表 CSV + 参数明细 CSV”双文件直导：
  - 主表 CSV：型号主信息
  - 参数明细 CSV：一行一条参数值
- 导入参数明细时，按 `item_code + categ_code + param_key` 匹配主表记录与参数定义。

**迁移原则**

- 历史上平铺在 `diecut.catalog.item` 主表上的技术字段，已按 `param_key` 映射迁移到 `spec_line_ids`。
- 后续新增大多数“测试型参数”时，原则上不再修改主表 schema，而是通过新增 `diecut.catalog.spec.def` 解决。

---

`<a id="4-核心业务规则"></a>`

## 4. 核心业务规则

### 4.1 价格体系 —— 统一按平方米计价

**核心原则**: 系统内所有价格底层统一为**每平方米单价（RMB/m²）**。

```
面积 (m²) = 宽度(mm) ÷ 1000 × 长度(m)
重量 (kg) = 面积 × 克重(g) ÷ 1000  （或 面积 × 密度 × 厚度 × 1000 ÷ 1000）

价格换算关系：
  seller.price = seller.price_per_m2 = 平米单价
  raw_material_unit_price = price_m2 × 面积   （整卷/片价格）
  price_per_kg = price_m2 × 面积 ÷ 重量       （公斤价格）
```

#### 价格联动链路

```
用户修改 price_per_m2
  → seller.price = price_per_m2
  → raw_material_unit_price = price_per_m2 × area
  → price_per_kg = price_per_m2 × area ÷ weight

用户修改 raw_material_unit_price
  → price_per_m2 = raw_material_unit_price ÷ area
  → seller.price = price_per_m2
  → price_per_kg = raw_material_unit_price ÷ weight

用户修改规格（宽度/长度等）
  → 保持 price_per_m2 不变
  → 重新计算 raw_material_unit_price = price_per_m2 × 新面积
  → 重新计算 price_per_kg
```

### 4.2 面积和重量计算 — `_get_diecut_factors()`

```python
宽度_m = width(mm) / 1000
长度_m = length  # 后台存储统一为米
        # 片料且值>10时，视为毫米值，自动除1000

面积 = 宽度_m × 长度_m

重量 = 面积 × 克重(g) / 1000          # 有克重时
     = 面积 × 密度 × 厚度 × 1000 / 1000  # 无克重但有密度时
```

### 4.3 长度智能解析 — `length_smart`

`length_smart` 字段根据 `rs_type` 自动判断单位：

- **卷料(R)**: 显示 "50 m"，存储 50.0
- **片料(S)**: 显示 "300 mm"，存储 0.3

反向解析时自动识别 mm/m 后缀并转换为内部统一的米存储。

### 4.4 选型目录 → ERP 原材料启用

```
选型目录变体 (product.product, is_catalog=True)
    │
    │  点击"启用到ERP"
    │
    ▼
启用向导 (diecut.catalog.activate.wizard)
    │  自动预填：名称、型号、分类、品牌、材质、厚度
    │  用户补填：宽度、长度、形态、供应商
    │
    │  确认启用
    │
    ▼
新 ERP 原材料 (product.template, is_raw_material=True)
    │  `diecut.catalog.item.erp_product_tmpl_id` → 新 ERP 产品
    │
    ▼
目录条目标记: erp_enabled=True, erp_product_tmpl_id=新产品ID
```

**幂等保护**:

1. `FOR UPDATE` 行锁防并发
2. 启用前检查当前目录条目是否已存在 `erp_product_tmpl_id`
3. 目录主表业务唯一键 `brand_id + code`

### 4.5 技术参数自动归一化 (Normalization)

为了平衡“原厂数据完整性”与“系统检索效率”，系统采用了“原文”+“标准化快照”的双字段设计。当型号原文字段（如 `型号原始厚度`）被写入时，系统会自动通过“标准化派生逻辑”生成对应的标准化字段。

#### 4.5.1 字段职责分工

| 类别                 | 字段属性                 | 核心职责                                                                     | 业务场景                                                        |
| :------------------- | :----------------------- | :--------------------------------------------------------------------------- | :-------------------------------------------------------------- |
| **原文描述**   | `型号原始颜色` 等     | **保留原样**。包含原产地语言、公差、测试条件、双面差异等所有技术细节。 | 型号详情页、规格对比表、正式技术文档导出。                      |
| **标准化快照** | `型号颜色标准值` 等 | **归一化处理**。去除空格、特殊符号、修正同义词、统一单位。             | **SearchPanel (搜索面板) 统计**、分组过滤、看板卡片展示。 |

#### 4.5.2 归一化核心价值

1. **解决检索歧义**：将不同厂商对相同特征的不同描述（如 "Black", "黑色", "BK"）在后台逻辑中尝试对齐，确保搜索“黑色”时能一次性搜出所有相关型号。
2. **支撑侧边搜索面板 (SearchPanel)**：Odoo 19 的搜索面板需要对数据进行分组统计。直接使用含有空格和特殊符号的原文会导致选项极其零碎且存在大量同义词。使用归一化字段能显著提升侧边栏的整洁度和选择效率。
3. **驱动系列级自动填充**：系列级字段（如 `legacy_field`）会自动聚合下属所有变体的 `_std` 字段进行去重排序。使用归一化字段作为源，可以确保系列级的汇总结果（如 "黑色, 透明"）不仅美观且准确。

#### 4.5.3 归一化处理规则

- **厚度归一化** (`_normalize_thickness_std`):
  - 规则：提取核心数值，并统一单位至 `μm`。
  - 示例："35±5 μm" → "35μm"；"0.1mm" → "100μm"；"100" (无单位且 >10) → "100μm"；"0.05" (无单位且 ≤10) → "50μm"。
- **文本归一化** (`_normalize_text_std`):
  - 适用字段：颜色 (`legacy_field`)、胶系 (`legacy_field`)、基材 (`legacy_field`)。
  - 规则：去除首尾空格、将内部连续空格压缩为一个、移除换行符。
  - 示例：" 黑色 (哑光) " → "黑色 (哑光)"。

#### 4.5.4 维护策略

- **自动化优先**：业务人员在界面操作或通过 CSV/JSON 导入时，**只需维护原文字段**。
- **透明同步**：系统在 `create` 和 `write` 钩子中会自动补全 `_std` 字段。
- **人工干预**：如果系统自动识别的标准化结果不符合特定分类需求，用户可以在界面或 CSV 中手动修改 `_std` 字段，系统将优先以手动录入的值为准，不再覆盖。

### 4.8 主子表数据同步机制 (Main-Sub Table Sync)

在 Odoo 19 中，系列（`product.template`）与型号（`product.product`）之间的数据流转由 ORM 核心属性严格控制，遵循“职责分离、局部同步”原则。

#### 4.8.1 三大同步逻辑

| 逻辑类型           | 方向     | 实现机制                       | 业务场景                                                                                                   |
| :----------------- | :------- | :----------------------------- | :--------------------------------------------------------------------------------------------------------- |
| **向上汇总** | 子 → 主 | `compute` + `@api.depends` | **型号颜色/厚度汇总** (`legacy_field`)。子表型号变动，主表索引自动刷新。                |
| **向下继承** | 主 → 子 | `related`                    | **共有属性**（品牌、厂家、分类）。主表修改，所有子表实时且只读地同步。                               |
| **独立存储** | N/A      | 默认 (无特殊属性)              | **差异化参数**。主表的 `thickness` (数字索引) 与子表的 `legacy_field` (原厂文字) 互不干扰。 |

#### 4.8.2 核心控制参数

- **`compute`**: 用于主表统计子表数据。
- **`related`**: 用于子表镜像主表数据，确保“系列级属性”的一致性。
- **`inverse`**: 允许通过修改计算字段来反向改写数据源（本模块慎用）。
- **`onchange`**: 仅用于 UI 编辑时的实时预览反馈。

#### 4.8.3 导入时的自动补齐

当通过 CSV/JSON 导入型号数据时，系统具备“自动填空”能力：

- 若 JSON 中缺失归一化字段（如 `legacy_field`），系统在 `write` 时会检测到原文变更，从而自动触发归一化计算进行补齐。
- 修补记录（2026-03）：修复了装载钩子中的“主动清空”逻辑，防止其干扰归一化字段的自动补全。

### 4.6 发布校验 — `_validate_catalog_publish()`

发布选型目录时必须满足：

- [X] 品牌不为空
- [X] 材料分类不为空
- [X] 系列名称不为空
- [X] 基材类型不为空
- [X] 胶系不为空
- [X] 产品特点不为空
- [X] 典型应用不为空
- [X] 至少上传一份技术文档（TDS/MSDS/规格书）
- [X] 至少有一个变体
- [X] 所有变体必须有型号编码

### 4.7 产品删除清理

当 ERP 原材料（`product.template`）被删除时，`unlink()` 会自动执行两类清理：

1. 重置目录条目：`diecut.catalog.item.erp_enabled=False`、`erp_product_tmpl_id=False`。
2. ERP 原材料自身按正常删除链路处理，不再回写旧变体启用状态。

---

`<a id="5-状态机与工作流"></a>`

## 5. 状态机与工作流

### 5.1 选型目录状态

```
  ┌──────────────────────────────────────────────┐
  │                                              │
  ▼                                              │
[草稿] ──提交评审──▶ [评审中] ──发布──▶ [已发布]    │
  ▲                    │                  │       │
  │                    │                  │       │
  └────退回草稿────────┘                  │       │
  └─────────────退回草稿──────────────────┘       │
                                                  │
  任意状态 ──标记停产──▶ [已停产] ─退回草稿─────────┘
```

| 操作     | 方法                           | 触发条件     |
| -------- | ------------------------------ | ------------ |
| 提交评审 | `action_submit_review()`     | 当前为草稿   |
| 发布     | `action_publish_catalog()`   | 通过发布校验 |
| 退回草稿 | `action_set_catalog_draft()` | 当前非草稿   |
| 标记停产 | `action_deprecate_catalog()` | 当前非停产   |

---

`<a id="6-视图与菜单结构"></a>`

## 6. 视图与菜单结构

### 6.1 菜单结构

```
模切管理系统 (menu_diecut_root)
├── 成本计算器              → action_diecut_quote
├── 📚 材料选型大全         → action_diecut_catalog_item_gray (diecut.catalog.item)
│   ├── 📋 材料型号清单      → action_diecut_catalog_item_gray (diecut.catalog.item)
│   ├── 品牌库               → action_diecut_brand
│   ├── 数据运维             → action_catalog_ops_wizard
│   └── 运维日志             → action_catalog_ops_log
├── 原材料                  → action_diecut_raw_material (product.template, is_raw_material=True)
├── 客户管理                → action_diecut_customer
├── 刀模管理                → action_diecut_mold
├── 分切管理                → action_material_slitting
├── 领料申请                → action_requisition_demo
└── 样品订单                → action_sample_order_custom
```

> 说明：自 `v1.7` 起，后台旧架构入口 `legacy_field` / `legacy_field` / `action_material_catalog` 已从默认菜单与模块加载清单中移除；后台目录主线统一收口到 `diecut.catalog.item`。

### 6.2 选型目录视图清单

| View ID                                 | 类型   | 模型               | 用途                                 |
| --------------------------------------- | ------ | ------------------ | ------------------------------------ |
| `view_material_catalog_form`          | Form   | product.template   | 历史后台视图（已退出主菜单）          |
| `view_material_catalog_tree`          | List   | product.template   | 系列级快速浏览                       |
| `view_material_catalog_search`        | Search | product.template   | 搜索/筛选/分组                       |
| `view_diecut_catalog_item_tree`       | List   | diecut.catalog.item | 型号清单（新架构主列表）             |
| `view_diecut_catalog_item_split_tree` | List   | diecut.catalog.item | 型号清单（分屏入口，js_class 挂载）  |
| `view_diecut_catalog_item_form`       | Form   | diecut.catalog.item | 型号详情与技术参数                   |
| `view_diecut_catalog_item_split_form` | Form   | diecut.catalog.item | 分屏右侧型号表单（去按钮箱干扰）     |
| `view_diecut_catalog_item_search`     | Search | diecut.catalog.item | 型号搜索 + SearchPanel               |
| `view_diecut_brand_list`              | List   | diecut.brand       | 品牌主数据维护                       |
| `view_diecut_brand_form`              | Form   | diecut.brand       | 品牌详情维护                         |

### 6.3 Action 配置

| Action ID                                | 模型               | Domain                                                           | 说明                                 |
| ---------------------------------------- | ------------------ | ---------------------------------------------------------------- | ------------------------------------ |
| `action_material_catalog`              | product.template   | `is_catalog=True`                                              | 历史后台动作（已退出主菜单）         |
| `action_diecut_catalog_item_gray`      | diecut.catalog.item | —                                                                | 型号清单主入口（新架构）             |
| `action_diecut_brand`                  | diecut.brand       | —                                                                | 品牌主数据入口                       |
| `action_diecut_raw_material`           | product.template   | `is_raw_material=True`                                         | ERP 原材料                           |
| `stock.product_template_action_product`| product.template   | `is_catalog=False`                                             | 库存模块产品模板列表（排除选型目录） |
| `stock.stock_product_normal_action`    | product.product    | `product_tmpl_id.is_catalog=False`                             | 库存模块产品变体列表（排除选型目录） |
| `stock.action_product_stock_view`      | product.product    | `detailed_type='product' and product_tmpl_id.is_catalog=False` | 库存在手产品视图（排除选型目录）     |

### 6.4 采购模块隔离策略（已落地）

**目标**: 选型目录材料（`is_catalog=True`）仅用于材料选型，不应在采购模块产品选择/产品列表中出现。
**当前状态**: 已落地，采购模块入口与采购单选料链路已做隔离。

**实现要点**（与库存隔离同一思路）:

- 采购相关产品入口统一增加过滤：排除 `is_catalog=True`
- 采购单行 `product_id` 选择器补充 domain，避免选到选型目录型号
- 保留原材料采购链路（`is_raw_material=True`）不受影响
- 回归结果：采购询价单/采购订单中新建行时，不再检索到 `is_catalog=True` 产品

### 6.5 搜索面板配置

**选型目录搜索面板**:

- 材质分类（`categ_id`，层级单选，展开）
- 品牌（`brand_id`，多选）

**型号清单搜索面板（新架构）**:

- 材料分类（`categ_id`，层级单选）
- 品牌（`brand_id`，多选）

> 说明：`catalog_dynamic_columns.js` 属于旧架构时期的列表增强脚本；当前后台主入口 `diecut.catalog.item` 默认采用稳定列集展示，不再依赖旧 `product.product` 型号清单。

#### 6.5.1 不同分类列表显示不同字段 — 规则与配置（历史兼容说明）

**设计目的**：该机制最初用于旧架构 `product.product` 型号清单，在按分类切换时收缩空列干扰；当前保留为历史兼容说明，不再作为后台主线设计。

**显隐规则（二者叠加）**：

| 规则                       | 说明                                                                                           | 适用范围                                                               |
| -------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **按分类显示指定列** | 某列仅在选中的分类路径命中配置的“关键词”时允许显示；否则强制隐藏。                           | 当前仅配置了密度列 `catalog_density`：泡棉、屏蔽材料、金属箔、石墨。 |
| **全空列自动隐藏**   | 对当前拉取到的所有记录逐列判断：若该列在所有当前页的记录中均无有效值，则彻底从渲染队列里剔除。 | 仅材料型号清单；原材料等其它列表不生效。                               |

**配置与实现机制（Owl Patch）**：

- **实现文件**：`static/src/js/catalog_dynamic_columns.js`（历史兼容脚本，当前后台主入口默认不依赖）。
- **Odoo 19 正规做法**：脚本不再注入 CSS 或者粗暴操作 DOM。相反，它使用了 `@web/core/utils/patch` 对 `@web/views/list/list_renderer` 的 `getActiveColumns()` 方法进行了补丁（Patch）。
- **拦截逻辑**：在 Owl 系统准备把字段列传递给虚拟 DOM（VDOM）渲染之前，拦截并检查当前视图是否为“材料型号清单”（依据是否同时拥有 `product_tmpl_id` 和 `catalog_categ_id`）。如果是，则通过遍历 `this.props.list.records` 并判定每列数据。
- **全空列隐藏**：如果判定某列在所有 `records` 中的 `val` 全都是空的（如 `false`, `null`, `""`, `0` 或者像 `—`、`...`），那么这列就会从返回的 `columns` 数组里被移除，渲染引擎根本就不会为该列生成 `<th>` 或 `<td>`。
- **优势**：这种方法与 Odoo 底层框架**完全兼容**。它不会引起 DOM 冲突报错，性能消耗极低，并且跟那些依赖点击、轮询、重写样式的“黑魔法”比起来更稳定，页面跳转与操作也不会再受到定时刷新的影响。

#### 6.5.2 SearchPanel 默认规则：该分类没有数据则默认不显示

**结论**：逻辑一致。Odoo SearchPanel 的默认行为就是：**若某分类（或某选项）在当前 domain 下没有任何记录，则不会作为可选值出现在面板中**。

### 6.6 型号详情与规格页（Catalog Item Form）

**目的**：以 `diecut.catalog.item` 作为型号清单的主展示与编辑对象，在同一入口完成技术参数、标准化字段、认证与附件维护。

**实现方式**：

- **视图**：`view_diecut_catalog_item_form`（`diecut.catalog.item`），由 `action_diecut_catalog_item_gray` 绑定。
- **布局**：分为「基础信息」「技术参数」「文档与附件」三个区块，支持在一个表单内维护型号级参数与标准化字段。
- **数据来源**：`diecut.catalog.item` 自身字段为主，旧模型仅作为历史兼容入口存在。
- **入口**：
  - 主入口：材料选型大全 → 材料型号清单（`action_diecut_catalog_item_gray`）。
  - 分屏：`view_diecut_catalog_item_split_tree` + `view_diecut_catalog_item_split_form`。
  - 列表/表单均保留「启用到ERP」「已启用ERP」动作按钮。

**动态属性说明**：

- 新架构 `diecut.catalog.item` 当前聚焦于标准参数、状态和 ERP 启用链路，未直接承载 `fields.Properties`。
- `fields.Properties` 仍由兼容模型 `legacy_field` 承载（定义来源于 `product.category.diecut_properties_definition`），用于旧入口与兼容编辑场景。
- 若后续需要把动态属性完全迁入新架构，可在 `diecut.catalog.item` 增加对应字段并制定一次性迁移策略。

**说明**：

- SearchPanel 的选项由服务端 `search_panel_select_range` / `search_panel_select_multi_range` 根据**当前模型的 domain** 统计得出；返回的是“在结果集中出现过的”字段值及其条数（`enable_counters="1"` 时显示数字）。
- 因此，若某分类下没有任何产品记录，该分类不会出现在“材料分类”的选项列表里；有数据的分类才会带条数显示。层级结构下，父节点可能仍会展示（用于展开），但**没有数据的叶子或分支不会作为可选项返回**，效果上即“该分类没有数据则默认不显示该分类”。
- 若个别版本或配置下出现“条数为 0 仍显示”的情况，可在对应模型的 `search_panel_select_range` / `search_panel_select_multi_range` 返回值中显式过滤掉 `__count` 或 `count` 为 0 的项。本项目当前依赖 Odoo 默认行为，未做该过滤。

**原材料搜索面板**:

- 材质分类（`raw_material_categ_id`，层级单选，展开）
- 功能类别（`product_tag_ids`，多选）
- 供应商（`main_vendor_id`，多选）
- 品牌（`brand_id`，多选）
- 颜色（`color_id`，多选）

`<a id="6-7-表单视图高级-ui-布局-bootstrap-5-栅格"></a>`

### 6.7 表单视图高级 UI 布局 (Bootstrap 5 栅格)

**设计目标**：为了解决 Odoo 原生 `<group>` 排版单调、当字段超过 10 个以上时显得拥挤和混乱的问题，系统全面引入 Odoo 19 原生支持的 **Bootstrap 5 UI 卡片与栅格化布局**。

**实现机制与优势**：
相较于开发繁重且易与 Owl VDOM 声明周期冲突的“前端拖拽改变字段顺序”方案，采用底层 XML 控制的 Bootstrap 5 布局能带来如下优势：

1. **精确到列宽与响应式支持**：利用 `class="col-12 col-md-4"` 轻松适配长宽屏，不会导致 UI 错位；
2. **极佳的视觉体验（高颜值）**：结合 `card`, `shadow-sm`, `border-start`，实现企业级 Dashboard 面板效果；
3. **彻底的安全与性能**：这依然是原汁原味的 Odoo XML 视图渲染，零 JS 注入，且不会导致模型解析负担。

#### 6.7.1 布局范例与实施参考

以当前 `diecut.catalog.item` 的完整表单为例，结构如下：

```xml
<sheet>
    ...
    <!-- 核心信息美化排版 (Bootstrap 5 栅格与卡片方案) -->
    <div class="row mt-4 mb-4 g-3">
    
        <!-- 左侧：基本信息 占4/12 -->
        <div class="col-12 col-md-4">
            <div class="card h-100 border-0 shadow-sm">
                <div class="card-body">
                    <h4 class="card-title text-primary"><i class="fa fa-tags me-2"/>基本信息</h4>
                    <group>
                        <field name="brand_id" />
                        <field name="series_name" />
                    </group>
                </div>
            </div>
        </div>
    
        <!-- 中间：产品特点 -->
        <div class="col-12 col-md-4">
            <div class="card h-100 border-0 shadow-sm">
                ...
            </div>
        </div>

        <!-- 右侧：典型应用 -->
        <div class="col-12 col-md-4">
            <div class="card h-100 border-0 shadow-sm">
                ... 
            </div>
        </div>
    </div>
</sheet>
```

#### 6.7.2 后续开发扩展指南

对新的表单如果需要精排版，推荐遵循以下规则：

- 最外层使用 `<div class="row g-x">` 包裹列；
- 使用 `<div class="card border-0 shadow-sm">` 构建卡片面板；
- 根据业务重要程度设定主色调分类 (`text-primary`, `text-success`, `text-info` 等) 和前缀 icon。

`<a id="6-8-型号清单分屏工作台"></a>`

### 6.8 型号清单分屏工作台

**目标**：在一个页面中实现“左侧型号列表 + 右侧可编辑表单”，减少列表/表单来回切换（当前主用于 `diecut.catalog.item`）。

**实现组成**：

- **自定义视图类型**：`js_class="diecut_split_list"`（挂载于 `view_diecut_catalog_item_split_tree`）。
- **控制器**：`DiecutSplitListController`（`static/src/js/material_split_preview.js`）负责模式状态与本地记忆。
- **渲染器**：`DiecutSplitListRenderer` 负责左右/上下布局、拖拽分隔条、右侧内嵌 `View(type='form')`。
- **模板**：`static/src/xml/material_split_preview.xml`。
- **样式**：`static/src/scss/material_split_preview.scss`。

**三种布局模式（ControlPanel 原生位置切换）**：

- 左右分屏（`vertical`）
- 上下分屏（`horizontal`）
- 仅列表（`list`）

按钮放置在 Odoo 原生控制栏右侧导航区域，采用 `o_cp_switch_buttons` / `o_switch_view` 风格与 OI 图标，保持与系统视图切换一致。

**状态记忆**：

- 存储位置：`localStorage`
- Key：`diecut_split_layout:action_diecut_catalog_item_gray`（由 action context 显式指定）
- 存储内容：`layoutMode`、`splitRatio`

**性能策略**：

- 拖拽分隔条使用 `requestAnimationFrame` 节流；拖动中优先更新 CSS 变量，`mouseup` 再提交最终比例。
- 拖动中临时禁用右侧表单的 pointer events，降低重渲染带来的卡顿感。

**编辑能力与权限说明**：

- 右侧内嵌 Form 视图使用 `view_diecut_catalog_item_split_form`（去按钮箱干扰，聚焦编辑）。
- 为满足业务编辑需求，内部用户组具备 `diecut.catalog.item` 读/写/创建权限（普通用户不删除）；兼容路径保留 `product.product` 读/写/创建权限（不含删除）。

#### 6.8.1 2026-03-13 界面收敛更新（Catalog Item / Split）

**本次目标**：统一 `diecut.catalog.item` 的产品信息表达、补足完整表单附件区、并优化分屏右侧的主操作入口位置。

**产品信息字段收敛**

- `diecut.catalog.item` 正式保留 4 个产品说明字段：
  - `product_features`：产品特点，`Text`
  - `product_description`：产品描述，`Text`
  - `main_applications`：主要应用，`Html`
  - `equivalent_type`：相当品（替代类型），`Text`
- 旧字段 `feature_desc`、`special_applications`、`typical_applications` 已退出正式界面与导入导出链路。
- 主 form 与 split 右侧 form 使用同一套字段语义，不再保留两套“产品信息/应用与特性”并行结构。

**产品信息区顺序**

- 主 form 与 split form 的“产品信息与应用”区块统一按以下顺序展示：
  1. `product_features`
  2. `product_description`
  3. `main_applications`
  4. `equivalent_type`
- 这样把“相当品（替代类型）”放在“主要应用”之后，阅读顺序更贴近业务录入习惯。

**完整表单附件区**

- `diecut.catalog.item` 继承 `mail.thread` 与 `mail.activity.mixin`。
- 完整 form 在 `</sheet>` 后接入标准 `<chatter />`，用于显示：
  - 发送消息
  - 备注
  - 活动
  - 附加文件
- split 右侧预览/编辑表单不显示 `chatter`，避免分屏区域变重。
- 原“文档与附件”业务区继续保留，仍负责：
  - 结构图
  - `tds_content`
  - `msds_content`
  - `datasheet_content`
- 设计上形成“两层职责”：
  - 业务资料正文：表单中部“文档与附件”区
  - 任意上传附件：完整 form 底部 `chatter`

**ERP 主操作入口调整**

- 列表视图中不再展示“启用到ERP”按钮，仅保留 `erp_enabled` 状态列。
- 主 form 顶部 `header` 保留：
  - `action_activate_to_erp`
  - `action_view_erp_product`
- split 右侧 form 顶部 `header` 保留同样的 ERP 动作按钮。

**split 右侧“打开表单”入口**

- 分屏右侧不再使用绝对定位悬浮按钮。
- 新增模型动作 `action_open_full_form()`，返回 `diecut.catalog.item` 主 form 的标准 `ir.actions.act_window`。
- 在 split standalone form 的 `header` 中新增按钮：
  - `action_open_full_form`
  - 文案：`打开表单`
- 该按钮与 `启用到ERP` / `已启用ERP` 位于同一 `header` 行，保持同层、同高、同线，不再受右上角分页控件遮挡。
- 主 form 本身不显示这个“打开表单”按钮，避免完整页出现自跳转入口。

**技术参数列表“值”列收敛**

- 主 form 与 split form 的 `spec_line_ids` 列表从“文本值/数值/布尔值/枚举值”四列收敛为单列 `值`。
- 统一使用 `value_text` 字段承载列表显示与编辑，`unit` 保持独立列。
- `display_value` 不再作为列表主展示列，继续保留给“值+单位”拼接展示场景。
- one2many 行内 form 继续保留分类型字段，保证类型校验与录入兼容。

**相关文件**

- `models/catalog_item.py`
- `views/catalog_item_views.xml`
- `static/src/xml/material_split_preview.xml`

#### 6.8.2 2026-03-13 后台旧目录入口清理

- 顶层菜单 `材料选型大全` 已直接绑定到 `action_diecut_catalog_item_gray`。
- 旧后台视图文件 `views/material_catalog_views.xml` 已从模块加载清单移除。
- 旧隐藏菜单 `材料型号清单(旧架构)`、`材料型号清单(旧架构列表)`、`新建材料系列` 与实验入口不再保留。
- `catalog_activate_wizard` 后台启用流程已收敛为仅支持 `diecut.catalog.item`，不再走 `product.product` 旧变体分支。

---

`<a id="7-安全与权限"></a>`

## 7. 安全与权限

### 7.1 访问控制规则

| 模型                            | 用户组       | 读 | 写 | 创建 | 删除 |
| ------------------------------- | ------------ | :-: | :-: | :--: | :--: |
| diecut.quote                    | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| diecut.quote                    | group_system | ✓ | ✓ |  ✓  |  ✓  |
| diecut.quote.material.line      | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| diecut.quote.manufacturing.line | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| diecut.mold                     | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| diecut.brand                    | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| diecut.color                    | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| diecut.catalog.activate.wizard  | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| diecut.catalog.item             | group_user   | ✓ | ✓ |  ✓  |  ✗  |
| product.product                 | group_user   | ✓ | ✓ |  ✓  |  ✗  |
| sample.order                    | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| sample.order                    | group_portal | ✓ | ✓ |  ✓  |  ✗  |

> 注：为支持「材料型号清单」分屏右侧直接编辑，本模块在 `security/ir.model.access.csv` 中为 `base.group_user` 配置了 `diecut.catalog.item` 读/写/创建（不授予删除）。`product.product` 的权限当前仅服务于 ERP / 网站兼容链路，不再作为后台目录入口设计前提。

---

`<a id="8-设计决策记录-adr"></a>`

## 8. 设计决策记录 (ADR)

### ADR-001: 价格统一按平方米计价

- **背景**: 模切行业中，材料有卷料、片料之分，供应商报价可能按卷/按公斤/按平方米。价格字段语义不一致会导致报价核算错误。
- **决策**: 系统底层 `seller.price` 和 `price_per_m2` 统一存储**每平方米单价**。整卷/片价格为派生值 (`price_m2 × 面积`)。
- **权衡**: 牺牲了与 Odoo 原生 `seller.price`（通常是 per-unit 价格）的语义一致性，但消除了多处价格换算的歧义。
- **日期**: 2025-01

### ADR-002: 选型目录与ERP原材料共用 product.template

- **状态**: 已被 `Phase 4 / v1.7` 的后台目录主线收口部分替代。后台型号管理与启用流程现以 `diecut.catalog.item` 为主；`product.template` 仍保留给 ERP 原材料与网站兼容链路。
- **背景**: 选型目录（材料手册）和 ERP 原材料（实际采购件）都涉及"材料"，需决定是否拆分为独立模型。
- **决策**: 共用 `product.template`，通过 `is_catalog` 和 `is_raw_material` 互斥标志位区分。
- **权衡**: 减少代码重复，可复用 Odoo 原生产品功能（变体、供应商、图片等），但需要严格的互斥约束和 domain 过滤。
- **日期**: 2025-01

### ADR-003: 变体技术参数使用 Char 类型

- **背景**: 原厂数据格式多样，如厚度 "35±5 μm"、剥离力 ">800 gf/inch"、胶厚 "13/13"。
- **决策**: 变体技术参数（`legacy_field`, `legacy_field` 等）使用 `Char` 类型保留原文。另加 `*_std` 字段存储归一化值用于筛选。
- **权衡**: 查询效率略低，但保留了数据完整性和可读性。
- **日期**: 2025-01

### ADR-004: 启用到ERP的幂等性保障

- **背景**: 多用户同时在选型目录中点击"启用到ERP"，可能导致重复创建 ERP 原材料。
- **决策**: 当前后台主线在 `diecut.catalog.item` 上维持单一启用状态，通过 `erp_enabled` / `erp_product_tmpl_id` 回写结果，并在目录主表上保持业务唯一键 `brand_id + code`。
- **权衡**: 收口后不再依赖旧 `legacy_field` 链路；网站兼容层仍保留在 `product.template / product.product` 周边，后续如继续清理需单独评估。
- **辅助工具**: 老的 `legacy_field` 排重 SQL 仅保留为历史资料，不再作为当前后台主链路运维工具。
- **日期**: 2025-01

### ADR-005: 供应商价格表的影子缓存字段

- **背景**: Odoo 的 `onchange` 在编辑状态下，子表（`seller_ids`）无法实时获取父表（`product.template`）未保存的规格变更。
- **决策**: 在 `product.supplierinfo` 上增加 `calc_area_cache` 和 `calc_weight_cache` 影子字段，父表 `onchange` 时主动推送最新面积/重量。
- **权衡**: 增加了两个技术字段，但解决了 Odoo onchange 的上下文隔离问题。
- **日期**: 2025-01

### ADR-006: 标准化字段迁移改为脚本化

- **背景**: Odoo 19 对业务字段 `oldname` 参数不再兼容，升级时会出现 unknown parameter 告警。
- **决策**: 停用 `oldname` 迁移写法，改为显式脚本迁移与重算：
  1. `legacy_field` 负责厚度标准单位从 `um` 统一为 `μm`；
  2. `legacy_field` 负责按当前归一化规则全量重算 `legacy_field`。
- **权衡**: 需要一次性执行运维脚本，但迁移逻辑更透明、可审计、可重复执行。
- **日期**: 2026-03

### ADR-007: 选型目录产品与库存模块隔离

- **背景**: 选型目录材料（`is_catalog=True`）设计目标是“仅用于选型参考，不参与库存业务”，但 Odoo 原生库存入口默认会展示全部产品。
- **决策**: 覆盖库存模块核心产品 Action 的 `domain`，统一增加 `is_catalog=False`（模板）或 `product_tmpl_id.is_catalog=False`（变体）过滤条件。
- **权衡**: 保证业务边界清晰、减少误操作；代价是需要持续跟踪 Odoo 升级后 Action ID 变化。
- **日期**: 2025-01

### ADR-008: SearchPanel 分类联动的动态列显隐 (Owl Patch 重构)

- **背景**: Odoo SearchPanel 不支持向 List 组件传递状态按分类定制列的显示。此前的做法是用原生的 JS 轮询和 CSS 注入强行改写 DOM，此为前端的反模式（Anti-pattern），易引发 Odoo 崩溃。
- **决策**: 重构为 Odoo 19 钦定的 Owl 组件扩展规范。通过 `patch` 方法拦截 `@web/views/list/list_renderer` 的 `getActiveColumns()` 方法。在渲染前自动过滤掉所有纯空字段列（即该列中所有记录都无值）和不符合分类规则的特定列（如密度列）。
- **权衡**: 牺牲了一点极其底层的代码灵活性（依赖 `this.props.list.records` 解析），但换来了极为出色的系统稳定性和渲染性能零损耗；不存在 DOM 重刷时的页面频闪与状态打架。
- **日期**: 2026-03 (重构)

### ADR-009: 采购模块与选型目录的业务隔离

- **背景**: 选型目录材料用于技术选型，不应参与采购业务。若采购入口不隔离，可能误将选型样本下单。
- **决策**: 采购模块产品入口与采购单产品选择统一过滤 `is_catalog=True`，仅允许 ERP 原材料/可采购产品进入采购流程。
- **权衡**: 业务边界更清晰，能降低误采风险；需要在 Odoo 升级后复核采购 Action/视图继承点。
- **状态**: 已落地。
- **日期**: 2025-01

### ADR-010: 表单视图高级 UI 布局 (Bootstrap 5 栅格)

- **背景**: 原本计划开发前端拖拽调整表单字段顺序和分组的功能，但这在 Odoo 19 (Owl VDOM) 中容易导致严重的渲染重绘冲突和生命周期问题，且配置过于复杂。
- **决策**: 放弃 “自定义拖拽表单排版” 方案。改为全面利用 Odoo 19 原生支持的 **Bootstrap 5 UI 卡片与栅格化布局**（`<div class="row">` / `<div class="col-md-4">` / `<div class="card">`）。
- **权衡**: 牺牲了用户级的“拖拽改排版”自由度，换来了极高颜值的企业级界面、零前端报错风险，以及长期的可维护性（纯 XML 继承控制）。
- **范围**: 适用于需要增强展示体验的核心模块表单（如当前 `diecut.catalog.item` 完整 form / split form）。
- **状态**: 已落地；当前主线视图见 `views/catalog_item_views.xml`。
- **日期**: 2026-03

### ADR-011: 多变体产品数据初始化的生成器策略 (Excel/CSV -> XML + JSON)

- **背景**: 在 Odoo 核心机制中，如果使用 XML 的 `<record>` 为 `product.template` 挂载属性（Attribute Lines），系统会后台自动生成一堆空壳变体。如果手写 `<record>` 写入变体的特有参数（如厚度、初粘力等），不仅代码极其臃肿，而且容易覆盖业务数据的修改。早前尝试过手写 JSON 并用 `post_init_hook` 拦截，但 `post_init_hook` 仅在首次安装生效，不支持后续的模块升级 (`Upgrade`)。同时，针对品牌分散、文件繁多的情况，手动维护 `__manifest__.py` 容易遗漏新生成的 XML 文件，导致数据“离奇失踪”。
- **决策**: 采用 **“Excel/CSV 业务驱动代码生成 + 自动注册”** 的大厂企业级策略：
  1. 彻底拥抱 Python 脚本生成器（`scripts/generate_catalog.py`）。当前主线以 `catalog_items.csv`（目录主表）和 `catalog_item_specs.csv`（技术参数明细）供非技术人员用 Excel 直接维护。
  2. 脚本运行后，自动生成标准的 `data/catalog_{brand}_data.xml` 和 `data/catalog_materials.json`。
  3. **注册自动化**: 脚本在结束前会**自动扫描并覆写 `__manifest__.py` 里的 `data` 列表**。它会精准定位 `catalog_*.xml` 文件并按顺序注册到触发器 `load_json_data.xml` 之前。
  4. 采用后置触发器 (`noupdate="0"`) 驱动 `_load_catalog_base_data_from_json` 钩子，根据 JSON 内容动态装填变体（使用 `getattr` 防覆盖机制）。
- **权衡**: 彻底将业务数据维护权释放给业务端，且实现了从“数据录入”到“manifest 注册”的全链路 100% 自动化，根绝了因手动漏写配置文件导致的功能异常。
- **日期**: 2026-03

### ADR-012: 双向同步机制与“主动清除”逻辑 (Field Clearing)

- **背景**: 早期同步方案仅支持覆盖（Overwrite）或忽略。用户反馈在 CSV 中把某个格子的值删掉置空后，Odoo 系统里对应的字段依然保留旧值，无法实现“删除”或“清空”的业务意图。同时，用户在 Odoo UI 界面手动修改的名字（如修复笔误）在导出后容易丢失中文语境。
- **决策**: 引入 **双向闭环同步 (Bi-directional Closure)** 与 **主动清除逻辑**:
  1. **导出加持（已收敛）**: 目录主数据导出以 Catalog Item 运维向导为主入口，统一中文语境并保证字段口径与主表/参数明细模板一致。
  2. **临时 ID 保护**: 针对 UI 手工创建的临时记录（如 `brand_ui_exported_21`），在同步时增加“白名单过滤”，防止生成器反向将品牌名误改为数字（乱码）。
  3. **主动清除 (Active Field Clearing)**: 在 `product_diecut.py` 的加载钩子中，改变以往“只管加，不管减”的逻辑。当 JSON 中某个变体字段明确不存在或为空字符串时，同步机制会**主动向 Odoo 写入 `False` (对应数据库 Null)**，从而物理级响应用户在 CSV 中的“置空”删除行为。
- **权衡**: 响应了用户对“所见即所得”的同步期待。虽然由于 Odoo 变体引擎限制，我们仍然不建议物理删除 `product.product` 记录（以防破坏订单关联），但实现了“数据内容层”的 100% 记录清零。
- **日期**: 2026-03

### ADR-013: 跨平台控制台与编码鲁棒性 (Carriage Return & GBK/UTF-8)

- **背景**: Windows 环境产生的 CSV 含有隐藏的 `\r\n` (CRLF)，当这些数据在 Linux 容器中打印或拼装字符串时，隐藏的 `\r` 会导致控制台光标跳行重叠（造成乱码重叠的视觉错觉）。此外，Excel 用户常在 GBK 和 UTF-8-sig 编码间切换，处理不当会引发 UnicodeDecodeError。
- **决策**: 在生成器底层引入 **Encoding Safety Guard**:
  1. **自动嗅探**: `read_csv_safe` 自动兼容带 BOM 的 UTF-8 和 GBK 编码。
  2. **CR Stripping**: 在解析 CSV 行的每一项时，强制对所有字符串执行 `.replace('\r', '')`。这不仅解决了字符串在数据库中的纯净度，也彻底消除了在同步过程中终端输出发生“吞字/叠字”的现象。
- **权衡**: 提升了工具在异构系统（Windows 开发 & Linux 运行）下的交互体验，减少了因不可见字符导致的数据校验故障。
- **日期**: 2026-03

### ADR-014: 材料型号清单分屏工作台（原生控制栏切换）

- **背景**: 传统列表→表单切换在型号维护场景下操作链路较长，且需要频繁返回列表；同时自定义悬浮切换条样式与 Odoo 原生控制栏不一致。
- **决策**: 在材料型号清单主入口（现为 `diecut.catalog.item`）引入 `diecut_split_list` 视图：
  1. 继承 `web.ListView`，将模式切换按钮插入 `control-panel-navigation-additional` 插槽（原生位置）；
  2. 采用 OI 图标与 `o_cp_switch_buttons` / `o_switch_view` 样式；
  3. 保留三种模式：左右/上下/仅列表；
  4. 右侧表单使用专用 `view_diecut_catalog_item_split_form`（去按钮箱干扰），支持直接编辑；。
- **权衡**: 前端实现复杂度提高（Controller + Renderer + XML 继承 + 状态同步），但显著提升了操作效率与一致性，且与 Odoo 原生 UI 视觉语言对齐。
- **日期**: 2026-03

### ADR-015: 技术参数模板分级继承与三 CSV 标准化

- **背景**: 原有技术参数模板仅按当前分类精确匹配，无法复用父分类参数；同时参数定义缺乏标准化导入导出，重装环境恢复依赖人工补录。
- **决策**:
  1. 参数模板改为分类继承链解析（父到子），同 `param_key` 冲突时子级覆盖父级；
  2. 型号新建、补齐模板、重建模板全部使用继承结果；
  3. 参数值导入匹配改为继承匹配，父分类参数可用于子分类型号；
  4. 运维标准升级为五表：`catalog_series.csv`（系列）、`catalog_items.csv`（主表）、`catalog_params.csv`（参数定义）、`catalog_category_params.csv`（分类参数）、`catalog_item_specs.csv`（参数值）；
  5. 参数定义采用 upsert（`categ_id_xml + param_key` 唯一键），不做隐式删除。
- **重装恢复 SOP**:
  1. 安装模块（加载基线参数定义）；
  2. 导入 `catalog_params.csv` 与 `catalog_category_params.csv`；
  3. 导入 `catalog_items.csv`；
  4. 导入 `catalog_item_specs.csv`；
  5. 执行“补齐参数模板”。
- **升级策略**: 保持参数定义基线数据 `noupdate=1`，升级不覆盖界面维护数据；仅显式导入参数定义 CSV 时变更参数定义。
- **日期**: 2026-03

---

`<a id="9-数据库约束与索引"></a>`

## 9. 数据库约束与索引

### SQL 约束

| 模型                    | 约束名                 | 类型                    | 说明               |
| ----------------------- | ---------------------- | ----------------------- | ------------------ |
| `diecut.brand`          | `diecut_brand_name_uniq` | UNIQUE(name)            | 品牌名称精确唯一   |
| `product.category`      | `name_parent_uniq`     | UNIQUE(name, parent_id) | 同层级不能重名     |
| `diecut.mold.location`  | `name_unique`          | UNIQUE(name)            | 刀模存放位置唯一   |

### 自定义索引

| 索引名                                                  | 表               | 列                        | 类型             | 条件                                        |
| ------------------------------------------------------- | ---------------- | ------------------------- | ---------------- | ------------------------------------------- |
| `legacy_field` | product_template | legacy_field | 历史索引 | 已退出后台主链路，保留历史说明 |

> 在 `init()` 方法中创建，升级前会检测历史重复数据，如有重复则抛出错误要求先清理。

### Python 约束

| 方法                                      | 触发字段                    | 说明                     |
| ----------------------------------------- | --------------------------- | ------------------------ |
| `_check_catalog_raw_material_exclusive` | is_catalog, is_raw_material | 互斥                     |
| `legacy_field`  | legacy_field   | 历史约束说明（当前后台主线不再使用） |
| `_check_catalog_replacements`           | replacement_catalog_ids     | 不能包含自己、非目录产品 |

---

`<a id="10-变更日志"></a>`

## 10. 变更日志

| 2026-03 | v1.10 | **技术参数“值”列枚举下拉**：新增前端字段组件 `diecut_spec_value_widget`，在主 form 与 split form 的 `spec_line_ids` 列表中为 `value_text` 提供动态渲染；当 `value_type=selection` 时显示下拉菜单（来源 `selection_options`），其他类型维持文本输入；不改数据模型与导入协议。 | static/src/js/spec_value_field.js、static/src/xml/spec_value_field.xml、views/catalog_item_views.xml、docs/DESIGN_MANUAL.md、__manifest__.py |
| 2026-03 | v1.9 | **技术参数列表“值”列收敛**：`diecut.catalog.item` 主 form 与 split form 的 `spec_line_ids` 列表由四列值字段（文本/数值/布尔/枚举）收敛为单列 `value_text`（标题“值”）；`unit` 保持独立列；`display_value` 保留为“值+单位”拼接场景，one2many 行内 form 继续保留分类型编辑。 | views/catalog_item_views.xml、docs/DESIGN_MANUAL.md |
| 2026-03 | v1.7 | **Catalog Item 界面、技术参数、后台入口与文档收敛**：统一产品信息字段为 `product_features` / `product_description` / `main_applications` / `equivalent_type`；完整 form 底部接入 `chatter` 附件区；split 右侧新增 `打开表单` 入口并移入表单 `header`；产品信息区顺序统一为“产品特点 → 产品描述 → 主要应用 → 相当品”；新增 `diecut.catalog.item + diecut.catalog.spec.def + diecut.catalog.item.spec.line` 三层技术参数管理说明与分类模板示例；后台旧目录入口、旧分屏视图与旧激活向导分支下线。 | models/catalog_item.py、models/catalog_spec.py、wizard/catalog_activate_wizard.py、views/catalog_item_views.xml、views/diecut_menu_view.xml、views/my_material_base_views.xml、static/src/xml/material_split_preview.xml、data/catalog_spec_def_data.xml、docs/DESIGN_MANUAL.md |
| 2026-03 | v1.8 | **技术参数模板继承与运维标准化**：参数模板支持分类继承（父到子、子级同键覆盖）；参数行约束放宽为“同分类或祖先分类”；参数值导入改为继承匹配；运维向导与 AG Grid 统一切换到 `catalog_params.csv` / `catalog_category_params.csv` / `catalog_item_specs.csv` 标准链路，并补充重装恢复 SOP 文档。 | models/catalog_item.py、models/catalog_spec.py、views/catalog_item_views.xml、wizard/catalog_ops_wizard.py、wizard/catalog_ops_wizard_view.xml、controllers/main.py、docs/DESIGN_MANUAL.md |
| 2026-03 | v1.6 | **目录架构收口（Phase 4）**：下线 `catalog_runtime_service` / `catalog_sync_service` / `catalog_shadow_service` 与相关切换/健康检查向导，收口为 `diecut.catalog.item` 单模型主线 + 运维日志。 | models/catalog_item.py、models/catalog_ops_log.py、wizard/catalog_ops_wizard.py、views/catalog_item_views.xml、views/diecut_menu_view.xml |
| 2026-03 | v1.7 | **旧架构代码直清理**：移除 `legacy_field` 老链路字段与旧网站模板依赖，删除旧 CSV 导出/爬取脚本（`series.csv/variants.csv` 流程），库存过滤统一转为 `is_raw_material` 主线。 | models/product_diecut.py、controllers/main.py、views/stock_quant_views.xml、__manifest__.py、scripts/*、docs/DESIGN_MANUAL.md |
| 2026-03 | v1.6 | **品牌主数据独立化**：`diecut.brand` 抽离为独立模型文件，新增品牌库基础视图与菜单，并落地 `UNIQUE(name)` 精确唯一约束（含历史重复品牌合并）。 | models/diecut_brand.py、views/diecut_brand_views.xml、views/diecut_menu_view.xml、security/ir.model.access.csv |
| 2026-03 | v1.6 | **Odoo 19 兼容清理**：移除不兼容 `oldname`/字段级 `placeholder` 写法，约束升级为 `models.Constraint`，厚度标准值统一为 `μm` 并提供重算脚本。 | models/product_diecut.py、models/diecut_quote.py、models/product_category.py、models/mold.py、scripts/legacy_field、scripts/recompute_legacy_field_std.py |
| 2026-03 | v1.5 | **Phase 3（统一入口路由）**：新增运行时路由服务 `diecut.catalog.runtime.service`，提供统一入口菜单与可切换模式（`legacy_split` / `new_gray`），实现不中断切换。 | models/catalog_runtime_service.py、wizard/catalog_runtime_switch_wizard.py、wizard/catalog_runtime_switch_wizard_view.xml、views/diecut_menu_view.xml |
| 2026-03 | v1.5 | **Phase 2（结构化双写）**：新增 `diecut.catalog.sync.service`，将新模型关键变更双写回旧模型，并通过 `skip_shadow_sync` 上下文避免回灌环路。 | models/catalog_sync_service.py、models/catalog_item.py |
| 2026-03 | v1.5 | **Phase 1 收口（服务化+健康检查）**：影子回填/对账逻辑下沉到 `diecut.catalog.shadow.service`；新增迁移健康检查向导与结构异常筛选（孤儿/重复）。 | models/catalog_shadow_service.py、wizard/catalog_shadow_health_wizard.py、views/catalog_item_views.xml |
| 2026-03 | v1.4 | **材料型号清单分屏升级**：引入 `diecut_split_list` 视图，支持控制栏原生位置切换（三种模式：左右/上下/仅列表）、拖拽调宽与本地记忆。 | static/src/js/material_split_preview.js、static/src/xml/material_split_preview.xml、static/src/scss/material_split_preview.scss、material_catalog_views.xml |
| 2026-03 | v1.4 | **型号清单权限补充**：为内部用户增加 `product.product` 读/写/创建（不删除）以支持分屏右侧直接编辑。 | security/ir.model.access.csv、DESIGN_MANUAL 7.1 |
| 2026-03 | v1.3 | **运维与数据安全**：在附录 B.4 补充 Odoo 数据库备份、Docker 命令行备份及 CSV 业务备份机制，保障开发数据不丢失。 | DESIGN_MANUAL.md |
| 2026-03 | v1.3 | **同步机制大升级**：1. 实现 **Bi-directional Sync**（导出脚本支持 zh_CN 语境，防止名字回退）；2. 引入 **Field Clearing** 逻辑（CSV 置空可同步清空系统数据）；3. 解决 Windows/Linux 跨平台回车符乱码重叠问题；4. **Manifest 自动化**：generator 自动同步模块注册表；5. **自动归一化补全**：修复导入时 _std 字段的自动填充逻辑。 | scripts/export_from_db.py, scripts/generate_catalog.py, models/product_diecut.py, __manifest__.py |
| 2026-03 | v1.3 | **设计手册更新**：整理并详细说明了技术指标归一化逻辑，以及主子表（Template/Product）之间 compute/related 的数据同步与隔离机制。 | DESIGN_MANUAL.md |
| 2026-03 | v1.2 | 重构 ADR-011 数据初始化规范：引入 `generate_catalog.py` 脚本，实现 Excel/CSV 业务驱动自动生成 XML/JSON，彻底废弃 `post_init_hook`，改用全自动化和升级强刷机制 | DESIGN_MANUAL 8 (ADR-011)、scripts/generate_catalog.py、catalog_materials.json、product_diecut.py |
| 2026-03 | v1.2 | 重构 6.5.1 及 ADR-008 动态列显隐：废弃前端 CSS 注入黑魔法，重构为符合规范的 Owl Patch (直接拦截 ListRenderer.getActiveColumns)，保障 100% 框架安全 | static/src/js/catalog_dynamic_columns.js、DESIGN_MANUAL 6.5.1、8（ADR-008） |
| 2025-01 | v1.2 | 图册符号约定（—=无、〇=白、●=黑）；新增推出力/可移除性字段；Tesa 泡棉数据补全剥离力/推出力/可移除性/DuPont | product_diecut.py、catalog_tesa_acrylic_foam_data.xml、material_catalog_views.xml、DESIGN_MANUAL 3.2.2 |
| 2025-01 | v1.2 | 设计手册补充列显隐刷新机制：requestAnimationFrame + 点击 80/350ms 延迟 + MutationObserver + 500ms 轮询兜底，加速显示 | DESIGN_MANUAL 6.5.1                                                |
| 2025-01 | v1.2 | 全空列自动隐藏仅材料型号清单生效：通过是否存在 catalog_density 列判断页面，原材料列表不执行显隐，避免体验问题 | catalog_dynamic_columns.js、DESIGN_MANUAL 6.5                                    |
| 2025-01 | v1.2 | 型号清单全空列自动隐藏：选择某类时若某列在当前结果中全部为空则隐藏 | catalog_dynamic_columns.js、DESIGN_MANUAL 6.5                                    |
| 2025-01 | v1.0 | 初始版本：选型目录、原材料、成本计算器、价格统一                   | 全模块                                                                           |
| 2025-01 | v1.0 | 价格统一改版：底层全部按 m² 计价                                  | product_diecut, diecut_quote, requisition                                        |
| 2025-01 | v1.0 | 启用幂等性：行锁 + 唯一索引                                        | product_diecut, catalog_activate_wizard                                          |
| 2025-01 | v1.0 | 添加评审状态、推荐等级、替代系列                                   | product_diecut, material_catalog_views                                           |
| 2025-01 | v1.0 | 标准化字段 *_std：自动归一化 + 聚合索引                            | product_diecut, material_catalog_views                                           |
| 2025-01 | v1.0 | 清理 material_family 特性（已移除）                                | product_category, product_diecut                                                 |
| 2025-01 | v1.2 | 型号清单新增 `catalog_density` 并支持 SearchPanel 联动动态列显隐 | product_diecut, material_catalog_views, static/src/js/catalog_dynamic_columns.js |
| 2025-01 | v1.2 | 库存模块产品入口隔离：排除 `is_catalog=True` 选型目录材料        | views/stock_quant_views.xml                                                      |
| 2025-01 | v1.2 | 采购模块隔离落地：采购入口与采购选料链路排除 `is_catalog=True`   | purchase 相关视图/动作、DESIGN_MANUAL.md                                         |
| 2025-01 | v1.2 | 新增附录 B「Odoo 开发指南」：FORM 视图灵活性、产品多分类、页面按钮触发 Action | DESIGN_MANUAL.md 附录 B                                                          |
| 2025-01 | v1.2 | 型号详情与规格页：product.product 专用 Form、Action 绑定、ProductProduct 关联字段 | material_catalog_views.xml、product_diecut.py、DESIGN_MANUAL 6.6 / 3.2.1         |
| 2025-01 | v1.2 | 认证与合规、替代建议、附件与资料改为每变体独立：legacy_fields 字段、变体 Form 三页、系列为默认 | product_diecut.py、material_catalog_views.xml、DESIGN_MANUAL 3.2.4 / 6.6         |

---

`<a id="附录-a-如何维护本手册"></a>`

## 附录 A: 如何维护本手册

### 何时更新

- **新增字段**: 在对应模型章节的字段表中添加行
- **修改业务规则**: 更新第 4 章对应小节
- **重要技术决策**: 在第 8 章添加新的 ADR 条目
- **视图/菜单变更**: 更新第 6 章
- **每次发版**: 在第 10 章添加变更记录

### 命名规范

- ADR 编号连续递增：ADR-001, ADR-002, ...
- 变更日志按时间倒序（最新在前）
- 字段表按逻辑分组，不按字母排序

---

`<a id="附录-b-odoo-开发指南"></a>`

## 附录 B: Odoo 开发指南

本附录汇总与视图、分类、Action 相关的通用知识点，便于选型与扩展时查阅。

### B.1 FORM 视图的灵活性

**能否按材料分类建不同的 FORM 视图？**可以。Odoo 的 form 视图与模型绑定，不强制与分类绑定。做法是：

- 为同一模型（如 `product.template`）定义多份 form 视图（不同 `id`、可设不同 `name`）。
- 通过 **Action** 的 `view_id` 或 `view_ids` 指定打开时用哪一份 form；或通过 **菜单** 绑定到不同 Action，从而“按入口”呈现不同表单。
- 若希望“选某一分类后自动用某份 form”，可在 Action 的 `context` 里带分类条件，再在 form 上用 `attrs="invisible"` / `invisible` 按条件显隐区块；或为不同分类配置不同菜单项，每个菜单项指向不同 Action（不同 `view_id`）。

**能否不按分类、按任意方式建多份 FORM？**
可以。form 视图数量不限，按业务需要定义多份即可。通过不同菜单、不同 Action、或同一列表/看板上的不同“打开方式”指向不同 `view_id`，即可实现“同一模型、多种表单”。

**小结**：FORM 视图与分类无必然绑定关系，可按分类、按入口、按权限等任意维度设计多套表单，由 Action/菜单决定用哪一套。

### B.2 产品与多分类

**一个产品能否属于两种不同的分类？**可以。Odoo 的 `product.template` 上有 `categ_id`（Many2one，单一主分类），若需“同属多类”，可用以下方式之一：

- **主分类 + 标签/多对多**：保留 `categ_id` 作主分类，另建 Many2many 字段（如“适用分类”“附加分类”）挂到 `product.category`，用于筛选与展示。
- **仅用多对多**：不用 `categ_id`，只用自定义 Many2many 关联多个 `product.category`，则一个产品可同时属于多个分类。注意：若其它模块或报表依赖 `categ_id`，需评估兼容性。

本模块当前采用单一 `categ_id`；若后续需要“同一材料既在泡棉类又在双面胶类”等场景，可扩展为 Many2many 分类而不必改模型名。

### B.3 在页面用按钮/图标打开 Action（不通过菜单）

**打开 FORM 是否只能通过菜单？**不是。除了菜单，还可以：

- **列表/看板上的按钮**：在 list/tree 或 kanban 视图中，用 `<button type="action" name="%(action_xml_id)d" .../>` 调用 `ir.actions.act_window`，即可打开该 Action 对应的 form（或其它 view_mode）。无需先点菜单。
- **FORM 上的按钮**：在 form 视图里同样可用 `<button type="action" name="%(action_xml_id)d" .../>`，在点击时打开另一个 Action（如“新建某类产品”“打开关联列表”等），实现页面内跳转或弹窗。
- **其它触发方式**：通过 Python 代码返回 `ir.actions.act_window`（如向导结束时跳转）、或在前端自定义按钮调用 Odoo 的 action 服务，也可打开指定 FORM。

**小结**：只要定义好 `ir.actions.act_window` 并指定 `view_id`/`view_ids`，即可通过菜单、列表/表单上的按钮、或代码返回的方式打开对应 FORM，不依赖菜单入口。

### B.4 数据备份与恢复

本系统运行在 Docker 环境下，数据安全至关重要。建议采取以下多重备份方案：

#### B.4.1 Web 界面备份 (Database Manager)

这是最直观的备份方式，适合日常发版前快照：

- **入口**: `http://localhost:8069/web/database/manager`（开发环境端口可能为 8070）。
- **操作**: 点击 **Backup** 按钮。
- **格式**: 选择 **zip (includes filestore)** 可同时备份数据库和附件（如产品图片、CAD图纸）。
- **主密码 (Master Password)**: 默认为 `admin`。

#### B.4.2 Docker 命令行备份 (SQL Dump)

适合开发人员在容器外部快速提取纯 SQL 数据：

```bash
# 备份：将 odoo 数据库导出为 .sql
docker exec -t db pg_dump -U odoo odoo > db_backup_$(date +%Y%m%d).sql

# 恢复：将 .sql 导入回数据库（需先清空或新建库）
cat backup.sql | docker exec -i db psql -U odoo odoo
```

#### B.4.3 业务数据级备份 (CSV/Excel)

本模块独有的 **“业务驱动备份”**：

- **原理**: 通过目录运维向导导出的 `catalog_items.csv` 和 `catalog_item_specs.csv`，实际承载了当前 Catalog Item 主线的核心材料目录知识。
- **价值**: 即便整库丢失，只要保留这两份 CSV，也可以重建 `diecut.catalog.item` 主表与技术参数明细表。
- **建议**: 定期提交 CSV 文件到 Git 仓库，实现数据与代码同步版本化。

#### B.4.4 企业级自动备份建议

- **模块**: 在 Odoo 应用市场搜索并安装 `auto_backup` 模块，配置自动按频率（如每天）将备份上传至 FTP、S3 或挂载的 NAS。
- **Filestore**: 注意一定要备份 Docker 卷映射的 `/var/lib/odoo` 目录，那里存储了所有的静态附件。

---

`<a id="附录-c-材料选型大全行业共建共享设想提纲"></a>`

## 附录 C: 材料选型大全行业共建共享（设想提纲）

> 本节仅记录“将材料选型大全推向电子辅料模切行业、共建共享”的设想提纲，供后续讨论与规划参考，不构成当前系统实现范围。

### C.1 设想目标

- 将本模块中的**材料选型大全**能力，推向**电子辅料 / 模切行业**，形成**共建、共享**的选型参考库。
- 统一品类、字段与符号约定，减少各家企业重复建库与沟通成本，提升选型效率与一致性。

### C.2 价值与可行性（简要）

| 维度       | 要点                                                                                         |
| ---------- | -------------------------------------------------------------------------------------------- |
| 行业痛点   | 品牌与规格多、选型依赖 Excel/PDF/个人经验，易出错、难统一。                                  |
| 标准化价值 | 统一“型号–厚度–胶系–剥离力–推出力–可移除性”等字段及符号（—/〇/●），便于比对与协作。 |
| 共建价值   | 行业共同维护一份选型库，摊薄单家建库与维护成本。                                             |
| 技术基础   | 当前 Odoo 模块与数据规范（本手册及图册符号约定）可作为“行业版”或“标准数据接口”的基础。   |

可行性取决于：**牵头方**（协会/联盟/头部企业）、**共建规则**（谁可写、如何审、如何版本管理）、**试点范围**（先 1～2 品类或少数参与方）。方向可行，落地需分步推进。

### C.3 主要挑战与应对方向

| 挑战           | 应对思路（提纲）                                                                         |
| -------------- | ---------------------------------------------------------------------------------------- |
| 数据归属与质量 | 明确角色：品牌/代理商维护自家数据；模切厂/协会做引用或补充应用信息；引入审核或版本管理。 |
| 商业与利益     | 先做“规格与选型”层，弱化或延后报价；可设“品牌专区”由品牌方自主维护。                 |
| 版权与合规     | 仅收录可公开的规格参数；TDS/MSDS 以链接或来源说明为主；必要时签数据使用/贡献协议。       |
| 牵头与运营     | 协会/联盟/头部企业牵头，或先小范围试点再扩大。                                           |
| 激励           | 贡献者获得曝光或“认证数据源”标识；使用者减少选型时间与试错成本。                       |

### C.4 可选落地形态（提纲）

- **形态 A**：协会/联盟牵头，选型大全作为行业基础设施，数据对会员或合规方开放。
- **形态 B**：提供“标准模块 + 数据规范”，各企业在自有 Odoo 中安装，按约定格式（如 CSV/API）同步到公共库或互换数据。
- **形态 C**：由一方提供 SaaS 版“材料选型大全”，品牌/模切厂以入驻或贡献数据换取使用权限。

### C.5 若推进时建议的步骤（提纲）

1. **固化标准**：以本手册及现有数据规范为基础，整理《选型数据规范》或《共建说明》（字段、分类、图册符号 —/〇/● 等），作为共建准入条件。
2. **小范围试点**：选 1～2 个品类（如泡棉胶带、双面胶）与 2～3 家愿意配合的品牌/代理商，用当前选型大全做“行业试点版”，跑通数据来源、审核与发布流程。
3. **明确共建形态**：在 A/B/C 或组合形态中选定方向，明确主办方、贡献者权益与数据使用范围。
4. **合规与法律**：涉及品牌、型号、TDS 引用等时，与法务或顾问确认可公开范围与授权需求。

### C.6 状态说明

- **当前状态**：设想阶段，仅作记录与讨论用。
- **与现有系统关系**：本模块设计与实现不受此设想约束；若未来推进行业共建，可在现有数据模型与规范之上扩展“行业库”或“同步接口”，而不必推翻现有选型大全。

---

*本手册由开发团队维护，如有疑问请联系系统架构师。 AAAA*
---

## v1.8 设计增补：Catalog 系列主数据 + 型号可覆盖（混合模式）

> 更新时间：2026-03-13  
> 适用模块：`diecut`  
> 目标：把“应用/描述/特性”从纯型号维护升级为“品牌下系列模板 + 型号按字段覆盖”。

### 1. 总体原则

1. 系列按品牌隔离管理，不同品牌系列不混用。  
2. 型号以 `series_id`（Many2one）作为系列主入口，`series_name` 作为导入与展示口径。  
3. 三个业务字段采用“继承默认 + 按字段覆盖”：
   - `product_features`
   - `product_description`
   - `main_applications`
4. 覆盖是字段级，不是整条记录级。  
5. CSV 标准链路升级为 4 文件：主表、参数值、参数定义、系列模板。  

### 2. 新增模型：`diecut.catalog.series`

系列模板主数据模型（品牌维度）：

- 关键字段：
  - `brand_id`
  - `name`
  - `product_features`
  - `product_description`
  - `main_applications`
  - `active`
  - `sequence`
- 业务约束：
  - 同品牌下系列名唯一：`(brand_id, name)`。
- 管理入口：
  - 菜单“系列模板管理”。

### 3. Catalog Item 继承与覆盖机制

`diecut.catalog.item` 使用以下规则：

1. 品牌与系列联动：
   - `series_id` 仅可选择当前 `brand_id` 下的系列。
   - `brand_id` 变更后，若现有 `series_id` 不属于新品牌，自动清空。  
2. 覆盖开关（三字段独立）：
   - `override_product_features`
   - `override_product_description`
   - `override_main_applications`
3. 生效规则：
   - 覆盖开关为 `false`：默认跟随系列模板值。
   - 覆盖开关为 `true`：使用型号自身字段值。  
4. 系列切换后可通过“应用系列模板”向导二选一：
   - 仅填空（`fill_empty`）
   - 覆盖全部（`overwrite`，但仅作用于未勾选覆盖的字段）

### 4. 表单与分屏（split）交互规范

1. 主 form 与 split form 的“产品信息与应用”区展示一致：
   - 系列（`series_id`）
   - 产品特点、产品描述、主要应用
   - 各字段覆盖开关状态
2. 系列字段禁 quick create，允许“弹窗创建并编辑”，保证主数据质量。  
3. “应用系列模板”按钮用于显式套用模板策略，不隐式覆盖人工维护内容。  

### 5. CSV 标准化（v1.8）

#### 5.1 四文件标准

1. `catalog_items.csv`（型号主表）
2. `catalog_item_specs.csv`（型号参数值）
3. `catalog_params.csv`（参数定义）
4. `catalog_category_params.csv`（分类参数）
5. `catalog_item_specs.csv`（型号参数值）
#### 5.2 主表列规范（关键变化）

- 主入口统一为 `series_id`，导入模板统一使用 `series_name`。  
- 品牌解析支持：
  - `brand_id_xml`（优先）
  - `brand_name`（兼容）

#### 5.3 导入顺序建议

1. 先导入 `catalog_series.csv`（按 `brand + series_name` upsert）。
2. 再导入 `catalog_items.csv`（绑定 `series_id`）。
3. 再导入 `catalog_params.csv` 与 `catalog_category_params.csv`。
4. 最后导入 `catalog_item_specs.csv`。  
#### 5.4 兼容说明

- 运行时不再兼容读取旧系列文本字段；历史库通过迁移脚本一次性收口到 `series_id` / `series_name`。  
- 新模板与新增数据维护应统一使用 `series_name`。  

### 6. 历史数据迁移规则（多数优先）

历史 `brand + 系列文本` 数据迁移到系列主数据时：

1. 按 `brand + 系列文本` 分组生成系列记录。
2. 每组对三字段取“多数值”写入系列模板。
3. 与多数值不同的型号自动打对应 `override_* = true`，并保留型号原值。
4. 型号最终关联到 `series_id`。

### 7. 回归边界

本次方案不改变以下主线：

1. 技术参数定义/值的分类继承逻辑（父到子，子覆盖父）。
2. `catalog_activate_wizard` 启用 ERP 主流程。
3. split 作为高频浏览入口的定位。  

### 8. 运维SOP（重装恢复）

重装或新库恢复推荐流程：

1. 安装模块并升级到目标版本。
2. 导入 4 CSV（系列模板 -> 主表 -> 参数定义 -> 参数值）。
3. 对需要的分类执行参数补齐动作。
4. 抽样验证：
   - 品牌-系列下拉隔离
   - 覆盖开关行为
   - 列表筛选/分组
   - 启用 ERP 流程

### 9. 变更日志（新增）

- **2026-03-13 / v1.8**
  - 新增系列主数据模型 `diecut.catalog.series`（品牌维度唯一）。
  - `diecut.catalog.item` 增加 `series_id` 与三字段覆盖开关。
  - 主 form / split form 统一系列继承+覆盖交互。
  - 运维 CSV 升级为四文件标准，加入 `catalog_series.csv`。
  - 明确 `series_id` / `series_name` 为正式入口，旧系列文本字段已下线。

- **2026-03-13 / v1.8.1**
  - `Catalog Item` 区块更名为“系列信息与应用”。
  - 型号侧 `product_features / product_description / main_applications` 改为只读强同步（以 `series_id` 模板为唯一来源）。
  - 新增型号层独立字段 `special_applications(Html)`（“型号特殊应用”），不参与系列同步。
  - 主 form 与 split form 同步调整：移除“应用系列模板”按钮与覆盖勾选项展示，仅保留系列强同步 + 型号特殊应用编辑。
## v1.8.2 设计增补（批量改分类与参数约束调整）

> 更新时间：2026-03-13  
> 适用模块：`diecut`

### 1) 批量改材料分类（含技术参数处理 + ERP同步）

在 `diecut.catalog.item.batch.update.wizard` 中新增分类专用流程：

- 新增向导字段：
  - `target_categ_id`（目标材料分类）
  - `categ_change_policy`（`keep_specs` / `rebuild_specs`）
- `keep_specs`（策略3）：
  - 仅改分类；
  - 若存在不兼容参数（参数定义不在目标分类继承链）则整批拦截并返回清单。
- `rebuild_specs`（策略1）：
  - 改分类后清空旧参数；
  - 按目标分类模板重建 `spec_line_ids`。
- 新增不兼容二次处理动作：
  - “同步更新新分类参数列表”；
  - 不兼容记录按重建处理，兼容记录仅改分类。
- ERP分类同步规则：
  - 仅对 `erp_enabled=True` 且 `erp_product_tmpl_id` 非空的记录同步 `product.template.categ_id`；
  - 未关联ERP产品的记录跳过并计入结果统计。

### 2) 技术参数“必填”强约束取消

`diecut.catalog.item.spec.line` 的后端约束已调整：

- 取消 `spec_def_id.required` 对参数值的强制拦截（不再因为“参数XX为必填项”阻止保存/批量改分类）。
- 保留以下校验不变：
  - 值类型互斥校验（char/float/boolean/selection 仅允许填写匹配字段）；
  - 枚举值合法性校验；
  - 参数定义分类必须属于当前型号分类继承链校验。

### 3) 操作建议

- 对已有大量参数的型号批量改分类时，优先使用策略3做兼容性预检；
- 若存在不兼容条目，使用“同步更新新分类参数列表”完成分流处理；
- 若业务允许参数重置，可直接使用策略1提高处理效率。
---

## v1.11 设计增补：AI/TDS、OdooBot 与草稿编辑主线

> 更新时间：2026-03-25  
> 适用模块：`diecut`、`chatter_ai_assistant`

### 1. 当前主链路

当前 AI/TDS 主线已经从“单模型专用解析入口”收口为统一入口：

- 业务记录 `chatter`
- `OdooBot` 一对一私聊
- 外部 `OpenClaw agent/cli`
- `diecut.catalog.source.document` 草稿审校与入库

运行形态为：

`用户消息 -> Odoo/OdooBot 触发 -> chatter.ai.run 排队 -> worker 认领 -> OpenClaw 执行 -> 回写 chatter / source document`

### 2. 触发规则

#### 2.1 业务记录 chatter

普通业务记录中，AI 仍采用显式触发：

- `@OdooBot`
- `@odoobot`
- `@bot`

仅当消息显式 mention 机器人时，才会进入 AI 链路，避免普通业务沟通误触发。

#### 2.2 OdooBot 私聊

与 `base.partner_root`（即 `OdooBot`）的一对一私聊已由 AI 接管：

- 用户在 OdooBot 私聊窗口中发送的每条普通消息都会触发 AI
- 不再要求额外输入 `@bot`
- 原生 OdooBot 的欢迎/教学类自动回复不再作为主链路

### 3. OpenClaw 执行模式

当前后端执行统一使用 `OpenClaw agent/cli` 模式，不再走旧 WebSocket gateway 方案。

设计原则：

- Odoo 不承担推理与工具调度
- OpenClaw 负责：
  - LLM 推理
  - tools / skills 调用
  - PDF、图片、网页等多模态理解
- Odoo 负责：
  - 收集消息、附件、上下文
  - 排队与并发隔离
  - 草稿落地
  - 审校与导入

### 4. source document 语义与自然语言入口

在 `diecut.catalog.source.document` 的 `chatter` 中：

- “这份文档”默认指当前单据主附件/当前消息附件
- “这张图片/这张截图”默认指当前消息新上传的图片，若没有则回退到单据可用附件
- “这个网页”默认指单据的 `source_url`，若消息中带了新链接则优先使用新链接

当前支持的自然语言主任务：

- `帮我把这份文档解析一下`
- `帮我总结这份 PDF`
- `帮我总结这张截图`
- `帮我解析这个网页`
- `把这张图里的参数整理出来`
- `把厚度单位改成 um`
- `记住这条规则，以后都这样`

设计约束：

- 支持自然语言，但要求意图明确
- 一条消息只执行一个主任务
- 不做“自由聊天自动猜测并顺便入库”

### 5. 多模态解析策略

当前默认策略如下：

- PDF：优先走 OpenClaw PDF 工具
- 图片 / 截图：优先走 OpenClaw 视觉工具
- 网页链接：优先走 OpenClaw 网页抓取/页面解析工具
- Odoo 旧提取逻辑：仅作为 PDF/TDS fallback

输出策略：

- 能结构化就写成草稿
- 不适合结构化时只回摘要/重点
- 不强迫每次都生成目录可入库数据

### 6. AI 草稿桶与业务落点

AI/TDS 草稿仍采用六桶口径：

- `series`
- `items`
- `params`
- `category_params`
- `spec_values`
- `unmatched`

业务落点不变：

- `series` -> `diecut.catalog.series`
- `items` -> `diecut.catalog.item`
- `params` -> `diecut.catalog.param`
- `category_params` -> `diecut.catalog.category.param`
- `spec_values` -> `diecut.catalog.item.spec.line`
- `unmatched` -> 审校产物，不直接入业务主表

### 7. 草稿编辑器设计

`diecut.catalog.source.document` 的“草稿编辑”页已经升级为人工审校主界面，目标是尽量贴近正式物料表单，而不是只看 JSON。

当前编辑页分为三块：

- `基础属性`
- `选型信息`
- `技术参数`

其中：

- `产品描述 / 产品特性 / 主要应用` 直接展示并可编辑
- `相当品(替代类型)`、型号补充说明等可人工修订
- 保存后会重新同步回 `draft_payload`
- 再执行入库时，以最新人工修订内容为准

### 8. 技术参数统一大表

旧的“参数字典”和“参数值”分离预览方式，已在草稿编辑场景下收口成一张统一大表。

当前大表最少包含这些列：

- 型号
- 参数字典
- 参数名称
- 参数键
- 参数状态
- 值
- 单位
- 条件摘要
- 测试方法
- 测试条件
- 备注
- 参数分类
- 写入位置
- 来源

设计目标：

- 一眼看出参数是否复用现有字典
- 一眼看出当前有没有解析到值
- 一眼看出该值最终落到哪里
- 支持人工逐行修改与补录

### 9. 参数状态的业务语义

参数状态用于帮助人工审核，不直接等价于数据库最终动作。

当前语义：

- `复用现有`
  - 已匹配到现有 `diecut.catalog.param`
  - 入库时复用现有参数定义
- `建议新建`
  - 当前草稿认为应新增参数字典
  - 需要人工确认后再进入正式参数定义流程
- `待确认`
  - 尚未完成稳定匹配
  - 不应直接视为可自动入库

### 10. 系列级说明字段的落库原则

以下内容属于 `series` 级说明，而不是普通参数值：

- 产品描述
- 产品特性
- 主要应用

这些内容在 AI 解析阶段会优先进入：

- `series.description` / `product_description`
- `series.features` / `product_features`
- `series.applications` / `main_applications`

在正式导入后，最终落到 `diecut.catalog.series` 对应字段，而不是误塞进技术参数表。

### 11. 并发与可见性

AI 运行记录按 `run` 粒度隔离：

- 每次触发一个独立 `run_id`
- 上下文按记录/频道隔离
- worker 与 OpenClaw 运行目录独立
- 同一触发消息默认只创建一个有效 run

前端可见性原则：

- 业务记录 chatter 允许短暂状态反馈
- OdooBot 私聊只保留最终回复，不插入噪音状态消息
- 页面自动刷新需防重，避免循环刷新

### 12. 当前实现文件落点

本轮主线涉及的关键文件包括：

- `custom_addons/chatter_ai_assistant/models/ai_run.py`
- `custom_addons/chatter_ai_assistant/models/mail_message.py`
- `custom_addons/chatter_ai_assistant/models/mail_bot.py`
- `custom_addons/chatter_ai_assistant/tools/openclaw_backends.py`
- `custom_addons/chatter_ai_assistant/tools/worker_service.py`
- `custom_addons/diecut/models/catalog_ai_draft_editor.py`
- `custom_addons/diecut/views/catalog_ai_draft_editor_views.xml`

### 13. 本增补对应的变更摘要

- OdooBot 已成为统一 AI 身份
- OdooBot 私聊已接入 OpenClaw
- `source document` 支持自然语言触发 PDF/TDS 解析与总结
- 草稿编辑页升级为贴近正式物料表单的人工审校界面
- 技术参数改为统一大表编辑
- 系列说明字段已纳入可见、可审、可导入主线
