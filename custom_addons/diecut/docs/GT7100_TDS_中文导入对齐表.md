# 3M GT7100 系列 TDS 中文导入对齐表

## 1. 建议落点

- 品牌：`3M`
- 材料分类：`原材料 / 胶带类 / 泡棉胶带`
- 分类 XMLID：`diecut.category_tape_foam`
- 适用对象：3M 汽车内外饰固定用丙烯酸泡棉胶带

## 2. PDF 内容与系统字段对齐

### 2.1 系列字典 `diecut.catalog.series`

建议新增 1 条系列记录：

- 系列名称：`3M GT7100 系列`
- 品牌：`3M`
- 产品特点：
  - 对汽车漆面与基材具有优异的最终粘接力和保持力
  - 满足多项 OEM 规范要求
  - 可跟随塑料件因温度变化产生的收缩与伸长
  - 粘弹性泡棉芯材具有良好的应力释放与复杂曲面贴服能力
  - 在不同温度条件下保持良好粘接性能
  - 具备耐候、耐溶剂与耐高温能力
- 产品描述：
  - 3M GT7100 系列为汽车外饰与内饰件固定应用设计的丙烯酸泡棉胶带，兼具高柔顺性与优异粘接性能。
- 主要应用：
  - 汽车外饰条固定
  - 汽车内饰件固定

### 2.2 材料型号清单 `diecut.catalog.item`

每个厚度型号单独建 1 条记录：

- `GT7102` `0.2 mm` `灰色`
- `GT7104` `0.4 mm` `灰色`
- `GT7106` `0.6 mm` `灰色`
- `GT7108` `0.8 mm` `灰色`
- `GT7110` `1.0 mm` `灰色`
- `GT7112` `1.2 mm` `灰色`
- `GT7116` `1.6 mm` `灰色`
- `GT7120` `2.0 mm` `灰色`
- `GT7125` `2.5 mm` `灰色`
- `GT7130` `3.0 mm` `白色`
- `GT7135` `3.5 mm` `白色`
- `GT7140` `4.0 mm` `白色`

主字段建议：

- `series_name`：`3M GT7100 系列`
- `catalog_status`：`published`
- `thickness`：对应厚度值
- `color_name`：`灰色` / `白色`
- `adhesive_type_name`：`丙烯酸压敏胶`
- `base_material_name`：`亚克力泡棉`
- `special_applications`：
  - `红色半透明聚乙烯离型膜；离型膜厚度不计入总厚度。`

### 2.3 参数字典 `diecut.catalog.param`

本样本建议把性能表拆成 16 个数值参数：

#### 180 度剥离力

- `peel_180_painted_immediate` 涂装板-即时状态-180度剥离力 `N/cm`
- `peel_180_painted_normal` 涂装板-常温状态-180度剥离力 `N/cm`
- `peel_180_painted_high_temp` 涂装板-高温状态-180度剥离力 `N/cm`
- `peel_180_painted_heat_aging` 涂装板-热老化后-180度剥离力 `N/cm`
- `peel_180_painted_warm_water` 涂装板-温水浸泡后-180度剥离力 `N/cm`
- `peel_180_pvc_immediate` PVC板-即时状态-180度剥离力 `N/cm`
- `peel_180_pvc_normal` PVC板-常温状态-180度剥离力 `N/cm`
- `peel_180_pvc_high_temp` PVC板-高温状态-180度剥离力 `N/cm`
- `peel_180_pvc_heat_aging` PVC板-热老化后-180度剥离力 `N/cm`
- `peel_180_pvc_warm_water` PVC板-温水浸泡后-180度剥离力 `N/cm`

#### 剪切强度

- `shear_painted_pvc_immediate` 涂装板/PVC板-即时状态-剪切强度 `MPa`
- `shear_painted_pvc_normal` 涂装板/PVC板-常温状态-剪切强度 `MPa`
- `shear_painted_pvc_high_temp` 涂装板/PVC板-高温状态-剪切强度 `MPa`
- `shear_painted_pvc_warm_water` 涂装板/PVC板-温水浸泡后-剪切强度 `MPa`
- `shear_painted_pvc_gasoline` 涂装板/PVC板-汽油浸泡后-剪切强度 `MPa`
- `shear_painted_pvc_wax_remover` 涂装板/PVC板-除蜡剂浸泡后-剪切强度 `MPa`

## 3. 不建议拆成参数的内容

以下内容建议保留在系列描述或 `datasheet_content`，不作为结构化参数：

- OEM 规范满足说明
- 贴服性、应力释放等概念性描述
- 保修免责条款
- 联系方式与法规网站地址

## 4. 草稿导入文件

对应草稿 CSV 已生成在：

- `custom_addons/diecut/scripts/tds_import_drafts/gt7100_catalog_series.csv`
- `custom_addons/diecut/scripts/tds_import_drafts/gt7100_catalog_items.csv`
- `custom_addons/diecut/scripts/tds_import_drafts/gt7100_catalog_params.csv`
- `custom_addons/diecut/scripts/tds_import_drafts/gt7100_catalog_category_params.csv`
- `custom_addons/diecut/scripts/tds_import_drafts/gt7100_catalog_item_specs.csv`

这些文件是审阅版草稿，不会自动进入正式导入流程。
