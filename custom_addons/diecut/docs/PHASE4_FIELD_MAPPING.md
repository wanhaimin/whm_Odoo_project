# Phase 4 字段映射表（初稿）

本文档给出当前已实现的新旧模型字段映射，作为切换准备基线。

## 1. 模型关系

- 新模型：`diecut.catalog.item`
- 旧模型：`product.template`（系列） + `product.product`（型号）
- 追溯字段：
  - `diecut.catalog.item.legacy_tmpl_id` -> `product.template.id`
  - `diecut.catalog.item.legacy_variant_id` -> `product.product.id`

## 2. 已落地映射（代码已实现）

| 业务含义 | 新模型字段 | 旧模型字段 | 同步方向 | 当前主源 | 备注 |
|---|---|---|---|---|---|
| 系列名称 | `name` (series) | `product.template.series_name` | 双向（影子回填 + 双写） | 旧 | `catalog_sync_service` 已覆盖 |
| 系列品牌 | `brand_id` (series) | `product.template.brand_id` | 双向（影子回填 + 双写） | 旧 | |
| 系列分类 | `categ_id` (series) | `product.template.categ_id` | 双向（影子回填 + 双写） | 旧 | |
| 系列状态 | `catalog_status` (series) | `product.template.catalog_status` | 双向（影子回填 + 双写） | 旧 | |
| 型号编码 | `code` (model) | `product.product.default_code` | 双向（影子回填 + 双写） | 旧 | 品牌+编码唯一在新模型强约束 |
| 型号名称 | `name` (model) | `product.product.name` | 双向（影子回填 + 双写） | 旧 | |
| 型号状态 | `catalog_status` (model) | `product.product.catalog_status` | 双向（影子回填 + 双写） | 旧 | |
| 型号品牌 | `brand_id` (model) | `product.product.catalog_brand_id` | 双向（影子回填 + 双写） | 旧 | |
| 型号分类 | `categ_id` (model) | `product.product.catalog_categ_id` | 双向（影子回填 + 双写） | 旧 | |
| ERP启用 | `erp_enabled` | `product.product.is_activated` | 双向（影子回填 + 双写） | 旧 | |
| ERP产品映射 | `erp_product_tmpl_id` | `product.product.activated_product_tmpl_id` | 双向（影子回填 + 双写） | 旧 | |
| 型号归属系列 | `parent_id` | （旧无直接字段） | 旧->新 | 新 | 由系列名/模板映射推导 |

## 3. 运行时切换策略（当前）

- 参数：`diecut.catalog.read_model`
- 可选值：
  - `legacy_split`（默认）：统一入口指向 `product.product`
  - `new_gray`：统一入口指向 `diecut.catalog.item`
- 控制服务：`diecut.catalog.runtime.service`

## 4. 待补充映射（Phase 4 待办）

以下通常属于 `product.product` 的业务扩展字段，需要逐项确认是否迁移到新模型：

- 技术参数字段（厚度、颜色、胶系、基材等）
- 合规字段（ROHS、REACH、无卤、防火等级）
- 文档字段（TDS/MSDS/规格书文件及文件名）
- 价格/参考价字段

说明：第一批技术参数与合规基础字段已在新模型落地（见上表），剩余重点为文档与附件类字段。

每个字段需补充：

- 新模型是否建字段
- 是否需要双写
- 是否保留旧模型只读镜像
- 切换后唯一主源

## 5. 切换门槛建议

- 对账指标持续为 0（缺失/重复/孤儿）
- 已迁移字段抽样一致率 >= 99%
- 管理员灰度运行 >= 1 周
- 回滚演练通过

## 6. 一键校验入口

- 运维向导操作：`新旧字段一致性检查`
- 脚本入口（容器内 Odoo shell）：
  - `/mnt/extra-addons/diecut/scripts/check_shadow_field_parity.py`
