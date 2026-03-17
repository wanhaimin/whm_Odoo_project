# Catalog CSV Templates (5-Table System)

This project uses a unified 5-table import contract for catalog + TDS AI outputs:

1. `catalog_series.csv` - 系列主数据（系列公共信息）
2. `catalog_items.csv` - 型号主数据（高频搜索主字段）
3. `catalog_params.csv` - 参数字典（参数定义 + AI 路由元数据）
4. `catalog_category_params.csv` - 分类参数策略（分类与参数绑定）
5. `catalog_item_specs.csv` - 参数值事实表（性能/测试/条件值）

`unmatched` does not go directly into business tables. It is exported for review.

## Import Order

1. 导入 `catalog_params.csv`
2. 导入 `catalog_category_params.csv`
3. 导入 `catalog_series.csv`
4. 导入 `catalog_items.csv`
5. 导入 `catalog_item_specs.csv`

## Keys

- 型号主键：`brand + code`
- 参数值主键：`brand + item_code + param_key`
- 分类参数主键：`category + param_key`
- 系列主键：`brand + series_name`

## Encoding

- All CSV files must be UTF-8 (`utf-8` or `utf-8-sig`).
- Non UTF-8 files are rejected during precheck.
