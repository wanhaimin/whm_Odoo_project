/** @odoo-module */

import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { useEffect } from "@odoo/owl";

/**
 * Patch FormController to support Enter key as Tab navigation
 */
patch(FormController.prototype, {
    setup() {
        super.setup();

        useEffect(
            () => {
                const onKeyDown = (ev) => {
                    // 只处理 Enter 键
                    if (ev.key !== "Enter") {
                        return;
                    }

                    // 忽略修饰键 (Ctrl+Enter 依然是保存)
                    if (ev.ctrlKey || ev.altKey || ev.metaKey || ev.shiftKey) {
                        return;
                    }

                    const target = ev.target;

                    // 如果不是输入框，忽略 (比如按钮上的回车)
                    // 并且如果是 TEXTAREA，回车应该是换行，不能跳转
                    const tagName = target.tagName;
                    if (tagName === "TEXTAREA" || target.isContentEditable) {
                        return;
                    }

                    // 如果是普通 input 或 delect 等
                    if (tagName === "INPUT" || tagName === "SELECT") {
                        ev.preventDefault();
                        ev.stopPropagation();

                        // 寻找下一个 focusable 元素
                        // 利用浏览器原生的 form elements 集合或通过 querySelectorAll
                        // 这里使用一个简单的 querySelector 查找所有可见的 inputs
                        const form = target.closest('.o_form_view') || document.body;
                        const focusables = Array.from(form.querySelectorAll('input, select, textarea, button, [tabindex]'))
                            .filter(el => {
                                // 过滤掉不可见、disabled、或者 tabindex=-1 的
                                return !el.disabled &&
                                    el.offsetParent !== null &&
                                    el.tabIndex !== -1 &&
                                    !el.classList.contains('o_invisible_modifier');
                            });

                        const currentIndex = focusables.indexOf(target);
                        if (currentIndex > -1 && currentIndex < focusables.length - 1) {
                            const next = focusables[currentIndex + 1];
                            next.focus();
                            if (next.select) {
                                next.select(); // 选中内容方便覆盖
                            }
                        }
                    }
                };

                // 绑定到 document 或 form 容器
                // 由于 FormController 渲染的内容可能动态变化，绑定在 window/document Capture 阶段比较稳
                // 但为了不影响全局，我们最好绑定在当前的 root 节点上
                // this.rootRef 在 FormController 中并不总是直接可用，我们用 addEventListener 到 window 但 check context

                // 但 patch setup 里的 useEffect 是最好的位置
                // 我们尝试绑定到 document，但在组件销毁时移除
                document.addEventListener("keydown", onKeyDown, true); // Use capture to intercept before Odoo handles it

                return () => {
                    document.removeEventListener("keydown", onKeyDown, true);
                };
            },
            () => []
        );
    }
});
