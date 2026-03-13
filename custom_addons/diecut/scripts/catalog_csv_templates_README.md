# Catalog CSV Templates

- `catalog_items.csv`: 主表导入文件（一行一个型号）
- `catalog_item_specs.csv`: 技术参数值导入文件（一行一条参数值）
- `catalog_spec_defs.csv`: 技术参数定义导入文件（一行一条定义）
- `catalog_series.csv`: 系列模板导入文件（一行一个品牌系列）
- `catalog_items_template.csv`: 主表模板示例
- `catalog_item_specs_template.csv`: 参数值模板示例
- `catalog_spec_defs_template.csv`: 参数定义模板示例
- `catalog_series_template.csv`: 系列模板示例

## 推荐顺序

1. 导入 `catalog_spec_defs.csv`（参数定义）
2. 导入 `catalog_series.csv`（系列模板）
3. 导入 `catalog_items.csv`（型号主表）
4. 导入 `catalog_item_specs.csv`（技术参数值）
5. 在系统中执行“补齐参数模板”

## 主键与约束

- 主表唯一键：`brand + code`
- 参数值唯一键：`brand + item_code + param_key`
- 参数定义唯一键：`categ_id_xml + param_key`
- 系列模板唯一键：`brand + series_name`

## 系列字段规则

- 主列：`series_name`
- 兼容列：`series_text`（迁移期兼容读取，不建议新模板继续使用）
- 品牌解析优先级：`brand_id_xml` > `brand_name`
- `catalog_items.csv` 可选新增：`special_applications`（型号特殊应用，型号独立维护）

## 系列强同步说明（v1.8.1）

- 型号侧 `product_features / product_description / main_applications` 为系列模板强同步字段。
- 导入主表时，即使主表 CSV 传入上述三列，若型号绑定 `series_name`，最终仍以系列模板值为准。
- 仅 `special_applications` 作为型号层可编辑补充，不参与系列模板同步。
