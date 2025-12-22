// 纯 JavaScript 实现列宽度记忆功能 - 最终版
// 不依赖 Odoo 模块系统，不依赖 URL 或 DOM 属性，直接识别表头特征

(function () {
    'use strict';

    // 配置：通过表头中的字段名或文本内容来识别模型
    const MODEL_FINGERPRINTS = {
        'my.material.category': ['name', 'description', '分类名称', '描述'],
        'my.material': ['thickness', 'width', 'code', 'spec', '厚度', '宽度', '规格']
    };

    const STORAGE_PREFIX = 'odoo_column_widths_';

    // 识别表格属于哪个模型
    function identifyModel(table) {
        const headers = Array.from(table.querySelectorAll('thead th'));
        const headerKeys = headers.map(th => {
            return (th.dataset.name || th.getAttribute('name') || th.textContent.trim()).toLowerCase();
        });

        for (const [model, keywords] of Object.entries(MODEL_FINGERPRINTS)) {
            for (const keyword of keywords) {
                if (headerKeys.includes(keyword)) {
                    return model;
                }
            }
        }
        return null;
    }

    // 保存宽度
    function saveWidths(model, table) {
        const widths = {};
        const headers = table.querySelectorAll('thead th');

        headers.forEach(th => {
            let name = th.dataset.name || th.getAttribute('name');
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

    // 恢复宽度
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

    // 核心处理函数
    function processTables() {
        const tables = document.querySelectorAll('table');

        tables.forEach(table => {
            if (table.dataset.widthProcessed || !table.querySelector('thead th')) return;

            const model = identifyModel(table);

            if (model) {
                table.dataset.widthProcessed = "true";

                // 1. 立即恢复宽度
                restoreWidths(model, table);

                // 2. 绑定事件用于保存
                const saveHandler = () => setTimeout(() => saveWidths(model, table), 500);

                table.addEventListener('mouseup', saveHandler);
                table.addEventListener('keyup', saveHandler);

                table.querySelectorAll('thead th').forEach(th => {
                    th.addEventListener('click', saveHandler);
                });
            }
        });
    }

    // 初始化
    function init() {
        // 高频检查，前10秒
        let checks = 0;
        const fastInterval = setInterval(() => {
            processTables();
            checks++;
            if (checks > 20) clearInterval(fastInterval);
        }, 500);

        // 之后进入低频检查模式
        setInterval(processTables, 2000);

        // 监听 DOM 变化
        const observer = new MutationObserver(() => processTables());
        observer.observe(document.body, { childList: true, subtree: true });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
    window.addEventListener('load', init);

})();
