# 模切管理系统 (Diecut ERP) — 设计手册

> **版本**: v1.2
> **模块技术名**: `diecut`
> **Odoo 版本**: 19
> **最后更新**: 2026-02-27
> **维护者**: 开发团队

---

## 目录

1. [系统概述](#1-系统概述)
2. [模块架构](#2-模块架构)
3. [数据模型详解](#3-数据模型详解)
4. [核心业务规则](#4-核心业务规则)
5. [状态机与工作流](#5-状态机与工作流)
6. [视图与菜单结构](#6-视图与菜单结构)
7. [安全与权限](#7-安全与权限)
8. [设计决策记录 (ADR)](#8-设计决策记录-adr)
9. [数据库约束与索引](#9-数据库约束与索引)
10. [变更日志](#10-变更日志)

---

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
│   └── stock_move.py            # 库存移动扩展
├── wizard/
│   └── catalog_activate_wizard.py  # 选型目录启用向导
├── views/
│   ├── material_catalog_views.xml  # ★ 选型目录视图
│   ├── my_material_base_views.xml  # 原材料视图
│   ├── product_category_view.xml   # 分类视图
│   ├── diecut_quote_views.xml      # 报价视图
│   ├── diecut_menu_view.xml        # 菜单定义
│   └── ...其他视图
├── security/
│   └── ir.model.access.csv        # 权限控制
├── data/
│   ├── product_category_data.xml   # 预置分类
│   ├── catalog_sidike_dst_data.xml # 预置选型数据(Sidike DST)
│   └── catalog_sidike_uv_data.xml  # 预置选型数据(Sidike UV)
├── docs/
│   ├── DESIGN_MANUAL.md            # 本文档
│   ├── check_source_catalog_variant_duplicates.sql
│   └── fix_source_catalog_variant_duplicates.sql
└── static/
    └── src/
        ├── scss/                   # 样式
        ├── js/
        │   └── catalog_dynamic_columns.js  # ★ SearchPanel 联动列显隐
        └── xml/                    # 前端模板
```

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

---

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
| `catalog_applications`          | Text                      | 典型应用       | 发布时必填                        |
| `catalog_structure_image`       | Binary                    | 产品结构图     | —                                |
| `catalog_ref_price`             | Float                     | 参考单价       | 仅供选型参考                      |
| `catalog_ref_currency_id`       | Many2one→res.currency    | 参考价币种     | —                                |
| `tds_file` / `tds_filename`   | Binary/Char               | TDS技术数据表  | —                                |
| `msds_file` / `msds_filename` | Binary/Char               | MSDS安全数据表 | —                                |
| `source_catalog_variant_id`     | Many2one→product.product | 源选型目录变体 | 溯源字段，有唯一索引              |
| `replacement_catalog_ids`       | Many2many→self           | 替代系列       | 停产时推荐替代                    |
| `replaced_by_catalog_ids`       | Many2many→self           | 被替代系列     | 反向只读                          |

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

#### 3.2.1 关联/冗余字段（用于列表筛选）

| 字段名                   | Related 来源                             | 说明                                 |
| ------------------------ | ---------------------------------------- | ------------------------------------ |
| `catalog_categ_id`     | `product_tmpl_id.categ_id`             | 分类                                 |
| `catalog_brand_id`     | `product_tmpl_id.brand_id`             | 品牌                                 |
| `catalog_status`       | `product_tmpl_id.catalog_status`       | 目录状态                             |
| `recommendation_level` | `product_tmpl_id.recommendation_level` | 推荐等级                             |
| `catalog_density`      | `product_tmpl_id.density`              | 密度(g/cm³)，型号清单列表中动态显隐 |

#### 3.2.2 变体级技术参数（原文保留）

| 字段名                         | 类型        | 说明         | 示例值              |
| ------------------------------ | ----------- | ------------ | ------------------- |
| `variant_thickness`          | Char        | 厚度         | "35±5 μm"         |
| `variant_adhesive_thickness` | Char        | 胶厚         | "13/13"             |
| `variant_color`              | Char        | 颜色         | "透明"、"黑色"      |
| `variant_peel_strength`      | Char        | 剥离力       | ">800 gf/inch"      |
| `variant_structure`          | Char        | 结构描述     | "胶+PET+胶+白色LXZ" |
| `variant_adhesive_type`      | Char        | 胶系(变体级) | 可覆盖模板级        |
| `variant_base_material`      | Char        | 基材(变体级) | 可覆盖模板级        |
| `variant_sus_peel`           | Char        | SUS面剥离力  | "13.0/13.0 N/cm"    |
| `variant_pe_peel`            | Char        | PE面剥离力   | "7.0/7.0 N/cm"      |
| `variant_dupont`             | Char        | DuPont冲击   | "0.7/0.1"           |
| `variant_tumbler`            | Char        | Tumbler滚球  | "40.0"              |
| `variant_holding_power`      | Char        | 保持力       | "4.0 N/cm"          |
| `variant_note`               | Text        | 型号备注     | —                  |
| `variant_ref_price`          | Float(16,4) | 参考单价     | —                  |

> **设计决策**: 使用 Char 类型而非 Float，因为原厂数据含公差(±)、条件说明、双面参数等复杂格式。

#### 3.2.3 标准化字段（筛选/归类用）

| 字段名                        | 说明       | 自动归一化规则        |
| ----------------------------- | ---------- | --------------------- |
| `variant_thickness_std`     | 标准化厚度 | "35±5 μm" → "35um" |
| `variant_color_std`         | 标准化颜色 | 去多余空格            |
| `variant_adhesive_std`      | 标准化胶系 | 去多余空格            |
| `variant_base_material_std` | 标准化基材 | 去多余空格            |

> 通过 `_normalize_thickness_std()` 和 `_normalize_text_std()` 方法自动从原文字段派生，`create()` / `write()` 时自动同步。支持 `oldname` 从 `*_grade` 字段迁移。

#### 3.2.4 选型目录溯源字段

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
    │  点击"🚀 启用到ERP"
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

### 4.5 变体标准化字段自动同步

当 `product.product` 的原文字段（如 `variant_thickness`）被写入时，自动通过 `_build_variant_std_vals()` 派生标准化字段（如 `variant_thickness_std`）。

**厚度归一化规则** (`_normalize_thickness_std`):

- "35±5 μm" → "35um"
- "0.1mm" → "100um"
- "100" (无单位, >10) → "100um"
- "0.05" (无单位, ≤10) → "50um"

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

## 6. 视图与菜单结构

### 6.1 菜单结构

```
模切管理系统 (menu_diecut_root)
├── 成本计算器              → action_diecut_quote
├── 📚 材料选型大全         → action_material_catalog (product.template, is_catalog=True)
│   ├── ➕ 新建材料系列      → action_material_catalog_create_template
│   └── 📋 材料型号清单     → action_material_catalog_variant (product.product)
├── 原材料                  → action_diecut_raw_material (product.template, is_raw_material=True)
├── 客户管理                → action_diecut_customer
├── 刀模管理                → action_diecut_mold
├── 分切管理                → action_material_slitting
├── 领料申请                → action_requisition_demo
└── 样品订单                → action_sample_order_custom
```

### 6.2 选型目录视图清单

| View ID                                  | 类型   | 模型             | 用途                |
| ---------------------------------------- | ------ | ---------------- | ------------------- |
| `view_material_catalog_form`           | Form   | product.template | 系列详情+变体对比表 |
| `view_material_catalog_tree`           | List   | product.template | 系列级快速浏览      |
| `view_material_catalog_search`         | Search | product.template | 搜索/筛选/分组      |
| `view_material_catalog_variant_tree`   | List   | product.product  | 型号级清单          |
| `view_material_catalog_variant_search` | Search | product.product  | 型号搜索            |

### 6.3 Action 配置

| Action ID                                   | 模型             | Domain                                                           | 说明                                 |
| ------------------------------------------- | ---------------- | ---------------------------------------------------------------- | ------------------------------------ |
| `action_material_catalog`                 | product.template | `is_catalog=True`                                              | 选型大全主入口                       |
| `action_material_catalog_create_template` | product.template | `is_catalog=True`                                              | 新建系列入口                         |
| `action_material_catalog_variant`         | product.product  | `product_tmpl_id.is_catalog=True`                              | 型号清单                             |
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
- 联动列显隐（前端脚本）：当分类路径命中关键词（如“泡棉”“屏蔽材料”“金属箔”“石墨”）时显示 `catalog_density`，否则隐藏

**原材料搜索面板**:

- 材质分类（`raw_material_categ_id`，层级单选，展开）
- 功能类别（`product_tag_ids`，多选）
- 供应商（`main_vendor_id`，多选）
- 品牌（`brand_id`，多选）
- 颜色（`color_id`，多选）

---

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
| sample.order                    | group_user   | ✓ | ✓ |  ✓  |  ✓  |
| sample.order                    | group_portal | ✓ | ✓ |  ✓  |  ✗  |

> 注：`product.template` 和 `product.product` 的权限由 Odoo 原生 `product` 模块管理。

---

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

### ADR-008: SearchPanel 分类联动的动态列显隐

- **背景**: Odoo SearchPanel 不支持“按分类切换不同列表视图/列集”，但业务上需要在同一型号清单中按材料类型动态展示字段（如密度）。
- **决策**: 使用轻量前端脚本 `static/src/js/catalog_dynamic_columns.js`，监听 SearchPanel 交互并按分类路径关键词动态注入 CSS，控制 `th[data-name]` 与 `td[name]` 的显示/隐藏。
- **权衡**: 以较小复杂度实现接近“按分类定制列”的体验；代价是依赖前端 DOM 结构，Odoo 前端升级时需要回归验证。
- **日期**: 2025-01

### ADR-009: 采购模块与选型目录的业务隔离

- **背景**: 选型目录材料用于技术选型，不应参与采购业务。若采购入口不隔离，可能误将选型样本下单。
- **决策**: 采购模块产品入口与采购单产品选择统一过滤 `is_catalog=True`，仅允许 ERP 原材料/可采购产品进入采购流程。
- **权衡**: 业务边界更清晰，能降低误采风险；需要在 Odoo 升级后复核采购 Action/视图继承点。
- **状态**: 已落地。
- **日期**: 2025-01

---

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

## 10. 变更日志

| 日期    | 版本 | 变更内容                                                           | 影响范围                                                                         |
| ------- | ---- | ------------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| 2025-01 | v1.0 | 初始版本：选型目录、原材料、成本计算器、价格统一                   | 全模块                                                                           |
| 2025-01 | v1.0 | 价格统一改版：底层全部按 m² 计价                                  | product_diecut, diecut_quote, requisition                                        |
| 2025-01 | v1.0 | 启用幂等性：行锁 + 唯一索引                                        | product_diecut, catalog_activate_wizard                                          |
| 2025-01 | v1.0 | 添加评审状态、推荐等级、替代系列                                   | product_diecut, material_catalog_views                                           |
| 2025-01 | v1.0 | 标准化字段 *_std：自动归一化 + 聚合索引                            | product_diecut, material_catalog_views                                           |
| 2025-01 | v1.0 | 清理 material_family 特性（已移除）                                | product_category, product_diecut                                                 |
| 2025-01 | v1.2 | 型号清单新增 `catalog_density` 并支持 SearchPanel 联动动态列显隐 | product_diecut, material_catalog_views, static/src/js/catalog_dynamic_columns.js |
| 2025-01 | v1.2 | 库存模块产品入口隔离：排除 `is_catalog=True` 选型目录材料        | views/stock_quant_views.xml                                                      |
| 2025-01 | v1.2 | 采购模块隔离落地：采购入口与采购选料链路排除 `is_catalog=True`   | purchase 相关视图/动作、DESIGN_MANUAL.md                                         |

---

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

*本手册由开发团队维护，如有疑问请联系系统架构师。*
