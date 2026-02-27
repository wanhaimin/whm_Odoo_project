-- 迁移前检查：是否存在“同一目录变体映射多个ERP原材料”
-- 运行方式示例：
-- psql -d <your_db> -f custom_addons/diecut/docs/check_source_catalog_variant_duplicates.sql

-- 1) 查看重复映射明细
SELECT
    pt.source_catalog_variant_id,
    array_agg(pt.id ORDER BY pt.id) AS duplicated_product_template_ids,
    COUNT(*) AS duplicate_count
FROM product_template pt
WHERE pt.source_catalog_variant_id IS NOT NULL
GROUP BY pt.source_catalog_variant_id
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, pt.source_catalog_variant_id;

-- 2) 查看每条重复映射对应的产品名称（便于人工确认保留哪条）
SELECT
    pt.source_catalog_variant_id,
    pt.id AS product_template_id,
    pt.name AS product_template_name,
    pt.default_code
FROM product_template pt
WHERE pt.source_catalog_variant_id IN (
    SELECT source_catalog_variant_id
    FROM product_template
    WHERE source_catalog_variant_id IS NOT NULL
    GROUP BY source_catalog_variant_id
    HAVING COUNT(*) > 1
)
ORDER BY pt.source_catalog_variant_id, pt.id;

-- 3) 清理建议（请先备份，确认后手工执行）：
--    - 每个 source_catalog_variant_id 仅保留 1 条 product_template
--    - 将其余重复记录的 source_catalog_variant_id 置空或删除冗余记录
--
-- 示例（仅示意，勿直接执行）：
-- UPDATE product_template
-- SET source_catalog_variant_id = NULL
-- WHERE id IN (<需要置空的 product_template_id 列表>);
