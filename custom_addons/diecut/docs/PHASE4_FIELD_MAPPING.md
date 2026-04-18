# Phase 4 字段映射说明（当前主线）

本文档用于说明 `AI/TDS`、目录导入和后台维护在当前版本中的字段落点。  
本文件只保留当前主线结构，不再继续维护旧参数定义 CSV、旧系列文本字段或旧型号兼容字段口径。

## 1. 当前主线模型

- 系列模型：`diecut.catalog.series`
- 型号模型：`diecut.catalog.item`
- 参数定义：`diecut.catalog.param`
- 分类参数：`diecut.catalog.category.param`
- 参数值：`diecut.catalog.item.spec.line`

## 2. 当前主字段落点

### 2.1 系列级字段

| 业务含义 | 当前字段 |
|---|---|
| 系列名称 | `series_name` |
| 品牌 | `brand_id` / `brand_name` |
| 分类 | `categ_id` / `category_name` |
| 产品描述 | `product_description` |
| 产品特点 | `product_features` |
| 主要应用 | `main_applications` |
| 特殊应用 | `special_applications` |

### 2.2 型号级主字段

| 业务含义 | 当前字段 |
|---|---|
| 型号编码 | `code` |
| 型号名称 | `name` |
| 归属系列 | `series_id` / `series_name` |
| 厚度 | `thickness` |
| 胶厚 | `adhesive_thickness` |
| 颜色 | `color_id` / `color_name` |
| 胶系 | `adhesive_type_id` / `adhesive_type_name` |
| 基材 | `base_material_id` / `base_material_name` |
| 厚度标准值 | `thickness_std` |
| 参考价 | `ref_price` |
| ROHS | `is_rohs` |
| REACH | `is_reach` |
| 无卤 | `is_halogen_free` |
| 防火等级 | `fire_rating` |
| 结构图 | `catalog_structure_image` |

## 3. 技术参数统一落点

以下内容不再直接塞进 `diecut.catalog.item` 主表，而是统一落在参数字典与参数值链路：

- 剥离力
- 剪切强度
- 保持力
- 结构说明
- 储存条件
- 工艺兼容性
- 其他长尾技术指标

对应结构：

- 参数定义：`diecut.catalog.param`
- 分类参数：`diecut.catalog.category.param`
- 参数值：`diecut.catalog.item.spec.line`

## 4. AI/TDS 六桶到五表映射

| 草稿 bucket | 目标结构 |
|---|---|
| `series` | `diecut.catalog.series` |
| `items` | `diecut.catalog.item` |
| `params` | `diecut.catalog.param` |
| `category_params` | `diecut.catalog.category.param` |
| `spec_values` | `diecut.catalog.item.spec.line` |
| `unmatched` | 审核产物，不直接入业务主表 |

## 5. 导入与同步原则

### 5.1 只认当前主线字段

当前导入、校验、同步、预演统一只接受：

- 系列主字段
- 型号主字段
- 参数定义
- 分类参数
- 参数值明细

不再接受以下旧口径：

- 旧参数定义 CSV
- 旧系列文本字段
- 旧型号兼容字段

### 5.2 系列主入口

- 运行时主入口：`series_id`
- 导入与展示口径：`series_name`

### 5.3 长尾参数入口

所有长尾技术参数均通过：

- `param_key`
- `value`
- `unit`
- `test_method`
- `test_condition`
- `remark`

写入 `diecut.catalog.item.spec.line`

## 6. 历史说明

旧 `product.template / product.product` 影子双写、旧型号兼容字段、旧分裂式目录架构仅保留在迁移脚本或历史设计文档中，不再作为当前后台主线设计。  
若后续需要清理更早期的 ERP 影子字段，应另开独立迁移工作包处理。
