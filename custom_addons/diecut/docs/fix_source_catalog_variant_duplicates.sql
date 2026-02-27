-- 自动修复脚本：清理 source_catalog_variant_id 的重复映射
-- 目标：每个 source_catalog_variant_id 只保留 1 条 product_template 记录绑定，其他记录置空
--
-- 使用步骤：
-- 1) 先执行 docs/check_source_catalog_variant_duplicates.sql 确认重复情况
-- 2) 在本脚本中选择一种保留策略（A 或 B）
-- 3) 先执行“预览查询”，确认无误后再执行 UPDATE
-- 4) 执行“修复后校验”
--
-- 强烈建议：先备份数据库，再执行。

BEGIN;

-- ============================================================
-- 0) 查看当前重复组（执行前确认）
-- ============================================================
SELECT
    pt.source_catalog_variant_id,
    array_agg(pt.id ORDER BY pt.id) AS duplicated_product_template_ids,
    COUNT(*) AS duplicate_count
FROM product_template pt
WHERE pt.source_catalog_variant_id IS NOT NULL
GROUP BY pt.source_catalog_variant_id
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, pt.source_catalog_variant_id;

-- ============================================================
-- 1) 选择保留策略（A/B 二选一）
-- ============================================================
-- A. 保留最早创建（最小 id）
WITH duplicate_groups AS (
    SELECT source_catalog_variant_id
    FROM product_template
    WHERE source_catalog_variant_id IS NOT NULL
    GROUP BY source_catalog_variant_id
    HAVING COUNT(*) > 1
),
keepers AS (
    SELECT
        pt.source_catalog_variant_id,
        MIN(pt.id) AS keep_id
    FROM product_template pt
    JOIN duplicate_groups dg
      ON dg.source_catalog_variant_id = pt.source_catalog_variant_id
    GROUP BY pt.source_catalog_variant_id
),
to_clear AS (
    SELECT
        pt.id,
        pt.source_catalog_variant_id,
        k.keep_id
    FROM product_template pt
    JOIN keepers k
      ON k.source_catalog_variant_id = pt.source_catalog_variant_id
    WHERE pt.id <> k.keep_id
)
SELECT
    tc.source_catalog_variant_id,
    tc.keep_id,
    array_agg(tc.id ORDER BY tc.id) AS will_clear_ids
FROM to_clear tc
GROUP BY tc.source_catalog_variant_id, tc.keep_id
ORDER BY tc.source_catalog_variant_id;

-- B. 保留最新创建（最大 id）
-- WITH duplicate_groups AS (
--     SELECT source_catalog_variant_id
--     FROM product_template
--     WHERE source_catalog_variant_id IS NOT NULL
--     GROUP BY source_catalog_variant_id
--     HAVING COUNT(*) > 1
-- ),
-- keepers AS (
--     SELECT
--         pt.source_catalog_variant_id,
--         MAX(pt.id) AS keep_id
--     FROM product_template pt
--     JOIN duplicate_groups dg
--       ON dg.source_catalog_variant_id = pt.source_catalog_variant_id
--     GROUP BY pt.source_catalog_variant_id
-- ),
-- to_clear AS (
--     SELECT
--         pt.id,
--         pt.source_catalog_variant_id,
--         k.keep_id
--     FROM product_template pt
--     JOIN keepers k
--       ON k.source_catalog_variant_id = pt.source_catalog_variant_id
--     WHERE pt.id <> k.keep_id
-- )
-- SELECT
--     tc.source_catalog_variant_id,
--     tc.keep_id,
--     array_agg(tc.id ORDER BY tc.id) AS will_clear_ids
-- FROM to_clear tc
-- GROUP BY tc.source_catalog_variant_id, tc.keep_id
-- ORDER BY tc.source_catalog_variant_id;

-- ============================================================
-- 2) 执行修复（默认采用策略 A：保留最小 id）
--    如需策略 B，请把下面 keepers 的 MIN(id) 改成 MAX(id)
-- ============================================================
WITH duplicate_groups AS (
    SELECT source_catalog_variant_id
    FROM product_template
    WHERE source_catalog_variant_id IS NOT NULL
    GROUP BY source_catalog_variant_id
    HAVING COUNT(*) > 1
),
keepers AS (
    SELECT
        pt.source_catalog_variant_id,
        MIN(pt.id) AS keep_id
    FROM product_template pt
    JOIN duplicate_groups dg
      ON dg.source_catalog_variant_id = pt.source_catalog_variant_id
    GROUP BY pt.source_catalog_variant_id
),
to_clear AS (
    SELECT pt.id
    FROM product_template pt
    JOIN keepers k
      ON k.source_catalog_variant_id = pt.source_catalog_variant_id
    WHERE pt.id <> k.keep_id
)
UPDATE product_template pt
SET source_catalog_variant_id = NULL
WHERE pt.id IN (SELECT id FROM to_clear);

-- ============================================================
-- 3) 修复后校验（应返回 0 行）
-- ============================================================
SELECT
    source_catalog_variant_id,
    COUNT(*) AS cnt
FROM product_template
WHERE source_catalog_variant_id IS NOT NULL
GROUP BY source_catalog_variant_id
HAVING COUNT(*) > 1;

-- ============================================================
-- 4) 提交/回滚
-- ============================================================
-- 先检查上面的结果再决定：
-- COMMIT;
ROLLBACK;

