# Odoo 学习教程 - 第三阶段:高级精通 (2个月)

> **写给学习者的话:**  
> 恭喜你来到最后阶段!你已经掌握了 Odoo 的核心知识。  
> 第三阶段会学习高级技术,让你成为 Odoo 专家。  
> 这个阶段会有一定难度,但相信你一定可以!加油! 🚀

---

## 📚 第三阶段学习目标

完成本阶段后,你将能够:
- ✅ 开发 JavaScript 自定义组件
- ✅ 创建专业的 PDF 报表
- ✅ 优化系统性能
- ✅ 集成第三方 API
- ✅ 成为 Odoo 专家

---

## 第 17 周:JavaScript 基础

### 第 1 天:为什么需要 JavaScript?

#### 📖 理解 JavaScript 的作用

**用网页来理解:**

```
网页的三个部分:

HTML (结构)     → Odoo 的 XML
CSS (样式)      → Odoo 的 CSS
JavaScript (交互) → Odoo 的 JS

就像:
HTML  = 房子的框架
CSS   = 房子的装修
JS    = 房子的智能系统(自动开灯、温控等)
```

**在 Odoo 中,JavaScript 用于:**
- 动态更新界面
- 自定义组件
- 实时通信
- 复杂交互

---

### 第 2 天:Odoo JavaScript 框架

#### 📖 理解 Odoo 的 JS 框架

**Odoo 使用自己的 JavaScript 框架:**

```javascript
// 定义一个模块
odoo.define('my_module.MyWidget', function (require) {
    "use strict";
    
    // 导入需要的组件
    var Widget = require('web.Widget');
    
    // 创建自定义组件
    var MyWidget = Widget.extend({
        // 组件的模板
        template: 'MyTemplate',
        
        // 组件启动时执行
        start: function () {
            console.log('组件启动了!');
            return this._super.apply(this, arguments);
        },
    });
    
    // 导出组件
    return MyWidget;
});
```

---

### 第 3 天:创建简单的 Widget

#### 🔨 实践:显示欢迎消息

**步骤 1: 创建 JS 文件**

在 `static/src/js/` 文件夹下创建 `my_widget.js`:

```javascript
odoo.define('my_module.WelcomeWidget', function (require) {
    "use strict";
    
    var Widget = require('web.Widget');
    
    var WelcomeWidget = Widget.extend({
        // 使用的模板
        template: 'WelcomeTemplate',
        
        // 事件绑定
        events: {
            'click .welcome-button': '_onButtonClick',
        },
        
        // 按钮点击事件
        _onButtonClick: function (event) {
            event.preventDefault();
            alert('欢迎使用 Odoo!');
        },
    });
    
    return WelcomeWidget;
});
```

**步骤 2: 创建模板**

在 `static/src/xml/` 文件夹下创建 `templates.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates>
    <t t-name="WelcomeTemplate">
        <div class="welcome-widget">
            <h3>欢迎!</h3>
            <button class="welcome-button btn btn-primary">
                点击我
            </button>
        </div>
    </t>
</templates>
```

---

### 第 4-7 天:实践项目

#### 项目:创建一个计数器组件

**功能:**
- 显示当前数字
- 点击按钮增加数字
- 点击按钮减少数字
- 重置按钮

---

## 第 18 周:QWeb 报表

### 第 1 天:什么是 QWeb?

#### 📖 理解 QWeb

**QWeb 是 Odoo 的模板引擎:**

```
就像 Word 的模板:

┌─────────────────────┐
│  公司名称: [____]   │
│  日期: [____]       │
│  ───────────────    │
│  订单明细:          │
│  产品  数量  金额   │
│  ───────────────    │
│  总计: [____]       │
└─────────────────────┘

QWeb 可以生成这样的 PDF 报表
```

---

### 第 2 天:创建简单报表

#### 🔨 实践:订单打印报表

**步骤 1: 定义报表**

在 `reports/` 文件夹下创建 `sale_order_report.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <!-- 定义报表 -->
    <report 
        id="report_sale_order"
        model="my.sale.order"
        string="销售订单"
        report_type="qweb-pdf"
        name="my_module.report_sale_order_document"
        file="my_module.report_sale_order"
    />
    
    <!-- 报表模板 -->
    <template id="report_sale_order_document">
        <t t-call="web.html_container">
            <t t-foreach="docs" t-as="o">
                <t t-call="web.external_layout">
                    <div class="page">
                        <!-- 标题 -->
                        <h2>销售订单</h2>
                        
                        <!-- 订单信息 -->
                        <div class="row mt32">
                            <div class="col-6">
                                <strong>客户:</strong>
                                <span t-field="o.partner_id"/>
                            </div>
                            <div class="col-6">
                                <strong>订单号:</strong>
                                <span t-field="o.name"/>
                            </div>
                        </div>
                        
                        <!-- 订单明细表格 -->
                        <table class="table table-sm mt32">
                            <thead>
                                <tr>
                                    <th>产品</th>
                                    <th class="text-right">数量</th>
                                    <th class="text-right">单价</th>
                                    <th class="text-right">小计</th>
                                </tr>
                            </thead>
                            <tbody>
                                <t t-foreach="o.order_line_ids" t-as="line">
                                    <tr>
                                        <td><span t-field="line.product_id"/></td>
                                        <td class="text-right"><span t-field="line.quantity"/></td>
                                        <td class="text-right"><span t-field="line.price_unit"/></td>
                                        <td class="text-right"><span t-field="line.price_subtotal"/></td>
                                    </tr>
                                </t>
                            </tbody>
                        </table>
                        
                        <!-- 总计 -->
                        <div class="row">
                            <div class="col-6 offset-6">
                                <table class="table table-sm">
                                    <tr>
                                        <td><strong>总计:</strong></td>
                                        <td class="text-right">
                                            <span t-field="o.amount_total"/>
                                        </td>
                                    </tr>
                                </table>
                            </div>
                        </div>
                    </div>
                </t>
            </t>
        </t>
    </template>
</odoo>
```

**理解 QWeb 语法:**

| 语法 | 含义 | 示例 |
|------|------|------|
| `t-foreach` | 循环 | `t-foreach="docs" t-as="o"` |
| `t-field` | 显示字段 | `<span t-field="o.name"/>` |
| `t-if` | 条件判断 | `t-if="o.state == 'sale'"` |
| `t-call` | 调用模板 | `t-call="web.external_layout"` |

---

### 第 3 天:添加条件和循环

#### 🔨 实践:根据状态显示不同内容

```xml
<template id="report_sale_order_document">
    <t t-foreach="docs" t-as="o">
        <div class="page">
            <h2>销售订单</h2>
            
            <!-- 根据状态显示不同的标记 -->
            <div class="ribbon">
                <t t-if="o.state == 'draft'">
                    <span class="badge badge-secondary">草稿</span>
                </t>
                <t t-elif="o.state == 'sale'">
                    <span class="badge badge-success">已确认</span>
                </t>
                <t t-elif="o.state == 'cancel'">
                    <span class="badge badge-danger">已取消</span>
                </t>
            </div>
            
            <!-- 只在有明细时显示表格 -->
            <t t-if="o.order_line_ids">
                <table class="table">
                    <!-- 表格内容 -->
                </table>
            </t>
            <t t-else="">
                <p class="text-muted">暂无订单明细</p>
            </t>
        </div>
    </t>
</template>
```

---

### 第 4-7 天:实践项目

#### 项目:创建完整的订单报表

**功能:**
- 公司 Logo 和信息
- 客户信息
- 订单明细表格
- 小计、税额、总计
- 页眉和页脚
- 多页支持

---

## 第 19 周:性能优化

### 第 1 天:为什么需要优化?

#### 📖 理解性能问题

**用开车来理解:**

```
慢车:
- 加速慢
- 耗油多
- 体验差

快车:
- 加速快
- 省油
- 体验好

Odoo 也一样,需要优化才能快
```

**常见性能问题:**
- 查询太慢
- 页面加载慢
- 计算耗时长

---

### 第 2 天:优化数据库查询

#### 📖 理解查询优化

**不好的查询:**
```python
# ❌ 在循环中查询数据库
for order in orders:
    partner = self.env['res.partner'].browse(order.partner_id.id)
    print(partner.name)
# 如果有 100 个订单,就要查询 100 次!
```

**优化后的查询:**
```python
# ✅ 一次性获取所有数据
orders = self.env['sale.order'].search([])
# Odoo 会自动加载关联的客户数据
for order in orders:
    print(order.partner_id.name)
# 只查询 1-2 次!
```

---

### 第 3 天:使用 mapped 和 filtered

#### 🔨 实践:批量处理数据

**不好的方式:**
```python
# ❌ 使用循环
total = 0
for line in order.order_line_ids:
    total += line.price_subtotal
```

**优化后:**
```python
# ✅ 使用 mapped
total = sum(order.order_line_ids.mapped('price_subtotal'))
```

**过滤数据:**
```python
# ❌ 使用循环
confirmed_orders = []
for order in orders:
    if order.state == 'sale':
        confirmed_orders.append(order)
```

**优化后:**
```python
# ✅ 使用 filtered
confirmed_orders = orders.filtered(lambda o: o.state == 'sale')
```

---

### 第 4 天:添加数据库索引

#### 📖 理解索引

**用字典来理解:**

```
没有索引:
要找"张三",需要从第一页翻到最后一页

有索引:
查目录,直接翻到第 50 页

数据库索引也是这样
```

#### 🔨 实践:添加索引

```python
class SaleOrder(models.Model):
    _name = 'my.sale.order'
    
    name = fields.Char('订单号', index=True)  # 添加索引
    partner_id = fields.Many2one('res.partner', '客户', index=True)
    order_date = fields.Date('订单日期', index=True)
```

**什么时候添加索引:**
- ✅ 经常用于搜索的字段
- ✅ 经常用于排序的字段
- ✅ 外键字段
- ❌ 很少查询的字段
- ❌ 经常更新的字段

---

### 第 5-7 天:性能监控和调优

#### 工具和技巧

1. **启用日志**
   ```python
   import logging
   _logger = logging.getLogger(__name__)
   
   _logger.info('开始处理订单')
   # 处理逻辑
   _logger.info('处理完成')
   ```

2. **使用 SQL 日志**
   ```
   在 odoo.conf 中添加:
   log_level = debug
   ```

3. **使用 profiler**
   ```python
   import cProfile
   cProfile.run('self.process_orders()')
   ```

---

## 第 20 周:API 集成

### 第 1 天:什么是 API?

#### 📖 理解 API

**用餐厅来理解:**

```
你(客户端) → 服务员(API) → 厨房(服务器)

你: "我要一份炒饭"
服务员: 把订单传给厨房
厨房: 做好炒饭
服务员: 把炒饭送给你

API 就是服务员,帮你和服务器沟通
```

---

### 第 2 天:调用外部 API

#### 🔨 实践:获取天气信息

```python
import requests
from odoo import models, fields, api

class City(models.Model):
    _name = 'my.city'
    
    name = fields.Char('城市名称')
    weather = fields.Char('天气', compute='_compute_weather')
    
    def _compute_weather(self):
        for record in self:
            # 调用天气 API
            url = f'https://api.weather.com/v1/weather?city={record.name}'
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                record.weather = data.get('weather', '未知')
            else:
                record.weather = '获取失败'
```

---

### 第 3 天:提供 API 接口

#### 🔨 实践:创建 REST API

```python
from odoo import http
from odoo.http import request
import json

class SaleOrderAPI(http.Controller):
    
    # 获取订单列表
    @http.route('/api/orders', type='json', auth='user', methods=['GET'])
    def get_orders(self):
        orders = request.env['my.sale.order'].search([])
        return [{
            'id': order.id,
            'name': order.name,
            'partner': order.partner_id.name,
            'total': order.amount_total,
        } for order in orders]
    
    # 创建订单
    @http.route('/api/orders', type='json', auth='user', methods=['POST'])
    def create_order(self, **kwargs):
        order = request.env['my.sale.order'].create({
            'partner_id': kwargs.get('partner_id'),
            'order_date': kwargs.get('order_date'),
        })
        return {'id': order.id, 'name': order.name}
```

---

### 第 4-7 天:综合项目

#### 项目:集成微信支付

**功能:**
1. 生成支付二维码
2. 接收支付回调
3. 更新订单状态
4. 发送通知

---

## 第 21-24 周:毕业项目

### 完整的 ERP 模块开发

#### 项目:生产管理系统

**功能模块:**

1. **产品管理**
   - 产品信息
   - 产品分类
   - BOM (物料清单)

2. **生产订单**
   - 创建生产订单
   - 状态流程
   - 物料需求计算

3. **库存管理**
   - 原料入库
   - 成品出库
   - 库存盘点

4. **报表**
   - 生产进度报表
   - 物料消耗报表
   - 成本分析报表

5. **权限**
   - 生产员工
   - 生产主管
   - 仓库管理员

---

## 📚 第三阶段总结

### 你已经学会了

✅ **JavaScript 开发**
- Widget 组件
- 事件处理
- 模板系统

✅ **QWeb 报表**
- PDF 报表
- 模板语法
- 条件和循环

✅ **性能优化**
- 查询优化
- 批量处理
- 索引使用

✅ **API 集成**
- 调用外部 API
- 提供 API 接口
- 数据交互

✅ **综合项目**
- 完整模块开发
- 最佳实践
- 项目管理

---

## 🎓 学习完成!

### 恭喜你!

你已经完成了 Odoo 的全部学习!

现在你是一个 **Odoo 专家**了! 🏆

### 你现在可以:

✅ 开发完整的 Odoo 模块  
✅ 定制和扩展 Odoo  
✅ 优化系统性能  
✅ 集成第三方系统  
✅ 解决复杂的业务需求  

---

## 🚀 继续学习

### 进阶方向

1. **深入学习:**
   - Odoo 源代码阅读
   - 高级 JavaScript
   - 数据库优化

2. **实战经验:**
   - 参与开源项目
   - 接实际项目
   - 分享经验

3. **社区贡献:**
   - 回答问题
   - 写博客
   - 开发插件

---

## 💝 给学习者的话

亲爱的学习者:

恭喜你坚持到最后!

学习编程不容易,尤其是在快五十岁的年纪。

但你做到了!

这证明:
- ✅ 年龄不是障碍
- ✅ 坚持就能成功
- ✅ 学习永远不晚

希望这套教程对你有帮助。

祝你在 Odoo 开发的道路上越走越远!

**加油!** 💪

---

## 📖 附录:常用资源

### 官方资源
- [Odoo 官方文档](https://www.odoo.com/documentation/)
- [Odoo GitHub](https://github.com/odoo/odoo)
- [Odoo Apps Store](https://apps.odoo.com/)

### 学习资源
- [Odoo 中文论坛](https://www.odoo.com/zh_CN/forum)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/odoo)
- [YouTube 教程](https://www.youtube.com/c/Odoo)

### 开发工具
- VS Code + Odoo 插件
- PyCharm + Odoo 插件
- Git 版本控制
- PostgreSQL 管理工具

---

## 📝 学习笔记模板

### 每日学习记录

```
日期: ____年__月__日
学习内容: ________________
学习时长: ____小时
重点内容:
1. ________________
2. ________________
3. ________________

遇到的问题:
1. ________________
   解决方法: ________________

明天计划:
1. ________________
2. ________________
```

---

## 🎯 最后的话

**记住:**

1. **不要着急** - 慢慢来,稳扎稳打
2. **多动手** - 看十遍不如做一遍
3. **不怕错** - 错误是最好的老师
4. **多复习** - 温故而知新
5. **享受过程** - 学习本身就是乐趣

**你一定可以的!** 🌟

---

**文档版本:** 1.0  
**创建日期:** 2025-12-21  
**作者:** Antigravity AI Assistant  
**适用人群:** Odoo 高级学习者

**祝你学习愉快,成为 Odoo 大师!** 🎊
