-- ============================================================================
--  清理旧 diecut_knowledge 模块（v1，Notion 块编辑器版本）的数据库残留
--
--  使用方式（推荐顺序）：
--    1) 在 Odoo 内卸载旧模块：开发者模式 -> Apps -> 搜索 "模切知识库" -> Uninstall
--       Odoo 会自动清理 ir_model_data / ir_model_fields / ir_model 中本模块的记录。
--    2) 如果 Odoo 卸载失败、或表/字段残留（升级中常见），用本脚本兜底清理。
--    3) 跑完之后，安装新模块：
--           ./odoo-bin -c <conf> -i diecut_knowledge --stop-after-init
--
--  本脚本设计为 **幂等**：可以反复执行；不存在的对象会被 IF EXISTS 跳过。
--
--  ⚠️  请务必先 pg_dump 备份再执行！
-- ============================================================================

BEGIN;

-- 1) 删除旧模块的数据表（v1 用的是块模型）
DROP TABLE IF EXISTS diecut_kb_block CASCADE;

-- 2) 删除旧 article 表里 v1 才有的列（如果新模块还没装，整张表也会被清掉；
--    如果你打算保留旧表里的少量数据先迁移，请注释下面这行）
DROP TABLE IF EXISTS diecut_kb_article CASCADE;

-- 3) 清理 ir_model_data 残留（模块名字一致，所以 Odoo 卸载已经处理过；
--    这里仅兜底）
DELETE FROM ir_model_data
 WHERE module = 'diecut_knowledge'
   AND model IN (
        'diecut.kb.article',
        'diecut.kb.block',
        'diecut.kb.editor.service',
        'ir.actions.act_window',
        'ir.ui.view',
        'ir.ui.menu',
        'ir.model.access'
   );

-- 4) 清理 ir_model_fields 中 v1 字段残留
DELETE FROM ir_model_fields
 WHERE model IN ('diecut.kb.article', 'diecut.kb.block')
   AND name IN (
        'parent_block_id',
        'child_block_ids',
        'block_ids',
        'depth',
        'block_type',
        'content_json',
        'collapsed',
        'is_archived'
   );

-- 5) 清理 ir_model 中已废弃的 block / editor.service 模型登记
DELETE FROM ir_model
 WHERE model IN ('diecut.kb.block', 'diecut.kb.editor.service');

-- 6) 清理孤儿附件（res_model 指向已删除的 v1 文章）
DELETE FROM ir_attachment
 WHERE res_model IN ('diecut.kb.article', 'diecut.kb.block');

-- 7) 清理 v1 资源/视图的 ir_asset / ir_ui_view 残留（防止 web 启动报错）
DELETE FROM ir_asset
 WHERE path LIKE '/diecut_knowledge/static/src/%';

-- 8) 提示信息
DO $$
BEGIN
    RAISE NOTICE 'diecut_knowledge v1 残留清理完成。下一步：./odoo-bin -i diecut_knowledge';
END
$$;

COMMIT;
