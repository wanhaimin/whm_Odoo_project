# Catalog Cutover Runbook

适用范围：`diecut` 模块目录架构切换（`legacy_split` <-> `new_gray`）

目标：在可回滚前提下完成一次受控灰度切换，并产出可审计记录。

## 1. 角色与职责

- 切换负责人（管理员）：执行切换、回滚、结果确认。
- 业务验证人：按清单验证关键流程。
- 记录人：保存执行时间点、结果与异常说明。

## 2. 切换前检查（T-30 分钟）

在 Odoo 容器执行：

```bash
odoo -d odoo -u diecut --stop-after-init --db_host=db --db_user=odoo --db_password=odoo
```

然后执行字段与附件一致性脚本：

```bash
odoo shell -d odoo -c /etc/odoo/odoo.conf --shell-file /mnt/extra-addons/diecut/scripts/check_shadow_field_parity.py --shell-interface=python
```

通过标准：

- `mapped_fields.all_match = true`
- `attachments.all_match = true`

再执行影子对账（运维向导或 shell）：

- `missing_shadow_count = 0`
- `duplicate_brand_code_count = 0`
- `orphan_model_count = 0`

建议最后在运维向导执行一次 `生成切换基线记录`，将结果写入 `运维日志`。

## 3. 切换步骤（T 时刻）

1. 管理员打开 `统一入口切换`。
2. 将模式从 `legacy_split` 切到 `new_gray`。
3. 保存后点击 `打开统一入口`。
4. 开始业务灰度验证（建议 0.5~1 天）。

## 4. 灰度验证清单（业务侧）

至少覆盖以下路径：

- 列表检索：按编码、品牌、状态筛选。
- 表单编辑：名称、编码、技术参数、附件文件名。
- 附件操作：上传/替换 TDS、MSDS、规格书。
- ERP相关：`erp_enabled` 状态查看与修改。
- 运维动作：
  - 新架构字段刷新（旧 -> 新）
  - 新旧字段一致性检查
  - 新旧附件一致性检查
  - 生成切换基线记录

通过标准：

- 页面无阻断错误。
- 保存后一致性检查仍通过。

## 5. 回滚步骤（任意时刻）

触发条件（任一满足即回滚）：

- 关键流程无法完成。
- 一致性检查出现大量异常。
- 业务确认无法继续灰度。

回滚动作：

1. 管理员打开 `统一入口切换`。
2. 将模式改回 `legacy_split` 并保存。
3. 打开统一入口，确认落到旧架构页面。
4. 运行一次对账和一致性脚本并归档。

## 6. 收尾与归档（T+窗口结束）

记录以下信息到发布记录：

- 执行时间（开始/结束）
- 执行人
- 切换前后模式
- 对账结果
- 字段一致性结果
- 附件一致性结果
- 异常与处理结论

## 7. 执行记录模板

```text
日期：
环境：
执行人：

切换前模式：legacy_split / new_gray
切换后模式：legacy_split / new_gray

对账结果：
- missing_shadow_count =
- duplicate_brand_code_count =
- orphan_model_count =

字段一致性：all_match =
附件一致性：all_match =

业务验证结果：通过 / 不通过
异常说明：
回滚是否执行：是 / 否
最终结论：
```
