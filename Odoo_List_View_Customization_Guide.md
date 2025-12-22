# Odoo 列表视图列宽自定义与持久化方案

## 1. 方案概述

本方案解决了 Odoo 列表视图（List View）在某些版本中存在的以下问题：
1. **列宽无法保存**：用户手动拖动列宽后，刷新页面或重启 Odoo 会恢复默认。
2. **表格过度拉伸**：表格会自动填满整个屏幕宽度，导致两列数据时看起来非常空旷，阅读体验差。

**解决方案特点**：
- **纯前端实现**：不依赖服务器后端存储，对服务器性能零影响。
- **LocalStorage 持久化**：使用浏览器本地存储，速度极快。
- **指纹识别技术**：自动识别特定的表格（如材料清单），无需复杂的模型配置。
- **无侵入性**：只影响指定的表格，不影响 Odoo 其他原生模块。

---

## 2. 文件结构

在您的自定义模块（例如 `my_material_list`）中，确保以下文件结构：

```text
my_material_list/
├── __manifest__.py
└── static/
    └── src/
        ├── css/
        │   └── material_list.css       # 样式控制
        └── js/
            └── table_width_controller.js # 核心逻辑
```

---

## 3. 实现步骤

### 第一步：创建 CSS 样式

创建 `static/src/css/material_list.css`。这个文件的作用是防止表格自动填满屏幕，并强制表头居中、数据居右。

```css
/* ==================== 表格宽度控制 ==================== */

/* 1. 多层容器宽度控制 - 防止自动填满视窗 */
.o_content .o_list_view[data-model="my.material"],
.o_content .o_list_view[data-model="my.material.category"] {
    width: fit-content !important; /* 关键：根据内容自适应宽度 */
    max-width: 100% !important;
    min-width: auto !important;
}

/* 2. 列表渲染器层 */
.o_list_view[data-model="my.material"] .o_list_renderer,
.o_list_view[data-model="my.material.category"] .o_list_renderer {
    width: fit-content !important;
    overflow-x: auto !important; /* 允许横向滚动 */
}

/* 3. 表格本身设置 */
.o_list_view[data-model="my.material"] .o_list_table,
.o_list_view[data-model="my.material.category"] .o_list_table {
    width: fit-content !important;
    table-layout: fixed !important; /* 关键：固定布局，尊重列宽设置 */
}

/* 4. 设置最小宽度以保证可读性 */
.o_list_view[data-model="my.material"] .o_list_table {
    min-width: 1200px !important;
}
.o_list_view[data-model="my.material.category"] .o_list_table {
    min-width: 600px !important;
}

/* 5. 防止 Flex 布局强制拉伸 */
.o_list_view[data-model="my.material"],
.o_list_view[data-model="my.material.category"] {
    flex: 0 0 auto !important;
}

/* ==================== 内容对齐控制 ==================== */

/* 表头强制居中 */
.o_list_view[data-model="my.material"] thead th,
.o_list_view[data-model="my.material.category"] thead th {
    text-align: center !important;
    vertical-align: middle !important;
}

/* 数据单元格强制靠右（除了 checkbox 和 操作按钮） */
.o_list_view[data-model="my.material"] tbody td:not(.o_list_record_selector):not(.o_list_actions),
.o_list_view[data-model="my.material.category"] tbody td:not(.o_list_record_selector):not(.o_list_actions) {
    text-align: right !important;
}
```

### 第二步：创建 JavaScript 控制器

创建 `static/src/js/table_width_controller.js`。这是核心逻辑，负责识别表格并保存宽度。

**配置指南**：修改 `MODEL_FINGERPRINTS` 对象，添加您想要管理的模型及其“特征字段”。特征字段是该表格独有的列名（如 'code', 'thickness' 等）。

```javascript
// 纯 JavaScript 实现列宽度记忆功能
// 自动指纹识别模式

(function() {
    'use strict';
    
    // 配置：在此处定义模型及其特征字段
    const MODEL_FINGERPRINTS = {
        'my.material.category': ['name', 'description', '分类名称', '描述'],
        'my.material': ['thickness', 'width', 'code', 'spec', '厚度', '宽度', '规格']
    };

    const STORAGE_PREFIX = 'odoo_column_widths_';
    
    // 识别表格属于哪个模型
    function identifyModel(table) {
        const headers = Array.from(table.querySelectorAll('thead th'));
        const headerKeys = headers.map(th => {
            // 获取列名或 data-name
            return (th.dataset.name || th.getAttribute('name') || th.textContent.trim()).toLowerCase();
        });

        // 遍历配置，寻找匹配的特征
        for (const [model, keywords] of Object.entries(MODEL_FINGERPRINTS)) {
            for (const keyword of keywords) {
                if (headerKeys.includes(keyword)) {
                    return model;
                }
            }
        }
        return null; // 未识别
    }

    // 保存宽度到 LocalStorage
    function saveWidths(model, table) {
        const widths = {};
        const headers = table.querySelectorAll('thead th');
        
        headers.forEach(th => {
            let name = th.dataset.name || th.getAttribute('name');
            // 后备方案：使用文本内容作为键
            if (!name && th.textContent) name = '__text__' + th.textContent.trim();

            if (name && th.offsetWidth > 0) {
                widths[name] = th.offsetWidth;
            }
        });

        if (Object.keys(widths).length > 0) {
            const key = STORAGE_PREFIX + model;
            localStorage.setItem(key, JSON.stringify(widths));
        }
    }

    // 从 LocalStorage 恢复宽度
    function restoreWidths(model, table) {
        const key = STORAGE_PREFIX + model;
        const saved = localStorage.getItem(key);
        if (!saved) return;

        try {
            const widths = JSON.parse(saved);
            const headers = table.querySelectorAll('thead th');

            headers.forEach(th => {
                let name = th.dataset.name || th.getAttribute('name');
                if (!name && th.textContent) name = '__text__' + th.textContent.trim();

                if (name && widths[name]) {
                    const w = widths[name];
                    // 强制应用样式
                    th.style.width = w + 'px';
                    th.style.minWidth = w + 'px';
                    th.style.maxWidth = w + 'px';
                    th.style.boxSizing = 'border-box';
                }
            });
        } catch (e) {
            console.error("Column width restore error:", e);
        }
    }

    // 扫描页面表格的主逻辑
    function processTables() {
        const tables = document.querySelectorAll('table');
        
        tables.forEach(table => {
            // 跳过已处理过的表格
            if (table.dataset.widthProcessed || !table.querySelector('thead th')) return;

            const model = identifyModel(table);
            
            if (model) {
                // 标记为已处理
                table.dataset.widthProcessed = "true";
                
                // 1. 立即恢复宽度
                restoreWidths(model, table);
                
                // 2. 绑定保存事件（防抖动处理）
                const saveHandler = () => setTimeout(() => saveWidths(model, table), 500);
                
                // 监听鼠标抬起（拖动结束）和键盘操作
                table.addEventListener('mouseup', saveHandler);
                table.addEventListener('keyup', saveHandler);
                
                // 监听点击（排序可能导致重绘）
                table.querySelectorAll('thead th').forEach(th => {
                    th.addEventListener('click', saveHandler);
                });
            }
        });
    }

    // === 初始化 ===
    function init() {
        // 前 10 秒高频检查 (500ms)，应对页面刚加载时的动态渲染
        let checks = 0;
        const fastInterval = setInterval(() => {
            processTables();
            checks++;
            if (checks > 20) clearInterval(fastInterval);
        }, 500);

        // 之后进入低频检查模式 (2s)，监控页面跳转
        setInterval(processTables, 2000);
        
        // 使用 MutationObserver 监听 DOM 变化
        const observer = new MutationObserver(() => processTables());
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
    window.addEventListener('load', init);

})();
```

### 第三步：注册 Assets

在 `__manifest__.py` 文件中，将上述两个文件注册到 `web.assets_backend` 中。

```python
'assets': {
    'web.assets_backend': [
        'my_material_list/static/src/css/material_list.css',
        'my_material_list/static/src/js/table_width_controller.js',
    ],
},
```

---

## 4. 如何复用到其他模块？

如果您想在另一个模块（例如 `sales_custom`）中使用此功能：

1. 将 `table_width_controller.js` 复制到新模块。
2. 修改代码顶部的 `MODEL_FINGERPRINTS` 配置：
   ```javascript
   const MODEL_FINGERPRINTS = {
       'sale.order': ['报价单号', 'order_date', '客户'], // 添加新模型的特征
       // ... 
   };
   ```
3. 在新模块的 manifest 中注册文件。
4. 刷新页面，即可生效。

## 5. 性能说明

- **无服务器负载**：所有逻辑在浏览器端运行，不产生 HTTP 请求。
- **智能跳过**：已处理的表格会被忽略，避免重复计算。
- **低资源消耗**：MutationObserver 和低频定时器几乎不占用 CPU。

---

*生成时间: 2025-12-20*
