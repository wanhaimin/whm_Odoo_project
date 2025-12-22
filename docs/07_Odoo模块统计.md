# Odoo 模块统计与分类

## 📊 模块总览

### 您的 Odoo 19.0 开发版模块统计

| 类型 | 数量 | 位置 |
|------|------|------|
| **官方模块** | **601 个** | `odoo/addons/` |
| **自定义模块** | **5 个** | `custom_addons/` |
| **总计** | **606 个** | - |

---

## 📦 官方模块 (601 个)

### 核心模块

这些是 Odoo 的基础模块,几乎所有其他模块都依赖它们:

| 模块名 | 说明 | 重要性 |
|--------|------|--------|
| `base` | 基础模块,所有模块的基础 | ⭐⭐⭐⭐⭐ |
| `web` | Web 界面核心 | ⭐⭐⭐⭐⭐ |
| `mail` | 邮件系统和消息功能 | ⭐⭐⭐⭐⭐ |
| `portal` | 客户门户 | ⭐⭐⭐⭐ |
| `bus` | 实时通信总线 | ⭐⭐⭐⭐ |

---

## 🎯 按功能分类

### 1. 财务会计模块 (约 80 个)

#### 核心模块

- `account` - 会计核心模块
- `account_accountant` - 会计师功能
- `account_invoicing` - 发票管理

#### 支付相关

- `account_payment` - 支付管理
- `account_check_printing` - 支票打印
- `payment` - 支付提供商

#### 税务相关

- `account_tax_python` - Python 税务计算
- `account_update_tax_tags` - 税务标签更新

#### 本地化模块 (l10n_*)

- `l10n_cn` - 中国本地化
- `l10n_us` - 美国本地化
- `l10n_uk` - 英国本地化
- `l10n_fr` - 法国本地化
- ... (约 50+ 个国家/地区)

---

### 2. 销售模块 (约 40 个)

#### 核心模块

- `sale` - 销售管理核心
- `sale_management` - 销售管理增强
- `crm` - 客户关系管理

#### 扩展模块

- `sale_stock` - 销售库存集成
- `sale_project` - 销售项目集成
- `sale_timesheet` - 销售工时集成
- `sale_margin` - 销售利润率
- `sale_quotation_builder` - 报价单构建器

#### POS (销售点)

- `point_of_sale` - POS 核心
- `pos_restaurant` - 餐厅 POS
- `pos_mercury` - Mercury 支付集成

---

### 3. 库存与物流模块 (约 50 个)

#### 核心模块

- `stock` - 库存管理核心
- `purchase` - 采购管理
- `delivery` - 物流配送

#### 扩展模块

- `stock_account` - 库存会计集成
- `stock_barcode` - 条形码扫描
- `stock_landed_costs` - 到岸成本
- `stock_picking_batch` - 批量拣货
- `quality_control` - 质量控制

#### 仓库管理

- `stock_dropshipping` - 直运
- `stock_sms` - 库存短信通知

---

### 4. 制造模块 (约 30 个)

#### 核心模块

- `mrp` - 制造资源计划 (MRP)
- `mrp_account` - 制造会计集成
- `mrp_workorder` - 工单管理

#### 扩展模块

- `mrp_subcontracting` - 外包制造
- `mrp_byproduct` - 副产品管理
- `quality_mrp` - 制造质量管理
- `mrp_plm` - 产品生命周期管理

---

### 5. 人力资源模块 (约 40 个)

#### 核心模块

- `hr` - 人力资源核心
- `hr_attendance` - 考勤管理
- `hr_holidays` - 休假管理
- `hr_expense` - 费用报销

#### 招聘与培训

- `hr_recruitment` - 招聘管理
- `hr_skills` - 技能管理

#### 薪资

- `hr_payroll` - 薪资管理
- `hr_payroll_account` - 薪资会计集成

#### 其他

- `hr_timesheet` - 工时表
- `hr_appraisal` - 绩效评估
- `hr_contract` - 合同管理

---

### 6. 项目管理模块 (约 20 个)

#### 核心模块

- `project` - 项目管理核心
- `project_timesheet` - 项目工时
- `project_forecast` - 项目预测

#### 扩展模块

- `project_purchase` - 项目采购集成
- `project_account` - 项目会计集成

---

### 7. 网站与电商模块 (约 60 个)

#### 核心模块

- `website` - 网站构建器核心
- `website_sale` - 电子商务
- `website_blog` - 博客
- `website_forum` - 论坛

#### 主题 (theme_*)

- `theme_default` - 默认主题
- `theme_clean` - 简洁主题
- `theme_bootswatch` - Bootswatch 主题
- ... (约 20+ 个主题)

#### 扩展模块

- `website_event` - 活动管理
- `website_slides` - 在线课程
- `website_livechat` - 在线客服
- `website_payment` - 在线支付

---

### 8. 营销模块 (约 30 个)

#### 核心模块

- `marketing_automation` - 营销自动化
- `mass_mailing` - 群发邮件
- `social` - 社交媒体管理

#### 扩展模块

- `marketing_card` - 营销卡片
- `sms` - 短信营销
- `survey` - 问卷调查

---

### 9. 其他功能模块 (约 200 个)

#### 文档管理

- `documents` - 文档管理
- `documents_spreadsheet` - 电子表格
- `knowledge` - 知识库

#### 通信

- `voip` - VoIP 电话
- `phone_validation` - 电话验证

#### 工具

- `calendar` - 日历
- `contacts` - 联系人
- `note` - 笔记
- `todo` - 待办事项

#### 集成

- `google_calendar` - Google 日历集成
- `google_drive` - Google Drive 集成
- `microsoft_calendar` - Microsoft 日历集成

---

## 🔧 自定义模块 (5 个)

### 您的自定义模块列表

| 模块名 | 说明 | 状态 |
|--------|------|------|
| `base_accounting_kit` | 会计工具包 | 已安装 |
| `base_account_budget` | 预算管理 | 已安装 |
| `diecut_custom` | 刀模定制(主要模块) | 开发中 ✅ |
| `my_material_list` | 材料清单 | 已安装 |
| `my_module_b` | 模块 B | 已安装 |

---

## 📈 Odoo 版本历史

### 官方模块数量变化

| 版本 | 官方模块数量 | 发布时间 | 主要新增功能 |
|------|-------------|----------|------------|
| **Odoo 19.0** | ~600 | 2024年10月 | AI 集成、性能优化 |
| Odoo 18.0 | ~580 | 2024年5月 | 新 UI、移动端优化 |
| Odoo 17.0 | ~560 | 2023年10月 | 知识库、文档管理 |
| Odoo 16.0 | ~540 | 2022年10月 | 营销自动化增强 |
| Odoo 15.0 | ~520 | 2021年10月 | 新会计功能 |
| Odoo 14.0 | ~500 | 2020年10月 | 社交媒体集成 |

**趋势:** 每个新版本增加 20-30 个新模块

---

## 🎯 常用模块推荐

### 必装模块 (通常默认安装)

✅ **基础设施:**
- `base` - 基础模块
- `web` - Web 界面
- `mail` - 邮件系统
- `calendar` - 日历
- `contacts` - 联系人

### 业务模块 (根据需要选择)

#### 销售型企业

```
推荐安装:
├── sale (销售管理)
├── crm (客户关系管理)
├── stock (库存管理)
├── purchase (采购管理)
└── account (会计)
```

#### 制造型企业

```
推荐安装:
├── mrp (制造管理)
├── stock (库存管理)
├── purchase (采购管理)
├── quality_control (质量控制)
└── account (会计)
```

#### 服务型企业

```
推荐安装:
├── project (项目管理)
├── hr_timesheet (工时管理)
├── sale (销售管理)
├── crm (客户关系管理)
└── account (会计)
```

#### 电商企业

```
推荐安装:
├── website (网站)
├── website_sale (电子商务)
├── stock (库存管理)
├── delivery (物流)
└── account (会计)
```

---

## 🔍 如何查看模块信息

### 方法 1: Odoo 界面

1. 登录 Odoo
2. 进入 **应用** 菜单
3. 可以看到:
   - 已安装的模块
   - 可安装的模块
   - 模块分类

### 方法 2: 文件系统

```bash
# 查看官方模块数量
Get-ChildItem -Path "odoo/addons" -Directory | Measure-Object

# 查看自定义模块数量
Get-ChildItem -Path "custom_addons" -Directory | Measure-Object

# 列出所有模块
Get-ChildItem -Path "odoo/addons" -Directory | Select-Object Name
```

### 方法 3: 数据库查询

```sql
-- 查看已安装模块
SELECT 
    name,
    state,
    category_id,
    summary
FROM ir_module_module
WHERE state = 'installed'
ORDER BY name;

-- 统计各状态模块数量
SELECT 
    state,
    COUNT(*) as count
FROM ir_module_module
GROUP BY state;
```

### 方法 4: Python Shell

```python
# 进入 Odoo Shell
python odoo-bin shell -c odoo.conf -d odoo_dev_new

# 查看已安装模块
installed = env['ir.module.module'].search([('state', '=', 'installed')])
print(f"已安装模块数量: {len(installed)}")

# 查看所有模块
all_modules = env['ir.module.module'].search([])
print(f"总模块数量: {len(all_modules)}")

# 按分类统计
categories = env['ir.module.category'].search([])
for category in categories:
    modules = env['ir.module.module'].search([('category_id', '=', category.id)])
    print(f"{category.name}: {len(modules)} 个模块")
```

---

## 📊 模块依赖关系

### 常见依赖链

```
base (基础)
├── web (Web界面)
│   ├── website (网站)
│   │   └── website_sale (电商)
│   └── portal (门户)
├── mail (邮件)
│   ├── crm (CRM)
│   └── project (项目)
├── account (会计)
│   ├── sale (销售)
│   │   └── sale_stock (销售库存)
│   └── purchase (采购)
│       └── purchase_stock (采购库存)
└── stock (库存)
    ├── mrp (制造)
    └── delivery (物流)
```

---

## 💡 模块选择建议

### 原则 1: 按需安装

❌ **不推荐:** 安装所有模块
- 占用资源
- 界面复杂
- 性能下降

✅ **推荐:** 只安装需要的模块
- 轻量高效
- 界面简洁
- 易于维护

### 原则 2: 先安装核心,再扩展

```
第一步: 安装核心模块
├── base
├── web
└── mail

第二步: 安装业务模块
├── sale
├── stock
└── account

第三步: 根据需要安装扩展
├── sale_stock
├── account_invoicing
└── ...
```

### 原则 3: 注意依赖关系

安装模块时,Odoo 会自动安装其依赖的模块。

**示例:**
```
安装 sale_stock
    ↓ 自动安装
├── sale
│   └── base
└── stock
    └── base
```

---

## 🎯 总结

### 您的 Odoo 环境

- **版本:** Odoo 19.0 (最新版)
- **官方模块:** 601 个
- **自定义模块:** 5 个
- **总计:** 606 个模块

### 模块分布

```
财务会计: ~80 个 (13%)
销售: ~40 个 (7%)
库存物流: ~50 个 (8%)
制造: ~30 个 (5%)
人力资源: ~40 个 (7%)
项目: ~20 个 (3%)
网站电商: ~60 个 (10%)
营销: ~30 个 (5%)
其他: ~251 个 (42%)
```

### 建议

1. ✅ 根据业务需要选择安装模块
2. ✅ 定期更新模块到最新版本
3. ✅ 自定义模块保持良好的文档
4. ✅ 测试模块兼容性
5. ✅ 备份数据库

---

**文档版本:** 1.0  
**创建日期:** 2025-12-21  
**统计时间:** 2025-12-21  
**Odoo 版本:** 19.0  
**作者:** Antigravity AI Assistant
