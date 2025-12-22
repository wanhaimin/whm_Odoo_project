/** @odoo-module **/

import { browser } from "@web/core/browser/browser";

/**
 * 该脚本实现了在 Odoo 19 列表和表单视图中，按下回车键（Enter）自动跳转到下一个输入框的功能。
 * 它模拟了 Tab 键的行为，提升数据录入效率。
 */

document.addEventListener("keydown", (ev) => {
    // 只处理 Enter 键，排除 Shift/Ctrl/Alt 组合键
    if (ev.key === "Enter" && !ev.shiftKey && !ev.ctrlKey && !ev.altKey && !ev.metaKey) {
        const target = ev.target;

        // 只拦截 input 和 select 标签
        const isInput = target.tagName === "INPUT" || target.tagName === "SELECT";
        if (!isInput) return;

        // 排除以下特殊场景，在这些场景下保留 Enter 的原生功能
        if (target.type === "button" || target.type === "submit" || target.type === "reset") return;
        if (target.type === "checkbox" || target.type === "radio") return;

        // 如果自动完成下拉框正在显示，回车应该用于确认选择而非跳格
        if (document.querySelector(".o-autocomplete--dropdown")) return;

        // 如果是日期选择器，回车用于确认日期而非跳格
        if (target.classList.contains("o_datepicker_input")) return;

        // 确认当前元素属于 Odoo 的表单或列表容器
        const isOdooView = target.closest(".o_form_view, .o_list_renderer");
        if (isOdooView) {
            // 阻止 Odoo 默认的 Enter 行为（如列表跳行或触发保存）
            ev.preventDefault();
            ev.stopPropagation();

            // 1. 尝试通过模拟 Tab 键盘事件来触发 Odoo 内部的单元格切换逻辑
            // 这对 Odoo 的列表（List View）内联编辑模式非常有效
            const tabEvent = new KeyboardEvent("keydown", {
                key: "Tab",
                code: "Tab",
                keyCode: 9,
                which: 9,
                bubbles: true,
                cancelable: true,
                shiftKey: false
            });

            target.dispatchEvent(tabEvent);

            // 2. 如果 10ms 后焦点仍未改变（说明不是在 Odoo List 内联编辑模式），则执行手动查找并聚焦
            setTimeout(() => {
                if (document.activeElement === target) {
                    // 获取页面上所有可见且未禁用的可聚焦元素
                    const focusable = Array.from(document.querySelectorAll('input:not([disabled]):not([readonly]):not([type="hidden"]), select:not([disabled]):not([readonly]), textarea:not([disabled]):not([readonly]), [tabindex]:not([tabindex="-1"])'))
                        .filter(el => {
                            const style = window.getComputedStyle(el);
                            return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0;
                        });

                    const index = focusable.indexOf(target);
                    if (index > -1 && index < focusable.length - 1) {
                        const nextElement = focusable[index + 1];
                        nextElement.focus();

                        // 自动选中新输入框的内容，方便直接修改
                        if (['text', 'number', 'password', 'search', 'tel', 'url'].includes(nextElement.type)) {
                            // 加上延时确保焦点已经稳定
                            setTimeout(() => {
                                nextElement.select?.();
                            }, 10);
                        }
                    }
                }
            }, 50);
        }
    }
}, true); // 使用捕获阶段 (Capture) 以确保在 Odoo 逻辑之前拦截
