# 模切管理系统 (Diecut ERP) — 设计手册

> **版本**: v1.5
> **模块技术名**: `diecut`
> **Odoo 版本**: 19
> **最后更新**: 2026-03-04
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
│   ├── catalog_shadow_service.py  # 影子回填/对账服务
│   ├── catalog_sync_service.py    # 新旧目录双写同步服务
│   └── catalog_runtime_service.py # 统一入口运行时路由服务
├── wizard/
│   ├── catalog_activate_wizard.py       # 选型目录启用向导
│   ├── catalog_ops_wizard.py            # 数据运维向导
│   ├── catalog_shadow_health_wizard.py  # 迁移健康检查向导
│   └── catalog_runtime_switch_wizard.py # 统一入口切换向导
├── views/
│   ├── material_catalog_views.xml  # ★ 旧架构选型目录视图
│   ├── catalog_item_views.xml      # ★ 新架构灰度视图
│   ├── my_material_base_views.xml  # 原材料视图
│   ├── product_category_view.xml   # 分类视图
│   ├── diecut_quote_views.xml      # 报价视图
│   ├── diecut_menu_view.xml        # 菜单定义
│   └── ...其他视图
├── security/
│   └── ir.model.access.csv        # 权限控制
├── data/
│   ├── product_category_data.xml   # 预置分类
│   ├── catalog_sidike_data.xml     # [自动生成] Sidike 选型大纲骨架
│   ├── catalog_tesa_data.xml       # [自动生成] Tesa 选型大纲骨架
│   ├── catalog_materials.json      # [自动生成] 跨品牌变体技术参数
│   └── load_json_data.xml          # ★ JSON挂载触发器 (noupdate="0")
├── scripts/                        # ★ 数据生成器脚本
│   ├── series.csv                  # [业务维护] 系列与大类总表
│   ├── variants.csv                # [业务维护] 型号与多变体参数总表
│   ├── generate_catalog.py         # CSV -> XML/JSON 生成核心
│   ├── export_from_db.py           # Odoo DB -> CSV 反向导出核心
│   ├── 1_导出Odoo全量物料到Excel.bat  # 快捷运行批处理
│   └── 2_从Excel生成选型目录代码.bat   # 快捷运行批处理
├── docs/
│   ├── DESIGN_MANUAL.md            # 本文档
│   ├── check_source_catalog_variant_duplicates.sql
│   └── fix_source_catalog_variant_duplicates.sql
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

**选型目录硬编码数据与代码生成**：我们采用 Excel (CSV) 驱动的自动代码生成策略（详见 [ADR-011](#8-设计决策记录-adr)）。业务人员维护 `scripts/` 下的 `series.csv` 与 `variants.csv`，运行批处理脚本后，自动产出 `data/catalog_{brand}_data.xml` （作为 Odoo `<record>` 骨架，`noupdate="1"` 以防后期业务分类被覆盖）及 `data/catalog_materials.json`。随后在更新模块时，`load_json_data.xml` (`noupdate="0"`) 会触发 Python 钩子 `_load_catalog_base_data_from_json`，将所有的 JSON 血肉参数智能合并回 `product.product`，彻底做到了防丢失、防覆盖。

### 2.2 模型继承关系图

```
product.template (Odoo 原生)
  └── ProductTemplate (product_diecut.py)
        ├── is_catalog=True  → 选型目录系列
        └── is_raw_material=True → ERP 原材料
              ↑ 启用（一键创建）
              │
product.product (Odoo 原生)
  └── ProductProduct (product_diecut.py)
        └── 选型目录变体（型号级技术参数）

product.supplierinfo (Odoo 原生)
  └── ProductSupplierinfo (product_diecut.py)
        └── 扩展：平米单价、公斤单价、面积/重量缓存

product.category (Odoo 原生)
  └── ProductCategoryExtend (product_category.py)
        └── 三级目录、动态属性定义

diecut.brand          → 品牌主数据
diecut.color          → 颜色主数据
diecut.quote          → 模切报价单
diecut.catalog.activate.wizard → 选型启用向导
```

### 2.3 目录迁移分层架构（Phase 1/2/3）

当前目录迁移采用“可回滚、可灰度、可切换”三层结构：

1. **领域模型层**（`diecut.catalog.item`）
   - 承载新架构系列/型号统一模型、结构约束与关键索引。
   - 通过 `legacy_tmpl_id` / `legacy_variant_id` 保留旧数据映射。
2. **服务层**（`catalog_shadow_service` / `catalog_sync_service` / `catalog_runtime_service`）
   - `catalog_shadow_service`：旧 -> 新影子回填、对账、重复键计算。
   - `catalog_sync_service`：新 -> 旧双写同步（开发期保障兼容）。
   - `catalog_runtime_service`：统一入口运行时路由（旧分栏/新灰度）。
3. **交互与运维层**（Wizard + Menu）
   - `catalog_ops_wizard`：运维操作（回填、对账等）。
   - `catalog_shadow_health_wizard`：迁移健康检查 + 一键查看结构异常。
   - `catalog_runtime_switch_wizard`：统一入口模式切换。

> 设计原则：旧入口、灰度入口、统一入口并存；任何时候都能回到旧架构路径。

---

`<a id="3-数据模型详解"></a>`

## 3. 数据模型详解

### 3.1 ProductTemplate（产品模板扩展）

**模型**: `product.template` | **文件**: `models/product_diecut.py`

> 同一模型通过 `is_catalog` 和 `is_raw_material` 两个布尔标志位区分用途，二者互斥。

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
| `source_catalog_variant_id`     | Many2one→product.product | 源选型目录变体 | 溯源字段，有唯一索引              |
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
| `variant_thickness_std_index`     | 所有变体的 `variant_thickness_std`     | 系列下所有型号的标准厚度值合集 |
| `variant_color_std_index`         | 所有变体的 `variant_color_std`         | 系列下所有型号的标准颜色值合集 |
| `variant_adhesive_std_index`      | 所有变体的 `variant_adhesive_std`      | 系列下所有型号的标准胶系值合集 |
| `variant_base_material_std_index` | 所有变体的 `variant_base_material_std` | 系列下所有型号的标准基材值合集 |

> 这些字段由 `_compute_variant_std_index` 聚合计算，存储于模板层，用于搜索面板和分组过滤。

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
| `variant_diecut_properties`     | 自有，`definition='catalog_categ_id.diecut_properties_definition'` | 变体物理特性：**定义**来自分类（不能为变体单独建定义），**值**每型号独立；需系列已设分类且分类已配置物理特性库方可编辑。变体上不做 related 的 diecut_properties，避免创建变体时 Properties 的 definition_record 解析为 None 导致 RPC 错误 |
| `tds_file` / `tds_filename`   | `product_tmpl_id.tds_file` / `tds_filename`                      | TDS 技术数据表，型号详情页附件                                                                                                                                                                                                                        |
| `msds_file` / `msds_filename` | `product_tmpl_id.msds_file` / `msds_filename`                    | MSDS 安全数据表，型号详情页附件                                                                                                                                                                                                                       |

#### 3.2.2 变体级技术参数（原文保留）

| 字段名                         | 类型        | 说明         | 示例值                       |
| ------------------------------ | ----------- | ------------ | ---------------------------- |
| `variant_thickness`          | Char        | 厚度         | "35±5 μm"                  |
| `variant_adhesive_thickness` | Char        | 胶厚         | "13/13"                      |
| `variant_color`              | Char        | 颜色         | "透明"、"黑色"               |
| `variant_peel_strength`      | Char        | 剥离力       | ">800 gf/inch"               |
| `variant_structure`          | Char        | 结构描述     | "胶+PET+胶+白色LXZ"          |
| `variant_adhesive_type`      | Char        | 胶系(变体级) | 可覆盖模板级                 |
| `variant_base_material`      | Char        | 基材(变体级) | 可覆盖模板级                 |
| `variant_sus_peel`           | Char        | SUS面剥离力  | "13.0/13.0 N/cm"             |
| `variant_pe_peel`            | Char        | PE面剥离力   | "7.0/7.0 N/cm"               |
| `variant_dupont`             | Char        | DuPont冲击   | "0.7/0.1"、"1.3/1.0 [A×cM]" |
| `variant_push_force`         | Char        | 推出力       | "229 N"                      |
| `variant_removability`       | Char        | 可移除性     | 星号等级（与同品类比较）     |
| `variant_tumbler`            | Char        | Tumbler滚球  | "40.0"                       |
| `variant_holding_power`      | Char        | 保持力       | "4.0 N/cm"                   |
| `variant_note`               | Text        | 型号备注     | —                           |
| `variant_ref_price`          | Float(16,4) | 参考单价     | —                           |

> **设计决策**: 使用 Char 类型而非 Float，因为原厂数据含公差(±)、条件说明、双面参数等复杂格式。
>
> **图册符号约定**（录入/识别图册时）：**—**（横线）表示无/没有；**〇** 表示白色；**●** 表示黑色。

#### 3.2.3 标准化字段（筛选/归类用）

| 字段名                        | 说明       | 自动归一化规则        |
| ----------------------------- | ---------- | --------------------- |
| `variant_thickness_std`     | 标准化厚度 | "35±5 μm" → "35um" |
| `variant_color_std`         | 标准化颜色 | 去多余空格            |
| `variant_adhesive_std`      | 标准化胶系 | 去多余空格            |
| `variant_base_material_std` | 标准化基材 | 去多余空格            |

> 通过 `_normalize_thickness_std()` 和 `_normalize_text_std()` 方法自动从原文字段派生，`create()` / `write()` 时自动同步。支持 `oldname` 从 `*_grade` 字段迁移。

#### 3.2.4 变体独立：认证与合规、替代建议、附件与资料

每个型号可拥有独立于系列的值，在型号详情与规格页维护。

| 字段名                                                 | 类型                        | 说明              |
| ------------------------------------------------------ | --------------------------- | ----------------- |
| `variant_is_rohs`                                    | Boolean                     | 该型号 ROHS 认证  |
| `variant_is_reach`                                   | Boolean                     | 该型号 REACH 认证 |
| `variant_is_halogen_free`                            | Boolean                     | 该型号 无卤       |
| `variant_fire_rating`                                | Selection                   | 该型号 防火等级   |
| `variant_replacement_catalog_ids`                    | Many2many→product.template | 该型号 可替代系列 |
| `variant_tds_file` / `variant_tds_filename`        | Binary/Char                 | 该型号 TDS        |
| `variant_msds_file` / `variant_msds_filename`      | Binary/Char                 | 该型号 MSDS       |
| `variant_datasheet` / `variant_datasheet_filename` | Binary/Char                 | 该型号 规格书     |
| `variant_catalog_structure_image`                    | Binary                      | 该型号 产品结构图 |

系列表单中「认证与合规」「替代建议」「附件与资料」为系列默认；各型号在型号详情页可填独立值。关系表：`product_product_catalog_replacement_rel`（`src_variant_id`, `dst_tmpl_id`）。约束：可替代系列不能包含本型号所属系列。

#### 3.2.5 选型目录溯源字段

| 字段名                        | 类型                       | 说明            |
| ----------------------------- | -------------------------- | --------------- |
| `is_activated`              | Boolean                    | 是否已启用到ERP |
| `activated_product_tmpl_id` | Many2one→product.template | 已启用的ERP产品 |

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

将选型目录变体"一键启用"为 ERP 原材料产品：

1. 自动预填产品名称、型号、分类、品牌、材质、厚度
2. 用户补填宽度、长度、形态、供应商
3. 确认后创建新的 `product.template`（`is_raw_material=True`）
4. 设置溯源关联（`source_catalog_variant_id`）
5. 并发保护：`FOR UPDATE` 行锁 + 唯一索引

---

### 3.7 辅助模型

| 模型                              | 文件              | 说明                          |
| --------------------------------- | ----------------- | ----------------------------- |
| `diecut.brand`                  | product_diecut.py | 品牌主数据                    |
| `diecut.color`                  | product_diecut.py | 颜色主数据                    |
| `my.material.requisition`       | requisition.py    | 领料申请（参考价按 m² 单价） |
| `diecut.material.filter.wizard` | diecut_quote.py   | 报价单中的材料筛选向导        |
| `diecut.material.filter.line`   | diecut_quote.py   | 筛选结果行                    |

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
    │  source_catalog_variant_id → 原变体ID (溯源)
    │
    ▼
原变体标记: is_activated=True, activated_product_tmpl_id=新产品ID
```

**幂等保护**:

1. `FOR UPDATE` 行锁防并发
2. 启用前检查 `source_catalog_variant_id` 是否已存在对应产品
3. 数据库唯一索引 `diecut_product_template_source_catalog_variant_uidx`

### 4.5 技术参数自动归一化 (Normalization)

为了平衡“原厂数据完整性”与“系统检索效率”，系统采用了“原文”+“标准化快照”的双字段设计。当变体的原文字段（如 `variant_thickness`）被写入时，系统会自动通过 `_build_variant_std_vals()` 派生对应的标准化字段。

#### 4.5.1 字段职责分工

| 类别                 | 字段属性                 | 核心职责                                                                     | 业务场景                                                        |
| :------------------- | :----------------------- | :--------------------------------------------------------------------------- | :-------------------------------------------------------------- |
| **原文描述**   | `variant_color` 等     | **保留原样**。包含原产地语言、公差、测试条件、双面差异等所有技术细节。 | 型号详情页、规格对比表、正式技术文档导出。                      |
| **标准化快照** | `variant_color_std` 等 | **归一化处理**。去除空格、特殊符号、修正同义词、统一单位。             | **SearchPanel (搜索面板) 统计**、分组过滤、看板卡片展示。 |

#### 4.5.2 归一化核心价值

1. **解决检索歧义**：将不同厂商对相同特征的不同描述（如 "Black", "黑色", "BK"）在后台逻辑中尝试对齐，确保搜索“黑色”时能一次性搜出所有相关型号。
2. **支撑侧边搜索面板 (SearchPanel)**：Odoo 19 的搜索面板需要对数据进行分组统计。直接使用含有空格和特殊符号的原文会导致选项极其零碎且存在大量同义词。使用归一化字段能显著提升侧边栏的整洁度和选择效率。
3. **驱动系列级自动填充**：系列级字段（如 `variant_color_std_index`）会自动聚合下属所有变体的 `_std` 字段进行去重排序。使用归一化字段作为源，可以确保系列级的汇总结果（如 "黑色, 透明"）不仅美观且准确。

#### 4.5.3 归一化处理规则

- **厚度归一化** (`_normalize_thickness_std`):
  - 规则：提取核心数值，并统一单位至 `um`。
  - 示例："35±5 μm" → "35um"；"0.1mm" → "100um"；"100" (无单位且 >10) → "100um"；"0.05" (无单位且 ≤10) → "50um"。
- **文本归一化** (`_normalize_text_std`):
  - 适用字段：颜色 (`variant_color`)、胶系 (`variant_adhesive_type`)、基材 (`variant_base_material`)。
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
| **向上汇总** | 子 → 主 | `compute` + `@api.depends` | **型号颜色/厚度汇总** (`variant_color_std_index`)。子表型号变动，主表索引自动刷新。                |
| **向下继承** | 主 → 子 | `related`                    | **共有属性**（品牌、厂家、分类）。主表修改，所有子表实时且只读地同步。                               |
| **独立存储** | N/A      | 默认 (无特殊属性)              | **差异化参数**。主表的 `thickness` (数字索引) 与子表的 `variant_thickness` (原厂文字) 互不干扰。 |

#### 4.8.2 核心控制参数

- **`compute`**: 用于主表统计子表数据。
- **`related`**: 用于子表镜像主表数据，确保“系列级属性”的一致性。
- **`inverse`**: 允许通过修改计算字段来反向改写数据源（本模块慎用）。
- **`onchange`**: 仅用于 UI 编辑时的实时预览反馈。

#### 4.8.3 导入时的自动补齐

当通过 CSV/JSON 导入型号数据时，系统具备“自动填空”能力：

- 若 JSON 中缺失归一化字段（如 `variant_color_std`），系统在 `write` 时会检测到原文变更，从而自动触发归一化计算进行补齐。
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

当 ERP 原材料（`product.template`）被删除时，`unlink()` 会自动重置对应选型目录变体的 `is_activated=False` 和 `activated_product_tmpl_id=False`。

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
├── 📚 材料选型大全         → action_material_catalog (product.template, is_catalog=True)
│   ├── ➕ 新建材料系列      → action_material_catalog_create_template
│   ├── 📋 材料型号清单     → action_material_catalog_variant_split (product.product, 分屏)
│   └── 📄 材料型号清单(列表) → action_material_catalog_variant (product.product, 纯列表)
├── 原材料                  → action_diecut_raw_material (product.template, is_raw_material=True)
├── 客户管理                → action_diecut_customer
├── 刀模管理                → action_diecut_mold
├── 分切管理                → action_material_slitting
├── 领料申请                → action_requisition_demo
└── 样品订单                → action_sample_order_custom
```

### 6.2 选型目录视图清单

| View ID                                      | 类型   | 模型             | 用途                           |
| -------------------------------------------- | ------ | ---------------- | ------------------------------ |
| `view_material_catalog_form`               | Form   | product.template | 系列详情+变体对比表            |
| `view_material_catalog_tree`               | List   | product.template | 系列级快速浏览                 |
| `view_material_catalog_search`             | Search | product.template | 搜索/筛选/分组                 |
| `view_material_catalog_variant_tree`       | List   | product.product  | 型号级清单                     |
| `view_material_catalog_variant_split_tree` | List   | product.product  | 型号清单（分屏入口）           |
| `view_material_catalog_variant_form`       | Form   | product.product  | 型号详情与规格页               |
| `view_material_catalog_variant_split_form` | Form   | product.product  | 分屏右侧型号表单（去 chatter） |
| `view_material_catalog_variant_search`     | Search | product.product  | 型号搜索                       |

### 6.3 Action 配置

| Action ID                                   | 模型             | Domain                                                           | 说明                                 |
| ------------------------------------------- | ---------------- | ---------------------------------------------------------------- | ------------------------------------ |
| `action_material_catalog`                 | product.template | `is_catalog=True`                                              | 选型大全主入口                       |
| `action_material_catalog_create_template` | product.template | `is_catalog=True`                                              | 新建系列入口                         |
| `action_material_catalog_variant_split`   | product.product  | `product_tmpl_id.is_catalog=True`                              | 型号清单（分屏主入口）               |
| `action_material_catalog_variant`         | product.product  | `product_tmpl_id.is_catalog=True`                              | 型号清单（纯列表回退入口）           |
| `action_diecut_raw_material`              | product.template | `is_raw_material=True`                                         | ERP原材料                            |
| `stock.product_template_action_product`   | product.template | `is_catalog=False`                                             | 库存模块产品模板列表（排除选型目录） |
| `stock.stock_product_normal_action`       | product.product  | `product_tmpl_id.is_catalog=False`                             | 库存模块产品变体列表（排除选型目录） |
| `stock.action_product_stock_view`         | product.product  | `detailed_type='product' and product_tmpl_id.is_catalog=False` | 库存在手产品视图（排除选型目录）     |

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

**型号清单搜索面板**:

- 材料分类（`catalog_categ_id`，层级单选）
- 品牌（`catalog_brand_id`，多选）
- 列显隐（前端脚本 `catalog_dynamic_columns.js`，**仅材料型号清单生效**）：① 密度列仅在选择泡棉/屏蔽材料/金属箔/石墨等分类时显示；② **全空列自动隐藏**：当选择某一类时，若某列在当前结果集中全部为空（无值）则自动隐藏该列。原材料等其它列表视图不执行上述逻辑，避免误隐藏列影响体验。

#### 6.5.1 不同分类列表显示不同字段 — 规则与配置（Owl VDOM 补丁）

**设计目的**：同一张型号清单列表，随左侧材料分类切换而显示不同列集，使每类材料只展示相关字段，减少空列干扰。

**显隐规则（二者叠加）**：

| 规则                       | 说明                                                                                           | 适用范围                                                               |
| -------------------------- | ---------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **按分类显示指定列** | 某列仅在选中的分类路径命中配置的“关键词”时允许显示；否则强制隐藏。                           | 当前仅配置了密度列 `catalog_density`：泡棉、屏蔽材料、金属箔、石墨。 |
| **全空列自动隐藏**   | 对当前拉取到的所有记录逐列判断：若该列在所有当前页的记录中均无有效值，则彻底从渲染队列里剔除。 | 仅材料型号清单；原材料等其它列表不生效。                               |

**配置与实现机制（Owl Patch）**：

- **实现文件**：`static/src/js/catalog_dynamic_columns.js`。
- **Odoo 19 正规做法**：脚本不再注入 CSS 或者粗暴操作 DOM。相反，它使用了 `@web/core/utils/patch` 对 `@web/views/list/list_renderer` 的 `getActiveColumns()` 方法进行了补丁（Patch）。
- **拦截逻辑**：在 Owl 系统准备把字段列传递给虚拟 DOM（VDOM）渲染之前，拦截并检查当前视图是否为“材料型号清单”（依据是否同时拥有 `product_tmpl_id` 和 `catalog_categ_id`）。如果是，则通过遍历 `this.props.list.records` 并判定每列数据。
- **全空列隐藏**：如果判定某列在所有 `records` 中的 `val` 全都是空的（如 `false`, `null`, `""`, `0` 或者像 `—`、`...`），那么这列就会从返回的 `columns` 数组里被移除，渲染引擎根本就不会为该列生成 `<th>` 或 `<td>`。
- **优势**：这种方法与 Odoo 底层框架**完全兼容**。它不会引起 DOM 冲突报错，性能消耗极低，并且跟那些依赖点击、轮询、重写样式的“黑魔法”比起来更稳定，页面跳转与操作也不会再受到定时刷新的影响。

#### 6.5.2 SearchPanel 默认规则：该分类没有数据则默认不显示

**结论**：逻辑一致。Odoo SearchPanel 的默认行为就是：**若某分类（或某选项）在当前 domain 下没有任何记录，则不会作为可选值出现在面板中**。

### 6.6 型号详情与规格页（变体 Form）

**目的**：为每个产品变体（材料型号）提供类似“产品详情与规格”的单页，便于工程师/销售查看技术参数、应用、特性评级与附件。

**实现方式**：

- **视图**：`view_material_catalog_variant_form`（`product.product` 的 form 视图），仅在从「材料型号清单」入口打开单条型号时使用（通过 Action `view_ids` 绑定）。
- **布局**：顶部为产品结构图或主图（优先该型号独立 `variant_catalog_structure_image`，否则系列/主图）、型号编码与系列名、产品描述、主要应用；中部为技术特性与型号技术参数；Notebook 含「特性评级」「粘合特性」「认证与合规」「替代建议」「附件与资料」——**认证与合规、替代建议、附件与资料**均为该型号独立字段（`variant_*`），每个变体单独拥有各自的值；系列表单中对应三项为系列默认，各型号可在本页覆盖或单独填写。
- **数据来源**：变体自身字段（`variant_*`、`catalog_*` 等）及系列上的关联展示字段。为在变体 form 中展示系列内容，在 `ProductProduct` 上增加了关联字段：`catalog_structure_image`、`catalog_features`、`catalog_applications`、`tds_file`/`tds_filename`、`msds_file`/`msds_filename`，均 `related='product_tmpl_id.xxx'`；变体物理特性使用自有字段 `variant_diecut_properties`（不在变体上做 related 的 diecut_properties，避免创建变体时报错）。
- **入口**：
  - 分屏主入口：材料选型大全 → 材料型号清单（`action_material_catalog_variant_split`），点击左侧行在右侧面板加载该 Form。
  - 纯列表入口：材料选型大全 → 材料型号清单(列表)（`action_material_catalog_variant`），按 Odoo 原生列表→表单流程打开。
  - 列表/表单上的「启用到ERP」「已启用ERP」按钮保留并统一图标样式。

**变体动态属性**：变体可以拥有自己的**属性值**，但不能单独建**属性定义**。

- **定义**：沿用 Odoo 机制，Properties 的“定义”（有哪些项、类型、选项）必须来自某条定义记录；当前实现中变体与系列共用**材料分类**上的 `diecut_properties_definition`，即定义在「产品分类」中配置，变体无法单独建一套只属于自己的定义。
- **值**：每个变体可存自己的值，字段为 `variant_diecut_properties`（`definition='catalog_categ_id.diecut_properties_definition'`），在变体 Form「特性评级」页编辑。视图中需包含 definition record（如 `catalog_categ_id`），且该变体所属系列已设置材料分类、该分类下已配置「物理特性库」，否则前端可能不提供编辑或无法保存。

**扩展**：若需“粘合特性”结构化（如按基材+时间点存 N/cm），可后续增加 `diecut.adhesion.test_result` 等 one2many 模型并在本 Form 的「粘合特性」页嵌入列表；当前用 `variant_note` 做文字说明。

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

以材料选型大全的 **产品系列表单 (view_material_catalog_form)** 为例，结构如下：

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

**目标**：在一个页面中实现“左侧型号列表 + 右侧可编辑表单”，减少列表/表单来回切换。

**实现组成**：

- **自定义视图类型**：`js_class="diecut_split_list"`（挂载于 `view_material_catalog_variant_split_tree`）。
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
- Key：`diecut_split_layout:product.product:variant`
- 存储内容：`layoutMode`、`splitRatio`

**性能策略**：

- 拖拽分隔条使用 `requestAnimationFrame` 节流；拖动中优先更新 CSS 变量，`mouseup` 再提交最终比例。
- 拖动中临时禁用右侧表单的 pointer events，降低重渲染带来的卡顿感。

**编辑能力与权限说明**：

- 右侧内嵌 Form 视图使用 `view_material_catalog_variant_split_form`（去 chatter，聚焦编辑）。
- 为满足业务编辑需求，内部用户组已补充 `product.product` 读/写/创建权限（不含删除），用于型号清单分屏编辑。

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
| product.product                 | group_user   | ✓ | ✓ |  ✓  |  ✗  |
| sample.order                    | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| sample.order                    | group_portal | ✓ | ✓ |  ✓  |  ✗  |

> 注：为支持「材料型号清单」分屏右侧直接编辑，本模块在 `security/ir.model.access.csv` 中额外授予 `base.group_user` 对 `product.product` 的读/写/创建权限（不授予删除）。

---

`<a id="8-设计决策记录-adr"></a>`

## 8. 设计决策记录 (ADR)

### ADR-001: 价格统一按平方米计价

- **背景**: 模切行业中，材料有卷料、片料之分，供应商报价可能按卷/按公斤/按平方米。价格字段语义不一致会导致报价核算错误。
- **决策**: 系统底层 `seller.price` 和 `price_per_m2` 统一存储**每平方米单价**。整卷/片价格为派生值 (`price_m2 × 面积`)。
- **权衡**: 牺牲了与 Odoo 原生 `seller.price`（通常是 per-unit 价格）的语义一致性，但消除了多处价格换算的歧义。
- **日期**: 2025-01

### ADR-002: 选型目录与ERP原材料共用 product.template

- **背景**: 选型目录（材料手册）和 ERP 原材料（实际采购件）都涉及"材料"，需决定是否拆分为独立模型。
- **决策**: 共用 `product.template`，通过 `is_catalog` 和 `is_raw_material` 互斥标志位区分。
- **权衡**: 减少代码重复，可复用 Odoo 原生产品功能（变体、供应商、图片等），但需要严格的互斥约束和 domain 过滤。
- **日期**: 2025-01

### ADR-003: 变体技术参数使用 Char 类型

- **背景**: 原厂数据格式多样，如厚度 "35±5 μm"、剥离力 ">800 gf/inch"、胶厚 "13/13"。
- **决策**: 变体技术参数（`variant_thickness`, `variant_peel_strength` 等）使用 `Char` 类型保留原文。另加 `*_std` 字段存储归一化值用于筛选。
- **权衡**: 查询效率略低，但保留了数据完整性和可读性。
- **日期**: 2025-01

### ADR-004: 启用到ERP的幂等性保障

- **背景**: 多用户同时在选型目录中点击"启用到ERP"，可能导致重复创建 ERP 原材料。
- **决策**: 三重保护：① `FOR UPDATE` 行锁防并发 ② 创建前二次查询检查 ③ 数据库 UNIQUE INDEX（partial）。
- **权衡**: 性能略有开销（行锁），但确保了数据一致性。
- **辅助工具**: `docs/check_source_catalog_variant_duplicates.sql` 和 `docs/fix_source_catalog_variant_duplicates.sql` 用于历史数据修复。
- **日期**: 2025-01

### ADR-005: 供应商价格表的影子缓存字段

- **背景**: Odoo 的 `onchange` 在编辑状态下，子表（`seller_ids`）无法实时获取父表（`product.template`）未保存的规格变更。
- **决策**: 在 `product.supplierinfo` 上增加 `calc_area_cache` 和 `calc_weight_cache` 影子字段，父表 `onchange` 时主动推送最新面积/重量。
- **权衡**: 增加了两个技术字段，但解决了 Odoo onchange 的上下文隔离问题。
- **日期**: 2025-01

### ADR-006: 使用 oldname 进行字段迁移

- **背景**: 标准化字段从 `variant_thickness_grade` 改名为 `variant_thickness_std`。
- **决策**: 使用 Odoo 字段的 `oldname` 属性，让 ORM 自动处理数据库列重命名。
- **权衡**: 比 `pre_init_hook` 更简洁，但仅适用于简单的字段重命名。
- **日期**: 2025-01

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
- **范围**: 适用于需要增强展示体验的核心模块表单（如材料选型大全）。
- **状态**: 已落地；在 `view_material_catalog_form` 中全面实装。
- **日期**: 2026-03

### ADR-011: 多变体产品数据初始化的生成器策略 (Excel/CSV -> XML + JSON)

- **背景**: 在 Odoo 核心机制中，如果使用 XML 的 `<record>` 为 `product.template` 挂载属性（Attribute Lines），系统会后台自动生成一堆空壳变体。如果手写 `<record>` 写入变体的特有参数（如厚度、初粘力等），不仅代码极其臃肿，而且容易覆盖业务数据的修改。早前尝试过手写 JSON 并用 `post_init_hook` 拦截，但 `post_init_hook` 仅在首次安装生效，不支持后续的模块升级 (`Upgrade`)。同时，针对品牌分散、文件繁多的情况，手动维护 `__manifest__.py` 容易遗漏新生成的 XML 文件，导致数据“离奇失踪”。
- **决策**: 采用 **“Excel/CSV 业务驱动代码生成 + 自动注册”** 的大厂企业级策略：
  1. 彻底拥抱 Python 脚本生成器（`scripts/generate_catalog.py`）。通过开放 `series.csv`（系列大表）和 `variants.csv`（型号大表）供非技术人员用 Excel 直接维护。
  2. 脚本运行后，自动生成标准的 `data/catalog_{brand}_data.xml` 和 `data/catalog_materials.json`。
  3. **注册自动化**: 脚本在结束前会**自动扫描并覆写 `__manifest__.py` 里的 `data` 列表**。它会精准定位 `catalog_*.xml` 文件并按顺序注册到触发器 `load_json_data.xml` 之前。
  4. 采用后置触发器 (`noupdate="0"`) 驱动 `_load_catalog_base_data_from_json` 钩子，根据 JSON 内容动态装填变体（使用 `getattr` 防覆盖机制）。
- **权衡**: 彻底将业务数据维护权释放给业务端，且实现了从“数据录入”到“manifest 注册”的全链路 100% 自动化，根绝了因手动漏写配置文件导致的功能异常。
- **日期**: 2026-03

### ADR-012: 双向同步机制与“主动清除”逻辑 (Field Clearing)

- **背景**: 早期同步方案仅支持覆盖（Overwrite）或忽略。用户反馈在 CSV 中把某个格子的值删掉置空后，Odoo 系统里对应的字段依然保留旧值，无法实现“删除”或“清空”的业务意图。同时，用户在 Odoo UI 界面手动修改的名字（如修复笔误）在导出后容易丢失中文语境。
- **决策**: 引入 **双向闭环同步 (Bi-directional Closure)** 与 **主动清除逻辑**:
  1. **导出加持 (export_from_db.py)**: 导出脚本强制注入 `{'lang': 'zh_CN'}` 上下文。确保 Odoo 界面里通过中文 UI 改写过的字段（Stored Translations）能精准导出到 CSV，不会因为导出时缺少语境而退化回旧的英文底稿名（如 CCCCCCC）。
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
- **决策**: 在 `product.product` 型号清单上引入 `diecut_split_list` 视图：
  1. 继承 `web.ListView`，将模式切换按钮插入 `control-panel-navigation-additional` 插槽（原生位置）；
  2. 采用 OI 图标与 `o_cp_switch_buttons` / `o_switch_view` 样式；
  3. 保留三种模式：左右/上下/仅列表；
  4. 右侧表单使用专用 `view_material_catalog_variant_split_form`（去 chatter），支持直接编辑；。
- **权衡**: 前端实现复杂度提高（Controller + Renderer + XML 继承 + 状态同步），但显著提升了操作效率与一致性，且与 Odoo 原生 UI 视觉语言对齐。
- **日期**: 2026-03

---

`<a id="9-数据库约束与索引"></a>`

## 9. 数据库约束与索引

### SQL 约束

| 模型             | 约束名               | 类型                    | 说明           |
| ---------------- | -------------------- | ----------------------- | -------------- |
| product.category | `name_parent_uniq` | UNIQUE(name, parent_id) | 同层级不能重名 |

### 自定义索引

| 索引名                                                  | 表               | 列                        | 类型             | 条件                                        |
| ------------------------------------------------------- | ---------------- | ------------------------- | ---------------- | ------------------------------------------- |
| `diecut_product_template_source_catalog_variant_uidx` | product_template | source_catalog_variant_id | UNIQUE (partial) | WHERE source_catalog_variant_id IS NOT NULL |

> 在 `init()` 方法中创建，升级前会检测历史重复数据，如有重复则抛出错误要求先清理。

### Python 约束

| 方法                                      | 触发字段                    | 说明                     |
| ----------------------------------------- | --------------------------- | ------------------------ |
| `_check_catalog_raw_material_exclusive` | is_catalog, is_raw_material | 互斥                     |
| `_check_source_catalog_variant_unique`  | source_catalog_variant_id   | 唯一映射                 |
| `_check_catalog_replacements`           | replacement_catalog_ids     | 不能包含自己、非目录产品 |

---

`<a id="10-变更日志"></a>`

## 10. 变更日志

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
| 2025-01 | v1.2 | 认证与合规、替代建议、附件与资料改为每变体独立：variant_* 字段、变体 Form 三页、系列为默认 | product_diecut.py、material_catalog_views.xml、DESIGN_MANUAL 3.2.4 / 6.6         |

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

- **原理**: 通过 `scripts/export_from_db.py` 导出的 `series.csv` 和 `variants.csv` 实际上包含了一家模切厂最核心的材料库知识。
- **价值**: 即便整库丢失，只要保留这两个 CSV，通过 `generate_catalog.py` 可以在任何新的 Odoo 系统中物理级重构所有产品模板、变体及物理参数。
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
