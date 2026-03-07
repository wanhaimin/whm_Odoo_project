# Phase 4 字段映射表（初稿）

本文档给出当前已实现的新旧模型字段映射，作为切换准备基线。

## 1. 模型关系

- 新模型：`diecut.catalog.item`
- 旧模型：`product.template`（系列） + `product.product`（型号）
- 当前新结构不再保留 `legacy_*` 追溯字段。

## 2. 已落地映射（代码已实现）

| 业务含义 | 新模型字段 | 旧模型字段 | 同步方向 | 当前主源 | 备注 |
|---|---|---|---|---|---|
| 名称 | `name` | `product.product.name` | 双向（导入期） | 新 | 单层模型不再区分系列/型号记录 |
| 品牌 | `brand_id` | `product.product.catalog_brand_id` | 双向（导入期） | 新 | |
| 分类 | `categ_id` | `product.product.catalog_categ_id` | 双向（导入期） | 新 | |
| 状态 | `catalog_status` | `product.product.catalog_status` | 双向（导入期） | 新 | |
| 型号编码 | `code` | `product.product.default_code` | 双向（导入期） | 新 | 品牌+编码唯一在新模型强约束 |
| ERP启用 | `erp_enabled` | `product.product.is_activated` | 双向（影子回填 + 双写） | 旧 | |
| ERP产品映射 | `erp_product_tmpl_id` | `product.product.activated_product_tmpl_id` | 双向（影子回填 + 双写） | 旧 | |
| 型号所属系列文本 | `series_text` | `product.template.series_name`（展示口径） | 旧->新（导入期） | 新 | 仅展示维度，不再维护层级关系 |
| TDS附件 | `variant_tds_file` / `variant_tds_filename` | `product.product.variant_tds_file` / `variant_tds_filename` | 双向（影子回填 + 双写） | 旧 | 附件一致性按“是否有文件 + 文件名”比对 |
| MSDS附件 | `variant_msds_file` / `variant_msds_filename` | `product.product.variant_msds_file` / `variant_msds_filename` | 双向（影子回填 + 双写） | 旧 | 同上 |
| 规格书附件 | `variant_datasheet` / `variant_datasheet_filename` | `product.product.variant_datasheet` / `variant_datasheet_filename` | 双向（影子回填 + 双写） | 旧 | 同上 |
| 结构图附件 | `variant_catalog_structure_image` | `product.product.variant_catalog_structure_image` | 双向（影子回填 + 双写） | 旧 | 按是否有图片比对 |
| 胶厚 | `variant_adhesive_thickness` | `product.product.variant_adhesive_thickness` | 双向（影子回填 + 双写） | 旧 | |
| 剥离力 | `variant_peel_strength` | `product.product.variant_peel_strength` | 双向（影子回填 + 双写） | 旧 | |
| 结构描述 | `variant_structure` | `product.product.variant_structure` | 双向（影子回填 + 双写） | 旧 | |
| SUS面剥离力 | `variant_sus_peel` | `product.product.variant_sus_peel` | 双向（影子回填 + 双写） | 旧 | |
| PE面剥离力 | `variant_pe_peel` | `product.product.variant_pe_peel` | 双向（影子回填 + 双写） | 旧 | |
| DuPont冲击 | `variant_dupont` | `product.product.variant_dupont` | 双向（影子回填 + 双写） | 旧 | |
| 推出力 | `variant_push_force` | `product.product.variant_push_force` | 双向（影子回填 + 双写） | 旧 | |
| 可移除性 | `variant_removability` | `product.product.variant_removability` | 双向（影子回填 + 双写） | 旧 | |
| Tumbler滚球 | `variant_tumbler` | `product.product.variant_tumbler` | 双向（影子回填 + 双写） | 旧 | |
| 保持力 | `variant_holding_power` | `product.product.variant_holding_power` | 双向（影子回填 + 双写） | 旧 | |

## 3. 运行时切换策略（当前）

- 参数：`diecut.catalog.read_model`
- 可选值：
  - `legacy_split`（默认）：统一入口指向 `product.product`
  - `new_gray`：统一入口指向 `diecut.catalog.item`
- 控制服务：`diecut.catalog.runtime.service`

## 4. 已对齐的扩展字段（Phase 4 已完成）

以下 `product.product` 业务扩展字段已在新模型 `diecut.catalog.item` 中落地并参与双向同步：

- 技术参数字段：厚度、胶厚、颜色、剥离力、结构描述、胶系、基材、SUS/PE 剥离力、DuPont 冲击、推出力、可移除性、Tumbler 滚球、保持力等
- 合规字段：ROHS、REACH、无卤、防火等级
- 文档字段：TDS/MSDS/规格书文件及文件名、产品结构图
- 参考价：variant_ref_price

后续重点：切换窗口演练与主源切换规则。

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
- 运维向导操作：`新旧附件一致性检查`
- 脚本入口（容器内 Odoo shell）：
  - `/mnt/extra-addons/diecut/scripts/check_shadow_field_parity.py`
